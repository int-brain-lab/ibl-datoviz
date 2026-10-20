"""CPU tests for IBL fixture snapshots and linked-slice readiness."""

from __future__ import annotations

import ctypes
import json

import pytest

from ibl_datoviz.interaction_benchmark import LinkedReadiness, ReviewFixture, scientific_state
from ibl_datoviz.navigator import AtlasCursor
from ibl_datoviz.slice_scheduler import SliceRequest


class FakeDatoviz:
    def dvz_arcball_model(self, _arcball, matrix):
        for row in range(4):
            for column in range(4):
                matrix[row][column] = 1.0 if row == column else 0.0
        matrix[0][3] = 0.25
        return 0


class FakeCamera:
    def __init__(self, viewer):
        self.viewer = viewer

    def reset(self):
        self.viewer.camera_angles = (-1.15, -0.2, 2.5)


def test_scientific_snapshot_tracks_pan_and_zoom_even_when_model_is_unchanged():
    class ArcballState(ctypes.Structure):
        _fields_ = [('zoom', ctypes.c_float), ('pan', ctypes.c_float * 2),
                    ('interacting', ctypes.c_bool)]

    class CameraView(ctypes.Structure):
        _fields_ = [('eye', ctypes.c_float * 3), ('target', ctypes.c_float * 3),
                    ('up', ctypes.c_float * 3)]

    class CameraProjection(ctypes.Structure):
        _fields_ = [('type', ctypes.c_int), ('fov_y', ctypes.c_float)]

    class NavigationDatoviz(FakeDatoviz):
        DvzArcballState = ArcballState
        DvzCameraView = CameraView
        DvzCameraProjection = CameraProjection
        zoom = 1.0
        pan = (0.0, 0.0)

        def dvz_arcball_state(self, _arcball, output):
            output._obj.zoom = self.zoom
            output._obj.pan[:] = self.pan
            return True

        def dvz_panel_camera(self, panel):
            return panel == 'brain'

        def dvz_camera_get_view(self, _camera, output):
            output._obj.eye[:] = (0, 0, 3)

        def dvz_camera_get_projection(self, _camera, output):
            output._obj.fov_y = 0.72

    viewer = FakeLinkedViewer()
    viewer.dvz = NavigationDatoviz()
    viewer.panel, viewer.slice_panels = 'brain', {'ap': 'fixed-slice'}
    before = scientific_state(viewer)
    viewer.dvz.zoom, viewer.dvz.pan = 2.0, (0.25, -0.5)
    after = scientific_state(viewer)
    assert before['camera']['model'] == after['camera']['model']
    assert before['camera']['navigation'] != after['camera']['navigation']
    assert after['camera']['navigation']['zoom'] == 2.0
    assert after['camera']['navigation']['pan'] == [0.25, -0.5]
    assert after['camera']['navigation']['panels']['ap'] is None


class FakeLinkedViewer:
    def __init__(self):
        self.cursor = AtlasCursor(1, 2, 3)
        self.mapping = 'allen'
        self._selected = (315,)
        self._selection_revision = 4
        self.selection = type('Selection', (), {'revision': 4})()
        self.slice_renderer = 'raster'
        self.camera_angles = (-1.15, -0.2, 2.5)
        self.camera = FakeCamera(self)
        self.arcball = object()
        self.dvz = FakeDatoviz()
        self.anatomy_visible = True
        self.annotation_visible = True
        self.boundaries_visible = True
        self.volume_opacity = 0.0
        self.annotation_opacity = 1.0
        self.boundary_opacity = 0.82
        self.surface_opacity = 1.0
        self.context_opacity = 0.12
        self._slice_source_id = 'fixture-grid'
        self._slice_revisions = dict.fromkeys(('ap', 'ml', 'dv'), 0)
        self._displayed_slice_requests = {}
        self._slice_error = None
        self.raise_upload = False
        for axis in ('ap', 'ml', 'dv'):
            self._displayed_slice_requests[axis] = self._slice_request(axis)

    def _slice_request(self, axis):
        index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        return SliceRequest(
            axis,
            index,
            self._slice_revisions[axis],
            source_id=self._slice_source_id,
            mapping=self.mapping,
            selected_region_ids=self._selected,
            annotation_opacity=self.annotation_opacity,
            anatomy_visible=self.anatomy_visible,
            annotation_visible=self.annotation_visible,
        )

    def _upload_slice_payload(self, request, _payload):
        if self.raise_upload:
            raise RuntimeError('upload failed')
        if request == self._slice_request(request.axis):
            self._displayed_slice_requests[request.axis] = request

    def selected_region_ids(self):
        return self._selected

    def set_camera_angles(self, angles):
        self.camera_angles = tuple(float(value) for value in angles)

    def set_mapping(self, mapping):
        self.mapping = mapping
        self._selected = ()
        self._bump_all()

    def set_cursor(self, cursor):
        old = self.cursor.as_index()
        self.cursor = cursor
        for axis, before, after in zip(('ap', 'ml', 'dv'), old, cursor.as_index(), strict=True):
            if before != after:
                self._slice_revisions[axis] += 1

    def set_selected_region_ids(self, ids):
        self._selected = tuple(ids)
        self._bump_all()

    def set_slice_layers(self, *, anatomy, annotations, boundaries):
        self.anatomy_visible = anatomy
        self.annotation_visible = annotations
        self.boundaries_visible = boundaries

    def set_volume_opacity(self, opacity):
        self.volume_opacity = opacity

    def set_surface_opacity(self, opacity):
        self.surface_opacity = opacity

    def set_context_opacity(self, opacity):
        self.context_opacity = opacity

    def _bump_all(self):
        for axis in self._slice_revisions:
            self._slice_revisions[axis] += 1


