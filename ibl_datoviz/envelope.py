"""Reference envelopes sharing a regional atlas mesh's exact display transform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from ibl_anatomy import load_surface_asset

if TYPE_CHECKING:
    from pathlib import Path

    from ibl_anatomy import SurfaceGeometry

    from .atlas import AtlasMesh


@dataclass(frozen=True)
class AtlasEnvelope:
    """Owned display arrays, independent of regional identity and picking data."""

    positions_um: np.ndarray
    positions: np.ndarray
    normals: np.ndarray
    indices: np.ndarray
    reference_space: str
    variant: str

    @classmethod
    def from_source(cls, path: str | Path, atlas: AtlasMesh) -> AtlasEnvelope:
        """Load the shared Allen reference envelope offline; never generate a fallback."""
        return cls.from_geometry(load_surface_asset(path), atlas)

    @classmethod
    def from_geometry(cls, surface: SurfaceGeometry, atlas: AtlasMesh) -> AtlasEnvelope:
        """Adapt verified world geometry without reapplying its source affine."""
        return cls.from_world_arrays(
            surface.positions_um,
            surface.normals,
            surface.indices,
            atlas,
            reference_space=surface.asset.reference_space_id,
            variant=surface.asset.variant,
        )

    @classmethod
    def from_world_arrays(
        cls,
        positions_um: np.ndarray,
        normals: np.ndarray,
        indices: np.ndarray,
        atlas: AtlasMesh,
        *,
        reference_space: str,
        variant: str,
    ) -> AtlasEnvelope:
        """Adapt prepared arrays using the regional atlas's unchanged framing."""
        if reference_space != atlas.reference_space:
            raise ValueError('envelope and atlas reference spaces differ')
        if variant not in ('source-native', 'annotation-boundary'):
            raise ValueError('unsupported envelope variant')
        positions = np.array(positions_um, dtype=np.float32, order='C', copy=True)
        normal_array = np.array(normals, dtype=np.float32, order='C', copy=True)
        index_array = np.array(indices, order='C', copy=True)
        if (
            positions.ndim != 2
            or positions.shape[1] != 3
            or len(positions) < 4
            or normal_array.shape != positions.shape
            or not np.isfinite(positions).all()
            or not np.isfinite(normal_array).all()
            or not np.allclose(np.linalg.norm(normal_array, axis=1), 1, rtol=1e-4)
            or index_array.dtype != np.uint32
            or index_array.ndim != 1
            or not len(index_array)
            or len(index_array) % 3
            or index_array.max() >= len(positions)
        ):
            raise ValueError('invalid envelope geometry')
        return cls(
            positions,
            atlas.normalize_points(positions),
            normal_array,
            index_array,
            reference_space,
            variant,
        )
