"""One public viewer facade, cursor transactions and scientific state isolation."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasCursor, AtlasMesh, AtlasViewer, LinkedAtlasNavigator, Points
from tests.test_volume_free_navigator import MESH, VOLUME


@pytest.fixture
def linked():
    source = open_volume_pack(VOLUME).load_volumes()
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(MESH),
        layout='linked',
        volumes=source,
        render_volume=False,
        width=640,
        height=480,
        enable_hover=False,
    ) as viewer:
        yield viewer


def test_facade_uses_one_existing_linked_owner_and_keeps_observations(linked, tmp_path):
    assert isinstance(linked, AtlasViewer) and isinstance(linked, LinkedAtlasNavigator)
    assert linked.layout == 'linked' and linked.slices.available
    scene, panels = linked.scene, dict(linked.slice_panels)
    point = linked.add_points(Points((0,), [[0, 0, 0]], linked.frame, {}))
    linked.selection.set_observations((point.observation(0),))
    table = linked.tables.show(point)
    linked.selection.set_regions((315,), mapping='allen')
    linked.slices.set_position(ap=1, ml=4, dv=1, units='voxel')
    assert linked.selection.observations == table.selected_refs() == (point.observation(0),)
    assert linked.selection.regions == (('allen', 315),)
    linked.slices.set_layers(anatomy=False, annotations=True, boundaries=False)
    assert linked.scene == scene and linked.slice_panels == panels
    assert not linked.anatomy_visible and linked.annotation_visible
    linked.render_offscreen(tmp_path / 'workspace.png')
    assert (tmp_path / 'workspace.png').is_file()


def test_cursor_units_and_callbacks_observe_committed_state(linked):
    events = []
    linked.slices.on_changed(lambda event: events.append((event, linked.slices.position)))
    linked.slices.set_position(ap=0, ml=4, dv=1, units='voxel')
    assert events[-1][0].current == events[-1][1]
    world = linked.slices.position.world_um
    linked.slices.set_position(ap=world[1], ml=world[0], dv=world[2], units='um')
    assert len(events) == 1
    assert linked.slices.position.index == (0, 4, 1)
    linked.slices.on_changed(lambda _: linked.slices.set_position(ap=0, ml=0, dv=0, units='voxel'))
    linked.slices.set_position(ap=1, ml=4, dv=1, units='voxel')
    assert linked.slices.position.index == (1, 4, 1)
    assert 'reentrantly' in str(linked.slices.callback_errors[-1])


def test_invalid_cursor_validates_all_axes_before_mutation(linked):
    before = linked.slices.position
    controls = tuple(v.value for v in linked._cursor_controls.values())
    for cursor in (AtlasCursor(0, 0, 999), AtlasCursor(0, True, 1)):
        with pytest.raises((TypeError, IndexError)):
            linked.set_cursor(cursor)
        assert linked.slices.position == before
        assert tuple(v.value for v in linked._cursor_controls.values()) == controls
    for kwargs in (
        dict(ap=True, ml=0, dv=0, units='voxel'),
        dict(ap=0, ml=0, dv=np.nan, units='um'),
        dict(ap=1e12, ml=0, dv=0, units='um'),
        dict(ap=0, ml=0, dv=0, units='mm'),
    ):
        with pytest.raises((ValueError, IndexError)):
            linked.slices.set_position(**kwargs)
        assert linked.slices.position == before


@pytest.mark.parametrize('select_region', (False, True))
def test_cursor_upload_failure_restores_cursor_controls_and_selection(
    linked, monkeypatch, select_region
):
    before = linked.slices.position
    selection = linked.selection.snapshot()
    cursor_events, selection_events = [], []
    linked.slices.on_changed(cursor_events.append)
    linked.selection.on_changed(selection_events.append)
    refresh = linked._refresh_slices
    calls = []

    def fail_once(axes=None):
        calls.append(linked.cursor.as_index())
        refresh(axes)
        if len(calls) == 1:
            raise RuntimeError('injected cursor upload failure')

    monkeypatch.setattr(linked, '_refresh_slices', fail_once)
    with pytest.raises(RuntimeError, match='injected'):
        linked.set_cursor(AtlasCursor(1, 4, 1), select_region=select_region)
    assert linked.slices.position == before and linked.selection.snapshot() == selection
    assert tuple(v.value for v in linked._cursor_controls.values()) == before.index
    assert not cursor_events and not selection_events
    assert calls[-1] == before.index


def test_cursor_thread_and_subscription_lifetimes(linked):
    subscription = linked.slices.on_changed(lambda _: None)
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match='owning thread'),
    ):
        pool.submit(linked.slices.set_position, ap=1, ml=4, dv=1, units='voxel').result()
    linked.close()
    assert subscription.owner is None
    with pytest.raises(RuntimeError, match='closed'):
        _ = linked.slices.position


def test_3d_viewer_does_not_require_or_load_slice_data():
    with AtlasViewer(atlas=AtlasMesh.from_pack(MESH)) as app:
        assert not app.slices.available
        with pytest.raises(ValueError, match='linked'):
            app.slices.set_position(ap=0, ml=0, dv=0, units='voxel')


def test_failed_base_validation_preserves_error_without_creating_slice_workers(monkeypatch):
    import ibl_datoviz.linked_atlas as implementation  # noqa: PLC0415

    def forbidden(*_args, **_kwargs):
        pytest.fail('slice workers allocated before base validation')

    monkeypatch.setattr(implementation, 'SliceScheduler', forbidden)
    source = open_volume_pack(VOLUME).load_volumes()
    with pytest.raises(ValueError, match='context opacity'):
        AtlasViewer(
            atlas=AtlasMesh.from_pack(MESH),
            layout='linked',
            slice_source=source,
            render_volume=False,
            context_opacity=2,
        )
