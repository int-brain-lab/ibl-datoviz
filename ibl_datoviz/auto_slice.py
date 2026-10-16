"""Owner-thread intent over asynchronous, exact-grid region anchors."""

from .latest_wins import LatestWinsExecutor
from .region_navigation import RegionNavigation


class AutoSliceNavigation:
    """Keep region-list navigation optional and discard superseded preparation."""

    def __init__(self, source, *, notify=None):
        self.navigation = RegionNavigation(source)
        self.enabled = True
        self.status = self.navigation.unavailable_reason
        self._worker = LatestWinsExecutor(self._prepare, notify=notify, max_workers=1)

    def _prepare(self, token):
        return self.navigation.anchor(*token)

    def cancel(self):
        """Cancel navigation intent without interrupting an active NumPy operation."""
        self._worker.cancel('region')
        self.status = self.navigation.unavailable_reason

    def set_enabled(self, enabled):
        """Change future selection behavior without moving the current cursor."""
        if not isinstance(enabled, bool):
            raise ValueError('auto-slice must be boolean')
        self.cancel()
        self.enabled = enabled

    def request(self, mapping, region_id):
        """Prepare an interior anchor only for an explicit Regions-list intent."""
        self.cancel()
        if not self.enabled or not self.navigation.available or region_id is None:
            return
        self.status = 'Finding slices for selected region…'
        self._worker.request('region', (mapping, region_id))

    def drain(self):
        """Consume the latest anchor; lookup failures leave the cursor untouched."""
        try:
            ready = self._worker.drain_ready()
        except Exception as error:
            self.status = f'Auto-slice unavailable: {error}'
            return None
        if not ready:
            return None
        anchor = ready[-1].result
        self.status = '' if anchor is not None else 'No occupied voxel for selected region'
        return anchor

    def close(self):
        """Join lookup work before the owning viewer releases its resources."""
        self._worker.close()
