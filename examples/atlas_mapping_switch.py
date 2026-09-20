#!/usr/bin/env python3
"""Compare Allen, Beryl, and Cosmos presentations of one D070 surface."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Open the atlas surface with its retained mapping selector."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='materialized D070 asset-set directory')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()

    with AtlasViewer.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        enable_interaction=True,
    ) as viewer:
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(
                title='IBL atlas mapping switch (Allen / Beryl / Cosmos)',
                frame_count=args.frames,
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
