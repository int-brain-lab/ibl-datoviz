"""Arbitrary atlas-world point collections, separate from linked probe sites."""

import ctypes
from dataclasses import dataclass

import numpy as np

from .component import ComponentCapabilities, ComponentVisual, owned, rgba_array


@dataclass(frozen=True)
class PointCollection:
    """Owned point positions in atlas-world micrometres, RGBA and pixel diameters."""

    positions_um: np.ndarray
    colors: np.ndarray
    sizes_px: np.ndarray

    def __post_init__(self):
        """Validate public construction and own every caller-supplied array."""
        positions = owned(self.positions_um, np.float32)
        if positions.ndim != 2 or positions.shape[1] != 3 or not np.isfinite(positions).all():
            raise ValueError('point positions must have finite shape (n, 3)')
        colors = rgba_array(self.colors, (len(positions),))
        sizes = np.asarray(self.sizes_px, dtype=np.float32)
        if sizes.ndim == 0:
            if not np.isfinite(sizes) or sizes <= 0:
                raise ValueError('point sizes must be finite and positive')
            sizes = np.full(len(positions), sizes, np.float32)
        if sizes.shape != (len(positions),) or not np.isfinite(sizes).all() or np.any(sizes <= 0):
            raise ValueError('point sizes must be finite and positive, with shape (n,) or scalar')
        for name, value in (
            ('positions_um', positions),
            ('colors', colors),
            ('sizes_px', owned(sizes, np.float32)),
        ):
            object.__setattr__(self, name, value)

    def __len__(self):
        """Return the logical number of points, including zero."""
        return len(self.positions_um)

    @classmethod
    def from_arrays(cls, positions_um, colors, *, sizes_px=3.0):
        """Validate and copy explicit colors; empty (0, 3) positions are supported."""
        return cls(positions_um, colors, sizes_px)

    @classmethod
    def from_scalars(cls, positions_um, values, *, palette, value_range, sizes_px=3.0):
        """Map scalars through an explicit LUT256 using website interpolation/rounding.

        Normalization is float64, RGB rounding is floor(x + 0.5), and finite values
        clip to the supplied increasing range. NaNs use the low RGB color with
        zero alpha. Infinities are rejected. No range or palette is inferred.
        """
        scalar = np.asarray(values, dtype=np.float64)
        if scalar.shape != (len(positions_um),) or np.isinf(scalar).any():
            raise ValueError('point values must have shape (n,) and contain no infinities')
        lut = np.asarray(palette)
        if (
            lut.shape != (256, 3)
            or not np.issubdtype(lut.dtype, np.integer)
            or np.any(lut < 0)
            or np.any(lut > 255)
        ):
            raise ValueError('palette must be a 256-entry integer RGB LUT in [0, 255]')
        bounds = np.asarray(value_range, dtype=np.float64)
        if bounds.shape != (2,) or not np.isfinite(bounds).all() or bounds[1] <= bounds[0]:
            raise ValueError('value range must be finite and increasing')
        low, high = bounds
        finite = np.isfinite(scalar)
        scaled = np.clip((np.where(finite, scalar, low) - low) / (high - low), 0, 1) * 255
        lower = np.floor(scaled).astype(np.intp)
        upper = np.minimum(lower + 1, 255)
        local = scaled - lower
        rgb = np.floor(
            lut[lower].astype(float)
            + (lut[upper].astype(float) - lut[lower]) * local[:, None]
            + 0.5
        )
        colors = np.column_stack((rgb, np.where(finite, 255, 0))).astype(np.uint8)
        return cls.from_arrays(positions_um, colors, sizes_px=sizes_px)