def fixture(viewer):
    return ReviewFixture.capture(
        viewer,
        fixture_id='linked-test-v1',
        app_id='2',
        preset='test',
        metadata={
            'assets': {'mesh': 'a' * 64, 'volume': 'b' * 64},
            'layout': {'logical': [800, 600], 'framebuffer': [1600, 1200]},
        },
    )


def test_fixture_capture_is_json_friendly_and_includes_committed_scientific_state():
    viewer = FakeLinkedViewer()
    saved = fixture(viewer).to_dict()
    assert saved['initial_state']['cursor'] == [1, 2, 3]
    assert saved['initial_state']['slice_indices'] == {'ap': 1, 'ml': 2, 'dv': 3}
    assert saved['initial_state']['selected_region_ids'] == [315]
    assert saved['initial_state']['displayed_slice_requests']['ap']['revision'] == 0
    assert saved['metadata']['assets']['mesh'] == 'a' * 64
    assert json.dumps(saved, sort_keys=True, allow_nan=False) == json.dumps(
        saved, sort_keys=True, allow_nan=False
    )


def test_camera_model_is_stable_json_data():
    state = scientific_state(FakeLinkedViewer())
    assert state['camera']['model'][0][3] == 0.25
    encoded = json.dumps(state, sort_keys=True, allow_nan=False)
    assert json.loads(encoded)['camera']['model'][3][3] == 1.0


def test_fixture_metadata_requires_exact_resolved_assets_and_layout():
    saved = fixture(FakeLinkedViewer())
    saved.assert_compatible(saved.metadata)
    changed = {**saved.metadata, 'layout': {'logical': [1024, 768]}}
    assert saved.compatibility_mismatches(changed) == ('layout',)
    with pytest.raises(ValueError, match='layout'):
        saved.assert_compatible(changed)


def test_fixture_reset_uses_viewer_setters_and_restores_scientific_state():
    viewer = FakeLinkedViewer()
    original = fixture(viewer)
    viewer.set_mapping('beryl')
    viewer.set_cursor(AtlasCursor(2, 2, 3))
    viewer.set_selected_region_ids((-315,))
    viewer.set_slice_layers(anatomy=False, annotations=False, boundaries=False)
    viewer.set_volume_opacity(0.7)
    viewer.set_surface_opacity(0.4)
    viewer.set_context_opacity(0.8)
    restored = original.reset(viewer)
    assert restored['mapping'] == 'allen'
    assert restored['cursor'] == [1, 2, 3]
    assert restored['selected_region_ids'] == [315]
    assert restored['layers'] == {'anatomy': True, 'annotations': True, 'boundaries': True}
    assert restored['opacity']['volume'] == 0
    assert restored['opacity']['surface'] == 1
    assert restored['opacity']['context'] == 0.12


