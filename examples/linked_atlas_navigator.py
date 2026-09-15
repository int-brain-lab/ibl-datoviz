#!/usr/bin/env python3
"""Navigate linked Allen annotation slices, anatomy, surface, and ontology."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_datoviz import LinkedAtlasNavigator


def main() -> int:
    """Open verified mesh and volume packs in the native linked navigator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh_pack', type=Path, help='verified D070 mesh-pack directory')
    parser.add_argument('volume_pack', type=Path, help='verified Allen volume-pack directory')
    parser.add_argument(
        '--slice-intensity-pack', type=Path, help='registered high-resolution intensity pack'
    )
    parser.add_argument(
        '--coronal-projection', type=Path, help='registered coronal projection manifest'
    )
    parser.add_argument(
        '--sagittal-projection', type=Path, help='registered sagittal projection manifest'
    )
    parser.add_argument(
        '--horizontal-projection', type=Path, help='registered horizontal projection manifest'
    )
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--annotation-opacity', type=float, default=0.58)
    parser.add_argument('--volume-opacity', type=float, default=0.24)
    parser.add_argument(
        '--ui-scale', type=float, default=1.5, help='additional UI/accessibility scale'
    )
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--frames', type=int, default=0, help='interactive frame limit; zero runs until closed'
    )
    args = parser.parse_args()

    projection_paths = {
        'ap': args.coronal_projection,
        'ml': args.sagittal_projection,
        'dv': args.horizontal_projection,
    }
    high_resolution = args.slice_intensity_pack is not None or any(projection_paths.values())
    missing_projection = any(path is None for path in projection_paths.values())
    if high_resolution and (args.slice_intensity_pack is None or missing_projection):
        parser.error('high-resolution slices require the intensity pack and all three projections')
    common = {
        'mapping': args.mapping,
        'annotation_opacity': args.annotation_opacity,
        'volume_opacity': args.volume_opacity,
        'ui_scale': args.ui_scale,
    }
    if high_resolution:
        navigator = LinkedAtlasNavigator.from_multiresolution_packs(
            args.mesh_pack,
            args.volume_pack,
            args.slice_intensity_pack,
            projection_paths,
            **common,
        )
    else:
        navigator = LinkedAtlasNavigator.from_packs(args.mesh_pack, args.volume_pack, **common)
    with navigator:
        if args.offscreen:
            rgba = navigator.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            navigator.show(title='IBL linked atlas navigator', frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
