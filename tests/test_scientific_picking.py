"""Exact identities and stale intent checks for the native selection bridge."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.layers import LayerObservationRef
from ibl_datoviz.scientific_picking import ScientificPicking


class FakeNative:
    DVZ_QUERY_CAPABILITY_ITEM = 1
    DVZ_QUERY_STATUS_HIT = 1
    DVZ_QUERY_STATUS_MISS = 2
    DVZ_QUERY_STATUS_NO_CAPABLE_VISUAL = 5
    DVZ_QUERY_STATUS_OUTSIDE_PANEL = 3

    def dvz_scene_id(self, _scene):
        return 8

    def dvz_panel_id(self, _panel):
        return 9

    def dvz_link_channel(self, *_args):
        return 13

    def dvz_link_channel_id(self, _channel):
        return 17

    def dvz_visual_set_query_capabilities(self, *_args):
        return 0

    def dvz_visual_set_link_keys(self, *_args):
        return 0

    def dvz_visual_id(self, visual):
        return visual

    def dvz_link_channel_destroy(self, _channel):
        pass


@pytest.fixture
def host():
    owner = SimpleNamespace(
        dvz=FakeNative(), scene=1, panel=2, layers=[], _require_open=lambda: None
    )
    owner.selection = SimpleNamespace(revision=0, observations=())

    def select(refs):
        owner.selection.observations = refs
        owner.selection.revision += 1

    owner.selection.set_observations = select
    owner._layer_registry = SimpleNamespace(
        contains=lambda ref: any(ref in layer.refs for layer in owner.layers)
    )
    owner.picking = ScientificPicking(owner)
    return owner


def layer(host, ids=(0, '0', 'missing'), *, visual=1, glyph='sphere', attachment='a'):
    refs = tuple(LayerObservationRef(attachment, value) for value in ids)
    component = SimpleNamespace(visual=visual)
    handle = SimpleNamespace(
        _glyph=glyph,
        _closed=False,
        effective_visible=True,
        _visual=component,
        refs=refs,
        positioned_refs=refs[:2],
        name=attachment,
        payload=SimpleNamespace(positioned=np.asarray([True, True, False])),
    )
    host.layers.append(handle)
    host.picking.register(handle, component)
    return handle


def result(host, handle, index=0, **changes):
    registered = host.picking._registrations[handle._visual.visual]
    fields = dict(
        hit=True,
        status=1,
        visual_id=handle._visual.visual,
        item_id=index,
        link_key=int(registered.keys[index]),
        link_channel=17,
        request_id=0x5343000000000001,
        scene_id=8,
        panel_id=9,
    )
    return SimpleNamespace(**(fields | changes))


def test_original_zero_and_string_ids_remain_distinct_and_missing_rows_not_linked(host):
    handle = layer(host)
    assert host.picking.resolve(result(host, handle, 0)).original_id == 0
    assert host.picking.resolve(result(host, handle, 1)).original_id == '0'
    registration = host.picking._registrations[1]
    assert registration.refs == handle.refs[:2]
    assert list(registration.keys) == [1, 2]
    with pytest.raises(ValueError):
        registration.keys.setflags(write=True)


def test_duplicate_original_ids_in_distinct_attachments_have_distinct_native_keys(host):
    first = layer(host)
    second = layer(host, attachment='other', visual=2)
    assert host.picking.resolve(result(host, first)) != host.picking.resolve(result(host, second))
    assert set(host.picking._registrations[1].keys).isdisjoint(host.picking._registrations[2].keys)


@pytest.mark.parametrize(
    'changes',
    [
        dict(link_key=999),
        dict(link_channel=999),
        dict(item_id=99),
        dict(item_id=-1),
        dict(scene_id=33),
        dict(panel_id=33),
        dict(visual_id=99),
        dict(hit=False),
    ],
)
def test_unknown_native_identity_cannot_resolve_a_scientific_reference(host, changes):
    handle = layer(host)
    assert host.picking.resolve(result(host, handle, **changes)) is None


@pytest.mark.parametrize('change', ['hidden', 'closed', 'replaced', 'removed'])
def test_stale_or_unavailable_attachment_cannot_resolve(host, change):
    handle = layer(host)
    query = result(host, handle)
    if change == 'hidden':
        handle.effective_visible = False
    elif change == 'closed':
        handle._closed = True
    elif change == 'replaced':
        handle._visual = SimpleNamespace(visual=2)
    else:
        host.layers.clear()
    assert host.picking.resolve(query) is None


def test_visible_unsupported_coverage_blocks_exact_picking_until_hidden(host):
    handle = layer(host, glyph='path')
    assert 'paths' in host.picking.unavailable_reason
    assert not host.picking._registrations
    handle.effective_visible = False
    assert not host.picking.unavailable_reason
    handle.effective_visible = True
    handle.payload.positioned[:] = False
    assert not host.picking.unavailable_reason


def test_external_unsupported_coverage_is_explicit(host):
    host.picking._external_blockers = lambda: ('probe lines have unsupported coverage',)
    assert 'probe lines' in host.picking.unavailable_reason


def test_queued_hit_uses_authoritative_controller_and_preserves_failure_selection(host):
    handle = layer(host)
    query = result(host, handle)
    host.picking._pending = (query.request_id, 0, 0)
    assert host.picking.consume(query)
    assert host.selection.observations == (handle.refs[0],)
    host.picking._pending = (query.request_id, 0, 1)
    query.status = 11
    host.picking.consume(query)
    assert host.picking.status == 'error'
    assert host.selection.observations == (handle.refs[0],)


def test_stale_selection_revision_and_invalidated_intent_are_discarded(host):
    handle = layer(host)
    query = result(host, handle)
    host.picking._pending = (query.request_id, 0, 0)
    host.selection.revision = 1
    host.picking.consume(query)
    assert not host.selection.observations
    assert host.picking.status == 'stale'
    host.picking._pending = (query.request_id, 0, 1)
    host.picking.invalidate()
    assert host.picking.consume(query)
    assert not host.selection.observations


def test_unrelated_native_results_are_not_scientific_clicks(host):
    handle = layer(host)
    assert not host.picking.consume(result(host, handle, request_id=23))


@pytest.mark.parametrize('operation', ['capability', 'links'])
def test_failed_registration_publishes_no_identity_and_never_recycles_keys(
    host, monkeypatch, operation
):
    handle = layer(host)
    host.picking.unregister(handle._visual)
    method = (
        'dvz_visual_set_query_capabilities'
        if operation == 'capability'
        else 'dvz_visual_set_link_keys'
    )
    original = getattr(host.dvz, method)
    monkeypatch.setattr(host.dvz, method, lambda *_args: -1)
    with pytest.raises(RuntimeError, match='failed with status'):
        host.picking.register(handle, handle._visual)
    assert not host.picking._registrations
    monkeypatch.setattr(host.dvz, method, original)
    host.picking.register(handle, handle._visual)
    assert list(host.picking._registrations[1].keys) == [5, 6]


def test_closed_adapter_rejects_further_native_access(host):
    handle = layer(host)
    query = result(host, handle)
    host.picking.close()
    host.picking.close()
    with pytest.raises(RuntimeError, match='closed'):
        host.picking.resolve(query)
