import ctypes
import json
from argparse import ArgumentParser
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from examples import review_common
from examples.review_common import add_review_arguments, finish_review
from ibl_datoviz import interaction_benchmark
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
        slice_panels={'ap': object(), 'ml': object(), 'dv': object()},
        panel=object(),
    )
    rectangles = review_common._panel_rects(viewer)
    assert tuple(rectangles) == ('ap', 'ml', 'dv', '3d')
    assert all(len(rect) == 4 for rect in rectangles.values())
    assert len(released) == 4


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
    viewer = SimpleNamespace(cursor=object(), slices=object())
    with pytest.raises(ValueError, match=message):
        finish_review(viewer, args, 'title')


def _runner_fakes(monkeypatch, trace):
    calls = []

    class Fixture:
        initial_state = {'camera': {'angles': [0.0, 0.0, 0.0]}}
        metadata = {}

        @classmethod
        def capture(cls, *_args, **_kwargs):
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
            return SimpleNamespace(ready=True, status='ready', to_dict=dict)

        def checkpoint(self, *, render_proof):
            assert render_proof is None
            return SimpleNamespace(to_dict=lambda: {'status': 'unavailable'})

        def close(self):
            calls.append(('readiness-closed',))

    monkeypatch.setattr(interaction_benchmark, 'ReviewFixture', Fixture)
    monkeypatch.setattr(interaction_benchmark, 'LinkedReadiness', Readiness)
    monkeypatch.setattr(interaction_benchmark, 'scientific_state', lambda _viewer: {'camera': {}})

    class Recorder:
        def __init__(self, *_args, **kwargs):
            calls.append(('recorder-created', kwargs['fixture']))

        def start(self):
            calls.append(('recorder-started',))

        def stop(self):
            calls.append(('recorder-stopped',))
            return 'trace-data'

    class Player:
        def __init__(self, *_args):
            calls.append(('player-created',))

        def run(self, *_args, **_kwargs):
            calls.append(('player-run',))
            return {'ok': True}

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
        cursor=object(),
        slices=object(),
        mapping='allen',
        width=800,
        height=600,
        ui_scale=1.0,
        app='app',
        view='view',
        dvz=SimpleNamespace(dvz_app_step=lambda _app, _timeout: 1),
        _sidebar=SimpleNamespace(sidebar_rect=(0.0, 0.0, 240.0, 600.0)),
        slice_panels={},
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
    assert report['ibl_display_checkpoint']['status'] == 'unavailable'
    assert ('player-run',) in calls
