#!/usr/bin/env python3
"""Where did we record? Explore a verified BWM recording inside anatomical context."""

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
    RECORDING_CAMERA,
    ReviewControls,
    add_review_arguments,
    finish_review,
    load_major_context,
    load_review_slice,
    review_context_surfaces,
)
from ibl_datoviz import (
    AtlasViewer,
    PointCollection,
    PointCollectionVisual,
    SampledPlane,
    SampledPlaneVisual,
)
from ibl_datoviz.context import DEFAULT_CONTEXT_LANDMARKS
from ibl_datoviz.presentation import scalar_colors

PRESETS = ('atlas', 'single-probe', 'multiple-insertions', 'mixed')
PRESET_LABELS = ('Atlas surface', 'Single BWM probe', 'Multiple W39 insertions', 'Points + plane')
BWM_ID = 'bwm-probe'
POINT_COLOR = (70, 220, 250, 180)
SITE_RADIUS_UM = 20.0
# A small nonredundant context cut; the complete verified catalog remains available.
CONTEXT_LANDMARKS = DEFAULT_CONTEXT_LANDMARKS
MISSING_W39 = (
    'Multiple insertions unavailable. Prepare the pinned W39 channels.pqt with '
    'tools/build_w39_insertions.py --channels /path/to/channels.pqt '
    '--output build/w39-insertions, then restart this review.'
)


