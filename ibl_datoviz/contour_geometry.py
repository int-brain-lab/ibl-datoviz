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
    for ring in (component.outer, *component.holes):
        points = np.rint(ring * 2).astype(np.int64)
        for a, b in zip(points, np.roll(points, -1, axis=0), strict=True):
            if a[1] == b[1]:
                yield 0, int(a[1]), min(int(a[0]), int(b[0])), max(int(a[0]), int(b[0]))
            else:
                yield 1, int(a[0]), min(int(a[1]), int(b[1])), max(int(a[1]), int(b[1]))


def _add(lines, axis, fixed, low, high):
    events = lines[axis, fixed]
    events[low] += 1
    events[high] -= 1


def _intervals(lines, *, parity):
    """Normalize partial overlaps without expanding long edges into grid steps."""
    for (axis, fixed), events in sorted(lines.items()):
        previous, count, run = None, 0, None
        for position, delta in sorted(events.items()):
            active = count % 2 != 0 if parity else count > 0
            if previous is not None:
                if active and run is None:
                    run = previous
                elif not active and run is not None:
                    yield axis, fixed, run, previous
                    run = None
            count += delta
            previous = position
        if run is not None:
            yield axis, fixed, run, previous
        if count:
            raise ValueError('unbalanced contour edge intervals')


def _segments(intervals):
    starts, ends = [], []
    for axis, fixed, low, high in intervals:
        if axis == 0:
            starts.append((low / 2, fixed / 2))
            ends.append((high / 2, fixed / 2))
        else:
            starts.append((fixed / 2, low / 2))
            ends.append((fixed / 2, high / 2))
    return _array(starts), _array(ends)


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
    selected = selected_descendants(catalog, mapping, selected_region_ids)
    components = []
    per_region = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    selection = defaultdict(lambda: defaultdict(int))
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
                atlas_id in selected,
            )
            components.append(component)
            for edge in _edges(component):
                _add(per_region[atlas_id], *edge)
                if component.selected:
                    _add(selection, *edge)
    combined = defaultdict(lambda: defaultdict(int))
    for lines in per_region.values():
        for edge in _intervals(lines, parity=True):
            _add(combined, *edge)
    starts, ends = _segments(_intervals(combined, parity=False))
    selection_starts, selection_ends = _segments(_intervals(selection, parity=True))
    return ContourGeometry(
        mapping, tuple(components), starts, ends, selection_starts, selection_ends
    )
