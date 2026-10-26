"""Only current, explicit region-list intent may navigate linked slices."""

from threading import Event
from types import SimpleNamespace

import pytest

from ibl_datoviz.auto_slice import AutoSliceNavigation
from ibl_datoviz.interaction_benchmark import LinkedReadiness
from ibl_datoviz.latest_wins import LatestWinsExecutor

pytest_plugins = ('tests.test_linked_scientific_state', 'tests.test_region_navigation')


@pytest.mark.parametrize('fails', [False, True])
def test_cancel_discards_running_outcome_and_pending_work(fails):
    entered, release = Event(), Event()
    calls = []

    def prepare(token):
        calls.append(token)
        entered.set()
        release.wait(2)
        if fails:
            raise ValueError('stale failure')
        return token

    queue = LatestWinsExecutor(prepare, max_workers=1)
    try:
        queue.request('region', 1)
        assert entered.wait(1)
        queue.request('region', 2)
        queue.cancel('region')
        release.set()
        # A barrier on the same worker proves the canceled loop has exited.
        queue._executor.submit(lambda: None).result(timeout=1)
        assert calls == [1]
        assert queue.drain_ready() == []
    finally:
        queue.close()


def test_enable_only_affects_future_intent_and_latest_wins(source):
    ready = Event()
    owner = AutoSliceNavigation(source, notify=lambda _: ready.set())
    source.annotation[1, 2, 3] = 5
    source.annotation[2, 7, 3] = 6
    try:
        assert owner.enabled
        owner.request('allen', -315)
        assert ready.wait(1)
        owner.set_enabled(False)
        assert owner.drain() is None
        owner.request('allen', 315)
        assert owner.drain() is None
        owner.set_enabled(True)
        assert owner.drain() is None
        ready.clear()
        owner.request('allen', 315)
        assert ready.wait(1)
        assert owner.drain() == (2, 7, 3)
        assert owner.status == ''
        with pytest.raises(ValueError, match='boolean'):
            owner.set_enabled(1)
    finally:
        owner.close()


def test_navigation_stays_pending_until_anchor_is_accepted(source):
    entered, release, ready = Event(), Event(), Event()
    owner = AutoSliceNavigation(source, notify=lambda _: ready.set())
    anchor = owner.navigation.anchor

    def slow_anchor(mapping, region_id):
        entered.set()
        assert release.wait(2)
        return anchor(mapping, region_id)

    owner.navigation.anchor = slow_anchor
    try:
        owner.request('allen', -315)
        assert entered.wait(1)
        assert owner.pending
        assert owner.error is None
        assert owner.drain() is None
        assert owner.pending
        release.set()
        assert ready.wait(1)
        assert owner.drain() == anchor('allen', -315)
        assert not owner.pending
        assert owner.error is None
    finally:
        release.set()
        owner.close()


def test_cancel_clears_pending_and_discards_late_anchor(source):
    entered, release = Event(), Event()
    owner = AutoSliceNavigation(source)
    anchor = owner.navigation.anchor

    def slow_anchor(mapping, region_id):
        entered.set()
        assert release.wait(2)
        return anchor(mapping, region_id)

    owner.navigation.anchor = slow_anchor
    try:
        owner.request('allen', -315)
        assert entered.wait(1)
        assert owner.pending
        owner.cancel()
        assert not owner.pending
        release.set()
        owner._worker._executor.submit(lambda: None).result(timeout=1)
        assert owner.drain() is None
        assert not owner.pending
        assert owner.error is None
    finally:
        release.set()
        owner.close()


@pytest.mark.parametrize('resolve_by', ['new-request', 'cancel'])
def test_lookup_error_remains_visible_until_replaced_or_cancelled(source, resolve_by):
    ready = Event()
    owner = AutoSliceNavigation(source, notify=lambda _: ready.set())

    def fail(_mapping, _region_id):
        raise ValueError('anchor lookup failed')

    owner.navigation.anchor = fail
    try:
        owner.request('allen', -315)
        assert owner.pending
        assert ready.wait(1)
        assert owner.drain() is None
        assert not owner.pending
        assert isinstance(owner.error, ValueError)
        assert str(owner.error) == 'anchor lookup failed'
        assert owner.status == 'Auto-slice unavailable: anchor lookup failed'
        # Draining again must not erase the surfaced failure.
        assert owner.drain() is None
        assert str(owner.error) == 'anchor lookup failed'

        if resolve_by == 'cancel':
            owner.cancel()
            assert not owner.pending
            assert owner.error is None
        else:
            owner.navigation.anchor = lambda *_: (2, 7, 3)
            ready.clear()
            owner.request('allen', 315)
            assert owner.pending
            assert owner.error is None
            assert ready.wait(1)
            assert owner.drain() == (2, 7, 3)
            assert owner.error is None
            assert not owner.pending
    finally:
        owner.close()


def test_close_clears_pending_and_error_state(source):
    entered, release = Event(), Event()
    owner = AutoSliceNavigation(source)

    def slow_anchor(_mapping, _region_id):
        entered.set()
        assert release.wait(2)
        raise ValueError('closed lookup failure')

    owner.navigation.anchor = slow_anchor
    owner.request('allen', -315)
    assert entered.wait(1)
    assert owner.pending
    release.set()
    owner.close()
    assert not owner.pending
    assert owner.error is None


def test_request_submission_failure_sets_error_without_leaving_pending(source):
    owner = AutoSliceNavigation(source)

    def reject(_key, _token):
        raise RuntimeError('worker queue rejected request')

    owner._worker.request = reject
    try:
        with pytest.raises(RuntimeError, match='worker queue rejected request'):
            owner.request('allen', -315)
        assert not owner.pending
        assert isinstance(owner.error, RuntimeError)
        assert str(owner.error) == 'worker queue rejected request'
        assert owner.status == 'Auto-slice unavailable: worker queue rejected request'
    finally:
        owner.close()


