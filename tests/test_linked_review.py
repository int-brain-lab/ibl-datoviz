"""CPU checks for the fixed-layout linked review composition."""

from __future__ import annotations

import ctypes
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from examples import linked_atlas_review as review
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.components import AtlasCursor
from ibl_datoviz.linked_atlas import LinkedSlices
from tests import FIXTURES
from tests.test_atlas import FakeDatoviz


class View2D(ctypes.Structure):
    _fields_ = [('mode', ctypes.c_int), ('aspect', ctypes.c_int), ('padding', ctypes.c_float)]


class ReviewDatoviz(FakeDatoviz):
    DVZ_ALPHA_BLENDED = 1
    DVZ_DIM_X = 0
    DVZ_DIM_Y = 1
    DVZ_PANEL_VIEW2D_CONTAIN = 1
    DVZ_PANEL_VIEW2D_ASPECT_EQUAL = 1

    def dvz_figure_grid(self, figure, rows, columns):
        self.calls.append(('grid', rows, columns))
        return object()

    def dvz_grid_panel(self, grid, row, column):
        return self._handle(f'panel-{row}-{column}')

    def dvz_panel_set_domain(self, *args):
        return 0

    def dvz_panel_view2d_desc(self):
        return View2D()

    def dvz_panel_set_view2d(self, *args):
        return 0

    def dvz_volume_set_opacity(self, volume, opacity):
        self.calls.append(('volume_opacity', opacity))
        return 0

    def dvz_gui_text(self, gui, text):
        self.calls.append(('gui_text', text))


class CpuReview(review.LinkedAtlasReview):
    """Exercise the real viewer and fixed-layout review composition."""


@pytest.fixture(autouse=True)
def cpu_slices(monkeypatch):
    """Replace only native slice uploads on the owned linked component."""

    def marker(component):
        component.marker_world_um = component.cursor.world_um(component.slice_source)

    def refresh(component, axes=None):
        for axis in review.AXES if axes is None else axes:
            component.prepared_slices[axis] = component._slice_layers(axis)
        marker(component)

    def create(component):
        component.prepared_slices = {}
        refresh(component)

    def volume(component):
        component.volume = component.viewer.dvz._handle('volume')
        component.viewer._update_surface_alpha_mode()

    monkeypatch.setattr(LinkedSlices, '_create_slices', create)
    monkeypatch.setattr(LinkedSlices, '_refresh_slices', refresh)
    monkeypatch.setattr(LinkedSlices, '_create_anatomical_volume', volume)
    monkeypatch.setattr(LinkedSlices, '_create_cursor_marker', marker)
    monkeypatch.setattr(LinkedSlices, '_update_cursor_marker', marker)


class PlaneAdapter:
    """Record borrowed handles, owned payload updates and destruction order."""

    def __init__(self, dvz, scene, panel, data, **kwargs):
        self.dvz, self.scene, self.panel = dvz, scene, panel
        self.data = data
        self.alpha_mode = kwargs['alpha_mode']
        self.alpha_cutoff = kwargs['alpha_cutoff']
        self.transform = kwargs['transform']
        assert kwargs['depth_policy'] == 'physical'
        self.closed = False
        self.visible = True
        self.replacements = 0
        self.dvz.calls.append(('plane_create', self.alpha_mode))

    def replace(self, data):
        self.data = data
        self.replacements += 1

    def set_visible(self, visible):
        self.visible = visible

    def close(self):
        if not self.closed:
            self.dvz.calls.append(('plane_close',))
            self.closed = True


@pytest.fixture
def viewer(monkeypatch):
    monkeypatch.setattr(review, 'SampledPlaneVisual', PlaneAdapter)
    volumes = open_volume_pack(FIXTURES / 'linked-atlas-v1' / 'volume-pack').load_volumes()
    mesh = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    native = ReviewDatoviz()
    with CpuReview(mesh, volumes, datoviz=native) as navigator:
        yield navigator


def handles(viewer):
    return (
        viewer.scene,
        viewer.figure,
        viewer.panel,
        viewer.view,
        viewer.arcball,
        *(viewer._linked.slice_panels[axis] for axis in review.AXES),
        viewer._linked.volume,
    )


