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


def _display_positions(positions_um: NDArray[np.float32]) -> tuple[NDArray[np.float32], float]:
    minimum = positions_um.min(axis=0)
    maximum = positions_um.max(axis=0)
    centre = (minimum + maximum) / 2
    span = float(np.max(maximum - minimum))
    if not np.isfinite(span) or span <= 0:
        raise ValueError('mesh bounds are degenerate')
    scale = 1.6 / span
    return np.ascontiguousarray((positions_um - centre) * scale, dtype=np.float32), scale


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
        return cls.from_geometry(open_mesh_pack(path).load_geometry())

    @classmethod
    def from_geometry(cls, geometry: MeshGeometry) -> AtlasMesh:
        """Prepare renderer arrays from already verified mesh geometry."""
        positions_um = geometry.world_positions()
        normals = geometry.world_normals()
        positions, display_scale = _display_positions(positions_um)
        return cls(
            positions_um=positions_um,
            positions=positions,
            normals=normals,
            indices=geometry.indices,
            component_ids=geometry.component_ids,
            presentation_ids=geometry.vertex_presentation_ids(positions_um),
            face_presentation_ids=geometry.face_presentation_ids(positions_um),
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
        lookup = np.zeros(len(self.presentations), dtype=np.int64)
        for presentation in self.presentations:
            mapped = presentation['mappings'][mapping]
            lookup[presentation['presentation_id']] = (
                MISSING_REGION_ID if mapped is None else int(mapped)
            )
        return np.ascontiguousarray(lookup[self.presentation_ids])

    def face_mapping_ids(self, mapping: str) -> NDArray[np.int64]:
        """Return signed region IDs for Datoviz indexed-mesh primitive item queries."""
        if mapping not in self.mapping_names:
            raise KeyError(f'unknown atlas mapping: {mapping}')
        lookup = np.zeros(len(self.presentations), dtype=np.int64)
        for item in self.presentations:
            lookup[item['presentation_id']] = (
                MISSING_REGION_ID
                if item['mappings'][mapping] is None
                else int(item['mappings'][mapping])
            )
        return np.ascontiguousarray(lookup[self.face_presentation_ids])

    def colors(
        self,
        mapping: str,
        palette: Mapping[int, Sequence[int]] | None = None,
    ) -> NDArray[np.uint8]:
        """Return atlas colors per vertex without changing geometry or identity arrays."""
        if mapping not in self.mapping_names:
            raise KeyError(f'unknown atlas mapping: {mapping}')
        palette = palette or {}
        lookup = np.empty((len(self.presentations), 4), dtype=np.uint8)
        for presentation in self.presentations:
            mapped = presentation['mappings'][mapping]
            key = MISSING_REGION_ID if mapped is None else int(mapped)
            raw = palette.get(key, palette.get(abs(key), _default_color(key)))
            color = tuple(int(channel) for channel in raw)
            if len(color) == 3:
                color += (255,)
            if len(color) != 4 or any(channel < 0 or channel > 255 for channel in color):
                raise ValueError(f'invalid RGBA color for region {key}')
            lookup[presentation['presentation_id']] = color
        return np.ascontiguousarray(lookup[self.presentation_ids])

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
