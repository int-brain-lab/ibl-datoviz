import ctypes
from types import SimpleNamespace

import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.ontology import encode_region_key
from ibl_datoviz.viewport_input import ViewportInputAdapter
from tests.test_atlas import FIXTURE, FakeDatoviz


class FakeViewportDatoviz(FakeDatoviz):
    DVZ_INPUT_EVENT_POINTER = 1
    DVZ_POINTER_EVENT_PRESS = 1
    DVZ_POINTER_EVENT_RELEASE = 0
    DVZ_POINTER_EVENT_MOVE = 2
    DVZ_POINTER_EVENT_DRAG_START = 10
    DVZ_POINTER_EVENT_DRAG = 11
    DVZ_POINTER_EVENT_DRAG_STOP = 12

    def dvz_hover_clear(self, _hover):
        self.mesh_hover = None
        self.calls.append(('hover_clear',))
        return 0

    def dvz_input_subscribe_event(self, _router, callback, _data):
        self.callback = callback
        return 0 if self.fail_on == 'subscription' else 17

    def dvz_input_unsubscribe(self, _router, subscription):
        assert self.callback is not None
        self.calls.append(('unsubscribe', subscription))
        self.callback = None
        return True


class FakeAppConfig(ctypes.Structure):
    _fields_ = [('font_ui_size_px', ctypes.c_float)]


dvz = FakeViewportDatoviz


def emit(adapter, event_type):
    event = SimpleNamespace(
        type=dvz.DVZ_INPUT_EVENT_POINTER,
        content=SimpleNamespace(pointer=SimpleNamespace(type=event_type)),
    )
    adapter.on_input(None, SimpleNamespace(contents=event), None)


@pytest.fixture
def viewer():
    with AtlasViewer(AtlasMesh.from_pack(FIXTURE), datoviz=FakeViewportDatoviz()) as owner:
        owner._viewport_input = ViewportInputAdapter(owner, object())
        yield owner


@pytest.mark.parametrize('start', [dvz.DVZ_POINTER_EVENT_PRESS, dvz.DVZ_POINTER_EVENT_DRAG_START])
def test_camera_gesture_clears_hover_preserves_selection_and_waits_for_fresh_move(viewer, start):
    adapter, fake = viewer._viewport_input, viewer.dvz
    viewer.set_selected_region_ids((315,))
    fake.mesh_hover = encode_region_key(-315)
    viewer._sync_viewport_hover(True)
    assert viewer._hovered_region_ids == (-315,)
    emit(adapter, start)
    assert viewer._hovered_region_ids == ()
    assert fake.mesh_hover is None
    assert viewer.selected_region_ids() == (315,)
    before = len(fake.calls)
    emit(adapter, dvz.DVZ_POINTER_EVENT_DRAG)
    assert not any(call[:3] == ('data', 'mesh', 'color') for call in fake.calls[before:])
    emit(adapter, dvz.DVZ_POINTER_EVENT_DRAG_STOP)
    emit(adapter, dvz.DVZ_POINTER_EVENT_RELEASE)
    # A query queued before the gesture must not reintroduce stale hover on release.
    fake.mesh_hover = encode_region_key(997)
    viewer._sync_viewport_hover(True)
    assert viewer._hovered_region_ids == ()
    assert fake.mesh_hover is None
    emit(adapter, dvz.DVZ_POINTER_EVENT_MOVE)
    fake.mesh_hover = encode_region_key(997)
    viewer._sync_viewport_hover(True)
    assert viewer._hovered_region_ids == (997,)
    assert viewer.selected_region_ids() == (315,)


def test_pressed_pointer_motion_does_not_resume_hover(viewer):
    adapter = viewer._viewport_input
    emit(adapter, dvz.DVZ_POINTER_EVENT_PRESS)
    emit(adapter, dvz.DVZ_POINTER_EVENT_MOVE)
    assert adapter.suspended
    emit(adapter, dvz.DVZ_POINTER_EVENT_RELEASE)
    assert adapter.suspended
    emit(adapter, dvz.DVZ_POINTER_EVENT_MOVE)
    assert not adapter.suspended


def test_viewer_unsubscribes_once_before_scene_teardown(viewer):
    adapter, fake = viewer._viewport_input, viewer.dvz
    adapter.subscribe()
    adapter.subscribe()
    viewer.close()
    viewer.close()
    assert fake.calls.count(('unsubscribe', 17)) == 1
    assert fake.calls.index(('unsubscribe', 17)) < fake.calls.index(('destroy_scene',))
    assert adapter.callback is None