def test_region_list_only_and_deselection_preserves_cursor(navigator):
    before = navigator._linked.cursor
    navigator.selection.set_regions((-315,), mapping='allen')
    assert navigator._linked.cursor == before
    candidate = SimpleNamespace(by_id={'315': SimpleNamespace(atlas_id=315)}, selected=['315'])
    ready = Event()
    navigator._linked._auto_slice._worker._notify = lambda _: ready.set()
    navigator._region_list_intent({'kind': 'select', 'id': '315'}, candidate)
    assert ready.wait(1)
    navigator._linked._drain_auto_slice()
    anchor = navigator._linked._auto_slice.navigation.anchor('allen', -315)
    assert navigator._linked.cursor.as_index() == anchor
    assert navigator.selection.regions == (('allen', -315),)
    candidate.selected = []
    navigator._region_list_intent({'kind': 'select', 'id': '315'}, candidate)
    assert navigator._linked._auto_slice.drain() is None


def test_checkpoint_waits_for_real_region_anchor_before_slice_readiness(navigator):
    owner = navigator._linked._auto_slice
    entered, release, ready = Event(), Event(), Event()
    original_anchor = owner.navigation.anchor
    owner._worker._notify = lambda _: ready.set()

    def delayed_anchor(mapping, region_id):
        entered.set()
        assert release.wait(2)
        return original_anchor(mapping, region_id)

    owner.navigation.anchor = delayed_anchor
    before = navigator._linked.cursor
    try:
        with LinkedReadiness(navigator) as readiness:
            owner.request('allen', -315)
            assert entered.wait(1)
            assert navigator._linked.cursor == before
            assert readiness.check().pending_navigation
            release.set()
            assert ready.wait(1)
            # Completed worker output is still not accepted scientific navigation.
            assert readiness.check().status == 'pending'
            navigator._linked._drain_auto_slice()
            assert navigator._linked.cursor.as_index() == original_anchor('allen', -315)
            accepted = readiness.check()
            assert not accepted.pending_navigation
            # This CPU navigator prepares slices without uploading native textures.
            assert accepted.status == 'pending' and accepted.pending_axes
    finally:
        release.set()


@pytest.mark.parametrize('cancel', ['manual', 'mapping', 'disabled', 'selection', 'direct'])
def test_new_navigation_intent_discards_ready_anchor(navigator, cancel):
    ready = Event()
    navigator._linked._auto_slice._worker._notify = lambda _: ready.set()
    navigator._linked._auto_slice.request('allen', -315)
    assert ready.wait(1)
    if cancel == 'manual':
        navigator._linked.set_cursor(navigator._linked.cursor)
    elif cancel == 'mapping':
        navigator.set_mapping('beryl')
    elif cancel == 'disabled':
        navigator.slices.set_auto_slice(False)
    elif cancel == 'selection':
        navigator.selection.set_regions((315,), mapping='allen')
    else:
        navigator._linked._cancel_auto_slice()
    before = navigator._linked.cursor
    navigator._linked._drain_auto_slice()
    assert navigator._linked.cursor == before


def test_closed_viewer_joins_auto_slice_worker(navigator):
    owner = navigator._linked._auto_slice
    navigator.close()
    assert navigator._linked._auto_slice is None
    with pytest.raises(RuntimeError, match='auto-slice navigation is closed'):
        owner.request('allen', -315)
    with pytest.raises(RuntimeError, match='closed'):
        owner._worker.request('region', ('allen', -315))


def test_native_post_auto_slice_upload_failure_is_contained(navigator, monkeypatch):
    monkeypatch.setattr(navigator._linked._auto_slice, 'drain', lambda: (0, 1, 0))

    def fail(*args, **kwargs):
        raise RuntimeError('auto-slice upload rejected')

    monkeypatch.setattr(navigator._linked, 'set_cursor', fail)
    navigator._linked._drain_prepared_slices(None, None)
    assert str(navigator._gui_callback_error) == 'auto-slice upload rejected'
    assert navigator._close_pending
    # The normal application frame finally releases the retained resources.
    navigator._close_pending = False


def test_persistent_projection_sliders_commit_one_cursor_update(navigator, monkeypatch):
    sliders = []
    requested = []
    monkeypatch.setattr(
        'ibl_datoviz.viewer.AtlasViewer._draw_viewport_toolbar_gui', lambda *_: None
    )
    dvz = navigator.dvz
    monkeypatch.setattr(dvz, 'dvz_gui_same_line', lambda *_: None, raising=False)
    monkeypatch.setattr(dvz, 'dvz_gui_checkbox', lambda *_: False, raising=False)
    monkeypatch.setattr(dvz, 'dvz_gui_set_next_item_width', lambda *_: None, raising=False)
    monkeypatch.setattr(navigator._sidebar, 'available', lambda *_: (900, 500))

    def slider(_gui, label, control, minimum, maximum):
        sliders.append((label, minimum, maximum))
        control._obj.value = minimum
        return True

    monkeypatch.setattr(dvz, 'dvz_gui_slider_int', slider, raising=False)
    monkeypatch.setattr(navigator._linked, 'set_cursor', requested.append)
    navigator._linked._draw_viewport_toolbar_gui(None)
    assert [s[0] for s in sliders] == [b'Coronal (AP)', b'Sagittal (ML)', b'Horizontal (DV)']
    assert [s[2] for s in sliders] == [n - 1 for n in navigator._linked.slice_source.grid.shape]
    assert len(requested) == 1 and requested[0].as_index() == (0, 0, 0)
