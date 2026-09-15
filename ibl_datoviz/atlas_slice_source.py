# ruff: noqa: PLR0912
"""Renderer-independent lazy volume made from atlas transport assets.

This module deliberately depends only on the public ``ibl-atlas-assets`` reader
interfaces.  In particular, it does not know about a canvas or a Datoviz
texture: callers receive the same ``values, array_axes`` contract as an atlas
volume slice.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy.typing import NDArray


_TOKEN = re.compile(r'[MmLlHhVvZz]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
_COMMANDS = frozenset('MmLlHhVvZz')
_DISPLAY_AXES = {'ap': ('ml', 'dv'), 'ml': ('ap', 'dv'), 'dv': ('ml', 'ap')}


@dataclass(frozen=True)
class AtlasSourceSlice:
    """One owned transport slice with explicit anatomical array axes."""

    values: NDArray[np.uint16]
    array_axes: tuple[str, str]


def parse_svg_path(  # noqa: PLR0915
    path: str,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Parse the restricted generated SVG path grammar into polygon rings."""
    matches = list(_TOKEN.finditer(path))
    if not matches or any(
        path[a.end() : b.start()].strip(' ,\t\r\n')
        for a, b in zip(matches, matches[1:], strict=False)
    ):
        raise ValueError('invalid SVG path separator')
    if path[: matches[0].start()].strip(' ,\t\r\n') or path[matches[-1].end() :].strip(' ,\t\r\n'):
        raise ValueError('invalid SVG path trailing data')
    tokens = [item.group() for item in matches]
    if any(c.isalpha() and c not in _COMMANDS and c not in 'eE' for c in path):
        raise ValueError('unsupported SVG path command')
    pos = 0
    command = None
    x = y = 0.0
    start = (0.0, 0.0)
    rings: list[tuple[tuple[float, float], ...]] = []
    ring: list[tuple[float, float]] = []

    def number() -> float:
        nonlocal pos
        if pos >= len(tokens) or tokens[pos] in _COMMANDS:
            raise ValueError('SVG path command has too few coordinates')
        try:
            value = float(tokens[pos])
        except ValueError as exc:
            raise ValueError('invalid SVG path number') from exc
        pos += 1
        return value

    while pos < len(tokens):
        if tokens[pos] in _COMMANDS:
            command = tokens[pos]
            pos += 1
            if command in 'Zz':
                if ring:
                    rings.append(tuple(ring))
                    ring = []
                x, y = start
                command = None
                continue
        if command is None:
            raise ValueError('SVG path coordinates require a command')
        relative = command.islower()
        upper = command.upper()
        if upper in 'ML':
            nx, ny = number(), number()
            if relative:
                nx, ny = x + nx, y + ny
            x, y = nx, ny
            if upper == 'M':
                if ring:
                    rings.append(tuple(ring))
                ring = []
                start = (x, y)
                command = 'l' if relative else 'L'
            ring.append((x, y))
        elif upper == 'H':
            nx = number()
            x = x + nx if relative else nx
            ring.append((x, y))
        elif upper == 'V':
            ny = number()
            y = y + ny if relative else ny
            ring.append((x, y))
        else:
            raise ValueError(f'unsupported SVG path command: {command}')
    if ring:
        rings.append(tuple(ring))
    if command is not None and command.upper() != 'Z':
        raise ValueError('SVG subpath must be explicitly closed with Z')
    if not rings or any(len(item) < 3 for item in rings):
        raise ValueError('SVG path ring has fewer than three points')
    return tuple(rings)


