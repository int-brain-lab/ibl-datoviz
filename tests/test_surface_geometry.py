"""Source-preserving render copies and complementary hemisphere coverage."""

from dataclasses import replace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, surface_geometry
from ibl_datoviz.atlas import _MeshPresentationBoundary
from ibl_datoviz.surface_geometry import SurfaceGeometry
from tests.test_atlas import FIXTURE


def triangle(ml, *, axis=0, left=0, right=1, threshold=0, on_plane='right'):
    positions = np.zeros((3, 3), np.float32)
    positions[:, axis] = ml
    others = [value for value in range(3) if value != axis]
    positions[1, others[0]] = 2
    positions[2, others[1]] = 3
    presentations = (
        {
            'presentation_id': 0,
            'side': 'left',
            'mappings': {'allen': -315, 'beryl': None, 'cosmos': -8},
        },
        {
            'presentation_id': 1,
            'side': 'right',
            'mappings': {'allen': 315, 'beryl': None, 'cosmos': 8},
        },
    )
    return AtlasMesh(
        positions_um=positions,
        positions=positions * 0.01 + np.array([1, 2, 3], np.float32),
        normals=np.array([[0.5, 0, 1], [0, 0.5, 1], [0.2, 0.2, 1]], np.float32),
        explode_offsets=np.tile(np.array([0.5, -0.25, 0.125], np.float32), (3, 1)),
        indices=np.array([0, 1, 2], np.uint32),
        component_ids=np.zeros(3, np.uint16),
        presentation_ids=np.where(positions[:, axis] < 0, 0, 1).astype(np.int32),
        face_presentation_ids=np.array([int(np.mean(ml) >= 0)], np.int32),
        presentations=presentations,
        reference_space='synthetic-test-only',
        display_scale=0.01,
        _presentation_boundary=_MeshPresentationBoundary(
            'original-world-ml', axis, threshold, on_plane, ((0, left, right),)
        ),
    )


def covered_presentations(surface, barycentric, source_face=0):
    clip = surface.fragment_clip[surface.mesh.indices.reshape(-1, 3)]
    result = []
    for face in np.flatnonzero(surface.source_face_indices == source_face):
        distance = np.dot(clip[face, :, 0], barycentric)
        include_zero = clip[face, 0, 1]
        if distance > 0 or (distance == 0 and include_zero):
            result.append(int(surface.mesh.face_presentation_ids[face]))
    return result


def test_crossing_faces_keep_exact_source_coverage_normals_displacement_and_keys():
    source = triangle([-1, 1, 1])
    snapshots = {
        name: np.array(getattr(source, name), copy=True)
        for name in (
            'positions_um',
            'positions',
            'normals',
            'explode_offsets',
            'indices',
            'component_ids',
            'presentation_ids',
            'face_presentation_ids',
        )
    }
    surface = SurfaceGeometry.from_mesh(source)
    render = surface.mesh
    assert surface.requires_fragment_clip
    np.testing.assert_array_equal(surface.source_face_indices, [0, 0])
    np.testing.assert_array_equal(render.face_mapping_ids('allen'), [-315, 315])
    np.testing.assert_array_equal(render.face_mapping_ids('cosmos'), [-8, 8])
    np.testing.assert_array_equal(render.face_mapping_ids('beryl'), [0, 0])
    np.testing.assert_array_equal(render.link_keys('allen').view(np.int64), [-315, 315])
    np.testing.assert_array_equal(
        surface.source_vertex_indices[render.indices.reshape(-1, 3)], [[0, 1, 2], [0, 1, 2]]
    )
    for name in ('positions_um', 'positions', 'normals', 'explode_offsets', 'component_ids'):
        np.testing.assert_array_equal(
            getattr(render, name), getattr(source, name)[surface.source_vertex_indices]
        )
    for amount in (0, 0.3, 1):
        np.testing.assert_array_equal(
            render.exploded_positions(amount),
            source.exploded_positions(amount)[surface.source_vertex_indices],
        )
    for name, snapshot in snapshots.items():
        np.testing.assert_array_equal(getattr(source, name), snapshot)
        array = getattr(render, name)
        assert not np.shares_memory(array, getattr(source, name))
        if name in ('positions_um', 'positions'):
            # Coordinate snapshots own immutable bytes rather than writable
            # ndarray storage, and keep that owner alive through their base.
            with pytest.raises(ValueError):
                array.setflags(write=True)
        else:
            assert array.flags.owndata
        assert not np.shares_memory(getattr(render, name), getattr(source, name))
    for array in (
        surface.source_face_indices,
        surface.source_vertex_indices,
        surface.fragment_clip,
    ):
        assert array.flags.owndata and array.flags.c_contiguous
    vertex_ids = render.presentation_ids[render.indices.reshape(-1, 3)]
    np.testing.assert_array_equal(vertex_ids, [[0, 0, 0], [1, 1, 1]])


