"""Renderer-independent slice preparation and owned upload buffers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

from .contour_geometry import ContourGeometry, prepare_contour_geometry
from .navigator import AtlasSliceComposer, label_contours

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

    from .slice_scheduler import SliceRequest


class _SliceSupersededError(RuntimeError):
    """Internal control flow discarded by the scheduler's stale generation check."""


def _check_current(is_current):
    if is_current is not None and not is_current():
        raise _SliceSupersededError('slice preparation was superseded or closed')


@dataclass(frozen=True, slots=True)
class PreparedSliceLayers:
    """Owned, read-only layers and normalized boundary geometry for one slice."""

    anatomy: NDArray[np.uint8]
    annotation: NDArray[np.uint8]
    boundary_starts: NDArray[np.float32]
    boundary_ends: NDArray[np.float32]

    selection_starts: NDArray[np.float32] = field(default_factory=lambda: np.empty((0, 2)))
    selection_ends: NDArray[np.float32] = field(default_factory=lambda: np.empty((0, 2)))

    contours: ContourGeometry | None = None
    svg_to_fraction: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        """Detach buffers from composer caches before transferring to the owner."""
        for name, dtype in (
            ('anatomy', np.uint8),
            ('annotation', np.uint8),
            ('boundary_starts', np.float32),
            ('boundary_ends', np.float32),
            ('selection_starts', np.float32),
            ('selection_ends', np.float32),
        ):
            values = np.array(getattr(self, name), dtype=dtype, order='C', copy=True)
            values.setflags(write=False)
            object.__setattr__(self, name, values)


def _immutable(values):
    values = np.asarray(values, dtype=np.float32)
    return np.frombuffer(values.tobytes(order='C'), dtype=np.float32).reshape(values.shape)


@dataclass(frozen=True)
class _CachedContours:
    geometry: ContourGeometry
    svg_to_fraction: tuple
    boundary_starts: np.ndarray
    boundary_ends: np.ndarray

    @property
    def retained_bytes(self):
        return (
            self.geometry.retained_bytes
            + self.boundary_starts.nbytes + self.boundary_ends.nbytes + 1024
        )


class _ContourCache:
    """Bounded mapped geometry for one immutable source and worker axis."""

    def __init__(self, source, *, max_entries=4, max_bytes=16 * 1024 * 1024):
        if max_entries < 1 or max_bytes < 1:
            raise ValueError('contour cache limits must be positive')
        self.source, self.max_entries, self.max_bytes = source, max_entries, max_bytes
        self.entries, self.retained_bytes = OrderedDict(), 0

    def get(self, request, *, is_current=None):
        _check_current(is_current)
        key = request.source_id, request.mapping, request.axis, request.index
        if key in self.entries:
            entry = self.entries.pop(key)
            self.entries[key] = entry
            return entry
        # Preload the shared numerical section before compose_layers so its
        # annotation adapter can reuse the same decoded reader result.
        section = self.source.contour_slice(request.axis, request.index)
        _check_current(is_current)
        geometry = prepare_contour_geometry(section.paths, self.source.regions, request.mapping)
        _check_current(is_current)
        transform = np.asarray(section.svg_to_fraction).reshape(3, 3)
        entry = _CachedContours(
            geometry, tuple(section.svg_to_fraction),
            _immutable(geometry.boundary_starts @ transform[:2, :2].T + transform[:2, 2]),
            _immutable(geometry.boundary_ends @ transform[:2, :2].T + transform[:2, 2]),
        )
        if entry.retained_bytes <= self.max_bytes:
            while self.entries and (
                len(self.entries) >= self.max_entries
                or self.retained_bytes + entry.retained_bytes > self.max_bytes
            ):
                _, previous = self.entries.popitem(last=False)
                self.retained_bytes -= previous.retained_bytes
            self.entries[key] = entry
            self.retained_bytes += entry.retained_bytes
        return entry


def _contour_entry(composer, request, *, is_current=None):
    caches = getattr(composer, '_contour_caches', None)
    if caches is None:
        caches = composer._contour_caches = {}
    cache = caches.get(request.axis)
    if cache is None or cache.source is not composer.volumes:
        cache = caches[request.axis] = _ContourCache(composer.volumes)
    return cache.get(request, is_current=is_current)


