#!/usr/bin/env python3
"""Review linked Allen 50 um slices and anatomy in a persistent four-panel layout.

The physical plane uses the same verified 50 um source and affine coordinates as
the linked slices. It is optional and starts off; volume context and the physical
plane are reviewed separately because their transparency composition is limited.
"""

from __future__ import annotations

import argparse
import ctypes
from contextlib import suppress
from pathlib import Path

import numpy as np

from examples.review_common import (
    ReviewControls,
    add_review_arguments,
    finish_review,
    load_review_slice,
)
from ibl_anatomy import bundled_asset_set, open_volume_pack, verify_materialized_asset_set
from ibl_datoviz import AtlasCursor, AtlasMesh, LinkedAtlasNavigator, SampledPlaneVisual

PRESETS = ('anatomy', 'labels', 'volume-context', 'physical-slice')
AXES = ('ap', 'ml', 'dv')
PLANE_MODES = ('wboit', 'mask')
PLANE_LAYERS = ('anatomy', 'annotation')


class LinkedAtlasReview(LinkedAtlasNavigator):
    """Keep the linked navigator's panels and camera while reviewing its layers."""

    def __init__(self, *args, preset='anatomy', **kwargs):
        """Allocate the normal volume once and leave physical-plane rendering off."""
        if preset not in PRESETS:
            raise ValueError(f'unknown review preset: {preset}')
        self.physical_plane = None
        self.review_controls = None
        self.plane_axis = 'ap'
        self.plane_mode = 'wboit'
        self.plane_layer = 'anatomy'
        self.plane_visible = False
        self.plane_opacity = 0.72
        self.plane_cutoff = 0.5
        self._plane_revision = None
        self._preset_control = ctypes.c_int(PRESETS.index(preset))
        self._plane_visible_control = ctypes.c_bool(False)
        self._plane_axis_control = ctypes.c_int(0)
        self._plane_mode_control = ctypes.c_int(0)
        self._plane_layer_control = ctypes.c_int(0)
        self._plane_opacity_control = ctypes.c_float(self.plane_opacity)
        self._plane_cutoff_control = ctypes.c_float(self.plane_cutoff)
        self._review_error = None
        kwargs.setdefault('width', 1400)
        kwargs.setdefault('height', 1000)
        kwargs.setdefault('surface_opacity', 0.24)
        kwargs['render_volume'] = True
        kwargs['volume_opacity'] = 0.0
        super().__init__(*args, **kwargs)
        try:
            self.review_controls = ReviewControls(self)
            self.apply_preset(preset)
        except Exception:
            self.close()
            raise

    def _plane_data(self):
        return load_review_slice(
            self.slice_composer,
            self.plane_axis,
            self.cursor.as_index()[AXES.index(self.plane_axis)],
            self.mapping,
            layer=self.plane_layer,
            opacity=self.plane_opacity,
        )

    def _sync_physical_plane(self):
        if not self.plane_visible:
            return
        revision = (
            self.plane_axis,
            self.cursor.as_index()[AXES.index(self.plane_axis)],
            self.mapping,
            self.plane_layer,
            self.plane_opacity,
            self.plane_mode,
            self.plane_cutoff,
        )
        if revision == self._plane_revision:
            return
        data = self._plane_data()
        adapter = self.physical_plane
        if (
            adapter is None
            or adapter.alpha_mode != self.plane_mode
            or adapter.alpha_cutoff != self.plane_cutoff
        ):
            replacement = SampledPlaneVisual(
                self.dvz,
                self.scene,
                self.panel,
                data,
                transform=self.mesh_data.normalize_points,
                depth_policy='physical',
                alpha_mode=self.plane_mode,
                alpha_cutoff=self.plane_cutoff,
            )
            self.physical_plane = replacement
            if adapter is not None:
                adapter.close()
        else:
            adapter.replace(data)
        self._plane_revision = revision

    def set_physical_plane(self, visible):
        """Show an affine-positioned plane, keeping the native volume allocated."""
        self._require_open()
        previous = self.plane_visible
        previous_volume_opacity = self.volume_opacity
        self.plane_visible = bool(visible)
        try:
            if visible:
                super().set_volume_opacity(0.0)
                self._sync_physical_plane()
            if self.physical_plane is not None:
                self.physical_plane.set_visible(visible)
        except Exception:
            self.plane_visible = previous
            self._plane_visible_control.value = previous
            super().set_volume_opacity(previous_volume_opacity)
            raise
        self._plane_visible_control.value = self.plane_visible

    def configure_physical_plane(
        self, *, axis=None, mode=None, layer=None, opacity=None, cutoff=None
    ):
        """Update the retained plane and restore its configuration on failure."""
        self._require_open()
        candidate = {
            'plane_axis': self.plane_axis if axis is None else axis,
            'plane_mode': self.plane_mode if mode is None else mode,
            'plane_layer': self.plane_layer if layer is None else layer,
            'plane_opacity': self.plane_opacity if opacity is None else float(opacity),
            'plane_cutoff': self.plane_cutoff if cutoff is None else float(cutoff),
        }
        for attribute, choices in (
            ('plane_axis', AXES),
            ('plane_mode', PLANE_MODES),
            ('plane_layer', PLANE_LAYERS),
        ):
            if candidate[attribute] not in choices:
                raise ValueError(f'{attribute} must be one of {choices}')
        for attribute in ('plane_opacity', 'plane_cutoff'):
            if not np.isfinite(candidate[attribute]) or not 0 <= candidate[attribute] <= 1:
                raise ValueError(f'{attribute} must be finite and in [0, 1]')
        previous = {attribute: getattr(self, attribute) for attribute in candidate}
        try:
            for attribute, value in candidate.items():
                setattr(self, attribute, value)
            self._sync_physical_plane()
        except Exception:
            for attribute, value in previous.items():
                setattr(self, attribute, value)
            raise
        finally:
            self._plane_axis_control.value = AXES.index(self.plane_axis)
            self._plane_mode_control.value = PLANE_MODES.index(self.plane_mode)
            self._plane_layer_control.value = PLANE_LAYERS.index(self.plane_layer)
            self._plane_opacity_control.value = self.plane_opacity
            self._plane_cutoff_control.value = self.plane_cutoff

    def set_volume_opacity(self, opacity):
        """Use native volume context independently of the physical-plane route."""
        super().set_volume_opacity(opacity)
        if opacity > 0 and self.plane_visible:
            self.set_physical_plane(False)

    def set_cursor(self, cursor, *, select_region=False):
        """Move all linked slices and the optional physical plane together."""
        super().set_cursor(cursor, select_region=select_region)
        self._sync_navigation_plane()

    def set_mapping(self, mapping, palette=None):
        """Refresh the physical annotation texture after a mapping change."""
        super().set_mapping(mapping, palette=palette)
        self._sync_navigation_plane()

    def _sync_navigation_plane(self):
        try:
            self._sync_physical_plane()
        except Exception as error:
            try:
                self.set_physical_plane(False)
            except Exception:
                self.close()
                raise RuntimeError('physical-plane hide failed; review closed') from error
            self._review_error = f'Physical plane hidden after update failure: {error}'
            raise

    def apply_preset(self, preset):
        """Change review layers without replacing panels, views or cameras."""
        if preset not in PRESETS:
            raise ValueError(f'unknown review preset: {preset}')
        self.set_physical_plane(False)
        self.set_volume_opacity(0.12 if preset == 'volume-context' else 0.0)
        self.set_slice_layers(
            anatomy=preset != 'labels',
            annotations=preset != 'anatomy',
            boundaries=preset != 'anatomy',
        )
        if preset == 'physical-slice':
            self.set_physical_plane(True)
        self._preset_control.value = PRESETS.index(preset)

    def reset_review(self):
        """Restore shared region controls, the centre cursor and anatomy preset."""
        self.set_physical_plane(False)
        self.review_controls.reset()
        self.plane_axis, self.plane_mode, self.plane_layer = 'ap', 'wboit', 'anatomy'
        self.plane_opacity, self.plane_cutoff = 0.72, 0.5
        for control in (
            self._plane_axis_control,
            self._plane_mode_control,
            self._plane_layer_control,
        ):
            control.value = 0
        self._plane_opacity_control.value = self.plane_opacity
        self._plane_cutoff_control.value = self.plane_cutoff
        self.set_cursor(AtlasCursor.centre(self.slice_source))
        self.apply_preset('anatomy')

    def _combo(self, gui, label, control, items):
        encoded = (ctypes.c_char_p * len(items))(*(item.encode() for item in items))
        return self.dvz.dvz_gui_combo(gui, label, ctypes.byref(control), encoded, len(items))

    def _draw_review_gui(self, gui):
        self.dvz.dvz_gui_separator_text(gui, b'Linked review')
        if self._combo(gui, b'Preset', self._preset_control, PRESETS):
            self.apply_preset(PRESETS[self._preset_control.value])
            self._review_error = None
        if self.dvz.dvz_gui_button(gui, b'Reset linked review'):
            self.reset_review()
            self._review_error = None
        self.review_controls.draw(gui)
        if not self.dvz.dvz_gui_collapsing_header(gui, b'Physical slice in 3-D', 0):
            return
        self.dvz.dvz_gui_text(gui, b'Verified 50 um slices; independent of volume context')
        if self.dvz.dvz_gui_checkbox(
            gui, b'Show physical plane', ctypes.byref(self._plane_visible_control)
        ):
            self.set_physical_plane(self._plane_visible_control.value)
            self._review_error = None
        for label, attribute, control, items in (
            (b'Plane axis', 'axis', self._plane_axis_control, AXES),
            (b'Plane content', 'layer', self._plane_layer_control, PLANE_LAYERS),
            (b'Plane alpha mode', 'mode', self._plane_mode_control, PLANE_MODES),
        ):
            if self._combo(gui, label, control, items):
                self.configure_physical_plane(**{attribute: items[control.value]})
                self._review_error = None
        if self.dvz.dvz_gui_slider_float(
            gui, b'Plane opacity', ctypes.byref(self._plane_opacity_control), 0.0, 1.0
        ):
            self.configure_physical_plane(opacity=self._plane_opacity_control.value)
            self._review_error = None
        if self.plane_mode == 'mask' and self.dvz.dvz_gui_slider_float(
            gui, b'Alpha cutoff', ctypes.byref(self._plane_cutoff_control), 0.0, 1.0
        ):
            self.configure_physical_plane(cutoff=self._plane_cutoff_control.value)
            self._review_error = None
        self.dvz.dvz_gui_text(gui, b'WBOIT blends; mask keeps effective alpha >= cutoff')

    def _draw_extra_gui(self, gui):
        try:
            super()._draw_extra_gui(gui)
            if self.review_controls is not None:
                self._draw_review_gui(gui)
        except Exception as error:
            self._review_error = str(error)
        if self._review_error is not None:
            self.dvz.dvz_gui_text(gui, f'Review update failed: {self._review_error}'.encode())

    def close(self):
        """Release the borrowed-scene plane before workers and the native scene."""
        if getattr(self, 'physical_plane', None) is not None:
            self.physical_plane.close()
            self.physical_plane = None
        super().close()

    def __del__(self):
        """Keep the borrowed-scene cleanup order during finalization too."""
        with suppress(Exception):
            self.close()


def main() -> int:
    """Open the pinned D070 and Allen 50 um sources for linked review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='verified D070 asset-set root')
    parser.add_argument('volume_root', type=Path, help='verified Allen 50 um volume pack')
    parser.add_argument('--preset', choices=PRESETS, default='anatomy')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    add_review_arguments(parser)
    args = parser.parse_args()
    assets = verify_materialized_asset_set(bundled_asset_set(), args.asset_root)
    volumes = open_volume_pack(args.volume_root).load_volumes()
    with LinkedAtlasReview(
        AtlasMesh.from_geometry(assets.geometry),
        volumes,
        preset=args.preset,
        mapping=args.mapping,
        width=args.width,
        height=args.height,
        ui_scale=args.ui_scale,
        enable_interaction=True,
    ) as viewer:
        finish_review(viewer, args, 'D070 linked atlas review')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
