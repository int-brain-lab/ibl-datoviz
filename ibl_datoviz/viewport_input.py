"""Suspend transient surface hover while the pointer controls the camera."""

from __future__ import annotations

import ctypes

from .slice_input import SliceInputAdapter


class ViewportInputAdapter:
    """Retain a viewport subscription until it is closed before native teardown."""

    def __init__(self, owner, router) -> None:
        self.owner = owner
        self.router = router
        self.subscription = 0
        self.callback = self.on_input
        self.pressed = False
        self.suspended = False

    def subscribe(self) -> None:
        """Subscribe once, keeping the callback alive throughout its native lifetime."""
        if self.subscription:
            return
        self.subscription = self.owner.dvz.dvz_input_subscribe_event(
            self.router, self.callback, None
        )
        if not self.subscription:
            raise RuntimeError('dvz_input_subscribe_event() failed')

    def close(self) -> None:
        """Unsubscribe before the viewport router is destroyed."""
        if self.subscription:
            self.owner.dvz.dvz_input_unsubscribe(self.router, self.subscription)
            self.subscription = 0
        self.callback = None

    def _request_observation(self, pointer):
        owner, dvz = self.owner, self.owner.dvz
        figure_position = SliceInputAdapter(owner, self.router).pointer_figure_position(pointer)
        if figure_position is None:
            return
        source = (ctypes.c_double * 2)(*figure_position)
        position = (ctypes.c_double * 2)()
        if dvz.dvz_panel_transform_point(
            owner.panel,
            dvz.DVZ_PANEL_COORD_FIGURE_PX,
            dvz.DVZ_PANEL_COORD_PANEL_PX,
            source,
            position,
        ):
            owner.picking.request(*position)
            dvz.dvz_view_request_frame(owner.view)

    def on_input(self, _router, event_ptr, _user_data) -> None:
        """Clear hover on press/drag; resume only on fresh motion after release."""
        dvz = self.owner.dvz
        event = event_ptr.contents
        if event.type != dvz.DVZ_INPUT_EVENT_POINTER:
            if hasattr(self.owner, '_invalidate_picking'):
                self.owner._invalidate_picking()
            return
        pointer = event.content.pointer
        event_type = pointer.type
        if event_type in (
            dvz.DVZ_POINTER_EVENT_PRESS,
            getattr(dvz, 'DVZ_POINTER_EVENT_CLICK', -1),
            getattr(dvz, 'DVZ_POINTER_EVENT_WHEEL', -1),
        ) and hasattr(self.owner, '_cancel_auto_slice'):
            self.owner._cancel_auto_slice()
        if event_type in (
            dvz.DVZ_POINTER_EVENT_PRESS,
            dvz.DVZ_POINTER_EVENT_DRAG_START,
            dvz.DVZ_POINTER_EVENT_DRAG,
            getattr(dvz, 'DVZ_POINTER_EVENT_WHEEL', -1),
        ) and hasattr(self.owner, '_invalidate_picking'):
            self.owner._invalidate_picking()
        if (
            event_type == getattr(dvz, 'DVZ_POINTER_EVENT_CLICK', -1)
            and getattr(pointer, 'button', None) == getattr(dvz, 'DVZ_POINTER_BUTTON_RIGHT', -2)
            and getattr(self.owner, 'picking', None) is not None
        ):
            try:
                self._request_observation(pointer)
            except Exception as error:
                # ctypes callbacks cannot propagate Python errors to app_run.
                self.owner._gui_callback_error = error
                self.owner._close_pending = True
                if self.owner.app is not None:
                    dvz.dvz_app_stop(self.owner.app)
            return
        if event_type in (
            dvz.DVZ_POINTER_EVENT_PRESS,
            dvz.DVZ_POINTER_EVENT_DRAG_START,
            dvz.DVZ_POINTER_EVENT_DRAG,
        ):
            self.pressed = True
            self.suspended = True
            self.owner._clear_surface_hover()
        elif event_type in (dvz.DVZ_POINTER_EVENT_RELEASE, dvz.DVZ_POINTER_EVENT_DRAG_STOP):
            self.pressed = False
            self.owner._clear_surface_hover()
        elif event_type == dvz.DVZ_POINTER_EVENT_MOVE and not self.pressed:
            self.suspended = False
