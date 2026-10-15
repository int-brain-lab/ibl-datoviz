from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.ibl import (
    COORDINATE_CONVENTION,
    BwmSource,
    ObservationRef,
    prepare_recording,
)


class Table:
    def __init__(self, rows):
        self.rows = rows

    @property
    def frame(self):
        return self

    def to_dict(self, *, orient):
        assert orient == 'records'
        return [dict(row) for row in self.rows]


def metadata(*, channels=None, units=None, pid='pid-a', version='1.1.0', digest='a' * 64):
    return SimpleNamespace(
        dataset_name='bwm',
        dataset_version=version,
        manifest_sha256=digest,
        pid=pid,
        eid='eid-a',
        channels=Table(channels or []),
        units=Table(units or []),
    )


def test_identity_scopes_same_source_ids_to_manifest_version_and_pid():
    base = ObservationRef('bwm', '1.1.0', 'a' * 64, 'pid-a', 'channel', 0)
    others = (
        ObservationRef('bwm', '1.1.0', 'b' * 64, 'pid-a', 'channel', 0),
        ObservationRef('bwm', '1.2.0', 'a' * 64, 'pid-a', 'channel', 0),
        ObservationRef('bwm', '1.1.0', 'a' * 64, 'pid-b', 'channel', 0),
        ObservationRef('bwm', '1.1.0', 'a' * 64, 'pid-a', 'cluster', 0),
    )
    assert all(base != other for other in others)
    assert ObservationRef('bwm', '1.1.0', 'a' * 64, 'pid-a', 'cluster', 0).source_id == 0
    with pytest.raises(ValueError, match='source IDs'):
        ObservationRef('bwm', '1.1.0', 'a' * 64, 'pid-a', 'channel', True)


def test_prepare_keeps_unpositioned_rows_and_cluster_channel_locations():
    source_channels = [
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'channel_id': 0,
            'mlapdv_x': 10,
            'mlapdv_y': 20,
            'mlapdv_z': 30,
        },
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'channel_id': 1,
            'mlapdv_x': None,
            'mlapdv_y': 50,
            'mlapdv_z': 60,
        },
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'channel_id': 2,
            'mlapdv_x': 10,
            'mlapdv_y': 20,
            'mlapdv_z': 30,
        },
    ]
    units = [
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'cluster_id': 0,
            'channels': 0,
            'x': 900,
            'y': 901,
            'z': 902,
        },
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'cluster_id': 1,
            'channels': 1,
            'x': 800,
            'y': 801,
            'z': 802,
        },
        {
            'pid': 'pid-a',
            'eid': 'eid-a',
            'cluster_id': 2,
            'channels': None,
            'x': 700,
            'y': 701,
            'z': 702,
        },
    ]
    recording = prepare_recording(
        metadata(channels=source_channels, units=units),
        coordinate_convention=COORDINATE_CONVENTION,
    )
    assert [ref.source_id for ref in recording.channels.refs] == [0, 1, 2]
    assert [ref.source_id for ref in recording.clusters.refs] == [0, 1, 2]
    np.testing.assert_array_equal(recording.channels.positioned, [True, False, True])
    np.testing.assert_array_equal(recording.clusters.positioned, [True, False, False])
    np.testing.assert_array_equal(recording.clusters.positions_um[0], [10, 20, 30])
    assert np.isnan(recording.clusters.positions_um[1, 0])
    np.testing.assert_array_equal(recording.clusters.positions_um[1, 1:], [50, 60])
    assert np.isnan(recording.clusters.positions_um[2]).all()
    assert (
        recording.channels.positions_um[0].tolist() == recording.channels.positions_um[2].tolist()
    )


@pytest.mark.parametrize('coordinate_convention', [None, 'guess-from-values', 'ibl-mlapdv-mm'])
def test_prepare_requires_explicit_supported_coordinate_profile(coordinate_convention):
    with pytest.raises(ValueError, match='coordinate_convention'):
        prepare_recording(metadata(), coordinate_convention=coordinate_convention)


@pytest.mark.parametrize('bad_id', [-1, 1.5, True, '2'])
def test_prepare_rejects_invalid_channel_or_cluster_ids(bad_id):
    channel = {'pid': 'pid-a', 'channel_id': bad_id, 'mlapdv_x': 0, 'mlapdv_y': 0, 'mlapdv_z': 0}
    with pytest.raises(ValueError, match='source IDs'):
        prepare_recording(
            metadata(channels=[channel]),
            coordinate_convention=COORDINATE_CONVENTION,
        )
    unit = {'pid': 'pid-a', 'cluster_id': bad_id, 'channels': 0}
    with pytest.raises(ValueError, match='source IDs'):
        prepare_recording(
            metadata(
                channels=[
                    {'pid': 'pid-a', 'channel_id': 0, 'mlapdv_x': 0, 'mlapdv_y': 0, 'mlapdv_z': 0}
                ],
                units=[unit],
            ),
            coordinate_convention=COORDINATE_CONVENTION,
        )


