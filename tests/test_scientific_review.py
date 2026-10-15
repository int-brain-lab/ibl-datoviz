"""Scientific review state/lifetime checks without creating a native runtime."""

from types import SimpleNamespace

import numpy as np
import pytest

from examples import scientific_scene_review as review
from examples.bwm_probe import FIXTURE, _load_fixture
from ibl_datoviz import AtlasViewer, SampledPlane


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
        self._closed = False
        self.ui_scale = 1.0
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
        self.probe_data = sites

    def surface(self, visible):
        self.surface_visible = visible

    def close(self):
        self._closed = True

    monkeypatch.setattr(AtlasViewer, '__init__', initialize)
    monkeypatch.setattr(AtlasViewer, 'set_insertion', insertion)
    monkeypatch.setattr(AtlasViewer, 'set_probe_data', probe_data)
    monkeypatch.setattr(AtlasViewer, 'set_surface_visible', surface, raising=False)
    monkeypatch.setattr(
        AtlasViewer,
        'set_insertion_visible',
        lambda self, key, value: self.path_styles[key].update(visible=value),
    )
    monkeypatch.setattr(
        AtlasViewer,
        'set_insertion_color',
        lambda self, key, value: self.path_styles[key].update(color=value),
    )
    monkeypatch.setattr(
        AtlasViewer,
        'set_insertion_width',
        lambda self, key, value: self.path_styles[key].update(width=value),
    )
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
    before = viewer.layers.copy()
    viewer.review_plane.fail_visibility = True
    assert not viewer._action(viewer.apply_preset, 'mixed')
    assert viewer.layers == before
    assert viewer.preset == 'atlas'
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
    assert single.preset == 'atlas'
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
    assert viewer.preset == 'atlas'
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
    assert viewer.review_points.visible
    assert not viewer.native_visibility[viewer.probe_sites]
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
    assert calls == [(b'Scientific data', True), 'end']
    assert viewer._show_scientific_data.value
