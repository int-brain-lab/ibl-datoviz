"""Owner-thread recovery for simultaneous asynchronous slice outcomes."""

from threading import Event, get_ident
from types import SimpleNamespace

from ibl_datoviz import LinkedAtlasNavigator
from ibl_datoviz.slice_scheduler import SliceRequest, SliceScheduler


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
    navigator = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    navigator._slice_loader = scheduler
    navigator._closed = False
    navigator._slice_error = None
    navigator._hovered_region_ids = ()
    navigator.view = object()
    navigator.dvz = SimpleNamespace(dvz_view_request_frame=frames.append)

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
            navigator._drain_prepared_slices(navigator.view, None)
            assert str(navigator._slice_error) == expected_error
            assert frames.pop() is navigator.view
            assert uploads == []
        navigator._drain_prepared_slices(navigator.view, None)
        assert uploads == [('dv', 7)]
        assert navigator._slice_error is None
        assert frames.pop() is navigator.view
    finally:
        scheduler.close()
