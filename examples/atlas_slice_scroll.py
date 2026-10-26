#!/usr/bin/env python3
"""Scroll one Allen anatomical slice plane in the native linked navigator.

The wheel over a slice panel advances that panel's AP/ML/DV plane.  The other
two panels and the shared world-space cursor are updated at the same time.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_datoviz import AtlasViewer
from ibl_datoviz.components import AtlasCursor


def _cursor_at_slice(navigator: AtlasViewer, axis: str, index: int) -> AtlasCursor:
    """Return the centred cursor with one anatomical plane at ``index``."""
    if axis not in ('ap', 'ml', 'dv'):
        raise ValueError('slice axis must be ap, ml or dv')
    cursor = AtlasCursor.centre(navigator._linked.volumes)
    return cursor.replace(axis, index, navigator._linked.slice_source.grid.shape)


def main() -> int:
    """Open the interactive navigator or capture its initial slice."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh_pack', type=Path, help='verified D070 mesh-pack directory')
    parser.add_argument('volume_pack', type=Path, help='verified Allen volume-pack directory')
    parser.add_argument('--axis', choices=('ap', 'ml', 'dv'), default='ap')
    parser.add_argument('--index', type=int, help='initial plane index (default: centre)')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--frames', type=int, default=0, help='interactive frame limit; zero runs until closed'
    )
    parser.add_argument('--ui-scale', type=float, default=1.0, help='GUI size multiplier')
    args = parser.parse_args()

    with AtlasViewer.from_packs(
        args.mesh_pack, args.volume_pack, mapping=args.mapping, ui_scale=args.ui_scale
    ) as navigator:
        if args.index is not None:
            cursor = _cursor_at_slice(navigator, args.axis, args.index)
            navigator.slices.set_position(ap=cursor.ap, ml=cursor.ml, dv=cursor.dv, units='voxel')
        if args.offscreen:
            rgba = navigator.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            navigator.show(
                title=f'IBL atlas {args.axis.upper()} slice scroll', frame_count=args.frames
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
