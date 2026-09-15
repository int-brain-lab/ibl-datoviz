#!/usr/bin/env python3
"""Stress-test an opaque atlas surface, then opt into ontology and explosion UI."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_atlas_assets import open_region_catalog
from ibl_datoviz import AtlasViewer


def main() -> int:
    """Run the interactive or offscreen atlas spike."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh_pack', type=Path)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--regions',
        type=Path,
        help='optional catalog enabling the separate ontology/selection test rung',
    )
    parser.add_argument(
        '--frames', type=int, default=0, help='interactive frame limit; zero runs until closed'
    )
    parser.add_argument(
        '--explode',
        type=float,
        default=0.0,
        help='initial region explosion in [0, 1]; requires --regions',
    )
    args = parser.parse_args()

    if args.explode and args.regions is None:
        parser.error('--explode requires --regions')

    catalog = open_region_catalog(args.regions) if args.regions else None
    with AtlasViewer.from_pack(
        args.mesh_pack,
        mapping=args.mapping,
        catalog=catalog,
        enable_interaction=catalog is not None,
        explode=args.explode,
    ) as viewer:
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(title='IBL 3-D brain surface baseline', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
