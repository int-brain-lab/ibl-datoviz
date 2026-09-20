from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh, LinkedAtlasNavigator
from ibl_datoviz.linked_atlas import volume_render_geometry
from ibl_datoviz.navigator import (
    AtlasCursor,
    AtlasSliceComposer,
    compose_atlas_slice,
    cursor_from_slice_fraction,
    mapped_region,
    oriented_slice,
    step_slice_cursor,
)

VOLUME_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / 'ibl-anatomy'
    / 'tests'
    / 'fixtures'
    / 'volume-pack-v1'
    / 'pack'
)
MESH_FIXTURE = VOLUME_FIXTURE.parents[1] / 'mesh-pack-v1' / 'pack'


@pytest.fixture
def volumes():
    return open_volume_pack(VOLUME_FIXTURE).load_volumes()


@pytest.mark.parametrize(
    ('axis', 'expected'),
    [
        ('ap', np.arange(15).reshape(5, 3).T),
        ('ml', np.arange(12).reshape(4, 3).T),
        ('dv', np.arange(20).reshape(4, 5)),
    ],
)
def test_oriented_slice_uses_explicit_anatomical_axes(axis, expected):
    source_axes = tuple(item for item in ('ap', 'ml', 'dv') if item != axis)
    actual = oriented_slice(expected.T if axis != 'dv' else expected, source_axes, axis)
    assert np.array_equal(actual, expected)
    assert actual.flags.c_contiguous


def test_oriented_slice_applies_world_direction_flips(volumes):
    raw = volumes.slice('template', 'dv', 1)
    actual = oriented_slice(raw.values, raw.array_axes, 'dv', grid=volumes.grid)
    assert actual[0, 0] == volumes.template[-1, 0, 1]
    assert actual[-1, -1] == volumes.template[0, -1, 1]


def test_cursor_world_and_mapping(volumes):
    cursor = AtlasCursor(2, 2, 1)
    assert np.array_equal(cursor.world_um(volumes), [-39.0, -100.0, 0.0])
    assert cursor.source_index(volumes) == 1
    row = cursor.region(volumes, 'beryl')
    assert row is not None
    assert (row.atlas_id, row.acronym) == (997, 'root')
    assert mapped_region(volumes, 3, 'allen').atlas_id == -997


def test_cursor_replacement_is_bounded(volumes):
    cursor = AtlasCursor.centre(volumes)
    assert cursor.replace('ml', 0, volumes.grid.shape) == AtlasCursor(2, 0, 1)
    with pytest.raises(IndexError, match='outside'):
        cursor.replace('dv', 3, volumes.grid.shape)


def test_step_slice_cursor_changes_only_plane_and_clamps(volumes):
    cursor = AtlasCursor(2, 2, 1)
    assert step_slice_cursor(cursor, 'dv', 1, volumes.grid.shape) == AtlasCursor(2, 2, 2)
    assert step_slice_cursor(cursor, 'ap', -99, volumes.grid.shape) == AtlasCursor(0, 2, 1)
    assert step_slice_cursor(cursor, 'ml', 99, volumes.grid.shape) == AtlasCursor(2, 4, 1)


def test_slice_fraction_moves_only_displayed_axes(volumes):
    cursor = AtlasCursor(2, 2, 1)
    moved = cursor_from_slice_fraction(cursor, 'dv', 0.0, 1.0, volumes.grid)
    assert moved == AtlasCursor(0, 0, 1)


def test_slice_composer_caches_volume_and_mapping_setup(volumes, monkeypatch):
    calls = 0
    original = np.percentile

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr('ibl_datoviz.navigator.np.percentile', counted)
    composer = AtlasSliceComposer(volumes)
    composer.compose('ap', 1)
    composer.compose('ap', 2)
    composer.set_mapping('beryl')
    composer.compose('ml', 2)
    assert calls == 1


def test_volume_geometry_uses_voxel_edges_and_numpy_texture_order(volumes):
    mesh = AtlasMesh.from_pack(MESH_FIXTURE)
    bounds_min, bounds_max, axis_order, axis_flip = volume_render_geometry(mesh, volumes)
    expected = mesh.normalize_points([[-289, -250, -150], [211, 150, 150]])
    assert np.allclose(bounds_min, expected.min(axis=0))
    assert np.allclose(bounds_max, expected.max(axis=0))
    assert axis_order == (2, 0, 1)  # NumPy AP/ML/DV -> texture W/V/U -> world DV/ML/AP
    assert axis_flip == (True, False, True)


