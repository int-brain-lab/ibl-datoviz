"""Immutable scientific geometry and identities, independent of native rendering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from numbers import Integral
from types import MappingProxyType

import numpy as np


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value


def _identity(value):
    if isinstance(value, str):
        return _text(value, 'observation ID')
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError('IDs must be integer or nonempty string labels, never booleans')
    return int(value)


def _freeze(value):
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError('provenance mapping keys must be strings')
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list, np.ndarray)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, np.generic):
        return _freeze(value.item())
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not np.isfinite(value):
            raise ValueError('provenance numeric values must be finite')
        return value
    raise ValueError('provenance must contain only mappings, sequences and scalar values')


def _provenance(value):
    if not isinstance(value, Mapping):
        raise ValueError('provenance must be a mapping')
    return _freeze(value)


def _array(value, dtype):
    # Immutable bytes backing prevents re-enabling writeability on retained arrays.
    array = np.array(value, dtype=dtype, order='C', copy=True)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True)
class SourceKey:
    """Content-pinned dataset identity without IBL-specific semantics."""

    provider: str
    dataset: str
    version: str
    content_sha256: str

    def __post_init__(self):
        """Validate the namespace and immutable content pin."""
        for name in ('provider', 'dataset', 'version'):
            _text(getattr(self, name), name)
        digest = self.content_sha256
        if (
            not isinstance(digest, str) or len(digest) != 64
            or any(char not in '0123456789abcdef' for char in digest)
        ):
            raise ValueError('content_sha256 must be a lowercase SHA-256 digest')


@dataclass(frozen=True)
class SourceObservationKey:
    """Original scientific identity, independent of viewer attachment."""

    source: SourceKey
    recording_id: str
    population: str
    original_id: int | str

    def __post_init__(self):
        """Reject ambiguous source scope and normalize integer labels."""
        if not isinstance(self.source, SourceKey):
            raise ValueError('source must be a SourceKey')
        _text(self.recording_id, 'recording_id')
        _text(self.population, 'population')
        object.__setattr__(self, 'original_id', _identity(self.original_id))


@dataclass(frozen=True)
class WorldFrame:
    """Shared anatomy reference ID with an explicit world-coordinate convention.

    ``ibl-mlapdv-um`` denotes the existing IBL atlas-world ML/AP/DV micrometre
    convention, including its bregma origin and axis orientation. A declaration
    alone does not establish source frame semantics. Reviewed evidence is an
    explicit ``verification`` provenance mapping containing nonempty ``method``
    and ``evidence`` strings. This identifies a coordinate frame, independently
    of insertion alignment quality or scientific source validation. These are
    retained assertions, not a validation service.
    """

    reference_space_id: str
    coordinate_convention: str = 'ibl-mlapdv-um'
    provenance: Mapping = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        """Snapshot frame evidence without inventing an atlas registry."""
        _text(self.reference_space_id, 'reference_space_id')
        _text(self.coordinate_convention, 'coordinate_convention')
        object.__setattr__(self, 'provenance', _provenance(self.provenance))

    def require_verified(self):
        """Require recorded evidence, rather than a bare compatibility assertion."""
        verification = self.provenance.get('verification')
        if not isinstance(verification, Mapping):
            raise ValueError('frame requires verification method and evidence provenance')
        for name in ('method', 'evidence'):
            _text(verification.get(name), f'frame verification {name}')
        return self


def _common(payload):
    ids = tuple(_identity(value) for value in payload.ids)
    if len(set(ids)) != len(ids):
        raise ValueError('observation IDs must be unique within a payload')
    if not isinstance(payload.frame, WorldFrame):
        raise ValueError('frame must be a WorldFrame')
    object.__setattr__(payload, 'ids', ids)
    object.__setattr__(payload, 'provenance', _provenance(payload.provenance))
    if payload.observation_keys is not None:
        keys = tuple(payload.observation_keys)
        if (
            len(keys) != len(ids)
            or not all(isinstance(key, SourceObservationKey) for key in keys)
            or tuple(key.original_id for key in keys) != ids
            or len(set(keys)) != len(keys)
        ):
            raise ValueError('observation_keys must exactly match the full ordered payload IDs')
        object.__setattr__(payload, 'observation_keys', keys)


@dataclass(frozen=True, eq=False)
class Points:
    """Complete point population; unavailable coordinates remain NaN rows."""

    ids: tuple
    positions_um: np.ndarray
    frame: WorldFrame
    provenance: Mapping
    observation_keys: tuple[SourceObservationKey, ...] | None = None
    allen_region_ids: np.ndarray | None = None

    def __post_init__(self):
        """Own geometry, region annotations and source identities."""
        _common(self)
        positions = _array(self.positions_um, np.float64)
        if positions.shape != (len(self.ids), 3) or np.isinf(positions).any():
            raise ValueError('positions_um must have shape (n, 3) without infinities')
        object.__setattr__(self, 'positions_um', positions)
        if self.allen_region_ids is not None:
            regions = np.asarray(self.allen_region_ids)
            if regions.shape != (len(self.ids),) or not np.issubdtype(regions.dtype, np.integer):
                raise ValueError('allen_region_ids must contain one integer per observation')
            object.__setattr__(self, 'allen_region_ids', _array(regions, np.int64))

    @property
    def positioned(self):
        """Return the finite-geometry row map without changing population order."""
        return _array(np.isfinite(self.positions_um).all(axis=1), bool)


@dataclass(frozen=True, eq=False)
class Channels(Points):
    """Original recording channels, including repeated physical coordinates."""


@dataclass(frozen=True, eq=False)
class Clusters(Points):
    """Original clusters with explicitly prepared positional meaning."""


@dataclass(frozen=True, eq=False)
class Sites(Points):
    """Physical sites or groups, with explicit optional channel membership."""

    memberships: tuple[tuple[SourceObservationKey, ...], ...] | None = None

    def __post_init__(self):
        """Snapshot known memberships without inventing original channel IDs."""
        super().__post_init__()
        if self.memberships is not None:
            groups = tuple(tuple(group) for group in self.memberships)
            if len(groups) != len(self.ids) or any(
                not all(isinstance(key, SourceObservationKey) for key in group)
                or len(set(group)) != len(group) for group in groups
            ):
                raise ValueError('memberships must give unique source keys for each site')
            object.__setattr__(self, 'memberships', groups)


@dataclass(frozen=True, eq=False)
class Paths:
    """Independently identified ordered polylines, with path-level identities."""

    ids: tuple
    positions_um: tuple[np.ndarray, ...]
    frame: WorldFrame
    provenance: Mapping
    observation_keys: tuple[SourceObservationKey, ...] | None = None

    def __post_init__(self):
        """Snapshot complete paths; missing vertices retain an unpositioned row."""
        _common(self)
        paths = tuple(_array(line, np.float64) for line in self.positions_um)
        if len(paths) != len(self.ids) or any(
            line.ndim != 2 or line.shape[1] != 3 or len(line) < 2 or np.isinf(line).any()
            for line in paths
        ):
            raise ValueError('each path requires an (n, 3) array, n >= 2, without infinities')
        object.__setattr__(self, 'positions_um', paths)

    @property
    def positioned(self):
        """Return which complete polylines have entirely finite geometry."""
        return _array([np.isfinite(line).all() for line in self.positions_um], bool)


@dataclass(frozen=True, eq=False, init=False)
class Trajectory(Paths):
    """One prepared recording trajectory with explicitly declared derivation."""

    def __init__(
        self, *, positions_um, frame, provenance, ids=('trajectory',), observation_keys=None,
    ):
        """Accept one vertex array and retain a stable trajectory label."""
        if len(ids) != 1:
            raise ValueError('a Trajectory contains exactly one path')
        super().__init__(ids, (positions_um,), frame, provenance, observation_keys)


def _recording_payload(payload, source, insertion_id, population):
    if payload.observation_keys is not None:
        return payload
    keys = tuple(
        SourceObservationKey(source, insertion_id, population, identity)
        for identity in payload.ids
    )
    if isinstance(payload, Trajectory):
        return Trajectory(
            ids=payload.ids, positions_um=payload.positions_um[0], frame=payload.frame,
            provenance=payload.provenance, observation_keys=keys,
        )
    return replace(payload, observation_keys=keys)


@dataclass(frozen=True, eq=False)
class Recording:
    """Prepared observations for one insertion, separate from session identity."""

    source: SourceKey
    insertion_id: str
    session_id: str
    channels: Channels | None = None
    clusters: Clusters | None = None
    sites: Sites | None = None
    path: Trajectory | None = None
    name: str = ''
    provenance: Mapping = field(default_factory=dict)

    def __post_init__(self):
        """Reject mixed frames or observations borrowed from another source."""
        if not isinstance(self.source, SourceKey):
            raise ValueError('source must be a SourceKey')
        _text(self.insertion_id, 'insertion_id')
        _text(self.session_id, 'session_id')
        if not isinstance(self.name, str):
            raise ValueError('name must be a string')
        object.__setattr__(self, 'provenance', _provenance(self.provenance))
        frames = []
        for name, kind in (
            ('channels', Channels), ('clusters', Clusters), ('sites', Sites), ('path', Trajectory),
        ):
            payload = getattr(self, name)
            if payload is None:
                continue
            if not isinstance(payload, kind):
                raise ValueError(f'{name} requires a {kind.__name__} payload')
            payload = _recording_payload(payload, self.source, self.insertion_id, name)
            object.__setattr__(self, name, payload)
            frames.append(payload.frame)
            if payload.observation_keys is not None and any(
                key.source != self.source or key.recording_id != self.insertion_id
                or key.population != name for key in payload.observation_keys
            ):
                raise ValueError(f'{name} source observation scope disagrees with recording')
            if name == 'sites' and payload.memberships is not None and any(
                key.source != self.source or key.recording_id != self.insertion_id
                or key.population != 'channels'
                for group in payload.memberships for key in group
            ):
                raise ValueError('site membership scope disagrees with recording channels')
        if frames and any(frame != frames[0] for frame in frames):
            raise ValueError('recording payloads must share the same world frame')
        if self.channels is not None and self.sites is not None and self.sites.memberships:
            channel_keys = set(self.channels.observation_keys)
            if any(key not in channel_keys for group in self.sites.memberships for key in group):
                raise ValueError('site membership contains an absent recording channel')

    @property
    def key(self):
        """Return the content-pinned insertion key, excluding display labels."""
        return self.source, self.insertion_id