@pytest.mark.parametrize('axis', [0, 1, 2])
def test_classification_uses_original_world_axis_and_exact_zero_not_display_or_explode(axis):
    surface = SurfaceGeometry.from_mesh(triangle([-1, 1, 1], axis=axis))
    # Every display-space coordinate is positive; those coordinates cannot
    # determine the original anatomical side, either before or after explosion.
    assert np.all(surface.mesh.positions > 0)
    assert covered_presentations(surface, [1, 0, 0]) == [0]
    assert covered_presentations(surface, [0.5, 0.5, 0]) == [1]
    assert covered_presentations(surface, [0.5, 0, 0.5]) == [1]
    assert covered_presentations(surface, [0, 0.5, 0.5]) == [1]


@pytest.mark.parametrize(
    'ml,expected,copies',
    [
        ([-1, -2, -3], 0, 1),
        ([1, 2, 3], 1, 1),
        ([0.0, -0.0, 0.0], 1, 1),
        ([-1, 0, 0], 1, 2),
        ([0, 1, 1], 1, 1),
    ],
)
def test_zero_edges_and_coplanar_faces_have_right_coverage(ml, expected, copies):
    surface = SurfaceGeometry.from_mesh(triangle(ml))
    assert len(surface.source_face_indices) == copies
    assert covered_presentations(surface, [0, 0.5, 0.5]) == [expected]


def test_audit_tolerance_does_not_change_small_coordinate_signs():
    surface = SurfaceGeometry.from_mesh(triangle([-1 / 1024, 1 / 1024, 1 / 1024]))
    assert covered_presentations(surface, [1, 0, 0]) == [0]
    assert covered_presentations(surface, [0, 1, 0]) == [1]
    assert covered_presentations(surface, [0.5, 0.5, 0]) == [1]


@pytest.mark.parametrize('on_plane,expected', [('left', 0), ('right', 1)])
def test_threshold_band_and_zero_policy_come_from_the_pack(on_plane, expected):
    surface = SurfaceGeometry.from_mesh(triangle([-1, 0, 1], threshold=0.25, on_plane=on_plane))
    assert covered_presentations(surface, [0, 1, 0]) == [expected]
    if on_plane == 'right':
        assert covered_presentations(surface, [0.25, 0.75, 0]) == [1]
        assert covered_presentations(surface, [0.5, 0.5, 0]) == [0]
    else:
        assert covered_presentations(surface, [0, 0.75, 0.25]) == [0]
        assert covered_presentations(surface, [0, 0.5, 0.5]) == [1]


@pytest.mark.parametrize('left,right,expected', [(0, None, 0), (None, 1, 1)])
def test_single_presentation_components_do_not_clip_at_the_original_plane(left, right, expected):
    surface = SurfaceGeometry.from_mesh(triangle([-1, 0, 1], left=left, right=right))
    assert not surface.requires_fragment_clip
    assert len(surface.source_face_indices) == 1
    for barycentric in ([1, 0, 0], [0, 1, 0], [0, 0, 1]):
        assert covered_presentations(surface, barycentric) == [expected]


