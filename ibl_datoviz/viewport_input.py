"""Suspend transient surface hover while the pointer controls the camera."""

from __future__ import annotations


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

    def on_input(self, _router, event_ptr, _user_data) -> None:
        """Clear hover on press/drag; resume only on fresh motion after release."""
        dvz = self.owner.dvz
        event = event_ptr.contents
        if event.type != dvz.DVZ_INPUT_EVENT_POINTER:
            return
        event_type = event.content.pointer.type
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
