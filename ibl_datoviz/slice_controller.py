"""Explicit-unit navigation over the viewer's existing linked slice owner."""

from dataclasses import dataclass
from numbers import Integral
from threading import get_ident

import numpy as np

from .navigator import AtlasCursor


@dataclass(frozen=True)
class CursorState:
    """Voxel AP/ML/DV and world ML/AP/DV µm at the accepted cursor."""

    index: tuple[int, int, int]
    world_um: tuple[float, float, float]


@dataclass(frozen=True)
class CursorEvent:
    """Accepted cursor/request state; asynchronous textures may still be loading."""

    previous: CursorState
    current: CursorState
    revision: int


class CursorSubscription:
    """One viewer-owned cursor callback registration."""

    def __init__(self, owner, callback):
        self.owner, self.callback = owner, callback

    def close(self):
        """Release the callback once, including during viewer shutdown."""
        if self.owner is not None:
            self.owner._subscriptions.remove(self)
            self.owner = None


class SliceController:
    """Expose linked navigation without constructing another viewer or scheduler."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._notifying = False
        self._subscriptions = []
        self._revision = 0
        self.callback_errors = ()

    @property
    def available(self):
        """Whether construction supplied a linked layout and explicit slice source."""
        return self.viewer._linked is not None

    def _check(self):
        self.viewer._require_open()
        if not self.available:
            raise ValueError('slice navigation requires layout="linked" and a slice source')

    @property
    def position(self):
        """Return both coordinate orders explicitly; requires a linked viewer."""
        if self.viewer._closed:
            raise RuntimeError('viewer is closed')
        if get_ident() != self.viewer._owner_thread:
            raise RuntimeError('cursor reads require the viewer owning thread')
        if not self.available:
            raise ValueError('slice navigation requires layout="linked" and a slice source')
        return self._snapshot()

    def _snapshot(self):
        return CursorState(
            self.viewer._linked.cursor.as_index(),
            tuple(
                map(float, self.viewer._linked.cursor.world_um(self.viewer._linked.slice_source))
            ),
        )

    @property
    def revision(self):
        """Monotonic revision of accepted cursor movements."""
        return self._revision

    def set_position(self, *, ap, ml, dv, units, select_region=False):
        """Set voxel indices or nearest world-µm voxel; reject out-of-grid positions."""
        self._check()
        raw = (ap, ml, dv)
        if units == 'voxel':
            if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral) for v in raw):
                raise ValueError('voxel cursor coordinates must be integers')
            values = tuple(map(int, raw))
        elif units == 'um':
            if any(
                np.asarray(v).shape != () or np.asarray(v).dtype.kind not in 'iuf' for v in raw
            ):
                raise ValueError('world cursor coordinates must be finite numbers')
            world = np.asarray((ml, ap, dv), dtype=float)
            if not np.isfinite(world).all():
                raise ValueError('world cursor coordinates must be finite numbers')
            indices = np.asarray(self.viewer._linked.slice_source.grid.world_to_index(world))
            shape = np.asarray(self.viewer._linked.slice_source.grid.shape)
            if np.any(indices < -1e-8) or np.any(indices > shape - 1 + 1e-8):
                raise IndexError('cursor coordinate is outside the volume')
            values = tuple(map(int, np.rint(indices)))
        else:
            raise ValueError('cursor units must be voxel or um')
        self.viewer._linked.set_cursor(AtlasCursor(*values), select_region=select_region)

    def locate(self, observation):
        """Move slices to one attached point's supplied position without selecting anatomy.

        Requires a positioned point/channel/cluster/site. Paths, foreign or
        removed references, missing positions and out-of-grid coordinates fail
        before cursor mutation. Scientific observation selection is preserved.
        """
        from .payloads import Points  # noqa: PLC0415

        self._check()
        for layer in self.viewer.layers:
            if observation not in layer.refs:
                continue
            if not isinstance(layer.payload, Points):
                raise ValueError('slice location requires a point observation, not a path')
            index = layer.refs.index(observation)
            if not layer.payload.positioned[index]:
                raise ValueError('observation location is unavailable')
            ml, ap, dv = layer.payload.positions_um[index]
            return self.set_position(ap=ap, ml=ml, dv=dv, units='um')
        raise ValueError('observation reference is foreign, removed or unknown')

    @property
    def auto_slice(self):
        """Whether subsequent Regions-list selections move all three slices."""
        self._check()
        return self.viewer._linked._auto_slice.enabled

    def set_auto_slice(self, enabled):
        """Enable future region navigation without recentering the current selection."""
        self._check()
        self.viewer._linked._auto_slice.set_enabled(enabled)

    def set_layers(self, *, anatomy=None, annotations=None, boundaries=None):
        """Change presentation in the existing slice panels."""
        self._check()
        self.viewer._linked.set_slice_layers(
            anatomy=anatomy, annotations=annotations, boundaries=boundaries
        )

    def show_plane(self, axis, *, in_3d=True):
        """Show or remove the physical slice plane at the current cursor."""
        self._check()
        self.viewer._linked.set_slice_plane(axis, in_3d=in_3d)

    def step(self, axis, delta):
        """Move one slice by a signed voxel step without selecting anatomy."""
        self._check()
        return self.viewer._linked.step_slice(axis, delta)

    def select_region(self):
        """Toggle the anatomical region at the current spatial cursor."""
        self._check()
        self.viewer._linked.toggle_cursor_region_selection()

    def set_volume_opacity(self, opacity):
        """Set the optional 3-D volume opacity, hiding it at zero."""
        self._check()
        component = self.viewer._linked
        previous = component.volume_opacity
        component.set_volume_opacity(opacity)
        try:
            self.viewer._on_volume_opacity_committed(opacity)
        except Exception as error:
            if not self.viewer._closed:
                try:
                    component.set_volume_opacity(previous)
                except Exception:
                    self.viewer.close()
                    raise RuntimeError('volume context rollback failed; viewer closed') from error
            raise

    def on_changed(self, callback):
        """Subscribe to accepted cursor movement; failures do not undo commits."""
        self._check()
        if not callable(callback):
            raise TypeError('cursor callback must be callable')
        subscription = CursorSubscription(self, callback)
        self._subscriptions.append(subscription)
        return subscription

    def _publish(self, previous):
        current = self._snapshot()
        if previous == current:
            return
        self._revision += 1
        event = CursorEvent(previous, current, self._revision)
        errors = []
        self._notifying = True
        try:
            for subscription in tuple(self._subscriptions):
                if subscription.owner is self:
                    try:
                        subscription.callback(event)
                    except Exception as error:
                        errors.append(error)
        finally:
            self._notifying = False
        self.callback_errors = tuple(errors)

    def _close(self):
        for subscription in tuple(self._subscriptions):
            subscription.close()
