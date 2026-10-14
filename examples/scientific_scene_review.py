#!/usr/bin/env python3
"""Review real atlas, probe, point and physical-plane layers in one fixed scene."""

from __future__ import annotations

import argparse
import ctypes
import textwrap
from contextlib import suppress
from pathlib import Path

import numpy as np

from examples.bwm_multiple_insertions import COLORS, DEFAULT_PATHS, WIDTHS, _load_paths
from examples.bwm_probe import FIXTURE, _load_fixture
from examples.review_common import (
    ReviewControls,
    add_review_arguments,
    finish_review,
    load_review_slice,
)
from ibl_datoviz import (
    AtlasViewer,
    PointCollection,
    PointCollectionVisual,
    SampledPlane,
    SampledPlaneVisual,
)
from ibl_datoviz.presentation import scalar_colors

PRESETS = ('atlas', 'single-probe', 'multiple-insertions', 'mixed')
PRESET_LABELS = ('Atlas surface', 'Single BWM probe', 'Multiple W39 insertions', 'Points + plane')
BWM_ID = 'bwm-probe'
POINT_COLOR = (70, 220, 250, 180)
MISSING_W39 = (
    'Multiple insertions unavailable. Prepare the pinned W39 channels.pqt with '
    'tools/build_w39_insertions.py --channels /path/to/channels.pqt '
    '--output build/w39-insertions, then restart this review.'
)


def firing_rate_range(sites):
    """Return the explicit finite-site 5th–95th percentile display range in Hz."""
    finite = sites.values[np.isfinite(sites.values)]
    if not len(finite):
        raise ValueError('BWM firing rates contain no finite values')
    low, high = (float(value) for value in np.quantile(finite, (0.05, 0.95)))
    if high <= low:
        raise ValueError('BWM 5th–95th percentile range must be increasing')
    return low, high


def point_colors(sites, value_range, *, mode='scalar', opacity=1.0):
    """Scale authored point alpha while preserving transparent missing scalar values."""
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('point opacity must be in [0, 1]')
    if mode == 'scalar':
        colors = scalar_colors(sites.values, value_range, 'sequential')
        colors[~np.isfinite(sites.values), 3] = 0
    elif mode == 'uniform':
        colors = np.tile(np.asarray(POINT_COLOR, dtype=np.uint8), (len(sites.values), 1))
    else:
        raise ValueError('point color mode must be uniform or scalar')
    colors[:, 3] = np.rint(colors[:, 3].astype(float) * opacity).astype(np.uint8)
    return colors


def point_payload(sites, value_range, *, mode='scalar', size_px=6.0, opacity=1.0):
    """Own real site coordinates and explicit WBOIT color/size encodings."""
    colors = point_colors(sites, value_range, mode=mode, opacity=opacity)
    return PointCollection.from_arrays(sites.positions_um, colors, sizes_px=size_px)


def optional_insertions(paths, provenance):
    """Disable absent optional W39 inputs; reject present inputs with invalid provenance."""
    paths, provenance = Path(paths), Path(provenance)
    if not paths.is_file() or not provenance.is_file():
        return [], MISSING_W39
    loaded, _metadata = _load_paths(paths, provenance)
    return loaded, ''


