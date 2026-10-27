"""Scientific review state/lifetime checks without creating a native runtime."""

import ctypes
from types import SimpleNamespace

import numpy as np
import pytest

from examples import review_common
from examples import scientific_scene_review as review
from examples.bwm_probe import FIXTURE, _load_fixture
from ibl_datoviz import AtlasViewer
from ibl_datoviz.components import SampledPlane
from ibl_datoviz.probe_presentation import ProbePresentation

BASE_CLOSE = AtlasViewer.close


class FakeComponent:
    instances = []

    def __init__(self, dvz, scene, panel, data, **kwargs):
        self.scene, self.panel, self.data = scene, panel, data
        self.options = kwargs
        self.visible = True
        self.closed = False
        self.fail_visibility = False
        self.instances.append(self)

    def replace(self, data):
        self.data = data

    def set_visible(self, visible):
        if self.fail_visibility:
            self.fail_visibility = False
            raise RuntimeError('injected visibility failure')
        self.visible = visible

    def update_colors(self, colors):
        self.data = review.PointCollection.from_arrays(
            self.data.positions_um, colors, sizes_px=self.data.sizes_px
        )

    def update_sizes(self, sizes):
        self.data = review.PointCollection.from_arrays(
            self.data.positions_um, self.data.colors, sizes_px=sizes
        )

    def close(self):
        self.closed = True


@pytest.fixture
def viewer(monkeypatch):
    FakeComponent.instances = []

    def initialize(self, mesh, **kwargs):
        self.mesh_data = mesh
        self.scene, self.panel, self.app, self.view = object(), object(), object(), object()
        self.camera_angles = (0.1, 0.2, 0.3)
        self.probe_sites, self.probe_table = object(), object()
        self.native_visibility, self.path_styles = {}, {}
        self._probe_presentation = ProbePresentation(self)
        self._insertions = SimpleNamespace(
            set_insertion=lambda *args, **options: insertion(self, *args, **options),
            set_visible=lambda key, value: self.path_styles[key].update(visible=value),
            set_color=lambda key, value: self.path_styles[key].update(color=value),
            set_width=lambda key, value: self.path_styles[key].update(width=value),
        )
        self._closed = False
        self.ui_scale = 1.0
        self._sidebar = SimpleNamespace(available=lambda _: (300.0, 600.0))
        self.dvz = SimpleNamespace(
            dvz_visual_set_visible=lambda handle, visible: (
                self.native_visibility.__setitem__(handle, visible) or 0
            )
        )

    def insertion(self, insertion_id, points, *, color, width_px):
        self.path_styles[insertion_id] = {
            'points': points,
            'color': color,
            'width': width_px,
            'visible': True,
        }

    def probe_data(self, sites, **kwargs):
        self.data = sites

    def surface(self, visible):
        self.surface_visible = visible

    def close(self):
        self._closed = True

    monkeypatch.setattr(AtlasViewer, '__init__', initialize)
    monkeypatch.setattr(AtlasViewer, '_insertion_collection', lambda self: self._insertions)
    monkeypatch.setattr(ProbePresentation, 'set_data', probe_data)
    monkeypatch.setattr(
        ProbePresentation, 'mapped_region_ids', lambda self, sites: sites.allen_region_ids
    )
    monkeypatch.setattr(ProbePresentation, 'upload_sites', lambda self, *args, **kwargs: None)
    monkeypatch.setattr(AtlasViewer, 'set_surface_visible', surface)
    monkeypatch.setattr(AtlasViewer, 'close', close)
    monkeypatch.setattr(review, 'PointCollectionVisual', FakeComponent)
    monkeypatch.setattr(review, 'SampledPlaneVisual', FakeComponent)
    monkeypatch.setattr(
        review,
        'ReviewControls',
        lambda viewer: SimpleNamespace(
            draw=lambda gui: None,
            reset=lambda: setattr(viewer, 'camera_angles', (0.1, 0.2, 0.3)),
        ),
    )
    sites, _provenance = _load_fixture(FIXTURE)
    plane = SampledPlane.from_arrays(
        [[0, 0, 0], [0, 10, 0], [20, 0, 0], [20, 10, 0]],
        np.full((3, 4, 4), 255, np.uint8),
    )
    instance = review.ScientificSceneReview(SimpleNamespace(normalize_points=lambda pts: pts))
    instance.configure_review(
        sites,
        plane,
        [('real-path-one', sites.positions_um), ('real-path-two', sites.positions_um)],
    )
    yield instance
    instance.close()