def recording_description(provenance):
    """Describe the supplied recording without borrowing another fixture's identity."""
    provenance = provenance or {}
    dataset = provenance.get('dataset', {})
    insertion = provenance.get('insertion', {})
    source = ' '.join(str(dataset[key]) for key in ('name', 'version') if dataset.get(key))
    recording = ' '.join(
        str(insertion[key]) for key in ('subject', 'probe_name') if insertion.get(key)
    )
    caption = ' / '.join(part for part in (source, recording) if part) or 'Supplied recording'
    description = provenance.get('derivation', {}).get('value', 'prepared recording-site values')
    return caption, description


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
        self.layers_rect = None
        self.envelope_note = ''
        self.review_points = self.review_plane = None
        self._review_error = ''
        kwargs.setdefault('enable_hover', False)
        kwargs.setdefault('selection_presentation', 'all')
        super().__init__(mesh, **kwargs)

    def configure_review(self, sites, plane, paths=(), *, unavailable_note='', provenance=None):
        """Attach verified data once, borrowing this viewer's scene and atlas panel."""
        self.review_sites, self.base_plane = sites, plane
        self.recording_provenance = provenance or {}
        self.recording_caption, self.value_description = recording_description(provenance)
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
        self.review_layers = {
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
        self._layer_controls = {
            name: ctypes.c_bool(value) for name, value in self.review_layers.items()
        }
        self.site_mode = 'uniform'
        self.site_radius_um = SITE_RADIUS_UM
        self._site_radius_control = ctypes.c_float(self.site_radius_um)
        self._site_mode_control = ctypes.c_int(0)
        self._point_mode_control = ctypes.c_int(1)
        self._point_size_control = ctypes.c_float(self.point_size)
        self._point_opacity_control = ctypes.c_float(self.point_opacity)
        self._plane_mode_control = ctypes.c_int(0)
        self._plane_opacity_control = ctypes.c_float(self.plane_opacity)
        self._plane_cutoff_control = ctypes.c_float(self.plane_cutoff)
        self.set_probe_data(
            sites,
            value_range=self.value_range,
            radius_um=self.site_radius_um,
            color_scheme='sequential',
        )
        self.set_site_mode('uniform')
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
        self.apply_preset('single-probe')

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
                    self.review_layers['insertions']
                    and style['visible']
                    and insertion_id in self._active_insertions
                ),
            )

    def set_surface_visible(self, visible):
        """Keep atlas display controls and preset rollback on one visibility state."""
        super().set_surface_visible(visible)
        if hasattr(self, 'review_layers'):
            self.review_layers['atlas'] = bool(visible)
            self._layer_controls['atlas'].value = bool(visible)

    def set_layer_visible(self, layer, visible):
        """Change a retained layer without changing camera or authored region styles."""
        if layer not in self.review_layers:
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
        old = self.review_layers[layer]
        self.review_layers[layer] = visible
        try:
            if layer == 'insertions':
                self._sync_insertions()
        except Exception:
            self.review_layers[layer] = old
            self._sync_insertions()
            raise
        self._layer_controls[layer].value = visible

    def apply_preset(self, preset):
        """Switch layer visibility in the same scene; never reset the current camera."""
        if preset not in PRESETS:
            raise ValueError(f'unknown scene preset: {preset}')
        if preset == 'multiple-insertions' and len(self._paths) == 1:
            raise ValueError(self.unavailable_note or MISSING_W39)
        previous_layers = self.review_layers.copy()
        previous_active = self._active_insertions
        self._active_insertions = (
            tuple(key for key in self._paths if key != BWM_ID)
            if preset == 'multiple-insertions'
            else (BWM_ID,)
        )
        enabled = {'atlas'}
        if preset == 'single-probe':
            enabled.update(('sites', 'insertions'))
        elif preset == 'multiple-insertions':
            enabled.add('insertions')
        elif preset == 'mixed':
            enabled.update(('points', 'plane', 'insertions'))
        try:
            for layer in self.review_layers:
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
            replacement.set_visible(self.review_layers['plane'])
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
                visible and self.review_layers['insertions']
                and insertion_id in self._active_insertions
            )
            self.set_insertion_visible(insertion_id, effective)
            style['visible'] = bool(visible)

    def reset_review(self):
        """Explicitly restore initial controls, camera, layers and scientific styles."""
        self.review_controls.reset()
        self.set_site_mode('uniform', radius_um=SITE_RADIUS_UM)
        self.set_point_mode('scalar')
        self.set_point_size(6.0)
        self.set_point_opacity(0.7)
        self.set_plane_opacity(0.65)
        self.set_plane_mode('wboit', cutoff=0.5)
        for insertion_id, (color, width) in self._initial_styles.items():
            self.style_insertion(insertion_id, visible=True, color=color, width=width)
        self.apply_preset('single-probe')
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
        if hasattr(self.dvz, 'dvz_gui_content_avail'):
            available_width, _ = self._sidebar.available(gui)
            width = max(12, min(width, int(available_width / (7.0 * self.ui_scale))))
        for line in textwrap.wrap(message, width=width):
            self.dvz.dvz_gui_text(gui, line.encode())

    def _combo(self, gui, label, control, choices):
        items = (ctypes.c_char_p * len(choices))(*(item.encode() for item in choices))
        return self.dvz.dvz_gui_combo(
            gui, label.encode(), ctypes.byref(control), items, len(choices)
        )

    def _draw_extra_gui(self, gui):
        """Keep atlas display choices separate from optional scientific data."""
        if self.review_controls is None:
            return
        self.review_controls.draw(gui)
        if self.envelope_note:
            self._text(gui, self.envelope_note)

    def _draw_viewport_toolbar_gui(self, gui):
        """Keep selection explosion and camera reset beside the recording viewport."""
        super()._draw_viewport_toolbar_gui(gui)

    def _draw_auxiliary_gui(self, gui):
        """Keep Layers docked on the right, outside the Regions browser."""
        if self.review_controls is None:
            return
        self._check(
            self.dvz.dvz_gui_dock_window_once(
                gui, b'Layers', self.dvz.DVZ_GUI_DOCK_SLOT_RIGHT, 330.0 * self.ui_scale
            ),
            'recording layers dock',
        )
        visible = self.dvz.dvz_gui_begin(gui, b'Layers', None, 0)
        try:
            self.layers_rect = self._sidebar.rect(gui)
            if visible:
                self._draw_layer_controls(gui)
        finally:
            self.dvz.dvz_gui_end(gui)

    def _draw_layer_controls(self, gui):
        rows = (
            (
                'atlas',
                'Brain context',
                (150, 170, 190, 255),
                len(getattr(getattr(self, '_anatomical_context', None), 'surfaces', ())),
            ),
            ('insertions', 'Insertion paths', COLORS[0], len(self._active_insertions)),
            ('sites', 'Recording sites', POINT_COLOR, len(self.review_sites.values)),
        )
        for layer, label, color, count in rows:
            control = self._layer_controls[layer]
            control.value = self.review_layers[layer]
            if self.dvz.dvz_gui_checkbox(gui, label.encode(), ctypes.byref(control)):
                self._action(self.set_layer_visible, layer, control.value)
                control.value = self.review_layers[layer]
            self.dvz.dvz_gui_same_line(gui, 0.0, 6.0 * self.ui_scale)
            rgba = (ctypes.c_float * 4)(*(np.asarray(color) / 255))
            # Read-only layer swatch; insertion rows below have editable swatches.
            self.dvz.dvz_gui_color_edit4(
                gui,
                f'##swatch_{layer}'.encode(),
                rgba,
                (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5) | (1 << 7),
            )
            self.dvz.dvz_gui_same_line(gui, 0.0, 6.0 * self.ui_scale)
            self.dvz.dvz_gui_text(gui, str(count).encode())
            if layer == 'insertions' and self.review_layers['insertions']:
                self._draw_insertion_gui(gui)
            if layer == 'sites' and self.review_layers['sites']:
                self._draw_site_controls(gui)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Recording details', 0):
            if self.dvz.dvz_gui_button(gui, b'Site table'):
                self._show_scientific_data.value = not self._show_scientific_data.value
            self._text(
                gui,
                f'{self.recording_caption}: {self.value_description}. '
                'Locations describe recording sites, not exact neuron positions.',
                width=100,
            )
            self._text(
                gui,
                'The supplied path joins channel coordinates; '
                'it is not an independent histology trace.',
                width=100,
            )
        if self._review_error:
            self._text(gui, f'Change failed: {self._review_error}')
        if self.dvz.dvz_gui_collapsing_header(gui, b'Advanced diagnostics', 0):
            self._draw_diagnostics_gui(gui)

    def _draw_diagnostics_gui(self, gui):
        self._draw_examples_gui(gui)
        for layer, label in (('points', 'Comparison points'), ('plane', 'Anatomical plane')):
            control = self._layer_controls[layer]
            control.value = self.review_layers[layer]
            if self.dvz.dvz_gui_checkbox(gui, label.encode(), ctypes.byref(control)):
                self._action(self.set_layer_visible, layer, control.value)
                control.value = self.review_layers[layer]
        if self.review_layers['points']:
            self._draw_point_gui(gui)
        if self.review_layers['plane']:
            self._draw_plane_gui(gui)

    def _draw_site_controls(self, gui):
        self.dvz.dvz_gui_text(gui, b'Color')
        self.dvz.dvz_gui_same_line(gui, 0.0, 6.0 * self.ui_scale)
        width, _ = self._sidebar.available(gui)
        self.dvz.dvz_gui_set_next_item_width(gui, max(1.0, width - 1.0))
        if self._combo(
            gui, '##site_color', self._site_mode_control, ('Uniform', 'Mean firing rate (Hz)')
        ):
            self._action(self.set_site_mode, ('uniform', 'scalar')[self._site_mode_control.value])
            self._site_mode_control.value = ('uniform', 'scalar').index(self.site_mode)
        self.dvz.dvz_gui_text(gui, 'Radius (µm)'.encode())
        self.dvz.dvz_gui_same_line(gui, 0.0, 6.0 * self.ui_scale)
        width, _ = self._sidebar.available(gui)
        self.dvz.dvz_gui_set_next_item_width(gui, max(1.0, width - 1.0))
        if self.dvz.dvz_gui_slider_float(
            gui, b'##site_radius_um', ctypes.byref(self._site_radius_control), 3.0, 40.0
        ):
            self._action(self.set_site_radius, self._site_radius_control.value)
            self._site_radius_control.value = self.site_radius_um
        low, high = self.value_range
        legend = (
            f'Mean firing rate: {low:.3g}–{high:.3g} Hz (5–95%). '
            'Purple: low; yellow: high; gray: missing.'
            if self.site_mode == 'scalar'
            else 'Cyan identifies recording sites; no quantity is encoded.'
        )
        self._text(gui, legend)
        self._text(
            gui,
            f'{len(self.review_sites.values)} co-located channel groups; sites are not neurons.',
        )
        if self.preset == 'multiple-insertions':
            self._text(gui, 'Sites belong to the BWM recording, not these W39 paths.')

    def set_site_radius(self, radius_um):
        """Resize glyphs in physical units while preserving observations and their encoding."""
        self.set_site_mode(self.site_mode, radius_um=radius_um)

    def set_site_mode(self, mode, *, radius_um=None):
        """Color the retained recording sites without changing identities or visibility."""
        if mode not in ('uniform', 'scalar'):
            raise ValueError('site color mode must be uniform or scalar')
        radius_um = self.site_radius_um if radius_um is None else float(radius_um)
        if not np.isfinite(radius_um) or radius_um <= 0:
            raise ValueError('site radius must be finite and positive')
        colors = (
            scalar_colors(self.review_sites.values, self.value_range, 'sequential')
            if mode == 'scalar'
            else np.tile(
                np.array((*POINT_COLOR[:3], 255), dtype=np.uint8),
                (len(self.review_sites.values), 1),
            )
        )
        self._upload_probe_sites(
            self.review_sites.positions_um,
            colors=colors,
            radius_um=radius_um,
            mapped_ids=self._mapped_probe_region_ids(self.review_sites),
        )
        self._probe_colors = colors
        self.site_mode = mode
        self.site_radius_um = radius_um
        self._site_radius_control.value = radius_um
        self._site_mode_control.value = ('uniform', 'scalar').index(mode)

    def _draw_examples_gui(self, gui):
        labels = tuple(PRESET_LABELS[PRESETS.index(name)] for name in self._available_presets)
        if self._combo(gui, 'Example', self._preset_control, labels) and not self._action(
            self.apply_preset, self._available_presets[self._preset_control.value]
        ):
            self._preset_control.value = self._available_presets.index(self.preset)
        if self.unavailable_note:
            self._text(gui, self.unavailable_note)
        if self.dvz.dvz_gui_button(gui, b'Restore all example defaults'):
            self._action(self.reset_review)

    def _draw_point_gui(self, gui):
        self._text(
            gui,
            'Comparison points use the same recorded coordinates. '
            'Missing firing rates are hidden; uniform color shows every site.',
        )
        if self._combo(
            gui,
            'Color mode',
            self._point_mode_control,
            ('Uniform color', 'Mean firing rate (Hz)'),
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
        if self._combo(gui, 'Appearance', self._plane_mode_control, ('Transparent', 'Cutout')):
            self._action(self.set_plane_mode, ('wboit', 'mask')[self._plane_mode_control.value])
            self._plane_mode_control.value = ('wboit', 'mask').index(self.plane_mode)
        if self.dvz.dvz_gui_slider_float(
            gui, b'Plane opacity', ctypes.byref(self._plane_opacity_control), 0.0, 1.0
        ):
            self._action(self.set_plane_opacity, self._plane_opacity_control.value)
            self._plane_opacity_control.value = self.plane_opacity
        if self.plane_mode == 'mask' and self.dvz.dvz_gui_slider_float(
            gui, b'Cutout threshold', ctypes.byref(self._plane_cutoff_control), 0.0, 1.0
        ):
            self._action(self.set_plane_mode, 'mask', cutoff=self._plane_cutoff_control.value)
            self._plane_cutoff_control.value = self.plane_cutoff
        self._text(
            gui,
            'Cutout keeps pixels at or above the threshold. '
            'Fully transparent pixels leave a hole.',
        )

    def _draw_insertion_gui(self, gui):
        """Keep every path's visibility, color and width on its own active-only row."""
        for insertion_id in self._active_insertions:
            row_width, _ = self._sidebar.available(gui)
            style = self._insertion_styles[insertion_id]
            label = 'BWM probe' if insertion_id == BWM_ID else insertion_id[:8]
            visibility = ctypes.c_bool(style['visible'])
            if self.dvz.dvz_gui_checkbox(
                gui, f'{label}##{insertion_id}'.encode(), ctypes.byref(visibility)
            ):
                self._action(self.style_insertion, insertion_id, visible=visibility.value)
            self.dvz.dvz_gui_same_line(gui, 0.0, 5.0 * self.ui_scale)
            rgba = (ctypes.c_float * 4)(*(np.asarray(style['color']) / 255))
            if self.dvz.dvz_gui_color_edit4(
                gui,
                f'##color_{insertion_id}'.encode(),
                rgba,
                (1 << 1) | (1 << 3) | (1 << 5) | (1 << 7),
            ):
                color = tuple(int(round(float(value) * 255)) for value in rgba[:3]) + (255,)
                self._action(self.style_insertion, insertion_id, color=color)
            if row_width >= 200.0 * self.ui_scale:
                self.dvz.dvz_gui_same_line(gui, 0.0, 5.0 * self.ui_scale)
                self.dvz.dvz_gui_text(gui, b'px')
            else:
                self.dvz.dvz_gui_text(gui, b'Width (px)')
            self.dvz.dvz_gui_same_line(gui, 0.0, 4.0 * self.ui_scale)
            available_width, _ = self._sidebar.available(gui)
            self.dvz.dvz_gui_set_next_item_width(gui, max(1.0, available_width - 1.0))
            width = ctypes.c_float(style['width'])
            if self.dvz.dvz_gui_slider_float(
                gui, f'##width_px_{insertion_id}'.encode(), ctypes.byref(width), 1.0, 12.0
            ):
                self._action(self.style_insertion, insertion_id, width=width.value)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Insertion details', 0):
            for insertion_id in self._active_insertions:
                if insertion_id == BWM_ID:
                    insertion = self.recording_provenance.get('insertion', {})
                    self._text(gui, self.recording_caption)
                    self._text(gui, f'Insertion: {insertion.get("pid", "not supplied")}')
                    self._text(gui, f'Session: {insertion.get("eid", "not supplied")}')
                    self._text(gui, 'Path joins the supplied BWM channel-group coordinates.')
                else:
                    self._text(gui, f'Insertion: {insertion_id}')
                    self._text(
                        gui,
                        'Source: pinned W39 channels; 384 ordered channel rows. '
                        'Session metadata is not supplied in this derivative.',
                    )

    def _draw_data_tables_gui(self, gui):
        if self.review_controls is None or not self._show_scientific_data.value:
            return False, False
        visible = self._sidebar._window(
            gui, b'Data table', self._show_scientific_data, details=True
        )
        probe_changed = False
        try:
            if visible:
                if self.dvz.dvz_gui_button(gui, b'Close##ibl_scientific_data'):
                    self._show_scientific_data.value = False
                low, high = self.value_range
                self._text(gui, f'Mean FR scale (Hz, 5-95%): {low:.3g} - {high:.3g}', width=55)
                self._text(gui, 'Purple=low; teal=mid; yellow=high.', width=55)
                if self.dvz.dvz_gui_collapsing_header(gui, b'Encoding and interaction notes', 0):
                    self._draw_encoding_notes(gui)
                if self.probe_table is not None:
                    result, events, dropped = self.dvz.dvz_gui_table_draw(gui, self.probe_table)
                    self._check(result, 'scientific data table draw')
                    if dropped:
                        raise RuntimeError('scientific data table input batch dropped')
                    probe_changed = any(
                        event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                        for event in events
                    )
        finally:
            self.dvz.dvz_gui_end(gui)
        return False, probe_changed

    def _draw_encoding_notes(self, gui):
        self._text(
            gui,
            f'{len(self.review_sites.values)} supplied recording sites. Display clips '
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
    parser.add_argument(
        '--context-root',
        type=Path,
        default=Path(__file__).resolve().parents[1] / 'build' / 'allen-major-context',
        help='prepared hash-verified major Allen surfaces (run just setup to prepare)',
    )
    parser.add_argument('--paths', type=Path, default=DEFAULT_PATHS)
    parser.add_argument(
        '--context-detail',
        choices=('landmarks', 'all'),
        default='landmarks',
        help='six orientation landmarks by default; all twelve surfaces for comparison',
    )
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--preset', choices=PRESETS, default='single-probe')
    parser.add_argument('--axis', choices=('ap', 'ml', 'dv'), default='ap')
    parser.add_argument('--index', type=int)
    parser.add_argument(
        '--hover',
        action='store_true',
        help='enable tree and brain hover feedback, including 3D queries',
    )
    add_review_arguments(parser)
    args = parser.parse_args()
    sites, provenance = _load_fixture(args.fixture)
    paths, note = optional_insertions(
        args.paths, args.provenance or args.paths.with_suffix('.json')
    )
    if args.preset == 'multiple-insertions' and not paths:
        parser.error(note)
    try:
        context_catalog, context_geometry = load_major_context(args.context_root)
    except (AttributeError, ImportError, FileNotFoundError, ValueError) as error:
        parser.error(
            f'Major anatomical context unavailable: {error}. '
            'Run just setup /path/to/datoviz to prepare the verified surfaces.'
        )
    plane = load_review_slice(args.volume_root, args.axis, args.index, args.mapping)
    with ScientificSceneReview.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        width=args.width,
        height=args.height,
        surface_opacity=0.18,
        anatomy_presentation='major',
        context_opacity=0.04,
        camera_angles=RECORDING_CAMERA,
        ui_scale=args.ui_scale,
        enable_hover=args.hover,
        enable_interaction=True,
        fit_workarea=args.offscreen is None,
    ) as viewer:
        viewer.set_anatomical_context(review_context_surfaces(
            viewer.mesh_data, context_catalog, context_geometry, detail=args.context_detail,
        ))
        viewer.configure_review(sites, plane, paths, unavailable_note=note, provenance=provenance)
        viewer.apply_preset(args.preset)
        finish_review(viewer, args, 'Where did we record?')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
