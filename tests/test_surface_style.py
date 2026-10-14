"""Signed surface presentation, filtered picking identity and authored alpha."""

from dataclasses import replace

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.surface_style import SurfaceStyle
from tests.test_atlas import FIXTURE, REGIONS, FakeDatoviz


@pytest.fixture
def mesh():
    return AtlasMesh.from_pack(FIXTURE)


def last_keys(fake):
    return [call[2] for call in fake.calls if call[0] == 'link_keys'][-1].view(np.int64)


def last_colors(fake):
    color_calls = [call[3] for call in fake.calls if call[:3] == ('data', 'mesh', 'color')]
    if color_calls:
        return color_calls[-1]
    return next(call[3]['color'] for call in fake.calls if call[:2] == ('data_many', 'mesh'))


def test_hide_region_filters_triangles_and_signed_pick_keys_and_restores(mesh):
    fake = FakeDatoviz()
    indices = mesh.indices.copy()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_selected_region_ids((-315,))
        viewer.hide_region(-315)
        mask = mesh.face_mapping_ids('allen') > 0
        uploaded = [call[1] for call in fake.calls if call[0] == 'indices'][-1]
        np.testing.assert_array_equal(uploaded, indices.reshape(-1, 3)[mask].reshape(-1))
        np.testing.assert_array_equal(last_keys(fake), mesh.face_mapping_ids('allen')[mask])
        assert viewer.visible_region_ids() == (315,)
        assert viewer.selected_region_ids() == (-315,)
        viewer.show_region(-315)
        assert viewer.visible_region_ids() == (-315, 315)
        np.testing.assert_array_equal(last_keys(fake), mesh.face_mapping_ids('allen'))
    np.testing.assert_array_equal(mesh.indices, indices)


def test_empty_surface_hides_without_zero_count_upload_and_restores(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_hemisphere('left')
        assert np.all(last_keys(fake) < 0)
        uploads = len([call for call in fake.calls if call[0] == 'indices'])
        viewer.set_hemisphere_visible('both', False)
        assert viewer.visible_region_ids() == ()
        assert ('visible', 'mesh', False) in fake.calls
        assert len([call for call in fake.calls if call[0] == 'indices']) == uploads
        viewer.set_hemisphere('right')
        assert viewer.visible_region_ids() == (315,)
        assert np.all(last_keys(fake) > 0)
        viewer.set_hemisphere('both')
        np.testing.assert_array_equal(last_keys(fake), mesh.face_mapping_ids('allen'))


def test_palette_alpha_selects_wboit_and_survives_selection_hover_mapping(mesh):
    fake = FakeDatoviz()
    palette = {-315: (220, 30, 40, 128), 315: (30, 180, 40, 255)}
    with AtlasViewer(mesh, datoviz=fake, palette=palette) as viewer:
        assert viewer._surface_alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids((-315,))
        left = mesh.mapping_ids('allen') < 0
        np.testing.assert_array_equal(last_colors(fake)[left, 3], 128)
        viewer.clear_selection()
        assert viewer._surface_alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_mapping('cosmos', {-315: (220, 30, 40, 255), 315: (30, 180, 40, 255)})
        assert viewer._surface_alpha_mode == fake.DVZ_ALPHA_OPAQUE


def test_authored_opacity_independent_of_global_selection_opacity(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, surface_opacity=0.5) as viewer:
        viewer.set_region_opacity(-315, 0.25)
        left = mesh.mapping_ids('allen') < 0
        np.testing.assert_array_equal(last_colors(fake)[left, 3], 32)
        viewer.set_selected_region_ids((-315,))
        np.testing.assert_array_equal(last_colors(fake)[left, 3], 32)
        viewer.set_region_opacity(-315, 0)
        assert np.all(last_keys(fake) > 0)
        assert viewer.visible_region_ids() == (315,)
        viewer.reset_region_style(-315)
        assert viewer.visible_region_ids() == (-315, 315)


def test_region_overrides_are_mapping_scoped_and_hemispheres_persist(mesh):
    # Give the fixture an independently mapped region identity in Beryl.
    presentations = tuple(
        {**p, 'mappings': {**p['mappings'], 'beryl': 8 if p['side'] == 'right' else -8}}
        for p in mesh.presentations
    )
    mesh = replace(mesh, presentations=presentations)
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.hide_region(-315)
        viewer.set_mapping('beryl')
        assert viewer.visible_region_ids() == (-8, 8)
        viewer.set_region_color(8, (10, 20, 30, 200), hemisphere='both')
        np.testing.assert_array_equal(
            last_colors(fake)[:, :3], [[10, 20, 30]] * len(mesh.positions)
        )
        assert viewer._surface_alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_hemisphere('right')
        viewer.set_mapping('allen')
        assert viewer.visible_region_ids() == (315,)
        viewer.set_hemisphere('both')
        assert viewer.visible_region_ids() == (315,)  # authored Allen hide retained


def test_zero_palette_alpha_is_not_resurrected_by_selection(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, palette={-315: (100, 120, 140, 0)}) as viewer:
        assert np.all(last_keys(fake) > 0)
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids((-315,))
        np.testing.assert_array_equal(last_colors(fake)[mesh.mapping_ids('allen') < 0, 3], 0)
        assert viewer.visible_region_ids() == (315,)


@pytest.mark.parametrize(
    'method,args',
    [
        ('set_region_visible', (0, False)),
        ('set_region_visible', (999, False)),
        ('set_region_color', (-315, [1, 2.5, 3])),
        ('set_region_opacity', (-315, np.nan)),
        ('set_region_opacity', (-315, 2)),
        ('set_hemisphere', ('midline',)),
    ],
)
def test_invalid_styles_do_not_mutate_viewer_or_gpu(mesh, method, args):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        calls = len(fake.calls)
        style = viewer._surface_style
        with pytest.raises(ValueError):
            getattr(viewer, method)(*args)
        assert viewer._surface_style is style
        assert len(fake.calls) == calls


def test_hemisphere_membership_uses_canonical_side_when_mapping_has_void(mesh):
    state = SurfaceStyle(mesh)
    state.set_hemisphere_visible('left', False)
    expected = state.face_sides == 'right'
    np.testing.assert_array_equal(state.visible_faces('beryl'), expected)


def test_linked_selection_remains_signed_when_selected_region_hidden(mesh):
    presentations = tuple(
        {**p, 'mappings': {**p['mappings'], 'allen': 8 if p['side'] == 'right' else -8}}
        for p in mesh.presentations
    )
    mesh = replace(mesh, presentations=presentations)
    with AtlasViewer(mesh, catalog=open_region_catalog(REGIONS), datoviz=FakeDatoviz()) as viewer:
        viewer.set_selected_region_ids((-8,))
        viewer.hide_region(-8)
        assert viewer.selected_region_ids() == (-8,)
        viewer.set_mapping('cosmos')
        assert viewer.selected_region_ids() == ()  # established mapping-change policy
