import ctypes
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import LinkedAtlasNavigator
from ibl_datoviz.slice_input import (
    PointerLayoutInputs,
    SliceInputAdapter,
    key_step,
    pointer_layout_inputs,
    wheel_step,
    wheel_zoom,
)
from ibl_datoviz.viewer import AtlasViewer


def test_fractional_wheel_keeps_remainder_and_signed_steps():
    step, remainder = wheel_step(0.0, 0.2, shift=False)
    assert step == 0
    assert remainder == pytest.approx(0.4)
    step, remainder = wheel_step(remainder, 0.4, shift=False)
    assert step == 1
    assert remainder == pytest.approx(0.2)
    assert wheel_step(0.0, -0.25, shift=True) == (-2, -0.5)
    assert wheel_step(-0.5, -0.25, shift=True) == (-3, 0.0)


@pytest.mark.parametrize('direction', [-1, 1])
def test_key_step_preserves_direction_and_shift(direction):
    assert key_step(direction, shift=False) == direction
    assert key_step(direction, shift=True) == direction * 5


def test_zoom_clamps_both_limits():
    assert wheel_zoom(1.0, -10) == 1.0
    assert wheel_zoom(8.0, 10) == 8.0
    assert wheel_zoom(2.0, 1) == pytest.approx(2.16)


def test_pointer_layout_uses_resize_fallback_and_per_axis_hidpi_scale():
    resize = SimpleNamespace(
        window_width=800, window_height=600, content_scale_x=2.0, content_scale_y=1.5
    )
    assert pointer_layout_inputs((np.nan, 0), np.nan, resize) == PointerLayoutInputs(
        800, 600, 2.0, 1.5
    )
    assert pointer_layout_inputs((640, 480), 2.0, resize) == PointerLayoutInputs(
        640, 480, 2.0, 1.5
    )
    assert pointer_layout_inputs((640, 480), -1) == PointerLayoutInputs(640, 480, 1, 1)


@pytest.fixture
def adapter():
    names = (
        'DVZ_INPUT_EVENT_KEYBOARD', 'DVZ_INPUT_EVENT_POINTER', 'DVZ_KEYBOARD_EVENT_PRESS',
        'DVZ_KEYBOARD_EVENT_REPEAT', 'DVZ_KEY_RIGHT_BRACKET', 'DVZ_KEY_PAGE_UP',
        'DVZ_KEY_LEFT_BRACKET', 'DVZ_KEY_PAGE_DOWN', 'DVZ_POINTER_EVENT_MOVE',
        'DVZ_POINTER_EVENT_WHEEL', 'DVZ_POINTER_EVENT_DOUBLE_CLICK',
        'DVZ_POINTER_EVENT_CLICK', 'DVZ_POINTER_BUTTON_LEFT',
    )
    dvz = SimpleNamespace(**{name: index + 10 for index, name in enumerate(names)})
    dvz.DVZ_KEY_MODIFIER_CONTROL = 1
    dvz.DVZ_KEY_MODIFIER_SHIFT = 2
    calls = []
    dvz.dvz_view_request_frame = lambda _view: calls.append(('frame',))
    owner = SimpleNamespace(
        dvz=dvz, view=object(), _hovered_slice_axis=None,
        _slice_zoom={'dv': 1.0}, _slice_wheel_accumulator={'dv': 0.0},
        step_slice=lambda *args: calls.append(('step', *args)) or True,
        _set_slice_hover=lambda *args: calls.append(('hover', *args)) or True,
        _update_slice_geometry=lambda axis: calls.append(('geometry', axis)),
        set_cursor_from_slice_data=lambda *args, **kwargs: (
            calls.append(('cursor', *args, kwargs)) or True
        ),
    )
    result = SliceInputAdapter(owner, object())
    result.slice_data_at_pointer = lambda _pointer: ('dv', 0.2, 0.4)
    return result, calls


