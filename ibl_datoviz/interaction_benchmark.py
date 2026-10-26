"""IBL fixture snapshots and linked-slice readiness for interaction replays.

This module adapts existing viewer state to a generic host replay player. It
does not define or import an input trace format, and it never owns renderer
resources or claims that a successful upload was displayed.
"""

from __future__ import annotations

import ctypes
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from threading import get_ident
from time import monotonic, sleep
from typing import Any

import numpy as np

from .navigator import AtlasCursor

_AXES = ('ap', 'ml', 'dv')


def _request_dict(request: object | None) -> dict[str, Any] | None:
    if request is None:
        return None
    values = asdict(request)
    return _json_value(values)


def _json_value(value: Any) -> Any:
    """Convert scientific state to finite, stable JSON-compatible values."""
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('benchmark state must not contain non-finite numbers')
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f'benchmark state is not JSON-compatible: {type(value).__name__}')


def _camera_model(viewer) -> list[list[float]] | None:
    """Read the current arcball model without retaining a native-owned handle."""
    arcball = getattr(viewer, 'arcball', None)
    dvz = getattr(viewer, 'dvz', None)
    model = getattr(dvz, 'dvz_arcball_model', None)
    if not arcball or not callable(model):
        return None
    storage = ctypes.create_string_buffer(64 + 15)
    offset = (-ctypes.addressof(storage)) % 16
    matrix = ((ctypes.c_float * 4) * 4).from_buffer(storage, offset)
    if model(arcball, matrix) != 0:
        raise RuntimeError('could not snapshot the current arcball model')
    values = np.ctypeslib.as_array(matrix).astype(np.float64).reshape(4, 4)
    return _json_value(values.tolist())


def _camera_navigation(viewer) -> dict[str, Any] | None:
    """Copy full controller navigation and panel camera state, including pan/zoom."""
    dvz = getattr(viewer, 'dvz', None)
    if not callable(getattr(dvz, 'dvz_arcball_state', None)):
        return None
    state = dvz.DvzArcballState()
    if not dvz.dvz_arcball_state(viewer.arcball, ctypes.byref(state)):
        raise RuntimeError('could not snapshot arcball navigation')
    panels = {'brain': viewer.panel, **getattr(viewer._linked, 'slice_panels', {})}
    cameras = {}
    for name, panel in panels.items():
        camera = dvz.dvz_panel_camera(panel)
        if not camera:
            if name == 'brain':
                raise RuntimeError('could not snapshot brain panel camera')
            cameras[name] = None  # Fixed 2D slice panels have no camera controller.
            continue
        view = dvz.DvzCameraView()
        projection = dvz.DvzCameraProjection()
        dvz.dvz_camera_get_view(camera, ctypes.byref(view))
        dvz.dvz_camera_get_projection(camera, ctypes.byref(projection))
        cameras[name] = {
            'view': {key: list(getattr(view, key)) for key, _ctype in view._fields_},
            'projection': {key: getattr(projection, key) for key, _ctype in projection._fields_},
        }
    return _json_value(
        {
            'zoom': state.zoom,
            'pan': list(state.pan),
            'interacting': state.interacting,
            'panels': cameras,
        }
    )


def scientific_state(viewer) -> dict[str, Any]:
    """Return the committed linked-view state in deterministic JSON form."""
    cursor = viewer._linked.cursor.as_index()
    requests = {
        axis: _request_dict(viewer._linked._displayed_slice_requests.get(axis)) for axis in _AXES
    }
    return _json_value(
        {
            'camera': {
                'angles': getattr(viewer, 'camera_angles', None),
                'model': _camera_model(viewer),
                'navigation': _camera_navigation(viewer),
                'controller': type(getattr(viewer, 'camera', None)).__name__,
            },
            'mapping': viewer.mapping,
            'cursor': list(cursor),
            'slice_indices': dict(zip(_AXES, cursor, strict=True)),
            'selected_region_ids': list(viewer.selected_region_ids()),
            'slice_renderer': viewer._linked.slice_renderer,
            'auto_slice_enabled': getattr(
                getattr(viewer._linked, '_auto_slice', None), 'enabled', None
            ),
            'displayed_slice_requests': requests,
            'layers': {
                'anatomy': viewer._linked.anatomy_visible,
                'annotations': viewer._linked.annotation_visible,
                'boundaries': viewer._linked.boundaries_visible,
            },
            'opacity': {
                'volume': viewer._linked.volume_opacity,
                'annotations': viewer._linked.annotation_opacity,
                'boundaries': viewer._linked.boundary_opacity,
                'surface': getattr(viewer, 'surface_opacity', None),
                'context': getattr(viewer, 'context_opacity', None),
            },
        }
    )


