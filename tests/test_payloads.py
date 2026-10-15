"""Scientific payload ownership and source/geometry identity invariants."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from ibl_datoviz.payloads import (
    Channels,
    Clusters,
    Paths,
    Points,
    Recording,
    Sites,
    SourceKey,
    SourceObservationKey,
    Trajectory,
    WorldFrame,
)


@pytest.fixture
def frame():
    return WorldFrame('allen-ccf-2017', provenance={
        'verification': {'method': 'registered transform', 'evidence': 'fixture transform pin'},
    })


@pytest.fixture
def source():
    return SourceKey('lab', 'dataset', '1', 'a' * 64)


def test_geometry_and_nested_provenance_are_independent_immutable_snapshots(frame):
    xyz = np.array([[1., 2., 3.], [np.nan, 0., 0.]])
    metadata = {'derivation': {'steps': ['input']}}
    points = Points((0, 'missing'), xyz, frame, metadata)
    xyz[0] = 999
    metadata['derivation']['steps'].append('changed')
    assert points.positions_um[0].tolist() == [1, 2, 3]
    assert points.provenance['derivation']['steps'] == ('input',)
    assert points.positioned.tolist() == [True, False]
    with pytest.raises(ValueError):
        points.positions_um.setflags(write=True)
    with pytest.raises(TypeError):
        points.provenance['derivation']['new'] = 1
    with pytest.raises(FrozenInstanceError):
        points.ids = (1, 2)


@pytest.mark.parametrize('ids', [(True,), (np.bool_(False),), (1.,), ('',), (0, 0)])
def test_ambiguous_or_duplicate_ids_fail(frame, ids):
    with pytest.raises(ValueError):
        Points(ids, np.zeros((len(ids), 3)), frame, {})


def test_zero_labels_repeated_coordinates_and_all_missing_rows_survive(frame):
    points = Channels((np.int64(0), 10, 42), [[1, 1, 1], [1, 1, 1], [np.nan] * 3], frame, {})
    assert points.ids == (0, 10, 42)
    assert points.positioned.tolist() == [True, True, False]
    empty = Clusters((), np.empty((0, 3)), frame, {})
    assert empty.positioned.tolist() == []


@pytest.mark.parametrize('xyz', [[[0, 0]], [[0, 0, np.inf]], [[0, 0, -np.inf]]])
def test_invalid_positions_fail(frame, xyz):
    with pytest.raises(ValueError):
        Points((0,), xyz, frame, {})


def test_source_keys_align_original_ids_and_preserve_scope(frame, source):
    key = SourceObservationKey(source, 'probe-a', 'clusters', 0)
    other = SourceObservationKey(source, 'probe-b', 'clusters', 0)
    assert key != other
    points = Clusters((0,), [[0, 0, 0]], frame, {}, observation_keys=(key,))
    assert points.observation_keys == (key,)
    with pytest.raises(ValueError, match='ordered'):
        Clusters((1,), [[0, 0, 0]], frame, {}, observation_keys=(key,))


def test_path_identity_is_per_polyline_and_missing_path_is_preserved(frame):
    vertices = np.array([[0., 0., 0.], [1., 2., 3.]])
    paths = Paths(('first', 'missing'), (vertices, [[0, 0, 0], [np.nan] * 3]), frame, {})
    vertices[:] = 100
    assert len(paths.ids) == 2
    assert paths.positioned.tolist() == [True, False]
    assert paths.positions_um[0][-1].tolist() == [1, 2, 3]
    with pytest.raises(ValueError):
        paths.positions_um[0].setflags(write=True)
    with pytest.raises(ValueError):
        Paths(('short',), ([[0, 0, 0]],), frame, {})


def test_frame_evidence_is_required_separately_from_declared_convention(frame):
    assert frame.require_verified() is frame
    with pytest.raises(ValueError, match='verification'):
        WorldFrame('allen-ccf-2017').require_verified()
    with pytest.raises(ValueError):
        WorldFrame('allen-ccf-2017', provenance={'verification': True}).require_verified()
    assert frame != WorldFrame('another-reference', provenance=frame.provenance)
    assert frame != WorldFrame('allen-ccf-2017', 'other-convention', frame.provenance)


def test_recording_scope_and_frame_conflicts_fail(frame, source):
    channel_key = SourceObservationKey(source, 'pid-a', 'channels', 0)
    channels = Channels((0,), [[0, 0, 0]], frame, {}, observation_keys=(channel_key,))
    recording = Recording(source, 'pid-a', 'eid-a', channels=channels)
    assert recording.key == (source, 'pid-a')
    with pytest.raises(ValueError, match='scope'):
        Recording(source, 'pid-b', 'eid-a', channels=channels)
    other_frame = WorldFrame('other-reference')
    clusters = Clusters((0,), [[0, 0, 0]], other_frame, {})
    with pytest.raises(ValueError, match='frame'):
        Recording(source, 'pid-a', 'eid-a', channels=channels, clusters=clusters)


def test_sites_preserve_declared_channel_membership_and_trajectory(frame, source):
    members = [[SourceObservationKey(source, 'pid', 'channels', 0)]]
    sites = Sites(('group-a',), [[0, 0, 0]], frame, {}, memberships=members)
    members[0].clear()
    assert sites.memberships[0][0].original_id == 0
    path = Trajectory(positions_um=[[0, 0, 0], [0, 0, 1]], frame=frame,
                      provenance={'derivation': 'supplied path'})
    assert path.ids == ('trajectory',)
    recording = Recording(source, 'pid', 'session', sites=sites, path=path)
    assert recording.path.provenance == path.provenance


def test_region_annotations_are_not_coerced_from_floats(frame):
    with pytest.raises(ValueError, match='integer'):
        Channels((0,), [[0, 0, 0]], frame, {}, allen_region_ids=[1.2])


def test_recording_assigns_source_keys_without_mutating_manual_payloads(frame, source):
    channels = Channels((0,), [[0, 0, 0]], frame, {})
    path = Trajectory(positions_um=[[0, 0, 0], [0, 0, 1]], frame=frame, provenance={})
    recording = Recording(source, 'pid', 'session', channels=channels, path=path)
    assert channels.observation_keys is None
    assert path.observation_keys is None
    assert isinstance(recording.channels, Channels)
    assert isinstance(recording.path, Trajectory)
    assert recording.channels.observation_keys == (
        SourceObservationKey(source, 'pid', 'channels', 0),
    )
    assert recording.path.observation_keys == (
        SourceObservationKey(source, 'pid', 'path', 'trajectory'),
    )
    assert recording.path.positions_um[0].shape == (2, 3)
    other = Recording(source, 'other-pid', 'session', channels=channels)
    assert recording.channels.observation_keys != other.channels.observation_keys


def test_site_membership_requires_present_original_channel_when_channels_supplied(frame, source):
    channels = Channels((0,), [[0, 0, 0]], frame, {})
    member = SourceObservationKey(source, 'pid', 'channels', 99)
    sites = Sites(('site',), [[0, 0, 0]], frame, {}, memberships=((member,),))
    with pytest.raises(ValueError, match='absent recording channel'):
        Recording(source, 'pid', 'session', channels=channels, sites=sites)
    # Membership may still document channels when the channel population is absent.
    assert Recording(source, 'pid', 'session', sites=sites).sites.memberships == ((member,),)


@pytest.mark.parametrize('digest', ['f' * 63, 'G' * 64, 'f' * 65])
def test_source_pin_requires_exact_sha256(digest):
    with pytest.raises(ValueError, match='SHA-256'):
        SourceKey('lab', 'dataset', 'release', digest)
