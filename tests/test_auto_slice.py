"""Only current, explicit region-list intent may navigate linked slices."""

from threading import Event
from types import SimpleNamespace

import pytest

from ibl_datoviz.auto_slice import AutoSliceNavigation
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


def test_region_list_only_and_deselection_preserves_cursor(navigator):
    before = navigator.cursor
    navigator.selection.set_regions((-315,), mapping='allen')
    assert navigator.cursor == before
    candidate = SimpleNamespace(by_id={'315': SimpleNamespace(atlas_id=315)}, selected=['315'])
    ready = Event()
    navigator._auto_slice._worker._notify = lambda _: ready.set()
    navigator._region_list_intent({'kind': 'select', 'id': '315'}, candidate)
    assert ready.wait(1)
    navigator._drain_auto_slice()
    anchor = navigator._auto_slice.navigation.anchor('allen', -315)
    assert navigator.cursor.as_index() == anchor
    assert navigator.selection.regions == (('allen', -315),)
    candidate.selected = []
    navigator._region_list_intent({'kind': 'select', 'id': '315'}, candidate)
    assert navigator._auto_slice.drain() is None


@pytest.mark.parametrize('cancel', ['manual', 'mapping', 'disabled', 'selection', 'direct'])
def test_new_navigation_intent_discards_ready_anchor(navigator, cancel):
    ready = Event()
    navigator._auto_slice._worker._notify = lambda _: ready.set()
    navigator._auto_slice.request('allen', -315)
    assert ready.wait(1)
    if cancel == 'manual':
        navigator.set_cursor(navigator.cursor)
    elif cancel == 'mapping':
        navigator.set_mapping('beryl')
    elif cancel == 'disabled':
        navigator.slices.set_auto_slice(False)
    elif cancel == 'selection':
        navigator.selection.set_regions((315,), mapping='allen')
    else:
        navigator._cancel_auto_slice()
    before = navigator.cursor
    navigator._drain_auto_slice()
    assert navigator.cursor == before


def test_closed_viewer_joins_auto_slice_worker(navigator):
    owner = navigator._auto_slice
    navigator.close()
    assert navigator._auto_slice is None
    with pytest.raises(RuntimeError, match='closed'):
        owner._worker.request('region', ('allen', -315))


def test_native_post_auto_slice_upload_failure_is_contained(navigator, monkeypatch):
    monkeypatch.setattr(navigator._auto_slice, 'drain', lambda: (0, 1, 0))

    def fail(*args, **kwargs):
        raise RuntimeError('auto-slice upload rejected')

    monkeypatch.setattr(navigator, 'set_cursor', fail)
    navigator._drain_prepared_slices(None, None)
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
    monkeypatch.setattr(navigator, 'set_cursor', requested.append)
    navigator._draw_viewport_toolbar_gui(None)
    assert [s[0] for s in sliders] == [b'Coronal (AP)', b'Sagittal (ML)', b'Horizontal (DV)']
    assert [s[2] for s in sliders] == [n - 1 for n in navigator.slice_source.grid.shape]
    assert len(requested) == 1 and requested[0].as_index() == (0, 0, 0)
