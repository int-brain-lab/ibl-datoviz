import ctypes
import json
from argparse import ArgumentParser
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from examples import review_common
from examples.review_common import add_review_arguments, finish_review
from ibl_datoviz import interaction_benchmark, interaction_checkpoint
from ibl_datoviz.viewer import AtlasViewer


def test_show_runner_owns_setup_loop_and_cleanup():
    viewer = AtlasViewer.__new__(AtlasViewer)
    viewer._closed = False
    viewer._close_pending = False
    viewer._gui_callback_error = None
    calls = []
    viewer._create_view = lambda **kwargs: calls.append(('create', kwargs))
    viewer.dvz = SimpleNamespace(
        dvz_app_run=lambda app, frames: calls.append(('run', app, frames))
    )
    viewer.app = 'app'

    def runner(current, run_loop):
        assert current is viewer
        calls.append(('runner-start',))
        run_loop()
        calls.append(('runner-stop',))

    viewer.show(title='fixture', frame_count=3, runner=runner)
    assert calls == [
        ('create', {'offscreen': False, 'title': 'fixture'}),
        ('runner-start',),
        ('run', 'app', 3),
        ('runner-stop',),
    ]


def test_show_runner_failure_still_processes_pending_close():
    viewer = AtlasViewer.__new__(AtlasViewer)
    viewer._closed = False
    viewer._close_pending = True
    viewer._gui_callback_error = None
    viewer._create_view = lambda **_kwargs: None
    viewer.close = lambda: setattr(viewer, 'closed_by_show', True)
    with pytest.raises(RuntimeError, match='runner failed'):
        viewer.show(runner=lambda *_args: (_ for _ in ()).throw(RuntimeError('runner failed')))
    assert viewer.closed_by_show


def test_panel_rect_snapshot_copies_layout_and_releases_native_snapshots():
    class Rect(ctypes.Structure):
        _fields_ = [
            ('x', ctypes.c_float),
            ('y', ctypes.c_float),
            ('width', ctypes.c_float),
            ('height', ctypes.c_float),
        ]

    class FrameInfo(ctypes.Structure):
        _fields_ = [('struct_size', ctypes.c_uint32), ('panel_rect_px', Rect)]

    released = []

    def resolve(panel):
        return ctypes.c_void_p(id(panel))

    def get_info(snapshot, output):
        info = output._obj
        index = int(snapshot.value) % 9
        info.panel_rect_px = Rect(index, index + 1, 100 + index, 200 + index)
        return True

    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            dvz_panel_resolve_frame=resolve,
            dvz_panel_frame_info=get_info,
            dvz_panel_frame_unref=lambda snapshot: released.append(snapshot.value),
            DvzPanelFrameInfo=FrameInfo,
        ),
        _linked=SimpleNamespace(slice_panels={'ap': object(), 'ml': object(), 'dv': object()}),
        panel=object(),
    )
    rectangles = review_common._panel_rects(viewer)
    assert tuple(rectangles) == ('ap', 'ml', 'dv', '3d')
    assert all(len(rect) == 4 for rect in rectangles.values())
    assert len(released) == 4


def test_panel_rects_use_alignment_safe_native_getters():
    class Rect(ctypes.Structure):
        _fields_ = [
            ('x', ctypes.c_float),
            ('y', ctypes.c_float),
            ('width', ctypes.c_float),
            ('height', ctypes.c_float),
        ]

    def getter(panel, output):
        rect = output._obj
        rect.x, rect.y, rect.width, rect.height = 1, 2, 3, 4
        return True

    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            DvzRect=Rect,
            dvz_panel_inner_rect_px=getter,
            dvz_panel_plot_rect_px=getter,
        ),
        _linked=SimpleNamespace(slice_panels={'ap': object(), 'ml': object(), 'dv': object()}),
        panel=object(),
    )
    result = review_common._panel_rects(viewer)
    assert result['ap'] == {'inner': [1.0, 2.0, 3.0, 4.0], 'plot': [1.0, 2.0, 3.0, 4.0]}
    assert tuple(result) == ('ap', 'ml', 'dv', '3d')


def test_fixture_warmup_requests_each_frame_before_layout_capture():
    requests = []
    steps = []
    outcomes = iter([0, 1] * review_common.INPUT_FIXTURE_WARMUP_FRAMES)

    class Readiness:
        def check(self):
            return SimpleNamespace(status='ready')

    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            dvz_view_request_frame=lambda view: requests.append(view) or 0,
            dvz_app_step=lambda app, timeout: steps.append((app, timeout)) or next(outcomes),
        ),
        app='app',
        view='view',
    )
    review_common._settle_linked_readiness(
        viewer, Readiness(), warmup_frames=review_common.INPUT_FIXTURE_WARMUP_FRAMES
    )
    assert len(requests) == review_common.INPUT_FIXTURE_WARMUP_FRAMES == 8
    assert len(steps) == 16