def _rasterize(rings, height, width, view):
    """Even-odd scanline fill, visiting only rows intersecting each ring.

    Intersections are evaluated for all affected rows at once. This keeps the
    exact pixel-centre and half-open interval rules of the scalar
    implementation while avoiding a Python loop over every edge on every row.
    """
    out = np.zeros((height, width), dtype=bool)
    x0, y0, vw, vh = view
    sx, sy = width / vw, height / vh
    for ring in rings:
        points = np.asarray(ring, dtype=float)
        points[:, 0] = (points[:, 0] - x0) * sx
        points[:, 1] = (points[:, 1] - y0) * sy
        ymin = max(0, int(np.ceil(points[:, 1].min() - 0.5)))
        ymax = min(height - 1, int(np.floor(points[:, 1].max() - 0.5)))
        if ymax < ymin:
            continue

        # Include an edge at its lower endpoint and exclude it at its upper
        # endpoint, matching the original scalar scanline test. NaNs mark
        # non-crossing edges and sort after all valid intersections.
        next_points = np.roll(points, -1, axis=0)
        rows = np.arange(ymin, ymax + 1)
        scanlines = rows[:, None] + 0.5
        ya, yb = points[:, 1], next_points[:, 1]
        crossing = ((ya > scanlines) & (yb <= scanlines)) | ((yb > scanlines) & (ya <= scanlines))
        denominator = yb - ya
        intersections = points[:, 0] + (
            (scanlines - ya)
            * (next_points[:, 0] - points[:, 0])
            / np.where(denominator == 0, 1, denominator)
        )
        intersections[~crossing] = np.nan
        intersections.sort(axis=1)

        for offset, row in enumerate(rows):
            row_intersections = intersections[offset]
            row_intersections = row_intersections[np.isfinite(row_intersections)]
            for left, right in zip(row_intersections[::2], row_intersections[1::2], strict=True):
                lo = max(0, int(np.ceil(left - 0.5)))
                hi = min(width, int(np.ceil(right - 0.5)))
                if hi > lo:
                    out[row, lo:hi] ^= True
    return out


