"""Renderer-independent slice preparation and owned upload buffers."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

from .contour_geometry import ContourGeometry, prepare_contour_geometry
from .navigator import AtlasSliceComposer, label_contours

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from .slice_scheduler import SliceRequest


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


def prepare_slice_layers(
    composer: AtlasSliceComposer, request: SliceRequest
) -> PreparedSliceLayers:
    """Prepare only from captured request values and a renderer-free composer."""
    if composer.mapping != request.mapping:
        composer.set_mapping(request.mapping)
    anatomy, annotation = composer.compose_layers(
        request.axis,
        request.index,
        annotation_opacity=request.annotation_opacity,
        selected_region_ids=request.selected_region_ids,
        selection_dim_factor=request.selection_dim_factor,
    )
    if not request.anatomy_visible:
        anatomy[..., 3] = 0
    if not request.annotation_visible:
        annotation[..., 3] = 0
    if request.renderer == 'contours':
        section = composer.volumes.contour_slice(request.axis, request.index)
        geometry = prepare_contour_geometry(
            section.paths, composer.volumes.regions, request.mapping, request.selected_region_ids
        )
        transform = np.asarray(section.svg_to_fraction).reshape(3, 3)

        def fractions(points):
            return points @ transform[:2, :2].T + transform[:2, 2]

        return PreparedSliceLayers(
            anatomy,
            annotation,
            fractions(geometry.boundary_starts),
            fractions(geometry.boundary_ends),
            fractions(geometry.selection_starts),
            fractions(geometry.selection_ends),
            geometry,
            section.svg_to_fraction,
        )
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

    def __init__(self, source, mapping: str) -> None:
        self._composers = {
            axis: AtlasSliceComposer(source, mapping) for axis in ('ap', 'ml', 'dv')
        }
        self._locks = {axis: RLock() for axis in self._composers}

    def __call__(self, request: SliceRequest) -> PreparedSliceLayers:
        """Return a complete owned payload under the axis cache lock."""
        with self._locks[request.axis]:
            return prepare_slice_layers(self._composers[request.axis], request)
