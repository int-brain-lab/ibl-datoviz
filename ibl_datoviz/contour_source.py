"""Exact registered section geometry and its display-plane affine."""

from dataclasses import dataclass

import numpy as np

from .navigator import SLICE_DISPLAY_AXES


@dataclass(frozen=True)
class ContourSection:
    """Shared decoded paths plus an immutable SVG-to-display-fraction transform."""

    paths: tuple
    svg_to_fraction: tuple[float, ...]


def projection_fraction_transform(grid, axis, projection):
    """Map SVG edges to the same world-increasing image edges as oriented_slice."""
    x, y, width, height = projection.manifest['view_box']
    sizes = projection.slice_shape
    grid_matrix = np.asarray(grid.index_to_world_um_matrix).reshape(4, 4)
    plane = np.asarray(projection.plane_index_to_world_um).reshape(4, 4)
    matrix = np.eye(3)
    for screen, name, origin, extent in zip(
        (0, 1), SLICE_DISPLAY_AXES[axis], (x, y), (width, height), strict=True
    ):
        world = grid.world_axes.index(name)
        column = grid.array_axes.index(name)
        derivative = plane[world, screen + 1]
        # AtlasSliceSource already verifies that centers/corners share the grid.
        # SVG view_box edges span all plane voxels, including their half cells.
        if not np.isfinite(extent) or extent <= 0 or derivative == 0:
            raise ValueError('contour projection requires finite axis-aligned extents')
        if sizes[screen] != grid.shape[column] or grid_matrix[world, column] == 0:
            raise ValueError('contour projection shape differs from the exact grid')
        sign = 1 if derivative > 0 else -1
        matrix[screen, screen] = sign / extent
        matrix[screen, 2] = -origin / extent if sign > 0 else 1 + origin / extent
    return tuple(map(float, matrix.reshape(-1)))
