#!/usr/bin/env python3
"""Explore the pinned Allen CCF 2017 mouse-brain surface and ontology."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Verify and display one materialized ``ibl-atlas-assets`` graph."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='materialized atlas asset-set directory')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--surface-opacity',
        type=float,
        help='anatomy opacity; defaults to 0.18 with --probe and 1 otherwise',
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
    args = parser.parse_args()

    surface_opacity = args.surface_opacity
    if surface_opacity is None:
        surface_opacity = 0.18 if args.probe else 1.0
    with AtlasViewer.from_asset_set(
        args.asset_root, mapping=args.mapping, surface_opacity=surface_opacity
    ) as viewer:
        if args.probe:
            entry = np.asarray(args.probe[:3], dtype=np.float32)
            tip = np.asarray(args.probe[3:], dtype=np.float32)
            viewer.set_probe((entry, tip), width_px=2.0)
            sites = np.linspace(entry, tip, 48, dtype=np.float32)
            phase = np.linspace(-np.pi, np.pi, len(sites))
            viewer.set_probe_sites(
                sites, values=np.sin(phase), value_range=(-1, 1), radius_um=75
            )
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(title='IBL Allen mouse brain atlas', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
