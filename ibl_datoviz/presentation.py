"""Pure scalar colors and mapping reductions, independent of native rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import Literal

    from numpy.typing import NDArray

    from ibl_anatomy import AtlasRegionCatalog

    from .regions import AtlasRegionValues


@dataclass(frozen=True)
class RegionPresentation:
    """Reduced signed region identities, display weights, values, and colors."""

    region_ids: NDArray[np.int64]
    values: NDArray[np.float64]
    weights: NDArray[np.float64]
    colors: NDArray[np.uint8]


def scalar_colors(
    values: NDArray[np.float64],
    value_range: tuple[float, float] | None,
    color_scheme: Literal['diverging', 'sequential'] = 'diverging',
) -> NDArray[np.uint8]:
    """Validate scalar values and interpolate their RGBA presentation."""
    if color_scheme not in ('diverging', 'sequential'):
        raise ValueError(f'unknown probe color scheme: {color_scheme}')
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or np.isinf(values).any():
        raise ValueError('probe values must be one-dimensional and contain no infinities')
    finite = np.isfinite(values)
    if value_range is None:
        if not np.any(finite):
            limits = (0.0, 1.0)
        else:
            limits = (float(np.min(values[finite])), float(np.max(values[finite])))
    else:
        raw_limits = np.asarray(value_range, dtype=np.float64)
        if raw_limits.shape != (2,):
            raise ValueError('probe value range must contain exactly two values')
        limits = (float(raw_limits[0]), float(raw_limits[1]))
    constant = value_range is None and limits[1] == limits[0]
    if (
        not np.isfinite(limits).all()
        or (limits[1] < limits[0])
        or (value_range is not None and limits[1] == limits[0])
    ):
        raise ValueError('probe value range must be finite and increasing')

    t = (
        np.full(len(values), 0.5, dtype=np.float64)
        if constant
        else np.clip((values - limits[0]) / (limits[1] - limits[0]), 0.0, 1.0)
    )
    if color_scheme == 'sequential':
        low = np.asarray((88, 70, 180), dtype=np.float64)
        middle = np.asarray((45, 180, 170), dtype=np.float64)
        high = np.asarray((253, 231, 73), dtype=np.float64)
    else:
        low = np.asarray((49, 116, 178), dtype=np.float64)
        middle = np.asarray((247, 247, 247), dtype=np.float64)
        high = np.asarray((203, 45, 62), dtype=np.float64)
    rgb = np.empty((len(values), 3), dtype=np.float64)
    lower = t <= 0.5
    rgb[lower] = low + (middle - low) * (2 * t[lower, None])
    rgb[~lower] = middle + (high - middle) * (2 * t[~lower, None] - 1)
    rgb[~finite] = (110, 116, 126)
    return np.ascontiguousarray(
        np.column_stack((np.rint(rgb), np.full(len(values), 255))), dtype=np.uint8
    )


def region_presentation(
    catalog: AtlasRegionCatalog,
    mapping: str,
    data: AtlasRegionValues,
    value_range: tuple[float, float] | None,
    color_scheme: Literal['diverging', 'sequential'],
    opacity: float,
) -> RegionPresentation:
    """Reduce mapping collisions with finite-only weighted scalar means."""
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('region opacity must be between zero and one')
    try:
        mapped_ids = catalog.map_allen_ids(data.allen_region_ids, mapping)
    except KeyError as error:
        raise ValueError(str(error)) from error
    grouped: dict[int, list[tuple[float, float]]] = {}
    for mapped_id, value, weight in zip(mapped_ids, data.values, data.weights, strict=True):
        if mapped_id is None or mapped_id == 0:
            continue
        grouped.setdefault(mapped_id, []).append((float(value), float(weight)))
    region_ids = np.ascontiguousarray(sorted(grouped), dtype=np.int64)
    values = np.empty(len(region_ids), dtype=np.float64)
    weights = np.empty(len(region_ids), dtype=np.float64)
    for index, region_id in enumerate(region_ids):
        entries = grouped[int(region_id)]
        weights[index] = sum(weight for _, weight in entries)
        finite = [(value, weight) for value, weight in entries if np.isfinite(value)]
        values[index] = (
            sum(value * weight for value, weight in finite) / sum(weight for _, weight in finite)
            if finite
            else np.nan
        )
    colors = scalar_colors(values, value_range, color_scheme)
    if opacity < 1:
        colors[:, 3] = np.rint(colors[:, 3] * opacity).astype(np.uint8)
    return RegionPresentation(region_ids, values, weights, colors)