class AtlasSliceSource:
    """Lazy template/annotation source backed by one grid and three projections."""

    def __init__(
        self,
        intensity_pack,
        projections: Mapping[str, object],
        regions,
        *,
        section_cache_size: int = 16,
    ) -> None:
        if set(projections) != {'ap', 'ml', 'dv'}:
            raise ValueError('three ap/ml/dv registered projections are required')
        if section_cache_size < 1:
            raise ValueError('section cache size must be positive')
        self._pack = intensity_pack
        self.regions = regions
        self.grid = intensity_pack.grid
        self._projections = dict(projections)
        self._annotation_cache: OrderedDict[tuple[str, int], NDArray[np.uint16]] = OrderedDict()
        self._cache_lock = RLock()
        self._cache_limit = section_cache_size
        if not all(self.reference_space_id == p.reference_space_id for p in projections.values()):
            raise ValueError('intensity and registered projection reference spaces differ')
        if not all(self.grid_id == p.grid_id for p in projections.values()):
            raise ValueError('intensity and registered projection grid IDs differ')
        for axis, projection in projections.items():
            if projection.world_slice_axis != axis:
                raise ValueError(f'projection {axis} has wrong world slice axis')
            if projection.slice_count != self.grid.shape[self.grid.array_axes.index(axis)]:
                raise ValueError(f'projection {axis} slice count differs from intensity grid')
            section = intensity_pack.read_section(axis, 0)
            expected_shape = tuple(
                section.values.shape[section.array_axes.index(anatomical_axis)]
                for anatomical_axis in _DISPLAY_AXES[axis]
            )
            if tuple(projection.slice_shape) != expected_shape:
                raise ValueError(f'projection {axis} plane shape differs from intensity grid')
            self._validate_affine(axis, projection)
        self._by_index = {int(row.index): row for row in regions.physical('allen')}
        self._by_id = {int(row.atlas_id): row for row in regions.physical('allen')}

    @property
    def reference_space_id(self):
        """Return the shared scientific reference-space identity."""
        return self.grid.reference_space_id

    @property
    def grid_id(self):
        """Return the exact high-resolution grid identity."""
        return self.grid.grid_id

    @property
    def value_range(self):
        """Return the exact scalar range declared by the intensity transport."""
        return self._pack.value_range

    @property
    def recommended_display_range(self):
        """Return the transport's explicit display window, when available."""
        return getattr(self._pack, 'recommended_display_range', self.value_range)

    @property
    def first_right_ml_index(self):
        """Return the first ML voxel centre on or to the right of the midline."""
        ml_axis = self.grid.array_axes.index('ml')
        indices = np.zeros((self.grid.shape[ml_axis], 3), dtype=np.float64)
        indices[:, ml_axis] = np.arange(self.grid.shape[ml_axis])
        ml_um = self.grid.index_to_world(indices)[:, self.grid.world_axes.index('ml')]
        right = np.flatnonzero(ml_um >= 0)
        return int(right[0]) if len(right) else self.grid.shape[ml_axis]

    def cache_info(self) -> tuple[int, int]:
        """Return annotation-cache entries and their decoded byte count."""
        with self._cache_lock:
            decoded_bytes = sum(item.nbytes for item in self._annotation_cache.values())
            return len(self._annotation_cache), decoded_bytes

    def clear_cache(self) -> None:
        """Drop decoded intensity blocks and rasterized annotation sections."""
        self._pack.clear_cache()
        with self._cache_lock:
            self._annotation_cache.clear()

    def _validate_affine(self, axis, projection) -> None:
        # A registered plane must agree with the volume's world transform at
        # voxel centres; testing corners catches translation, scale and flips.
        screen_axes = _DISPLAY_AXES[axis]
        shape = projection.slice_shape
        slice_count = self.grid.shape[self.grid.array_axes.index(axis)]
        grid_matrix = np.asarray(self.grid.index_to_world_um_matrix).reshape(4, 4)
        projection_matrix = np.asarray(projection.plane_index_to_world_um).reshape(4, 4)
        for u, v, s in (
            (0, 0, 0),
            (shape[0] - 1, shape[1] - 1, 0),
            (0, 0, slice_count - 1),
            (shape[0] - 1, shape[1] - 1, slice_count - 1),
        ):
            idx = np.zeros(3)
            idx[self.grid.array_axes.index(axis)] = s
            for plane_column, anatomical_axis, screen_value, screen_size in (
                (1, screen_axes[0], u, shape[0]),
                (2, screen_axes[1], v, shape[1]),
            ):
                array_index = self.grid.array_axes.index(anatomical_axis)
                world_index = self.grid.world_axes.index(anatomical_axis)
                same_direction = (
                    grid_matrix[world_index, array_index]
                    * projection_matrix[world_index, plane_column]
                    > 0
                )
                idx[array_index] = (
                    screen_value if same_direction else screen_size - 1 - screen_value
                )
            if not np.allclose(
                projection.index_to_world((s, u, v)), self.grid.index_to_world(idx), atol=1e-5
            ):
                raise ValueError(f'projection {axis} affine differs from intensity grid')

    def _annotation(self, axis: str, index: int) -> NDArray[np.uint16]:
        key = (axis, index)
        with self._cache_lock:
            value = self._annotation_cache.pop(key, None)
            if value is not None:
                self._annotation_cache[key] = value
                return value.copy()
        projection = self._projections[axis]
        section = projection.load_slice(index)
        width, height = projection.slice_shape
        view = projection.manifest['view_box']
        result = np.zeros((height, width), dtype=np.uint16)
        for item in section.paths:
            rings = parse_svg_path(item.d)
            row = self._by_id.get(int(item.atlas_ids['allen']))
            if row is None:
                raise KeyError(f'unknown Allen atlas ID: {item.atlas_ids["allen"]}')
            result[_rasterize(rings, height, width, view)] = row.index
        # SVG is plane (row=v, column=u); transport sections use raw atlas
        # array axes. Compare both affines to recover any projection-specific
        # reversal (notably AP in the canonical sagittal projection).
        section_axes = tuple(item for item in self.grid.array_axes if item != axis)
        x_axis, y_axis = _DISPLAY_AXES[axis]
        grid_matrix = np.asarray(self.grid.index_to_world_um_matrix).reshape(4, 4)
        projection_matrix = np.asarray(projection.plane_index_to_world_um).reshape(4, 4)
        for screen_axis, plane_column, anatomical_axis in (
            (1, 1, x_axis),
            (0, 2, y_axis),
        ):
            world_index = self.grid.world_axes.index(anatomical_axis)
            array_index = self.grid.array_axes.index(anatomical_axis)
            if (
                grid_matrix[world_index, array_index]
                * projection_matrix[world_index, plane_column]
                < 0
            ):
                result = np.flip(result, axis=screen_axis)
        screen_permutation = (section_axes.index(y_axis), section_axes.index(x_axis))
        result = np.ascontiguousarray(np.transpose(result, np.argsort(screen_permutation)))
        with self._cache_lock:
            self._annotation_cache[key] = result
            while len(self._annotation_cache) > self._cache_limit:
                self._annotation_cache.popitem(last=False)
        return result.copy()

    def slice(self, volume: str, axis: str, index: int) -> AtlasSourceSlice:
        """Return one lazy high-resolution anatomy or annotation section."""
        if axis not in self._projections:
            raise ValueError('slice axis must be ap, ml or dv')
        if volume not in ('template', 'annotation'):
            raise ValueError('volume must be template or annotation')
        array_axes = tuple(item for item in self.grid.array_axes if item != axis)
        values = (
            self._pack.read_section(axis, index).values
            if volume == 'template'
            else self._annotation(axis, index)
        )
        return AtlasSourceSlice(np.ascontiguousarray(values), array_axes)

    def annotation_index_at_world(self, positions_um, *, mode='raise'):
        """Resolve high-resolution annotation source indices at world positions."""
        if mode not in ('raise', 'clip'):
            raise ValueError('volume lookup mode must be raise or clip')
        indices = np.rint(self.grid.world_to_index(positions_um)).astype(np.int64)
        shape = np.asarray(self.grid.shape)
        outside = np.any((indices < 0) | (indices >= shape), axis=-1)
        if np.any(outside) and mode == 'raise':
            raise ValueError('world position lies outside the atlas volume')
        indices = np.clip(indices, 0, shape - 1)
        flat = indices.reshape(-1, 3)
        # AP sections expose (ml, dv), hence this lookup uses the AP-native
        # projection and remains correct regardless of the other projections'
        # display orientation.
        result = np.asarray(
            [self._annotation('ap', int(i[0]))[i[1], i[2]] for i in flat], dtype=np.uint16
        )
        return result.reshape(indices.shape[:-1])

    def cached_annotation_index_at_world(self, position_um, *, preferred_axis='ap'):
        """Return one cached annotation index, or ``None`` without doing I/O."""
        if preferred_axis not in self.grid.array_axes:
            raise ValueError('preferred axis must be ap, ml or dv')
        indices = np.rint(self.grid.world_to_index(position_um)).astype(np.int64)
        if indices.shape != (3,):
            raise ValueError('cached annotation lookup requires one world position')
        shape = np.asarray(self.grid.shape)
        if np.any((indices < 0) | (indices >= shape)):
            return None
        axes = (
            preferred_axis,
            *tuple(axis for axis in self.grid.array_axes if axis != preferred_axis),
        )
        with self._cache_lock:
            for axis in axes:
                section_index = int(indices[self.grid.array_axes.index(axis)])
                annotation = self._annotation_cache.get((axis, section_index))
                if annotation is None:
                    continue
                plane_indices = tuple(
                    int(indices[self.grid.array_axes.index(item)])
                    for item in self.grid.array_axes
                    if item != axis
                )
                return int(annotation[plane_indices])
        return None

    def region_for_source_index(self, source_index: int):
        """Resolve an annotation source row index through the shared catalog."""
        try:
            return self._by_index[int(source_index)]
        except KeyError as exc:
            raise KeyError(f'unknown annotation source index: {source_index}') from exc
