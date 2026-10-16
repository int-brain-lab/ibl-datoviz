"""Owned mapped geometry from the shared reader's exact half-grid contour rings.

No SVG parsing or anatomy IO occurs here. Boundary cancellation consumes the
reader's partitioned anatomical regions: shared edges cancel within each mapped
region, and selected regions form one outline without internal selected edges.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from numbers import Integral

import numpy as np


def _ring(values):
    raw = np.asarray(values, dtype=np.float64)
    if raw.ndim != 2 or raw.shape[1] != 2 or len(raw) < 4 or not np.isfinite(raw).all():
        raise ValueError('contour rings must contain finite Nx2 rectilinear coordinates')
    if np.array_equal(raw[0], raw[-1]):
        raw = raw[:-1]
    doubled = raw * 2
    if not np.equal(doubled, np.rint(doubled)).all() or np.abs(doubled).max() > 2**52:
        raise ValueError('contour rings must use exact bounded half-grid coordinates')
    delta = np.roll(raw, -1, axis=0) - raw
    if not np.all(np.logical_xor(delta[:, 0] == 0, delta[:, 1] == 0)):
        raise ValueError('contour rings must have nonzero axis-aligned edges')
    shifted = raw - raw[0]
    if (
        np.sum(
            shifted[:, 0] * np.roll(shifted[:, 1], -1) - shifted[:, 1] * np.roll(shifted[:, 0], -1)
        )
        == 0
    ):
        raise ValueError('contour rings must enclose nonzero area')
    return np.frombuffer(raw.tobytes(order='C'), dtype=np.float64).reshape(raw.shape)


def _array(values):
    raw = np.asarray(values, dtype=np.float64).reshape((-1, 2))
    if not np.isfinite(raw).all():
        raise ValueError('contour boundaries must contain finite coordinates')
    return np.frombuffer(raw.tobytes(order='C'), dtype=np.float64).reshape(raw.shape)


def selected_descendants(catalog, mapping, region_ids):
    """Expand exact signed target parents; opposite hemispheres remain independent."""
    ids = tuple(region_ids)
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) for value in ids
    ):
        raise ValueError('selected contour region IDs must be signed integers')
    selected = {int(value) for value in ids if value}
    rows = catalog.physical(mapping)
    by_id = {row.atlas_id: row for row in rows}
    result = set()
    for row in rows:
        current, seen = row, set()
        while current is not None:
            if current.atlas_id in selected:
                result.add(row.atlas_id)
                break
            if current.atlas_id in seen:
                raise ValueError('cyclic region ancestry cannot select contour descendants')
            seen.add(current.atlas_id)
            current = by_id.get(current.parent_id)
    return frozenset(result)


@dataclass(frozen=True)
class ContourComponent:
    """One owned filled outer ring and holes, in original SVG coordinates."""

    atlas_id: int
    allen_id: int
    outer: np.ndarray
    holes: tuple[np.ndarray, ...]
    selected: bool
    bounds: tuple[float, float, float, float] = field(init=False, repr=False)

    def __post_init__(self):
        """Validate identities and detach every ring from the shared source."""
        for value in (self.atlas_id, self.allen_id):
            if (
                isinstance(value, (bool, np.bool_))
                or not isinstance(value, Integral)
                or value == 0
            ):
                raise ValueError('contour identities must be nonzero signed integers')
        if not isinstance(self.selected, (bool, np.bool_)):
            raise ValueError('contour selection must be boolean')
        object.__setattr__(self, 'outer', _ring(self.outer))
        object.__setattr__(self, 'holes', tuple(_ring(hole) for hole in self.holes))
        low, high = self.outer.min(axis=0), self.outer.max(axis=0)
        object.__setattr__(self, 'bounds', (*map(float, low), *map(float, high)))


def _contains(ring, x, y):
    """Return inside and exact-edge membership using the half-open ray rule."""
    a, b = ring, np.roll(ring, -1, axis=0)
    edge = (
        (a[:, 0] == b[:, 0])
        & (x == a[:, 0])
        & (y >= np.minimum(a[:, 1], b[:, 1]))
        & (y <= np.maximum(a[:, 1], b[:, 1]))
    )
    edge |= (
        (a[:, 1] == b[:, 1])
        & (y == a[:, 1])
        & (x >= np.minimum(a[:, 0], b[:, 0]))
        & (x <= np.maximum(a[:, 0], b[:, 0]))
    )
    # Only vertical edges can cross a horizontal ray in the supported profile.
    cross = ((a[:, 1] > y) != (b[:, 1] > y)) & (a[:, 0] > x)
    return bool(np.count_nonzero(cross) % 2), bool(np.any(edge))


@dataclass(frozen=True)
class ContourGeometry:
    """Prepared owned fills, deduplicated mapped borders and selected union edges."""

    mapping: str
    components: tuple[ContourComponent, ...]
    boundary_starts: np.ndarray
    boundary_ends: np.ndarray
    selection_starts: np.ndarray
    selection_ends: np.ndarray
    _region_intervals: tuple = field(default=(), init=False, repr=False, compare=False)
    _selected_ids: frozenset | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        """Freeze endpoint storage and enforce paired segment extents."""
        object.__setattr__(self, 'components', tuple(self.components))
        for name in ('boundary_starts', 'boundary_ends', 'selection_starts', 'selection_ends'):
            object.__setattr__(self, name, _array(getattr(self, name)))
        if (
            self.boundary_starts.shape != self.boundary_ends.shape
            or self.selection_starts.shape != self.selection_ends.shape
        ):
            raise ValueError('contour boundary endpoints must have matching shapes')

    def with_selection(self, catalog, selected_region_ids=()):
        """Share validated rings/borders and derive only the selected region union.

        Per-region boundary parity was already normalized during preparation.
        XORing those intervals preserves the original partition cancellation,
        including holes, partial overlaps and independently signed hemispheres.
        """
        selected = selected_descendants(catalog, self.mapping, selected_region_ids)
        if selected == self._selected_ids:
            return self
        intervals = self._region_intervals or _mapped_intervals(self.components)
        starts, ends = _segments(_selected_intervals(intervals, selected))
        components = []
        for component in self.components:
            flag = component.atlas_id in selected
            if flag == component.selected:
                components.append(component)
                continue
            # Only already-validated owned immutable storage enters this path.
            clone = object.__new__(ContourComponent)
            for name in ('atlas_id', 'allen_id', 'outer', 'holes', 'bounds'):
                object.__setattr__(clone, name, getattr(component, name))
            object.__setattr__(clone, 'selected', flag)
            components.append(clone)
        result = object.__new__(ContourGeometry)
        for name in ('mapping', 'boundary_starts', 'boundary_ends'):
            object.__setattr__(result, name, getattr(self, name))
        object.__setattr__(result, 'components', tuple(components))
        object.__setattr__(result, 'selection_starts', starts)
        object.__setattr__(result, 'selection_ends', ends)
        object.__setattr__(result, '_region_intervals', intervals)
        object.__setattr__(result, '_selected_ids', selected)
        return result

    @property
    def retained_bytes(self):
        """Account owned arrays plus conservative fixed Python storage overhead."""
        rings = [
            ring for component in self.components for ring in (component.outer, *component.holes)
        ]
        arrays = [
            *rings, self.boundary_starts, self.boundary_ends,
            self.selection_starts, self.selection_ends,
            *(edges for _, edges in self._region_intervals),
        ]
        return (
            sum(array.nbytes + 256 for array in arrays)
            + 512 * len(self.components) + 256 * len(self._region_intervals) + 1024
        )

    def region_at(self, svgx, svgy):
        """Resolve signed mapped identity; exact edges use reverse source paint order.

        Hole interiors are empty; their boundaries belong to the surrounding
        component. Nested islands are separate filled components from the reader.
        """
        point = np.asarray((svgx, svgy), dtype=float)
        if point.shape != (2,) or not np.isfinite(point).all():
            raise ValueError('contour picking requires two finite SVG coordinates')
        x, y = map(float, point)
        for component in reversed(self.components):
            x0, y0, x1, y1 = component.bounds
            if not x0 <= x <= x1 or not y0 <= y <= y1:
                continue
            inside, boundary = _contains(component.outer, x, y)
            if not inside and not boundary:
                continue
            in_hole = False
            for hole in component.holes:
                hole_inside, hole_boundary = _contains(hole, x, y)
                if hole_inside and not hole_boundary:
                    in_hole = True
                    break
            if not in_hole:
                return component.atlas_id
        return None


def _edges(component):
    arrays = []
    for ring in (component.outer, *component.holes):
        points = np.rint(ring * 2).astype(np.int64)
        following = np.roll(points, -1, axis=0)
        horizontal = points[:, 1] == following[:, 1]
        first = np.where(horizontal, points[:, 0], points[:, 1])
        last = np.where(horizontal, following[:, 0], following[:, 1])
        arrays.append(np.column_stack((
            np.logical_not(horizontal).astype(np.int64),
            np.where(horizontal, points[:, 1], points[:, 0]),
            np.minimum(first, last), np.maximum(first, last),
        )))
    return np.concatenate(arrays)


def _segments(intervals):
    values = intervals if isinstance(intervals, np.ndarray) else tuple(intervals)
    edges = np.asarray(values, dtype=np.int64).reshape(-1, 4)
    horizontal = edges[:, 0] == 0
    starts, ends = np.empty((len(edges), 2)), np.empty((len(edges), 2))
    starts[:, 0] = np.where(horizontal, edges[:, 2], edges[:, 1]) / 2
    starts[:, 1] = np.where(horizontal, edges[:, 1], edges[:, 2]) / 2
    ends[:, 0] = np.where(horizontal, edges[:, 3], edges[:, 1]) / 2
    ends[:, 1] = np.where(horizontal, edges[:, 1], edges[:, 3]) / 2
    return _array(starts), _array(ends)


def _normalize_intervals(edges, *, parity):
    """Normalize exact interval events, preserving lexicographic segment order."""
    if not len(edges):
        return np.empty((0, 4), dtype=np.int64)
    events = np.concatenate((edges[:, :3], edges[:, (0, 1, 3)]))
    order = np.lexsort((events[:, 2], events[:, 1], events[:, 0]))
    events = events[order]
    changed = np.any(events[1:] != events[:-1], axis=1)
    starts = np.flatnonzero(np.r_[True, changed])
    if parity:
        counts = np.diff(np.r_[starts, len(events)])
        # Even endpoint multiplicity cannot change XOR membership. Dropping it
        # also coalesces adjacent spans exactly as the original sweep does.
        endpoints = events[starts[counts % 2 != 0]]
    else:
        deltas = np.ones(2 * len(edges), dtype=np.int64)
        deltas[len(edges):] = -1
        counts = np.cumsum(np.add.reduceat(deltas[order], starts), dtype=np.int64)
        unique = events[starts]
        line_ends = np.r_[np.any(unique[1:, :2] != unique[:-1, :2], axis=1), True]
        if np.any(counts < 0) or np.any(counts[line_ends] != 0):
            raise ValueError('unbalanced contour edge intervals')
        # Every line is balanced, so cumulative counts restart at zero without
        # subtracting coordinates or expanding any long half-grid edge.
        previous = np.r_[0, counts[:-1]]
        endpoints = unique[(previous > 0) != (counts > 0)]
    if len(endpoints) % 2 or np.any(endpoints[::2, :2] != endpoints[1::2, :2]):
        raise ValueError('unbalanced contour edge intervals')
    return np.column_stack((endpoints[::2], endpoints[1::2, 2]))


def _selected_intervals(per_region, selected):
    arrays = [edges for atlas_id, edges in per_region if atlas_id in selected and len(edges)]
    edges = np.concatenate(arrays) if arrays else np.empty((0, 4), dtype=np.int64)
    return _normalize_intervals(edges, parity=True)


def _mapped_intervals(components):
    per_region = defaultdict(list)
    for component in components:
        per_region[component.atlas_id].append(_edges(component))
    result = []
    for atlas_id, arrays in per_region.items():
        edges = _normalize_intervals(np.concatenate(arrays), parity=True)
        immutable = np.frombuffer(edges.tobytes(), dtype=np.int64).reshape(edges.shape)
        result.append((atlas_id, immutable))
    return tuple(result)


def prepare_contour_geometry(paths, catalog, mapping, selected_region_ids=()):
    """Map shared decoded partition components; never decode or smooth their rings."""
    paths = tuple(paths)
    allen_ids = tuple(path.atlas_ids['allen'] for path in paths)
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
        for value in allen_ids
    ):
        raise ValueError('contour Allen IDs must be signed integers')
    targets = {row.atlas_id for row in catalog.physical(mapping)}
    mapped = catalog.map_allen_ids(allen_ids, mapping)
    components = []
    for path, allen_id, atlas_id in zip(paths, allen_ids, mapped, strict=True):
        if atlas_id is None or atlas_id == 0:
            continue
        if atlas_id not in targets:
            raise ValueError('mapped contour ID is absent from its physical catalog')
        for source in path.components:
            component = ContourComponent(
                int(atlas_id),
                int(allen_id),
                source.outer,
                tuple(source.holes),
                False,
            )
            components.append(component)
    per_region = _mapped_intervals(components)
    arrays = [edges for _, edges in per_region if len(edges)]
    combined = np.concatenate(arrays) if arrays else np.empty((0, 4), dtype=np.int64)
    starts, ends = _segments(_normalize_intervals(combined, parity=False))
    geometry = ContourGeometry(
        mapping, tuple(components), starts, ends, np.empty((0, 2)), np.empty((0, 2)),
    )
    object.__setattr__(geometry, '_region_intervals', per_region)
    object.__setattr__(geometry, '_selected_ids', frozenset())
    return geometry.with_selection(catalog, selected_region_ids)
