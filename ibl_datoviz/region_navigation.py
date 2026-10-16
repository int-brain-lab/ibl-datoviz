"""Interior navigation anchors from the viewer's exact local annotation grid.

Anchors are presentation aids, not measurements. No external LUT, transport,
renderer, projection materialization or signal reader participates in lookup.
"""

from __future__ import annotations

from collections import OrderedDict
from numbers import Integral
from threading import RLock

import numpy as np

from ibl_anatomy import AtlasVolumes


class RegionNavigation:
    """Find an occupied voxel nearest a signed mapped region's voxel centroid.

    Two bounded flat-chunk passes compute moments and minimize centroid distance.
    Integer scores preserve exact AP/ML/DV tie breaking without floating-point
    centroid rounding. The source grid is the displayed grid, so an occupied
    anchor lies inside the same mapped region on all three exact slice planes.

    ``anchor()`` performs synchronous CPU work and is safe to invoke from the
    viewer's latest-wins worker. The owner must discard superseded intent before
    applying the returned tuple; this object never changes a cursor or selection.
    """

    def __init__(self, source, *, cache_size=128, chunk_voxels=262144):
        if isinstance(cache_size, bool) or not isinstance(cache_size, Integral) or cache_size < 1:
            raise ValueError('navigation cache size must be a positive integer')
        if (
            isinstance(chunk_voxels, bool)
            or not isinstance(chunk_voxels, Integral)
            or chunk_voxels < 1
        ):
            raise ValueError('navigation chunk size must be a positive integer')
        self.source = source
        self.cache_size, self.chunk_voxels = int(cache_size), int(chunk_voxels)
        self._anchors = OrderedDict()
        self._lookups = {}
        self._lock = RLock()
        self.available = isinstance(source, AtlasVolumes)
        self.unavailable_reason = (
            ''
            if self.available
            else (
                'Auto-slice requires dense annotation voxels; '
                'lazy projection sources are unavailable'
            )
        )
        if not self.available:
            return
        values = source.annotation
        if (
            not isinstance(values, np.ndarray)
            or values.dtype != np.uint16
            or values.ndim != 3
            or tuple(values.shape) != tuple(source.grid.shape)
            or tuple(source.grid.array_axes) != ('ap', 'ml', 'dv')
        ):
            raise ValueError(
                'region navigation requires uint16 annotations on the exact AP/ML/DV grid'
            )
        self._shape = tuple(map(int, values.shape))
        if any(size < 1 for size in self._shape):
            raise ValueError('region navigation requires a nonempty annotation grid')

    def _lookup(self, mapping):
        if mapping in self._lookups:
            return self._lookups[mapping]
        catalog = self.source.regions
        targets = {row.atlas_id for row in catalog.physical(mapping)}
        rows = catalog.physical('allen')
        size = max(row.index for row in rows) + 1
        if size > 65536 or min(row.index for row in rows) < 0:
            raise ValueError('annotation source rows must fit uint16 labels')
        mapped = np.zeros(size, np.int64)
        known = np.zeros(size, bool)
        for row, region_id in zip(
            rows, catalog.map_allen_ids((row.atlas_id for row in rows), mapping), strict=True
        ):
            known[row.index] = True
            if row.index == 0 or row.atlas_id == 0 or region_id is None or region_id == 0:
                continue
            if region_id not in targets:
                raise ValueError('mapped region is absent from its signed physical catalog')
            if (region_id < 0) != (row.atlas_id < 0):
                # Some legacy reduced-root crosswalks fold a side into the
                # opposite root. Never use that as a navigation anchor.
                continue
            mapped[row.index] = region_id
        self._lookups[mapping] = mapped, known, targets
        return mapped, known, targets

    def _matching_chunks(self, membership, known):
        values = self.source.annotation
        for start in range(0, values.size, self.chunk_voxels):
            # flat slicing remains bounded even for non-contiguous NumPy sources.
            chunk = values.flat[start : start + self.chunk_voxels]
            if int(chunk.max(initial=0)) >= len(known) or not np.all(known[chunk]):
                raise ValueError('annotation contains an unknown source index')
            offsets = np.flatnonzero(membership[chunk])
            if len(offsets):
                yield offsets + start

    def _coordinates(self, flat, axis):
        if axis == 0:
            return flat // (self._shape[1] * self._shape[2])
        if axis == 1:
            return flat // self._shape[2] % self._shape[1]
        return flat % self._shape[2]

    def anchor(self, mapping, region_id):
        """Return AP/ML/DV indices, or None for absent/unmapped/void regions.

        Unknown mappings and inconsistent source labels fail explicitly. A lazy
        source returns None without accessing its projection or intensity data.
        Equal distances resolve to the first AP, then ML, then DV voxel.
        """
        if isinstance(region_id, (bool, np.bool_)) or not isinstance(region_id, Integral):
            raise ValueError('region navigation requires a signed integer region ID')
        if not self.available:
            return None
        region_id = int(region_id)
        key = mapping, region_id
        with self._lock:
            if key in self._anchors:
                result = self._anchors.pop(key)
                self._anchors[key] = result
                return result
            mapped, known, targets = self._lookup(mapping)
            result = None
            membership = mapped == region_id
            if region_id != 0 and region_id in targets and np.any(membership):
                result = self._compute_anchor(membership, known)
            self._anchors[key] = result
            if len(self._anchors) > self.cache_size:
                self._anchors.popitem(last=False)
            return result

    def _compute_anchor(self, membership, known):
        result = None
        count, sums = 0, [0, 0, 0]
        # Bound moments and exact distance arithmetic before any int64 sums.
        voxels = int(self.source.annotation.size)
        maximum = tuple(size - 1 for size in self._shape)
        if voxels * max(maximum) > np.iinfo(np.int64).max:
            raise OverflowError('region navigation moments exceed exact int64 range')
        for flat in self._matching_chunks(membership, known):
            count += len(flat)
            for axis in range(3):
                sums[axis] += int(self._coordinates(flat, axis).sum(dtype=np.int64))
        if count:
            # n*||x||² - 2*x·sum is proportional to centroid distance,
            # with the same region-constant term omitted for every voxel.
            bound = count * sum(value * value for value in maximum)
            bound += 2 * sum(value * total for value, total in zip(maximum, sums, strict=True))
            if bound > np.iinfo(np.int64).max:
                raise OverflowError('region navigation distances exceed exact int64 range')
            best_score, best_flat = None, None
            for flat in self._matching_chunks(membership, known):
                score = np.zeros(len(flat), np.int64)
                for axis in range(3):
                    coord = self._coordinates(flat, axis)
                    score += count * coord * coord - 2 * sums[axis] * coord
                first = int(score.argmin())
                value = int(score[first])
                if best_score is None or value < best_score:
                    best_score, best_flat = value, int(flat[first])
            result = tuple(map(int, np.unravel_index(best_flat, self._shape)))
        return result
