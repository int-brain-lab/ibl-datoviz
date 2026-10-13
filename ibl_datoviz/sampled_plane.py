"""Owned sampled rectangles and honest native image-overlay adapters."""

import ctypes
from dataclasses import dataclass

import numpy as np

from .component import ComponentCapabilities, ComponentVisual, owned, rgba_array

UV = owned([[0, 0], [0, 1], [1, 0], [1, 1]], np.float32)


@dataclass(frozen=True)
class SampledPlane:
    """Atlas-world rectangle with RGBA pixels, ordered TL, BL, TR, BR.

    Image row zero corresponds to the top edge. Coordinates are micrometres;
    adapters apply a caller-provided display transform exactly once.
    """

    corners_um: np.ndarray
    rgba: np.ndarray
    sampling: str = 'nearest'

    def __post_init__(self):
        """Validate public construction and own every caller-supplied array."""
        corners = owned(self.corners_um, np.float32)
        if corners.shape != (4, 3) or not np.isfinite(corners).all():
            raise ValueError('plane corners must have finite shape (4, 3)')
        vertical = corners[1].astype(float) - corners[0]
        horizontal = corners[2].astype(float) - corners[0]
        height, width = np.linalg.norm(vertical), np.linalg.norm(horizontal)
        if min(height, width) <= 0:
            raise ValueError('plane rectangle must be non-degenerate')
        tolerance = max(height, width) * 1e-5
        if (
            np.linalg.norm(corners[3].astype(float) - corners[1] - horizontal) > tolerance
            or abs(np.dot(vertical, horizontal)) > height * width * 1e-5
        ):
            raise ValueError('plane corners must form a planar rectangle in TL, BL, TR, BR order')
        pixels = np.asarray(self.rgba)
        if pixels.ndim != 3 or min(pixels.shape[:2]) <= 0 or pixels.shape[2] != 4:
            raise ValueError('plane pixels must have non-empty shape (height, width, 4)')
        pixels = rgba_array(pixels, pixels.shape[:2])
        if self.sampling not in ('nearest', 'linear'):
            raise ValueError('sampling must be nearest or linear')
        object.__setattr__(self, 'corners_um', corners)
        object.__setattr__(self, 'rgba', pixels)

    @classmethod
    def from_arrays(cls, corners_um, rgba, *, sampling='nearest'):
        """Validate and own rectangle geometry and RGBA8 samples."""
        return cls(corners_um, rgba, sampling)