def test_failed_subscription_leaves_cleanup_safe(viewer):
    adapter = viewer._viewport_input
    viewer.dvz.fail_on = 'subscription'
    with pytest.raises(RuntimeError, match='subscribe_event'):
        adapter.subscribe()
    viewer.close()
    assert adapter.callback is None
    assert not any(call[0] == 'unsubscribe' for call in viewer.dvz.calls)


def test_gui_font_size_is_configured_before_app_creation(viewer, monkeypatch):
    configured = []
    viewer.catalog = object()
    monkeypatch.setattr(viewer.dvz, 'dvz_app_config', FakeAppConfig, raising=False)

    def create_app(_scene, config):
        configured.append(config._obj.font_ui_size_px)

    monkeypatch.setattr(viewer.dvz, 'dvz_app_with_config', create_app, raising=False)
    with pytest.raises(RuntimeError, match='dvz_app'):
        viewer._create_view(offscreen=False, title='test')
    assert configured == [18.0]


@pytest.mark.parametrize('layout', ['3d', 'linked'])
def test_right_click_uses_shared_pointer_conversion_without_constructing_slice_adapter(
    viewer, monkeypatch, layout
):
    """Observation picking works in both layouts, independent of linked ownership."""
    requests, conversions, frames = [], [], []
    native = viewer.dvz

    class Resize(ctypes.Structure):
        _fields_ = [('unused', ctypes.c_int)]

    def to_layout(figure, x, y, width, height, scale_x, scale_y, out_x, out_y):
        conversions.append((figure, x, y, width, height, scale_x, scale_y))
        out_x._obj.value, out_y._obj.value = 52.0, 61.0
        return True

    def to_panel(panel, _source_space, _target_space, source, target):
        assert panel is viewer.panel
        assert tuple(source) == (52.0, 61.0)
        target[:] = (12.0, 21.0)
        return True

    with monkeypatch.context() as patch:
        patch.setattr(native, 'DVZ_POINTER_EVENT_CLICK', 3, raising=False)
        patch.setattr(native, 'DVZ_POINTER_BUTTON_RIGHT', 1, raising=False)
        patch.setattr(native, 'DVZ_PANEL_COORD_FIGURE_PX', 1, raising=False)
        patch.setattr(native, 'DVZ_PANEL_COORD_PANEL_PX', 2, raising=False)
        patch.setattr(native, 'DvzInputResizeEvent', Resize, raising=False)
        patch.setattr(native, 'dvz_input_router_last_resize', lambda *_: False, raising=False)
        patch.setattr(native, 'dvz_figure_window_to_layout', to_layout, raising=False)
        patch.setattr(native, 'dvz_panel_transform_point', to_panel, raising=False)
        patch.setattr(native, 'dvz_view_request_frame', frames.append, raising=False)
        patch.setattr(
            viewer, 'picking', SimpleNamespace(request=lambda *pos: requests.append(pos))
        )
        if layout == 'linked':
            patch.setattr(viewer, '_linked', SimpleNamespace(_cancel_auto_slice=lambda: None))
        pointer = SimpleNamespace(
            type=3, button=1, pos=(80.0, 90.0), window_size=(640, 480), content_scale=2.0
        )
        event = SimpleNamespace(
            type=native.DVZ_INPUT_EVENT_POINTER, content=SimpleNamespace(pointer=pointer)
        )
        viewer._viewport_input.on_input(None, SimpleNamespace(contents=event), None)
        assert viewer._gui_callback_error is None
        assert requests == [(12.0, 21.0)]
        assert frames == [viewer.view]
        assert conversions == [(viewer.figure, 80.0, 90.0, 640.0, 480.0, 2.0, 2.0)]


@pytest.mark.parametrize('event_type', [1, 3, 4])
def test_manual_viewport_input_cancels_pending_linked_navigation(event_type):
    """Manual press, click and wheel supersede an outstanding region-list jump."""
    cancelled = []
    native = FakeViewportDatoviz()
    native.DVZ_POINTER_EVENT_CLICK, native.DVZ_POINTER_EVENT_WHEEL = 3, 4
    owner = SimpleNamespace(
        dvz=native,
        _linked=SimpleNamespace(_cancel_auto_slice=lambda: cancelled.append(True)),
        _invalidate_picking=lambda: None,
        _clear_surface_hover=lambda: None,
    )
    adapter = ViewportInputAdapter(owner, object())
    emit(adapter, event_type)
    assert cancelled == [True]