def test_prepare_rejects_invalid_channel_associations_and_recording_identity():
    channel = {'pid': 'pid-a', 'channel_id': 0, 'mlapdv_x': 0, 'mlapdv_y': 0, 'mlapdv_z': 0}
    for association in (4, -1, 1.5, True):
        with pytest.raises(ValueError):
            prepare_recording(
                metadata(
                    channels=[channel],
                    units=[{'pid': 'pid-a', 'cluster_id': 5, 'channels': association}],
                ),
                coordinate_convention=COORDINATE_CONVENTION,
            )
    with pytest.raises(ValueError, match='identity'):
        prepare_recording(
            metadata(channels=[{**channel, 'pid': 'pid-b'}]),
            coordinate_convention=COORDINATE_CONVENTION,
        )


def test_retained_positions_are_detached_read_only_and_do_not_track_inputs():
    row = {'pid': 'pid-a', 'channel_id': 3, 'mlapdv_x': 1, 'mlapdv_y': 2, 'mlapdv_z': 3}
    source = metadata(channels=[row])
    recording = prepare_recording(source, coordinate_convention=COORDINATE_CONVENTION)
    retained = recording.channels.positions_um
    row['mlapdv_x'] = 999
    assert not retained.flags.writeable
    with pytest.raises(ValueError):
        retained[0, 0] = -1
    np.testing.assert_array_equal(retained, [[1, 2, 3]])


class Workspace:
    def __init__(self, metadata_by_id, descriptions=None):
        self.metadata_by_id = metadata_by_id
        self.descriptions = descriptions or {
            object_id: {'data_object': {'metadata': {'pid': item.pid}}}
            for object_id, item in metadata_by_id.items()
        }
        self.recording_calls = []

    def objects(self, *, semantic_type):
        assert semantic_type == 'spike_sorting'
        return [{'id': object_id} for object_id in self.metadata_by_id]

    def describe(self, object_id):
        return self.descriptions[object_id]

    def bwm_recording(self, object_id):
        self.recording_calls.append(object_id)
        return self.metadata_by_id[object_id]

    def spikes(self, object_id, *, requirements):
        self.spike_call = (object_id, requirements)
        return self.spike_value


def test_workspace_resolves_unique_pid_and_delegates_public_bwm_recording():
    source_meta = metadata(
        channels=[{'pid': 'pid-a', 'channel_id': 0, 'mlapdv_x': 1, 'mlapdv_y': 2, 'mlapdv_z': 3}]
    )
    workspace = Workspace({'object-a': source_meta})
    source = BwmSource.from_workspace(workspace, coordinate_convention=COORDINATE_CONVENTION)
    recording = source.insertion('pid-a')
    assert recording.object_id == 'object-a'
    assert workspace.recording_calls == ['object-a']
    assert recording.pid == 'pid-a'


def test_workspace_rejects_ambiguous_and_mismatched_pid():
    first = metadata(pid='pid-a')
    second = metadata(pid='pid-a', version='1.2.0')
    source = BwmSource.from_workspace(
        Workspace({'a': first, 'b': second}),
        coordinate_convention=COORDINATE_CONVENTION,
    )
    with pytest.raises(ValueError, match='2 catalog objects'):
        source.insertion('pid-a')
    mismatched = Workspace({'a': metadata(pid='pid-b')})
    with pytest.raises(ValueError, match='0 catalog objects'):
        BwmSource.from_workspace(
            mismatched,
            coordinate_convention=COORDINATE_CONVENTION,
        ).insertion('pid-a')


def test_spikes_forwards_gate_and_requirements_without_fallback(monkeypatch):
    channel = {'pid': 'pid-a', 'channel_id': 0, 'mlapdv_x': 1, 'mlapdv_y': 2, 'mlapdv_z': 3}
    unit = {'pid': 'pid-a', 'cluster_id': 7, 'channels': 0}
    workspace = Workspace({'obj': metadata(channels=[channel], units=[unit])})
    source = BwmSource.from_workspace(workspace, coordinate_convention=COORDINATE_CONVENTION)
    recording = source.insertion('pid-a')
    requirements = object()
    expected = SimpleNamespace(unit_ids=(7,))
    workspace.spike_value = expected
    assert source.spikes(recording, requirements=requirements) is expected
    assert workspace.spike_call == ('obj', requirements)

    def fail(*_args, **_kwargs):
        raise RuntimeError('validation gate rejected source')

    monkeypatch.setattr(workspace, 'spikes', fail)
    with pytest.raises(RuntimeError, match='validation gate rejected'):
        source.spikes(recording, requirements=requirements)


def test_spikes_reject_unknown_loaded_cluster_ids():
    workspace = Workspace(
        {'obj': metadata(units=[{'pid': 'pid-a', 'cluster_id': 7, 'channels': None}])}
    )
    source = BwmSource.from_workspace(workspace, coordinate_convention=COORDINATE_CONVENTION)
    recording = source.insertion('pid-a')
    workspace.spike_value = SimpleNamespace(unit_ids=(999,))
    with pytest.raises(ValueError, match='identities disagree'):
        source.spikes(recording, requirements=object())