def test_fixture_warmup_fails_on_retained_callback_error():
    class Readiness:
        def check(self):
            return SimpleNamespace(status='ready')

    viewer = SimpleNamespace(
        _gui_callback_error=RuntimeError('GUI draw failed'),
        dvz=SimpleNamespace(
            dvz_view_request_frame=lambda _view: 0,
            dvz_app_step=lambda _app, _timeout: 1,
        ),
        app='app',
        view='view',
    )
    with pytest.raises(RuntimeError, match='gui_callback failed during fixture setup'):
        review_common._settle_linked_readiness(viewer, Readiness(), warmup_frames=1)


def test_fixture_preflight_rejects_transient_sidebar_layout():
    viewer = SimpleNamespace(
        width=800,
        height=600,
        sidebar_width=280,
        ui_scale=1.0,
        _sidebar=SimpleNamespace(sidebar_rect=(0, 0, 48, 59)),
    )
    with pytest.raises(RuntimeError, match='sidebar layout did not stabilize'):
        review_common._fixture_preflight(viewer)


def test_review_arguments_and_validation_preserve_normal_path(tmp_path):
    parser = ArgumentParser()
    add_review_arguments(parser)
    args = parser.parse_args([])
    assert args.record_input is None and args.replay_input is None

    viewer = SimpleNamespace(show=lambda **kwargs: pytest.fail('normal path uses show directly'))
    args = SimpleNamespace(
        frames=0,
        offscreen=None,
        record_input=None,
        replay_input=None,
        replay_mode='paced',
        replay_report=None,
    )
    calls = []
    viewer.show = lambda **kwargs: calls.append(kwargs)
    finish_review(viewer, args, 'title')
    assert calls == [{'title': 'title', 'frame_count': 0}]


@pytest.mark.parametrize(
    'updates, message',
    [
        ({'record_input': Path('record'), 'replay_input': Path('replay')}, 'mutually exclusive'),
        ({'record_input': Path('record'), 'offscreen': Path('capture.png')}, 'interactive host'),
        ({'replay_mode': 'controlled'}, 'requires --replay-input'),
        ({'replay_report': Path('report.json')}, 'requires --replay-input'),
    ],
)
def test_review_input_options_reject_incompatible_combinations(updates, message):
    args = SimpleNamespace(
        frames=0,
        offscreen=None,
        record_input=None,
        replay_input=None,
        replay_mode='paced',
        replay_report=None,
    )
    for key, value in updates.items():
        setattr(args, key, value)
    viewer = SimpleNamespace(_linked=SimpleNamespace(cursor=object()), slices=object())
    with pytest.raises(ValueError, match=message):
        finish_review(viewer, args, 'title')


