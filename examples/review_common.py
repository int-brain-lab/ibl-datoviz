"""Shared controls and source-grounded slice preparation for the two review apps."""

from __future__ import annotations

import ctypes
from pathlib import Path

import numpy as np

from ibl_anatomy import open_volume_pack
from ibl_datoviz import SampledPlane
from ibl_datoviz.navigator import SLICE_DISPLAY_AXES, AtlasSliceComposer
from ibl_datoviz.surface_style import RegionStyle


def add_review_arguments(parser):
    """Add consistent review options without changing native discovery."""
    parser.add_argument('--frames', type=int, default=0, help='zero runs until closed')
    parser.add_argument('--ui-scale', type=float, default=1.0)
    parser.add_argument('--width', type=int, default=1400)
    parser.add_argument('--height', type=int, default=1000)
    parser.add_argument('--offscreen', type=Path, metavar='PNG')


def finish_review(viewer, args, title):
    """Use the caller-owned viewer's existing capture or interactive frame loop."""
    if args.frames < 0:
        raise ValueError('frames must be nonnegative')
    if args.offscreen:
        rgba = viewer.render_offscreen(args.offscreen)
        print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
    else:
        viewer.show(title=title, frame_count=args.frames)


def load_review_slice(source, axis, index=None, mapping='allen', *, layer='anatomy', opacity=1.0):
    """Prepare one physical rectangle using the same orientation as the linked slices.

    Corners follow pixel edges through the source affine; no fitted geometry,
    reorientation of scientific coordinates or resampling is introduced.
    """
    composer = source if isinstance(source, AtlasSliceComposer) else None
    if composer is not None:
        source = composer.volumes
    if isinstance(source, (str, Path)):
        source = open_volume_pack(source).load_volumes()
    if axis not in SLICE_DISPLAY_AXES or layer not in ('anatomy', 'annotation'):
        raise ValueError('slice axis/layer must be AP/ML/DV and anatomy/annotation')
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('plane opacity must be finite and in [0, 1]')
    grid = source.grid
    fixed = grid.array_axes.index(axis)
    if index is None:
        index = grid.shape[fixed] // 2
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
        raise ValueError('slice index must be an integer')
    if not 0 <= index < grid.shape[fixed]:
        raise ValueError('slice index is outside the source grid')
    if composer is None:
        composer = AtlasSliceComposer(source, mapping)
    elif composer.mapping != mapping:
        composer.set_mapping(mapping)
    anatomy, annotation = composer.compose_layers(axis, int(index), annotation_opacity=1.0)
    pixels = np.array(anatomy if layer == 'anatomy' else annotation, copy=True)
    pixels[..., 3] = np.rint(pixels[..., 3].astype(float) * opacity).astype(np.uint8)
    matrix = np.asarray(grid.index_to_world_um_matrix, dtype=float).reshape(4, 4)
    x_axis, y_axis = SLICE_DISPLAY_AXES[axis]

    def bounds(name):
        array_axis = grid.array_axes.index(name)
        world_axis = grid.world_axes.index(name)
        linear = matrix[:3, array_axis]
        if np.count_nonzero(np.abs(linear) > 1e-8) != 1 or linear[world_axis] == 0:
            raise ValueError('physical slices require the axis-aligned source grid')
        ends = (-0.5, grid.shape[array_axis] - 0.5)
        return ends if linear[world_axis] > 0 else ends[::-1]

    x0, x1 = bounds(x_axis)
    y0, y1 = bounds(y_axis)
    corners = np.zeros((4, 3), dtype=float)
    corners[:, fixed] = index
    corners[:, grid.array_axes.index(x_axis)] = (x0, x0, x1, x1)
    corners[:, grid.array_axes.index(y_axis)] = (y0, y1, y0, y1)
    return SampledPlane.from_arrays(grid.index_to_world(corners), pixels, sampling='nearest')


