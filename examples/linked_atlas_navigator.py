#!/usr/bin/env python3
"""Navigate linked Allen annotation slices, anatomy, surface, and ontology."""

from __future__ import annotations

import argparse
from pathlib import Path

from ibl_anatomy import bundled_registered_asset_set, verify_materialized_registered_asset_set
from ibl_datoviz import LinkedAtlasNavigator


def main() -> int:
    """Open verified mesh and volume packs in the native linked navigator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh_pack', type=Path, help='verified D070 mesh-pack directory')
    parser.add_argument('volume_pack', type=Path, help='verified Allen volume-pack directory')
    parser.add_argument(
        '--slice-intensity-pack', type=Path, help='registered high-resolution intensity pack'
    )
    parser.add_argument('--anatomy-pack', type=Path, help='complete registered anatomy-v2 pack')
    parser.add_argument(
        '--registered-asset-root',
        type=Path,
        help='materialized root graph verified by the bundled ibl-anatomy lock',
    )
    parser.add_argument('--slice-resolution', choices=('volume', 'registered'), default='volume')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--annotation-opacity', type=float, default=0.58)
    parser.add_argument('--volume-opacity', type=float, default=0.24)
    parser.add_argument(
        '--ui-scale', type=float, default=1.125, help='additional UI/accessibility scale'
    )
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument(
        '--frames', type=int, default=0, help='interactive frame limit; zero runs until closed'
    )
    args = parser.parse_args()

    high_resolution = args.slice_resolution == 'registered'
    registered_source_count = sum(
        value is not None for value in (args.anatomy_pack, args.registered_asset_root)
    )
    if high_resolution and (args.slice_intensity_pack is None or registered_source_count != 1):
        parser.error(
            'registered slices require --slice-intensity-pack and exactly one of '
            '--registered-asset-root or --anatomy-pack'
        )
    if not high_resolution and (args.slice_intensity_pack is not None or registered_source_count):
        parser.error('high-resolution pack options require --slice-resolution registered')
    common = {
        'mapping': args.mapping,
        'annotation_opacity': args.annotation_opacity,
        'volume_opacity': args.volume_opacity,
        'ui_scale': args.ui_scale,
    }
    if args.registered_asset_root is not None:
        assets = verify_materialized_registered_asset_set(
            bundled_registered_asset_set(), args.registered_asset_root
        )
        navigator = LinkedAtlasNavigator.from_registered_assets(
            args.mesh_pack,
            args.volume_pack,
            args.slice_intensity_pack,
            assets,
            **common,
        )
    elif high_resolution:
        navigator = LinkedAtlasNavigator.from_anatomy_packs(
            args.mesh_pack,
            args.volume_pack,
            args.slice_intensity_pack,
            args.anatomy_pack,
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
