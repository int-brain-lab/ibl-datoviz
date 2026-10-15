"""Owned physical 3-D planes of the linked viewer's accepted prepared slices."""

from __future__ import annotations

from numbers import Integral

import numpy as np

from .navigator import SLICE_DISPLAY_AXES
from .sampled_plane import SampledPlane, SampledPlaneVisual


def slice_plane_corners(grid, axis, index):
    """Return half-voxel image edges in ML/AP/DV µm, matching oriented_slice.

    Row zero and column zero are the smallest displayed world coordinates.
    Corner order follows image rows: row0/col0, lastrow/col0, row0/lastcol,
    lastrow/lastcol (the sampled-plane TL, BL, TR, BR convention).
    """
    if axis not in SLICE_DISPLAY_AXES:
        raise ValueError('slice axis must be ap, ml or dv')
    if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral):
        raise ValueError('slice index must be an integer')
    array_axes, world_axes = tuple(grid.array_axes), tuple(grid.world_axes)
    if set(array_axes) != {'ap', 'ml', 'dv'} or set(world_axes) != set(array_axes):
        raise ValueError('slice planes require explicit AP/ML/DV array and world axes')
    shape = np.asarray(grid.shape)
    fixed = array_axes.index(axis)
    if not 0 <= index < shape[fixed]:
        raise IndexError('slice index is outside the grid')
    matrix = np.asarray(grid.index_to_world_um_matrix, dtype=float).reshape(4, 4)
    if not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]):
        raise ValueError('slice planes require a finite affine grid')
    linear = matrix[:3, :3]
    tolerance = max(1.0, float(np.max(np.abs(linear)))) * 1e-10
    for column, name in enumerate(array_axes):
        active = np.flatnonzero(np.abs(linear[:, column]) > tolerance)
        if len(active) != 1 or active[0] != world_axes.index(name):
            raise ValueError('slice planes require an axis-aligned anatomical grid')
    x_name, y_name = SLICE_DISPLAY_AXES[axis]
    x, y = array_axes.index(x_name), array_axes.index(y_name)

    def edges(column, name):
        bounds = (-0.5, float(shape[column]) - 0.5)
        return bounds if linear[world_axes.index(name), column] > 0 else bounds[::-1]

    x0, x1 = edges(x, x_name)
    y0, y1 = edges(y, y_name)
    indices = np.empty((4, 3), dtype=float)
    indices[:, fixed] = index
    indices[:, x] = (x0, x0, x1, x1)
    indices[:, y] = (y0, y1, y0, y1)
    world = indices @ linear.T + matrix[:3, 3]
    # Downstream display transforms consume world coordinates in ML/AP/DV order.
    return np.ascontiguousarray(world[:, [world_axes.index(name) for name in ('ml', 'ap', 'dv')]])


class SlicePlanes:
    """Borrow existing prepared pixels; create no reader, worker or cursor state."""

    def __init__(self, viewer, source, *, source_id=None):
        self.viewer, self.source = viewer, source
        self.source_id = str(source_id) if source_id is not None else None
        self._accepted = {}
        self._planes = {}
        self._closed = False

    def _check(self):
        self.viewer._require_open()
        if self._closed:
            raise RuntimeError('slice planes are closed')

    @staticmethod
    def _axis(axis):
        if axis not in SLICE_DISPLAY_AXES:
            raise ValueError('slice axis must be ap, ml or dv')

    @property
    def visible_axes(self):
        """Axes currently drawn in 3-D, with unsupported scientific query coverage."""
        self._check()
        return tuple(axis for axis in SLICE_DISPLAY_AXES if axis in self._planes)

    def _invalidate(self):
        picking = getattr(self.viewer, 'picking', None)
        if picking is not None:
            picking.invalidate()

    def _build(self, request, payload):
        corners = slice_plane_corners(self.source.grid, request.axis, request.index)
        candidates = []
        try:
            for pixels, sampling in ((payload.anatomy, 'linear'), (payload.annotation, 'nearest')):
                candidates.append(
                    SampledPlaneVisual(
                        self.viewer.dvz,
                        self.viewer.scene,
                        self.viewer.panel,
                        SampledPlane(corners, pixels, sampling),
                        transform=self.viewer.mesh_data.normalize_points,
                        depth_policy='physical',
                        alpha_mode='wboit',
                    )
                )
        except Exception:
            for candidate in reversed(candidates):
                candidate.close()
            raise
        return tuple(candidates)

    def update(self, axis, request, payload):
        """Accept paired pixels/geometry; stale requests cannot replace a newer plane."""
        self._check()
        self._axis(axis)
        if request.axis != axis:
            raise ValueError('slice request axis does not match the plane')
        if self.source_id is not None and request.source_id != self.source_id:
            raise ValueError('slice request belongs to a different source grid')
        # Validate geometry and both pixel extents before changing native or retained state.
        slice_plane_corners(self.source.grid, axis, request.index)
        x, y = SLICE_DISPLAY_AXES[axis]
        shape = dict(zip(self.source.grid.array_axes, self.source.grid.shape, strict=True))
        expected = (shape[y], shape[x], 4)
        for pixels in (payload.anatomy, payload.annotation):
            if pixels.dtype != np.uint8 or pixels.shape != expected:
                raise ValueError(f'{axis} plane pixels must be RGBA8 with extent {expected}')
        previous = self._accepted.get(axis)
        if previous is not None:
            previous_request = previous[0]
            if request.revision < previous_request.revision:
                return False
            if request.revision == previous_request.revision and request != previous_request:
                raise ValueError('one slice revision cannot identify different requests')
        candidates = self._build(request, payload) if axis in self._planes else None
        if candidates is not None:
            old = self._planes[axis]
            self._planes[axis] = candidates
            self._invalidate()
            for component in reversed(old):
                component.close()
        self._accepted[axis] = (request, payload)
        return True

    def show(self, axis, visible=True):
        """Create or remove one paired physical plane from its accepted slice payload."""
        self._check()
        self._axis(axis)
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('plane visibility must be boolean')
        if bool(visible) == (axis in self._planes):
            return
        if visible:
            if axis not in self._accepted:
                raise ValueError('slice plane has no accepted prepared slice payload')
            self._planes[axis] = self._build(*self._accepted[axis])
        else:
            old = self._planes.pop(axis)
            for component in reversed(old):
                component.close()
        self._invalidate()

    def close(self):
        """Destroy plane pairs before their borrowed scene and source workers."""
        if self._closed:
            return
        self._check()
        for pair in reversed(tuple(self._planes.values())):
            for component in reversed(pair):
                component.close()
        self._planes.clear()
        self._accepted.clear()
        self._invalidate()
        self._closed = True
