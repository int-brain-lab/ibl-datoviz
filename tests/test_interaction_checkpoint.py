"""CPU coverage for designated terminal source captures and comparisons."""

from __future__ import annotations

import copy
from contextlib import suppress

import numpy as np
import pytest

from ibl_datoviz.interaction_benchmark import LinkedReadiness
from ibl_datoviz.interaction_checkpoint import (
    capture_terminal_checkpoint,
    compare_terminal_checkpoints,
)
from ibl_datoviz.navigator import AtlasCursor
from tests.test_interaction_benchmark import FakeLinkedViewer


class FakeSourceDatoviz:
    def __init__(self, *, pixels=None):
        self.source = object()
        self.serial = 0
        self.pixels = np.zeros((3, 4, 4), dtype=np.uint8) if pixels is None else pixels
        self.fail_source_render = False
        self.advance_source_render = True
        self.advance_during_capture = False
        self.change_scientific_state = None
        self.render_enabled = False
        self.render_policy_updates = []

    def dvz_gui_viewport_source(self, _viewport):
        return self.source

    def dvz_view_render_serial(self, view):
        assert view is self.source
        return self.serial

    def dvz_view_render_once(self, view):
        if view is not self.source:
            return 0  # owner-thread work pump for the host view
        if self.fail_source_render:
            return -1
        if self.change_scientific_state is not None:
            self.change_scientific_state()
            self.change_scientific_state = None
        if self.advance_source_render:
            self.serial += 1
        return 0

    def dvz_view_capture_rgba(self, view):
        assert view is self.source
        if self.advance_during_capture:
            self.serial += 1
        return self.pixels

    def dvz_view_render_enabled(self, view):
        assert view is self.source
        return self.render_enabled

    def dvz_view_set_render_enabled(self, view, enabled):
        assert view is self.source
        self.render_enabled = bool(enabled)
        self.render_policy_updates.append(self.render_enabled)
        return 0


class MissingSourceApiDatoviz:
    def __getattr__(self, name):
        if name == 'dvz_gui_viewport_source':
            raise AttributeError(name)
        return getattr(FakeSourceDatoviz(), name)


def capture(viewer, *, readiness_error=None):
    native = FakeSourceDatoviz()
    viewer.dvz = native
    viewer.view = object()
    viewer.viewport = object()
    if readiness_error is not None:
        viewer._slice_error = readiness_error
    with LinkedReadiness(viewer) as readiness:
        result = capture_terminal_checkpoint(viewer, readiness)
    return result, native


def test_terminal_capture_advances_scientific_source_once_and_records_exact_pixels():
    viewer = FakeLinkedViewer()
    result, native = capture(viewer)

    assert result['status'] == 'ready'
    assert result['scope'] == 'designated-terminal-source-capture'
    assert result['rendering']['proof']['source_generation'] == 1
    assert (
        result['rendering']['proof']['slice_requests'] == result['rendering']['accepted_requests']
    )
    assert result['image']['shape'] == [3, 4, 4]
    assert result['image']['dtype'] == 'uint8'
    assert len(result['image']['sha256']) == 64
    assert native.serial == 1
    assert native.render_policy_updates == [True, False]
    assert native.render_enabled is False


def test_terminal_capture_reports_missing_source_apis_and_readiness_failures():
    viewer = FakeLinkedViewer()
    viewer.dvz = MissingSourceApiDatoviz()
    viewer.view = object()
    viewer.viewport = object()
    with LinkedReadiness(viewer) as readiness:
        unavailable = capture_terminal_checkpoint(viewer, readiness)
    assert unavailable['status'] == 'unavailable'

    viewer = FakeLinkedViewer()
    viewer.set_cursor(AtlasCursor(2, 2, 3))
    native = FakeSourceDatoviz()
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()
    with LinkedReadiness(viewer) as readiness:
        readiness.wait = lambda **_kwargs: readiness.check()
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] == 'pending'

    viewer = FakeLinkedViewer()
    result, _native = capture(viewer, readiness_error=RuntimeError('worker failed'))
    assert result['status'] == 'error'

    viewer = FakeLinkedViewer()
    viewer.set_cursor(AtlasCursor(2, 2, 3))
    viewer.raise_upload = True
    native = FakeSourceDatoviz()
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()
    with LinkedReadiness(viewer) as readiness:
        with suppress(RuntimeError):
            viewer._upload_slice_payload(viewer._slice_request('ap'), object())
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] == 'error'


def test_terminal_capture_rejects_failed_or_non_advancing_source_render():
    for configure in ('failure', 'no-op'):
        viewer = FakeLinkedViewer()
        native = FakeSourceDatoviz()
        native.fail_source_render = configure == 'failure'
        native.advance_source_render = configure != 'no-op'
        viewer.dvz = native
        viewer.view = object()
        viewer.viewport = object()
        with LinkedReadiness(viewer) as readiness:
            result = capture_terminal_checkpoint(viewer, readiness)
        assert result['status'] == 'error'
        assert native.render_enabled is False
        assert native.render_policy_updates == [True, False]


