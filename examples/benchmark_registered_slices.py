#!/usr/bin/env python3
"""Measure lazy registered atlas slice decoding, composition, and cache reuse."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from ibl_atlas_assets import (
    open_anatomy_pack,
    open_intensity_block_pack,
    open_volume_pack,
)
from ibl_datoviz import AtlasSliceComposer, AtlasSliceSource


def _measure(callable_):
    started = perf_counter()
    value = callable_()
    return value, 1000 * (perf_counter() - started)


def main() -> int:
    """Run cold/warm measurements without creating a Datoviz scene."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('volume_pack', type=Path, help='catalog-bearing volume pack')
    parser.add_argument('intensity_pack', type=Path)
    parser.add_argument('anatomy_pack', type=Path)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--json', type=Path, metavar='REPORT')
    args = parser.parse_args()

    catalog = open_volume_pack(args.volume_pack).load_volumes().regions
    intensity = open_intensity_block_pack(args.intensity_pack)
    anatomy = open_anatomy_pack(
        args.anatomy_pack,
        reference_space_id=intensity.reference_space_id,
        grid_id=intensity.grid_id,
    )
    source = AtlasSliceSource(
        intensity,
        {projection.world_slice_axis: projection for projection in anatomy.projections.values()},
        catalog,
    )
    composer = AtlasSliceComposer(source, args.mapping)
    report = {
        'dataset_id': intensity.dataset_id,
        'reference_space_id': intensity.reference_space_id,
        'grid_id': intensity.grid_id,
        'shape_ap_ml_dv': list(intensity.shape),
        'mapping': args.mapping,
        'axes': {},
    }
    for axis, size in zip(('ap', 'ml', 'dv'), intensity.shape, strict=True):
        index = size // 2
        source.clear_cache()
        _, cold_ms = _measure(lambda axis=axis, index=index: composer.compose_layers(axis, index))
        (starts, _), boundary_ms = _measure(
            lambda axis=axis, index=index: composer.boundary_segments(axis, index)
        )
        _, warm_ms = _measure(lambda axis=axis, index=index: composer.compose_layers(axis, index))
        report['axes'][axis] = {
            'index': index,
            'cold_compose_ms': cold_ms,
            'boundary_ms': boundary_ms,
            'warm_compose_ms': warm_ms,
            'boundary_segments': len(starts),
        }
    report['intensity_cache'] = vars(intensity.cache_info())
    report['annotation_cache_entries'], report['annotation_cache_bytes'] = source.cache_info()
    payload = json.dumps(report, indent=2, sort_keys=True)
    print(payload)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(payload + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