def _restore_auto_slice(viewer, initial, current):
    """Restore navigation policy through the public slice controller."""
    expected = initial.get('auto_slice_enabled')
    observed = current.get('auto_slice_enabled')
    if (expected is None) != (observed is None):
        raise RuntimeError('fixture auto-slice availability changed')
    if expected != observed:
        setter = getattr(getattr(viewer, 'slices', None), 'set_auto_slice', None)
        if not callable(setter):
            raise RuntimeError('fixture reset has no public auto-slice setter')
        setter(expected)


@dataclass(frozen=True, slots=True)
class ReviewFixture:
    """JSON-compatible fixture identity and captured scientific reset state.

    ``metadata`` is caller-supplied resolved environment data such as asset
    hashes, preset, window/framebuffer dimensions, DPI, UI scale, and panel
    rectangles. This class records those values but does not create layouts or
    infer that two environments are compatible.
    """

    fixture_id: str
    app_id: str
    preset: str
    metadata: Mapping[str, Any]
    initial_state: Mapping[str, Any]

    @classmethod
    def capture(
        cls,
        viewer,
        *,
        fixture_id: str,
        app_id: str,
        preset: str,
        metadata: Mapping[str, Any],
    ) -> ReviewFixture:
        """Capture a fixture identity and the current committed viewer state."""
        if not all(isinstance(value, str) and value for value in (fixture_id, app_id, preset)):
            raise ValueError('fixture_id, app_id, and preset must be non-empty strings')
        encoded_metadata = _json_value(metadata)
        state = scientific_state(viewer)
        # Validate serializability at the capture boundary, not during report writing.
        json.dumps({'metadata': encoded_metadata, 'initial_state': state}, allow_nan=False)
        return cls(fixture_id, app_id, preset, encoded_metadata, state)

    def to_dict(self) -> dict[str, Any]:
        """Return the complete stable fixture record."""
        return _json_value(
            {
                'fixture_id': self.fixture_id,
                'app_id': self.app_id,
                'preset': self.preset,
                'metadata': self.metadata,
                'initial_state': self.initial_state,
            }
        )

    def compatibility_mismatches(self, observed: Mapping[str, Any]) -> tuple[str, ...]:
        """Return top-level fixture metadata keys that differ from this record."""
        resolved = _json_value(observed)
        return tuple(
            sorted(
                key
                for key in self.metadata.keys() | resolved.keys()
                if self.metadata.get(key) != resolved.get(key)
            )
        )

    def assert_compatible(self, observed: Mapping[str, Any]) -> None:
        """Reject a host or asset state that differs from the recorded fixture."""
        mismatches = self.compatibility_mismatches(observed)
        if mismatches:
            raise ValueError(f'incompatible fixture metadata: {", ".join(mismatches)}')

    def reset(self, viewer) -> dict[str, Any]:  # noqa: PLR0912
        """Restore state through viewer setters, then return the observed state.

        Runtime handles, GUI layout, source assets, and asynchronous jobs are
        deliberately outside this reset operation. Fields without a public
        setter must already match the fixture or reset fails before mutation.
        """
        initial = self.initial_state
        current = scientific_state(viewer)
        fixed_fields = (
            ('slice_renderer',),
            ('opacity', 'annotations'),
            ('opacity', 'boundaries'),
        )
        for path in fixed_fields:
            expected = initial[path[0]] if len(path) == 1 else initial[path[0]][path[1]]
            actual = current[path[0]] if len(path) == 1 else current[path[0]][path[1]]
            if expected != actual:
                label = '.'.join(path)
                raise RuntimeError(f'fixture reset has no public setter for changed {label}')

        _restore_auto_slice(viewer, initial, current)

        camera = initial['camera']
        camera_controller = getattr(viewer, 'camera', None)
        if callable(getattr(camera_controller, 'reset', None)):
            camera_controller.reset()
            if camera['angles'] is not None and callable(
                getattr(viewer, 'set_camera_angles', None)
            ):
                viewer.set_camera_angles(camera['angles'])
        elif camera['angles'] is not None and callable(getattr(viewer, 'set_camera_angles', None)):
            viewer.set_camera_angles(camera['angles'])
        elif camera != current['camera']:
            raise RuntimeError('fixture reset has no public camera reset/setter')
        if scientific_state(viewer)['camera'] != camera:
            raise RuntimeError('public camera reset did not restore the captured camera state')

        if viewer.mapping != initial['mapping']:
            viewer.set_mapping(initial['mapping'])
        target_cursor = AtlasCursor(*initial['cursor'])
        if viewer._linked.cursor != target_cursor:
            viewer.slices.set_position(
                ap=target_cursor.ap, ml=target_cursor.ml, dv=target_cursor.dv, units='voxel'
            )
        if tuple(viewer.selected_region_ids()) != tuple(initial['selected_region_ids']):
            viewer.set_selected_region_ids(initial['selected_region_ids'])
        layers = initial['layers']
        viewer.slices.set_layers(
            anatomy=layers['anatomy'],
            annotations=layers['annotations'],
            boundaries=layers['boundaries'],
        )
        opacity = initial['opacity']
        if opacity['volume'] != viewer._linked.volume_opacity:
            viewer.slices.set_volume_opacity(opacity['volume'])
        if opacity['surface'] is not None and opacity['surface'] != viewer.surface_opacity:
            viewer.set_surface_opacity(opacity['surface'])
        if opacity['context'] is not None and opacity['context'] != viewer.context_opacity:
            viewer.set_context_opacity(opacity['context'])

        restored = scientific_state(viewer)
        if restored['camera'] != camera:
            raise RuntimeError('public camera reset did not restore the captured camera state')
        for key in ('mapping', 'cursor', 'selected_region_ids', 'layers', 'auto_slice_enabled'):
            if restored[key] != initial[key]:
                raise RuntimeError(f'fixture reset did not restore {key}')
        for key in ('volume', 'surface', 'context'):
            if restored['opacity'][key] != opacity[key]:
                raise RuntimeError(f'fixture reset did not restore {key} opacity')
        return restored


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Nonblocking readiness/checkpoint outcome for one linked viewer."""

    status: str
    pending_axes: tuple[str, ...] = ()
    accepted_requests: Mapping[str, Any] | None = None
    error: str | None = None
    proof: Mapping[str, Any] | None = None
    pending_navigation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the checkpoint outcome as JSON-compatible data."""
        return _json_value(asdict(self))


