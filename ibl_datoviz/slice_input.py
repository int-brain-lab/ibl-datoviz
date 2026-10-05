"""Slice input calculations and explicit native event subscription ownership."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import numpy as np


def wheel_step(remainder: float, amount: float, *, shift: bool) -> tuple[int, float]:
    """Accumulate fractional wheel motion using the documented step sensitivity."""
    accumulated = remainder + amount * (10.0 if shift else 2.0)
    step = int(np.trunc(accumulated))
    return step, accumulated - step


def key_step(direction: int, *, shift: bool) -> int:
    """Return the keyboard step for a recognized direction key."""
    return direction * (5 if shift else 1)


def wheel_zoom(current: float, amount: float) -> float:
    """Clamp wheel zoom to the existing one-to-eight range."""
    return float(np.clip(current * 1.08**amount, 1.0, 8.0))


@dataclass(frozen=True, slots=True)
class PointerLayoutInputs:
    """Logical window dimensions and per-axis scale passed to native conversion."""

    width: float
    height: float
    scale_x: float
    scale_y: float


def pointer_layout_inputs(window_size, content_scale: float, resize=None) -> PointerLayoutInputs:
    """Resolve pointer dimensions and resize scale without a native call."""
    width, height = (float(value) for value in window_size)
    scale_x = scale_y = (
        float(content_scale) if np.isfinite(content_scale) and content_scale > 0 else 1.0
    )
    if resize is not None:
        if not np.isfinite(width) or width <= 0:
            width = float(resize.window_width)
        if not np.isfinite(height) or height <= 0:
            height = float(resize.window_height)
        if resize.content_scale_x > 0:
            scale_x = float(resize.content_scale_x)
        if resize.content_scale_y > 0:
            scale_y = float(resize.content_scale_y)
    return PointerLayoutInputs(width, height, scale_x, scale_y)


class SliceInputAdapter:
    """Route native slice events while the viewer owns authoritative scene state.

    The callback reference and router are retained through unsubscription.
    ``LinkedAtlasNavigator`` wires the adapter and closes it before scene cleanup.
    """

    def __init__(self, owner, router) -> None:
        self.owner = owner
        self.router = router
        self.subscription = 0
        self.callback = self.on_input

    def subscribe(self) -> None:
        """Subscribe once, retaining the callback even during a failed setup."""
        if self.subscription:
            return
        self.subscription = self.owner.dvz.dvz_input_subscribe_event(
            self.router, self.callback, None
        )
        if not self.subscription:
            raise RuntimeError('dvz_input_subscribe_event() failed')

    def close(self) -> None:
        """Unsubscribe exactly once before releasing the callback reference."""
        if self.subscription:
            self.owner.dvz.dvz_input_unsubscribe(self.router, self.subscription)
            self.subscription = 0
        self.callback = None

    def pointer_figure_position(self, pointer) -> tuple[float, float] | None:
        """Convert raw pointer coordinates through native viewport layout."""
        owner, dvz = self.owner, self.owner.dvz
        resize = dvz.DvzInputResizeEvent()
        has_resize = dvz.dvz_input_router_last_resize(self.router, ctypes.byref(resize))
        latest = resize if has_resize else None
        values = pointer_layout_inputs(pointer.window_size, float(pointer.content_scale), latest)
        figure_x, figure_y = ctypes.c_float(), ctypes.c_float()
        converted = dvz.dvz_figure_window_to_layout(
            owner.figure,
            float(pointer.pos[0]),
            float(pointer.pos[1]),
            values.width,
            values.height,
            values.scale_x,
            values.scale_y,
            ctypes.byref(figure_x),
            ctypes.byref(figure_y),
        )
        return (figure_x.value, figure_y.value) if converted else None

    def slice_data_at_pointer(self, pointer):
        """Translate a pointer into the first containing slice panel's data space."""
        figure_position = self.pointer_figure_position(pointer)
        if figure_position is None:
            return None
        owner, dvz = self.owner, self.owner.dvz
        for axis, panel in owner.slice_panels.items():
            figure_pos = (ctypes.c_double * 2)(*figure_position)
            panel_pos = (ctypes.c_double * 2)()
            inside = dvz.dvz_panel_transform_point(
                panel,
                dvz.DVZ_PANEL_COORD_FIGURE_PX,
                dvz.DVZ_PANEL_COORD_PANEL_PX,
                figure_pos,
                panel_pos,
            )
            if not inside:
                continue
            data_pos = (ctypes.c_double * 2)()
            if not dvz.dvz_panel_position_to_data(
                panel, dvz.DVZ_PANEL_COORD_PANEL_PX, panel_pos, data_pos
            ):
                continue
            return axis, float(data_pos[0]), float(data_pos[1])
        return None

    def on_input(self, _router, event_ptr, _user_data) -> None:  # noqa: PLR0911, PLR0912
        """Dispatch keyboard and pointer interactions without changing selection policy."""
        owner, dvz = self.owner, self.owner.dvz
        event = event_ptr.contents
        if event.type == dvz.DVZ_INPUT_EVENT_KEYBOARD:
            keyboard = event.content.keyboard
            if (
                keyboard.type not in (dvz.DVZ_KEYBOARD_EVENT_PRESS, dvz.DVZ_KEYBOARD_EVENT_REPEAT)
                or owner._hovered_slice_axis is None
            ):
                return
            if keyboard.key in (dvz.DVZ_KEY_RIGHT_BRACKET, dvz.DVZ_KEY_PAGE_UP):
                direction = 1
            elif keyboard.key in (dvz.DVZ_KEY_LEFT_BRACKET, dvz.DVZ_KEY_PAGE_DOWN):
                direction = -1
            else:
                return
            step = key_step(direction, shift=bool(keyboard.mods & dvz.DVZ_KEY_MODIFIER_SHIFT))
            if owner.step_slice(owner._hovered_slice_axis, step):
                dvz.dvz_view_request_frame(owner.view)
            return
        if event.type != dvz.DVZ_INPUT_EVENT_POINTER:
            return
        pointer = event.content.pointer
        hit = self.slice_data_at_pointer(pointer)
        if hit is None:
            if pointer.type == dvz.DVZ_POINTER_EVENT_MOVE and owner._set_slice_hover(None):
                dvz.dvz_view_request_frame(owner.view)
            return
        axis, x, y = hit
        if pointer.type == dvz.DVZ_POINTER_EVENT_MOVE:
            if owner._set_slice_hover(axis, x, y):
                dvz.dvz_view_request_frame(owner.view)
            return
        if pointer.type == dvz.DVZ_POINTER_EVENT_WHEEL:
            amount = float(pointer.content.w.dir[1])
            if pointer.mods & dvz.DVZ_KEY_MODIFIER_CONTROL:
                if amount:
                    owner._slice_zoom[axis] = wheel_zoom(owner._slice_zoom[axis], amount)
                    owner._update_slice_geometry(axis)
                    dvz.dvz_view_request_frame(owner.view)
                return
            if amount:
                step, remainder = wheel_step(
                    owner._slice_wheel_accumulator[axis], amount,
                    shift=bool(pointer.mods & dvz.DVZ_KEY_MODIFIER_SHIFT),
                )
                owner._slice_wheel_accumulator[axis] = remainder
                if step and owner.step_slice(axis, step):
                    dvz.dvz_view_request_frame(owner.view)
            return
        if pointer.type == dvz.DVZ_POINTER_EVENT_DOUBLE_CLICK:
            owner._slice_zoom[axis] = 1.0
            owner._update_slice_geometry(axis)
            dvz.dvz_view_request_frame(owner.view)
            return
        if (
            pointer.type == dvz.DVZ_POINTER_EVENT_CLICK
            and pointer.button == dvz.DVZ_POINTER_BUTTON_LEFT
            and owner.set_cursor_from_slice_data(axis, x, y, select_region=False)
        ):
            dvz.dvz_view_request_frame(owner.view)
