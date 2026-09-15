"""Renderer-neutral state and slice composition for a linked atlas navigator."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray

    from ibl_anatomy import AtlasRegion, AtlasVolumes


SLICE_DISPLAY_AXES = {
    'ap': ('ml', 'dv'),
    'ml': ('ap', 'dv'),
    'dv': ('ml', 'ap'),
}


def _hex_rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[offset : offset + 2], 16) for offset in (1, 3, 5))  # type: ignore[return-value]


def oriented_slice(
    values: NDArray,
    array_axes: Sequence[str],
    axis: str,
    *,
    grid=None,
) -> NDArray:
    """Orient a raw atlas slice as image rows (y) and columns (x).

    With a grid, increasing ML/AP/DV world coordinates are shown right/up. This
    compensates for both the atlas affine sign and Datoviz's row-zero-at-v-zero
    image convention.
    """
    if axis not in SLICE_DISPLAY_AXES:
        raise ValueError('slice axis must be ap, ml or dv')
    axes = tuple(array_axes)
    if len(axes) != 2 or set(axes) != set(SLICE_DISPLAY_AXES[axis]):
        raise ValueError(f'unexpected {axis} slice axes: {axes}')
    x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
    result = np.transpose(values, (axes.index(y_axis), axes.index(x_axis)))
    if grid is not None:
        matrix = np.asarray(grid.index_to_world_um_matrix, dtype=np.float64).reshape(4, 4)
        for screen_axis, anatomical_axis in ((1, x_axis), (0, y_axis)):
            array_index = grid.array_axes.index(anatomical_axis)
            world_index = grid.world_axes.index(anatomical_axis)
            derivative = matrix[world_index, array_index]
            if derivative == 0:
                raise ValueError('slice orientation requires an axis-aligned atlas grid')
            if derivative < 0:
                result = np.flip(result, axis=screen_axis)
    return np.ascontiguousarray(result)


def mapped_region(volumes: AtlasVolumes, source_index: int, mapping: str) -> AtlasRegion | None:
    """Resolve an annotation source index to its signed target-mapping row."""
    allen = volumes.region_for_source_index(int(source_index))
    mapped_id = volumes.regions.map_allen_ids((allen.atlas_id,), mapping)[0]
    if mapped_id is None:
        return None
    by_id = {row.atlas_id: row for row in volumes.regions.physical(mapping)}
    return by_id[mapped_id]


def _true_runs(values: NDArray[np.bool_]) -> tuple[tuple[int, int], ...]:
    """Return half-open runs of true values in one Boolean row."""
    padded = np.pad(values.astype(np.int8, copy=False), (1, 1))
    transitions = np.diff(padded)
    starts = np.flatnonzero(transitions == 1)
    stops = np.flatnonzero(transitions == -1)
    return tuple(zip(starts.tolist(), stops.tolist(), strict=True))


class AtlasSliceComposer:
    """Cache volume-wide contrast and mapping lookup state for fast slice updates."""

    def __init__(self, volumes: AtlasVolumes, mapping: str = 'allen') -> None:
        self.volumes = volumes
        display_range = getattr(volumes, 'recommended_display_range', None)
        if display_range is None:
            template = getattr(volumes, 'template', None)
            if template is None:
                display_range = getattr(volumes, 'value_range', (0, np.iinfo(np.uint16).max))
            else:
                display_range = np.percentile(template, (1, 99))
        self.low, self.high = (float(value) for value in display_range)
        if self.high <= self.low:
            self.high = self.low + 1.0
        self.mapping = ''
        self._colors = np.empty((0, 3), dtype=np.uint8)
        self._mapped_ids = np.empty(0, dtype=np.int64)
        self._valid = np.empty(0, dtype=bool)
        self._boundary_cache: OrderedDict[tuple[str, str, int], tuple[NDArray, NDArray]] = (
            OrderedDict()
        )
        self._boundary_cache_size = 16
        self.set_mapping(mapping)

    def set_mapping(self, mapping: str) -> None:
        """Rebuild the dense source-index lookup for one target mapping."""
        physical = self.volumes.regions.physical('allen')
        size = max(row.index for row in physical) + 1
        colors = np.zeros((size, 3), dtype=np.uint8)
        mapped_ids = np.zeros(size, dtype=np.int64)
        valid = np.zeros(size, dtype=bool)
        target_by_id = {row.atlas_id: row for row in self.volumes.regions.physical(mapping)}
        mapped = self.volumes.regions.map_allen_ids((row.atlas_id for row in physical), mapping)
        for row, mapped_id in zip(physical, mapped, strict=True):
            if mapped_id is None or row.index == 0:
                continue
            target = target_by_id[mapped_id]
            colors[row.index] = _hex_rgb(target.color_hex)
            mapped_ids[row.index] = target.atlas_id
            valid[row.index] = True
        self.mapping = mapping
        self._colors = colors
        self._mapped_ids = mapped_ids
        self._valid = valid
        self._boundary_cache.clear()

    def boundary_segments(  # noqa: PLR0912
        self, axis: str, index: int
    ) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        """Return merged mapping-aware boundaries in normalized slice coordinates.

        Boundaries follow target-mapping identities rather than raw Allen source
        labels, so borders disappear when Allen regions collapse into one Beryl
        or Cosmos region. Adjacent boundary cells are merged into longer vector
        segments for efficient retained rendering.
        """
        key = (self.mapping, axis, int(index))
        cached = self._boundary_cache.pop(key, None)
        if cached is not None:
            self._boundary_cache[key] = cached
            return cached
        annotation_slice = self.volumes.slice('annotation', axis, index)
        annotation = oriented_slice(
            annotation_slice.values, annotation_slice.array_axes, axis, grid=self.volumes.grid
        )
        if int(annotation.max(initial=0)) >= len(self._valid):
            raise ValueError('annotation contains an unknown source index')
        labels = self._mapped_ids[annotation]
        valid = self._valid[annotation]
        height, width = labels.shape
        segments: list[tuple[float, float, float, float]] = []

        vertical = (labels[:, :-1] != labels[:, 1:]) & (valid[:, :-1] | valid[:, 1:])
        for column in range(width - 1):
            for start, stop in _true_runs(vertical[:, column]):
                x = (column + 1) / width
                segments.append((x, start / height, x, stop / height))

        horizontal = (labels[:-1, :] != labels[1:, :]) & (valid[:-1, :] | valid[1:, :])
        for row in range(height - 1):
            for start, stop in _true_runs(horizontal[row, :]):
                y = (row + 1) / height
                segments.append((start / width, y, stop / width, y))

        for start, stop in _true_runs(valid[:, 0]):
            segments.append((0.0, start / height, 0.0, stop / height))
        for start, stop in _true_runs(valid[:, -1]):
            segments.append((1.0, start / height, 1.0, stop / height))
        for start, stop in _true_runs(valid[0, :]):
            segments.append((start / width, 0.0, stop / width, 0.0))
        for start, stop in _true_runs(valid[-1, :]):
            segments.append((start / width, 1.0, stop / width, 1.0))

        if segments:
            values = np.asarray(segments, dtype=np.float32)
            starts = np.ascontiguousarray(values[:, :2])
            ends = np.ascontiguousarray(values[:, 2:])
        else:
            starts = np.empty((0, 2), dtype=np.float32)
            ends = np.empty((0, 2), dtype=np.float32)
        result = (starts, ends)
        self._boundary_cache[key] = result
        while len(self._boundary_cache) > self._boundary_cache_size:
            self._boundary_cache.popitem(last=False)
        return result

    def compose(
        self,
        axis: str,
        index: int,
        *,
        annotation_opacity: float = 0.58,
        selected_region_ids: Sequence[int] = (),
        selection_dim_factor: float = 0.35,
    ) -> NDArray[np.uint8]:
        """Compose one RGBA slice in O(slice pixels) after cached setup."""
        if not np.isfinite(annotation_opacity) or not 0 <= annotation_opacity <= 1:
            raise ValueError('annotation_opacity must be between zero and one')
        if not np.isfinite(selection_dim_factor) or not 0 <= selection_dim_factor <= 1:
            raise ValueError('selection_dim_factor must be between zero and one')

        template_slice = self.volumes.slice('template', axis, index)
        annotation_slice = self.volumes.slice('annotation', axis, index)
        template = oriented_slice(
            template_slice.values, template_slice.array_axes, axis, grid=self.volumes.grid
        )
        annotation = oriented_slice(
            annotation_slice.values, annotation_slice.array_axes, axis, grid=self.volumes.grid
        )
        if int(annotation.max(initial=0)) >= len(self._valid):
            raise ValueError('annotation contains an unknown source index')

        gray = np.clip((template.astype(np.float32) - self.low) / (self.high - self.low), 0, 1)
        rgb = np.repeat(np.rint(gray[..., None] * 255).astype(np.uint8), 3, axis=2)
        valid = self._valid[annotation]
        region_rgb = self._colors[annotation].astype(np.float32)
        selected = {abs(int(region_id)) for region_id in selected_region_ids if region_id}
        if selected:
            dim = valid & ~np.isin(np.abs(self._mapped_ids[annotation]), tuple(selected))
            region_rgb[dim] *= selection_dim_factor
        blended = rgb.astype(np.float32) * (1 - annotation_opacity)
        blended += region_rgb * annotation_opacity
        rgb[valid] = np.rint(blended[valid]).astype(np.uint8)
        alpha = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
        return np.ascontiguousarray(np.concatenate((rgb, alpha), axis=2))

    def compose_layers(
        self,
        axis: str,
        index: int,
        *,
        annotation_opacity: float = 0.58,
        selected_region_ids: Sequence[int] = (),
        selection_dim_factor: float = 0.35,
    ) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
        """Return independent anatomical and annotation RGBA image layers.

        Keeping the layers separate lets the renderer use linear filtering for
        the template and nearest-neighbour filtering for integer atlas labels.
        The annotation alpha is premultiplied only by its UI opacity; callers
        can therefore toggle either layer without recomposing the other one.
        """
        if not np.isfinite(annotation_opacity) or not 0 <= annotation_opacity <= 1:
            raise ValueError('annotation_opacity must be between zero and one')
        if not np.isfinite(selection_dim_factor) or not 0 <= selection_dim_factor <= 1:
            raise ValueError('selection_dim_factor must be between zero and one')
        template_slice = self.volumes.slice('template', axis, index)
        annotation_slice = self.volumes.slice('annotation', axis, index)
        template = oriented_slice(
            template_slice.values, template_slice.array_axes, axis, grid=self.volumes.grid
        )
        annotation = oriented_slice(
            annotation_slice.values, annotation_slice.array_axes, axis, grid=self.volumes.grid
        )
        if int(annotation.max(initial=0)) >= len(self._valid):
            raise ValueError('annotation contains an unknown source index')
        gray = np.clip((template.astype(np.float32) - self.low) / (self.high - self.low), 0, 1)
        anatomy_rgb = np.repeat(np.rint(gray[..., None] * 255).astype(np.uint8), 3, axis=2)
        valid = self._valid[annotation]
        # Let the panel background show through outside atlas tissue instead of
        # painting an artificial black rectangle around every slice.
        anatomy_alpha = np.where(valid, 255, 0).astype(np.uint8)
        anatomy = np.concatenate((anatomy_rgb, anatomy_alpha[..., None]), axis=2)
        region_rgb = self._colors[annotation].copy()
        selected = {abs(int(region_id)) for region_id in selected_region_ids if region_id}
        if selected:
            dim = valid & ~np.isin(np.abs(self._mapped_ids[annotation]), tuple(selected))
            region_rgb[dim] = np.rint(region_rgb[dim] * selection_dim_factor).astype(np.uint8)
        annotation_rgba = np.concatenate(
            (
                region_rgb,
                np.where(valid, np.rint(annotation_opacity * 255), 0).astype(np.uint8)[..., None],
            ),
            axis=2,
        )
        return np.ascontiguousarray(anatomy), np.ascontiguousarray(annotation_rgba)

    def region_mask(self, axis: str, index: int, region_ids: Sequence[int]) -> NDArray[np.bool_]:
        """Return a mapping-aware mask for logical atlas region identities."""
        annotation_slice = self.volumes.slice('annotation', axis, index)
        annotation = oriented_slice(
            annotation_slice.values, annotation_slice.array_axes, axis, grid=self.volumes.grid
        )
        if int(annotation.max(initial=0)) >= len(self._valid):
            raise ValueError('annotation contains an unknown source index')
        logical_ids = tuple({abs(int(region_id)) for region_id in region_ids if region_id})
        if not logical_ids:
            return np.zeros(annotation.shape, dtype=bool)
        return self._valid[annotation] & np.isin(np.abs(self._mapped_ids[annotation]), logical_ids)


def cursor_from_slice_fraction(
    cursor: AtlasCursor,
    axis: str,
    x_fraction: float,
    y_fraction: float,
    grid,
) -> AtlasCursor:
    """Move two cursor axes from normalized coordinates within a slice image."""
    if axis not in SLICE_DISPLAY_AXES:
        raise ValueError('slice axis must be ap, ml or dv')
    if not np.isfinite((x_fraction, y_fraction)).all():
        raise ValueError('slice coordinates must be finite')
    if not 0 <= x_fraction <= 1 or not 0 <= y_fraction <= 1:
        raise ValueError('slice coordinates must lie between zero and one')
    shape = grid.shape
    sizes = dict(zip(('ap', 'ml', 'dv'), shape, strict=True))
    x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
    fractions = {x_axis: x_fraction, y_axis: y_fraction}
    for anatomical_axis in (x_axis, y_axis):
        array_index = grid.array_axes.index(anatomical_axis)
        world_index = grid.world_axes.index(anatomical_axis)
        matrix = np.asarray(grid.index_to_world_um_matrix, dtype=np.float64).reshape(4, 4)
        derivative = matrix[world_index, array_index]
        if derivative == 0:
            raise ValueError('slice cursor requires an axis-aligned atlas grid')
        if derivative < 0:
            fractions[anatomical_axis] = 1 - fractions[anatomical_axis]
    result = cursor.replace(x_axis, round(fractions[x_axis] * (sizes[x_axis] - 1)), shape)
    return result.replace(y_axis, round(fractions[y_axis] * (sizes[y_axis] - 1)), shape)


def slice_index_fraction(grid, axis: str, index: int) -> float:
    """Map one array index to a world-increasing screen fraction."""
    array_index = grid.array_axes.index(axis)
    world_index = grid.world_axes.index(axis)
    derivative = np.asarray(grid.index_to_world_um_matrix).reshape(4, 4)[world_index, array_index]
    fraction = index / max(1, grid.shape[array_index] - 1)
    return float(1 - fraction if derivative < 0 else fraction)


def step_slice_cursor(
    cursor: AtlasCursor,
    axis: str,
    delta: int,
    shape: Sequence[int],
) -> AtlasCursor:
    """Move the cursor along one orthogonal-slice axis, clamped to the grid.

    ``axis`` identifies the slice plane (``'ap'``, ``'ml'`` or ``'dv'``), so
    wheel navigation changes that plane's index while leaving the in-plane
    cursor position untouched.
    """
    if axis not in ('ap', 'ml', 'dv'):
        raise ValueError('slice axis must be ap, ml or dv')
    if not isinstance(delta, (int, np.integer)):
        raise TypeError('slice step must be an integer')
    axis_index = ('ap', 'ml', 'dv').index(axis)
    size = int(shape[axis_index])
    if size <= 0:
        raise ValueError('slice axis has no samples')
    value = int(np.clip(cursor.as_index()[axis_index] + int(delta), 0, size - 1))
    return cursor.replace(axis, value, shape)


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
    return AtlasSliceComposer(volumes, mapping).compose(
        axis,
        index,
        annotation_opacity=annotation_opacity,
        selected_region_ids=selected_region_ids,
        selection_dim_factor=selection_dim_factor,
    )


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
        lookup = getattr(volumes, 'annotation_index_at_world', None)
        if lookup is not None:
            return int(np.asarray(lookup(self.world_um(volumes))).item())
        return int(volumes.annotation[self.as_index()])

    def region(self, volumes: AtlasVolumes, mapping: str) -> AtlasRegion | None:
        """Return the signed mapped region at this cursor, including void."""
        return mapped_region(volumes, self.source_index(volumes), mapping)