def test_verified_pack_metadata_is_frozen_and_canonical_accessors_stay_unchanged():
    source = AtlasMesh.from_pack(FIXTURE)
    original_indices = source.indices.copy()
    original_keys = source.link_keys('allen').copy()
    boundary = source._presentation_boundary
    assert boundary.coordinate == 'original-world-ml'
    assert boundary.ml_axis == 0 and boundary.threshold_um == 0
    surface = SurfaceGeometry.from_mesh(source)
    assert surface.requires_fragment_clip
    assert len(surface.source_face_indices) > len(source.indices) // 3
    np.testing.assert_array_equal(source.indices, original_indices)
    np.testing.assert_array_equal(source.link_keys('allen'), original_keys)
    for face in range(len(original_indices) // 3):
        assert covered_presentations(surface, [1 / 3] * 3, face) == [
            source.face_presentation_ids[face]
        ]


def test_manual_constructor_without_boundary_metadata_preserves_authored_arrays():
    source = replace(triangle([-1, 0, 1]), _presentation_boundary=None)
    surface = SurfaceGeometry.from_mesh(source)
    assert not surface.requires_fragment_clip
    np.testing.assert_array_equal(surface.mesh.indices, source.indices)
    np.testing.assert_array_equal(surface.mesh.presentation_ids, source.presentation_ids)
    np.testing.assert_array_equal(surface.mesh.face_presentation_ids, source.face_presentation_ids)


@pytest.mark.parametrize(
    'field,value,error',
    [
        ('normals', np.zeros((2, 3)), 'normals'),
        ('explode_offsets', np.zeros((2, 3)), 'explode_offsets'),
        ('component_ids', np.zeros(2, np.uint16), 'component_ids'),
        ('presentation_ids', np.zeros(2, np.int32), 'presentation_ids'),
        ('face_presentation_ids', np.zeros(2, np.int32), 'face_presentation_ids'),
        ('indices', np.array([0, 1], np.uint32), 'complete source triangles'),
        ('indices', np.array([0, 1, 3], np.uint32), 'within the vertex array'),
    ],
)
def test_malformed_source_counts_are_rejected_before_derivation(field, value, error):
    with pytest.raises(ValueError, match=error):
        SurfaceGeometry.from_mesh(replace(triangle([-1, 0, 1]), **{field: value}))


@pytest.mark.parametrize(
    'changes,error',
    [
        ({'coordinate': 'display-ml'}, 'unsupported'),
        ({'ml_axis': 3}, 'world ML axis'),
        ({'threshold_um': -0.001}, 'nonnegative'),
        ({'on_plane_side': 'midline'}, 'zero side'),
        ({'components': ((0, None, None),)}, 'no presentation'),
        ({'components': ((0, 1, 0),)}, 'side presentation'),
        ({'components': ((1, 0, 1),)}, 'every source component'),
    ],
)
def test_malformed_boundary_metadata_is_rejected(changes, error):
    source = triangle([-1, 0, 1])
    source = replace(
        source, _presentation_boundary=replace(source._presentation_boundary, **changes)
    )
    with pytest.raises(ValueError, match=error):
        SurfaceGeometry.from_mesh(source)


@pytest.mark.parametrize('capacity,error', [(1, 'face count'), (4, 'vertex count')])
def test_derived_counts_are_checked_before_uint32_conversion(monkeypatch, capacity, error):
    monkeypatch.setattr(surface_geometry, '_MAX_RENDER_COUNT', capacity)
    with pytest.raises(ValueError, match=error):
        SurfaceGeometry.from_mesh(triangle([-1, 0, 1]))


def test_finite_source_coordinates_cannot_produce_infinite_clip_distances():
    source = triangle([-3e38, 3e38, 3e38], threshold=1e38)
    assert np.isfinite(source.positions_um).all()
    with pytest.raises(ValueError, match='clip distance must remain finite'):
        SurfaceGeometry.from_mesh(source)