def test_presets_keep_four_panels_view_camera_and_region_overrides(viewer):
    viewer.view, viewer.arcball = object(), object()
    original = handles(viewer)
    camera_calls = [call for call in viewer.dvz.calls if call[0] == 'camera']
    assert viewer.width == 1400 and viewer.height == 1000
    assert viewer._linked.volume is not None and viewer._linked.volume_opacity == 0
    assert viewer.physical_plane is None and not viewer.plane_visible
    assert (
        viewer._linked.anatomy_visible,
        viewer._linked.annotation_visible,
        viewer._linked.boundaries_visible,
    ) == (
        True,
        True,
        True,
    )
    viewer.set_region_opacity(315, 0.35)
    initial_colors = viewer._display_surface_colors().copy()

    expected = {
        'anatomy': (True, False, False, 0.0, False),
        'overlay': (True, True, True, 0.0, False),
        'labels': (False, True, True, 0.0, False),
        'volume-context': (True, True, True, 0.12, False),
        'physical-slice': (True, True, True, 0.0, True),
    }
    for preset, settings in expected.items():
        viewer.apply_preset(preset)
        assert (
            viewer._linked.anatomy_visible,
            viewer._linked.annotation_visible,
            viewer._linked.boundaries_visible,
            viewer._linked.volume_opacity,
            viewer.plane_visible,
        ) == settings
        assert all(
            before is after for before, after in zip(original, handles(viewer), strict=True)
        )
        np.testing.assert_array_equal(viewer._display_surface_colors(), initial_colors)
    assert [call for call in viewer.dvz.calls if call[0] == 'camera'] == camera_calls
    assert [call for call in viewer.dvz.calls if call[0] == 'grid'] == [('grid', 2, 2)]


@pytest.mark.parametrize('mapping', ['allen', 'beryl', 'cosmos'])
def test_slice_region_selection_keeps_crosshair_and_zoom_fixed(viewer, mapping):
    viewer.set_mapping(mapping)
    cursor = viewer._linked.cursor
    viewer._linked._slice_zoom = dict.fromkeys(review.AXES, 2.0)
    selected = set()
    for axis in review.AXES:
        quad, _ = viewer._linked._slice_quad(axis)
        for fraction in ((0.1, 0.1), (0.5, 0.5), (0.9, 0.9)):
            point = quad[0, :2] + np.asarray(fraction) * (quad[3, :2] - quad[0, :2])
            location = viewer._linked._cursor_at_slice_data(axis, *point)
            row = location.region(viewer._linked.slice_source, mapping)
            expected = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
            assert viewer._linked._select_region_at_slice_data(axis, *point)
            assert viewer.selected_region_ids() == expected
            assert viewer._linked.cursor == cursor
            assert viewer._linked._slice_zoom == dict.fromkeys(review.AXES, 2.0)
            selected.update(expected)
    if mapping == 'allen':
        assert selected
    before = viewer.selected_region_ids()
    assert not viewer._linked._select_region_at_slice_data('ap', 100, 100)
    assert viewer.selected_region_ids() == before
    assert viewer._linked.cursor == cursor


def test_physical_plane_follows_cursor_mapping_and_axis_with_retained_adapter(viewer):
    viewer.apply_preset('physical-slice')
    adapter = viewer.physical_plane
    assert adapter.scene is viewer.scene and adapter.panel is viewer.panel
    first_corners = adapter.data.corners_um.copy()
    viewer.slices.set_position(
        ap=0, ml=viewer._linked.cursor.ml, dv=viewer._linked.cursor.dv, units='voxel'
    )
    assert viewer.physical_plane is adapter
    assert not np.array_equal(adapter.data.corners_um, first_corners)
    np.testing.assert_array_equal(
        viewer.mesh_data.normalize_points(adapter.data.corners_um),
        adapter.transform(adapter.data.corners_um),
    )
    uploads = adapter.replacements
    viewer.slices.set_position(
        ap=viewer._linked.cursor.ap, ml=0, dv=viewer._linked.cursor.dv, units='voxel'
    )
    assert adapter.replacements == uploads  # the AP plane did not move
    viewer.slices.set_position(
        ap=1, ml=viewer._linked.cursor.ml, dv=viewer._linked.cursor.dv, units='voxel'
    )
    viewer.configure_physical_plane(layer='annotation')
    allen_pixels = adapter.data.rgba.copy()
    viewer.set_mapping('beryl')
    assert viewer.physical_plane is adapter
    assert not np.array_equal(adapter.data.rgba, allen_pixels)
    viewer.configure_physical_plane(axis='ml')
    assert viewer.physical_plane is adapter and adapter.data.sampling == 'nearest'
    assert adapter.data.rgba.flags.owndata and adapter.data.corners_um.flags.owndata


