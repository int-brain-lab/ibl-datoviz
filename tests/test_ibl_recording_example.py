"""Example reports distinguish accepted frame evidence from source validation."""

import json
import sys
from types import SimpleNamespace

import pytest

from examples import ibl_recordings as client
from ibl_datoviz.ibl import COORDINATE_CONVENTION, prepare_bwm_recording, prepare_recording
from ibl_datoviz.payloads import WorldFrame
from tests.test_bwm_payload_bridge import Table, _declared_shared_metadata


@pytest.fixture
def prepared():
    metadata = SimpleNamespace(
        dataset_name='fixture',
        dataset_version='1',
        manifest_sha256='a' * 64,
        pid='insertion-a',
        eid='session-a',
        channels=Table(
            [dict(channel_id=0, pid='insertion-a', mlapdv_x=1.0, mlapdv_y=2.0, mlapdv_z=3.0)]
        ),
        units=Table([dict(cluster_id=0, pid='insertion-a', channels=0)]),
    )
    return prepare_recording(metadata, coordinate_convention=COORDINATE_CONVENTION)


def test_receipt_reports_actual_table_validation_and_snapshots_accepted_evidence(prepared):
    shared = _declared_shared_metadata(prepared)
    shared['source_validation']['status'] = 'failed'
    shared['source_validation']['references'] = [
        {'uri': 'urn:fixture:failed', 'description': 'fixture failure'}
    ]
    prepared.metadata.metadata = shared
    prepared.metadata.units.provenance['validation_status'] = 'failed'
    result = prepare_bwm_recording(prepared)
    receipt = client._receipt(result)
    assert receipt['source_validation_status'] == 'failed'
    assert receipt['populations']['clusters']['source_validation_status'] == 'failed'
    assert receipt['populations']['channels']['source_validation_status'] == 'unknown'
    assert receipt['signal_validation'] == 'not_requested'
    assert receipt['populations']['clusters']['original_ids'] == [0]
    assert receipt['frame_evidence']['provenance']['source_insertion_ids'] == ['insertion-a']
    receipt['frame_evidence']['provenance']['source_insertion_ids'].append('changed')
    assert result.channels.frame.provenance['source_insertion_ids'] == ('insertion-a',)
    json.dumps(receipt)


@pytest.mark.parametrize('producer_declared', [True, False])
def test_cli_accepts_producer_metadata_or_explicit_legacy_evidence(
    prepared,
    producer_declared,
    tmp_path,
    monkeypatch,
):
    arguments = [
        'ibl-recordings',
        str(tmp_path),
        '--release',
        str(tmp_path),
        '--pid',
        'insertion-a',
        '--frames',
        '3',
    ]
    if producer_declared:
        prepared.metadata.metadata = _declared_shared_metadata(prepared)
    else:
        frame = WorldFrame(
            'allen-ccf-2017',
            provenance={
                'verification': {'method': 'fixture review', 'evidence': 'fixture evidence'},
                'source_manifest_sha256': prepared.metadata.manifest_sha256,
                'source_insertion_ids': [prepared.pid],
            },
        )
        path = tmp_path / 'frame.json'
        path.write_text(json.dumps(client._frame_receipt(frame)))
        arguments.extend(['--frame-evidence', str(path)])
    monkeypatch.setattr(sys, 'argv', arguments)
    monkeypatch.setattr(
        client, '_source', lambda _args: SimpleNamespace(insertion=lambda _pid: prepared)
    )
    monkeypatch.setattr(client, 'prepare_viewer', lambda _args: {})
    reports = []

    class Viewer:
        def __init__(self, **_options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            pass

        def add_recording(self, recording, **_options):
            assert recording.insertion_id == 'insertion-a'
            return SimpleNamespace()

    monkeypatch.setattr(client, 'AtlasViewer', Viewer)
    monkeypatch.setattr(
        client, 'finish', lambda _viewer, _args, report, _title: reports.append(report)
    )
    client.main()
    (report,) = reports
    accepted = report['frame_evidence']['insertion-a']
    assert accepted['provenance']['source_manifest_sha256'] == prepared.metadata.manifest_sha256
    assert accepted['provenance']['source_insertion_ids'] == ['insertion-a']
    assert report['recordings'][0]['source_validation_status'] == 'unknown'
    json.dumps(report)