def test_reset_refuses_unsettable_opacity_before_mutating_viewer():
    viewer = FakeLinkedViewer()
    original = fixture(viewer)
    viewer.annotation_opacity = 0.5
    before = viewer.mapping, viewer.cursor, viewer.selected_region_ids()
    with pytest.raises(RuntimeError, match='opacity.annotations'):
        original.reset(viewer)
    assert (viewer.mapping, viewer.cursor, viewer.selected_region_ids()) == before


def test_readiness_tracks_only_successful_current_owner_uploads_and_restores_wrapper():
    viewer = FakeLinkedViewer()
    original_upload = viewer._upload_slice_payload
    with LinkedReadiness(viewer) as readiness:
        viewer.set_cursor(AtlasCursor(2, 2, 3))
        latest = viewer._slice_request('ap')
        stale = SliceRequest(
            'ap',
            latest.index,
            latest.revision - 1,
            source_id=latest.source_id,
            mapping=latest.mapping,
            selected_region_ids=latest.selected_region_ids,
        )
        viewer._upload_slice_payload(stale, object())
        assert readiness.check().status == 'pending'
        viewer.raise_upload = True
        with pytest.raises(RuntimeError, match='upload failed'):
            viewer._upload_slice_payload(latest, object())
        assert readiness.check().status == 'error'
        assert readiness.accepted_requests['ap']['revision'] == 0
        viewer.raise_upload = False
        viewer._slice_error = None
        readiness._upload_error = None
        viewer._upload_slice_payload(latest, object())
        result = readiness.check()
        assert result.status == 'ready'
        assert result.accepted_requests['ap']['revision'] == latest.revision
    assert viewer._upload_slice_payload == original_upload


def test_old_worker_completion_cannot_satisfy_newer_revision():
    viewer = FakeLinkedViewer()
    with LinkedReadiness(viewer) as readiness:
        viewer.set_cursor(AtlasCursor(2, 2, 3))
        old = viewer._displayed_slice_requests['ap']
        viewer._upload_slice_payload(old, object())
        assert readiness.check().pending_axes == ('ap',)
        current = viewer._slice_request('ap')
        viewer._upload_slice_payload(current, object())
        assert readiness.check().status == 'ready'


def test_wait_reports_timeout_cancellation_and_upload_errors():
    viewer = FakeLinkedViewer()
    with LinkedReadiness(viewer) as readiness:
        viewer.set_cursor(AtlasCursor(2, 2, 3))
        assert readiness.wait(timeout=0, pump=lambda: None).status == 'timeout'
        viewer._slice_error = ValueError('worker failed')
        assert readiness.wait(timeout=1, pump=lambda: None).status == 'error'
        viewer._slice_error = None
        cancelled = readiness.wait(timeout=1, pump=lambda: None, cancelled=lambda: True)
        assert cancelled.status == 'cancelled'
        assert readiness.check().status == 'cancelled'
    assert viewer._upload_slice_payload.__func__ is FakeLinkedViewer._upload_slice_payload


def test_checkpoint_requires_rendered_capture_associated_with_current_requests():
    viewer = FakeLinkedViewer()
    with LinkedReadiness(viewer) as readiness:
        assert readiness.checkpoint(render_proof=None).status == 'unavailable'
        expected = readiness.accepted_requests
        proof = {
            'source_generation': 11,
            'capture_id': 'capture-11',
            'slice_requests': expected,
        }
        result = readiness.checkpoint(render_proof=lambda _state: proof)
        assert result.status == 'ready'
        assert result.proof == proof
        mismatched = {**proof, 'slice_requests': {**expected, 'ap': None}}
        assert readiness.checkpoint(render_proof=lambda _state: mismatched).status == 'unavailable'


def test_checkpoint_reports_identity_change_during_capture():
    viewer = FakeLinkedViewer()
    with LinkedReadiness(viewer) as readiness:

        def capture(_state):
            viewer.set_cursor(AtlasCursor(2, 2, 3))
            return {
                'source_generation': 12,
                'capture_id': 'capture-12',
                'slice_requests': readiness.accepted_requests,
            }

        assert readiness.checkpoint(render_proof=capture).status == 'pending'


def test_wrapper_cleanup_preserves_replacement_and_closed_readiness_cancels():
    viewer = FakeLinkedViewer()
    readiness = LinkedReadiness(viewer)

    def replacement(_request, _payload):
        return None

    viewer._upload_slice_payload = replacement
    readiness.close()
    assert viewer._upload_slice_payload is replacement
    assert readiness.check().status == 'cancelled'
    readiness.close()
