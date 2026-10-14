"""CPU checks for the fixed-layout linked review composition."""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from examples import linked_atlas_review as review
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasCursor, AtlasMesh, LinkedAtlasNavigator
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
    """Use actual controller/layout code and replace only native layer uploads."""

    def _create_slices(self):
        self.prepared_slices = {}
        self._refresh_slices()

    def _refresh_slices(self, axes=None):
        for axis in review.AXES if axes is None else axes:
            self.prepared_slices[axis] = self._slice_layers(axis)
        self._update_cursor_marker()

    def _create_anatomical_volume(self):
        self.volume = self.dvz._handle('volume')
        self._update_surface_alpha_mode()

    def _create_cursor_marker(self):
        self._update_cursor_marker()

    def _update_cursor_marker(self):
        self.marker_world_um = self.cursor.world_um(self.slice_source)


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
        *(viewer.slice_panels[axis] for axis in review.AXES),
        viewer.volume,
    )


def test_presets_keep_four_panels_view_camera_and_region_overrides(viewer):
    viewer.view, viewer.arcball = object(), object()
    original = handles(viewer)
    camera_calls = [call for call in viewer.dvz.calls if call[0] == 'camera']
    assert viewer.width == 1400 and viewer.height == 1000
    assert viewer.volume is not None and viewer.volume_opacity == 0
    assert viewer.physical_plane is None and not viewer.plane_visible
    viewer.set_region_opacity(315, 0.35)
    initial_colors = viewer._display_surface_colors().copy()

    expected = {
        'anatomy': (True, False, False, 0.0, False),
        'labels': (False, True, True, 0.0, False),
        'volume-context': (True, True, True, 0.12, False),
        'physical-slice': (True, True, True, 0.0, True),
    }
    for preset, settings in expected.items():
        viewer.apply_preset(preset)
        assert (
            viewer.anatomy_visible,
            viewer.annotation_visible,
            viewer.boundaries_visible,
            viewer.volume_opacity,
            viewer.plane_visible,
        ) == settings
        assert all(
            before is after for before, after in zip(original, handles(viewer), strict=True)
        )
        np.testing.assert_array_equal(viewer._display_surface_colors(), initial_colors)
    assert [call for call in viewer.dvz.calls if call[0] == 'camera'] == camera_calls
    assert [call for call in viewer.dvz.calls if call[0] == 'grid'] == [('grid', 2, 2)]


def test_physical_plane_follows_cursor_mapping_and_axis_with_retained_adapter(viewer):
    viewer.apply_preset('physical-slice')
    adapter = viewer.physical_plane
    assert adapter.scene is viewer.scene and adapter.panel is viewer.panel
    first_corners = adapter.data.corners_um.copy()
    viewer.set_cursor(viewer.cursor.replace('ap', 0, viewer.slice_source.grid.shape))
    assert viewer.physical_plane is adapter
    assert not np.array_equal(adapter.data.corners_um, first_corners)
    np.testing.assert_array_equal(
        viewer.mesh_data.normalize_points(adapter.data.corners_um),
        adapter.transform(adapter.data.corners_um),
    )
    uploads = adapter.replacements
    viewer.set_cursor(viewer.cursor.replace('ml', 0, viewer.slice_source.grid.shape))
    assert adapter.replacements == uploads  # the AP plane did not move
    viewer.set_cursor(viewer.cursor.replace('ap', 1, viewer.slice_source.grid.shape))
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
    assert viewer.volume_opacity == 0.2
    viewer.set_physical_plane(True)
    assert viewer.plane_visible and viewer.volume_opacity == 0
    assert all(before is after for before, after in zip(original, handles(viewer), strict=True))


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
    moved = viewer.cursor.replace('ap', 0, viewer.slice_source.grid.shape)
    with pytest.raises(RuntimeError, match='source unavailable'):
        viewer.set_cursor(moved)
    assert viewer.cursor == moved
    assert not viewer.plane_visible and not adapter.visible
    assert not viewer._plane_visible_control.value
    assert viewer._review_error == 'Physical plane hidden after update failure: source unavailable'


def test_physical_updates_reuse_the_navigator_contrast_cache(viewer, monkeypatch):
    monkeypatch.setattr(np, 'percentile', lambda *a, **k: pytest.fail('contrast was rescanned'))
    viewer.set_physical_plane(True)
    viewer.set_cursor(viewer.cursor.replace('ap', 0, viewer.slice_source.grid.shape))
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
    viewer._slice_loader = SimpleNamespace(
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
    viewer.set_cursor(AtlasCursor(0, 0, 0))
    viewer.set_region_opacity(315, 0.3)
    original = handles(viewer)
    viewer.reset_review()
    assert viewer.cursor == AtlasCursor.centre(viewer.slice_source)
    assert not viewer.plane_visible and viewer.volume_opacity == 0
    assert viewer.plane_axis == 'ap' and viewer.plane_mode == 'wboit'
    assert viewer.plane_opacity == 0.72 and viewer.plane_cutoff == 0.5
    assert all(before is after for before, after in zip(original, handles(viewer), strict=True))


def test_extra_gui_keeps_linked_controls_and_reports_update_errors(viewer, monkeypatch):
    events = []
    monkeypatch.setattr(
        LinkedAtlasNavigator, '_draw_extra_gui', lambda *a: events.append('linked')
    )
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
    mesh, volumes, geometry = object(), object(), object()
    monkeypatch.setattr(review, 'bundled_asset_set', lambda: 'immutable-lock')
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
        lambda viewer, args, title: calls.append(('finish', args.frames, args.offscreen, title)),
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
        ],
    )
    assert review.main() == 0
    assert calls[:2] == [('assets', 'immutable-lock', '/assets/d070'), ('volume', '/assets/50um')]
    assert calls[2] == (
        'options',
        {
            'preset': 'labels',
            'mapping': 'allen',
            'width': 1400,
            'height': 1000,
            'ui_scale': 1.5,
            'enable_interaction': True,
            'enable_hover': False,
        },
    )
    assert calls[3] == ('finish', 3, None, 'D070 linked atlas review')
    assert calls[4] == ('close',)


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
    assert viewer.volume_opacity == 0.12


def test_failed_physical_preset_restores_previous_slice_and_volume_state(viewer, monkeypatch):
    viewer.apply_preset('volume-context')
    previous = (
        viewer.anatomy_visible,
        viewer.annotation_visible,
        viewer.boundaries_visible,
        viewer.volume_opacity,
        viewer._preset_control.value,
    )

    def failure():
        raise RuntimeError('injected plane source failure')

    monkeypatch.setattr(viewer, '_plane_data', failure)
    with pytest.raises(RuntimeError, match='injected'):
        viewer.apply_preset('physical-slice')
    assert (
        viewer.anatomy_visible,
        viewer.annotation_visible,
        viewer.boundaries_visible,
        viewer.volume_opacity,
        viewer._preset_control.value,
    ) == previous
    assert not viewer.plane_visible
