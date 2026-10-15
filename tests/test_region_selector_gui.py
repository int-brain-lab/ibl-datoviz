"""Controlled widget inputs, frame precedence and copied native ownership."""

import ctypes
from types import MappingProxyType, MethodType, SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog, open_volume_pack
from ibl_datoviz import AtlasMesh, AtlasTreeModel, AtlasViewer, LinkedAtlasNavigator
from ibl_datoviz.gui_data import GuiWidget
from ibl_datoviz.ontology import ROOT_PARENT, encode_region_key
from ibl_datoviz.region_selector import RegionSelector, SelectorRegion
from ibl_datoviz.region_selector_gui import RegionSelectorGui, signed_selection
from ibl_datoviz.selection import selection_decision
from tests.test_atlas import FIXTURE, REGIONS, FakeDatoviz
from tests.test_volume_free_navigator import VOLUME, CpuNavigator


class InputDatoviz(FakeDatoviz):
    class DvzRect(ctypes.Structure):
        _fields_ = [('height', ctypes.c_float)]

    def dvz_gui_current_window_rect(self, _gui, rect):
        rect._obj.height = 1200.0
        return True

    DVZ_GUI_DOCK_SLOT_LEFT = 0

    def __init__(self):
        super().__init__()
        self.events = []
        self.draw_result = 0
        self.dropped = 0
        self.buttons = set()
        self.query = None
        self.multiple = None
        self.texts = []

    def dvz_gui_dock_window_once(self, *_args):
        pass

    def dvz_gui_begin(self, *_args):
        return True

    def dvz_gui_end(self, *_args):
        pass

    def dvz_gui_combo(self, *_args):
        return False

    def dvz_gui_collapsing_header(self, *_args):
        return False

    def dvz_gui_text(self, _gui, text):
        self.texts.append(text)

    def dvz_gui_separator_text(self, *_args):
        pass

    def dvz_gui_button(self, _gui, label):
        return label in self.buttons

    def dvz_gui_same_line(self, *_args):
        pass

    def dvz_gui_input_text(self, _gui, _label, buffer, _size):
        if self.query is None:
            return False
        buffer.value = self.query.encode()
        self.query = None
        return True

    def dvz_gui_checkbox(self, _gui, _label, value):
        if self.multiple is None:
            return False
        value._obj.value = self.multiple
        self.multiple = None
        return True

    def dvz_gui_begin_child(self, *_args):
        return True

    def dvz_gui_end_child(self, *_args):
        pass

    def dvz_gui_tree_draw(self, *_args):
        events, self.events = self.events, []
        return self.draw_result, events, self.dropped


def event(fake, kind, region_id=0, *, flags=0, detail=0):
    return SimpleNamespace(
        type=getattr(fake, f'DVZ_GUI_DATA_EVENT_{kind}'),
        row_key=encode_region_key(region_id) if region_id else 0,
        flags=flags,
        detail=detail,
    )


def tree_model():
    ids = np.array([-8, -100, -101, -102, -103], dtype=np.int64)
    return AtlasTreeModel(
        'allen',
        ids,
        ids.view(np.uint64).copy(),
        np.array([ROOT_PARENT, 0, 1, 1, 1], dtype=np.uint32),
        ('grey', 'Branch', 'LeafA', 'LeafB', 'Context'),
        ('Grey', 'Parent', 'Àα alpha alpha', 'Other leaf', 'Unselectable'),
        np.full((5, 4), 255, dtype=np.uint8),
        np.array([True, False, True, True, False], dtype=np.bool_),
        MappingProxyType({101: 'Leaf A', 102: 'Leaf B'}),
    )


@pytest.fixture
def viewer():
    fake = InputDatoviz()
    viewer = AtlasViewer(
        AtlasMesh.from_pack(FIXTURE), catalog=open_region_catalog(REGIONS), datoviz=fake
    )
    viewer.tree_model = tree_model()
    viewer._replace_region_tree()
    yield viewer, fake
    viewer.close()


