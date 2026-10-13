from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasEnvelope, AtlasMesh
from tests import FIXTURES


def surface_arrays():
    positions = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
    normals = np.tile(np.array([0, 0, 1], np.float32), (4, 1))
    indices = np.array([0, 1, 2, 0, 2, 3], np.uint32)
    return positions, normals, indices


def test_envelope_shares_atlas_transform_and_owns_arrays():
    atlas = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    positions, normals, indices = surface_arrays()
    result = AtlasEnvelope.from_world_arrays(
        positions,
        normals,
        indices,
        atlas,
        reference_space=atlas.reference_space,
        variant='source-native',
    )
    np.testing.assert_array_equal(result.positions, atlas.normalize_points(positions))
    np.testing.assert_array_equal(result.positions_um, positions)
    positions[:] = 100
    normals[:] = 0
    indices[:] = 3
    assert result.positions_um[0, 0] == 0
    assert result.normals[0, 2] == 1
    assert result.indices[0] == 0
    assert all(
        a.flags.owndata
        for a in (result.positions_um, result.positions, result.normals, result.indices)
    )


def test_from_geometry_preserves_already_transformed_world_coordinates():
    atlas = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    p, n, i = surface_arrays()
    surface = SimpleNamespace(
        positions_um=p,
        normals=n,
        indices=i,
        asset=SimpleNamespace(reference_space_id=atlas.reference_space, variant='source-native'),
    )
    result = AtlasEnvelope.from_geometry(surface, atlas)
    np.testing.assert_array_equal(result.positions_um, p)


def test_rejects_wrong_reference_space_and_unknown_variant():
    atlas = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    arrays = surface_arrays()
    with pytest.raises(ValueError, match='reference spaces'):
        AtlasEnvelope.from_world_arrays(
            *arrays, atlas, reference_space='other', variant='source-native'
        )
    with pytest.raises(ValueError, match='variant'):
        AtlasEnvelope.from_world_arrays(
            *arrays, atlas, reference_space=atlas.reference_space, variant='smoothed'
        )


def test_rejects_nonunit_normals_and_invalid_indices():
    atlas = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    p, n, i = surface_arrays()
    with pytest.raises(ValueError, match='geometry'):
        AtlasEnvelope.from_world_arrays(
            p, n * 2, i, atlas, reference_space=atlas.reference_space, variant='source-native'
        )
    with pytest.raises(ValueError, match='geometry'):
        AtlasEnvelope.from_world_arrays(
            p,
            n,
            i.astype(np.int64),
            atlas,
            reference_space=atlas.reference_space,
            variant='source-native',
        )
