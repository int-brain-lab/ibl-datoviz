"""Renderer-neutral scalar values attached to signed Allen regions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray


@dataclass(frozen=True)
class AtlasRegionValues:
    """One scalar and aggregation weight per signed Allen region."""

    allen_region_ids: NDArray[np.int64]
    values: NDArray[np.float64]
    weights: NDArray[np.float64]
    labels: tuple[str, ...]
    value_name: str
    weight_name: str

    @classmethod
    def from_arrays(
        cls,
        allen_region_ids: Sequence[int],
        values: Sequence[float],
        *,
        weights: Sequence[float] | None = None,
        labels: Sequence[str] | None = None,
        value_name: str = 'Value',
        weight_name: str = 'Weight',
    ) -> AtlasRegionValues:
        """Validate and copy a mapping-independent region payload."""
        raw_ids = np.asarray(allen_region_ids)
        scalar = np.asarray(values, dtype=np.float64)
        if (
            raw_ids.ndim != 1
            or len(raw_ids) == 0
            or not np.issubdtype(raw_ids.dtype, np.integer)
            or np.any(raw_ids == 0)
            or len(np.unique(raw_ids)) != len(raw_ids)
        ):
            raise ValueError('Allen region IDs must be unique nonzero integers')
        count = len(raw_ids)
        if scalar.shape != (count,) or np.isinf(scalar).any():
            raise ValueError('region values must have shape (n,) and contain no infinities')
        raw_weights = (
            np.ones(count, dtype=np.float64)
            if weights is None
            else np.asarray(weights, dtype=np.float64)
        )
        if (
            raw_weights.shape != (count,)
            or not np.isfinite(raw_weights).all()
            or np.any(raw_weights < 0)
            or np.any(np.isfinite(scalar) & (raw_weights == 0))
        ):
            raise ValueError(
                'region weights must be finite and nonnegative, and positive for finite values'
            )
        region_labels = (
            tuple(str(int(region_id)) for region_id in raw_ids)
            if labels is None
            else tuple(str(label) for label in labels)
        )
        if len(region_labels) != count or any(not label for label in region_labels):
            raise ValueError('region labels must contain one non-empty label per region')
        if not value_name or not weight_name:
            raise ValueError('region value and weight names cannot be empty')

        arrays = (
            np.ascontiguousarray(raw_ids, dtype=np.int64),
            np.ascontiguousarray(scalar, dtype=np.float64),
            np.ascontiguousarray(raw_weights, dtype=np.float64),
        )
        for array in arrays:
            array.setflags(write=False)
        return cls(*arrays, region_labels, str(value_name), str(weight_name))