def test_stable_inventory_no_idle_uploads_and_zero_match_does_not_request_focus(viewer):
    viewer, fake = viewer
    handle = viewer.region_tree
    before = len(fake.calls)
    viewer._gui_callback(None, None, None)
    assert not any(call[0].startswith('tree_') for call in fake.calls[before:])
    fake.query = 'no matching region'
    viewer._gui_callback(None, None, None)
    assert viewer.region_tree is handle
    assert viewer._selector_model.visible_rows() == ()
    assert not any(call[0] == 'tree_focus' for call in fake.calls)
    assert sum(call[0] == 'tree_rows' for call in fake.calls) == 1


@pytest.mark.parametrize(
    ('ids', 'values', 'left'),
    [
        ([101], [9.0], None),
        ([101, -101], [9.0, 2.0], 2.0),
        ([101, -101], [9.0, float('nan')], float('nan')),
        ([101, -101], [9.0, 0.0], 0.0),
    ],
)
def test_browser_values_keep_exact_signed_hemisphere(viewer, ids, values, left):
    viewer, _fake = viewer
    viewer._mapped_region_values = lambda: SimpleNamespace(region_ids=ids, values=values)
    supplied = viewer._selector_values(viewer._selector_model)
    if left is None:
        assert supplied == {}
    elif np.isnan(left):
        assert np.isnan(supplied['-101'])
    else:
        assert supplied == {'-101': left}


def test_controls_search_fold_and_rank_cycle_restore_requested_order(viewer):
    viewer, fake = viewer
    viewer._selector_model.values = {'-101': 2.0, '-102': 1.0}
    viewer._selector_values = lambda _model: {'-101': 2.0, '-102': 1.0}
    fake.buttons = {b'Anatomy order'}
    viewer._gui_callback(None, None, None)
    assert viewer._selector_model.order == 'value-desc'
    fake.query = 'leaf'
    fake.buttons = {b'Value descending'}
    viewer._gui_callback(None, None, None)
    assert viewer._selector_model.order == 'anatomy'
    assert viewer._selector_model.requested_order == 'value-desc'
    assert b'2 regions / 0 selected' in fake.texts
    fake.buttons = {b'Clear search'}
    viewer._gui_callback(None, None, None)
    assert viewer._selector_model.order == 'value-desc'


def test_branch_disclosure_multiple_modifiers_and_keyboard_focus(viewer):
    viewer, fake = viewer
    fake.events = [event(fake, 'ROW_CLICKED', -100)]
    viewer._gui_callback(None, None, None)
    assert '-100' in viewer._selector_model.collapsed
    assert viewer.selected_region_ids() == ()
    fake.events = [event(fake, 'DISCLOSURE_CLICKED', -100)]
    viewer._gui_callback(None, None, None)
    fake.multiple = True
    fake.events = [event(fake, 'ROW_CLICKED', -101), event(fake, 'ROW_CLICKED', -102)]
    viewer._gui_callback(None, None, None)
    assert viewer.selected_region_ids() == (-101, -102)
    fake.events = [
        event(fake, 'FOCUS_CHANGED', -101, detail=1),
        event(fake, 'KEY_PRESSED', -101, detail=fake.DVZ_KEY_DOWN),
    ]
    viewer._gui_callback(None, None, None)
    assert viewer._selector_model.focus == '-102'
    assert [call for call in fake.calls if call[0] == 'tree_focus'][-1] == (
        'tree_focus',
        encode_region_key(-102),
    )
    before = len(fake.calls)
    viewer.set_selected_region_ids([102])
    assert not any(call[0] in ('tree_focus', 'tree_reveal') for call in fake.calls[before:])


def test_tree_preserves_existing_signed_ids_and_losing_proposal_does_not_commit_anchor(viewer):
    viewer, fake = viewer
    viewer.set_selected_region_ids([101])
    fake.events = [event(fake, 'ROW_CLICKED', -102, flags=2)]
    viewer._gui_callback(None, None, None)
    assert viewer.selected_region_ids() == (101, -102)
    viewer.set_selected_region_ids([101])
    anchor = viewer._selector_model.anchor
    candidate = viewer._selector_gui.candidate()
    viewer._selector_gui.intents(candidate, [event(fake, 'ROW_CLICKED', -102)])
    viewer._region_table_selected_region_ids = lambda: (101,)
    viewer._sync_selection_highlight(
        tree_changed=True, region_table_changed=True, candidate=candidate
    )
    assert viewer.selected_region_ids() == (101,)
    assert viewer._selector_model.anchor == anchor
    assert viewer._selector_model.selected == ['-101']


