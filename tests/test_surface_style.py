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


@pytest.mark.parametrize('mapping', ['allen', 'beryl'])
def test_face_visibility_uses_compact_authored_alpha_with_mutable_palette(
    mesh, mapping, monkeypatch
):
    fake = FakeDatoviz()
    palette = {315: (12, 34, 56, 255), -315: (23, 45, 67, 0)}
    with AtlasViewer(mesh, mapping=mapping, palette=palette, datoviz=fake) as viewer:
        render = viewer._surface_mesh

        def dense_reference():
            alpha = viewer._surface_presentation.style.apply(
                mapping, render.colors(mapping, palette)
            )[:, 3]
            minimum = np.full(len(render.presentations), 255, np.uint8)
            np.minimum.at(minimum, render.presentation_ids, alpha)
            return viewer._surface_presentation.style.visible_faces(mapping) & (
                minimum[render.face_presentation_ids] > 0
            )

        expected = dense_reference()
        np.testing.assert_array_equal(viewer._visible_surface_faces(mapping), expected)
        palette[315] = (12, 34, 56, 0)
        expected = dense_reference()

        def dense_colors_forbidden(*_):
            pytest.fail('visibility must not expand vertex RGBA colors')

        monkeypatch.setattr(AtlasMesh, 'colors', dense_colors_forbidden)
        np.testing.assert_array_equal(viewer._visible_surface_faces(mapping), expected)


def last_keys(fake):
    return [call[2] for call in fake.calls if call[0] == 'link_keys'][-1].view(np.int64)


def last_colors(fake):
    color_calls = [call[3] for call in fake.calls if call[:3] == ('data', 'mesh', 'color')]
    if color_calls:
        return color_calls[-1]
    return next(call[3]['color'] for call in fake.calls if call[:2] == ('data_many', 'mesh'))


def test_hide_region_filters_triangles_and_signed_pick_keys_and_restores(mesh):
    fake = FakeDatoviz()
    source_indices = mesh.indices.copy()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        render = viewer._surface_mesh
        indices = render.indices.copy()
        viewer.set_selected_region_ids((-315,))
        viewer.hide_region(-315)
        mask = render.face_mapping_ids('allen') > 0
        uploaded = [call[1] for call in fake.calls if call[0] == 'indices'][-1]
        np.testing.assert_array_equal(uploaded, indices.reshape(-1, 3)[mask].reshape(-1))
        np.testing.assert_array_equal(last_keys(fake), render.face_mapping_ids('allen')[mask])
        assert viewer.visible_region_ids() == (315,)
        assert viewer.selected_region_ids() == (-315,)
        viewer.show_region(-315)
        assert viewer.visible_region_ids() == (-315, 315)
        np.testing.assert_array_equal(last_keys(fake), render.face_mapping_ids('allen'))
    np.testing.assert_array_equal(mesh.indices, source_indices)


def test_empty_surface_hides_without_zero_count_upload_and_restores(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        render = viewer._surface_mesh
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
        np.testing.assert_array_equal(last_keys(fake), render.face_mapping_ids('allen'))


def test_palette_alpha_selects_wboit_and_survives_selection_hover_mapping(mesh):
    fake = FakeDatoviz()
    palette = {-315: (220, 30, 40, 128), 315: (30, 180, 40, 255)}
    with AtlasViewer(mesh, datoviz=fake, palette=palette) as viewer:
        render = viewer._surface_mesh
        assert viewer._surface_presentation.alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids((-315,))
        left = render.mapping_ids('allen') < 0
        np.testing.assert_array_equal(last_colors(fake)[left, 3], 128)
        viewer.clear_selection()
        assert viewer._surface_presentation.alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_mapping('cosmos', {-315: (220, 30, 40, 255), 315: (30, 180, 40, 255)})
        assert viewer._surface_presentation.alpha_mode == fake.DVZ_ALPHA_OPAQUE


def test_authored_opacity_independent_of_global_selection_opacity(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, surface_opacity=0.5) as viewer:
        render = viewer._surface_mesh
        viewer.set_region_opacity(-315, 0.25)
        left = render.mapping_ids('allen') < 0
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
        render = viewer._surface_mesh
        viewer.hide_region(-315)
        viewer.set_mapping('beryl')
        assert viewer.visible_region_ids() == (-8, 8)
        viewer.set_region_color(8, (10, 20, 30, 200), hemisphere='both')
        np.testing.assert_array_equal(
            last_colors(fake)[:, :3], [[10, 20, 30]] * len(render.positions)
        )
        assert viewer._surface_presentation.alpha_mode == fake.DVZ_ALPHA_WBOIT
        viewer.set_hemisphere('right')
        viewer.set_mapping('allen')
        assert viewer.visible_region_ids() == (315,)
        viewer.set_hemisphere('both')
        assert viewer.visible_region_ids() == (315,)  # authored Allen hide retained


def test_zero_palette_alpha_is_not_resurrected_by_selection(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, palette={-315: (100, 120, 140, 0)}) as viewer:
        render = viewer._surface_mesh
        assert np.all(last_keys(fake) > 0)
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids((-315,))
        np.testing.assert_array_equal(last_colors(fake)[render.mapping_ids('allen') < 0, 3], 0)
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
        style = viewer._surface_presentation.style
        with pytest.raises(ValueError):
            getattr(viewer, method)(*args)
        assert viewer._surface_presentation.style is style
        assert len(fake.calls) == calls


def test_hemisphere_membership_uses_canonical_side_when_mapping_has_void(mesh):
    state = SurfaceStyle(mesh)
    state.set_hemisphere_visible('left', False)
    expected = (state.face_sides == 'right') & (mesh.face_mapping_ids('beryl') != 0)
    np.testing.assert_array_equal(state.visible_faces('beryl'), expected)


@pytest.mark.parametrize('unmapped_sides', [('left',), ('left', 'right')])
def test_unmapped_presentations_stay_hidden_through_mapping_and_interaction(mesh, unmapped_sides):
    mesh = replace(
        mesh,
        presentations=tuple(
            {
                **p,
                'mappings': {
                    **p['mappings'],
                    'beryl': None if p['side'] in unmapped_sides else 8,
                },
            }
            for p in mesh.presentations
        ),
    )
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, mapping='beryl') as viewer:
        render = viewer._surface_mesh
        mapped = render.face_mapping_ids('beryl') != 0
        np.testing.assert_array_equal(viewer._surface_presentation.face_mask, mapped)
        if mapped.any():
            np.testing.assert_array_equal(
                last_keys(fake), render.face_mapping_ids('beryl')[mapped]
            )
            uploaded = [call[1] for call in fake.calls if call[0] == 'indices'][-1]
            np.testing.assert_array_equal(
                uploaded, render.indices.reshape(-1, 3)[mapped].reshape(-1)
            )
        else:
            assert ('visible', 'mesh', False) in fake.calls
        viewer.set_selected_region_ids((8,))
        viewer._set_hovered_region_ids((8,))
        viewer.set_explode(1)
        viewer.set_hemisphere('left')
        assert not viewer._surface_presentation.face_mask.any()
        viewer.set_hemisphere('both')
        np.testing.assert_array_equal(viewer._surface_presentation.face_mask, mapped)
        viewer.set_mapping('allen')
        assert viewer._surface_presentation.face_mask.all()
        np.testing.assert_array_equal(last_keys(fake), render.face_mapping_ids('allen'))
        viewer.set_mapping('beryl')
        np.testing.assert_array_equal(viewer._surface_presentation.face_mask, mapped)


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
