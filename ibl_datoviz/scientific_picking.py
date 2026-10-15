"""Exact native point and sphere identities bridged into the scientific selection controller.

This adapter owns no selection model. The pinned engine cannot compose paths or stroked
points with other geometry; their visible coverage blocks exact picking.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class _Registration:
    layer: object
    component: object
    visual_id: int
    keys: np.ndarray
    refs: tuple


class ScientificPicking:
    """Viewer-owned native query bridge with fail-closed coverage semantics.

    Register candidates before layer publication, unregister before destroying
    their native visuals, and invalidate pending clicks after scene/camera edits.
    Native result polling belongs to the viewer; ``poll()`` returns other results
    so callers may retain their public result stream. Native interactions have
    already received their results before the public queue is drained.
    """

    def __init__(self, viewer, *, external_blockers=None):
        self.viewer = viewer
        self._external_blockers = external_blockers
        self._registrations = {}
        self._channel = None
        self._channel_id = 0
        self._next_key = 1
        self._next_request = 0x5343000000000000
        self._generation = 0
        self._pending = None
        self._closed = False
        self.status = 'idle'
        self.reason = ''

    def _check(self):
        self.viewer._require_open()
        if self._closed:
            raise RuntimeError('scientific picking is closed')

    @staticmethod
    def capability_reason(layer):
        """Return an explicit native limitation, or an empty supported reason."""
        if layer._glyph in ('sphere', 'point'):
            # Scientific point layers use filled disks without depth cue or stroke.
            return ''
        return 'paths do not support composed frontmost native queries'

    @property
    def unavailable_reason(self):
        """Explain visible unsupported coverage without silently picking through it."""
        self._check()
        if self._external_blockers is not None:
            reasons = tuple(self._external_blockers())
            if reasons:
                return '; '.join(reasons)
        for layer in self.viewer.layers:
            if layer.effective_visible and any(layer.payload.positioned):
                reason = self.capability_reason(layer)
                if reason:
                    return f'{layer.name or "Unnamed layer"}: {reason}'
        return ''

    def register(self, layer, component):
        """Prepare owned positive native keys for a candidate filled-point or sphere component."""
        self._check()
        if self.capability_reason(layer) or not component.visual:
            return
        dvz = self.viewer.dvz
        if self._channel is None:
            self._channel = dvz.dvz_link_channel(self.viewer.scene, b'scientific-observations')
            if not self._channel:
                raise RuntimeError('scientific picking link channel creation failed')
            self._channel_id = int(dvz.dvz_link_channel_id(self._channel))
        refs = layer.positioned_refs
        end = self._next_key + len(refs)
        if end > 2**64:
            raise OverflowError('scientific picking native keys exhausted')
        keys = np.frombuffer(np.arange(self._next_key, end, dtype=np.uint64).tobytes(), np.uint64)
        self._next_key = end  # Never recycle keys after failed registration or removal.
        status = dvz.dvz_visual_set_query_capabilities(
            component.visual, dvz.DVZ_QUERY_CAPABILITY_ITEM
        )
        if status != 0:
            raise RuntimeError(f'scientific picking capability failed with status {status}')
        status = dvz.dvz_visual_set_link_keys(component.visual, self._channel, keys)
        if status != 0:
            raise RuntimeError(f'scientific observation link keys failed with status {status}')
        visual_id = int(dvz.dvz_visual_id(component.visual))
        self._registrations[visual_id] = _Registration(layer, component, visual_id, keys, refs)

    def unregister(self, component):
        """Forget a candidate or committed visual before native destruction."""
        self._check()
        self._registrations = {
            key: value
            for key, value in self._registrations.items()
            if value.component is not component
        }
        self.invalidate()

    def invalidate(self):
        """Discard queued intent after geometry, presentation, camera or input changes."""
        self._generation += 1
        self._pending = None
        if self.status == 'pending':
            self.status, self.reason = 'stale', 'scene or input changed before query completion'

    def request(self, x, y):
        """Queue one panel-local logical-pixel click; replace earlier pending intent."""
        self._check()
        position = np.asarray((x, y), dtype=float)
        if not np.isfinite(position).all():
            raise ValueError('picking coordinates must be finite logical pixels')
        self._pending = None
        reason = self.unavailable_reason
        if reason:
            self.status, self.reason = 'unavailable', reason
            return None
        request = self.viewer.dvz.dvz_query_request()
        self._next_request += 1
        request.request_id = self._next_request
        request.target = self.viewer.dvz.DVZ_SCENE_TARGET_ITEM
        request.hit_policy = self.viewer.dvz.DVZ_QUERY_HIT_FRONTMOST
        status = self.viewer.dvz.dvz_panel_query_px(
            self.viewer.panel, *position, ctypes.byref(request)
        )
        if status != 0:
            raise RuntimeError(f'scientific picking query failed with status {status}')
        self._pending = (request.request_id, self._generation, self.viewer.selection.revision)
        self.status, self.reason = 'pending', ''
        return int(request.request_id)

    def resolve(self, result):
        """Translate only a current, visible native point/sphere row to its exact reference."""
        self._check()
        dvz = self.viewer.dvz
        if int(result.scene_id) != int(dvz.dvz_scene_id(self.viewer.scene)) or int(
            result.panel_id
        ) != int(dvz.dvz_panel_id(self.viewer.panel)):
            return None
        if not result.hit or result.status != dvz.DVZ_QUERY_STATUS_HIT:
            return None
        registration = self._registrations.get(int(result.visual_id))
        if registration is None:
            return None  # Supported anatomical mesh hit: it blocks the sphere.
        layer = registration.layer
        if (
            layer._closed
            or not layer.effective_visible
            or layer._visual is not registration.component
            or result.link_channel != self._channel_id
        ):
            return None
        index = int(result.item_id)
        if not 0 <= index < len(registration.refs) or int(result.link_key) != int(
            registration.keys[index]
        ):
            return None
        ref = registration.refs[index]
        return ref if self.viewer._layer_registry.contains(ref) else None

    def consume(self, result):
        """Apply a matching click through the existing authoritative controller."""
        self._check()
        request_id = int(result.request_id)
        if request_id >> 48 != 0x5343:
            return False
        pending = self._pending
        if pending is None or request_id != pending[0]:
            return True
        self._pending = None
        if (
            pending[1] != self._generation
            or pending[2] != self.viewer.selection.revision
            or self.unavailable_reason
        ):
            self.status, self.reason = (
                'stale',
                'scene or selection changed before query completion',
            )
            return True
        dvz = self.viewer.dvz
        if result.status not in (
            dvz.DVZ_QUERY_STATUS_HIT,
            dvz.DVZ_QUERY_STATUS_MISS,
            dvz.DVZ_QUERY_STATUS_NO_CAPABLE_VISUAL,
            dvz.DVZ_QUERY_STATUS_OUTSIDE_PANEL,
        ):
            self.status, self.reason = 'error', f'native query status {result.status}'
            return True  # A failed query must never clear a successful selection.
        ref = self.resolve(result)
        if result.hit and int(result.visual_id) in self._registrations and ref is None:
            self.status, self.reason = 'stale', 'native identity no longer matches its attachment'
            return True
        self.viewer.selection.set_observations(() if ref is None else (ref,))
        self.status, self.reason = ('miss' if ref is None else 'hit'), ''
        return True

    def poll(self):
        """Consume completed scientific clicks, returning unrelated native results."""
        self._check()
        others = []
        result = self.viewer.dvz.DvzQueryResult()
        while self.viewer.dvz.dvz_scene_poll_query(self.viewer.scene, ctypes.byref(result)):
            if not self.consume(result):
                others.append(type(result).from_buffer_copy(bytes(result)))
        return tuple(others)

    def close(self):
        """Release retained identities before the viewer destroys its scene."""
        if not self._closed:
            self._check()
            self.invalidate()
            self._registrations.clear()
            if self._channel is not None:
                self.viewer.dvz.dvz_link_channel_destroy(self._channel)
            self._channel = None
            self._closed = True