def test_tree_hover_survives_unhovered_viewport_and_exit_clears_it(viewer):
    viewer, fake = viewer
    fake.events = [event(fake, 'HOVER_CHANGED', -101, detail=1)]
    viewer._gui_callback(None, None, None)
    viewer._sync_viewport_hover(False)
    assert viewer._hovered_region_ids == (-101,)
    fake.events = [event(fake, 'HOVER_CHANGED', -101, detail=0)]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == ()


@pytest.mark.parametrize(('result', 'dropped'), [(-1, 0), (0, 1)])
def test_failed_or_dropped_draw_rejects_entire_browser_batch(viewer, result, dropped):
    viewer, fake = viewer
    prior = viewer._selector_model.snapshot()
    fake.query = 'leaf'
    fake.multiple = True
    fake.draw_result, fake.dropped = result, dropped
    fake.events = [event(fake, 'ROW_CLICKED', -101)]
    with pytest.raises(RuntimeError, match='draw|dropped'):
        viewer._gui_callback(None, None, None)
    assert viewer._selector_model.snapshot() == prior
    assert not viewer._selector_model.multiple
    assert viewer._tree_filter.value == b''
    assert viewer.selected_region_ids() == ()


def test_partial_projection_failure_restores_old_model_and_native_projection(viewer, monkeypatch):
    viewer, fake = viewer
    old = viewer._selector_model
    original = fake.dvz_gui_tree_set_projection
    calls = 0

    def fail_once(*args):
        nonlocal calls
        original(*args)
        calls += 1
        return -1 if calls == 1 else 0

    monkeypatch.setattr(fake, 'dvz_gui_tree_set_projection', fail_once)
    fake.query = 'leaf'
    with pytest.raises(RuntimeError, match='projection'):
        viewer._gui_callback(None, None, None)
    assert viewer._selector_model is old
    assert not viewer._closed
    projection = [call for call in fake.calls if call[0] == 'tree_projection'][-1]
    assert projection[1].view(np.int64).tolist() == [-100, -101, -102, -103]


def test_failed_projection_rollback_closes_viewer(viewer, monkeypatch):
    viewer, fake = viewer
    scopes = []

    def end_child(_gui):
        assert not viewer._closed
        scopes.append('end_child')

    def end(_gui):
        assert not viewer._closed
        scopes.append('end')

    monkeypatch.setattr(fake, 'dvz_gui_end_child', end_child)
    monkeypatch.setattr(fake, 'dvz_gui_end', end)
    monkeypatch.setattr(fake, 'dvz_gui_tree_set_projection', lambda *_args: -1)
    fake.query = 'leaf'
    with pytest.raises(RuntimeError, match='rollback failed; viewer closed'):
        viewer._gui_callback(None, None, None)
    assert viewer._closed
    assert scopes == ['end_child', 'end_child', 'end_child', 'end']
    assert sum(call[0] == 'tree_destroy' for call in fake.calls) == 1