class PointCollectionVisual(ComponentVisual):
    """Attach ordinary points to a borrowed scene/panel with explicit alpha policy."""

    def __init__(
        self, dvz, scene, panel, data, *, transform=None, alpha_mode='blended', depth_test=True
    ):
        if alpha_mode not in ('opaque', 'blended'):
            raise ValueError(
                'points support opaque or blended alpha; WBOIT/mask/peeling unavailable'
            )
        super().__init__(dvz, scene, panel, transform)
        self.alpha_mode, self.depth_test = alpha_mode, bool(depth_test)
        self.capabilities = ComponentCapabilities(
            ('opaque', 'blended'), self.depth_test, self.depth_test and alpha_mode == 'opaque'
        )
        self._display_positions = None
        try:
            self.replace(data)
        except Exception:
            self.close()
            raise

    def _has_data(self):
        return self.data is not None and len(self.data) > 0

    @staticmethod
    def _attributes(data, positions):
        return {'position': positions, 'color': data.colors, 'diameter_px': data.sizes_px}

    def replace(self, data):
        """Atomically replace all point attributes; empty data hides retained storage."""
        self._require_open()
        if not isinstance(data, PointCollection):
            raise TypeError('data must be a PointCollection')
        positions = self._positions(data.positions_um)
        previous, old_positions = self.data, self._display_positions
        if not len(data):
            if self.visual:
                self._check(self.dvz.dvz_visual_set_visible(self.visual, False), 'empty points')
            self.data, self._display_positions = data, positions
            return
        created = not self.visual
        try:
            if created:
                self.visual = self._required(self.dvz.dvz_point(self.scene, 0), 'point visual')
                style = self.dvz.dvz_point_style_desc()
                style.aspect, style.stroke_width_px = self.dvz.DVZ_SHAPE_ASPECT_FILLED, 0
                self._check(
                    self.dvz.dvz_point_set_style(self.visual, ctypes.byref(style)), 'point style'
                )
                mode = getattr(self.dvz, f'DVZ_ALPHA_{self.alpha_mode.upper()}')
                self._check(self.dvz.dvz_visual_set_alpha_mode(self.visual, mode), 'point alpha')
                self._check(
                    self.dvz.dvz_visual_set_depth_test(self.visual, self.depth_test), 'point depth'
                )
            self._check(
                self.dvz.dvz_visual_set_data_many(self.visual, self._attributes(data, positions)),
                'point attributes',
            )
            self._check(
                self.dvz.dvz_visual_set_visible(self.visual, self._visible), 'point visibility'
            )
            if created:
                self._check(
                    self.dvz.dvz_panel_add_visual(self.panel, self.visual, None), 'point attach'
                )
        except Exception as error:
            if created:
                if self.visual:
                    self.dvz.dvz_visual_destroy(self.visual)
                self.visual = None
            else:
                try:
                    if previous is not None and len(previous):
                        self._check(
                            self.dvz.dvz_visual_set_data_many(
                                self.visual, self._attributes(previous, old_positions)
                            ),
                            'point rollback',
                        )
                    self._check(
                        self.dvz.dvz_visual_set_visible(
                            self.visual, self._visible and self._has_data()
                        ),
                        'point visibility rollback',
                    )
                except Exception:
                    self.close()
                    raise RuntimeError('point rollback failed; component closed') from error
            raise
        self.data, self._display_positions = data, positions

    def update_colors(self, colors):
        """Replace colors while preserving world positions and sizes."""
        self._require_open()
        colors = rgba_array(colors, (len(self.data),))
        if len(self.data):
            self._check(self.dvz.dvz_visual_set_data(self.visual, 'color', colors), 'point colors')
        self._replace_attribute('colors', colors)

    def update_sizes(self, sizes_px):
        """Replace pixel diameters while preserving world positions and colors."""
        self._require_open()
        sizes = np.asarray(sizes_px, dtype=np.float32)
        if not np.isfinite(sizes).all() or np.any(sizes <= 0):
            raise ValueError('point sizes must be finite and positive')
        if sizes.ndim == 0:
            sizes = np.full(len(self.data), sizes, np.float32)
        if sizes.shape != (len(self.data),):
            raise ValueError('point sizes must have shape (n,) or be scalar')
        sizes = owned(sizes, np.float32)
        if len(self.data):
            self._check(
                self.dvz.dvz_visual_set_data(self.visual, 'diameter_px', sizes), 'point sizes'
            )
        self._replace_attribute('sizes_px', sizes)

    def _replace_attribute(self, name, value):
        # Existing arrays are already owned and immutable. Share them internally
        # instead of copying dense geometry on each color-only animation frame.
        updated = object.__new__(PointCollection)
        for field_name in ('positions_um', 'colors', 'sizes_px'):
            object.__setattr__(
                updated,
                field_name,
                value if field_name == name else getattr(self.data, field_name),
            )
        self.data = updated

    def close(self):
        """Release this visual's resources without destroying the caller's scene."""
        super().close()
        self._display_positions = None
