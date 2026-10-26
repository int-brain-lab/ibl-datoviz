"""Linked scientific events commit after all presentation domains succeed."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.components import AtlasCursor
from tests.test_region_selector_gui import linked_feedback  # noqa: F401 - shared pytest fixture
from tests.test_volume_free_navigator import (
    MESH,
    VOLUME,
    VolumeForbiddenDatoviz,
    cpu_slice_visuals,  # noqa: F401 - shared fixture
)


@pytest.fixture
def navigator(request):
    request.getfixturevalue('cpu_slice_visuals')
    source = open_volume_pack(VOLUME).load_volumes()
    with AtlasViewer.from_slice_source(
        AtlasMesh.from_pack(MESH), source, datoviz=VolumeForbiddenDatoviz()
    ) as viewer:
        yield viewer


def test_mapping_event_observes_both_committed_domains(navigator):
    navigator.set_selected_region_ids((315,))
    observed = []
    navigator.selection.on_changed(
        lambda event: observed.append(
            (event, navigator.mapping, navigator._linked.slice_composer.mapping)
        )
    )
    navigator.set_mapping('beryl')
    assert len(observed) == 1
    event, mesh_mapping, slice_mapping = observed[0]
    assert mesh_mapping == slice_mapping == 'beryl'
    assert event.current.regions == ()
    assert event.previous.regions == (('allen', 315),)


def test_mapping_slice_failure_restores_surfaces_regions_and_slices(navigator, monkeypatch):
    navigator.set_selected_region_ids((315,))
    before = {
        axis: tuple(np.array(a, copy=True) for a in arrays)
        for axis, arrays in navigator._linked.prepared_slices.items()
    }
    revision = navigator.selection.revision
    navigator._last_mesh_region_ids = (315,)
    monkeypatch.setattr(navigator, '_mesh_selected_region_ids', lambda: ())
    events = []
    navigator.selection.on_changed(events.append)
    refresh = navigator._linked._refresh_slices
    attempted = []

    def fail_once(axes=None):
        attempted.append(navigator.mapping)
        refresh(axes)
        if len(attempted) == 1:
            raise RuntimeError('injected slice update failure after upload')

    monkeypatch.setattr(navigator._linked, '_refresh_slices', fail_once)
    with pytest.raises(RuntimeError, match='slice update failure'):
        navigator.set_mapping('beryl')
    assert attempted == ['beryl', 'allen']
    assert navigator.mapping == navigator._linked.slice_composer.mapping == 'allen'
    assert navigator.tree_model.mapping == 'allen'
    assert navigator.selected_region_ids() == (315,)
    assert navigator.selection.revision == revision and not events
    assert not navigator.selection._hold_events
    navigator._sync_selection_highlight()
    assert navigator.selected_region_ids() == (315,)
    assert navigator.selection.revision == revision and not events
    for axis, arrays in before.items():
        for original, restored in zip(
            arrays, navigator._linked.prepared_slices[axis], strict=True
        ):
            np.testing.assert_equal(original, restored)


def test_cursor_selection_commits_once_and_failed_slice_selection_emits_nothing(
    navigator, monkeypatch
):
    events = []
    navigator.selection.on_changed(events.append)
    navigator._linked.set_cursor(AtlasCursor(1, 4, 1), select_region=True)
    assert len(events) == 1 and events[0].current.regions == (('allen', 315),)
    navigator.slices.select_region()
    assert len(events) == 2 and events[-1].current.regions == ()
    before_revision = navigator.selection.revision
    refresh = navigator._linked._refresh_slices
    attempts = []

    def fail_once(axes=None):
        attempts.append(navigator.selected_region_ids())
        refresh(axes)
        if len(attempts) == 1:
            raise RuntimeError('slice selection failure')

    monkeypatch.setattr(navigator._linked, '_refresh_slices', fail_once)
    with pytest.raises(RuntimeError, match='slice selection failure'):
        navigator.slices.select_region()
    assert attempts == [(315,), ()]
    assert navigator.selected_region_ids() == ()
    assert len(events) == 2 and navigator.selection.revision == before_revision


def test_linked_close_rejects_callback_and_foreign_thread_before_cleanup(navigator):
    loader = navigator._linked._slice_loader
    input_state = navigator._linked._slice_input
    errors = []

    def close_from_event(_event):
        try:
            navigator.close()
        except RuntimeError as error:
            errors.append(str(error))

    navigator.selection.on_changed(close_from_event)
    navigator.set_selected_region_ids((315,))
    assert errors and 'reentrantly' in errors[0]
    assert navigator._linked._slice_loader is loader
    assert navigator._linked._slice_input is input_state
    assert not navigator._closed
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(navigator.close)
        with pytest.raises(RuntimeError, match='owning thread'):
            future.result()
    assert navigator._linked._slice_loader is loader and not navigator._closed


def test_linked_close_from_gui_defers_loader_and_subscription_cleanup(navigator):
    closed = []
    loader = navigator._linked._slice_loader
    # Keep the actual scheduler alive for final normal cleanup; use an observable input stub.
    navigator._linked._slice_input = SimpleNamespace(close=lambda: closed.append('input'))
    navigator._gui_callback_depth = 1
    navigator.close()
    assert navigator._close_pending and not navigator._closed
    assert navigator._linked._slice_loader is loader and not closed
    navigator._gui_callback_depth = 0
    navigator.close()
    assert navigator._closed and closed == ['input'] and navigator._linked._slice_loader is None


@pytest.mark.usefixtures('linked_feedback')
def test_selector_outer_failure_does_not_publish_inner_slice_commit(monkeypatch, request):
    from ibl_datoviz.selection import selection_decision  # noqa: PLC0415

    navigator, native, _submitted, _pixels = request.getfixturevalue('linked_feedback')
    events = []
    navigator.selection.on_changed(events.append)
    original = native.dvz_selection_clear
    failed = False

    def fail_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            return -1
        return original(*args)

    monkeypatch.setattr(native, 'dvz_selection_clear', fail_once)
    candidate = navigator._selector_gui.candidate()
    candidate.set_selected(['-315'])
    with pytest.raises(RuntimeError, match='surface selection clear'):
        navigator._commit_selector_frame(candidate, (-315,), selection_decision(tree_changed=True))
    assert navigator.selected_region_ids() == ()
    assert navigator.selection.revision == 0 and not events


def test_direct_slice_input_failure_keeps_resources_during_dispatch(navigator, monkeypatch):
    from ibl_datoviz.slice_input import SliceInputAdapter  # noqa: PLC0415

    adapter = SliceInputAdapter(navigator._linked, object())
    loader = navigator._linked._slice_loader
    observed = []

    def dispatch(_event):
        navigator.close()
        observed.append(
            (navigator._closed, navigator._linked._slice_loader is loader, adapter.callback)
        )
        raise RuntimeError('direct slice callback failure')

    monkeypatch.setattr(adapter, '_dispatch_input', dispatch)
    with pytest.raises(RuntimeError, match='direct slice callback failure'):
        adapter.on_input(None, None, None)
    assert observed == [(False, True, adapter.callback)]
    assert navigator._closed and navigator._linked._slice_loader is None


def test_native_slice_input_failure_stops_app_and_defers_cleanup(navigator, monkeypatch):
    from ibl_datoviz.slice_input import SliceInputAdapter  # noqa: PLC0415

    adapter = SliceInputAdapter(navigator._linked, object())
    loader = navigator._linked._slice_loader
    app = object()
    stopped = []
    navigator.app = app
    monkeypatch.setattr(navigator.dvz, 'dvz_app_stop', stopped.append, raising=False)

    def dispatch(_event):
        raise RuntimeError('native slice callback failure')

    monkeypatch.setattr(adapter, '_dispatch_input', dispatch)
    adapter.on_input(None, None, None)  # ctypes boundary must contain the exception
    assert isinstance(navigator._gui_callback_error, RuntimeError)
    assert str(navigator._gui_callback_error) == 'native slice callback failure'
    assert stopped == [app] and navigator._close_pending
    assert not navigator._closed and navigator._linked._slice_loader is loader
    assert navigator._gui_callback_depth == 0
    # Simulate returning from app_run before normal cleanup, as show() does.
    navigator.app = None
    navigator.close()
    assert navigator._closed and navigator._linked._slice_loader is None