def test_native_gui_rollback_stops_then_closes_after_app_run_returns(viewer, monkeypatch):
    viewer, fake = viewer
    viewer.app = app = object()
    scene = viewer.scene
    scopes, lifecycle = [], []
    returned = False

    def begin(*_args):
        scopes.append('window')
        return True

    def begin_child(*_args):
        scopes.append('child')
        return True

    def end_child(*_args):
        assert not viewer._closed and viewer.scene is scene
        assert scopes.pop() == 'child'
        lifecycle.append('end_child')

    def end(*_args):
        assert not viewer._closed and viewer.app is app
        assert scopes.pop() == 'window'
        lifecycle.append('end')

    def stop(native_app):
        assert native_app is app and not returned and scopes
        lifecycle.append('stop')
        return 0

    def destroy(native_app):
        assert native_app is app and returned and not scopes
        lifecycle.append('destroy')

    def run(_native_app, _frames):
        nonlocal returned
        viewer._gui_callback(None, None, None)
        assert viewer._close_pending and not viewer._closed
        assert viewer.app is app and viewer.scene is scene
        assert viewer._gui_callback_error is not None
        # A frame resumed by the native caller may invoke the callback again.
        before = lifecycle.copy()
        viewer._gui_callback(None, None, None)
        assert lifecycle == before
        returned = True
        lifecycle.append('run_return')

    monkeypatch.setattr(viewer, '_create_view', lambda **_kwargs: None)
    monkeypatch.setattr(fake, 'dvz_gui_begin', begin)
    monkeypatch.setattr(fake, 'dvz_gui_begin_child', begin_child)
    monkeypatch.setattr(fake, 'dvz_gui_end_child', end_child)
    monkeypatch.setattr(fake, 'dvz_gui_end', end)
    monkeypatch.setattr(fake, 'dvz_app_stop', stop, raising=False)
    monkeypatch.setattr(fake, 'dvz_app_run', run, raising=False)
    monkeypatch.setattr(fake, 'dvz_app_destroy', destroy)
    monkeypatch.setattr(fake, 'dvz_gui_tree_set_projection', lambda *_args: -1)
    fake.query = 'leaf'
    with pytest.raises(RuntimeError, match='rollback failed; viewer closed'):
        viewer.show()
    assert viewer._closed and viewer.app is None and viewer.scene is None
    assert lifecycle.index('stop') < lifecycle.index('end')
    assert lifecycle[-2:] == ['run_return', 'destroy']
    assert viewer._gui_callback_error is None


def test_annotation_spans_are_utf8_bytes_and_native_copies_temporary_storage():
    fake = FakeDatoviz()
    model = RegionSelector(
        [SelectorRegion('-101', None, -101, 'Àα', 'Àα alpha alpha')],
        {'query': 'alpha', 'values': {'-101': 2.0}},
    )
    widget = GuiWidget(fake, 'tree', None, controlled=True)
    widget.handle = SimpleNamespace(name='tree')
    adapter = RegionSelectorGui(widget, model, value_name='Firing rate (Hz)')
    annotations = [call[1] for call in fake.calls if call[0] == 'tree_annotations'][-1]
    assert annotations[0]['secondary'] == [(5, 5), (11, 5)]
    assert annotations[0]['value'] == b'2.000'
    assert b'Firing rate (Hz): 2.000' in annotations[0]['tooltip']
    assert b'Allen ID: 101' in annotations[0]['tooltip']
    adapter.model.values.clear()
    assert annotations[0]['value'] == b'2.000'
    assert signed_selection(model, (101, -101)) == ()


def test_focus_hover_membership_and_old_source_exit_does_not_clear_new_row(viewer):
    viewer, fake = viewer
    fake.events = [event(fake, 'FOCUS_CHANGED', -101, detail=1)]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == (-101,)
    fake.events = [
        event(fake, 'HOVER_CHANGED', -102, detail=1),
        event(fake, 'FOCUS_CHANGED', -101, detail=0),
    ]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == (-102,)
    fake.events = [event(fake, 'FOCUS_CHANGED', -100, detail=1)]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == ()
    fake.events = [event(fake, 'HOVER_CHANGED', -103, detail=1)]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == ()


def test_table_draw_failure_rolls_back_candidate_and_native_table_selection(viewer):
    viewer, fake = viewer
    viewer.set_selected_region_ids([101])
    old = viewer._selector_model
    fake.query = 'leaf'
    fake.events = [event(fake, 'ROW_CLICKED', -102)]
    viewer.region_table = SimpleNamespace(name='table')
    viewer._set_region_table_selection = lambda ids: fake.calls.append(
        ('restore_table', tuple(ids))
    )
    fake.dvz_gui_table_draw = lambda *_args: (-1, [], 0)
    with pytest.raises(RuntimeError, match='table draw'):
        viewer._gui_callback(None, None, None)
    assert viewer._selector_model is old
    assert viewer.selected_region_ids() == (101,)
    assert ('restore_table', (101,)) in fake.calls


