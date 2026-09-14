"""Renderer-neutral probe-site payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence

    from numpy.typing import NDArray


@dataclass(frozen=True)
class ProbeSites:
    """Stable site identity, atlas coordinates, values, and signed Allen labels."""

    site_ids: NDArray[np.uint64]
    positions_um: NDArray[np.float32]
    values: NDArray[np.float64]
    allen_region_ids: NDArray[np.int64]
    labels: tuple[str, ...]

    @classmethod
    def from_arrays(
        cls,
        positions_um: Sequence[Sequence[float]],
        values: Sequence[float],
        allen_region_ids: Sequence[int],
        *,
        site_ids: Sequence[int] | None = None,
        labels: Sequence[str] | None = None,
    ) -> ProbeSites:
        """Validate arrays and copy them into immutable contiguous storage."""
        positions = np.asarray(positions_um, dtype=np.float32)
        scalar = np.asarray(values, dtype=np.float64)
        regions = np.asarray(allen_region_ids)
        if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
            raise ValueError('probe positions must have non-empty shape (n, 3)')
        count = len(positions)
        if not np.isfinite(positions).all():
            raise ValueError('probe positions must be finite')
        if scalar.shape != (count,) or np.isinf(scalar).any():
            raise ValueError('probe values must have shape (n,) and contain no infinities')
        if regions.shape != (count,) or not np.issubdtype(regions.dtype, np.integer):
            raise ValueError('Allen region IDs must be an integer array with shape (n,)')

        raw_ids = np.arange(1, count + 1) if site_ids is None else np.asarray(site_ids)
        if (
            raw_ids.shape != (count,)
            or not np.issubdtype(raw_ids.dtype, np.integer)
            or np.any(raw_ids <= 0)
            or len(np.unique(raw_ids)) != count
        ):
            raise ValueError('site IDs must be unique positive integers with shape (n,)')
        site_labels = (
            tuple(f'Site {site_id}' for site_id in raw_ids)
            if labels is None
            else tuple(str(label) for label in labels)
        )
        if len(site_labels) != count or any(not label for label in site_labels):
            raise ValueError('probe labels must contain one non-empty label per site')

        arrays = (
            np.ascontiguousarray(raw_ids, dtype=np.uint64),
            np.ascontiguousarray(positions, dtype=np.float32),
            np.ascontiguousarray(scalar, dtype=np.float64),
            np.ascontiguousarray(regions, dtype=np.int64),
        )
        for array in arrays:
            array.setflags(write=False)
        return cls(*arrays, site_labels)
