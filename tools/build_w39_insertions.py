#!/usr/bin/env python3
"""Prepare a small pinned W39 trajectory set from the canonical channels parquet.

Requires pandas and a parquet engine (pyarrow). No network access is used. The
source table contains channel XYZ in metres and QC labels; output XYZ is in µm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

RELEASE = '2026_W39-ibl-review-20261007-v1'
CHANNEL_ROOT_MANIFEST_SHA256 = '6adc9fa963196d6db829125c5ac869c49bec7622ec7397e8503965f79476a2b8'
SOURCE_SHA256 = '17dd0a9be89a7eea683d05a6c34170726bde47e66d509aba5217932dbffff52e'


def sha256(path: Path) -> str:
    """Return the SHA256 of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    """Hash the canonical little-endian float64 bytes of an array."""
    canonical = np.asarray(array, dtype='<f8', order='C')
    return hashlib.sha256(canonical.tobytes(order='C')).hexdigest()


def prepare(channels_path: Path) -> tuple[dict[str, np.ndarray], dict]:
    """Validate the pinned parquet and return sorted per-insertion paths."""
    if sha256(channels_path) != SOURCE_SHA256:
        raise ValueError(
            f'{channels_path} is not the pinned {RELEASE} channels.pqt '
            f'(expected SHA256 {SOURCE_SHA256})'
        )
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError as error:
        raise ImportError('install pandas and pyarrow to read the pinned parquet') from error

    try:
        frame = pd.read_parquet(channels_path)
    except Exception as error:
        raise ValueError(f'cannot decode pinned channels parquet: {error}') from error
    if not isinstance(frame.index, pd.MultiIndex) or 'pid' not in frame.index.names:
        raise ValueError('channels parquet needs a MultiIndex with a pid level')
    required = {'x', 'y', 'z', 'axial_um', 'lateral_um', 'labels'}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f'channels parquet lacks required columns: {sorted(missing)}')
    if not frame.index.is_unique:
        raise ValueError('channel identities must be unique')

    pid_values = frame.index.get_level_values('pid').astype(str)
    pids = sorted(pid_values.unique())[:3]
    if len(pids) != 3:
        raise ValueError('pinned channels source must contain at least three insertion PIDs')
    output: dict[str, np.ndarray] = {}
    counts: dict[str, int] = {}
    for pid in pids:
        selected = frame.loc[pid_values == pid].copy()
        coordinates = selected[['x', 'y', 'z', 'axial_um', 'lateral_um']].to_numpy(
            dtype=np.float64
        )
        finite = np.isfinite(coordinates).all(axis=1)
        labels = selected['labels'].to_numpy(dtype=np.float64)
        selected = selected.loc[finite & np.isfinite(labels) & (labels != 3)].copy()
        selected = selected.sort_values(['axial_um', 'lateral_um'], kind='mergesort')
        points = selected[['x', 'y', 'z']].to_numpy(dtype=np.float64) * 1e6
        points = np.asarray(points, dtype=np.float64, order='C')
        if len(points) < 2 or not np.isfinite(points).all():
            raise ValueError(f'{pid} has fewer than two finite non-label-3 channels')
        if np.max(np.abs(points)) > 20000:
            raise ValueError(f'{pid} positions do not look like mouse brain XYZ in µm')
        output[pid] = points
        counts[pid] = len(points)

    metadata = {
        'format': 'ibl-datoviz-w39-insertions-v1',
        'release': RELEASE,
        'channel_root_manifest_sha256': CHANNEL_ROOT_MANIFEST_SHA256,
        'source_file': 'channels.pqt',
        'source_sha256': SOURCE_SHA256,
        'ids': pids,
        'selection': (
            'first three lexically sorted PIDs in the source; finite x/y/z/axial_um/lateral_um; '
            'labels != 3; rows sorted by axial_um then lateral_um using stable mergesort'
        ),
        'coordinates': 'source x/y/z metres multiplied by 1e6; no fitted or extrapolated points',
        'position_units': 'µm in source XYZ / atlas ML-AP-DV world order',
        'site_count': counts,
        'array_sha256': {pid: array_sha256(output[pid]) for pid in pids},
    }
    return output, metadata


def main() -> int:
    """Run the W39 trajectory preparation CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channels', type=Path, required=True, help='pinned channels.pqt file')
    parser.add_argument(
        '--output', type=Path, required=True, help='new, not-yet-existing directory'
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'output directory already exists; choose a fresh path: {args.output}')
    try:
        paths, provenance = prepare(args.channels)
        args.output.mkdir(parents=True, exist_ok=False)
        archive = args.output / 'insertions.npz'
        metadata_path = args.output / 'insertions.json'
        with archive.open('xb') as stream:
            np.savez(stream, **paths)
        with metadata_path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(provenance, indent=2) + '\n')
    except (ValueError, FileNotFoundError, ImportError, FileExistsError) as error:
        parser.exit(1, f'Preparation failed: {error}\n')
    print(f'Wrote {archive} and {metadata_path}')
    for pid in provenance['ids']:
        print(f'  {pid}: {provenance["site_count"][pid]} channels')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
