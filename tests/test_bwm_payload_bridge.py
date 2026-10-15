"""The optional BWM adapter produces immutable generic source-scoped payloads."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.ibl import COORDINATE_CONVENTION, prepare_bwm_recording, prepare_recording
from ibl_datoviz.payloads import WorldFrame


class Table:
    def __init__(self, rows):
        self.rows = rows
        self.provenance = {'validation_status': 'unknown', 'source': {'pin': 'fixture'}}

    @property
    def frame(self):
        return self

    def to_dict(self, *, orient):
        assert orient == 'records'
        return [dict(row) for row in self.rows]


@pytest.fixture
def frame():
    return WorldFrame('allen-ccf-2017', provenance={
        'verification': {'method': 'registered source transform', 'evidence': 'fixture transform'},
    })


@pytest.fixture
def recording():
    metadata = SimpleNamespace(
        dataset_name='bwm', dataset_version='1.1.0', manifest_sha256='a' * 64,
        pid='insertion-a', eid='session-a',
        channels=Table([
            {'channel_id': 0, 'pid': 'insertion-a', 'mlapdv_x': 10,
             'mlapdv_y': 20, 'mlapdv_z': 30},
            {'channel_id': 7, 'pid': 'insertion-a'},
        ]),
        units=Table([
            {'cluster_id': 0, 'pid': 'insertion-a', 'channels': 0},
            {'cluster_id': 36, 'pid': 'insertion-a', 'channels': 7},
        ]),
    )
    return prepare_recording(metadata, coordinate_convention=COORDINATE_CONVENTION)


def test_bridge_retains_source_identity_complete_rows_and_positional_meaning(recording, frame):
    result = prepare_bwm_recording(recording, frame=frame)
    assert result.insertion_id == 'insertion-a'
    assert result.session_id == 'session-a'
    assert result.clusters.ids == (0, 36)
    assert result.clusters.positioned.tolist() == [True, False]
    assert result.clusters.observation_keys[0].original_id == 0
    assert result.clusters.observation_keys[0].source == result.source
    assert result.clusters.provenance['position_meaning'] == 'assigned channel location'
    assert result.path is None and result.sites is None
    assert result.provenance['signal_validation'] == 'not_requested'


def test_bridge_snapshots_geometry_identity_and_nested_provenance(recording, frame):
    result = prepare_bwm_recording(recording, frame=frame)
    recording.metadata.pid = 'changed'
    recording.metadata.channels.provenance['source']['pin'] = 'changed'
    assert result.insertion_id == 'insertion-a'
    assert result.channels.provenance['source_metadata']['source']['pin'] == 'fixture'
    with pytest.raises(ValueError):
        result.clusters.positions_um.setflags(write=True)


@pytest.mark.parametrize('field,value', [
    ('pid', 'foreign-pid'), ('manifest_sha256', 'b' * 64), ('dataset_version', '2.0.0'),
])
def test_changed_metadata_identity_is_not_silently_assigned_to_refs(
    recording, frame, field, value,
):
    setattr(recording.metadata, field, value)
    with pytest.raises(ValueError):
        prepare_bwm_recording(recording, frame=frame)


def test_changed_metadata_rows_and_geometry_are_rejected(recording, frame):
    recording.metadata.units.rows[0]['cluster_id'] = 99
    with pytest.raises(ValueError, match='disagree'):
        prepare_bwm_recording(recording, frame=frame)


def test_bridge_requires_verified_frame_and_matching_convention(recording, frame):
    with pytest.raises(ValueError, match='verification'):
        prepare_bwm_recording(recording, frame=WorldFrame('allen-ccf-2017'))
    with pytest.raises(ValueError, match='conventions'):
        prepare_bwm_recording(recording, frame=replace(frame, coordinate_convention='other'))


def test_forged_geometry_cannot_override_source_rows(recording, frame):
    clusters = replace(recording.clusters, positions_um=np.zeros((2, 3)))
    with pytest.raises(ValueError, match='disagree'):
        prepare_bwm_recording(replace(recording, clusters=clusters), frame=frame)


def test_release_scoped_frame_evidence_cannot_be_reused_for_another_manifest(recording):
    provenance = {
        'verification': {'method': 'source convention audit', 'evidence': 'pinned source code'},
        'source_manifest_sha256': 'b' * 64,
    }
    frame = WorldFrame('allen-ccf-2017', provenance=provenance)
    with pytest.raises(ValueError, match='source manifest'):
        prepare_bwm_recording(recording, frame=frame)
    provenance['source_manifest_sha256'] = recording.metadata.manifest_sha256
    matched = WorldFrame('allen-ccf-2017', provenance=provenance)
    payload = prepare_bwm_recording(recording, frame=matched)
    assert payload.provenance['source_validation_status'] == 'unknown'
    assert payload.provenance['signal_validation'] == 'not_requested'


def test_insertion_scoped_frame_evidence_rejects_unreviewed_recording(recording, frame):
    provenance = dict(frame.provenance)
    provenance['source_insertion_ids'] = ['another-pid']
    with pytest.raises(ValueError, match='insertion scope'):
        prepare_bwm_recording(
            recording, frame=WorldFrame('allen-ccf-2017', provenance=provenance)
        )
    provenance['source_insertion_ids'] = [recording.pid]
    payload = prepare_bwm_recording(
        recording, frame=WorldFrame('allen-ccf-2017', provenance=provenance)
    )
    assert payload.insertion_id == recording.pid