def test_real_firing_rate_points_have_explicit_range_owned_data_and_nan_alpha():
    sites, _metadata = _load_fixture(FIXTURE)
    limits = review.firing_rate_range(sites)
    finite = sites.values[np.isfinite(sites.values)]
    assert limits == tuple(np.quantile(finite, (0.05, 0.95)))
    scalar = review.point_payload(sites, limits)
    assert np.any(~np.isfinite(sites.values))
    assert np.all(scalar.colors[~np.isfinite(sites.values), 3] == 0)
    assert np.all(scalar.colors[np.isfinite(sites.values), 3] == 255)
    assert not np.shares_memory(scalar.positions_um, sites.positions_um)
    assert not scalar.positions_um.flags.writeable
    uniform = review.point_payload(sites, limits, mode='uniform')
    assert np.all(uniform.colors == review.POINT_COLOR)
    np.testing.assert_array_equal(uniform.positions_um, sites.positions_um)


def test_presets_retain_scene_panel_view_camera_and_components(viewer):
    resources = (
        viewer.scene,
        viewer.panel,
        viewer.app,
        viewer.view,
        viewer.review_points,
        viewer.review_plane,
        viewer.probe_table,
    )
    viewer.camera_angles = (1.0, 2.0, 3.0)
    for preset in ('single-probe', 'multiple-insertions', 'mixed', 'atlas'):
        viewer.apply_preset(preset)
        assert (
            viewer.scene,
            viewer.panel,
            viewer.app,
            viewer.view,
            viewer.review_points,
            viewer.review_plane,
            viewer.probe_table,
        ) == resources
        assert viewer.camera_angles == (1.0, 2.0, 3.0)
    viewer.apply_preset('mixed')
    assert viewer.review_points.visible and viewer.review_plane.visible
    assert not viewer.native_visibility[viewer.probe_sites]
    assert viewer.path_styles[review.BWM_ID]['visible']
    assert not viewer.path_styles['real-path-one']['visible']


def test_independent_path_styles_survive_preset_changes_and_layer_gate(viewer):
    viewer.apply_preset('multiple-insertions')
    viewer.style_insertion('real-path-one', visible=False, color=review.COLORS[2], width=9.0)
    viewer.set_layer_visible('insertions', False)
    viewer.set_layer_visible('insertions', True)
    assert not viewer.path_styles['real-path-one']['visible']
    assert viewer.path_styles['real-path-two']['visible']
    viewer.apply_preset('atlas')
    viewer.apply_preset('multiple-insertions')
    assert not viewer.path_styles['real-path-one']['visible']
    assert viewer.path_styles['real-path-one']['width'] == 9.0
    assert viewer.path_styles['real-path-one']['color'] == review.COLORS[2]
    assert viewer.path_styles['real-path-two']['width'] == review.WIDTHS[1]


def test_point_updates_and_opacity_retain_components_and_source_plane(viewer):
    points, plane = viewer.review_points, viewer.review_plane
    viewer.set_point_mode('uniform')
    viewer.set_point_size(12)
    viewer.set_plane_opacity(0.2)
    assert viewer.review_points is points and viewer.review_plane is plane
    assert np.all(points.data.sizes_px == 12)
    assert np.all(points.data.colors[:, :3] == review.POINT_COLOR[:3])
    assert np.all(points.data.colors[:, 3] == round(review.POINT_COLOR[3] * viewer.point_opacity))
    assert np.all(plane.data.rgba[..., 3] == 51)
    assert np.all(viewer.base_plane.rgba[..., 3] == 255)
    np.testing.assert_array_equal(plane.data.corners_um, viewer.base_plane.corners_um)


def test_physical_mode_rebuilds_only_plane_and_preserves_hidden_state(viewer):
    old_plane = viewer.review_plane
    resources = viewer.scene, viewer.panel, viewer.app, viewer.view, viewer.review_points
    viewer.set_plane_mode('mask', cutoff=0.25)
    assert old_plane.closed
    assert not viewer.review_plane.visible
    assert viewer.review_plane.options['depth_policy'] == 'physical'
    assert viewer.review_plane.options['alpha_mode'] == 'mask'
    assert viewer.review_plane.options['alpha_cutoff'] == 0.25
    assert (viewer.scene, viewer.panel, viewer.app, viewer.view, viewer.review_points) == resources
    replacement = viewer.review_plane
    viewer.set_plane_mode('mask', cutoff=0.25)
    assert viewer.review_plane is replacement


