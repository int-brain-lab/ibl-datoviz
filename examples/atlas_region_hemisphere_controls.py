#!/usr/bin/env python3
"""Review independent region styling and left/right hemisphere visibility."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Open the D070 viewer with optional initial region and hemisphere state."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='materialized pinned D070 asset-set root')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--hemisphere', choices=('left', 'right', 'both'), default='left')
    parser.add_argument('--region-id', type=int, help='ID in the selected mapping')
    parser.add_argument('--region-hemisphere', choices=('left', 'right'))
    parser.add_argument('--opacity', type=float, default=0.45)
    parser.add_argument('--hide-region', action='store_true')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--ui-scale', type=float, default=1.0)
    args = parser.parse_args()
    if args.region_hemisphere and args.region_id is None:
        parser.error('--region-hemisphere requires --region-id')

    with AtlasViewer.from_asset_set(
        args.asset_root, mapping=args.mapping, ui_scale=args.ui_scale, enable_interaction=True
    ) as viewer:
        viewer.set_hemisphere(args.hemisphere)
        region_id = args.region_id
        if region_id is None:
            visible = viewer.visible_region_ids()
            if not visible:
                parser.error(f'no visible regions are available in the {args.mapping} mapping')
            region_id = visible[0]
        hemisphere = args.region_hemisphere
        if args.hide_region:
            viewer.hide_region(region_id, hemisphere=hemisphere)
        else:
            viewer.set_region_opacity(region_id, args.opacity, hemisphere=hemisphere)
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(title='D070 region and hemisphere controls', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