def test_mode_replacement_and_volume_toggles_keep_native_layout(viewer):
    original = handles(viewer)
    viewer.set_physical_plane(True)
    old = viewer.physical_plane
    viewer.configure_physical_plane(mode='mask', cutoff=0.4)
    assert old.closed
    assert viewer.physical_plane is not old
    assert viewer.physical_plane.alpha_mode == 'mask'
    assert viewer.physical_plane.alpha_cutoff == 0.4
    viewer.set_volume_opacity(0.2)
    assert not viewer.plane_visible and not viewer.physical_plane.visible
    assert viewer._linked.volume_opacity == 0.2
    viewer.set_physical_plane(True)
    assert viewer.plane_visible and viewer._linked.volume_opacity == 0
    assert all(before is after for before, after in zip(original, handles(viewer), strict=True))


@pytest.mark.parametrize('previous, requested', [(0.0, 0.2), (0.2, 0.0)])
def test_volume_visibility_tracks_opacity_and_rolls_back_partial_failure(
    viewer, monkeypatch, previous, requested
):
    viewer.set_volume_opacity(previous)
    original = viewer.dvz.dvz_visual_set_visible
    visibility = previous > 0
    failed = False

    def fail_once(visual, visible):
        nonlocal visibility, failed
        if visual is viewer._linked.volume:
            visibility = bool(visible)
            if not failed:
                failed = True
                return -1
        return original(visual, visible)

    monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_visible', fail_once)
    with pytest.raises(RuntimeError, match='volume visibility'):
        viewer.set_volume_opacity(requested)
    assert visibility is (previous > 0)
    assert viewer._linked.volume_opacity == previous
    assert viewer._linked._volume_opacity_control.value == pytest.approx(previous)
    viewer.set_volume_opacity(requested)
    assert visibility is (requested > 0)
    assert viewer._linked.volume_opacity == requested


def test_plane_preparation_failure_restores_configuration_and_existing_payload(
    viewer, monkeypatch
):
    viewer.set_physical_plane(True)
    adapter, data = viewer.physical_plane, viewer.physical_plane.data
    monkeypatch.setattr(
        review,
        'load_review_slice',
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('source unavailable')),
    )
    with pytest.raises(RuntimeError, match='source unavailable'):
        viewer.configure_physical_plane(axis='ml', mode='mask')
    assert viewer.plane_axis == 'ap' and viewer.plane_mode == 'wboit'
    assert viewer._plane_axis_control.value == viewer._plane_mode_control.value == 0
    assert viewer.physical_plane is adapter and adapter.data is data and not adapter.closed


def test_navigation_failure_hides_stale_physical_plane(viewer, monkeypatch):
    viewer.set_physical_plane(True)
    adapter = viewer.physical_plane

    def unavailable(*args, **kwargs):
        raise RuntimeError('source unavailable')

    monkeypatch.setattr(review, 'load_review_slice', unavailable)
    moved = viewer._linked.cursor.replace('ap', 0, viewer._linked.slice_source.grid.shape)
    with pytest.raises(RuntimeError, match='source unavailable'):
        viewer.slices.set_position(ap=moved.ap, ml=moved.ml, dv=moved.dv, units='voxel')
    assert viewer._linked.cursor == moved
    assert not viewer.plane_visible and not adapter.visible
    assert not viewer._plane_visible_control.value
    assert viewer._review_error == 'Physical plane hidden after update failure: source unavailable'


def test_physical_updates_reuse_the_navigator_contrast_cache(viewer, monkeypatch):
    monkeypatch.setattr(np, 'percentile', lambda *a, **k: pytest.fail('contrast was rescanned'))
    viewer.set_physical_plane(True)
    viewer.slices.set_position(
        ap=0, ml=viewer._linked.cursor.ml, dv=viewer._linked.cursor.dv, units='voxel'
    )
    viewer.configure_physical_plane(axis='dv', layer='annotation')
    viewer.set_mapping('beryl')


