"""Terminal scientific and rendered-source evidence outside timed replay input."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np

from .interaction_benchmark import _json_value, scientific_state

if TYPE_CHECKING:
    from pathlib import Path


def _assert_callback_success(viewer):
    """Reject failures retained by callbacks that ctypes cannot propagate."""
    for name in ('_gui_callback_error', '_review_error'):
        error = getattr(viewer, name, None)
        if error:
            raise RuntimeError(f'{name} during terminal checkpoint: {error}')
    slice_error = getattr(viewer._linked, '_slice_error', None)
    if slice_error:
        raise RuntimeError(f'_slice_error during terminal checkpoint: {slice_error}')
    error = getattr(getattr(viewer, 'review_controls', None), 'error', None)
    if error:
        raise RuntimeError(f'review controls failed during terminal checkpoint: {error}')


def capture_terminal_checkpoint(viewer, readiness, *, output: Path | None = None):
    """Return terminal evidence or a structured failure, including callback errors."""
    try:
        _assert_callback_success(viewer)
        result = _capture_terminal_checkpoint(viewer, readiness, output=output)
        _assert_callback_success(viewer)
        return result
    except Exception as error:
        return {'status': 'error', 'error': f'{type(error).__name__}: {error}'}


def _capture_terminal_checkpoint(viewer, readiness, *, output: Path | None = None):
    """Settle uploads, then render and read the existing scientific source view.

    This designated capture proves terminal source rendering, not that the host
    presented that image during playback. It also works after the host closes,
    while its app-owned source and worker callbacks remain alive.
    """
    dvz = viewer.dvz
    if not all(
        callable(getattr(dvz, name, None))
        for name in (
            'dvz_gui_viewport_source',
            'dvz_view_render_serial',
            'dvz_view_render_once',
            'dvz_view_capture_rgba',
            'dvz_view_render_enabled',
            'dvz_view_set_render_enabled',
        )
    ):
        return {
            'status': 'unavailable',
            'error': 'native source capture APIs are unavailable',
            'scientific_state': scientific_state(viewer),
        }
    source = dvz.dvz_gui_viewport_source(viewer.viewport)
    if not source:
        return {'status': 'error', 'error': 'scientific viewport source is unavailable'}

    def pump():
        # Closed host views still drain owner-thread posts before skipping draw.
        if dvz.dvz_view_render_once(viewer.view) < 0:
            raise RuntimeError('terminal owner-thread work failed')
        drain = getattr(viewer._linked, '_drain_prepared_slices', None)
        if callable(drain):
            drain(viewer.view, None)
        _assert_callback_success(viewer)

    try:
        pump()
        settled = readiness.wait(timeout=10.0, pump=pump)
    except Exception as error:
        return {'status': 'error', 'error': f'{type(error).__name__}: {error}'}
    if settled.status != 'ready':
        return {'status': settled.status, 'readiness': settled.to_dict()}
    state = scientific_state(viewer)
    image = {}

    def capture_source(accepted):
        before = dvz.dvz_view_render_serial(source)
        if dvz.dvz_view_render_once(source) < 0:
            raise RuntimeError('terminal scientific source rendering failed')
        serial = dvz.dvz_view_render_serial(source)
        if serial != before + 1:
            raise RuntimeError('terminal source did not submit exactly one new frame')
        rgba = np.asarray(dvz.dvz_view_capture_rgba(source))
        if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4 or not rgba.size:
            raise RuntimeError('terminal source capture must contain RGBA8 pixels')
        if dvz.dvz_view_render_serial(source) != serial:
            raise RuntimeError('scientific source advanced during capture')
        image.update(
            {
                'shape': list(rgba.shape),
                'dtype': 'uint8',
                'sha256': hashlib.sha256(np.ascontiguousarray(rgba).tobytes()).hexdigest(),
            }
        )
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            if dvz.dvz_view_capture_png(source, str(output).encode()) != 0:
                raise RuntimeError('terminal source PNG capture failed')
            image['artifact'] = str(output)
        return {
            'source_generation': serial,
            'capture_id': f'rgba8-sha256:{image["sha256"]}',
            'slice_requests': accepted['accepted_requests'],
        }

    def render_proof(accepted):
        enabled = dvz.dvz_view_render_enabled(source)
        if not enabled and dvz.dvz_view_set_render_enabled(source, True) != 0:
            raise RuntimeError('could not enable terminal source capture')
        try:
            return capture_source(accepted)
        finally:
            if not enabled and dvz.dvz_view_set_render_enabled(source, False) != 0:
                raise RuntimeError('could not restore source render policy')

    rendered = readiness.checkpoint(render_proof=render_proof).to_dict()
    if scientific_state(viewer) != state:
        return {'status': 'changed_during_render', 'error': 'scientific state changed in capture'}
    return {
        'status': rendered['status'],
        'scientific_state': state,
        'rendering': rendered,
        'image': image,
        'scope': 'designated-terminal-source-capture',
    }


def _comparison_state(state):
    """Exclude scheduling revision counters while retaining scientific request content."""
    normalized = _json_value(state)
    for request in normalized.get('displayed_slice_requests', {}).values():
        if request is not None:
            request.pop('revision', None)
    return normalized


def compare_terminal_checkpoints(expected, observed):
    """Compare terminal scientific state and exact RGBA8 pixels; never infer throughput."""
    if not isinstance(expected, Mapping) or expected.get('status') != 'ready':
        return {'status': 'unavailable', 'reason': 'recording has no ready terminal checkpoint'}
    if observed.get('status') != 'ready':
        return {'status': 'unavailable', 'reason': 'replay terminal capture is not ready'}
    for checkpoint in (expected, observed):
        image = checkpoint.get('image', {})
        if not isinstance(image, Mapping):
            return {'status': 'unavailable', 'reason': 'invalid terminal checkpoint image'}
        shape = image.get('shape')
        if (
            checkpoint.get('scope') != 'designated-terminal-source-capture'
            or not isinstance(checkpoint.get('scientific_state'), Mapping)
            or not isinstance(shape, (list, tuple))
            or len(shape) != 3
            or any(type(value) is not int or value <= 0 for value in shape)
            or shape[2] != 4
            or image.get('dtype') != 'uint8'
            or not re.fullmatch('[0-9a-f]{64}', str(image.get('sha256', '')))
        ):
            return {'status': 'unavailable', 'reason': 'invalid terminal checkpoint evidence'}
    mismatches = []
    for key in ('scientific_state', 'image'):
        if key == 'scientific_state':
            left = _comparison_state(expected.get(key, {}))
            right = _comparison_state(observed.get(key, {}))
        else:
            fields = ('shape', 'dtype', 'sha256')
            left = {field: expected.get(key, {}).get(field) for field in fields}
            right = {field: observed.get(key, {}).get(field) for field in fields}
        if left != right:
            mismatches.append(key)
    return {
        'status': 'match' if not mismatches else 'mismatch',
        'mismatches': mismatches,
        'policy': 'exact-scientific-state-and-rgba8',
        'scope': 'terminal-only; intermediate work and throughput are unverified',
    }