def dispatch(adapter, *, pointer=None, keyboard=None):
    kind = 'DVZ_INPUT_EVENT_POINTER' if pointer is not None else 'DVZ_INPUT_EVENT_KEYBOARD'
    content = SimpleNamespace(pointer=pointer, keyboard=keyboard)
    event = SimpleNamespace(type=getattr(adapter.owner.dvz, kind), content=content)
    adapter.on_input(None, SimpleNamespace(contents=event), None)


def test_keyboard_requires_hover_and_recognized_press(adapter):
    adapter, calls = adapter
    dvz = adapter.owner.dvz
    keyboard = SimpleNamespace(
        type=dvz.DVZ_KEYBOARD_EVENT_PRESS, key=dvz.DVZ_KEY_PAGE_UP, mods=2
    )
    dispatch(adapter, keyboard=keyboard)
    assert calls == []
    adapter.owner._hovered_slice_axis = 'dv'
    dispatch(adapter, keyboard=keyboard)
    assert calls == [('step', 'dv', 5), ('frame',)]
    calls.clear()
    keyboard.type = 999
    dispatch(adapter, keyboard=keyboard)
    keyboard.type, keyboard.key = dvz.DVZ_KEYBOARD_EVENT_REPEAT, 999
    dispatch(adapter, keyboard=keyboard)
    assert calls == []


def test_pointer_move_enters_and_exits_hover(adapter):
    adapter, calls = adapter
    pointer = SimpleNamespace(type=adapter.owner.dvz.DVZ_POINTER_EVENT_MOVE)
    dispatch(adapter, pointer=pointer)
    assert calls == [('hover', 'dv', 0.2, 0.4), ('frame',)]
    adapter.slice_data_at_pointer = lambda _pointer: None
    calls.clear()
    dispatch(adapter, pointer=pointer)
    assert calls == [('hover', None), ('frame',)]


def test_control_wheel_precedes_shift_and_double_click_resets_zoom(adapter):
    adapter, calls = adapter
    dvz = adapter.owner.dvz
    pointer = SimpleNamespace(
        type=dvz.DVZ_POINTER_EVENT_WHEEL, mods=3,
        content=SimpleNamespace(w=SimpleNamespace(dir=(0, 1))),
    )
    dispatch(adapter, pointer=pointer)
    assert adapter.owner._slice_zoom['dv'] == pytest.approx(1.08)
    assert adapter.owner._slice_wheel_accumulator['dv'] == 0.0
    assert calls == [('geometry', 'dv'), ('frame',)]
    calls.clear()
    pointer.mods = 2
    dispatch(adapter, pointer=pointer)
    assert calls == [('step', 'dv', 10), ('frame',)]
    calls.clear()
    pointer.type = dvz.DVZ_POINTER_EVENT_DOUBLE_CLICK
    dispatch(adapter, pointer=pointer)
    assert adapter.owner._slice_zoom['dv'] == 1.0
    assert calls == [('geometry', 'dv'), ('frame',)]


def test_slice_left_click_moves_cursor_without_selection(adapter):
    adapter, calls = adapter
    dvz = adapter.owner.dvz
    pointer = SimpleNamespace(type=dvz.DVZ_POINTER_EVENT_CLICK, button=999)
    dispatch(adapter, pointer=pointer)
    assert calls == []
    pointer.button = dvz.DVZ_POINTER_BUTTON_LEFT
    dispatch(adapter, pointer=pointer)
    assert calls == [('cursor', 'dv', 0.2, 0.4, {'select_region': False}), ('frame',)]


def test_subscription_retains_callback_until_unsubscribed_once(adapter):
    adapter, _calls = adapter
    events = []
    callback = adapter.callback
    dvz = adapter.owner.dvz
    dvz.dvz_input_subscribe_event = lambda *_args: events.append('subscribe') or 17

    def unsubscribe(router, subscription):
        assert router is adapter.router
        assert subscription == 17
        assert adapter.callback is callback
        events.append('unsubscribe')

    dvz.dvz_input_unsubscribe = unsubscribe
    adapter.subscribe()
    adapter.subscribe()
    adapter.close()
    adapter.close()
    assert events == ['subscribe', 'unsubscribe']
    assert adapter.callback is None


