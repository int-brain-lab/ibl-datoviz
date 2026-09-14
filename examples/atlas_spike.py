#!/usr/bin/env python3
"""Display a verified atlas mesh pack with Datoviz v0.4."""

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
    parser.add_argument('--regions', type=Path, help='optional ibl-atlas-regions-v1 catalog')
    args = parser.parse_args()

    catalog = open_region_catalog(args.regions) if args.regions else None
    with AtlasViewer.from_pack(args.mesh_pack, mapping=args.mapping, catalog=catalog) as viewer:
        viewer.set_probe([[-1.5, -0.8, -0.8], [0.0, 0.0, 0.0], [2.5, 0.8, 0.8]])
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
