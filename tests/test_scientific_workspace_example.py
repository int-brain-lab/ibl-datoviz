"""The linked workspace client can use a named shared-reader workspace."""

import json
import sys
from types import SimpleNamespace

import pytest

from examples import scientific_workspace as client


def test_workspace_source_uses_shared_reader_and_keeps_receipt(tmp_path, monkeypatch):
    arguments = [
        'scientific-workspace',
        str(tmp_path / 'atlas'),
        '--volume-pack',
        str(tmp_path / 'volume'),
        '--workspace',
        str(tmp_path / 'workspace'),
        '--pid',
        'insertion-a',
        '--frames',
        '3',
    ]
    monkeypatch.setattr(sys, 'argv', arguments)
    monkeypatch.setattr(
        client, 'open_volume_pack', lambda _path: SimpleNamespace(load_volumes=lambda: ())
    )
    monkeypatch.setattr(client, 'prepare_viewer', lambda _args: {})
    seen = []
    recording = SimpleNamespace(
        insertion_id='insertion-a',
        channels=SimpleNamespace(frame=SimpleNamespace()),
        clusters=SimpleNamespace(),
    )
    monkeypatch.setattr(
        client,
        '_source',
        lambda args: (
            seen.append((args.release, args.workspace))
            or SimpleNamespace(insertion=lambda pid: SimpleNamespace(pid=pid))
        ),
    )
    monkeypatch.setattr(client, 'prepare_bwm_recording', lambda _record, frame=None: recording)
    monkeypatch.setattr(client, '_receipt', lambda _record: {'insertion_id': 'insertion-a'})

    class Viewer:
        def __init__(self, **_options):
            self.tables = SimpleNamespace(show=lambda _table: None)
            self.layout = 'linked'
            self.slices = SimpleNamespace(position=SimpleNamespace(index=(), world_um=()))
            self._linked = SimpleNamespace(_slice_planes=SimpleNamespace(visible_axes=()))
            self.picking = SimpleNamespace(unavailable_reason='not requested')

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            pass

        def add_recording(self, _recording, **_options):
            return SimpleNamespace(clusters=object())

    monkeypatch.setattr(client, 'AtlasViewer', Viewer)
    reports = []
    monkeypatch.setattr(
        client, 'finish', lambda _app, _args, report, _title: reports.append(report)
    )

    client.main()

    assert seen == [(None, tmp_path / 'workspace')]
    assert reports[0]['signal_reads'] == 'not_requested'
    assert reports[0]['recordings'][0]['insertion_id'] == 'insertion-a'
    json.dumps(reports[0])


def test_contour_source_requires_explicit_matching_packs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'workspace',
            str(tmp_path),
            '--volume-pack',
            str(tmp_path),
            '--slice-renderer',
            'contours',
        ],
    )
    monkeypatch.setattr(
        client, 'prepare_viewer', lambda *_: pytest.fail('loaded before validation')
    )
    with pytest.raises(SystemExit):
        client.main()


@pytest.mark.parametrize(
    'extra',
    [
        ['--region-values', 'prepared.json'],
        ['--region-mapping-reduction', 'weighted_mean'],
    ],
)
def test_regional_mapping_reduction_requires_explicit_paired_input(monkeypatch, tmp_path, extra):
    monkeypatch.setattr(
        sys, 'argv', ['workspace', str(tmp_path), '--volume-pack', str(tmp_path), *extra]
    )
    monkeypatch.setattr(
        client, 'open_volume_pack', lambda *_: pytest.fail('read before declaration')
    )
    with pytest.raises(SystemExit):
        client.main()
