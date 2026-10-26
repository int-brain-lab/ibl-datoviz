"""Host-window, docking and GUI assembly for one atlas viewer.

The viewer owns this component and every native handle it creates. Handles stay
on the viewer so its ordered, callback-safe teardown remains authoritative;
this component never destroys scene-owned objects or registers extra callbacks.
"""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from .viewport_input import ViewportInputAdapter

if TYPE_CHECKING:
    from .viewer import AtlasViewer


class ViewerLayout:
    """Assemble a viewer's host and GUI without owning scientific state."""

    def __init__(self, viewer: AtlasViewer) -> None:
        self.viewer = viewer

    def draw_frame(self, gui) -> None:
        """Draw one GUI frame with balanced native window and child scopes."""
        viewer = self.viewer
        viewer._process_gui_frame()
        viewer._dock_gui_windows(gui)
        # Dear ImGui NoScrollbar | NoScrollWithMouse: child panes own scrolling.
        visible = viewer.dvz.dvz_gui_begin(gui, b'Regions', None, (1 << 3) | (1 << 4))
        try:
            if visible:
                viewer._draw_sidebar_gui(gui)
        finally:
            viewer.dvz.dvz_gui_end(gui)
        if viewer.viewport is not None:
            # Reopening the same ImGui window appends the image below this toolbar.
            visible = viewer.dvz.dvz_gui_begin(gui, b'3D atlas', None, 0)
            try:
                if visible:
                    viewer._draw_viewport_toolbar_gui(gui)
            finally:
                viewer.dvz.dvz_gui_end(gui)
            viewer.dvz.dvz_gui_viewport_window(viewer.viewport, b'3D atlas', None, 0)
            hovered = ctypes.c_bool()
            mouse_pos = (ctypes.c_float * 2)()
            viewport_size = (ctypes.c_float * 2)()
            if viewer.dvz.dvz_gui_viewport_mouse(
                viewer.viewport, mouse_pos, viewport_size, ctypes.byref(hovered)
            ):
                viewer._sync_viewport_hover(bool(hovered.value))
            linked = getattr(viewer, '_linked', None)
            label = getattr(linked, '_hovered_region_label', None)
            if hovered.value and label:
                viewer.dvz.dvz_gui_tooltip(gui, label.encode())

        viewer._draw_auxiliary_gui(gui)
        viewer._draw_scientific_layers_gui(gui)
        if getattr(viewer, 'tables', None) is not None:
            viewer.tables.draw(gui)

    def dock_windows(self, gui) -> None:
        """Split sidebars before the central observation dock, preserving user moves."""
        viewer = self.viewer
        viewer.dvz.dvz_gui_dock_window_once(
            gui,
            b'Regions',
            viewer.dvz.DVZ_GUI_DOCK_SLOT_LEFT,
            viewer.sidebar_width * viewer.ui_scale,
        )
        registry = getattr(viewer, '_regional_quantities', None)
        quantity = registry.handle if registry is not None else None
        if viewer.layers or quantity is not None:
            viewer.dvz.dvz_gui_dock_window_once(
                gui,
                b'Layers',
                viewer.dvz.DVZ_GUI_DOCK_SLOT_RIGHT,
                340 * viewer.ui_scale,
            )
        tables = getattr(viewer, 'tables', None)
        if tables is not None and tables.visible:
            viewer.dvz.dvz_gui_dock_window_once(
                gui,
                b'Observations',
                viewer.dvz.DVZ_GUI_DOCK_SLOT_BOTTOM,
                280 * viewer.ui_scale,
            )
        if viewer.viewport is not None:
            viewer.dvz.dvz_gui_dock_window_once(
                gui, b'3D atlas', viewer.dvz.DVZ_GUI_DOCK_SLOT_CENTER, 0.0
            )

    def create_window(self, figure, title):
        """Create a host window with the configured work-area policy."""
        viewer = self.viewer
        if not viewer.fit_workarea:
            return viewer.dvz.dvz_view_window(
                viewer.app, figure, viewer.width, viewer.height, title.encode()
            )
        descriptor = viewer.dvz.dvz_view_desc(viewer.dvz.DVZ_VIEW_WINDOW)
        descriptor.size_policy = viewer.dvz.DVZ_VIEW_SIZE_HOST_LOGICAL_PX
        descriptor.size_width = viewer.width
        descriptor.size_height = viewer.height
        descriptor.title = title.encode()
        descriptor.fit_workarea = True
        return viewer.dvz.dvz_view(viewer.app, figure, ctypes.byref(descriptor))

    def create_view(self, *, offscreen: bool, title: str) -> None:  # noqa: PLR0912, PLR0915
        """Create host resources, input routing and the initial camera."""
        viewer = self.viewer
        if viewer.app is not None:
            raise RuntimeError('viewer already has an active app')
        if not offscreen and viewer.catalog is not None:
            app_config = viewer.dvz.dvz_app_config()
            app_config.font_ui_size_px = 18.0
            viewer.app = viewer.dvz.dvz_app_with_config(viewer.scene, ctypes.byref(app_config))
        else:
            viewer.app = viewer.dvz.dvz_app(viewer.scene)
        if not viewer.app:
            raise RuntimeError('dvz_app() failed')
        # Image-plane pan keeps overlapping translucent anatomy under the cursor at every depth.
        # The pinned baseline predates this optional native policy.
        arcball_descriptor = None
        if hasattr(viewer.dvz, 'DVZ_ARCBALL_FLAGS_SCREEN_PAN'):
            arcball_descriptor = viewer.dvz.dvz_arcball_desc()
            arcball_descriptor.controller_flags |= viewer.dvz.DVZ_ARCBALL_FLAGS_SCREEN_PAN
            if hasattr(viewer.dvz, 'DVZ_ARCBALL_FLAGS_PROJECTION_ZOOM'):
                arcball_descriptor.controller_flags |= viewer.dvz.DVZ_ARCBALL_FLAGS_PROJECTION_ZOOM
            if hasattr(viewer.dvz, 'DVZ_ARCBALL_FLAGS_ADAPTIVE_ORBIT'):
                arcball_descriptor.controller_flags |= viewer.dvz.DVZ_ARCBALL_FLAGS_ADAPTIVE_ORBIT
        arcball_config = (
            ctypes.byref(arcball_descriptor) if arcball_descriptor is not None else None
        )
        if offscreen:
            viewer.view = viewer.dvz.dvz_view_offscreen(
                viewer.app, viewer.figure, viewer.width, viewer.height
            )
            if not viewer.view:
                raise RuntimeError('Datoviz view creation failed')
            viewer.arcball = viewer.dvz.dvz_view_arcball(viewer.view, viewer.panel, arcball_config)
        elif viewer.catalog is None:
            viewer.view = viewer._create_window_view(viewer.figure, title)
            if not viewer.view:
                raise RuntimeError('Datoviz view creation failed')
            viewer.arcball = viewer.dvz.dvz_view_arcball(viewer.view, viewer.panel, arcball_config)
        else:
            viewer.host_figure = viewer.dvz.dvz_figure(
                viewer.scene, viewer.width, viewer.height, 0
            )
            if not viewer.host_figure:
                raise RuntimeError('Datoviz host figure creation failed')
            host_panel = viewer.dvz.dvz_panel_full(viewer.host_figure)
            if not host_panel:
                raise RuntimeError('Datoviz host panel creation failed')
            viewer.dvz.dvz_panel_set_background_color(
                host_panel, viewer.dvz.DvzColor(24, 27, 32, 255)
            )
            viewer.view = viewer._create_window_view(viewer.host_figure, title)
        if not viewer.view:
            raise RuntimeError('Datoviz view creation failed')
        viewer._check(
            viewer.dvz.dvz_view_set_user_scale(viewer.view, viewer.ui_scale),
            'view user scale',
        )
        if not offscreen and viewer.catalog is not None:
            if not hasattr(viewer.dvz, 'dvz_hover_copy'):
                raise RuntimeError(
                    'interactive atlas hover requires current Datoviz v0.4 Python bindings; '
                    'put the Datoviz source checkout on PYTHONPATH when using a development '
                    'libdatoviz build'
                )
            viewer._replace_region_tree()
            if viewer._probe_presentation.data is not None:
                viewer._replace_probe_table()
            if viewer.region_data is not None:
                viewer._replace_region_table()
            config = viewer.dvz.dvz_gui_config()
            config.gui_flags = (
                viewer.dvz.DVZ_GUI_FLAGS_DOCKING
                | viewer.dvz.DVZ_GUI_FLAGS_DOCKSPACE
                | viewer.dvz.DVZ_GUI_FLAGS_NAV_KEYBOARD
            )
            config.default_window_width = 430
            viewer.gui = viewer.dvz.dvz_view_gui(viewer.view, ctypes.byref(config))
            if not viewer.gui:
                raise RuntimeError('dvz_view_gui() failed')
            viewport_config = viewer.dvz.dvz_gui_viewport_config()
            viewport_config.viewport_flags = viewer.dvz.DVZ_GUI_VIEWPORT_FLAGS_FORWARD_INPUT
            viewer.viewport = viewer.dvz.dvz_gui_viewport(
                viewer.gui, viewer.figure, ctypes.byref(viewport_config)
            )
            if not viewer.viewport:
                raise RuntimeError('dvz_gui_viewport() failed')
            if viewer.interaction is not None:
                router = viewer.dvz.dvz_gui_viewport_input(viewer.viewport)
                if not router:
                    raise RuntimeError('dvz_gui_viewport_input() failed')
                viewer._viewport_input = ViewportInputAdapter(viewer, router)
                viewer._viewport_input.subscribe()
            viewer.arcball_controller = viewer.dvz.dvz_arcball(viewer.scene, arcball_config)
            if not viewer.arcball_controller:
                raise RuntimeError('dvz_arcball() failed')
            viewer.arcball = viewer.dvz.dvz_controller_arcball(viewer.arcball_controller)
            if not viewer.arcball:
                raise RuntimeError('dvz_controller_arcball() failed')
            viewer._check(
                viewer.dvz.dvz_panel_bind_controller(
                    viewer.panel, viewer.arcball_controller, viewer.dvz.DVZ_DIM_MASK_XYZ
                ),
                'arcball panel binding',
            )
            viewer._check(
                viewer.dvz.dvz_panel_connect_input(
                    viewer.panel, viewer.dvz.dvz_gui_viewport_input(viewer.viewport)
                ),
                'embedded viewport input connection',
            )
            viewer._check(
                viewer.dvz.dvz_view_set_gui_callback(viewer.view, viewer._gui_callback, None),
                'atlas GUI callback',
            )
        if not viewer.arcball:
            raise RuntimeError('dvz arcball creation failed')
        angles = (ctypes.c_float * 3)(*viewer.camera_angles)
        viewer._check(viewer.dvz.dvz_arcball_initial(viewer.arcball, angles), 'arcball setup')
