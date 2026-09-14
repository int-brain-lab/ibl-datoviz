#!/usr/bin/env python3
"""Derive one compact, provenance-recorded probe fixture from local BWM ephys tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_PID = 'a21bade7-5be7-4a17-a9b9-ddee453e6260'
SOURCE_FILES = (
    'metadata/channels.parquet',
    'metadata/insertions.parquet',
    'metadata/units.parquet',
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    """Write a deterministic CSV plus provenance JSON for one insertion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset_root', type=Path)
    parser.add_argument('output_root', type=Path)
    parser.add_argument('--pid', default=DEFAULT_PID)
    args = parser.parse_args()

    channels = pd.read_parquet(args.dataset_root / SOURCE_FILES[0])
    insertions = pd.read_parquet(args.dataset_root / SOURCE_FILES[1])
    units = pd.read_parquet(args.dataset_root / SOURCE_FILES[2])
    channels = channels.loc[channels['pid'] == args.pid].copy()
    insertion = insertions.loc[insertions['pid'] == args.pid]
    units = units.loc[units['pid'] == args.pid]
    if len(channels) == 0 or len(insertion) != 1 or len(units) == 0:
        raise ValueError('PID must resolve to channels, one insertion, and good units')

    coordinate_columns = ['mlapdv_x', 'mlapdv_y', 'mlapdv_z']
    if channels[coordinate_columns + ['brainLocationIds_ccf_2017']].isna().any().any():
        raise ValueError('fixture source channels require complete histology coordinates and IDs')
    unit_summary = units.groupby('channels')['firing_rate'].agg(['mean', 'count'])
    channels = channels.join(unit_summary, on='channel_id')

    rows = []
    grouped = channels.groupby(coordinate_columns, sort=False, dropna=False)
    for _, group in grouped:
        region_ids = group['brainLocationIds_ccf_2017'].unique()
        acronyms = group['acronym'].unique()
        if len(region_ids) != 1 or len(acronyms) != 1:
            raise ValueError('co-located channels disagree on Allen annotation')
        channel_ids = sorted(int(value) for value in group['channel_id'])
        firing_rates = group['mean'].dropna().to_numpy(dtype=np.float64)
        unit_count = int(group['count'].fillna(0).sum())
        allen_id = int(region_ids[0])
        ml_um = float(group['mlapdv_x'].iloc[0])
        if allen_id and ml_um < 0:
            allen_id = -abs(allen_id)
        rows.append(
            {
                'site_id': min(channel_ids) + 1,
                'label': 'ch' + '-'.join(f'{value:03d}' for value in channel_ids),
                'ml_um': ml_um,
                'ap_um': float(group['mlapdv_y'].iloc[0]),
                'dv_um': float(group['mlapdv_z'].iloc[0]),
                'allen_region_id': allen_id,
                'acronym': str(acronyms[0]),
                'mean_firing_rate_hz': (
                    float(np.average(firing_rates, weights=group['count'].dropna()))
                    if len(firing_rates)
                    else None
                ),
                'good_unit_count': unit_count,
            }
        )
    rows.sort(key=lambda row: (row['dv_um'], row['site_id']), reverse=True)

    args.output_root.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_root / 'bwm-ephys-1.1.0-a21bade7-probe.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    record = insertion.iloc[0]
    provenance = {
        'format': 'ibl-datoviz-real-probe-fixture-v1',
        'dataset': {'name': 'bwm_ephys', 'version': '1.1.0'},
        'source': {
            'freeze': '2023_12_bwm_release',
            'good_unit_rule': 'label >= 1.0',
            'files': {
                relative: {'sha256': _sha256(args.dataset_root / relative)}
                for relative in SOURCE_FILES
            },
        },
        'insertion': {
            key: record[key]
            for key in ('pid', 'eid', 'subject', 'date', 'lab', 'probe_name')
        },
        'derivation': {
            'coordinates': 'source ML/AP/DV micrometres; exact co-located channels collapsed',
            'hemisphere': 'nonzero Allen IDs negated where original ML < 0',
            'value': 'mean firing rate of good units assigned to each co-located channel group',
            'missing_value': 'empty CSV field where no good unit is assigned',
        },
        'artifact': {'path': csv_path.name, 'sha256': _sha256(csv_path)},
        'site_count': len(rows),
    }
    provenance['insertion']['date'] = str(provenance['insertion']['date'])
    json_path = csv_path.with_suffix('.provenance.json')
    json_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'wrote {csv_path} and {json_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
