from __future__ import annotations

from threading import Event
from time import monotonic, sleep

import pytest

from ibl_datoviz.slice_scheduler import PreparedSlice, SliceRequest, SliceScheduler


def wait_until(predicate, timeout=2.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.005)
    assert predicate()


def test_request_is_immutable_and_carries_complete_presentation_state():
    request = SliceRequest(
        'ap',
        17,
        4,
        source_id='allen-ccfv3-10um',
        mapping='beryl',
        selected_region_ids=(3, 7),
    )
    assert request.source_id == 'allen-ccfv3-10um'
    assert request.mapping == 'beryl'
    assert request.selected_region_ids == (3, 7)
    with pytest.raises(AttributeError):
        request.revision = 5


def test_old_revision_is_rejected_before_worker_submission():
    calls = []
    scheduler = SliceScheduler(lambda request: calls.append(request) or request.index)
    try:
        assert scheduler.submit(SliceRequest('dv', 2, 8))
        assert not scheduler.submit(SliceRequest('dv', 1, 7))
        assert not scheduler.submit(SliceRequest('dv', 2, 8))
        wait_until(lambda: bool(scheduler.drain_ready()))
        assert [request.revision for request in calls] == [8]
    finally:
        scheduler.close()


def test_inflight_result_is_dropped_when_newer_revision_arrives():
    started = Event()
    release = Event()
    calls = []

    def prepare(request):
        calls.append(request.revision)
        if request.revision == 1:
            started.set()
            release.wait(2)
        return request.index

    scheduler = SliceScheduler(prepare, max_workers=1)
    try:
        scheduler.submit(SliceRequest('ml', 10, 1))
        assert started.wait(1)
        scheduler.submit(SliceRequest('ml', 20, 2))
        release.set()
        ready = []

        def collect():
            ready.extend(scheduler.drain_ready())
            return bool(ready)

        wait_until(collect)
        assert calls == [1, 2]
        # The only result observed by the owner is the latest request.
        assert [(item.request.revision, item.payload) for item in ready] == [(2, 20)]
    finally:
        scheduler.close()


def test_axes_progress_independently_and_result_is_paired():
    scheduler = SliceScheduler(lambda request: (request.axis, request.index), max_workers=2)
    try:
        scheduler.submit(SliceRequest('ap', 4, 1))
        scheduler.submit(SliceRequest('dv', 9, 1))
        ready = []

        def collect():
            ready.extend(scheduler.drain_ready())
            return len(ready) == 2

        wait_until(collect)
        assert {(item.request.axis, item.request.index, item.payload) for item in ready} == {
            ('ap', 4, ('ap', 4)),
            ('dv', 9, ('dv', 9)),
        }
    finally:
        scheduler.close()


def test_prepared_slice_is_request_result_pair():
    item = PreparedSlice(SliceRequest('ap', 1, 1), b'payload')
    assert item.request.axis == 'ap'
    assert item.payload == b'payload'
