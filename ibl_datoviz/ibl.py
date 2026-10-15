"""Optional IBL source adapter and exact recording identities.

The shared data library owns file reading and validation. This module prepares
immutable display observations without reading source files or decoding spikes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from numbers import Integral

import numpy as np

from .component import owned

__all__ = [
    'BwmRecording', 'BwmSource', 'ObservationRef',
    'RecordingObservations', 'prepare_recording',
]

COORDINATE_CONVENTION = 'ibl-mlapdv-um'


@dataclass(frozen=True)
class ObservationRef:
    """An original channel or cluster ID scoped to one immutable recording."""

    dataset: str
    version: str
    manifest_sha256: str
    pid: str
    kind: str
    source_id: int

    def __post_init__(self):
        """Reject ambiguous identity types before equality or GUI key translation."""
        if self.kind not in ('channel', 'cluster'):
            raise ValueError('observation kind must be channel or cluster')
        _source_id(self.source_id)
        for value in (self.dataset, self.version, self.pid):
            if not isinstance(value, str) or not value:
                raise ValueError('observation source identity must contain nonempty strings')
        if (
            not isinstance(self.manifest_sha256, str) or len(self.manifest_sha256) != 64
            or any(char not in '0123456789abcdef' for char in self.manifest_sha256)
        ):
            raise ValueError('observation identity requires a lowercase manifest SHA-256')


@dataclass(frozen=True)
class RecordingObservations:
    """All source observations, including rows without displayable coordinates."""

    refs: tuple[ObservationRef, ...]
    positions_um: np.ndarray
    position_meaning: str

    def __post_init__(self):
        """Own retained positions; NaNs retain unavailable source coordinates."""
        refs = tuple(self.refs)
        if not all(isinstance(ref, ObservationRef) for ref in refs):
            raise ValueError('observations require scoped ObservationRef identities')
        positions = owned(self.positions_um, np.float64)
        if positions.shape != (len(refs), 3) or np.isinf(positions).any():
            raise ValueError('observation positions must have shape (n, 3), without infinities')
        if len(set(refs)) != len(refs):
            raise ValueError('observation identities must be unique')
        object.__setattr__(self, 'positions_um', positions)
        object.__setattr__(self, 'refs', refs)

    @property
    def positioned(self):
        """Return which source rows have all three finite coordinates."""
        return np.isfinite(self.positions_um).all(axis=1)


@dataclass(frozen=True)
class BwmRecording:
    """Prepared geometry with detached source tables and their provenance."""

    metadata: object
    channels: RecordingObservations
    clusters: RecordingObservations
    coordinate_convention: str
    object_id: str | None = None

    @property
    def key(self):
        """Return a source/version/manifest/PID recording identity."""
        data = self.metadata
        return (data.dataset_name, data.dataset_version, data.manifest_sha256, data.pid)

    @property
    def pid(self):
        """Return the original insertion UUID."""
        return self.metadata.pid

    @property
    def eid(self):
        """Return the original session UUID."""
        return self.metadata.eid


def _source_id(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError('source IDs must be nonnegative integers, including zero')
    return int(value)


def _position(row):
    values = [row.get(name) for name in ('mlapdv_x', 'mlapdv_y', 'mlapdv_z')]
    return [np.nan if value is None else float(value) for value in values]


def prepare_recording(metadata, *, coordinate_convention, object_id=None):
    """Adapt explicitly declared legacy ML/AP/DV µm coordinates without reduction.

    BWM 1.1.0 does not declare field units in its schema. Callers must explicitly
    choose the documented IBL convention; numeric magnitudes never select it.
    Cluster markers use the assigned channel position, not unit x/y/z fields.
    """
    if coordinate_convention != COORDINATE_CONVENTION:
        raise ValueError(f'explicit coordinate_convention={COORDINATE_CONVENTION!r} is required')
    metadata = deepcopy(metadata)
    channel_rows = metadata.channels.frame.to_dict(orient='records')
    unit_rows = metadata.units.frame.to_dict(orient='records')

    def reference(kind, identity):
        return ObservationRef(
            metadata.dataset_name, metadata.dataset_version, metadata.manifest_sha256,
            metadata.pid, kind, _source_id(identity),
        )

    positions = {}
    refs, coordinates = [], []
    for row in channel_rows:
        if row.get('pid') != metadata.pid or row.get('eid', metadata.eid) != metadata.eid:
            raise ValueError('channel recording identity disagrees with insertion')
        identity = _source_id(row['channel_id'])
        if identity in positions:
            raise ValueError('duplicate channel ID within insertion')
        position = _position(row)
        positions[identity] = position
        refs.append(reference('channel', identity))
        coordinates.append(position)
    channels = RecordingObservations(
        tuple(refs), np.asarray(coordinates).reshape(-1, 3), 'supplied channel location',
    )
    refs, coordinates = [], []
    for row in unit_rows:
        if row.get('pid') != metadata.pid or row.get('eid', metadata.eid) != metadata.eid:
            raise ValueError('cluster recording identity disagrees with insertion')
        refs.append(reference('cluster', row['cluster_id']))
        identity = row.get('channels')
        if identity is None or (isinstance(identity, float) and np.isnan(identity)):
            coordinates.append([np.nan] * 3)
            continue
        # Nullable integer columns can arrive as floats, but never round a label.
        if isinstance(identity, (float, np.floating)) and np.isfinite(identity):
            if not float(identity).is_integer():
                raise ValueError('cluster channel association is not an integer ID')
            identity = int(identity)
        identity = _source_id(identity)
        if identity not in positions:
            raise ValueError('cluster channel association is absent from this insertion')
        coordinates.append(positions[identity])
    clusters = RecordingObservations(
        tuple(refs), np.asarray(coordinates).reshape(-1, 3), 'assigned channel location',
    )
    return BwmRecording(metadata, channels, clusters, coordinate_convention, object_id)


class BwmSource:
    """Prepare IBL observations through the optional shared data access library."""

    def __init__(self, *, release=None, workspace=None, coordinate_convention):
        """Select exactly one explicit release or existing catalog workspace."""
        if (release is None) == (workspace is None):
            raise ValueError('provide exactly one release or workspace')
        if coordinate_convention != COORDINATE_CONVENTION:
            raise ValueError(
                f'explicit coordinate_convention={COORDINATE_CONVENTION!r} is required'
            )
        self.release = release
        self.workspace = workspace
        self.coordinate_convention = coordinate_convention

    @classmethod
    def from_release(cls, path, *, coordinate_convention, expected_manifest_sha256=None):
        """Open source metadata without importing converter or signal dependencies."""
        try:
            # Keep the source data library optional for renderer-only callers.
            from ibl_ai_agent.access import open_bwm_release  # noqa: PLC0415
        except ImportError as error:
            raise ImportError(
                'BWM integration requires ibl-ai-agent-next with its packages extra '
                'and public open_bwm_release metadata API'
            ) from error
        return cls(
            release=open_bwm_release(path, expected_manifest_sha256=expected_manifest_sha256),
            coordinate_convention=coordinate_convention,
        )

    @classmethod
    def from_workspace(cls, workspace, *, coordinate_convention):
        """Use registered BWM identities, immutable release pins and signal gates."""
        return cls(workspace=workspace, coordinate_convention=coordinate_convention)

    def insertion(self, pid):
        """Prepare all channel and released-unit rows for one unambiguous PID."""
        object_id = None
        if self.workspace is None:
            metadata = self.release.insertion(pid)
        else:
            matches = []
            for item in self.workspace.objects(semantic_type='spike_sorting'):
                description = self.workspace.describe(item['id'])
                if description['data_object']['metadata'].get('pid') == pid:
                    matches.append(item['id'])
            if len(matches) != 1:
                raise ValueError(f'PID {pid!r} resolves to {len(matches)} catalog objects')
            object_id = matches[0]
            metadata = self.workspace.bwm_recording(object_id)
        return prepare_recording(
            metadata, coordinate_convention=self.coordinate_convention, object_id=object_id,
        )

    def spikes(self, recording, *, requirements):
        """Load explicitly requested signals through their existing validation gate."""
        if self.workspace is None or recording.object_id is None:
            raise ValueError('spike access requires a recording from a registered workspace')
        metadata = self.workspace.bwm_recording(recording.object_id)
        if recording.key != (
            metadata.dataset_name, metadata.dataset_version,
            metadata.manifest_sha256, metadata.pid,
        ):
            raise ValueError('registered recording identity changed since geometry preparation')
        spikes = self.workspace.spikes(recording.object_id, requirements=requirements)
        if not set(spikes.unit_ids) <= {ref.source_id for ref in recording.clusters.refs}:
            raise ValueError('spike identities disagree with the recording cluster metadata')
        return spikes