def test_mapping_failure_after_new_selector_upload_restores_exact_navigation(viewer, monkeypatch):
    viewer, fake = viewer
    candidate = viewer._selector_gui.candidate()
    candidate.set_query('leaf')
    candidate.requested_order = 'value-desc'
    candidate.multiple = True
    candidate.collapsed.add('-100')
    viewer._commit_selector_frame(candidate, (), None)
    previous = viewer._selector_model
    original = viewer._clear_surface_hover
    calls = 0

    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('mapping post-selector failure')
        return original()

    monkeypatch.setattr(viewer, '_clear_surface_hover', fail_once)
    with pytest.raises(RuntimeError, match='post-selector'):
        viewer.set_mapping('beryl')
    assert viewer.mapping == 'allen'
    assert viewer._selector_model.snapshot() == previous.snapshot()
    assert viewer._selector_model.multiple is True
    assert viewer._selector_model.collapsed == previous.collapsed
    assert viewer._selector_gui.model is viewer._selector_model
    assert not viewer._closed


def test_native_key_before_focus_observation_keeps_requested_next_row(viewer):
    viewer, fake = viewer
    fake.events = [
        event(fake, 'KEY_PRESSED', -101, detail=fake.DVZ_KEY_DOWN),
        event(fake, 'FOCUS_CHANGED', -101, detail=1),
    ]
    viewer._gui_callback(None, None, None)
    assert viewer._selector_model.focus == '-102'
    assert viewer._hovered_region_ids == (-102,)


def test_mesh_proposal_upload_failure_keeps_cache_for_next_frame_retry(viewer, monkeypatch):
    viewer, fake = viewer
    fake.mesh_selection = [encode_region_key(101)]
    original = fake.dvz_gui_tree_set_selection
    calls = 0

    def fail_once(*args):
        nonlocal calls
        original(*args)
        calls += 1
        return -1 if calls == 1 else 0

    monkeypatch.setattr(fake, 'dvz_gui_tree_set_selection', fail_once)
    with pytest.raises(RuntimeError, match='selection'):
        viewer._gui_callback(None, None, None)
    assert viewer._last_mesh_region_ids == ()
    assert viewer.selected_region_ids() == ()
    viewer._gui_callback(None, None, None)
    assert viewer.selected_region_ids() == (101,)
    assert viewer._last_mesh_region_ids == (101,)


def test_partial_surface_style_failure_forces_previous_feedback_back(viewer, monkeypatch):
    viewer, fake = viewer
    viewer._update_surface_emphasis()
    previous = viewer._surface_state.handle.words.copy()
    original = fake.dvz_item_state_buffer_style
    calls = 0

    def partial_failure(bank, selection, hovered, active):
        nonlocal calls
        result = original(bank, selection, hovered, active)
        calls += 1
        return -1 if calls == 1 else result

    monkeypatch.setattr(fake, 'dvz_item_state_buffer_style', partial_failure)
    fake.events = [event(fake, 'ROW_CLICKED', -101)]
    with pytest.raises(RuntimeError, match='selection and hover'):
        viewer._gui_callback(None, None, None)
    assert viewer.selected_region_ids() == ()
    np.testing.assert_array_equal(viewer._surface_state.handle.words, previous)
    assert not viewer._surface_state.handle.active
    assert calls == 2
    assert not viewer._closed


@pytest.fixture
def linked_feedback():
    fake = InputDatoviz()
    fake.DVZ_FIELD_FORMAT_RGBA8_UNORM = 1
    fake.DVZ_FIELD_SEMANTIC_COLOR = 1
    fake.DVZ_FIELD_DIM_2D = 2
    source = open_volume_pack(VOLUME).load_volumes()
    navigator = CpuNavigator.from_slice_source(AtlasMesh.from_pack(FIXTURE), source, datoviz=fake)
    navigator._replace_region_tree()
    navigator._slice_loader.close()
    submitted = []
    navigator._slice_loader = SimpleNamespace(submit=submitted.append, close=lambda: None)
    navigator.view = object()
    navigator._slice_fields = {axis: object() for axis in ('ap', 'ml', 'dv')}
    navigator._crosshairs = {
        axis: SimpleNamespace(name=f'{axis}_crosshair') for axis in navigator._slice_fields
    }
    navigator._hover_fields = {
        axis: SimpleNamespace(name=axis) for axis in navigator._slice_fields
    }
    navigator._refresh_slices = MethodType(LinkedAtlasNavigator._refresh_slices, navigator)
    pixels = {}
    fake.dvz_sampled_field_update_from_array = lambda field, values, **_kwargs: pixels.update(
        {field.name: np.array(values, copy=True)}
    )
    navigator._refresh_hover_overlays()
    yield navigator, fake, submitted, pixels
    navigator.close()