class ReviewControls:
    """Share anatomical style controls without changing the app's view structure."""

    def __init__(self, viewer):
        """Remember an explicit reset target and own only Python GUI input buffers."""
        self.viewer = viewer
        self.initial_mapping = viewer.mapping
        self.initial_camera = viewer.camera_angles
        self.initial_opacity = viewer.surface_opacity
        self.error = None
        self._region_key = None
        self._available_regions = {}
        self._region_opacity = ctypes.c_float(1)
        self._region_visible = ctypes.c_bool(True)
        self._region_color = (ctypes.c_float * 4)(1, 1, 1, 1)

    def reset(self):
        """Explicitly reset appearance and camera; ordinary layer edits never do so."""
        viewer = self.viewer
        viewer.set_mapping(self.initial_mapping)
        viewer.clear_selection()
        viewer.reset_surface_style()
        viewer.set_surface_visible(True)
        viewer.set_surface_opacity(self.initial_opacity)
        viewer.set_explode(0)
        viewer.set_camera_angles(self.initial_camera)
        self._region_key = None
        self.error = None

    def _attempt(self, callback, *args):
        try:
            callback(*args)
            self.error = None
        except (ValueError, RuntimeError) as error:
            self.error = str(error)
            self._region_key = None

    def draw(self, gui):
        """Draw stable control IDs and read state back from the authoritative model."""
        dvz = self.viewer.dvz
        if dvz.dvz_gui_collapsing_header(gui, b'Atlas appearance and region styles', 0):
            self._draw_styles(gui)
        if self.error:
            dvz.dvz_gui_text(gui, f'Change failed: {self.error}'.encode())

    def _draw_styles(self, gui):
        viewer, dvz = self.viewer, self.viewer.dvz
        dvz.dvz_gui_text(gui, b'3D surface styles; slice labels keep mapping colors.')
        opacity = ctypes.c_float(viewer.surface_opacity)
        if dvz.dvz_gui_slider_float(gui, b'Surface opacity', ctypes.byref(opacity), 0, 1):
            self._attempt(viewer.set_surface_opacity, opacity.value)
        for side in ('left', 'right'):
            value = ctypes.c_bool(viewer._surface_style.hemispheres[side])
            if dvz.dvz_gui_checkbox(
                gui, f'{side.title()} hemisphere'.encode(), ctypes.byref(value)
            ):
                self._attempt(viewer.set_hemisphere_visible, side, value.value)
        regions = viewer.selected_region_ids()
        if not regions:
            dvz.dvz_gui_text(gui, b'Select a surface or tree region to edit its style.')
            return
        region = regions[0]
        if viewer.mapping not in self._available_regions:
            self._available_regions[viewer.mapping] = set(
                np.unique(viewer.mesh_data.face_mapping_ids(viewer.mapping)).tolist()
            )
        if region not in self._available_regions[viewer.mapping]:
            dvz.dvz_gui_text(gui, b'The selected region has no displayed mesh faces.')
            return
        key = (viewer.mapping, region)
        if key != self._region_key:
            style = viewer._surface_style.regions.get(key, RegionStyle())
            color = style.color
            if color is None:
                color = (viewer.palette or {}).get(region, (120, 160, 220, 255))
            rgba = tuple(color) if len(color) == 4 else (*color, 255)
            self._region_color[:] = np.asarray(rgba, dtype=float) / 255
            self._region_opacity.value = style.opacity
            self._region_visible.value = style.visible
            self._region_key = key
        dvz.dvz_gui_text(gui, f'Editing signed region {region} (first selected)'.encode())
        if dvz.dvz_gui_checkbox(gui, b'Region visible', ctypes.byref(self._region_visible)):
            self._attempt(viewer.set_region_visible, region, bool(self._region_visible.value))
        if dvz.dvz_gui_slider_float(
            gui, b'Region opacity', ctypes.byref(self._region_opacity), 0, 1
        ):
            self._attempt(viewer.set_region_opacity, region, float(self._region_opacity.value))
        if dvz.dvz_gui_color_edit4(gui, b'Region RGBA', self._region_color, 0):
            color = np.rint(np.clip(self._region_color, 0, 1) * 255).astype(np.uint8)
            self._attempt(viewer.set_region_color, region, color)
        if dvz.dvz_gui_button(gui, b'Reset this region style'):
            self._attempt(viewer.reset_region_style, region)
            self._region_key = None