def test_failed_plane_rebuild_preserves_live_previous_component(viewer, monkeypatch):
    previous = viewer.review_plane

    def fail(*args, **kwargs):
        raise RuntimeError('injected native failure')

    monkeypatch.setattr(viewer, '_new_plane', fail)
    assert not viewer._action(viewer.set_plane_mode, 'mask')
    assert viewer.review_plane is previous and not previous.closed
    assert viewer.plane_mode == 'wboit'
    assert 'injected native failure' in viewer._review_error


def test_failed_preset_restores_layers_and_current_preset(viewer):
    before = viewer.review_layers.copy()
    viewer.review_plane.fail_visibility = True
    assert not viewer._action(viewer.apply_preset, 'mixed')
    assert viewer.review_layers == before
    assert viewer.preset == 'single-probe'
    assert not viewer.review_points.visible and not viewer.review_plane.visible
    assert not viewer._closed


def test_missing_optional_w39_is_disabled_without_substitute(tmp_path, viewer):
    paths, note = review.optional_insertions(tmp_path / 'absent.npz', tmp_path / 'absent.json')
    assert paths == []
    assert 'tools/build_w39_insertions.py' in note
    viewer.close()
    # Reconfigure a fresh fake viewer with the actual BWM fixture and no optional paths.
    mesh = SimpleNamespace(normalize_points=lambda pts: pts)
    single = review.ScientificSceneReview(mesh)
    single.configure_review(viewer.review_sites, viewer.base_plane, unavailable_note=note)
    assert 'multiple-insertions' not in single._available_presets
    with pytest.raises(ValueError, match='Multiple insertions unavailable'):
        single.apply_preset('multiple-insertions')
    assert single.preset == 'single-probe'
    assert set(single._paths) == {review.BWM_ID}
    single.close()


def test_present_optional_w39_corruption_is_not_silently_treated_as_absence(tmp_path):
    archive, sidecar = tmp_path / 'paths.npz', tmp_path / 'paths.json'
    archive.write_bytes(b'invalid archive')
    sidecar.write_text('{"format":"untrusted"}')
    with pytest.raises(ValueError, match='unexpected W39'):
        review.optional_insertions(archive, sidecar)


def test_explicit_reset_restores_styles_layers_and_camera(viewer):
    viewer.camera_angles = (1.0, 2.0, 3.0)
    viewer.apply_preset('mixed')
    viewer.set_point_mode('uniform')
    viewer.set_point_size(12)
    viewer.set_point_opacity(0.1)
    viewer.set_plane_mode('mask', cutoff=0.9)
    viewer.set_plane_opacity(0.2)
    viewer.style_insertion('real-path-one', visible=False, width=11)
    viewer.reset_review()
    assert viewer.preset == 'single-probe'
    assert viewer.camera_angles == (0.1, 0.2, 0.3)
    assert viewer.point_mode == 'scalar' and viewer.point_size == 6
    assert viewer.point_opacity == 0.7
    assert viewer.plane_mode == 'wboit' and viewer.plane_opacity == 0.65
    assert viewer.plane_cutoff == 0.5
    assert viewer._insertion_styles['real-path-one']['visible']
    assert viewer.path_styles['real-path-one']['width'] == review.WIDTHS[0]


def test_close_releases_components_before_scene_and_is_idempotent(viewer):
    points, plane = viewer.review_points, viewer.review_plane
    viewer.close()
    viewer.close()
    assert points.closed and plane.closed and viewer._closed
    assert viewer.review_points is None and viewer.review_plane is None


def test_single_probe_encoding_changes_visible_points_and_preserves_table_camera(viewer):
    viewer.apply_preset('single-probe')
    assert not viewer.review_points.visible
    assert viewer.native_visibility[viewer.probe_sites]
    assert viewer.path_styles[review.BWM_ID]['visible']
    resources = viewer.scene, viewer.panel, viewer.app, viewer.view, viewer.probe_table
    viewer.camera_angles = (1.0, 2.0, 3.0)
    viewer.set_point_opacity(0.4)
    viewer.set_point_mode('uniform')
    assert np.all(viewer.review_points.data.colors[:, 3] == 72)
    viewer.set_layer_visible('sites', True)
    viewer.set_point_mode('scalar')
    assert viewer.native_visibility[viewer.probe_sites]
    assert viewer.point_opacity == 0.4
    assert viewer.camera_angles == (1.0, 2.0, 3.0)
    assert (viewer.scene, viewer.panel, viewer.app, viewer.view, viewer.probe_table) == resources
    finite = np.isfinite(viewer.review_sites.values)
    assert np.all(viewer.review_points.data.colors[finite, 3] == 102)
    assert np.all(viewer.review_points.data.colors[~finite, 3] == 0)