class ScientificSceneReview(AtlasViewer):
    """Keep one viewer and persistent GUI areas while changing scientific layers."""

    def __init__(self, mesh, **kwargs):
        self.review_controls = None
        self._show_scientific_data = ctypes.c_bool(False)
        self.review_points = self.review_plane = None
        self._review_error = ''
        self._tree_height = 260.0
        super().__init__(mesh, **kwargs)

    def configure_review(self, sites, plane, paths=(), *, unavailable_note=''):
        """Attach verified data once, borrowing this viewer's scene and atlas panel."""
        self.review_sites, self.base_plane = sites, plane
        self.value_range = firing_rate_range(sites)
        self.unavailable_note = unavailable_note
        self._paths = dict(paths)
        self._paths[BWM_ID] = sites.positions_um
        self._available_presets = tuple(
            name for name in PRESETS if name != 'multiple-insertions' or len(self._paths) > 1
        )
        self._initial_styles = {
            insertion_id: (COLORS[index % len(COLORS)], WIDTHS[index % len(WIDTHS)])
            for index, insertion_id in enumerate(self._paths)
        }
        self._insertion_styles = {
            key: {'visible': True, 'color': color, 'width': width}
            for key, (color, width) in self._initial_styles.items()
        }
        self.layers = {
            'atlas': True,
            'sites': False,
            'points': False,
            'plane': False,
            'insertions': False,
        }
        self.point_mode, self.point_size, self.point_opacity = 'scalar', 6.0, 0.7
        self.plane_mode, self.plane_opacity, self.plane_cutoff = 'wboit', 0.65, 0.5
        self.preset = 'atlas'
        self._active_insertions = (BWM_ID,)
        self._preset_control = ctypes.c_int(0)
        self._layer_controls = {name: ctypes.c_bool(value) for name, value in self.layers.items()}
        self._point_mode_control = ctypes.c_int(1)
        self._point_size_control = ctypes.c_float(self.point_size)
        self._point_opacity_control = ctypes.c_float(self.point_opacity)
        self._plane_mode_control = ctypes.c_int(0)
        self._plane_opacity_control = ctypes.c_float(self.plane_opacity)
        self._plane_cutoff_control = ctypes.c_float(self.plane_cutoff)
        self.set_probe_data(
            sites, value_range=self.value_range, radius_um=85, color_scheme='sequential'
        )
        self.review_points = PointCollectionVisual(
            self.dvz,
            self.scene,
            self.panel,
            point_payload(
                sites,
                self.value_range,
                mode=self.point_mode,
                size_px=self.point_size,
                opacity=self.point_opacity,
            ),
            transform=self.mesh_data.normalize_points,
            alpha_mode='wboit',
        )
        self.review_plane = self._new_plane(self.plane_mode, self.plane_cutoff)
        for insertion_id, points in self._paths.items():
            color, width = self._initial_styles[insertion_id]
            self.set_insertion(insertion_id, points, color=color, width_px=width)
        self.review_controls = ReviewControls(self)
        self.apply_preset('atlas')

    def _plane_data(self, opacity=None):
        pixels = self.base_plane.rgba.copy()
        opacity = self.plane_opacity if opacity is None else opacity
        pixels[..., 3] = np.rint(pixels[..., 3].astype(float) * opacity).astype(np.uint8)
        return SampledPlane.from_arrays(
            self.base_plane.corners_um, pixels, sampling=self.base_plane.sampling
        )

    def _new_plane(self, mode, cutoff):
        return SampledPlaneVisual(
            self.dvz,
            self.scene,
            self.panel,
            self._plane_data(),
            transform=self.mesh_data.normalize_points,
            depth_policy='physical',
            alpha_mode=mode,
            alpha_cutoff=cutoff,
        )

    def _sync_insertions(self):
        for insertion_id, style in self._insertion_styles.items():
            self.set_insertion_visible(
                insertion_id,
                bool(
                    self.layers['insertions']
                    and style['visible']
                    and insertion_id in self._active_insertions
                ),
            )

    def set_layer_visible(self, layer, visible):
        """Change a retained layer without changing camera or authored region styles."""
        if layer not in self.layers:
            raise ValueError(f'unknown scientific layer: {layer}')
        visible = bool(visible)
        if layer == 'atlas':
            self.set_surface_visible(visible)
        elif layer == 'sites':
            self._check(
                self.dvz.dvz_visual_set_visible(self.probe_sites, visible),
                'analytic site visibility',
            )
        elif layer == 'points':
            self.review_points.set_visible(visible)
        elif layer == 'plane':
            self.review_plane.set_visible(visible)
        old = self.layers[layer]
        self.layers[layer] = visible
        try:
            if layer == 'insertions':
                self._sync_insertions()
        except Exception:
            self.layers[layer] = old
            self._sync_insertions()
            raise
        self._layer_controls[layer].value = visible

    def apply_preset(self, preset):
        """Switch layer visibility in the same scene; never reset the current camera."""
        if preset not in PRESETS:
            raise ValueError(f'unknown scene preset: {preset}')
        if preset == 'multiple-insertions' and len(self._paths) == 1:
            raise ValueError(self.unavailable_note or MISSING_W39)
        previous_layers = self.layers.copy()
        previous_active = self._active_insertions
        self._active_insertions = (
            tuple(key for key in self._paths if key != BWM_ID)
            if preset == 'multiple-insertions'
            else (BWM_ID,)
        )
        enabled = {'atlas'}
        if preset == 'single-probe':
            enabled.update(('points', 'insertions'))
        elif preset == 'multiple-insertions':
            enabled.add('insertions')
        elif preset == 'mixed':
            enabled.update(('points', 'plane', 'insertions'))
        try:
            for layer in self.layers:
                self.set_layer_visible(layer, layer in enabled)
        except Exception as error:
            self._active_insertions = previous_active
            try:
                for layer, visible in previous_layers.items():
                    self.set_layer_visible(layer, visible)
            except Exception:
                self.close()
                raise RuntimeError('preset rollback failed; review closed') from error
            raise
        self.preset = preset
        self._preset_control.value = self._available_presets.index(preset)

    def set_point_mode(self, mode):
        """Update only point colors, retaining geometry, component and camera."""
        colors = point_colors(
            self.review_sites, self.value_range, mode=mode, opacity=self.point_opacity
        )
        self.review_points.update_colors(colors)
        self.point_mode = mode
        self._point_mode_control.value = ('uniform', 'scalar').index(mode)

    def set_point_size(self, size_px):
        """Change WBOIT point diameter in pixels without moving real sites."""
        self.review_points.update_sizes(size_px)
        self.point_size = float(size_px)
        self._point_size_control.value = self.point_size

    def set_point_opacity(self, opacity):
        """Update colors only, retaining camera, table, positions and point sizes."""
        colors = point_colors(
            self.review_sites, self.value_range, mode=self.point_mode, opacity=opacity
        )
        self.review_points.update_colors(colors)
        self.point_opacity = float(opacity)
        self._point_opacity_control.value = self.point_opacity

    def set_plane_opacity(self, opacity):
        """Multiply source alpha without modifying source pixels or plane corners."""
        if not np.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('plane opacity must be in [0, 1]')
        self.review_plane.replace(self._plane_data(opacity))
        self.plane_opacity = float(opacity)
        self._plane_opacity_control.value = self.plane_opacity

    def set_plane_mode(self, mode, *, cutoff=None):
        """Replace only the plane adapter after successful physical-mode creation."""
        if mode not in ('wboit', 'mask'):
            raise ValueError('review planes support wboit or mask')
        cutoff = self.plane_cutoff if cutoff is None else float(cutoff)
        if not np.isfinite(cutoff) or not 0 <= cutoff <= 1:
            raise ValueError('mask cutoff must be in [0, 1]')
        if mode == self.plane_mode and cutoff == self.plane_cutoff:
            return
        replacement = self._new_plane(mode, cutoff)
        try:
            replacement.set_visible(self.layers['plane'])
        except Exception:
            replacement.close()
            raise
        old, self.review_plane = self.review_plane, replacement
        old.close()
        self.plane_mode, self.plane_cutoff = mode, cutoff
        self._plane_mode_control.value = ('wboit', 'mask').index(mode)
        self._plane_cutoff_control.value = cutoff

    def style_insertion(self, insertion_id, *, visible=None, color=None, width=None):
        """Style one stable path identity independently of the other paths."""
        style = self._insertion_styles[insertion_id]
        if color is not None:
            self.set_insertion_color(insertion_id, color)
            style['color'] = tuple(color)
        if width is not None:
            self.set_insertion_width(insertion_id, width)
            style['width'] = float(width)
        if visible is not None:
            effective = bool(
                visible and self.layers['insertions'] and insertion_id in self._active_insertions
            )
            self.set_insertion_visible(insertion_id, effective)
            style['visible'] = bool(visible)

    def reset_review(self):
        """Explicitly restore initial controls, camera, layers and scientific styles."""
        self.review_controls.reset()
        self.set_point_mode('scalar')
        self.set_point_size(6.0)
        self.set_point_opacity(0.7)
        self.set_plane_opacity(0.65)
        self.set_plane_mode('wboit', cutoff=0.5)
        for insertion_id, (color, width) in self._initial_styles.items():
            self.style_insertion(insertion_id, visible=True, color=color, width=width)
        self.apply_preset('atlas')
        self._review_error = ''

    def _action(self, action, *args, **kwargs):
        try:
            action(*args, **kwargs)
        except (ValueError, RuntimeError) as error:
            self._review_error = str(error)
            return False
        self._review_error = ''
        return True

    def _text(self, gui, message, *, width=43):
        for line in textwrap.wrap(message, width=width):
            self.dvz.dvz_gui_text(gui, line.encode())

    def _combo(self, gui, label, control, choices):
        items = (ctypes.c_char_p * len(choices))(*(item.encode() for item in choices))
        return self.dvz.dvz_gui_combo(
            gui, label.encode(), ctypes.byref(control), items, len(choices)
        )

    def _draw_extra_gui(self, gui):
        if self.review_controls is None:
            return
        self.dvz.dvz_gui_checkbox(
            gui, b'Show scientific data', ctypes.byref(self._show_scientific_data)
        )
        self.dvz.dvz_gui_separator_text(gui, b'Scientific scene')
        labels = tuple(PRESET_LABELS[PRESETS.index(name)] for name in self._available_presets)
        if self._combo(gui, 'Preset', self._preset_control, labels) and not self._action(
            self.apply_preset, self._available_presets[self._preset_control.value]
        ):
            self._preset_control.value = self._available_presets.index(self.preset)
        if self.unavailable_note:
            self._text(gui, self.unavailable_note)
        if self.dvz.dvz_gui_button(gui, b'Reset scientific scene'):
            self._action(self.reset_review)
        if self._review_error:
            self._text(gui, f'Change failed: {self._review_error}')
        if self.dvz.dvz_gui_collapsing_header(gui, b'Scientific layers', 0):
            for layer, label in (
                ('atlas', 'Atlas surface'),
                ('sites', 'Analytic sites: FR colors'),
                ('points', 'WBOIT recording-site points'),
                ('plane', 'Physical anatomical plane'),
                ('insertions', 'Insertion paths'),
            ):
                control = self._layer_controls[layer]
                if self.dvz.dvz_gui_checkbox(gui, label.encode(), ctypes.byref(control)):
                    self._action(self.set_layer_visible, layer, control.value)
                    control.value = self.layers[layer]
        if self.dvz.dvz_gui_collapsing_header(gui, b'Point encoding', 0):
            self._draw_point_gui(gui)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Physical plane', 0):
            self._draw_plane_gui(gui)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Independent insertion styles', 0):
            self._draw_insertion_gui(gui)
        self.review_controls.draw(gui)

    def _draw_point_gui(self, gui):
        self._text(
            gui,
            'These controls affect WBOIT recording-site points. '
            'Analytic sites keep their independent firing-rate colors.',
        )
        if self._combo(
            gui,
            'Color mode',
            self._point_mode_control,
            ('Uniform site geometry', 'Mean firing rate (Hz)'),
        ):
            self._action(
                self.set_point_mode, ('uniform', 'scalar')[self._point_mode_control.value]
            )
            self._point_mode_control.value = ('uniform', 'scalar').index(self.point_mode)
        if self.dvz.dvz_gui_slider_float(
            gui, b'Diameter (px)', ctypes.byref(self._point_size_control), 1.0, 18.0
        ):
            self._action(self.set_point_size, self._point_size_control.value)
            self._point_size_control.value = self.point_size
        if self.dvz.dvz_gui_slider_float(
            gui, b'Point opacity', ctypes.byref(self._point_opacity_control), 0.0, 1.0
        ):
            self._action(self.set_point_opacity, self._point_opacity_control.value)
            self._point_opacity_control.value = self.point_opacity

    def _draw_plane_gui(self, gui):
        if self._combo(gui, 'Composition', self._plane_mode_control, ('WBOIT', 'Mask')):
            self._action(self.set_plane_mode, ('wboit', 'mask')[self._plane_mode_control.value])
            self._plane_mode_control.value = ('wboit', 'mask').index(self.plane_mode)
        if self.dvz.dvz_gui_slider_float(
            gui, b'Plane opacity', ctypes.byref(self._plane_opacity_control), 0.0, 1.0
        ):
            self._action(self.set_plane_opacity, self._plane_opacity_control.value)
            self._plane_opacity_control.value = self.plane_opacity
        if self.plane_mode == 'mask' and self.dvz.dvz_gui_slider_float(
            gui, b'Inclusive alpha cutoff', ctypes.byref(self._plane_cutoff_control), 0.0, 1.0
        ):
            self._action(self.set_plane_mode, 'mask', cutoff=self._plane_cutoff_control.value)
            self._plane_cutoff_control.value = self.plane_cutoff
        self._text(
            gui,
            'Mask writes physical depth where effective alpha is at least '
            'the cutoff; zero alpha always leaves a hole.',
        )

    def _draw_insertion_gui(self, gui):
        for insertion_id, style in self._insertion_styles.items():
            label = 'BWM probe' if insertion_id == BWM_ID else insertion_id[:8]
            visibility = ctypes.c_bool(style['visible'])
            if self.dvz.dvz_gui_checkbox(
                gui, f'{label}##{insertion_id}'.encode(), ctypes.byref(visibility)
            ):
                self._action(self.style_insertion, insertion_id, visible=visibility.value)
            color = ctypes.c_int(next((i for i, c in enumerate(COLORS) if c == style['color']), 0))
            if self._combo(gui, f'Color##{insertion_id}', color, ('Gold', 'Cyan', 'Rose')):
                self._action(self.style_insertion, insertion_id, color=COLORS[color.value])
            width = ctypes.c_float(style['width'])
            if self.dvz.dvz_gui_slider_float(
                gui, f'Width (px)##{insertion_id}'.encode(), ctypes.byref(width), 1.0, 12.0
            ):
                self._action(self.style_insertion, insertion_id, width=width.value)

    def _draw_data_tables_gui(self, gui):
        if self.review_controls is None or not self._show_scientific_data.value:
            return False, False
        self.dvz.dvz_gui_dock_window_once(
            gui, b'Scientific data', self.dvz.DVZ_GUI_DOCK_SLOT_BOTTOM, 280.0 * self.ui_scale
        )
        probe_changed = False
        if self.dvz.dvz_gui_begin(gui, b'Scientific data', None, 0):
            low, high = self.value_range
            self._text(gui, f'Mean FR scale (Hz, 5-95%): {low:.3g} - {high:.3g}', width=55)
            self._text(gui, 'Purple=low; teal=mid; yellow=high.', width=55)
            if self.dvz.dvz_gui_collapsing_header(gui, b'Encoding and interaction notes', 0):
                self._draw_encoding_notes(gui)
            if self.probe_table is not None:
                _, events, _dropped = self.dvz.dvz_gui_table_draw(gui, self.probe_table)
                probe_changed = any(
                    event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED for event in events
                )
        self.dvz.dvz_gui_end(gui)
        return False, probe_changed

    def _draw_encoding_notes(self, gui):
        self._text(
            gui,
            f'{len(self.review_sites.values)} real BWM sites. Display clips '
            'at finite-site 5th/95th percentiles; table values stay unchanged.',
        )
        self._text(
            gui,
            f'WBOIT points: {self.point_mode}; opacity multiplier '
            f'{self.point_opacity:.2f}. Scalar missing FR has alpha 0. '
            'Uniform points are cyan and retain every real coordinate. '
            'Analytic sites and table swatches show missing FR in gray.',
        )
        self._text(
            gui,
            'Surface colors identify regions. Plane grayscale is real '
            'Allen anatomy positioned by its source affine. Opaque path colors '
            'identify insertions; paths connect actual channel coordinates '
            'without fitted or extrapolated points.',
        )
        self._text(
            gui,
            'Table selection links atlas regions. WBOIT points and '
            'sampled planes are not picking targets. Point encoding controls '
            'affect the WBOIT point layer; analytic sites retain FR colors.',
        )

    def close(self):
        """Close owned components before destroying the borrowed viewer scene."""
        for name in ('review_points', 'review_plane'):
            component = getattr(self, name, None)
            if component is not None:
                component.close()
                setattr(self, name, None)
        super().close()

    def __del__(self):
        """Keep component-before-scene cleanup when the caller omits explicit close."""
        with suppress(Exception):
            self.close()


def main():
    """Start the fixed-layout native review over verified D070/BWM/Allen inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('volume_root', type=Path)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--paths', type=Path, default=DEFAULT_PATHS)
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--preset', choices=PRESETS, default='atlas')
    parser.add_argument('--axis', choices=('ap', 'ml', 'dv'), default='ap')
    parser.add_argument('--index', type=int)
    add_review_arguments(parser)
    args = parser.parse_args()
    sites, _provenance = _load_fixture(args.fixture)
    paths, note = optional_insertions(
        args.paths, args.provenance or args.paths.with_suffix('.json')
    )
    if args.preset == 'multiple-insertions' and not paths:
        parser.error(note)
    plane = load_review_slice(args.volume_root, args.axis, args.index, args.mapping)
    with ScientificSceneReview.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        width=args.width,
        height=args.height,
        surface_opacity=1.0,
        camera_angles=(1.0, 0.75, -0.25),
        ui_scale=args.ui_scale,
        enable_interaction=True,
    ) as viewer:
        viewer.configure_review(sites, plane, paths, unavailable_note=note)
        viewer.apply_preset(args.preset)
        finish_review(viewer, args, 'IBL scientific scene review')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