@pytest.mark.parametrize(
    'kwargs',
    [
        {'axis': 'other'},
        {'mode': 'blended'},
        {'layer': 'other'},
        {'opacity': -0.1},
        {'cutoff': float('nan')},
    ],
)
def test_invalid_plane_configuration_does_not_allocate_native_resources(viewer, kwargs):
    before = list(viewer.dvz.calls)
    with pytest.raises(ValueError):
        viewer.configure_physical_plane(**kwargs)
    assert viewer.dvz.calls == before and viewer.physical_plane is None


def test_cleanup_releases_plane_before_scene_and_is_idempotent(viewer):
    viewer.set_physical_plane(True)
    adapter = viewer.physical_plane
    viewer._linked._slice_loader = SimpleNamespace(
        close=lambda: viewer.dvz.calls.append(('worker_close',))
    )
    viewer.close()
    calls = viewer.dvz.calls
    assert calls.index(('plane_close',)) < calls.index(('worker_close',))
    assert calls.index(('worker_close',)) < calls.index(('destroy_scene',))
    assert adapter.closed and viewer.physical_plane is None
    viewer.close()
    assert calls.count(('plane_close',)) == calls.count(('destroy_scene',)) == 1


def test_explicit_reset_restores_controls_without_reallocating_layout(viewer):
    viewer.apply_preset('physical-slice')
    viewer.configure_physical_plane(axis='dv', mode='mask', opacity=0.4, cutoff=0.2)
    viewer.slices.set_position(ap=0, ml=0, dv=0, units='voxel')
    viewer.set_region_opacity(315, 0.3)
    original = handles(viewer)
    viewer.reset_review()
    assert viewer._linked.cursor == AtlasCursor.centre(viewer._linked.slice_source)
    assert not viewer.plane_visible and viewer._linked.volume_opacity == 0
    assert viewer.plane_axis == 'ap' and viewer.plane_mode == 'wboit'
    assert viewer.plane_opacity == 0.72 and viewer.plane_cutoff == 0.5
    assert all(before is after for before, after in zip(original, handles(viewer), strict=True))


def test_extra_gui_keeps_linked_controls_and_reports_update_errors(viewer, monkeypatch):
    events = []
    monkeypatch.setattr(AtlasViewer, '_draw_extra_gui', lambda *a: events.append('linked'))
    monkeypatch.setattr(viewer, '_draw_review_gui', lambda *a: events.append('review'))
    viewer._draw_extra_gui(object())
    assert events == ['linked', 'review']
    monkeypatch.setattr(
        viewer,
        '_draw_review_gui',
        lambda *a: (_ for _ in ()).throw(RuntimeError('native upload failed')),
    )
    viewer._draw_extra_gui(object())
    assert viewer._review_error == 'native upload failed'
    assert ('gui_text', b'Review update failed: native upload failed') in viewer.dvz.calls


def test_cli_loads_explicit_verified_sources_and_forwards_review_options(monkeypatch):
    calls = []
    fixture_calls = []
    mesh, volumes, geometry = object(), object(), object()
    monkeypatch.setattr(review, 'bundled_asset_set', lambda: 'immutable-lock')

    def fixture_identity(*args):
        fixture_calls.append(args)
        return {'atlas_manifest_sha256': 'manifest-digest'}

    monkeypatch.setattr(
        review,
        '_review_asset_identity',
        fixture_identity,
    )
    monkeypatch.setattr(review, '_context_surface_identity', lambda _catalog: {})
    monkeypatch.setattr(
        review,
        'verify_materialized_asset_set',
        lambda lock, root: (
            calls.append(('assets', lock, str(root))) or SimpleNamespace(geometry=geometry)
        ),
    )
    monkeypatch.setattr(
        review,
        'open_volume_pack',
        lambda root: (
            calls.append(('volume', str(root))) or SimpleNamespace(load_volumes=lambda: volumes)
        ),
    )
    monkeypatch.setattr(review.AtlasMesh, 'from_geometry', lambda value: mesh)
    context = (object(),)
    catalog, context_geometry = object(), (object(),)
    monkeypatch.setattr(review, 'load_major_context', lambda root: (catalog, context_geometry))
    monkeypatch.setattr(
        review,
        'review_context_surfaces',
        lambda actual_mesh, actual_catalog, actual_geometry: context,
    )

    class ReviewStub:
        def __init__(self, actual_mesh, actual_volumes, **kwargs):
            assert actual_mesh is mesh and actual_volumes is volumes
            calls.append(('options', kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(('close',))

    monkeypatch.setattr(review, 'LinkedAtlasReview', ReviewStub)
    monkeypatch.setattr(
        review,
        'finish_review',
        lambda viewer, args, title, **kwargs: calls.append(
            ('finish', args.frames, args.offscreen, title, kwargs)
        ),
    )
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'linked_atlas_review',
            '/assets/d070',
            '/assets/50um',
            '--preset',
            'labels',
            '--frames',
            '3',
            '--ui-scale',
            '1.5',
            '--record-input',
            '/tmp/recorded-actions.json',
        ],
    )
    assert review.main() == 0
    assert calls[:2] == [('assets', 'immutable-lock', '/assets/d070'), ('volume', '/assets/50um')]
    assert fixture_calls[0][2:] == (
        'immutable-lock',
        Path('/assets/d070'),
        Path('/assets/50um'),
    )
    assert calls[2] == (
        'options',
        {
            'preset': 'labels',
            'mapping': 'allen',
            'anatomy_presentation': 'major',
            'anatomical_context': context,
            'context_opacity': 0.04,
            'camera_angles': review.RECORDING_CAMERA,
            'width': 2240,
            'height': 1600,
            'ui_scale': 1.5,
            'enable_interaction': True,
            'fit_workarea': True,
            'enable_hover': False,
        },
    )
    assert calls[3] == (
        'finish',
        3,
        None,
        'D070 linked atlas review',
        {'app_id': '2', 'preset': 'labels'},
    )
    assert calls[4] == ('close',)


