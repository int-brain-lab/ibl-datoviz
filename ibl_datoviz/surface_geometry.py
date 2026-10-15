"""Private draw geometry for exact source-bound hemisphere presentation.

Crossing source triangles are drawn twice with complementary fragment predicates.
Their source vertices, normals and displacement vectors are copied exactly; no
vertex is moved, cut or capped. The two copies therefore have identical raster
coverage even when the zero plane coincides with a pixel sample.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from .atlas import AtlasMesh

_MAX_RENDER_COUNT = np.iinfo(np.uint32).max


def _owned(array, dtype=None):
    return np.array(array, dtype=dtype, order='C', copy=True)


def _validate_mesh(mesh):
    count = len(mesh.positions_um)
    for name in ('positions_um', 'positions', 'normals', 'explode_offsets'):
        array = np.asarray(getattr(mesh, name))
        if array.shape != (count, 3) or not np.isfinite(array).all():
            raise ValueError(f'{name} must contain {count} finite three-dimensional vertices')
    for name in ('component_ids', 'presentation_ids'):
        array = np.asarray(getattr(mesh, name))
        if array.shape != (count,) or not np.issubdtype(array.dtype, np.integer):
            raise ValueError(f'{name} must contain one integer per source vertex')
        if np.any(array < 0):
            raise ValueError(f'{name} must contain nonnegative identities')
    if np.any(np.asarray(mesh.component_ids) > np.iinfo(np.uint16).max):
        raise ValueError('component_ids exceed the source component identity range')
    indices = np.asarray(mesh.indices)
    if (
        indices.ndim != 1
        or len(indices) % 3
        or not np.issubdtype(indices.dtype, np.integer)
        or np.any(indices < 0)
        or np.any(indices >= count)
    ):
        raise ValueError('indices must contain complete source triangles within the vertex array')
    if count > np.iinfo(np.uint32).max:
        raise ValueError('source vertex count exceeds the mesh index range')
    faces = len(indices) // 3
    face_ids = np.asarray(mesh.face_presentation_ids)
    if face_ids.shape != (faces,) or not np.issubdtype(face_ids.dtype, np.integer):
        raise ValueError('face_presentation_ids must contain one integer per source triangle')
    for name in ('presentation_ids', 'face_presentation_ids'):
        values = np.asarray(getattr(mesh, name))
        if np.any(values < 0) or np.any(values >= len(mesh.presentations)):
            raise ValueError(f'{name} refers to an absent presentation')
    return indices.reshape(-1, 3)


def _boundary_components(source, boundary):
    """Validate the retained policy and resolve bounded component lookup arrays."""
    if boundary.coordinate != 'original-world-ml':
        raise ValueError('unsupported mesh presentation boundary coordinate')
    if boundary.ml_axis not in (0, 1, 2):
        raise ValueError('mesh presentation boundary requires a valid original world ML axis')
    if not np.isfinite(boundary.threshold_um) or boundary.threshold_um < 0:
        raise ValueError('mesh presentation threshold must be finite and nonnegative')
    if boundary.on_plane_side not in ('left', 'right'):
        raise ValueError('mesh presentation boundary requires a left or right zero side')
    # Web assigns the entire threshold band to the chosen on-plane side.
    # D070's threshold is exactly zero; the policy still comes from its pack.
    left_includes_zero = boundary.on_plane_side == 'left'
    with np.errstate(over='ignore'):
        cut = np.float32(boundary.threshold_um * (1 if left_includes_zero else -1))
    if not np.isfinite(cut):
        raise ValueError('mesh presentation threshold exceeds the float32 coordinate range')
    component_count = int(np.asarray(source.component_ids).max(initial=0)) + 1
    left = np.full(component_count, -1, dtype=np.int32)
    right = np.full(component_count, -1, dtype=np.int32)
    seen = set()
    for component_id, left_id, right_id in boundary.components:
        if component_id < 0 or component_id > np.iinfo(np.uint16).max:
            raise ValueError('mesh presentation boundary has an invalid component identity')
        if component_id in seen:
            raise ValueError('mesh presentation boundary repeats a component identity')
        seen.add(component_id)
        if left_id is None and right_id is None:
            raise ValueError('mesh component has no presentation')
        for presentation_id, side in ((left_id, 'left'), (right_id, 'right')):
            if presentation_id is not None and (
                not 0 <= presentation_id < len(source.presentations)
                or source.presentations[presentation_id]['side'] != side
            ):
                raise ValueError('mesh component refers to an invalid side presentation')
        if component_id < component_count:
            left[component_id] = -1 if left_id is None else left_id
            right[component_id] = -1 if right_id is None else right_id
    return cut, left_includes_zero, left, right


@dataclass(frozen=True)
class SurfaceGeometry:
    """Owned private render arrays and their immutable source provenance.

    ``mesh`` uses render vertex/face ordinals. Public canonical ``AtlasMesh``
    arrays and identities remain unchanged. ``fragment_clip`` is the engine's
    copied float32 (signed distance, include-zero) input, one row per render
    vertex. Geometry, signed face keys and GPU state slots all use ``mesh``.
    """

    mesh: AtlasMesh
    source_vertex_indices: NDArray[np.uint32]
    source_face_indices: NDArray[np.uint32]
    fragment_clip: NDArray[np.float32]
    requires_fragment_clip: bool

    @classmethod
    def from_mesh(cls, source: AtlasMesh) -> SurfaceGeometry:
        """Prepare draw copies from source coordinates before display or explosion."""
        triangles = _validate_mesh(source)
        boundary = source._presentation_boundary
        if boundary is None:
            # Hand-constructed meshes predate source-boundary metadata. Preserve
            # their authored presentation semantics without inventing a plane.
            return cls(
                mesh=replace(
                    source,
                    **{
                        name: _owned(getattr(source, name))
                        for name in (
                            'positions_um',
                            'positions',
                            'explode_offsets',
                            'normals',
                            'indices',
                            'component_ids',
                            'presentation_ids',
                            'face_presentation_ids',
                        )
                    },
                ),
                source_vertex_indices=np.arange(len(source.positions), dtype=np.uint32),
                source_face_indices=np.arange(len(triangles), dtype=np.uint32),
                fragment_clip=np.ones((len(source.positions), 2), dtype=np.float32),
                requires_fragment_clip=False,
            )
        cut, left_includes_zero, left, right = _boundary_components(source, boundary)
        component_ids = np.asarray(source.component_ids)
        face_components = component_ids[triangles]
        if np.any(face_components != face_components[:, :1]):
            raise ValueError('source triangle vertices must belong to the same mesh component')
        face_left = left[face_components[:, 0]]
        face_right = right[face_components[:, 0]]
        if np.any((face_left < 0) & (face_right < 0)):
            raise ValueError('mesh presentation boundary does not cover every source component')
        ml = np.asarray(source.positions_um)[:, boundary.ml_axis]
        face_ml = ml[triangles]
        minimum, maximum = face_ml.min(axis=1), face_ml.max(axis=1)
        bilateral = (face_left >= 0) & (face_right >= 0)
        has_left = bilateral & ((minimum < cut) | (left_includes_zero & (minimum == cut)))
        has_right = bilateral & ((maximum > cut) | ((not left_includes_zero) & (maximum == cut)))
        crossing = has_left & has_right
        if len(triangles) + np.count_nonzero(crossing) > _MAX_RENDER_COUNT:
            raise ValueError('derived face count exceeds the mesh identity range')
        primary_left = (face_right < 0) | has_left
        primary_ids = np.where(primary_left, face_left, face_right)
        # Noncrossing triangles retain one source-face entry; additional copies
        # follow in source order. No canonical FACE ordinal is repurposed.
        source_faces = np.concatenate((np.arange(len(triangles)), np.flatnonzero(crossing)))
        face_presentations = np.concatenate((primary_ids, face_right[crossing]))
        face_polarity = np.concatenate(
            (
                np.where(bilateral, np.where(primary_left, -1, 1), 0),
                np.ones(np.count_nonzero(crossing), dtype=np.int8),
            )
        )
        face_zero = np.where(
            face_polarity == 0,
            True,
            np.where(face_polarity < 0, left_includes_zero, not left_includes_zero),
        )
        emitted_vertices = triangles[source_faces].reshape(-1)
        # Reuse source vertices within a presentation while keeping seam copies
        # independent. uint64 packing avoids sorting a large structured array.
        packed = (emitted_vertices.astype(np.uint64) << np.uint64(32)) | np.repeat(
            face_presentations.astype(np.uint64), 3
        )
        unique, first, inverse = np.unique(packed, return_index=True, return_inverse=True)
        if len(unique) > _MAX_RENDER_COUNT:
            raise ValueError('derived vertex count exceeds the mesh index range')
        source_vertices = _owned(unique >> np.uint64(32), np.uint32)
        vertex_presentations = _owned(unique & np.uint64(0xFFFFFFFF), np.int32)
        polarity = np.repeat(face_polarity, 3)[first]
        clip = np.empty((len(source_vertices), 2), dtype=np.float32)
        with np.errstate(over='ignore', invalid='ignore'):
            clip[:, 0] = np.where(polarity == 0, 1, polarity * (ml[source_vertices] - cut))
        clip[:, 1] = np.repeat(face_zero, 3)[first]
        if not np.isfinite(clip).all():
            raise ValueError('derived fragment clip distance must remain finite')
        render = replace(
            source,
            positions_um=_owned(source.positions_um[source_vertices]),
            positions=_owned(source.positions[source_vertices]),
            explode_offsets=_owned(source.explode_offsets[source_vertices]),
            normals=_owned(source.normals[source_vertices]),
            indices=_owned(inverse, np.uint32),
            component_ids=_owned(source.component_ids[source_vertices]),
            presentation_ids=vertex_presentations,
            face_presentation_ids=_owned(face_presentations, np.int32),
            _presentation_boundary=None,
        )
        return cls(
            mesh=render,
            source_vertex_indices=source_vertices,
            source_face_indices=_owned(source_faces, np.uint32),
            fragment_clip=clip,
            requires_fragment_clip=bool(np.any(crossing)),
        )
