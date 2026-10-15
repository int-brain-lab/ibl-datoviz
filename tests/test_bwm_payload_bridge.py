"""The optional BWM adapter produces immutable generic source-scoped payloads."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.ibl import (
    COORDINATE_CONVENTION,
    frame_from_bwm_metadata,
    prepare_bwm_recording,
    prepare_recording,
)
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
    return WorldFrame(
        'allen-ccf-2017',
        provenance={
            'verification': {
                'method': 'registered source transform',
                'evidence': 'fixture transform',
            },
        },
    )


@pytest.fixture
def recording():
    metadata = SimpleNamespace(
        dataset_name='bwm',
        dataset_version='1.1.0',
        manifest_sha256='a' * 64,
        pid='insertion-a',
        eid='session-a',
        channels=Table(
            [
                {
                    'channel_id': 0,
                    'pid': 'insertion-a',
                    'mlapdv_x': 10,
                    'mlapdv_y': 20,
                    'mlapdv_z': 30,
                },
                {'channel_id': 7, 'pid': 'insertion-a'},
            ]
        ),
        units=Table(
            [
                {'cluster_id': 0, 'pid': 'insertion-a', 'channels': 0},
                {'cluster_id': 36, 'pid': 'insertion-a', 'channels': 7},
            ]
        ),
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


@pytest.mark.parametrize(
    'field,value',
    [
        ('pid', 'foreign-pid'),
        ('manifest_sha256', 'b' * 64),
        ('dataset_version', '2.0.0'),
    ],
)
def test_changed_metadata_identity_is_not_silently_assigned_to_refs(
    recording,
    frame,
    field,
    value,
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
        prepare_bwm_recording(recording, frame=WorldFrame('allen-ccf-2017', provenance=provenance))
    provenance['source_insertion_ids'] = [recording.pid]
    payload = prepare_bwm_recording(
        recording, frame=WorldFrame('allen-ccf-2017', provenance=provenance)
    )
    assert payload.insertion_id == recording.pid


def _shared_metadata(recording):
    return {
        'provider': 'ibl',
        'dataset_name': recording.metadata.dataset_name,
        'dataset_version': recording.metadata.dataset_version,
        'manifest_sha256': recording.metadata.manifest_sha256,
        'recording_id': recording.pid,
        'session_id': recording.eid,
        'coordinates': [],
        'byte_integrity': {
            'status': 'passed',
            'references': [{'uri': 'urn:fixture:schema', 'description': 'sealed fixture'}],
        },
        'source_validation': {'status': 'unknown'},
        'warnings': ['unknown source validation'],
    }


def test_shared_metadata_is_retained_without_promoting_source_validation(recording, frame):
    shared = _shared_metadata(recording)
    recording.metadata.metadata = shared
    result = prepare_bwm_recording(recording, frame=frame)
    assert result.provenance['prepared_recording_metadata']['byte_integrity']['status'] == 'passed'
    assert result.provenance['source_validation_status'] == 'unknown'
    assert (
        result.channels.provenance['prepared_recording_metadata']['recording_id'] == recording.pid
    )
    shared['warnings'].append('modified')
    assert result.provenance['prepared_recording_metadata']['warnings'] == (
        'unknown source validation',
    )


@pytest.mark.parametrize(
    'field,value',
    [
        ('provider', 'other'),
        ('dataset_name', 'other'),
        ('dataset_version', 'other'),
        ('manifest_sha256', 'b' * 64),
        ('recording_id', 'other'),
        ('session_id', 'other'),
    ],
)
def test_shared_metadata_identity_mismatch_fails(recording, frame, field, value):
    shared = _shared_metadata(recording)
    shared[field] = value
    recording.metadata.metadata = shared
    with pytest.raises(ValueError, match='metadata identity disagrees'):
        prepare_bwm_recording(recording, frame=frame)


def _declared_shared_metadata(recording):
    shared = _shared_metadata(recording)
    shared['coordinates'] = [
        {
            'table': 'channels',
            'columns': ['mlapdv_x', 'mlapdv_y', 'mlapdv_z'],
            'meaning': 'supplied channel location',
            'frame': {
                'name': 'IBL atlas world',
                'axes': ['ML', 'AP', 'DV'],
                'positive_directions': ['right', 'anterior', 'dorsal'],
                'unit': 'um',
                'origin': 'bregma',
                'reference': 'allen-ccf-2017',
                'coordinate_convention': COORDINATE_CONVENTION,
            },
            'frame_evidence': {
                'status': 'passed',
                'references': [
                    {
                        'uri': 'urn:fixture:frame-review',
                        'description': 'Reviewed synthetic fixture frame',
                    }
                ],
            },
            'source_validation': {'status': 'unknown'},
            'alignment_validation': {'status': 'unknown'},
        }
    ]
    return shared


def test_declared_reviewed_frame_resolves_without_an_explicit_override(recording):
    recording.metadata.metadata = _declared_shared_metadata(recording)
    frame = frame_from_bwm_metadata(recording)
    assert frame.reference_space_id == 'allen-ccf-2017'
    assert frame.provenance['source_insertion_ids'] == (recording.pid,)
    assert frame.provenance['source_manifest_sha256'] == recording.metadata.manifest_sha256
    result = prepare_bwm_recording(recording)
    assert result.channels.frame == frame
    assert result.clusters.ids == (0, 36)
    assert result.provenance['source_validation_status'] == 'unknown'
    declaration = result.provenance['prepared_recording_metadata']['coordinates'][0]
    assert declaration['alignment_validation']['status'] == 'unknown'
    assert result.provenance['signal_validation'] == 'not_requested'


@pytest.mark.parametrize('status', ['unknown', 'not_checked', 'failed'])
def test_unreviewed_source_declarations_cannot_be_overridden(recording, frame, status):
    shared = _declared_shared_metadata(recording)
    shared['coordinates'][0]['frame_evidence']['status'] = status
    recording.metadata.metadata = shared
    for override in (None, frame):
        with pytest.raises(ValueError, match='passed declaration evidence'):
            prepare_bwm_recording(recording, frame=override)


@pytest.mark.parametrize(
    'field,value',
    [
        ('unit', 'mm'),
        ('origin', 'voxel zero'),
        ('reference', 'other-atlas'),
        ('axes', ['AP', 'ML', 'DV']),
        ('positive_directions', ['left', 'anterior', 'dorsal']),
        ('coordinate_convention', 'other'),
        ('reference_version', '2020'),
        ('species', 'human'),
    ],
)
def test_mismatched_producer_frame_is_rejected_without_transform(recording, frame, field, value):
    shared = _declared_shared_metadata(recording)
    shared['coordinates'][0]['frame'][field] = value
    recording.metadata.metadata = shared
    for override in (None, frame):
        with pytest.raises(ValueError, match='exactly match'):
            prepare_bwm_recording(recording, frame=override)


def test_legacy_missing_declarations_still_require_reviewed_override(recording, frame):
    recording.metadata.metadata = _shared_metadata(recording)
    with pytest.raises(ValueError, match='reviewed source channel frame'):
        prepare_bwm_recording(recording)
    assert prepare_bwm_recording(recording, frame=frame).channels.frame == frame


def test_ambiguous_or_incomplete_producer_declaration_is_rejected(recording):
    shared = _declared_shared_metadata(recording)
    shared['coordinates'].append(shared['coordinates'][0].copy())
    recording.metadata.metadata = shared
    with pytest.raises(ValueError, match='one reviewed'):
        prepare_bwm_recording(recording)
    shared['coordinates'].pop()
    shared['coordinates'][0]['frame_evidence']['references'] = []
    with pytest.raises(ValueError, match='evidence references'):
        prepare_bwm_recording(recording)


def test_explicit_reviewed_frame_cannot_disagree_with_declared_source_reference(recording, frame):
    recording.metadata.metadata = _declared_shared_metadata(recording)
    other = replace(frame, reference_space_id='other-atlas')
    with pytest.raises(ValueError, match='disagrees with source'):
        prepare_bwm_recording(recording, frame=other)