def test_linked_partial_second_axis_hover_failure_restores_all_fields_and_requests(
    linked_feedback, monkeypatch
):
    navigator, fake, submitted, pixels = linked_feedback
    previous = {axis: values.copy() for axis, values in pixels.items()}
    original = fake.dvz_sampled_field_update_from_array
    failed = False

    def partially_fail(field, values, **kwargs):
        nonlocal failed
        original(field, values, **kwargs)
        if field.name == 'ml' and not failed:
            failed = True
            raise RuntimeError('partial ml hover upload')

    monkeypatch.setattr(fake, 'dvz_sampled_field_update_from_array', partially_fail)
    candidate = navigator._selector_gui.candidate()
    candidate.set_selected(['-315'])
    candidate.apply({'op': 'hover', 'id': '-315'})
    with pytest.raises(RuntimeError, match='partial ml hover'):
        navigator._commit_selector_frame(candidate, (-315,), selection_decision(tree_changed=True))
    assert navigator.selected_region_ids() == ()
    assert navigator._hovered_region_ids == ()
    assert not navigator._closed
    for axis, old_pixels in previous.items():
        np.testing.assert_array_equal(pixels[axis], old_pixels)
        rejected, restored = [request for request in submitted if request.axis == axis]
        assert rejected.selected_region_ids == (-315,)
        assert restored.selected_region_ids == ()
        assert restored.revision > rejected.revision
        assert navigator._slice_revisions[axis] == restored.revision


def test_linked_late_selection_failure_invalidates_queued_rejected_slice_revisions(
    linked_feedback, monkeypatch
):
    navigator, fake, submitted, _pixels = linked_feedback
    original = fake.dvz_selection_clear
    failed = False

    def fail_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            return -1
        return original(*args)

    monkeypatch.setattr(fake, 'dvz_selection_clear', fail_once)
    candidate = navigator._selector_gui.candidate()
    candidate.set_selected(['-315'])
    with pytest.raises(RuntimeError, match='surface selection clear'):
        navigator._commit_selector_frame(candidate, (-315,), selection_decision(tree_changed=True))
    assert navigator.selected_region_ids() == ()
    for axis in ('ap', 'ml', 'dv'):
        rejected, restored = [request for request in submitted if request.axis == axis]
        assert rejected.selected_region_ids == (-315,)
        assert restored.selected_region_ids == ()
        assert restored.revision == rejected.revision + 1
        assert restored.revision == navigator._slice_revisions[axis]
    assert not navigator._closed


def test_linked_feedback_rollback_failure_closes_owner(linked_feedback, monkeypatch):
    navigator, fake, _submitted, _pixels = linked_feedback

    def fail_hover(*_args, **_kwargs):
        raise RuntimeError('hover field unavailable')

    monkeypatch.setattr(fake, 'dvz_sampled_field_update_from_array', fail_hover)
    candidate = navigator._selector_gui.candidate()
    candidate.apply({'op': 'hover', 'id': '-315'})
    with pytest.raises(RuntimeError, match='frame rollback failed; viewer closed'):
        navigator._commit_selector_frame(candidate, (), None)
    assert navigator._closed
    assert navigator._slice_loader is None


def test_disabled_tree_hover_retains_click_selection(viewer):
    viewer, fake = viewer
    viewer.enable_hover = False
    before = len(fake.calls)
    fake.events = [event(fake, 'HOVER_CHANGED', -101, detail=1)]
    viewer._gui_callback(None, None, None)
    assert viewer._hovered_region_ids == ()
    assert not any(call[:3] == ('data', 'mesh', 'color') for call in fake.calls[before:])
    fake.events = [event(fake, 'ROW_CLICKED', -101)]
    viewer._gui_callback(None, None, None)
    assert viewer.selected_region_ids() == (-101,)
