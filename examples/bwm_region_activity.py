#!/usr/bin/env python3
"""Link real BWM firing rates across sites, regions, ontology, and surfaces."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from bwm_probe import FIXTURE, _load_fixture

from ibl_datoviz import AtlasRegionValues, AtlasViewer, ProbeSites


def _aggregate_regions(data: ProbeSites) -> AtlasRegionValues:
    """Compute one site-weighted mean for every signed Allen region."""
    region_ids = np.unique(data.allen_region_ids[data.allen_region_ids != 0])
    values = []
    weights = []
    for region_id in region_ids:
        samples = data.values[data.allen_region_ids == region_id]
        finite = samples[np.isfinite(samples)]
        values.append(float(np.mean(finite)) if len(finite) else np.nan)
        weights.append(len(finite))
    return AtlasRegionValues.from_arrays(
        region_ids,
        values,
        weights=weights,
        value_name='Mean site FR (Hz)',
        weight_name='Sites',
    )


def main() -> int:
    """Render one mapping-aware regional summary from the pinned insertion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()

    sites, provenance = _load_fixture(args.fixture)
    regions = _aggregate_regions(sites)
    finite = sites.values[np.isfinite(sites.values)]
    value_range = tuple(float(value) for value in np.quantile(finite, (0.05, 0.95)))
    with AtlasViewer.from_asset_set(
        args.asset_root, mapping=args.mapping, surface_opacity=0.32
    ) as viewer:
        viewer.set_probe((sites.positions_um[0], sites.positions_um[-1]), width_px=2)
        viewer.set_probe_data(
            sites,
            value_range=value_range,
            radius_um=70,
            color_scheme='sequential',
        )
        viewer.set_region_data(
            regions,
            value_range=value_range,
            color_scheme='sequential',
        )
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            insertion = provenance['insertion']
            title = f'BWM regional activity — {insertion["subject"]} {insertion["probe_name"]}'
            viewer.show(title=title, frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
