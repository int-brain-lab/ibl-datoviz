#!/usr/bin/env python3
"""Explore the pinned Allen CCF 2017 mouse-brain surface and ontology."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from ibl_datoviz import AtlasViewer, ProbeSites

DEMO_ENTRY_UM = np.asarray((-2200, -2500, 0), dtype=np.float32)
DEMO_TIP_UM = np.asarray((1000, -2500, -6500), dtype=np.float32)
# Precomputed with iblatlas AllenAtlas(25).get_labels(); ML sign supplies physical hemisphere.
DEMO_ALLEN_REGION_IDS = np.asarray(
    [
        0, -805, -41, -501, -565, -257, -1046, -971, -382, -382, -382, -382,
        -382, -484682470, -10703, -997, -215, -215, -215, -215, -313, -313,
        -634, -549009203, -549009203, -549009203, -313, -795, -795, -795,
        -795, -795, -313, 946, 946, 946, 313, 313, 525, 525, 606826647,
        606826647, 606826647, 606826647, 1097, 0, 0, 0,
    ],
    dtype=np.int64,
)


def main() -> int:
    """Verify and display one materialized ``ibl-anatomy`` graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='materialized atlas asset-set directory')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--surface-opacity',
        type=float,
        default=1.0,
        help='brain-surface opacity; defaults to opaque',
    )
    parser.add_argument(
        '--frames', type=int, default=0, help='interactive frame limit; zero runs until closed'
    )
    parser.add_argument(
        '--probe',
        nargs=6,
        type=float,
        metavar=('ENTRY_ML', 'ENTRY_AP', 'ENTRY_DV', 'TIP_ML', 'TIP_AP', 'TIP_DV'),
        help='optional entry and tip in atlas ML/AP/DV micrometres',
    )
    parser.add_argument(
        '--demo-probe',
        action='store_true',
        help='show a fixed iblatlas-annotated trajectory and linked site table',
    )
    args = parser.parse_args()
    if args.probe and args.demo_probe:
        parser.error('--probe and --demo-probe are mutually exclusive')

    with AtlasViewer.from_asset_set(
        args.asset_root, mapping=args.mapping, surface_opacity=args.surface_opacity
    ) as viewer:
        if args.probe or args.demo_probe:
            entry = (
                DEMO_ENTRY_UM
                if args.demo_probe
                else np.asarray(args.probe[:3], dtype=np.float32)
            )
            tip = (
                DEMO_TIP_UM
                if args.demo_probe
                else np.asarray(args.probe[3:], dtype=np.float32)
            )
            viewer.set_probe((entry, tip), width_px=2.0)
            sites = np.linspace(entry, tip, 48, dtype=np.float32)
            phase = np.linspace(-np.pi, np.pi, len(sites))
            values = np.sin(phase)
            if args.demo_probe:
                data = ProbeSites.from_arrays(
                    sites,
                    values,
                    DEMO_ALLEN_REGION_IDS,
                    labels=[f'Site {index:02d}' for index in range(len(sites))],
                )
                viewer.set_probe_data(data, value_range=(-1, 1), radius_um=75)
            else:
                viewer.set_probe_sites(
                    sites, values=values, value_range=(-1, 1), radius_um=75
                )
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(title='IBL Allen mouse brain atlas', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