def test_terminal_capture_rejects_invalid_rgba_and_source_advancement_during_capture():
    for pixels in (
        np.zeros((3, 4, 3), dtype=np.uint8),
        np.zeros((3, 4, 4), dtype=np.float32),
        np.zeros((0, 4, 4), dtype=np.uint8),
    ):
        viewer = FakeLinkedViewer()
        native = FakeSourceDatoviz(pixels=pixels)
        viewer.dvz, viewer.view, viewer.viewport = native, object(), object()
        with LinkedReadiness(viewer) as readiness:
            result = capture_terminal_checkpoint(viewer, readiness)
        assert result['status'] == 'error'

    viewer = FakeLinkedViewer()
    native = FakeSourceDatoviz()
    native.advance_during_capture = True
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()
    with LinkedReadiness(viewer) as readiness:
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] == 'error'


def test_scientific_state_change_during_capture_cannot_produce_ready_checkpoint():
    viewer = FakeLinkedViewer()
    native = FakeSourceDatoviz()
    native.change_scientific_state = lambda: viewer.set_cursor(AtlasCursor(2, 2, 3))
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()
    with LinkedReadiness(viewer) as readiness:
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] != 'ready'


@pytest.mark.parametrize('during_capture', [False, True])
def test_retained_callback_failure_is_a_structured_checkpoint_error(during_capture):
    viewer = FakeLinkedViewer()
    native = FakeSourceDatoviz()
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()

    def fail():
        viewer._review_error = RuntimeError('selection callback failed')

    if during_capture:
        native.change_scientific_state = fail
    else:
        fail()
    with LinkedReadiness(viewer) as readiness:
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] == 'error'
    assert 'selection callback failed' in result['error']
    assert native.render_enabled is False


@pytest.mark.parametrize('during_capture', [False, True])
def test_nonfinite_scientific_snapshot_preserves_structured_failure(during_capture):
    viewer = FakeLinkedViewer()
    native = FakeSourceDatoviz()
    viewer.dvz, viewer.view, viewer.viewport = native, object(), object()

    def corrupt():
        viewer.camera_angles = (float('nan'), 0, 0)

    if during_capture:
        native.change_scientific_state = corrupt
    else:
        corrupt()
    with LinkedReadiness(viewer) as readiness:
        result = capture_terminal_checkpoint(viewer, readiness)
    assert result['status'] == 'error'
    assert 'non-finite' in result['error']
    assert native.render_enabled is False


def test_comparison_requires_ready_complete_proofs_and_exact_state_and_pixels():
    viewer = FakeLinkedViewer()
    expected, _native = capture(viewer)
    observed = copy.deepcopy(expected)
    assert compare_terminal_checkpoints(expected, observed)['status'] == 'match'

    changed_pixels = copy.deepcopy(expected)
    changed_pixels['image']['sha256'] = 'f' * 64
    assert compare_terminal_checkpoints(expected, changed_pixels)['mismatches'] == ['image']

    changed_state = copy.deepcopy(expected)
    changed_state['scientific_state']['camera']['angles'][0] += 0.25
    assert compare_terminal_checkpoints(expected, changed_state)['mismatches'] == [
        'scientific_state'
    ]

    absent = {key: value for key, value in expected.items() if key != 'image'}
    assert compare_terminal_checkpoints(absent, expected)['status'] == 'unavailable'
    malformed = copy.deepcopy(expected)
    malformed['image']['shape'] = [3, 4, 3]
    assert compare_terminal_checkpoints(malformed, expected)['status'] == 'unavailable'


def test_comparison_excludes_slice_revision_counters_but_compares_request_content():
    viewer = FakeLinkedViewer()
    expected, _native = capture(viewer)
    observed = copy.deepcopy(expected)
    for request in observed['scientific_state']['displayed_slice_requests'].values():
        request['revision'] += 20
    assert compare_terminal_checkpoints(expected, observed)['status'] == 'match'

    observed['scientific_state']['displayed_slice_requests']['ap']['index'] += 1
    comparison = compare_terminal_checkpoints(expected, observed)
    assert comparison['status'] == 'mismatch'
    assert comparison['mismatches'] == ['scientific_state']


def test_comparison_reports_unavailable_for_absent_or_malformed_expected_proof():
    viewer = FakeLinkedViewer()
    ready, _native = capture(viewer)
    observed = copy.deepcopy(ready)
    assert compare_terminal_checkpoints(None, observed)['status'] == 'unavailable'
    malformed = copy.deepcopy(ready)
    malformed['scope'] = 'unverified'
    assert compare_terminal_checkpoints(malformed, observed)['status'] == 'unavailable'
    malformed = copy.deepcopy(ready)
    malformed['image']['sha256'] = 'not-a-digest'
    assert compare_terminal_checkpoints(malformed, observed)['status'] == 'unavailable'
