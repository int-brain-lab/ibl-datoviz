#!/usr/bin/env python3
"""Explore one real BWM insertion with atlas-linked channel firing rates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from ibl_datoviz import AtlasViewer, ProbeSites

FIXTURE = Path(__file__).with_name('data') / 'bwm-ephys-1.1.0-a21bade7-probe.csv'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_fixture(path: Path) -> tuple[ProbeSites, dict]:
    provenance_path = path.with_suffix('.provenance.json')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    if provenance.get('format') != 'ibl-datoviz-real-probe-fixture-v1':
        raise ValueError('unexpected probe fixture format')
    if provenance['artifact']['sha256'] != _sha256(path):
        raise ValueError('probe fixture CSV does not match its provenance hash')
    with path.open(encoding='utf-8', newline='') as stream:
        rows = tuple(csv.DictReader(stream))
    if len(rows) != provenance['site_count']:
        raise ValueError('probe fixture row count does not match provenance')
    values = [
        float(row['mean_firing_rate_hz']) if row['mean_firing_rate_hz'] else np.nan
        for row in rows
    ]
    return (
        ProbeSites.from_arrays(
            [[row['ml_um'], row['ap_um'], row['dv_um']] for row in rows],
            values,
            [int(row['allen_region_id']) for row in rows],
            site_ids=[int(row['site_id']) for row in rows],
            labels=[row['label'] for row in rows],
            value_name='Mean FR (Hz)',
        ),
        provenance,
    )


def main() -> int:
    """Render the pinned insertion against one materialized atlas asset set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()

    data, provenance = _load_fixture(args.fixture)
    finite = data.values[np.isfinite(data.values)]
    value_range = tuple(float(value) for value in np.quantile(finite, (0.05, 0.95)))
    with AtlasViewer.from_asset_set(
        args.asset_root, mapping=args.mapping, surface_opacity=0.16
    ) as viewer:
        viewer.set_probe((data.positions_um[0], data.positions_um[-1]), width_px=2)
        viewer.set_probe_data(
            data,
            value_range=value_range,
            radius_um=85,
            color_scheme='sequential',
        )
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            insertion = provenance['insertion']
            title = f"BWM {insertion['subject']} {insertion['probe_name']}"
            viewer.show(title=title, frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
