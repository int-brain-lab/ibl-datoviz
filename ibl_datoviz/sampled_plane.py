"""Owned sampled rectangles with overlay and physical textured-mesh adapters."""

import ctypes
from dataclasses import dataclass

import numpy as np

from .component import ComponentCapabilities, ComponentVisual, owned, rgba_array

UV = owned([[0, 0], [0, 1], [1, 0], [1, 1]], np.float32)
_INDICES = owned([0, 2, 1, 2, 3, 1], np.uint32)
_COLORS = owned(np.full((4, 4), 255), np.uint8)
_PHYSICAL_ALPHA_MODES = ('opaque', 'blended', 'wboit', 'mask')


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
    """Attach a sampled rectangle to a borrowed native panel.

    The default blended image overlay ignores 3D depth. Explicit physical depth
    uses an unlit textured mesh: opaque/masked fragments write depth, while
    blended/WBOIT fragments test depth without writing it. Mask cutoff uses the
    sampled effective alpha; nearest sampling preserves discrete label pixels.
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
        alpha_cutoff=0.5,
    ):
        if depth_policy not in ('overlay', 'physical'):
            raise ValueError('sampled-plane 3D depth policy must be overlay or physical')
        if depth_policy == 'overlay' and alpha_mode != 'blended':
            raise ValueError(
                'sampled planes support blended overlay alpha only; WBOIT/mask unavailable'
            )
        if depth_policy == 'physical' and alpha_mode not in _PHYSICAL_ALPHA_MODES:
            raise ValueError('physical plane alpha must be opaque, blended, wboit, or mask')
        if alpha_mode == 'mask':
            try:
                alpha_cutoff = float(alpha_cutoff)
            except (TypeError, ValueError) as error:
                raise ValueError('alpha cutoff must be finite and in [0, 1]') from error
            if not np.isfinite(alpha_cutoff) or not 0 <= alpha_cutoff <= 1:
                raise ValueError('alpha cutoff must be finite and in [0, 1]')
        super().__init__(dvz, scene, panel, transform)
        self.alpha_mode, self.depth_policy = alpha_mode, depth_policy
        self.alpha_cutoff = alpha_cutoff
        physical = depth_policy == 'physical'
        self.capabilities = ComponentCapabilities(
            _PHYSICAL_ALPHA_MODES if physical else ('blended',),
            physical,
            physical and alpha_mode in ('opaque', 'mask'),
            order_independent=physical and alpha_mode == 'wboit',
            sampled_plane_3d=physical,
        )
        self.field = None
        self._index_buffer = None
        self._display_corners = None
        self._display_geometry = None
        try:
            self.replace(data)
        except Exception:
            self.close()
            raise

    def _sampling(self, data):
        if self.depth_policy == 'physical':
            sampling = self.dvz.dvz_field_sampling_desc()
            mode = getattr(self.dvz, f'DVZ_FIELD_FILTER_{data.sampling.upper()}')
            sampling.min_filter = sampling.mag_filter = mode
            self._check(
                self.dvz.dvz_visual_set_field_sampling(
                    self.visual, b'texture', ctypes.byref(sampling)
                ),
                'plane sampling',
            )
            return
        mode = getattr(self.dvz, f'DVZ_IMAGE_SAMPLING_{data.sampling.upper()}')
        self._check(self.dvz.dvz_image_set_sampling(self.visual, mode), 'plane sampling')

    def _create_visual(self):
        if self.depth_policy == 'physical':
            self.visual = self._required(self.dvz.dvz_mesh(self.scene, 0), 'plane mesh')
            desc = self.dvz.dvz_scene_buffer_desc()
            desc.usage = self.dvz.DVZ_SCENE_BUFFER_USAGE_INDEX
            desc.stride = _INDICES.itemsize
            self._index_buffer = self._required(
                self.dvz.dvz_scene_buffer(self.scene, ctypes.byref(desc)), 'plane index buffer'
            )
            self._check(
                self.dvz.dvz_scene_buffer_set_data(self._index_buffer, _INDICES), 'plane indices'
            )
            self._check(
                self.dvz.dvz_visual_set_buffer(self.visual, b'index', self._index_buffer),
                'plane index binding',
            )
            material = self.dvz.dvz_material_desc()
            material.model = self.dvz.DVZ_MATERIAL_MODEL_UNLIT
            material.alpha_mode = getattr(self.dvz, f'DVZ_ALPHA_{self.alpha_mode.upper()}')
            material.opacity = 1.0
            self._check(
                self.dvz.dvz_visual_set_material(self.visual, ctypes.byref(material)),
                'plane material',
            )
            self._check(
                self.dvz.dvz_visual_set_depth_test(self.visual, True), 'plane physical depth'
            )
            if self.alpha_mode == 'mask':
                self._check(
                    self.dvz.dvz_visual_set_alpha_cutoff(self.visual, self.alpha_cutoff),
                    'plane alpha cutoff',
                )
            return
        self.visual = self._required(self.dvz.dvz_image(self.scene, 0), 'image visual')
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.visual, self.dvz.DVZ_ALPHA_BLENDED),
            'plane alpha',
        )
        self._check(self.dvz.dvz_visual_set_depth_test(self.visual, False), 'plane overlay')

    def _geometry(self, corners):
        geometry = {'position': corners, 'texcoords': UV}
        if self.depth_policy == 'physical':
            points = corners.astype(np.float64)
            normal = np.cross(points[2] - points[0], points[1] - points[0])
            length = np.linalg.norm(normal)
            other = np.cross(points[3] - points[2], points[1] - points[2])
            extent = np.max(np.linalg.norm(points - points[0], axis=1))
            if (
                length == 0
                or np.dot(normal, other) <= 0
                or abs(np.dot(points[3] - points[0], normal)) > extent * length * 1e-5
            ):
                raise ValueError('display transform must preserve a non-degenerate planar plane')
            geometry['normal'] = owned(np.tile(normal / length, (4, 1)), np.float32)
            geometry['color'] = _COLORS
        return geometry

    def _field_slot(self):
        return b'texture' if self.depth_policy == 'physical' else b'field'

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
            self._upload_field(field, pixels)
        except Exception:
            self.dvz.dvz_sampled_field_destroy(field)
            raise
        return field

    def _upload_field(self, field, pixels):
        view = self.dvz.dvz_field_data_view()
        view.data = ctypes.c_void_p(pixels.ctypes.data)
        view.bytes_per_row, view.rows_per_image = pixels.strides[0], 0
        self._check(
            self.dvz.dvz_sampled_field_set_data(field, ctypes.byref(view)), 'plane field upload'
        )

    def _update_field(self, field, pixels):
        # Facade returns the field handle, raising on failed native status.
        self._required(
            self.dvz.dvz_sampled_field_update_from_array(field, pixels), 'plane pixel update'
        )

    def _restore(self, previous, geometry, field, new_field, pixels_updated, visible):
        self._check(
            self.dvz.dvz_visual_set_data_many(self.visual, geometry),
            'plane geometry rollback',
        )
        if new_field:
            self._check(
                self.dvz.dvz_visual_set_field(self.visual, self._field_slot(), field),
                'plane field rollback',
            )
        if pixels_updated:
            self._upload_field(field, previous.rgba)
        self._sampling(previous)
        self._check(
            self.dvz.dvz_visual_set_visible(self.visual, visible), 'plane visibility rollback'
        )

    def _recover(self, created, snapshot, error):
        if created:
            if self.visual:
                self.dvz.dvz_visual_destroy(self.visual)
            self.visual = None
            if self._index_buffer:
                self.dvz.dvz_scene_buffer_destroy(self._index_buffer)
            self._index_buffer = None
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
        geometry = self._geometry(corners)
        previous = getattr(self, '_uploaded_data', None)
        old_geometry, old_field = self._display_geometry, self.field
        created = not self.visual
        new_field = None
        pixels_updated = False
        succeeded = False
        prior_visible = self._visible and self._has_data()
        try:
            if created:
                self._create_visual()
            self._check(
                self.dvz.dvz_visual_set_data_many(self.visual, geometry),
                'plane geometry',
            )
            if previous is None or previous.rgba.shape != data.rgba.shape:
                new_field = self._create_field(data.rgba)
                self._check(
                    self.dvz.dvz_visual_set_field(self.visual, self._field_slot(), new_field),
                    'plane field bind',
                )
            elif not np.array_equal(previous.rgba, data.rgba):
                # A failed upload may have mutated native pixels before reporting
                # failure; include it in the rollback snapshot before calling.
                pixels_updated = True
                self._update_field(old_field, data.rgba)
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
                (previous, old_geometry, old_field, new_field, pixels_updated, prior_visible),
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
        self._display_geometry = geometry

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
        if self._index_buffer:
            self.dvz.dvz_scene_buffer_destroy(self._index_buffer)
        if self.field:
            self.dvz.dvz_sampled_field_destroy(self.field)
        self.field = self._index_buffer = self._display_corners = self._display_geometry = None
        self._uploaded_data = None
