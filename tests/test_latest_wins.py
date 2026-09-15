from __future__ import annotations

from threading import Event, Lock
from time import monotonic, sleep

import pytest

from ibl_datoviz.latest_wins import LatestWinsExecutor


def wait_until(predicate, timeout=2.0):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.005)
    assert predicate()


def test_stale_result_never_drains_and_ready_is_bounded():
    started = Event()
    release = Event()
    calls = []

    def prepare(token):
        calls.append(token)
        if token == 1:
            started.set()
            release.wait(2)
        return token * 10

    queue = LatestWinsExecutor(prepare, max_workers=1)
    try:
        queue.request('x', 1)
        assert started.wait(1)
        for token in range(2, 20):
            queue.request('x', token)
        release.set()
        wait_until(lambda: 19 in calls)
        # The first result and all intermediate pending requests were dropped.
        assert [(item.token, item.result) for item in queue.drain_ready()] == [(19, 190)]
        assert queue.drain_ready() == []
        assert calls == [1, 19]
    finally:
        queue.close()


def test_independent_keys_progress_concurrently():
    entered = {key: Event() for key in ('x', 'y')}
    release = Event()
    notified = []

    def prepare(token):
        entered[token].set()
        release.wait(2)
        return token

    queue = LatestWinsExecutor(prepare, notify=notified.append, max_workers=2)
    try:
        queue.request('x', 'x')
        queue.request('y', 'y')
        assert entered['x'].wait(1)
        assert entered['y'].wait(1)
        release.set()
        wait_until(lambda: len(notified) == 2)
        assert len(queue.drain_ready()) == 2
    finally:
        queue.close()


def test_worker_exception_is_raised_on_drain():
    failure = ValueError('decode failed')
    notified = Event()
    queue = LatestWinsExecutor(
        lambda token: (_ for _ in ()).throw(failure),
        notify=lambda _key: notified.set(),
        max_workers=1,
    )
    try:
        queue.request('axis', object())
        assert notified.wait(1)
        with pytest.raises(ValueError, match='decode failed'):
            queue.drain_ready()
    finally:
        queue.close()


def test_close_rejects_new_work_and_is_idempotent():
    queue = LatestWinsExecutor(lambda token: token)
    queue.close()
    queue.close()
    with pytest.raises(RuntimeError, match='closed'):
        queue.request('x', 1)


def test_notify_only_wakes_owner_and_does_not_drain():
    notified = []
    lock = Lock()
    queue = LatestWinsExecutor(
        lambda token: token + 1,
        notify=lambda key: _append(notified, lock, key),
    )
    try:
        queue.request('x', 3)
        wait_until(lambda: _notified(notified, lock))
        assert queue.drain_ready()[0].result == 4
    finally:
        queue.close()


def _append(values, lock, value):
    with lock:
        values.append(value)


def _notified(values, lock):
    with lock:
        return bool(values)