def test_review_asset_identity_uses_verified_source_roots_and_required_hashes(tmp_path):
    asset_root = tmp_path / 'd070'
    volume_root = tmp_path / 'volume'
    (asset_root / 'mesh-pack').mkdir(parents=True)
    volume_root.mkdir()
    mesh_manifest = asset_root / 'mesh-pack' / 'manifest.json'
    region_catalog = asset_root / 'regions.json'
    volume_manifest = volume_root / 'manifest.json'
    mesh_manifest.write_bytes(b'mesh manifest')
    region_catalog.write_bytes(b'region catalog')
    volume_manifest.write_bytes(b'volume manifest')
    mesh_digest = hashlib.sha256(mesh_manifest.read_bytes()).hexdigest()
    region_digest = hashlib.sha256(region_catalog.read_bytes()).hexdigest()
    volume_digest = hashlib.sha256(volume_manifest.read_bytes()).hexdigest()
    geometry_digest = 'a' * 64
    mesh_pack = SimpleNamespace(
        manifest_path=mesh_manifest,
        manifest={
            'pack_id': 'd070-pack',
            'default_lod_id': 'default',
            'lods': [{'id': 'default', 'resource': {'sha256': geometry_digest}}],
        },
    )
    assets = SimpleNamespace(root=asset_root, mesh_pack=mesh_pack)
    volume_pack = SimpleNamespace(
        root=volume_root,
        manifest={
            'pack_id': 'allen-50um',
            'region_catalog': {'sha256': region_digest},
            'volumes': {
                'template': {'sha256': 'b' * 64},
                'annotation': {'sha256': 'c' * 64},
            },
        },
    )
    asset_set = SimpleNamespace(
        asset_set_id='d070-set',
        mesh_manifest=SimpleNamespace(sha256=mesh_digest),
        region_catalog=SimpleNamespace(sha256=region_digest),
        expected_geometry_sha256=geometry_digest,
    )

    identity = review._review_asset_identity(
        assets, volume_pack, asset_set, asset_root, volume_root
    )
    assert identity == {
        'asset_set_id': 'd070-set',
        'atlas_pack_id': 'd070-pack',
        'atlas_manifest_sha256': mesh_digest,
        'atlas_geometry_sha256': geometry_digest,
        'region_catalog_sha256': region_digest,
        'volume_manifest_sha256': volume_digest,
        'volume_pack_id': 'allen-50um',
        'volume_resources_sha256': {'template': 'b' * 64, 'annotation': 'c' * 64},
    }