def test_failed_subscription_can_be_cleaned_up(adapter):
    adapter, _calls = adapter
    adapter.owner.dvz.dvz_input_subscribe_event = lambda *_args: 0
    with pytest.raises(RuntimeError, match='subscribe'):
        adapter.subscribe()
    assert adapter.callback is not None
    adapter.close()
    assert adapter.callback is None


def test_native_pointer_conversion_receives_resolved_dimensions(adapter):
    adapter, _calls = adapter
    dvz = adapter.owner.dvz
    adapter.owner.figure = object()

    class Resize(ctypes.Structure):
        _fields_ = [
            ('window_width', ctypes.c_float), ('window_height', ctypes.c_float),
            ('content_scale_x', ctypes.c_float), ('content_scale_y', ctypes.c_float),
        ]

    dvz.DvzInputResizeEvent = Resize

    def last_resize(_router, pointer):
        resize = pointer._obj
        resize.window_width, resize.window_height = 800, 600
        resize.content_scale_x, resize.content_scale_y = 2, 1.5
        return True

    def convert(figure, x, y, width, height, scale_x, scale_y, out_x, out_y):
        assert figure is adapter.owner.figure
        assert (x, y, width, height, scale_x, scale_y) == (12, 18, 800, 600, 2, 1.5)
        out_x._obj.value, out_y._obj.value = 24, 27
        return True

    dvz.dvz_input_router_last_resize = last_resize
    dvz.dvz_figure_window_to_layout = convert
    pointer = SimpleNamespace(pos=(12, 18), window_size=(0, np.nan), content_scale=np.nan)
    assert adapter.pointer_figure_position(pointer) == (24, 27)
    dvz.dvz_figure_window_to_layout = lambda *_args: False
    assert adapter.pointer_figure_position(pointer) is None


def test_navigator_wires_and_closes_subscription_before_scene(monkeypatch):
    calls = []
    router = object()
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    viewer._slice_loader = None
    viewer._slice_input = None
    viewer._input_subscription = 0
    viewer.viewport = object()
    viewer.dvz = SimpleNamespace(
        dvz_gui_viewport_input=lambda _viewport: router,
        dvz_input_subscribe_event=lambda *_args: 17,
        dvz_input_unsubscribe=lambda *_args: calls.append('unsubscribe'),
    )
    monkeypatch.setattr(AtlasViewer, '_create_view', lambda *_args, **_kwargs: None)
    original_close = AtlasViewer.close

    def close_scene(owner):
        if owner is viewer:
            calls.append('scene')
        else:
            original_close(owner)

    monkeypatch.setattr(AtlasViewer, 'close', close_scene)
    viewer._create_view(offscreen=False, title='test')
    assert viewer._slice_input.callback is viewer._input_callback
    assert viewer._input_subscription == 17
    viewer.close()
    assert calls == ['unsubscribe', 'scene']
    assert viewer._slice_input is viewer._input_callback is None
    assert viewer._input_subscription == 0


def test_navigator_failed_subscription_leaves_cleanup_safe(monkeypatch):
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    viewer._slice_loader = None
    viewer._slice_input = None
    viewer._input_subscription = 0
    viewer.viewport = object()
    viewer.dvz = SimpleNamespace(
        dvz_gui_viewport_input=lambda _viewport: object(),
        dvz_input_subscribe_event=lambda *_args: 0,
    )
    monkeypatch.setattr(AtlasViewer, '_create_view', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(AtlasViewer, 'close', lambda _viewer: None)
    with pytest.raises(RuntimeError, match='subscribe'):
        viewer._create_view(offscreen=False, title='test')
    assert viewer._input_callback is not None
    viewer.close()
    assert viewer._slice_input is viewer._input_callback is None
