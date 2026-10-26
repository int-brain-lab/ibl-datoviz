"""Owner-thread recovery for simultaneous asynchronous slice outcomes."""

from threading import Event, get_ident
from types import SimpleNamespace

from ibl_datoviz import AtlasViewer
from ibl_datoviz.linked_atlas import LinkedSlices
from ibl_datoviz.slice_scheduler import SliceRequest, SliceScheduler
from ibl_datoviz.viewer_layout import ViewerLayout


def test_navigator_retries_queued_success_without_new_cursor_request():
    notified = {axis: Event() for axis in ('ap', 'ml', 'dv')}
    owner = get_ident()
    uploads = []
    frames = []

    def prepare(request):
        assert get_ident() != owner
        if request.axis != 'dv':
            raise ValueError(f'{request.axis} failed')
        return request.index

    scheduler = SliceScheduler(prepare, notify=lambda axis: notified[axis].set())
    # Exercise the real callback without creating native scene resources.
    navigator = LinkedSlices.__new__(LinkedSlices)
    navigator.viewer = SimpleNamespace(_check=AtlasViewer._check)
    navigator._auto_slice = None
    navigator._slice_loader = scheduler
    navigator.viewer._closed = False
    navigator._slice_error = None
    navigator.viewer._hovered_region_ids = ()
    navigator.viewer.view = object()
    navigator.viewer.dvz = SimpleNamespace(dvz_view_request_frame=frames.append)

    def upload(request, payload):
        assert get_ident() == owner
        uploads.append((request.axis, payload))

    navigator._upload_slice_payload = upload
    try:
        for axis in notified:
            scheduler.submit(SliceRequest(axis, 7, 1))
        assert all(event.wait(2) for event in notified.values())
        # Notifications are already coalesced. Each failure must schedule a
        # subsequent owner frame rather than waiting for another cursor move.
        for expected_error in ('ap failed', 'ml failed'):
            navigator._process_gui_frame()
            assert str(navigator._slice_error) == expected_error
            assert frames.pop() is navigator.viewer.view
            assert uploads == []
        navigator._process_gui_frame()
        assert uploads == [('dv', 7)]
        assert navigator._slice_error is None
        assert frames.pop() is navigator.viewer.view
    finally:
        scheduler.close()


def test_completed_slices_are_processed_when_sidebar_is_not_drawn():
    navigator = LinkedSlices.__new__(LinkedSlices)
    navigator.viewer = SimpleNamespace(_check=AtlasViewer._check)
    navigator._auto_slice = None
    navigator._slice_loader = object()
    navigator.viewer._closed = False
    navigator.viewer.view = object()
    navigator.viewer.viewport = None
    navigator.viewer.sidebar_width = 300
    navigator.viewer.ui_scale = 1.5
    processed = []
    navigator._drain_prepared_slices = lambda view, _: processed.append(view)
    navigator._draw_extra_gui = lambda _: (_ for _ in ()).throw(
        AssertionError('settings must stay unopened')
    )
    navigator.viewer.dvz = SimpleNamespace(
        DVZ_GUI_DOCK_SLOT_LEFT=0,
        dvz_gui_dock_window_once=lambda *_: None,
        dvz_gui_begin=lambda *_: False,
        dvz_gui_end=lambda *_: None,
    )
    navigator.viewer._linked = navigator
    navigator.viewer._process_gui_frame = lambda: navigator._process_gui_frame()
    navigator.viewer._draw_viewport_toolbar_gui = lambda _: None
    navigator.viewer._dock_gui_windows = lambda _: None
    navigator.viewer._draw_sidebar_gui = lambda _: None
    navigator.viewer._draw_data_tables_gui = lambda _: None
    navigator.viewer._draw_auxiliary_gui = lambda _: None
    navigator.viewer._draw_scientific_layers_gui = lambda _: None
    navigator.viewer._window = ViewerLayout(navigator.viewer)
    AtlasViewer._draw_gui_frame(navigator.viewer, None)
    assert processed == [navigator.viewer.view]


def test_posted_native_upload_failure_stops_without_destroying_inside_callback():
    navigator = LinkedSlices.__new__(LinkedSlices)
    navigator.viewer = SimpleNamespace(_check=AtlasViewer._check)
    navigator._auto_slice = None
    error = RuntimeError('native upload failed')
    navigator.viewer._closed = False
    navigator.viewer._hovered_region_ids = ()
    navigator.viewer.app = object()
    stopped = []
    navigator.viewer.dvz = SimpleNamespace(dvz_app_stop=stopped.append)
    navigator._slice_loader = SimpleNamespace(
        drain_ready=lambda: [SimpleNamespace(request=SliceRequest('ap', 1, 2), payload=None)]
    )

    def fail(*_):
        raise error

    navigator._upload_slice_payload = fail
    navigator._drain_prepared_slices(None, None)
    assert navigator.viewer._gui_callback_error is error and navigator._slice_error is error
    assert navigator.viewer._close_pending and stopped == [navigator.viewer.app]
    assert not navigator.viewer._closed
    navigator.viewer._closed = True
