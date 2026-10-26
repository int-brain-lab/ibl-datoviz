#!/usr/bin/env python3
"""Navigate real 50 um Allen slices without a native 3D volume visual."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Open the pinned 50 um slice source with volume rendering disabled."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh_pack', type=Path, help='verified D070 mesh-pack directory')
    parser.add_argument('volume_pack', type=Path, help='verified Allen 50 um source pack')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--ui-scale', type=float, default=1.0)
    args = parser.parse_args()

    with AtlasViewer.from_packs(
        args.mesh_pack,
        args.volume_pack,
        mapping=args.mapping,
        render_volume=False,
        ui_scale=args.ui_scale,
    ) as navigator:
        if args.offscreen:
            rgba = navigator.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            navigator.show(title='D070 volume-free slice navigator', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