def test_navigator_rejects_incompatible_mesh_catalog(volumes):
    mesh = AtlasMesh.from_pack(MESH_FIXTURE)
    with pytest.raises(ValueError, match='IDs are absent'):
        LinkedAtlasNavigator(mesh, volumes)


def test_navigator_rejects_palette_that_would_desynchronize_slices(volumes):
    mesh = AtlasMesh.from_pack(MESH_FIXTURE)
    with pytest.raises(ValueError, match='verified catalog palette'):
        LinkedAtlasNavigator(mesh, volumes, palette={315: (1, 2, 3, 255)})


@pytest.mark.parametrize(
    ('factory_name', 'args'),
    [
        ('from_pack', (MESH_FIXTURE,)),
        ('from_assets', (object(),)),
        ('from_asset_set', (MESH_FIXTURE,)),
    ],
)
def test_navigator_rejects_inherited_surface_only_factories(factory_name, args):
    factory = getattr(LinkedAtlasNavigator, factory_name)
    with pytest.raises(TypeError, match=r'requires atlas volumes.*from_packs\(\)'):
        factory(*args)


def test_composed_slice_is_rgba_and_preserves_void_template(volumes):
    image = compose_atlas_slice(volumes, 'dv', 1, annotation_opacity=1.0)
    assert image.shape == (4, 5, 4)
    assert image.dtype == np.uint8
    assert image.flags.c_contiguous
    assert np.all(image[..., 3] == 255)
    assert tuple(image[1, 2, :3]) == (255, 255, 255)  # right root
    assert len({tuple(pixel) for pixel in image[..., :3].reshape(-1, 3)}) > 3


def test_slice_layers_keep_anatomy_and_annotation_independent(volumes):
    composer = AtlasSliceComposer(volumes)
    anatomy, annotation = composer.compose_layers('dv', 1, annotation_opacity=0.5)
    assert anatomy.shape == annotation.shape == (4, 5, 4)
    assert anatomy.dtype == annotation.dtype == np.uint8
    assert set(np.unique(anatomy[..., 3])) <= {0, 255}
    assert annotation[..., 3].max() <= 128
    # Atlas void remains transparent in both layers so the panel background shows through.
    assert annotation[0, 0, 3] == 0
    assert anatomy[0, 0, 3] == 0


def test_slice_boundaries_are_vectorized_cached_and_mapping_aware(volumes):
    composer = AtlasSliceComposer(volumes)
    allen_starts, allen_ends = composer.boundary_segments('dv', 1)
    cached_starts, cached_ends = composer.boundary_segments('dv', 1)
    assert cached_starts is allen_starts
    assert cached_ends is allen_ends
    assert allen_starts.shape == allen_ends.shape
    assert allen_starts.shape[1] == 2
    assert allen_starts.dtype == allen_ends.dtype == np.float32
    assert np.all((allen_starts >= 0) & (allen_starts <= 1))
    assert np.all((allen_ends >= 0) & (allen_ends <= 1))

    composer.set_mapping('beryl')
    beryl_starts, _ = composer.boundary_segments('dv', 1)
    assert len(beryl_starts) < len(allen_starts)


def test_selection_dims_only_other_mapped_regions(volumes):
    all_regions = compose_atlas_slice(volumes, 'dv', 1, annotation_opacity=1.0)
    selected = compose_atlas_slice(
        volumes,
        'dv',
        1,
        annotation_opacity=1.0,
        selected_region_ids=(997,),
        selection_dim_factor=0.25,
    )
    assert np.array_equal(selected[1, 2], all_regions[1, 2])
    assert np.all(selected[2, 1, :3] < all_regions[2, 1, :3])
    assert np.array_equal(selected[0, 0], all_regions[0, 0])  # void is anatomical grayscale


def test_region_mask_uses_current_mapping_without_selecting_other_regions(volumes):
    composer = AtlasSliceComposer(volumes, 'allen')
    mask = composer.region_mask('dv', 1, (997,))
    assert mask.shape == (4, 5)
    assert mask.dtype == np.bool_
    assert mask.any()
    assert not mask.all()
    assert not composer.region_mask('dv', 1, ()).any()