def test_point_opacity_zero_and_restore_preserve_nan_and_authored_colors(viewer):
    viewer.apply_preset('mixed')
    component = viewer.review_points
    before_rgb = component.data.colors[:, :3].copy()
    viewer.set_point_opacity(0)
    assert np.all(component.data.colors[:, 3] == 0)
    assert viewer.review_points is component and component.visible
    viewer.set_point_mode('uniform')
    assert np.all(component.data.colors[:, 3] == 0)
    viewer.set_point_mode('scalar')
    viewer.set_point_opacity(1)
    np.testing.assert_array_equal(component.data.colors[:, :3], before_rgb)
    finite = np.isfinite(viewer.review_sites.values)
    assert np.all(component.data.colors[finite, 3] == 255)
    assert np.all(component.data.colors[~finite, 3] == 0)
    with pytest.raises(ValueError, match='point opacity'):
        viewer.set_point_opacity(float('nan'))
    assert viewer.point_opacity == 1


def test_finalizer_closes_components_before_the_borrowed_scene(viewer, monkeypatch):
    points, plane = viewer.review_points, viewer.review_plane
    closed = []

    def close_scene(instance):
        assert points.closed and plane.closed
        if not instance._closed:
            closed.append(instance.scene)
        instance._closed = True

    monkeypatch.setattr(AtlasViewer, 'close', close_scene)
    viewer.__del__()
    assert points.closed and plane.closed
    assert viewer._closed and closed == [viewer.scene]
    viewer.__del__()
    assert len(closed) == 1


@pytest.mark.parametrize(('result', 'dropped'), [(-1, 0), (0, 1)])
def test_scientific_data_failure_balances_separate_window(viewer, result, dropped):
    calls = []
    viewer._show_scientific_data.value = True
    viewer._sidebar = SimpleNamespace(
        _window=lambda _gui, title, opened, **_kwargs: (
            calls.append((title, opened.value)) or True
        )
    )
    viewer.dvz.dvz_gui_button = lambda *_: False
    viewer.dvz.dvz_gui_text = lambda *_: None
    viewer.dvz.dvz_gui_collapsing_header = lambda *_: False
    viewer.dvz.dvz_gui_table_draw = lambda *_: (result, [], dropped)
    viewer.dvz.dvz_gui_end = lambda *_: calls.append('end')
    with pytest.raises(RuntimeError, match='scientific data table'):
        viewer._draw_data_tables_gui(None)
    assert calls == [(b'Data table', True), 'end']
    assert viewer._show_scientific_data.value


def test_primary_layers_read_authoritative_state_and_hide_diagnostics(viewer):
    drawn = []
    labels = []
    viewer.dvz.dvz_gui_button = lambda *_: False
    viewer.dvz.dvz_gui_checkbox = lambda _gui, label, pointer: labels.append(label) or False
    viewer.dvz.dvz_gui_collapsing_header = lambda *_: False
    viewer.dvz.dvz_gui_same_line = lambda *_: None
    viewer.dvz.dvz_gui_text = lambda *_: None
    viewer.dvz.dvz_gui_color_edit4 = lambda *_: None
    viewer.dvz.dvz_gui_set_next_item_width = lambda *_: None
    viewer.dvz.dvz_gui_combo = lambda *_: False
    viewer.dvz.dvz_gui_slider_float = lambda *_: False
    viewer._draw_point_gui = lambda _gui: drawn.append('points')
    viewer._draw_plane_gui = lambda _gui: drawn.append('plane')
    viewer._draw_insertion_gui = lambda _gui: drawn.append('insertions')
    viewer._layer_controls['sites'].value = False
    viewer._draw_layer_controls(None)
    assert drawn == []  # Appearance starts collapsed.
    assert labels == [b'Brain context', b'Insertion paths', b'Recording sites']
    assert viewer._layer_controls['sites'].value
    assert viewer.camera_angles == (0.1, 0.2, 0.3)


