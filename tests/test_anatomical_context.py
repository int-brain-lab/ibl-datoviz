"""Major geometry remains independent from fine selection and mapping."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.context import AtlasContextSurface
from tests import FIXTURES
from tests.test_atlas import FIXTURE, FakeDatoviz


class ContextNative(FakeDatoviz):
    def __init__(self):
        super().__init__()
        self.visuals = []
        self.destroyed = []

    def dvz_mesh(self, *_args):
        visual = SimpleNamespace(name='mesh', visible=True, attributes={})
        self.visuals.append(visual)
        return visual

    def dvz_visual_set_data(self, visual, name, values):
        visual.attributes[name] = np.array(values, copy=True)
        return super().dvz_visual_set_data(visual, name, values)

    def dvz_visual_set_data_many(self, visual, values):
        visual.attributes.update({k: np.array(v, copy=True) for k, v in values.items()})
        return super().dvz_visual_set_data_many(visual, values)

    def dvz_visual_set_index_data(self, visual, values):
        visual.indices = np.array(values, copy=True)
        return super().dvz_visual_set_index_data(visual, values)

    def dvz_visual_set_visible(self, visual, visible):
        visual.visible = bool(visible)
        return super().dvz_visual_set_visible(visual, visible)

    def dvz_visual_set_query_capabilities(self, visual, flags):
        visual.query_flags = flags
        return 0

    def dvz_visual_set_target_link_keys(self, visual, target, channel, keys):
        visual.keys = np.array(keys, copy=True)
        return super().dvz_visual_set_target_link_keys(visual, target, channel, keys)

    def dvz_visual_set_alpha_mode(self, visual, mode):
        visual.alpha_mode = mode
        return super().dvz_visual_set_alpha_mode(visual, mode)

    def dvz_visual_destroy(self, visual):
        self.destroyed.append(visual)


def prepared(mesh, source_allen_id=8):
    geometry = SimpleNamespace(
        positions_um=mesh.positions_um.copy(),
        normals=mesh.normals.copy(),
        indices=mesh.indices.copy(),
        asset=SimpleNamespace(
            reference_space_id=mesh.reference_space,
            variant='source-native',
            source_allen_id=source_allen_id,
        ),
    )
    return AtlasContextSurface.from_geometry(
        geometry, mesh, color=(120, 175, 140), name=str(source_allen_id)
    )


def viewer_context(source_allen_id=8, **kwargs):
    mesh = AtlasMesh.from_pack(FIXTURE)
    return AtlasViewer(
        mesh,
        anatomical_context=[prepared(mesh, source_allen_id)],
        anatomy_presentation='major',
        datoviz=ContextNative(),
        **kwargs,
    )


def context_visual(viewer):
    return viewer._anatomical_context.entries[0].visual


def test_major_context_stable_with_selected_translucent_fine_faces_and_mapping():
    with viewer_context() as viewer:
        context = context_visual(viewer)
        assert context.visible
        assert not viewer.mesh.visible
        assert viewer.visible_region_ids() == ()
        positions, colors = (
            context.attributes['position'].copy(),
            context.attributes['color'].copy(),
        )
        indices = context.indices.copy()
        viewer.set_selected_region_ids((-315,))
        assert viewer.visible_region_ids() == (-315,)
        assert viewer.mesh.visible
        assert np.max(viewer._surface_presentation.base_colors[:, 3]) <= round(255 * 0.18)
        assert not viewer._surface_state.handle.active
        np.testing.assert_array_equal(context.indices, indices)
        np.testing.assert_array_equal(context.attributes['color'], colors)
        np.testing.assert_array_equal(context.attributes['position'], positions)
        viewer.set_mapping('cosmos')
        assert context.visible and not viewer.mesh.visible
        np.testing.assert_array_equal(context.attributes['color'], colors)
        viewer.set_mapping('allen')
        assert context.query_flags == viewer.dvz.DVZ_QUERY_CAPABILITY_FACE
        assert set(context.keys.view(np.int64)) == {-8, 8}


def test_context_side_filter_and_original_world_reference_survive_explosion():
    with viewer_context() as viewer:
        context = context_visual(viewer)
        original = context.attributes['position'].copy()
        viewer.set_selected_region_ids((-315,))
        viewer.set_hemisphere('left')
        assert context.visible
        assert set(context.keys.view(np.int64)) == {-8}
        viewer.set_explode(0.7)
        assert context.visible
        np.testing.assert_array_equal(context.attributes['position'], original)
        viewer.set_hemisphere_visible('left', False)
        assert not context.visible
        viewer.set_hemisphere('both')
        assert context.visible and set(context.keys.view(np.int64)) == {-8, 8}


def test_context_opacity_visibility_and_sparse_hover_preserve_styles():
    with viewer_context() as viewer:
        context = context_visual(viewer)
        viewer.set_context_opacity(0.27)
        colors = context.attributes['color'].copy()
        assert set(colors[:, 3]) == {69}
        viewer.set_surface_visible(False)
        assert not context.visible
        viewer.set_surface_visible(True)
        np.testing.assert_array_equal(context.attributes['color'], colors)
        before = len(viewer.dvz.calls)
        viewer._set_hovered_region_ids((-315,))
        assert not any(
            c[0] in ('data', 'data_many', 'indices', 'link_keys')
            for c in viewer.dvz.calls[before:]
        )
        viewer.set_anatomy_presentation('detailed')
        assert not context.visible and viewer.mesh.visible
        viewer.set_anatomy_presentation('major')
        assert context.visible and not viewer.mesh.visible


def test_context_arrays_own_source_storage_and_close_before_scene():
    viewer = viewer_context()
    surface = viewer._anatomical_context.surfaces[0]
    assert not np.shares_memory(surface.geometry.mesh.positions_um, viewer.mesh_data.positions_um)
    assert not surface.geometry.mesh.positions_um.flags.writeable
    context = context_visual(viewer)
    native = viewer.dvz
    viewer.close()
    assert any(v is context for v in native.destroyed)
    assert native.calls[-1] == ('destroy_scene',)


def test_context_opacity_failure_restores_actual_native_colors(monkeypatch):
    with viewer_context() as viewer:
        context = context_visual(viewer)
        old_colors = context.attributes['color'].copy()
        original = viewer.dvz.dvz_visual_set_data
        failures = []

        def fail_once(visual, name, values):
            result = original(visual, name, values)
            if visual is context and not failures:
                failures.append(True)
                return -1
            return result

        monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_data', fail_once)
        with pytest.raises(RuntimeError):
            viewer.set_context_opacity(0.9)
        assert viewer.context_opacity == 0.12
        assert not viewer._closed
        np.testing.assert_array_equal(context.attributes['color'], old_colors)


def test_context_midline_predicate_uses_original_world_ml():
    mesh = AtlasMesh.from_pack(FIXTURE)
    surface = prepared(mesh)
    geometry = surface.geometry
    render = geometry.mesh
    np.testing.assert_allclose(render.positions, mesh.normalize_points(render.positions_um))
    signs = np.where(render.mapping_ids('allen') < 0, -1, 1)
    np.testing.assert_allclose(geometry.fragment_clip[:, 0], signs * render.positions_um[:, 0])
    np.testing.assert_array_equal(geometry.fragment_clip[:, 1], signs > 0)


def test_failed_context_replacement_restores_original_visible_visual(monkeypatch):
    with viewer_context() as viewer:
        native = viewer.dvz
        original_context = viewer._anatomical_context
        original_visual = context_visual(viewer)
        viewer.set_selected_region_ids((-315,))
        assert viewer.visible_region_ids() == (-315,)
        original = native.dvz_visual_set_visible
        failures = []

        def fail_old_hide(visual, visible):
            result = original(visual, visible)
            if visual is original_visual and not visible and not failures:
                failures.append(True)
                return -1
            return result

        monkeypatch.setattr(native, 'dvz_visual_set_visible', fail_old_hide)
        with pytest.raises(RuntimeError):
            viewer.set_anatomical_context([prepared(viewer.mesh_data, 315)])
        assert viewer._anatomical_context is original_context
        assert viewer.visible_region_ids() == (-315,)
        assert viewer.mesh.visible
        assert original_visual.visible
        assert not viewer._closed
        assert not any(v is original_visual for v in native.destroyed)


@pytest.mark.parametrize('opacity', [0, 0.12, 0.9, 1.0])
def test_context_keeps_wboit_through_full_opacity_sweep(opacity):
    with viewer_context() as viewer:
        viewer.set_context_opacity(opacity)
        visual = context_visual(viewer)
        assert visual.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT
        assert visual.visible == (opacity > 0)


def test_selected_displayed_coarse_parent_only_accents_context():
    with viewer_context(source_allen_id=315) as viewer:
        context = context_visual(viewer)
        entry = viewer._anatomical_context.entries[0]
        positions = context.attributes['position'].copy()
        colors = context.attributes['color'].copy()
        indices = context.indices.copy()
        viewer.set_selected_region_ids((-315,))
        assert viewer.selected_region_ids() == (-315,)
        assert viewer.visible_region_ids() == ()
        assert not viewer.mesh.visible and context.visible
        assert tuple(entry.state.words) == (viewer.dvz.DVZ_ITEM_STATE_SELECTED, 0)
        np.testing.assert_array_equal(context.attributes['position'], positions)
        np.testing.assert_array_equal(context.attributes['color'], colors)
        np.testing.assert_array_equal(context.indices, indices)
        before = len(viewer.dvz.calls)
        viewer._set_hovered_region_ids((-315,))
        assert not any(
            c[0] in ('data', 'data_many', 'indices', 'link_keys')
            for c in viewer.dvz.calls[before:]
        )
        viewer._set_hovered_region_ids(())
        viewer.clear_selection()
        assert not np.any(entry.state.words)
        assert not viewer.mesh.visible and context.visible


def test_coarse_descendants_only_overlay_when_also_explicitly_selected():
    catalog = open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json')
    with viewer_context(source_allen_id=8, catalog=catalog) as viewer:
        viewer.set_selected_region_ids((-8,))
        assert viewer._signed_focus_ids() == (-315, -8)
        assert viewer.visible_region_ids() == ()
        viewer.set_selected_region_ids((-8, 315))
        assert viewer.selected_region_ids() == (-8, 315)
        assert viewer.visible_region_ids() == (315,)
        entry = viewer._anatomical_context.entries[0]
        assert tuple(entry.state.words) == (viewer.dvz.DVZ_ITEM_STATE_SELECTED, 0)
        assert context_visual(viewer).visible


def test_context_replacement_updates_selected_parent_fine_overlay():
    with viewer_context(source_allen_id=8) as viewer:
        viewer.set_selected_region_ids((-315,))
        assert viewer.visible_region_ids() == (-315,)
        viewer.set_anatomical_context([prepared(viewer.mesh_data, 315)])
        assert viewer.selected_region_ids() == (-315,)
        assert viewer.visible_region_ids() == ()
        assert context_visual(viewer).visible
        viewer.set_anatomical_context([prepared(viewer.mesh_data, 8)])
        assert viewer.visible_region_ids() == (-315,)


@pytest.mark.parametrize('zero_side', ['left', 'right', None])
def test_context_zero_plane_fragment_ownership_matches_atlas(zero_side):
    atlas = AtlasMesh.from_pack(FIXTURE)
    if zero_side is None:
        atlas = replace(atlas, _presentation_boundary=None)
    else:
        atlas = replace(
            atlas,
            _presentation_boundary=replace(atlas._presentation_boundary, on_plane_side=zero_side),
        )
    surface = prepared(atlas)
    geometry = surface.geometry
    original_ml = geometry.mesh.positions_um[:, 0]
    keys = geometry.mesh.mapping_ids('allen')
    clip = geometry.fragment_clip
    # Evaluate the same strict/inclusive coverage predicate as the renderer.
    covered = (clip[:, 0] > 0) | ((clip[:, 0] == 0) & (clip[:, 1] != 0))
    on_plane = original_ml == 0
    assert np.any(on_plane & (keys < 0)) and np.any(on_plane & (keys > 0))
    actual = set(np.sign(keys[on_plane & covered]))
    assert actual == ({-1} if zero_side == 'left' else {1})
    assert not np.any(covered & (original_ml < 0) & (keys > 0))
    assert not np.any(covered & (original_ml > 0) & (keys < 0))
