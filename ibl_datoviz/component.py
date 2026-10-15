"""Small shared validation and lifetime helpers for caller-owned scenes."""

from dataclasses import dataclass

import numpy as np


def owned(array, dtype):
    """Return immutable C-contiguous storage independent of the input."""
    result = np.array(array, dtype=dtype, order='C', copy=True)
    result.setflags(write=False)
    return result


def rgba_array(colors, shape):
    """Validate integer RGB/RGBA channels before conversion to uint8."""
    raw = np.asarray(colors)
    if (
        raw.shape not in (shape + (3,), shape + (4,))
        or not np.issubdtype(raw.dtype, np.integer)
        or np.any(raw < 0)
        or np.any(raw > 255)
    ):
        raise ValueError('colors must contain RGB/RGBA integer channels in [0, 255]')
    if raw.shape[-1] == 3:
        raw = np.concatenate((raw, np.full(shape + (1,), 255, np.uint8)), axis=-1)
    return owned(raw, np.uint8)


@dataclass(frozen=True)
class ComponentCapabilities:
    """Supported behavior for the current native component configuration."""

    alpha_modes: tuple[str, ...]
    depth_test: bool
    depth_write: bool
    order_independent: bool = False
    sampled_plane_3d: bool = False


class ComponentVisual:
    """Own component resources while borrowing the caller's live scene and panel."""

    def __init__(self, dvz, scene, panel, transform):
        self.dvz, self.scene, self.panel = dvz, scene, panel
        self.transform = transform
        self.visual = None
        self.data = None
        self._visible = True
        self._closed = False

    @staticmethod
    def _check(status, context):
        if status != 0:
            raise RuntimeError(f'{context} failed with status {status}')

    @staticmethod
    def _required(handle, context):
        if not handle:
            raise RuntimeError(f'{context} returned no handle')
        return handle

    def _require_open(self):
        if self._closed:
            raise RuntimeError('component is closed')

    def _positions(self, coordinates):
        # Empty populations own no drawable positions; atlas normalization needs bounds.
        transformed = (
            coordinates
            if self.transform is None or not len(coordinates)
            else self.transform(coordinates)
        )
        result = owned(transformed, np.float32)
        if result.shape != coordinates.shape or not np.isfinite(result).all():
            raise ValueError('display transform must return finite positions of the same shape')
        return result

    def set_visible(self, visible):
        """Set authored visibility, independently of an empty payload."""
        self._require_open()
        if self.visual:
            self._check(
                self.dvz.dvz_visual_set_visible(self.visual, bool(visible) and self._has_data()),
                'component visibility',
            )
        self._visible = bool(visible)

    def _has_data(self):
        return self.data is not None

    def close(self):
        """Destroy this component before the caller destroys its scene; idempotent."""
        if self._closed:
            return
        if self.visual:
            self.dvz.dvz_visual_destroy(self.visual)
        self.visual = self.data = None
        self._closed = True