@pytest.mark.parametrize('fail', [False, True])
def test_layers_window_is_persistent_dockable_and_balances_scope(viewer, fail):
    calls = []
    viewer._sidebar = SimpleNamespace(rect=lambda _: (0, 500, 1100, 170))
    viewer.dvz.DVZ_GUI_DOCK_SLOT_RIGHT = 2
    viewer.dvz.dvz_gui_dock_window_once = lambda *args: calls.append(('dock', args[1:])) or 0
    viewer.dvz.dvz_gui_begin = lambda *args: calls.append(('begin', args[1:])) or True
    viewer.dvz.dvz_gui_end = lambda *_: calls.append('end')

    def draw(_gui):
        calls.append('controls')
        if fail:
            raise RuntimeError('layer draw failed')

    viewer._draw_layer_controls = draw
    if fail:
        with pytest.raises(RuntimeError, match='layer draw failed'):
            viewer._draw_auxiliary_gui(None)
    else:
        viewer._draw_auxiliary_gui(None)
    assert calls == [
        ('begin', (b'Layers', None, 0)),
        'controls',
        'end',
    ]
    assert viewer.layers_rect == (0, 500, 1100, 170)


def test_recording_is_visible_at_start_and_layer_toggles_preserve_styles(viewer):
    assert viewer.preset == 'single-probe'
    assert viewer.review_layers == dict(
        atlas=True, sites=True, points=False, plane=False, insertions=True
    )
    assert viewer.native_visibility[viewer.probe_sites]
    before = viewer.path_styles[review.BWM_ID].copy()
    for name in ('sites', 'insertions', 'atlas'):
        viewer.set_layer_visible(name, False)
        viewer.set_layer_visible(name, True)
    assert viewer.path_styles[review.BWM_ID] == before
    assert viewer.camera_angles == (0.1, 0.2, 0.3)


def test_site_color_changes_preserve_population_identities_and_visibility(viewer):
    uploads = []
    viewer._probe_presentation.mapped_region_ids = lambda sites: sites.allen_region_ids
    viewer._probe_presentation.upload_sites = lambda positions, **kwargs: uploads.append(
        (positions, kwargs)
    )
    for mode in ('uniform', 'scalar'):
        viewer.set_site_mode(mode)
        assert viewer.site_mode == mode
        assert viewer.review_layers['sites']
        positions, options = uploads[-1]
        np.testing.assert_array_equal(positions, viewer.review_sites.positions_um)
        np.testing.assert_array_equal(options['mapped_ids'], viewer.review_sites.allen_region_ids)
        assert np.all(options['colors'][:, 3] == 255)
    missing = ~np.isfinite(viewer.review_sites.values)
    np.testing.assert_array_equal(
        uploads[-1][1]['colors'][missing, :3], np.tile([110, 116, 126], (missing.sum(), 1))
    )


def test_atlas_display_visibility_is_preserved_by_failed_preset(viewer):
    viewer.set_surface_visible(False)
    assert not viewer.review_layers['atlas']
    assert not viewer._layer_controls['atlas'].value
    viewer.review_plane.fail_visibility = True
    with pytest.raises(RuntimeError, match='visibility failure'):
        viewer.apply_preset('mixed')
    assert not viewer.surface_visible
    assert not viewer.review_layers['atlas']
    assert not viewer._layer_controls['atlas'].value


def test_major_context_loading_delegates_to_hash_verified_shared_catalog(monkeypatch, tmp_path):
    catalog, geometry = object(), (object(), object())
    calls = []
    monkeypatch.setattr(review_common, 'bundled_surface_catalog', lambda: catalog, raising=False)
    monkeypatch.setattr(
        review_common,
        'load_surface_catalog',
        lambda path, source: calls.append((path, source)) or geometry,
        raising=False,
    )
    assert review.load_major_context(tmp_path) == (catalog, geometry)
    assert calls == [(tmp_path, catalog)]


def test_recording_caption_tracks_supplied_provenance_without_default_identity():
    caption, values = review.recording_description(
        {
            'dataset': {'name': 'other_release', 'version': '2.0'},
            'insertion': {'subject': 'OtherSubject', 'probe_name': 'probe01'},
            'derivation': {'value': 'declared prepared site statistic'},
        }
    )
    assert caption == 'other_release 2.0 / OtherSubject probe01'
    assert values == 'declared prepared site statistic'
    assert review.recording_description(None) == (
        'Supplied recording',
        'prepared recording-site values',
    )