class LinkedReadiness:
    """Track owner-thread slice uploads and require explicit rendered proof.

    The instance wrapper is installed only on the supplied viewer and restored
    by :meth:`close`. A worker completion is never treated as an accepted upload.
    """

    def __init__(self, viewer) -> None:
        self.viewer = viewer
        self._original_upload = viewer._linked._upload_slice_payload
        self._wrapper = None
        self._closed = False
        self._upload_error: Exception | None = None
        self._accepted = dict(getattr(viewer._linked, '_displayed_slice_requests', {}))

        def tracked_upload(request, payload):
            owner_thread = getattr(viewer, '_owner_thread', None)
            if owner_thread is not None and get_ident() != owner_thread:
                raise RuntimeError('slice readiness uploads require the viewer owning thread')
            try:
                result = self._original_upload(request, payload)
            except Exception as error:
                self._upload_error = error
                raise
            axis = request.axis
            if (
                not self._closed
                and viewer._linked._displayed_slice_requests.get(axis) == request
                and viewer._linked._slice_revisions.get(axis) == request.revision
                and viewer._linked._slice_request(axis) == request
            ):
                self._accepted[axis] = request
                self._upload_error = None
            return result

        self._wrapper = tracked_upload
        viewer._linked._upload_slice_payload = tracked_upload

    @property
    def accepted_requests(self) -> dict[str, dict[str, Any]]:
        """Return the full identity of each latest successfully uploaded request."""
        return {axis: _request_dict(self._accepted.get(axis)) for axis in _AXES}

    def _expected(self, axis: str):
        return self.viewer._linked._slice_request(axis)

    def check(self) -> ReadinessResult:
        """Inspect current request identities without blocking or rendering."""
        if self._closed:
            return ReadinessResult('cancelled', error='readiness adapter is closed')
        owner_thread = getattr(self.viewer, '_owner_thread', None)
        if owner_thread is not None and get_ident() != owner_thread:
            return ReadinessResult(
                'error', error='readiness checks require the viewer owning thread'
            )
        navigation = getattr(self.viewer._linked, '_auto_slice', None)
        error = (
            self._upload_error
            or getattr(self.viewer._linked, '_slice_error', None)
            or getattr(navigation, 'error', None)
        )
        if error is not None:
            return ReadinessResult('error', error=f'{type(error).__name__}: {error}')
        pending = tuple(axis for axis in _AXES if self._accepted.get(axis) != self._expected(axis))
        pending_navigation = bool(getattr(navigation, 'pending', False))
        status = 'pending' if pending or pending_navigation else 'ready'
        return ReadinessResult(
            status, pending, self.accepted_requests, pending_navigation=pending_navigation
        )

    def wait(
        self,
        *,
        timeout: float,
        pump: Callable[[], object],
        cancelled: Callable[[], bool] | None = None,
        interval: float = 0.005,
    ) -> ReadinessResult:
        """Pump owner-thread work until current slices are uploaded or fail."""
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError('timeout must be finite and non-negative')
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError('interval must be finite and positive')
        if not callable(pump):
            raise TypeError('pump must be callable on the viewer owner thread')
        deadline = monotonic() + timeout
        while True:
            result = self.check()
            if result.status != 'pending':
                return result
            if cancelled is not None and cancelled():
                self.close()
                return ReadinessResult(
                    'cancelled',
                    result.pending_axes,
                    result.accepted_requests,
                    error='readiness wait cancelled',
                    pending_navigation=result.pending_navigation,
                )
            remaining = deadline - monotonic()
            if remaining <= 0:
                return ReadinessResult(
                    'timeout',
                    result.pending_axes,
                    result.accepted_requests,
                    error='linked scientific readiness timed out',
                    pending_navigation=result.pending_navigation,
                )
            pump()
            sleep(min(interval, remaining))

    def checkpoint(  # noqa: PLR0911
        self,
        *,
        render_proof: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None,
    ) -> ReadinessResult:
        """Validate uploads around a caller-rendered capture and its generation proof.

        A proof must report ``source_generation``, ``capture_id``, and a full
        ``slice_requests`` mapping associated with that capture. Upload readiness
        without this evidence is reported as unavailable, never as displayed.
        """
        before = self.check()
        if before.status != 'ready':
            return before
        if not callable(render_proof):
            return ReadinessResult(
                'unavailable',
                accepted_requests=before.accepted_requests,
                error='caller-supplied rendered proof is required',
            )
        try:
            proof = render_proof(before.to_dict())
        except Exception as error:
            return ReadinessResult(
                'error',
                accepted_requests=before.accepted_requests,
                error=f'{type(error).__name__}: {error}',
            )
        after = self.check()
        if after.status != 'ready':
            return after
        if after.accepted_requests != before.accepted_requests:
            return ReadinessResult(
                'changed_during_render',
                accepted_requests=after.accepted_requests,
                error='accepted slice identity changed while rendered proof was produced',
            )
        if not isinstance(proof, Mapping):
            return ReadinessResult(
                'unavailable',
                accepted_requests=after.accepted_requests,
                error='render proof must be a mapping',
            )
        source_generation = proof.get('source_generation')
        capture_id = proof.get('capture_id')
        slice_requests = proof.get('slice_requests')
        if (
            not (
                (
                    isinstance(source_generation, int)
                    and not isinstance(source_generation, bool)
                    and source_generation >= 0
                )
                or (isinstance(source_generation, str) and bool(source_generation))
            )
            or not isinstance(capture_id, str)
            or not capture_id
            or not isinstance(slice_requests, Mapping)
        ):
            return ReadinessResult(
                'unavailable',
                accepted_requests=after.accepted_requests,
                error='render proof needs source_generation, capture_id, and slice_requests',
            )
        try:
            normalized = _json_value(slice_requests)
            generation = _json_value(source_generation)
        except (TypeError, ValueError) as error:
            return ReadinessResult('unavailable', error=str(error))
        if normalized != before.accepted_requests:
            return ReadinessResult(
                'unavailable',
                accepted_requests=after.accepted_requests,
                error='render proof does not identify the accepted slice requests',
            )
        checked_proof = _json_value(
            {
                'source_generation': generation,
                'capture_id': capture_id,
                'slice_requests': normalized,
            }
        )
        return ReadinessResult(
            'ready', accepted_requests=after.accepted_requests, proof=checked_proof
        )

    def close(self) -> None:
        """Detach the per-viewer wrapper, preserving any later replacement."""
        if self._closed:
            return
        self._closed = True
        if getattr(self.viewer._linked, '_upload_slice_payload', None) is self._wrapper:
            self.viewer._linked._upload_slice_payload = self._original_upload

    def __enter__(self) -> LinkedReadiness:
        """Return this adapter for use as a scoped context manager."""
        return self

    def __exit__(self, *_exc_info) -> None:
        """Restore the wrapped viewer method on context exit."""
        self.close()
