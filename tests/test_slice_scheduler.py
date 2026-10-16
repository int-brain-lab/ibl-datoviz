from __future__ import annotations

from threading import Event, Thread
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


def test_failed_axis_preserves_another_axis_and_can_resume():
    notified = {axis: Event() for axis in ('ap', 'dv')}

    def prepare(request):
        if request.axis == 'ap' and request.revision == 1:
            raise ValueError('AP preparation failed')
        return request.index

    scheduler = SliceScheduler(prepare, notify=lambda axis: notified[axis].set())
    try:
        scheduler.submit(SliceRequest('dv', 9, 1))
        scheduler.submit(SliceRequest('ap', 4, 1))
        assert all(event.wait(2) for event in notified.values())
        with pytest.raises(ValueError, match='AP preparation failed'):
            scheduler.drain_ready()
        assert scheduler.drain_ready() == [PreparedSlice(SliceRequest('dv', 9, 1), 9)]
        notified['ap'].clear()
        scheduler.submit(SliceRequest('ap', 5, 2))
        assert notified['ap'].wait(2)
        assert scheduler.drain_ready() == [PreparedSlice(SliceRequest('ap', 5, 2), 5)]
    finally:
        scheduler.close()


def test_optional_cancellable_callback_reports_real_current_errors_once():
    notified = {axis: Event() for axis in ('ap', 'dv')}

    def ordinary(_request):
        raise AssertionError('the explicitly supplied cooperative callback should run')

    def cancellable(request, is_current):
        assert is_current()
        if request.axis == 'ap':
            raise ValueError('current scientific preparation failed')
        return request.index

    scheduler = SliceScheduler(
        ordinary, prepare_cancellable=cancellable,
        notify=lambda axis: notified[axis].set(),
    )
    try:
        scheduler.submit(SliceRequest('ap', 1, 1))
        scheduler.submit(SliceRequest('dv', 2, 1))
        assert all(event.wait(2) for event in notified.values())
        with pytest.raises(ValueError, match='scientific preparation'):
            scheduler.drain_ready()
        assert scheduler.drain_ready() == [PreparedSlice(SliceRequest('dv', 2, 1), 2)]
        assert scheduler.drain_ready() == []
    finally:
        scheduler.close()


def test_close_invalidates_checkpoint_before_join_and_preserves_submission_state():
    started, release, closing = Event(), Event(), Event()
    notifications, checks = [], []

    def cancellable(_request, is_current):
        started.set()
        assert release.wait(2)
        checks.append(is_current())
        raise RuntimeError('obsolete cancellation or old source failure')

    scheduler = SliceScheduler(lambda _: None, prepare_cancellable=cancellable,
                               notify=notifications.append)
    original_close = scheduler._executor.close

    def joined_close():
        closing.set()
        original_close()

    scheduler._executor.close = joined_close
    scheduler.submit(SliceRequest('ap', 1, 5))
    assert started.wait(2)
    closer = Thread(target=scheduler.close)
    closer.start()
    try:
        assert closing.wait(2)
        assert closer.is_alive()
        # Even stale submissions must reject close before changing state.
        for revision in (1, 6):
            with pytest.raises(RuntimeError, match='closed'):
                scheduler.submit(SliceRequest('ap', 2, revision))
        assert scheduler.latest_revision('ap') == 5
        release.set()
        closer.join(2)
        assert not closer.is_alive()
        assert checks == [False] and notifications == []
        assert scheduler.drain_ready() == []
        scheduler.close()
    finally:
        release.set()
        closer.join(2)
        scheduler.close()
