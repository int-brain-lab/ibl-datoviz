"""Scientific controls commit native and retained state before issuing events."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, Channels, Points, Recording, SourceKey, WorldFrame
from tests import FIXTURES
from tests.test_atlas import FIXTURE


@pytest.fixture
def app(native_datoviz):
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json'),
        width=640,
        height=480,
        enable_hover=False,
    ) as viewer:
        yield viewer


def points(app):
    return Points((0, 'missing'), [[0, 0, 0], [np.nan, 0, 0]], app.frame, {})


def test_source_and_attachment_selection_survive_mapping_visibility_and_removal(app):
    source = SourceKey('test', 'fixture', '1', 'a' * 64)
    population = Channels((0, 21), [[0, 0, 0], [np.nan, 0, 0]], app.frame, {})
    first = app.add_recording(
        Recording(source, 'pid-a', 'eid', channels=population), show=('channels',)
    )
    second = app.add_recording(
        Recording(source, 'pid-b', 'eid', channels=population), show=('channels',)
    )
    ref = first.channels.observation(21)
    other = second.channels.observation(21)
    assert ref.source_key != other.source_key
    events = []
    app.selection.on_changed(events.append)
    app.selection.set_observations((ref, other))
    first.set_visible(False)
    first.channels.set_visible(False)
    assert app.selection.observations == (ref, other)
    assert len(events) == 1
    app.selection.set_regions((-315,), mapping='allen')
    app.anatomy.set_mapping('beryl')
    assert not app.selection.regions
    assert app.selection.observations == (ref, other)
    assert events[-1].reason == 'mapping'
    app.remove_recording(first)
    assert first._closed and all(layer._closed for layer in first.layers)
    assert app.selection.observations == (other,)
    assert events[-1].reason == 'removed'
    assert events[-1].current.observations == (other,)
    with pytest.raises(ValueError, match='foreign'):
        app.selection.set_observations((ref,))
    assert app.selection.observations == (other,)


def test_region_selection_failure_restores_legacy_state_without_success_event(app, monkeypatch):
    events = []
    app.selection.on_changed(events.append)
    original = app._update_surface_emphasis
    fail = True

    def partial_failure():
        nonlocal fail
        original()
        if fail:
            fail = False
            raise RuntimeError('injected after native surface update')

    monkeypatch.setattr(app, '_update_surface_emphasis', partial_failure)
    with pytest.raises(RuntimeError, match='injected'):
        app.selection.set_regions((-315,), mapping='allen')
    assert app.selected_region_ids() == ()
    assert not app.selection.regions and not events and app.selection.revision == 0
    app.selection.set_regions((-315,), mapping='allen')
    assert events[-1].current.regions == (('allen', -315),)


def test_clear_failure_restores_both_domains_and_emits_no_event(app, monkeypatch):
    layer = app.add_points(points(app))
    ref = layer.observation(0)
    app.selection.set_observations((ref,))
    app.selection.set_regions((-315,), mapping='allen')
    previous = app.selection.snapshot()
    revision = app.selection.revision
    original = app.set_selected_region_ids

    def fail(_ids):
        raise RuntimeError('injected region clear failure')

    monkeypatch.setattr(app, 'set_selected_region_ids', fail)
    with pytest.raises(RuntimeError, match='injected'):
        app.selection.clear()
    assert app.selection.snapshot() == previous
    assert layer._selected == frozenset((ref,))
    assert app.selection.revision == revision
    monkeypatch.setattr(app, 'set_selected_region_ids', original)
    events = []
    app.selection.on_changed(events.append)
    app.selection.clear()
    assert len(events) == 1 and events[0].reason == 'clear'
    assert not app.selection.regions and not app.selection.observations


def test_callback_failures_cannot_undo_commits_or_write_reentrantly(app):
    layer = app.add_points(points(app))
    recorded = []

    def callback(event):
        recorded.append(event)
        layer.set_visible(False)

    subscription = app.selection.on_changed(callback)
    ref = layer.observation('missing')
    app.selection.set_observations((ref,))
    assert app.selection.observations == (ref,) and layer.visible
    assert len(recorded) == 1
    assert isinstance(app.selection.callback_errors[0], RuntimeError)
    subscription.close()
    app.selection.clear()
    assert len(recorded) == 1
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match='owning thread'),
    ):
        pool.submit(layer.set_visible, False).result()
    assert layer.visible


def test_frame_mismatch_rejected_before_attaching_native_layers(app):
    wrong = WorldFrame('another-reference', provenance=app.frame.provenance)
    with pytest.raises(ValueError, match='frame'):
        app.add_points(Points((0,), [[0, 0, 0]], wrong, {}))
    with pytest.raises(ValueError, match='verification'):
        app.add_points(Points((0,), [[0, 0, 0]], WorldFrame(app.frame.reference_space_id), {}))
    assert not app.layers


@pytest.mark.parametrize('action', ['close', 'error'])
def test_gui_callback_teardown_releases_layers_after_native_frame(app, monkeypatch, action):
    layer = app.add_points(points(app))
    original = app._draw_scientific_layers_gui
    reached = []

    def draw(gui):
        original(gui)
        reached.append(True)
        if action == 'error':
            raise RuntimeError('injected package GUI failure')
        app.close()
        assert not layer._closed and app.scene is not None

    monkeypatch.setattr(app, '_draw_scientific_layers_gui', draw)
    if action == 'error':
        with pytest.raises(RuntimeError, match='package GUI'):
            app.show(frame_count=3)
    else:
        app.show(frame_count=3)
    assert reached and app._closed and layer._closed and app.scene is None


def test_scalar_metadata_is_immutable_and_native_missing_row_map_is_preserved(app):
    layer = app.add_points(points(app))
    layer.color_by([0.4, np.nan], name='Confidence', units='1', cmap='viridis', limits=(0, 1))
    with pytest.raises(ValueError):
        layer.scalar_encoding.values.setflags(write=True)
    assert len(layer.refs) == 2 and len(layer.positioned_refs) == 1
    rgba = app.render_offscreen()
    assert rgba.shape == (480, 640, 4)


def test_region_rollback_table_failure_closes_viewer_without_success_event(app, monkeypatch):
    events = []
    app.selection.on_changed(events.append)
    original = app._update_surface_emphasis
    failed = False

    def fail_update_once():
        nonlocal failed
        original()
        if not failed:
            failed = True
            raise RuntimeError('injected original operation failure')

    def fail_rollback_table(ids):
        if not ids:
            raise RuntimeError('injected rollback table failure')

    monkeypatch.setattr(app, '_update_surface_emphasis', fail_update_once)
    monkeypatch.setattr(app, '_set_probe_table_selection', fail_rollback_table)
    with pytest.raises(RuntimeError, match='selection rollback failed'):
        app.selection.set_regions((-315,), mapping='allen')
    assert app._closed and app.scene is None and not events
