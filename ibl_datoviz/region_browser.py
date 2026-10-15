"""Compact permanent region browser and its optional scene/details windows."""

from __future__ import annotations

import ctypes
import textwrap


class RegionBrowserSidebar:
    """Retain only window visibility; selection stays in the viewer's controller."""

    def __init__(self, viewer):
        self.viewer = viewer
        self.scene_open = ctypes.c_bool(False)
        self.details_open = ctypes.c_bool(False)
        self.row_height = self.tree_height = self.footer_height = self.browser_width = 0.0
        self.tree_rect = self.scene_rect = self.details_rect = None
        self.sidebar_rect = None
        self._window_layouts = {}

    def available(self, gui):
        """Measure the remaining current-window content in host logical units."""
        size = (ctypes.c_float * 2)()
        if not self.viewer.dvz.dvz_gui_content_avail(gui, size):
            raise RuntimeError('region browser content measurement failed')
        return tuple(size)

    def rect(self, gui):
        """Expose current-window bounds for bounded interaction review."""
        rect = self.viewer.dvz.DvzRect()
        if self.viewer.dvz.dvz_gui_current_window_rect(gui, ctypes.byref(rect)):
            return (rect.x, rect.y, rect.width, rect.height)
        return None

    def icon(self, gui, name, kind, tooltip, *, active=False, disabled=False):
        """Draw a compact native vector icon with an explicit explanatory tooltip."""
        dvz = self.viewer.dvz
        flags = (dvz.DVZ_GUI_ICON_BUTTON_FLAGS_ACTIVE if active else 0) | (
            dvz.DVZ_GUI_ICON_BUTTON_FLAGS_DISABLED if disabled else 0
        )
        return dvz.dvz_gui_icon_button(
            gui,
            name,
            getattr(dvz, f'DVZ_GUI_ICON_{kind}'),
            22.0 * self.viewer.ui_scale,
            tooltip.encode(),
            flags,
        )

    def header(self, gui):
        """Draw mapping, anatomical-side visibility and the Scene launcher."""
        viewer, dvz = self.viewer, self.viewer.dvz
        self.sidebar_rect = self.rect(gui)
        width, height = self.available(gui)
        self.browser_width = width
        gap, icon = 6.0 * viewer.ui_scale, 22.0 * viewer.ui_scale
        field_width = max(1.0, (width - icon - 2 * gap) * 0.5)
        dvz.dvz_gui_set_next_item_width(gui, field_width)
        if dvz.dvz_gui_combo(
            gui,
            b'##ibl_atlas_mapping',
            ctypes.byref(viewer._mapping_control),
            viewer._mapping_items,
            len(viewer._mapping_items),
        ):
            viewer.set_mapping(viewer.mesh_data.mapping_names[viewer._mapping_control.value])
        dvz.dvz_gui_same_line(gui, 0.0, gap)
        sides = viewer._surface_style.hemispheres
        choices = ((True, True), (True, False), (False, True), (False, False))
        hemisphere = ctypes.c_int(choices.index((sides['left'], sides['right'])))
        items = (ctypes.c_char_p * 4)(b'Both sides', b'Left only', b'Right only', b'None')
        dvz.dvz_gui_set_next_item_width(gui, field_width)
        if dvz.dvz_gui_combo(gui, b'##ibl_hemisphere', ctypes.byref(hemisphere), items, 4):
            candidate = viewer._surface_style.copy()
            for side, visible in zip(('left', 'right'), choices[hemisphere.value], strict=True):
                candidate.set_hemisphere_visible(side, visible)
            viewer._commit_surface_style(candidate)
        dvz.dvz_gui_same_line(gui, 0.0, gap)
        if self.icon(
            gui,
            b'##ibl_scene',
            'SETTINGS',
            'Scene and display settings',
            active=self.scene_open.value,
        ):
            self.scene_open.value = not self.scene_open.value
        self.row_height = height - self.available(gui)[1]

    def reserve_tree(self, gui):
        """Give the hierarchy all remaining height except the two-row footer."""
        # Use the actual font/style row footprint measured above, in host logical
        # coordinates. The font has already been scaled by the GUI configuration.
        self.footer_height = 2.0 * self.row_height
        self.tree_height = max(
            1.0, self.available(gui)[1] - self.footer_height - 6.0 * self.viewer.ui_scale
        )
        return self.tree_height

    def footer(self, gui):
        """Draw two stable rows regardless of the committed selection size."""
        viewer, dvz = self.viewer, self.viewer.dvz
        selected = viewer._selected_region_ids
        limit = max(8, int(self.browser_width / (7.0 * viewer.ui_scale)) - 15)
        if len(selected) == 1:
            region_id = selected[0]
            label = viewer.tree_model.describe(region_id) if viewer.tree_model else str(region_id)
            acronym, _, name = label.partition(' — ')
            summary = f'{acronym} ({"Left" if region_id < 0 else "Right"})'
            hint = name or label
        elif selected:
            summary = f'{len(selected)} regions selected'
            hint = 'Ctrl/Cmd adds; Shift selects a range'
        else:
            summary, hint = 'No regions selected', 'Click a leaf or brain region'
        dvz.dvz_gui_text(gui, self._short(summary, limit).encode())
        dvz.dvz_gui_same_line(gui, 0.0, 6.0 * viewer.ui_scale)
        clear = self.icon(
            gui, b'##ibl_clear_selection', 'CLEAR', 'Clear selection', disabled=not selected
        )
        dvz.dvz_gui_same_line(gui, 0.0, 6.0 * viewer.ui_scale)
        if self.icon(
            gui,
            b'##ibl_selection_details',
            'INFO',
            'Selection details',
            active=self.details_open.value,
        ):
            self.details_open.value = not self.details_open.value
        dvz.dvz_gui_text(gui, self._short(hint, limit + 10).encode())
        return clear

    @staticmethod
    def _short(text, limit):
        return text if len(text) <= limit else text[: limit - 3] + '...'

    def _window(self, gui, title, opened, *, details=False):
        viewer, dvz = self.viewer, self.viewer.dvz
        # Preserve ordinary user positioning until the surrounding host/sidebar
        # changes, then restore bounds over the resized scientific viewport.
        scale = viewer.ui_scale
        rect = dvz.DvzRect()
        sidebar_right = viewer.sidebar_width * scale
        if self.sidebar_rect is not None and self.sidebar_rect[2] > 0:
            sidebar_right = self.sidebar_rect[0] + self.sidebar_rect[2]
        host_width, host_height = viewer.width, viewer.height
        if viewer.view is not None:
            size = dvz.dvz_view_resolved_size(viewer.view)
            if size.host_logical_width > 0 and size.host_logical_height > 0:
                host_width, host_height = size.host_logical_width, size.host_logical_height
        rect.x = sidebar_right + 16.0 * scale
        rect.y = (64.0 if details else 24.0) * scale
        rect.width = min(430.0 * scale, max(1.0, host_width - rect.x - 12.0 * scale))
        rect.height = min(510.0 * scale, max(1.0, host_height - rect.y - 12.0 * scale))
        signature = (host_width, host_height, self.sidebar_rect, scale)
        previous = self._window_layouts.get(title)
        condition = 0 if previous is not None and previous != signature else 4
        viewer._check(
            dvz.dvz_gui_set_next_window_rect(gui, ctypes.byref(rect), condition),
            'browser auxiliary window bounds',
        )
        visible = dvz.dvz_gui_begin(
            gui, title, ctypes.byref(opened) if opened is not None else None, 1 << 19
        )
        self._window_layouts[title] = signature
        return visible

    def scene(self, gui):
        """Draw explicitly opened scene controls without blocking other windows."""
        if not self.scene_open.value:
            return
        viewer, dvz = self.viewer, self.viewer.dvz
        visible = self._window(gui, b'Scene', self.scene_open)
        try:
            self.scene_rect = self.rect(gui)
            if visible:
                if dvz.dvz_gui_button(gui, b'Close##ibl_scene'):
                    self.scene_open.value = False
                viewer._draw_sidebar_controls_gui(gui)
        finally:
            dvz.dvz_gui_end(gui)

    def details(self, gui):
        """Show the complete committed selection and ancestry on explicit request."""
        if not self.details_open.value:
            return
        viewer, dvz = self.viewer, self.viewer.dvz
        visible = self._window(gui, b'Selection details', self.details_open, details=True)
        try:
            self.details_rect = self.rect(gui)
            if visible:
                wrap_width = max(
                    12, min(48, int(self.available(gui)[0] / (7.0 * viewer.ui_scale)))
                )
                if dvz.dvz_gui_button(gui, b'Close##ibl_details'):
                    self.details_open.value = False
                if not viewer._selected_region_ids:
                    dvz.dvz_gui_text(gui, b'No regions selected')
                for region_id in viewer._selected_region_ids:
                    label = (
                        viewer.tree_model.describe(region_id)
                        if viewer.tree_model
                        else str(region_id)
                    )
                    dvz.dvz_gui_separator_text(
                        gui, f'{region_id} / {"Left" if region_id < 0 else "Right"}'.encode()
                    )
                    for line in textwrap.wrap(label.replace(' — ', ': '), width=wrap_width):
                        dvz.dvz_gui_text(gui, line.encode())
                    model = viewer._selector_model
                    key = (
                        next(
                            (r.id for r in model.regions if abs(r.atlas_id) == abs(region_id)),
                            None,
                        )
                        if model
                        else None
                    )
                    ancestors = []
                    while key is not None:
                        region = model.by_id[key]
                        ancestors.append(region.acronym)
                        key = region.parent_id
                    for line in textwrap.wrap(' / '.join(reversed(ancestors)), width=wrap_width):
                        dvz.dvz_gui_text(gui, line.encode())
        finally:
            dvz.dvz_gui_end(gui)
