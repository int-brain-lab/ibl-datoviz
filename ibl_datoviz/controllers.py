"""Scientific selection and presentation controllers for the owned viewer."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from threading import get_ident


@dataclass(frozen=True)
class SelectionState:
    """Committed region namespaces and attachment-specific observations."""

    regions: tuple
    observations: tuple


@dataclass(frozen=True)
class SelectionEvent:
    """One successful scientific selection transition."""

    previous: SelectionState
    current: SelectionState
    reason: str
    revision: int


class SelectionSubscription:
    """An independently closable viewer-owned change subscription."""

    def __init__(self, owner, callback):
        self.owner, self.callback = owner, callback

    def close(self):
        """Unsubscribe idempotently."""
        if self.owner is not None:
            self.owner._subscriptions.remove(self)
            self.owner = None


class SelectionController:
    """Keep exact observations separate from mapping-dependent region selection."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._observations = ()
        self._state = self.snapshot()
        self._revision = 0
        self._subscriptions = []
        self._notifying = False
        self._hold_events = 0
        self.callback_errors = ()

    @property
    def observations(self):
        """Return selected exact attachment references, including hidden rows."""
        return self._observations

    @property
    def regions(self):
        """Return immutable (mapping, signed ID) region references."""
        return self.snapshot().regions

    @property
    def revision(self):
        """Return the last committed selection event revision."""
        return self._revision

    def snapshot(self):
        """Read scientific state without querying native renderer indices."""
        return SelectionState(
            tuple((self.viewer.mapping, value) for value in self.viewer.selected_region_ids()),
            self._observations,
        )

    def _check_mutation(self):
        self.viewer._require_open()
        if get_ident() != self.viewer._owner_thread:
            raise RuntimeError('viewer mutations require its owning thread')
        if self._notifying:
            raise RuntimeError('selection callbacks cannot mutate the viewer reentrantly')

    def _publish(self, reason):
        if self._hold_events:
            return
        current = self.snapshot()
        if current == self._state:
            return
        self._revision += 1
        event = SelectionEvent(self._state, current, reason, self._revision)
        self._state = current
        errors = []
        self._notifying = True
        try:
            for subscription in tuple(self._subscriptions):
                if subscription.owner is self:
                    try:
                        subscription.callback(event)
                    except Exception as error:
                        # A callback cannot undo native/retained state already committed.
                        errors.append(error)
        finally:
            self._notifying = False
        self.callback_errors = tuple(errors)

    def set_observations(self, refs):
        """Replace exact selection after validating every attached reference."""
        self._check_mutation()
        refs = tuple(dict.fromkeys(refs))
        registry = self.viewer._layer_registry
        if any(not registry.contains(ref) for ref in refs):
            raise ValueError('observation reference is foreign, removed or unknown')
        if refs == self._observations:
            return
        tables = getattr(self.viewer, 'tables', None)
        if tables is not None:
            tables._set_selection(refs)
        try:
            registry.update_selection(refs)
        except Exception:
            if tables is not None and not self.viewer._closed:
                try:
                    tables._set_selection(self._observations)
                except Exception as rollback_error:
                    self.viewer.close()
                    raise RuntimeError(
                        'observation table rollback failed; viewer closed'
                    ) from rollback_error
            raise
        self._observations = refs
        self._publish('observations')

    def set_regions(self, region_ids, *, mapping):
        """Select IDs in the current mapping; namespace mismatches fail."""
        self._check_mutation()
        if mapping != self.viewer.mapping:
            raise ValueError('region selection mapping must match the current viewer mapping')
        region_ids = tuple(region_ids)
        if any(isinstance(value, bool) or not isinstance(value, Integral) for value in region_ids):
            raise ValueError('region IDs must be signed integers, never booleans or row indices')
        self.viewer.set_selected_region_ids(region_ids)

    def clear_observations(self):
        """Clear exact observations without changing regions or visibility."""
        self.set_observations(())

    def clear_regions(self):
        """Clear only the region-selection domain."""
        self.set_regions((), mapping=self.viewer.mapping)

    def clear(self):
        """Clear both domains with one committed event, rolling back on failure."""
        self._check_mutation()
        previous = self._observations
        self._hold_events += 1
        try:
            self.set_observations(())
            try:
                self.viewer.set_selected_region_ids(())
            except Exception:
                try:
                    self.set_observations(previous)
                except Exception as rollback_error:
                    self.viewer.close()
                    raise RuntimeError(
                        'selection rollback failed; viewer closed'
                    ) from rollback_error
                raise
        finally:
            self._hold_events -= 1
        self._publish('clear')

    def _removed(self, refs):
        tables = getattr(self.viewer, 'tables', None)
        if tables is not None:
            tables._remove(refs)
        removed = set(refs)
        self._observations = tuple(ref for ref in self._observations if ref not in removed)
        self._publish('removed')

    def on_changed(self, callback):
        """Subscribe; callback failures are exposed through callback_errors."""
        self._check_mutation()
        if not callable(callback):
            raise TypeError('selection callback must be callable')
        subscription = SelectionSubscription(self, callback)
        self._subscriptions.append(subscription)
        return subscription

    def _close(self):
        """Release callback references during viewer teardown only."""
        for subscription in tuple(self._subscriptions):
            subscription.close()
        self._observations = ()


class AnatomyController:
    """Present anatomy through the viewer's existing transactional operations."""

    def __init__(self, viewer):
        self.viewer = viewer

    def set_context(self, context):
        """Choose supplied major surfaces or detailed anatomy explicitly."""
        if context == 'major' and self.viewer._anatomical_context is None:
            raise ValueError('major anatomy requires prepared source-native context surfaces')
        self.viewer.set_anatomy_presentation(context)

    def set_opacity(self, opacity):
        """Set the opacity of the active anatomical context."""
        if self.viewer.anatomy_presentation == 'major':
            self.viewer.set_context_opacity(opacity)
        else:
            self.viewer.set_surface_opacity(opacity)

    def set_mapping(self, mapping):
        """Change mapping and reset only region selection."""
        self.viewer.set_mapping(mapping)

    def set_explode(self, amount):
        """Adjust regional explosion without changing exact observations."""
        self.viewer.set_explode(amount)

    def set_hemispheres(self, *, left, right):
        """Apply hemisphere visibility as one surface-style update."""
        self.viewer._require_open()
        candidate = self.viewer._surface_presentation.style.copy()
        candidate.set_hemisphere_visible('left', left)
        candidate.set_hemisphere_visible('right', right)
        self.viewer._commit_surface_style(candidate)


class CameraController:
    """Expose the current camera and its established startup reset baseline."""

    def __init__(self, viewer):
        self.viewer = viewer

    def set_view(self, view):
        """Apply the accepted recording-context orientation or explicit angles."""
        if isinstance(view, str):
            if view != 'recording':
                raise ValueError('unknown camera view')
            view = (-1.15, -0.20, 2.50)
        self.viewer.set_camera_angles(view)

    def reset(self):
        """Restore the same baseline as the Reset view button and double-click."""
        self.viewer._require_open()
        self.viewer._invalidate_picking()
        if self.viewer.arcball is not None:
            self.viewer._check(
                self.viewer.dvz.dvz_arcball_reset(self.viewer.arcball), 'camera reset'
            )
