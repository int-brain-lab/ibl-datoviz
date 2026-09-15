"""Renderer-neutral state and slice composition for a linked atlas navigator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from ibl_atlas_assets import AtlasRegion, AtlasVolumes


SLICE_DISPLAY_AXES = {
    'ap': ('ml', 'dv'),
    'ml': ('ap', 'dv'),
    'dv': ('ml', 'ap'),
}


def _hex_rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[offset : offset + 2], 16) for offset in (1, 3, 5))  # type: ignore[return-value]


def oriented_slice(values: NDArray, array_axes: Sequence[str], axis: str) -> NDArray:
    """Orient a raw atlas slice as image rows (y) and columns (x)."""
    if axis not in SLICE_DISPLAY_AXES:
        raise ValueError('slice axis must be ap, ml or dv')
    axes = tuple(array_axes)
    if len(axes) != 2 or set(axes) != set(SLICE_DISPLAY_AXES[axis]):
        raise ValueError(f'unexpected {axis} slice axes: {axes}')
    x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
    return np.ascontiguousarray(np.transpose(values, (axes.index(y_axis), axes.index(x_axis))))


def mapped_region(volumes: AtlasVolumes, source_index: int, mapping: str) -> AtlasRegion | None:
    """Resolve an annotation source index to its signed target-mapping row."""
    allen = volumes.region_for_source_index(int(source_index))
    mapped_id = volumes.regions.map_allen_ids((allen.atlas_id,), mapping)[0]
    if mapped_id is None:
        return None
    by_id = {row.atlas_id: row for row in volumes.regions.physical(mapping)}
    return by_id[mapped_id]


def compose_atlas_slice(
    volumes: AtlasVolumes,
    axis: str,
    index: int,
    *,
    mapping: str = 'allen',
    annotation_opacity: float = 0.58,
    selected_region_ids: Sequence[int] = (),
    selection_dim_factor: float = 0.35,
) -> NDArray[np.uint8]:
    """Blend one anatomical slice with exact atlas colors on the CPU.

    Annotation values remain source indices until each distinct value is resolved
    through the volume pack and requested atlas mapping. Void and unmapped reduced
    regions show the anatomical template without an invented ontology identity.
    """
    if not np.isfinite(annotation_opacity) or not 0 <= annotation_opacity <= 1:
        raise ValueError('annotation_opacity must be between zero and one')
    if not np.isfinite(selection_dim_factor) or not 0 <= selection_dim_factor <= 1:
        raise ValueError('selection_dim_factor must be between zero and one')

    template_slice = volumes.slice('template', axis, index)
    annotation_slice = volumes.slice('annotation', axis, index)
    template = oriented_slice(template_slice.values, template_slice.array_axes, axis)
    annotation = oriented_slice(annotation_slice.values, annotation_slice.array_axes, axis)

    low, high = np.percentile(volumes.template, (1.0, 99.0))
    if high <= low:
        high = low + 1.0
    gray = np.clip((template.astype(np.float32) - low) / (high - low), 0, 1)
    base = np.rint(gray[..., None] * 255).astype(np.uint8)
    rgb = np.repeat(base, 3, axis=2)

    selected = {abs(int(region_id)) for region_id in selected_region_ids if region_id}
    for raw_source_index in np.unique(annotation):
        source_index = int(raw_source_index)
        if source_index == 0:
            continue
        row = mapped_region(volumes, source_index, mapping)
        if row is None:
            continue
        region_rgb = np.asarray(_hex_rgb(row.color_hex), dtype=np.float32)
        if selected and abs(row.atlas_id) not in selected:
            region_rgb *= selection_dim_factor
        mask = annotation == source_index
        blended = (
            rgb[mask].astype(np.float32) * (1 - annotation_opacity)
            + region_rgb * annotation_opacity
        )
        rgb[mask] = np.rint(blended).astype(np.uint8)
    alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
    return np.ascontiguousarray(np.concatenate((rgb, alpha), axis=2))


@dataclass(frozen=True)
class AtlasCursor:
    """One integer AP/ML/DV cursor coupled to an atlas volume grid."""

    ap: int
    ml: int
    dv: int

    @classmethod
    def centre(cls, volumes: AtlasVolumes) -> AtlasCursor:
        """Return the centre voxel of a volume."""
        return cls(*(size // 2 for size in volumes.grid.shape))

    def as_index(self) -> tuple[int, int, int]:
        """Return the cursor in canonical AP/ML/DV array order."""
        return self.ap, self.ml, self.dv

    def replace(self, axis: str, value: int, shape: Sequence[int]) -> AtlasCursor:
        """Return a cursor with one validated coordinate replaced."""
        if axis not in ('ap', 'ml', 'dv'):
            raise ValueError('cursor axis must be ap, ml or dv')
        axis_index = ('ap', 'ml', 'dv').index(axis)
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError('cursor coordinate must be an integer')
        if value < 0 or value >= int(shape[axis_index]):
            raise IndexError('cursor coordinate is outside the volume')
        values = list(self.as_index())
        values[axis_index] = value
        return AtlasCursor(*values)

    def world_um(self, volumes: AtlasVolumes) -> NDArray[np.float64]:
        """Return this voxel centre in ML/AP/DV atlas world micrometres."""
        return volumes.grid.index_to_world(self.as_index())

    def source_index(self, volumes: AtlasVolumes) -> int:
        """Return the annotation source index at this cursor."""
        return int(volumes.annotation[self.as_index()])

    def region(self, volumes: AtlasVolumes, mapping: str) -> AtlasRegion | None:
        """Return the signed mapped region at this cursor, including void."""
        return mapped_region(volumes, self.source_index(volumes), mapping)
