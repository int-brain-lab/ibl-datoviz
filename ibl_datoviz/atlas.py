"""Renderer-neutral atlas mesh presentation data."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ibl_atlas_assets import open_mesh_pack

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from numpy.typing import NDArray

    from ibl_atlas_assets import MeshGeometry

MISSING_REGION_ID = 0


def _world_geometry(geometry: MeshGeometry) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    matrix = np.asarray(
        geometry.coordinate_system['source_to_world_um'], dtype=np.float64
    ).reshape(4, 4)
    homogeneous = np.column_stack(
        (geometry.positions.astype(np.float64), np.ones(len(geometry.positions)))
    )
    positions = homogeneous @ matrix.T
    if np.any(np.abs(positions[:, 3]) < np.finfo(np.float64).eps):
        raise ValueError('mesh source-to-world transform produced points at infinity')
    positions = positions[:, :3] / positions[:, 3, None]

    normal_matrix = np.linalg.inv(matrix[:3, :3]).T
    normals = geometry.normals.astype(np.float64) @ normal_matrix.T
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths == 0):
        raise ValueError('mesh contains a zero-length transformed normal')
    normals /= lengths[:, None]
    return (
        np.ascontiguousarray(positions, dtype=np.float32),
        np.ascontiguousarray(normals, dtype=np.float32),
    )


def _display_positions(positions_um: NDArray[np.float32]) -> tuple[NDArray[np.float32], float]:
    minimum = positions_um.min(axis=0)
    maximum = positions_um.max(axis=0)
    centre = (minimum + maximum) / 2
    span = float(np.max(maximum - minimum))
    if not np.isfinite(span) or span <= 0:
        raise ValueError('mesh bounds are degenerate')
    scale = 1.6 / span
    return np.ascontiguousarray((positions_um - centre) * scale, dtype=np.float32), scale


def _presentation_ids(
    geometry: MeshGeometry, positions_um: NDArray[np.float32]
) -> NDArray[np.int32]:
    sentinel = np.iinfo(np.int32).min
    ids = np.full(len(positions_um), sentinel, dtype=np.int32)
    axes = geometry.coordinate_system['world_axes']
    try:
        ml_axis = axes.index('ml')
    except ValueError as error:
        raise ValueError('mesh world axes do not declare the ML coordinate') from error

    for item in geometry.ranges:
        sl = slice(item.vertex_start, item.vertex_start + item.vertex_count)
        ids[sl] = geometry.presentation_ids_for_component(
            item.component_id, positions_um[sl, ml_axis]
        )
    if np.any(ids == sentinel):
        raise ValueError('mesh presentation identity does not cover every vertex')
    return ids


def _face_presentation_ids(
    geometry: MeshGeometry, positions_um: NDArray[np.float32]
) -> NDArray[np.int32]:
    """Resolve the primitive identity emitted by Datoviz indexed-mesh item queries."""
    sentinel = np.iinfo(np.int32).min
    ids = np.full(len(geometry.indices) // 3, sentinel, dtype=np.int32)
    ml_axis = geometry.coordinate_system['world_axes'].index('ml')
    triangles = geometry.indices.reshape(-1, 3)
    for item in geometry.ranges:
        face_start = item.index_start // 3
        face_end = (item.index_start + item.index_count) // 3
        centroids_ml = positions_um[triangles[face_start:face_end], ml_axis].mean(axis=1)
        ids[face_start:face_end] = geometry.presentation_ids_for_component(
            item.component_id, centroids_ml
        )
    if np.any(ids == sentinel):
        raise ValueError('mesh presentation identity does not cover every face')
    return ids


def _default_color(region_id: int) -> tuple[int, int, int, int]:
    if region_id == MISSING_REGION_ID:
        return (90, 98, 108, 255)
    hue = (abs(region_id) * 0.6180339887498949) % 1.0
    rgb = colorsys.hsv_to_rgb(hue, 0.52, 0.88)
    return tuple(round(channel * 255) for channel in rgb) + (255,)


@dataclass(frozen=True)
class AtlasMesh:
    """Dense mesh arrays and stable per-vertex atlas presentation identity."""

    positions_um: NDArray[np.float32]
    positions: NDArray[np.float32]
    normals: NDArray[np.float32]
    indices: NDArray[np.uint32]
    component_ids: NDArray[np.uint16]
    presentation_ids: NDArray[np.int32]
    face_presentation_ids: NDArray[np.int32]
    presentations: tuple[dict, ...]
    reference_space: str
    display_scale: float

    @classmethod
    def from_pack(cls, path: str | Path) -> AtlasMesh:
        """Verify and load an atlas mesh pack."""
        geometry = open_mesh_pack(path).load_geometry()
        positions_um, normals = _world_geometry(geometry)
        positions, display_scale = _display_positions(positions_um)
        return cls(
            positions_um=positions_um,
            positions=positions,
            normals=normals,
            indices=geometry.indices,
            component_ids=geometry.component_ids,
            presentation_ids=_presentation_ids(geometry, positions_um),
            face_presentation_ids=_face_presentation_ids(geometry, positions_um),
            presentations=geometry.presentations,
            reference_space=geometry.reference_space,
            display_scale=display_scale,
        )

    @property
    def mapping_names(self) -> tuple[str, ...]:
        """Return mapping names common to every presentation."""
        if not self.presentations:
            return ()
        names = set(self.presentations[0]['mappings'])
        for presentation in self.presentations[1:]:
            names.intersection_update(presentation['mappings'])
        return tuple(sorted(names))

    def mapping_ids(self, mapping: str) -> NDArray[np.int64]:
        """Return signed mapped region IDs per vertex, using zero for unmapped vertices."""
        if mapping not in self.mapping_names:
            raise KeyError(f'unknown atlas mapping: {mapping}')
        lookup: dict[int, int] = {}
        for presentation in self.presentations:
            mapped = presentation['mappings'][mapping]
            lookup[presentation['presentation_id']] = (
                MISSING_REGION_ID if mapped is None else int(mapped)
            )
        try:
            values = [lookup[int(item)] for item in self.presentation_ids]
        except KeyError as error:
            raise ValueError(f'unknown presentation ID in mesh: {error.args[0]}') from error
        return np.ascontiguousarray(values, dtype=np.int64)

    def face_mapping_ids(self, mapping: str) -> NDArray[np.int64]:
        """Return signed region IDs for Datoviz indexed-mesh primitive item queries."""
        if mapping not in self.mapping_names:
            raise KeyError(f'unknown atlas mapping: {mapping}')
        lookup = {
            item['presentation_id']: (
                MISSING_REGION_ID
                if item['mappings'][mapping] is None
                else int(item['mappings'][mapping])
            )
            for item in self.presentations
        }
        try:
            values = [lookup[int(item)] for item in self.face_presentation_ids]
        except KeyError as error:
            raise ValueError(f'unknown presentation ID in mesh: {error.args[0]}') from error
        return np.ascontiguousarray(values, dtype=np.int64)

    def colors(
        self,
        mapping: str,
        palette: Mapping[int, Sequence[int]] | None = None,
    ) -> NDArray[np.uint8]:
        """Return atlas colors per vertex without changing geometry or identity arrays."""
        ids = self.mapping_ids(mapping)
        colors = np.empty((len(ids), 4), dtype=np.uint8)
        palette = palette or {}
        for region_id in np.unique(ids):
            key = int(region_id)
            raw = palette.get(key, palette.get(abs(key), _default_color(key)))
            color = tuple(int(channel) for channel in raw)
            if len(color) == 3:
                color += (255,)
            if len(color) != 4 or any(channel < 0 or channel > 255 for channel in color):
                raise ValueError(f'invalid RGBA color for region {key}')
            colors[ids == region_id] = color
        return np.ascontiguousarray(colors)

    def link_keys(self, mapping: str) -> NDArray[np.uint64]:
        """Encode signed mapping IDs losslessly as Datoviz uint64 link keys."""
        return self.face_mapping_ids(mapping).view(np.uint64)

    def normalize_points(self, points_um: Sequence[Sequence[float]]) -> NDArray[np.float32]:
        """Transform world-space micrometre points into this mesh's display space."""
        points = np.asarray(points_um, dtype=np.float32)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('points must have shape (n, 3)')
        centre = (self.positions_um.min(axis=0) + self.positions_um.max(axis=0)) / 2
        return np.ascontiguousarray((points - centre) * self.display_scale, dtype=np.float32)
