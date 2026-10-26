"""One public viewer facade, cursor transactions and scientific state isolation."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh, AtlasViewer, Points
from ibl_datoviz.components import AtlasCursor
from ibl_datoviz.slice_preparation import prepare_slice_layers
from tests.test_volume_free_navigator import MESH, VOLUME


@pytest.fixture
def linked(native_datoviz):
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
    assert type(linked) is AtlasViewer
    assert linked.layout == 'linked' and linked.slices.available
    scene, panels = linked.scene, dict(linked._linked.slice_panels)
    point = linked.add_points(Points((0,), [[0, 0, 0]], linked.frame, {}))
    linked.selection.set_observations((point.observation(0),))
    table = linked.tables.show(point)
    linked.selection.set_regions((315,), mapping='allen')
    linked.slices.set_position(ap=1, ml=4, dv=1, units='voxel')
    assert linked.selection.observations == table.selected_refs() == (point.observation(0),)
    assert linked.selection.regions == (('allen', 315),)
    linked.slices.set_layers(anatomy=False, annotations=True, boundaries=False)
    assert linked.scene == scene and linked._linked.slice_panels == panels
    assert not linked._linked.anatomy_visible and linked._linked.annotation_visible
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
    controls = tuple(v.value for v in linked._linked._cursor_controls.values())
    for cursor in (AtlasCursor(0, 0, 999), AtlasCursor(0, True, 1)):
        with pytest.raises((TypeError, IndexError)):
            linked._linked.set_cursor(cursor)
        assert linked.slices.position == before
        assert tuple(v.value for v in linked._linked._cursor_controls.values()) == controls
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
    refresh = linked._linked._refresh_slices
    calls = []

    def fail_once(axes=None):
        calls.append(linked._linked.cursor.as_index())
        refresh(axes)
        if len(calls) == 1:
            raise RuntimeError('injected cursor upload failure')

    monkeypatch.setattr(linked._linked, '_refresh_slices', fail_once)
    with pytest.raises(RuntimeError, match='injected'):
        linked._linked.set_cursor(AtlasCursor(1, 4, 1), select_region=select_region)
    assert linked.slices.position == before and linked.selection.snapshot() == selection
    assert tuple(v.value for v in linked._linked._cursor_controls.values()) == before.index
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


def test_3d_viewer_does_not_require_or_load_slice_data(native_datoviz):
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


def test_native_slice_palette_round_trips_srgb_without_a_second_gamma_encode(linked):
    expected = set()
    for axis in ('ap', 'ml', 'dv'):
        _, annotation = linked._linked._slice_layers(axis)
        expected.update(
            tuple(pixel[:3])
            for pixel in annotation.reshape(-1, 4)
            if pixel[3] == 255 and len(set(pixel[:3])) > 1
        )
    assert expected  # Test chromatic catalog colors, not only black/white endpoints.
    linked._create_view(offscreen=True, title='Slice catalog color regression')
    for visual in (
        *linked._linked._crosshairs.values(),
        *linked._linked._boundary_visuals.values(),
    ):
        assert linked.dvz.dvz_visual_set_visible(visual, False) == 0
    assert linked.dvz.dvz_view_render_once(linked.view) == 0
    pixels = np.array(linked.dvz.dvz_view_capture_rgba(linked.view), copy=True)[..., :3]
    for color in expected:
        difference = np.abs(pixels.astype(np.int16) - color)
        assert np.count_nonzero(np.max(difference, axis=-1) <= 1) > 10, color


def test_slice_selection_keeps_context_colors_and_adds_an_owned_outline(linked):
    before = {axis: linked._linked._slice_layers(axis) for axis in ('ap', 'ml', 'dv')}
    linked.selection.set_regions((315,), mapping='allen')
    found = False
    for axis in before:
        payload = prepare_slice_layers(
            linked._linked.slice_composer, linked._linked._slice_request(axis)
        )
        np.testing.assert_array_equal(payload.anatomy, before[axis][0])
        np.testing.assert_array_equal(payload.annotation, before[axis][1])
        assert not payload.selection_starts.flags.writeable
        assert not payload.selection_ends.flags.writeable
        found |= len(payload.selection_starts) > 0
    assert found
    linked.selection.clear_regions()
    for axis in before:
        payload = prepare_slice_layers(
            linked._linked.slice_composer, linked._linked._slice_request(axis)
        )
        assert len(payload.selection_starts) == 0


def test_selection_outline_follows_slice_zoom_and_hides_after_deselection(linked, monkeypatch):
    linked.selection.set_regions((315,), mapping='allen')
    uploads = []
    upload = linked._linked._upload_boundaries

    def record(visual, starts, ends, context, **kwargs):
        if context == 'slice selection outline':
            uploads.append((starts.copy(), ends.copy()))
        return upload(visual, starts, ends, context, **kwargs)

    monkeypatch.setattr(linked._linked, '_upload_boundaries', record)
    axis = next(a for a, (starts, _) in linked._linked._selection_contours.items() if len(starts))
    before = linked._linked._map_boundary_segments(axis, *linked._linked._selection_contours[axis])
    linked._linked._slice_zoom[axis] = 2.0
    linked._linked._update_slice_geometry(axis)
    assert len(uploads) == 2
    np.testing.assert_allclose(uploads[0][0][:, :2], before[0][:, :2] * 2)
    np.testing.assert_allclose(uploads[0][1][:, :2], before[1][:, :2] * 2)
    linked.selection.clear_regions()
    assert all(len(starts) == 0 for starts, _ in linked._linked._selection_contours.values())