def test_review_asset_identity_fails_closed_on_missing_manifest(tmp_path):
    asset_set = SimpleNamespace(
        asset_set_id='d070-set',
        mesh_manifest=SimpleNamespace(sha256='a' * 64),
        region_catalog=SimpleNamespace(sha256='b' * 64),
        expected_geometry_sha256='c' * 64,
    )
    assets = SimpleNamespace(root=tmp_path, mesh_pack=SimpleNamespace())
    volume_pack = SimpleNamespace(root=tmp_path, manifest={})
    with pytest.raises(RuntimeError, match='source is missing'):
        review._review_asset_identity(assets, volume_pack, asset_set, tmp_path, tmp_path)


def test_failed_plane_visibility_restores_native_visibility_and_volume(viewer, monkeypatch):
    viewer.set_volume_opacity(0.12)
    viewer.set_physical_plane(True)
    viewer.set_physical_plane(False)
    viewer.set_volume_opacity(0.12)
    adapter = viewer.physical_plane
    original = adapter.set_visible
    failed = False

    def fail_once(visible):
        nonlocal failed
        if not failed:
            failed = True
            adapter.visible = visible  # Emulate a setter that partially mutated before failing.
            raise RuntimeError('injected visibility failure')
        original(visible)

    monkeypatch.setattr(adapter, 'set_visible', fail_once)
    with pytest.raises(RuntimeError, match='injected'):
        viewer.set_physical_plane(True)
    assert not viewer.plane_visible and not adapter.visible
    assert viewer._linked.volume_opacity == 0.12


def test_failed_physical_preset_restores_previous_slice_and_volume_state(viewer, monkeypatch):
    viewer.apply_preset('volume-context')
    previous = (
        viewer._linked.anatomy_visible,
        viewer._linked.annotation_visible,
        viewer._linked.boundaries_visible,
        viewer._linked.volume_opacity,
        viewer._preset_control.value,
    )

    def failure():
        raise RuntimeError('injected plane source failure')

    monkeypatch.setattr(viewer, '_plane_data', failure)
    with pytest.raises(RuntimeError, match='injected'):
        viewer.apply_preset('physical-slice')
    assert (
        viewer._linked.anatomy_visible,
        viewer._linked.annotation_visible,
        viewer._linked.boundaries_visible,
        viewer._linked.volume_opacity,
        viewer._preset_control.value,
    ) == previous
    assert not viewer.plane_visible


def test_failed_volume_context_hide_restores_visible_physical_plane(viewer, monkeypatch):
    viewer.set_physical_plane(True)
    adapter = viewer.physical_plane
    original = adapter.set_visible
    failed = False

    def fail_once(visible):
        nonlocal failed
        adapter.visible = visible
        if not failed:
            failed = True
            raise RuntimeError('injected plane hide failure')
        original(visible)

    monkeypatch.setattr(adapter, 'set_visible', fail_once)
    with pytest.raises(RuntimeError, match='plane hide failure'):
        viewer.slices.set_volume_opacity(0.2)
    assert not viewer._closed
    assert viewer._linked.volume_opacity == 0
    assert viewer.plane_visible and adapter.visible
    assert viewer._plane_visible_control.value
    viewer.slices.set_volume_opacity(0.2)
    assert viewer._linked.volume_opacity == 0.2
    assert not viewer.plane_visible and not adapter.visible


@pytest.mark.parametrize('guard', ['owner_thread', 'selection_callback'])
def test_close_guards_preserve_plane_and_scene(viewer, monkeypatch, guard):
    viewer.set_physical_plane(True)
    adapter = viewer.physical_plane
    with monkeypatch.context() as patch:
        if guard == 'owner_thread':
            patch.setattr(viewer, '_owner_thread', -1)
        else:
            patch.setattr(viewer.selection, '_notifying', True)
        with pytest.raises(RuntimeError):
            viewer.close()
    assert viewer.physical_plane is adapter and not adapter.closed
    assert not viewer._closed
    assert ('destroy_scene',) not in viewer.dvz.calls


def test_close_during_gui_callback_defers_plane_until_scene_can_close(viewer):
    viewer.set_physical_plane(True)
    adapter = viewer.physical_plane
    viewer._gui_callback_depth = 1
    viewer.close()
    assert viewer._close_pending and not viewer._closed
    assert viewer.physical_plane is adapter and not adapter.closed
    assert ('destroy_scene',) not in viewer.dvz.calls
    viewer._gui_callback_depth = 0
    viewer.close()
    assert adapter.closed and viewer._closed
    assert viewer.dvz.calls.index(('plane_close',)) < viewer.dvz.calls.index(('destroy_scene',))