def test_insertion_rows_change_only_active_path_and_preserve_other_styles(viewer):
    viewer.apply_preset('multiple-insertions')
    before_bwm = viewer._insertion_styles[review.BWM_ID].copy()
    labels = []
    viewer.dvz.dvz_gui_same_line = lambda *_: None
    viewer.dvz.dvz_gui_set_next_item_width = lambda *_: None
    viewer.dvz.dvz_gui_text = lambda *_: None
    viewer.dvz.dvz_gui_collapsing_header = lambda *_: False

    def checkbox(_gui, label, pointer):
        labels.append(label)
        if label.endswith(b'##real-path-one'):
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_bool))[0] = False
            return True
        return False

    def color(_gui, label, rgba, _flags):
        if label == b'##color_real-path-two':
            rgba[0], rgba[1], rgba[2] = 0.5, 0.25, 1.0
            return True
        return False

    def width(_gui, label, pointer, _low, _high):
        if label == b'##width_px_real-path-two':
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_float))[0] = 6.0
            return True
        return False

    viewer.dvz.dvz_gui_checkbox = checkbox
    viewer.dvz.dvz_gui_color_edit4 = color
    viewer.dvz.dvz_gui_slider_float = width
    viewer._draw_insertion_gui(None)
    assert len(labels) == 2 and all(b'bwm' not in label.lower() for label in labels)
    assert not viewer._insertion_styles['real-path-one']['visible']
    assert viewer._insertion_styles['real-path-two']['color'] == (128, 64, 255, 255)
    assert viewer._insertion_styles['real-path-two']['width'] == 6.0
    assert viewer._insertion_styles[review.BWM_ID] == before_bwm
    assert not viewer.path_styles[review.BWM_ID]['visible']


def test_site_radius_preserves_scalar_missingness_and_is_transactional(viewer):
    uploads = []
    viewer._probe_presentation.upload_sites = lambda positions, **kwargs: uploads.append(
        (positions, kwargs)
    )
    viewer.set_site_mode('scalar')
    viewer.set_site_radius(7.0)
    assert viewer.site_mode == 'scalar' and viewer.site_radius_um == 7.0
    assert uploads[-1][1]['radius_um'] == 7.0
    np.testing.assert_array_equal(uploads[-1][0], viewer.review_sites.positions_um)
    colors = uploads[-1][1]['colors']
    missing = ~np.isfinite(viewer.review_sites.values)
    np.testing.assert_array_equal(
        colors[missing, :3], np.tile([110, 116, 126], (missing.sum(), 1))
    )
    assert np.all(colors[:, 3] == 255)
    for invalid in (0, -1, np.nan, np.inf):
        with pytest.raises(ValueError, match='radius'):
            viewer.set_site_radius(invalid)
    assert viewer.site_radius_um == 7.0 and viewer.site_mode == 'scalar'

    def fail(*args, **kwargs):
        raise RuntimeError('upload failed')

    viewer._probe_presentation.upload_sites = fail
    with pytest.raises(RuntimeError, match='upload failed'):
        viewer.set_site_radius(12.0)
    assert viewer.site_radius_um == 7.0 and viewer._site_radius_control.value == 7.0


@pytest.mark.parametrize('guard', ['owner_thread', 'selection_callback'])
def test_close_guards_preserve_scientific_components(viewer, monkeypatch, guard):
    points, plane = viewer.review_points, viewer.review_plane
    with monkeypatch.context() as patch:
        if guard == 'owner_thread':
            patch.setattr(viewer, '_owner_thread', -1, raising=False)
        else:
            patch.setattr(viewer, 'selection', SimpleNamespace(_notifying=True), raising=False)
        with pytest.raises(RuntimeError):
            viewer.close()
    assert viewer.review_points is points and viewer.review_plane is plane
    assert not points.closed and not plane.closed and not viewer._closed


def test_close_during_gui_callback_defers_scientific_components(viewer, monkeypatch):
    points, plane = viewer.review_points, viewer.review_plane
    stopped = []
    viewer.dvz.dvz_app_stop = stopped.append
    viewer._gui_callback_depth = 1
    monkeypatch.setattr(AtlasViewer, 'close', BASE_CLOSE)
    viewer.close()
    assert stopped == [viewer.app]
    assert viewer._close_pending and not viewer._closed
    assert not points.closed and not plane.closed

    def close_scene(instance):
        assert points.closed and plane.closed
        instance._closed = True

    monkeypatch.setattr(AtlasViewer, 'close', close_scene)
    viewer._gui_callback_depth = 0
    viewer.close()
    assert points.closed and plane.closed and viewer._closed