def _runner_fakes(monkeypatch, trace):
    calls = []

    class Fixture:
        initial_state = {'camera': {'angles': [0.0, 0.0, 0.0]}}
        metadata = {}

        @classmethod
        def capture(cls, *_args, **_kwargs):
            calls.append(('fixture-captured', _kwargs['metadata']))
            return cls()

        def assert_compatible(self, observed):
            if observed != self.metadata:
                raise ValueError('fixture mismatch')

        def to_dict(self):
            return {'initial_state': self.initial_state, 'metadata': self.metadata}

    class Readiness:
        def __init__(self, _viewer):
            calls.append(('readiness-attached',))

        def check(self):
            return SimpleNamespace(ready=True, status='ready', to_dict=lambda: {'status': 'ready'})

        def checkpoint(self, *, render_proof):
            assert render_proof is None
            return SimpleNamespace(to_dict=lambda: {'status': 'unavailable'})

        def close(self):
            calls.append(('readiness-closed',))

    monkeypatch.setattr(interaction_benchmark, 'ReviewFixture', Fixture)
    monkeypatch.setattr(interaction_benchmark, 'LinkedReadiness', Readiness)
    monkeypatch.setattr(interaction_benchmark, 'scientific_state', lambda _viewer: {'camera': {}})
    monkeypatch.setattr(interaction_checkpoint, 'scientific_state', lambda _viewer: {'camera': {}})

    class Recorder:
        def __init__(self, *_args, **kwargs):
            calls.append(('recorder-created', kwargs['fixture']))

        def start(self):
            calls.append(('recorder-started',))

        def stop(self, *, cancel=False):
            calls.append(('recorder-cancel', cancel))
            calls.append(('recorder-stopped',))
            return 'trace-data'

    class Player:
        def __init__(self, *_args):
            calls.append(('player-created',))

        def run(self, *_args, finalize, **_kwargs):
            calls.append(('player-run',))
            finalization = finalize(lambda: calls.append(('finalization-pump',)))
            return {'ok': True, 'finalization': finalization}

    replay = SimpleNamespace(Recorder=Recorder, Player=Player)

    def plain(value):
        if isinstance(value, Mapping):
            return {str(key): plain(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [plain(item) for item in value]
        return value

    trace_io = SimpleNamespace(read_trace=lambda _path: trace, plain=plain)
    writes = []
    trace_io.write_trace = lambda value, path: writes.append((value, path))
    viewer = SimpleNamespace(
        _linked=SimpleNamespace(cursor=object(), slice_panels={}),
        slices=object(),
        mapping='allen',
        width=800,
        height=600,
        ui_scale=1.0,
        app='app',
        view='view',
        dvz=SimpleNamespace(
            dvz_app_step=lambda _app, _timeout: 1,
            dvz_view_request_frame=lambda _view: 0,
        ),
        _sidebar=SimpleNamespace(sidebar_rect=(0.0, 0.0, 240.0, 600.0)),
        panel='panel',
        review_fixture_options={},
    )
    args = SimpleNamespace(
        record_input=Path('trace.json'),
        replay_input=None,
        replay_mode='paced',
        replay_report=None,
        offscreen=None,
    )
    monkeypatch.setattr(
        review_common,
        '_input_options',
        lambda *_args: (
            args.record_input,
            args.replay_input,
            args.replay_mode,
            args.replay_report,
        ),
    )
    return calls, writes, viewer, args, replay, trace_io


def test_record_runner_stops_and_writes_trace_when_host_loop_raises(monkeypatch):
    calls, writes, viewer, args, replay, trace_io = _runner_fakes(monkeypatch, None)
    with pytest.raises(RuntimeError, match='loop failed'):
        review_common._input_runner(
            viewer,
            args,
            replay,
            trace_io,
            title='review',
            app_id='2',
            preset='overlay',
            run_loop=lambda: (_ for _ in ()).throw(RuntimeError('loop failed')),
        )
    assert ('recorder-started',) in calls
    assert ('recorder-cancel', False) in calls
    assert ('recorder-stopped',) in calls
    assert writes == [('trace-data', args.record_input)]
    assert calls[-1] == ('readiness-closed',)


def test_replay_rejects_cross_app_fixture_before_player_dispatch(monkeypatch):
    trace = SimpleNamespace(
        manifest={
            'fixture': {
                'metadata': {},
                'app_id': '1',
                'preset': 'overlay',
                'initial_state': {'camera': {'angles': [0.0, 0.0, 0.0]}},
            }
        }
    )
    calls, _writes, viewer, args, replay, trace_io = _runner_fakes(monkeypatch, trace)
    args.record_input = None
    args.replay_input = Path('trace.json')
    with pytest.raises(ValueError, match='different review app'):
        review_common._input_runner(
            viewer,
            args,
            replay,
            trace_io,
            title='review',
            app_id='2',
            preset='overlay',
            run_loop=lambda: pytest.fail('replay does not call the recording loop'),
        )
    assert not any(call[0] == 'player-created' for call in calls)
    assert calls[-1] == ('readiness-closed',)


def test_replay_report_labels_display_checkpoint_unavailable(tmp_path, monkeypatch):
    trace = SimpleNamespace(
        manifest=MappingProxyType(
            {
                'fixture': MappingProxyType(
                    {
                        'metadata': MappingProxyType({}),
                        'app_id': '2',
                        'preset': 'overlay',
                        'initial_state': MappingProxyType(
                            {'camera': MappingProxyType({'angles': (0.0, 0.0, 0.0)})}
                        ),
                    }
                )
            }
        )
    )
    calls, _writes, viewer, args, replay, trace_io = _runner_fakes(monkeypatch, trace)
    args.record_input = None
    args.replay_input = Path('trace.json')
    args.replay_report = tmp_path / 'report.json'
    review_common._input_runner(
        viewer,
        args,
        replay,
        trace_io,
        title='review',
        app_id='2',
        preset='overlay',
        run_loop=lambda: pytest.fail('replay does not call the recording loop'),
    )
    report = json.loads(args.replay_report.read_text())
    assert report['ok'] is True
    finalization = report['finalization']
    assert finalization['ibl_display_checkpoint']['status'] == 'unavailable'
    assert finalization['ibl_benchmark_verdict'] == 'unavailable'
    assert finalization['ibl_terminal_comparison']['status'] == 'unavailable'
    assert 'intermediate work' in finalization['ibl_benchmark_verdict_reason']
    assert ('player-run',) in calls
    metadata = next(call[1] for call in calls if call[0] == 'fixture-captured')
    assert metadata['layout_warmup_frames'] == 8


def test_record_terminal_checkpoint_rehash_preserves_input_duration(monkeypatch, tmp_path):
    checkpoint = {'status': 'ready', 'scope': 'designated-terminal-source-capture'}
    monkeypatch.setattr(
        interaction_checkpoint, 'capture_terminal_checkpoint', lambda *_args, **_kwargs: checkpoint
    )
    manifest = {
        'fixture': {'app_id': '2'},
        'windows': {'host-0': {}},
        'duration_ns': '12345',
        'required_capabilities': ['mouse'],
        'adapter_platform': 'linux',
    }
    trace = SimpleNamespace(manifest=manifest, observations=('event',))
    builds = []

    def build_trace(observations, windows, **kwargs):
        builds.append((observations, windows, kwargs))
        return 'freshly-hashed-trace'

    codec = SimpleNamespace(plain=lambda value: value, build_trace=build_trace)
    assert (
        review_common._record_terminal_trace(
            object(), object(), trace, codec, tmp_path / 'manifest.json'
        )
        == 'freshly-hashed-trace'
    )
    assert builds[0][0] == ('event',)
    assert builds[0][2]['duration_ns'] == 12345
    assert builds[0][2]['fixture']['terminal_checkpoint'] == checkpoint
    assert manifest['fixture'] == {'app_id': '2'}


@pytest.mark.parametrize('status', ['mismatch', 'unavailable'])
def test_required_terminal_checkpoint_cannot_be_silently_downgraded(status):
    with pytest.raises(RuntimeError, match='terminal checkpoint failed'):
        review_common._validate_terminal_report(
            {
                'ibl_final_slice_readiness': {'status': 'ready'},
                'ibl_display_checkpoint': {'status': 'ready'},
                'ibl_terminal_comparison': {'status': status},
                'ibl_terminal_checkpoint_required': True,
            }
        )


def test_replay_preserves_report_before_raising_terminal_capture_error(tmp_path, monkeypatch):
    trace = SimpleNamespace(
        manifest={
            'fixture': {
                'metadata': {},
                'app_id': '2',
                'preset': 'overlay',
                'initial_state': {'camera': {'angles': [0.0, 0.0, 0.0]}},
            }
        }
    )
    _calls, _writes, viewer, args, replay, trace_io = _runner_fakes(monkeypatch, trace)
    args.record_input, args.replay_input = None, Path('manifest.json')
    args.replay_report = tmp_path / 'report.json'
    monkeypatch.setattr(
        interaction_checkpoint,
        'capture_terminal_checkpoint',
        lambda *_args, **_kwargs: {'status': 'error', 'error': 'capture failed'},
    )
    with pytest.raises(RuntimeError, match='terminal checkpoint failed'):
        review_common._input_runner(
            viewer,
            args,
            replay,
            trace_io,
            title='review',
            app_id='2',
            preset='overlay',
            run_loop=lambda: pytest.fail('unexpected recording loop'),
        )
    report = json.loads(args.replay_report.read_text())
    assert report['finalization']['ibl_display_checkpoint']['error'] == 'capture failed'


def test_normal_recording_completion_explicitly_cancels_before_checkpoint(monkeypatch):
    calls, writes, viewer, args, replay, trace_io = _runner_fakes(monkeypatch, None)

    def terminal(*_args):
        assert ('recorder-cancel', True) in calls
        calls.append(('terminal-checkpoint',))
        return 'completed-trace'

    monkeypatch.setattr(review_common, '_record_terminal_trace', terminal)
    review_common._input_runner(
        viewer,
        args,
        replay,
        trace_io,
        title='review',
        app_id='2',
        preset='overlay',
        run_loop=lambda: None,
    )
    assert writes == [('completed-trace', args.record_input)]
    assert calls.index(('recorder-stopped',)) < calls.index(('terminal-checkpoint',))