class SampledPlaneVisual(ComponentVisual):
    """Attach a data-positioned image overlay to a borrowed native panel.

    The current image shader has no 3D depth test/write or WBOIT route. Selecting
    overlay is an explicit rendering limitation, including for XYZ geometry.
    """

    def __init__(
        self,
        dvz,
        scene,
        panel,
        data,
        *,
        transform=None,
        alpha_mode='blended',
        depth_policy='overlay',
    ):
        if alpha_mode != 'blended':
            raise ValueError(
                'sampled planes support blended overlay alpha only; WBOIT/mask unavailable'
            )
        if depth_policy != 'overlay':
            raise ValueError(
                'sampled-plane 3D depth is unavailable; select explicit overlay policy'
            )
        super().__init__(dvz, scene, panel, transform)
        self.alpha_mode, self.depth_policy = alpha_mode, depth_policy
        self.capabilities = ComponentCapabilities(('blended',), False, False)
        self.field = None
        self._display_corners = None
        try:
            self.replace(data)
        except Exception:
            self.close()
            raise

    def _sampling(self, data):
        mode = getattr(self.dvz, f'DVZ_IMAGE_SAMPLING_{data.sampling.upper()}')
        self._check(self.dvz.dvz_image_set_sampling(self.visual, mode), 'plane sampling')

    def _create_visual(self):
        self.visual = self._required(self.dvz.dvz_image(self.scene, 0), 'image visual')
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.visual, self.dvz.DVZ_ALPHA_BLENDED),
            'plane alpha',
        )
        self._check(self.dvz.dvz_visual_set_depth_test(self.visual, False), 'plane overlay')

    def _create_field(self, pixels):
        # Obtain the handle before upload so a native upload failure can release
        # its allocation. The array convenience helper hides this failure handle.
        desc = self.dvz.dvz_sampled_field_desc()
        desc.dim = self.dvz.DVZ_FIELD_DIM_2D
        desc.format = self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM
        desc.semantic = self.dvz.DVZ_FIELD_SEMANTIC_COLOR
        desc.color_role = self.dvz.DVZ_COLOR_ROLE_SRGB_COLOR
        desc.height, desc.width, desc.depth = *pixels.shape[:2], 1
        field = self._required(
            self.dvz.dvz_sampled_field(self.scene, ctypes.byref(desc)), 'plane field'
        )
        try:
            view = self.dvz.dvz_field_data_view()
            view.data = ctypes.c_void_p(pixels.ctypes.data)
            view.bytes_per_row, view.rows_per_image = pixels.strides[0], 0
            self._check(
                self.dvz.dvz_sampled_field_set_data(field, ctypes.byref(view)),
                'plane field upload',
            )
        except Exception:
            self.dvz.dvz_sampled_field_destroy(field)
            raise
        return field

    def _update_field(self, field, pixels):
        # Facade returns the field handle, raising on failed native status.
        self._required(
            self.dvz.dvz_sampled_field_update_from_array(field, pixels), 'plane pixel update'
        )

    def _restore(self, previous, corners, field, new_field, pixels_updated, visible):
        self._check(
            self.dvz.dvz_visual_set_data_many(self.visual, {'position': corners, 'texcoords': UV}),
            'plane geometry rollback',
        )
        if new_field:
            self._check(
                self.dvz.dvz_visual_set_field(self.visual, b'field', field), 'plane field rollback'
            )
        if pixels_updated:
            self._update_field(field, previous.rgba)
        self._sampling(previous)
        self._check(
            self.dvz.dvz_visual_set_visible(self.visual, visible), 'plane visibility rollback'
        )

    def _recover(self, created, snapshot, error):
        if created:
            if self.visual:
                self.dvz.dvz_visual_destroy(self.visual)
            self.visual = None
            return
        try:
            self._restore(*snapshot)
        except Exception:
            self.close()
            raise RuntimeError('plane rollback failed; component closed') from error

    def replace(self, data):
        """Replace geometry/pixels, or hide the plane with None.

        Same-sized fields update in place. Changed extents bind a new field and
        destroy the old one after successful commit. Failures restore the prior
        snapshot; rollback failure closes only this component.
        """
        self._require_open()
        if data is not None and not isinstance(data, SampledPlane):
            raise TypeError('data must be a SampledPlane or None')
        if data is None:
            if self.visual:
                self._check(self.dvz.dvz_visual_set_visible(self.visual, False), 'empty plane')
            # Keep the upload snapshot for field rollback and extent comparisons.
            self.data = None
            return
        corners = self._positions(data.corners_um)
        previous = getattr(self, '_uploaded_data', None)
        old_corners, old_field = self._display_corners, self.field
        created = not self.visual
        new_field = None
        pixels_updated = False
        succeeded = False
        prior_visible = self._visible and self._has_data()
        try:
            if created:
                self._create_visual()
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    self.visual, {'position': corners, 'texcoords': UV}
                ),
                'plane geometry',
            )
            if previous is None or previous.rgba.shape != data.rgba.shape:
                new_field = self._create_field(data.rgba)
                self._check(
                    self.dvz.dvz_visual_set_field(self.visual, b'field', new_field),
                    'plane field bind',
                )
            elif not np.array_equal(previous.rgba, data.rgba):
                self._update_field(old_field, data.rgba)
                pixels_updated = True
            self._sampling(data)
            self._check(
                self.dvz.dvz_visual_set_visible(self.visual, self._visible), 'plane visibility'
            )
            if created:
                self._check(
                    self.dvz.dvz_panel_add_visual(self.panel, self.visual, None), 'plane attach'
                )
            succeeded = True
        except Exception as error:
            self._recover(
                created,
                (previous, old_corners, old_field, new_field, pixels_updated, prior_visible),
                error,
            )
            raise
        finally:
            if not succeeded and new_field is not None:
                self.dvz.dvz_sampled_field_destroy(new_field)
        if new_field is not None:
            self.field = new_field
            if old_field:
                self.dvz.dvz_sampled_field_destroy(old_field)
        self.data = self._uploaded_data = data
        self._display_corners = corners

    def update_pixels(self, rgba):
        """Replace pixels, including changed texture dimensions."""
        self._require_open()
        if self.data is None:
            raise RuntimeError('empty plane requires replace(data) before updating pixels')
        self.replace(
            SampledPlane.from_arrays(self.data.corners_um, rgba, sampling=self.data.sampling)
        )

    def update_corners(self, corners_um):
        """Move the rectangle while retaining the sampled field."""
        self._require_open()
        if self.data is None:
            raise RuntimeError('empty plane requires replace(data) before updating corners')
        self.replace(
            SampledPlane.from_arrays(corners_um, self.data.rgba, sampling=self.data.sampling)
        )

    def close(self):
        """Release this visual and sampled field before caller scene destruction."""
        if self._closed:
            return
        super().close()
        if self.field:
            self.dvz.dvz_sampled_field_destroy(self.field)
        self.field = self._display_corners = None
        self._uploaded_data = None