def _contour_payload(anatomy, annotation, entry, geometry):
    """Share only trusted immutable cached geometry; detach mutable image inputs."""
    transform = np.asarray(entry.svg_to_fraction).reshape(3, 3)
    # Public construction still always detaches callers' arrays. This private
    # path shares byte-backed buffers owned by this worker's bounded cache.
    payload = object.__new__(PreparedSliceLayers)
    for name, values in (('anatomy', anatomy), ('annotation', annotation)):
        owned = np.array(values, dtype=np.uint8, order='C', copy=True)
        owned.setflags(write=False)
        object.__setattr__(payload, name, owned)
    for name in ('boundary_starts', 'boundary_ends'):
        object.__setattr__(payload, name, getattr(entry, name))
    for name in ('selection_starts', 'selection_ends'):
        values = getattr(geometry, name)
        normalized = _immutable(values @ transform[:2, :2].T + transform[:2, 2])
        object.__setattr__(payload, name, normalized)
    object.__setattr__(payload, 'contours', geometry)
    object.__setattr__(payload, 'svg_to_fraction', entry.svg_to_fraction)
    return payload


def prepare_slice_layers(
    composer: AtlasSliceComposer, request: SliceRequest, *,
    is_current: Callable[[], bool] | None = None,
) -> PreparedSliceLayers:
    """Prepare only from captured request values and a renderer-free composer."""
    _check_current(is_current)
    if composer.mapping != request.mapping:
        composer.set_mapping(request.mapping)
    contour_entry = (
        _contour_entry(composer, request, is_current=is_current)
        if request.renderer == 'contours' else None
    )
    _check_current(is_current)
    anatomy, annotation = composer.compose_layers(
        request.axis,
        request.index,
        annotation_opacity=request.annotation_opacity,
        selected_region_ids=request.selected_region_ids,
        selection_dim_factor=request.selection_dim_factor,
    )
    _check_current(is_current)
    if not request.anatomy_visible:
        anatomy[..., 3] = 0
    if not request.annotation_visible:
        annotation[..., 3] = 0
    if request.renderer == 'contours':
        geometry = contour_entry.geometry.with_selection(
            composer.volumes.regions, request.selected_region_ids,
        )
        return _contour_payload(anatomy, annotation, contour_entry, geometry)
    starts, ends = composer.boundary_segments(request.axis, request.index)
    if request.selected_region_ids:
        mask = composer.region_mask(request.axis, request.index, request.selected_region_ids)
        selection_starts, selection_ends = label_contours(mask)
    else:
        selection_starts = selection_ends = np.empty((0, 2), dtype=np.float32)
    return PreparedSliceLayers(anatomy, annotation, starts, ends, selection_starts, selection_ends)


class SlicePreparation:
    """Keep bounded composer caches independent for each worker axis.

    The source grid/catalog is the immutable asset contract retained at
    construction. Mapping, cursor, selection, and visibility arrive exclusively
    through each immutable request; no viewer or native handle is retained.
    """

    def __init__(
        self, source, mapping: str, *, contour_cache_entries=4,
        contour_cache_bytes=16 * 1024 * 1024,
    ) -> None:
        self._composers = {
            axis: AtlasSliceComposer(source, mapping) for axis in ('ap', 'ml', 'dv')
        }
        self._locks = {axis: RLock() for axis in self._composers}
        for axis, composer in self._composers.items():
            composer._contour_caches = {
                axis: _ContourCache(
                    source, max_entries=contour_cache_entries, max_bytes=contour_cache_bytes,
                ),
            }

    def contour_cache_info(self):
        """Return per-axis entry counts and accounted bytes for diagnostics."""
        result = {}
        for axis, composer in self._composers.items():
            with self._locks[axis]:
                cache = composer._contour_caches[axis]
                result[axis] = len(cache.entries), cache.retained_bytes
        return result

    def __call__(self, request: SliceRequest) -> PreparedSliceLayers:
        """Return a complete owned payload under the axis cache lock."""
        return self.prepare_cancellable(request, None)

    def prepare_cancellable(
        self, request: SliceRequest, is_current: Callable[[], bool] | None,
    ) -> PreparedSliceLayers:
        """Stop obsolete preparation at phase boundaries without retaining a viewer.

        Numerical decoding and raster composition finish their current operation;
        cancellation is cooperative, never an interruption of source/cache writes.
        The scheduler suppresses obsolete outcomes before native presentation.
        """
        _check_current(is_current)
        with self._locks[request.axis]:
            _check_current(is_current)
            return prepare_slice_layers(
                self._composers[request.axis], request, is_current=is_current,
            )
