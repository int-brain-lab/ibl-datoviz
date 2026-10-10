from types import SimpleNamespace

import datoviz as dvz
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.ontology import encode_region_key
from ibl_datoviz.viewport_input import ViewportInputAdapter
from tests.test_atlas import FIXTURE, FakeDatoviz


class FakeViewportDatoviz(FakeDatoviz):
    DVZ_INPUT_EVENT_POINTER = dvz.DVZ_INPUT_EVENT_POINTER
    DVZ_POINTER_EVENT_PRESS = dvz.DVZ_POINTER_EVENT_PRESS
    DVZ_POINTER_EVENT_RELEASE = dvz.DVZ_POINTER_EVENT_RELEASE
    DVZ_POINTER_EVENT_MOVE = dvz.DVZ_POINTER_EVENT_MOVE
    DVZ_POINTER_EVENT_DRAG_START = dvz.DVZ_POINTER_EVENT_DRAG_START
    DVZ_POINTER_EVENT_DRAG = dvz.DVZ_POINTER_EVENT_DRAG
    DVZ_POINTER_EVENT_DRAG_STOP = dvz.DVZ_POINTER_EVENT_DRAG_STOP

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
    monkeypatch.setattr(viewer.dvz, 'dvz_app_config', lambda: dvz.DvzAppConfig(), raising=False)

    def create_app(_scene, config):
        configured.append(config._obj.font_ui_size_px)

    monkeypatch.setattr(viewer.dvz, 'dvz_app_with_config', create_app, raising=False)
    with pytest.raises(RuntimeError, match='dvz_app'):
        viewer._create_view(offscreen=False, title='test')
    assert configured == [18.0]
