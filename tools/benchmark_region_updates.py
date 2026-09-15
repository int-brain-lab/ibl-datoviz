#!/usr/bin/env python3
"""Benchmark full-catalog regional recoloring on a materialized atlas asset set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ibl_atlas_assets import bundled_asset_set, verify_materialized_asset_set
from ibl_datoviz import AtlasRegionValues, AtlasViewer


def main() -> int:
    """Measure complete preparation and native upload for repeated regional updates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--iterations', type=int, default=20)
    parser.add_argument('--json', type=Path, dest='json_path')
    args = parser.parse_args()
    if args.iterations <= 0:
        parser.error('--iterations must be positive')

    asset_set = bundled_asset_set()
    assets = verify_materialized_asset_set(asset_set, args.asset_root)
    rows = tuple(
        row
        for row in assets.regions.physical('allen')
        if row.atlas_id != 0 and row.mapping_member
    )
    region_ids = np.asarray([row.atlas_id for row in rows], dtype=np.int64)
    values = np.log1p(np.abs(region_ids)).astype(np.float64)
    data = AtlasRegionValues.from_arrays(region_ids, values)

    with AtlasViewer.from_assets(assets, mapping=args.mapping) as viewer:
        viewer.set_region_data(data, mapping_reduction='weighted_mean')
        started = time.perf_counter()
        for _ in range(args.iterations):
            viewer.set_region_data(data, mapping_reduction='weighted_mean')
        elapsed = time.perf_counter() - started

    result = {
        'asset_set_id': asset_set.asset_set_id,
        'mapping': args.mapping,
        'source_region_count': len(region_ids),
        'vertex_count': len(assets.geometry.positions),
        'iterations': args.iterations,
        'elapsed_seconds': elapsed,
        'mean_update_milliseconds': 1000 * elapsed / args.iterations,
    }
    encoded = json.dumps(result, indent=2, sort_keys=True)
    print(encoded)
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(encoded + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
