"""Regression checks for provenance boundaries on the W39 trajectory example."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_builder_rejects_unpinned_source_before_parquet_decoder(tmp_path, monkeypatch):
    """Bad source bytes fail at the pin check, before optional parquet imports."""
    module = runpy.run_path(ROOT / 'tools' / 'build_w39_insertions.py')
    source = tmp_path / 'channels.pqt'
    source.write_bytes(b'not the pinned parquet')
    monkeypatch.setitem(sys.modules, 'pandas', None)

    with pytest.raises(ValueError, match='not the pinned'):
        module['prepare'](source)


def test_example_rejects_forged_sidecar_for_modified_path(tmp_path):
    """Self-consistent sidecar hashes cannot authorize changed scientific arrays."""
    module = runpy.run_path(ROOT / 'examples' / 'bwm_multiple_insertions.py')
    expected = module['EXPECTED_PATHS']
    pids = list(expected)
    paths = {pid: np.zeros((count, 3), dtype=np.float64) for pid, (count, _) in expected.items()}
    paths[pids[0]][0, 0] = 1.0
    archive = tmp_path / 'insertions.npz'
    np.savez(archive, **paths)
    metadata = {
        'format': 'ibl-datoviz-w39-insertions-v1',
        'source_sha256': module['SOURCE_SHA256'],
        'ids': pids,
        'coordinates': 'source x/y/z metres multiplied by 1e6; no fitted or extrapolated points',
        'array_sha256': {
            pid: module['hashlib'].sha256(paths[pid].astype('<f8').tobytes()).hexdigest()
            for pid in pids
        },
    }
    sidecar = tmp_path / 'insertions.json'
    sidecar.write_text(json.dumps(metadata), encoding='utf-8')

    with pytest.raises(ValueError, match='differs from its pinned trajectory array'):
        module['_load_paths'](archive, sidecar)


def test_builder_preserves_existing_output(tmp_path, monkeypatch):
    """A non-empty target is rejected without overwriting any user file."""
    module = runpy.run_path(ROOT / 'tools' / 'build_w39_insertions.py')
    output = tmp_path / 'output'
    output.mkdir()
    sentinel = output / 'keep.txt'
    sentinel.write_text('keep', encoding='utf-8')
    monkeypatch.setattr(
        sys,
        'argv',
        ['build_w39_insertions.py', '--channels', 'missing.pqt', '--output', str(output)],
    )

    with pytest.raises(SystemExit) as error:
        module['main']()

    assert error.value.code == 2
    assert sentinel.read_text(encoding='utf-8') == 'keep'
