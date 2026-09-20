#!/usr/bin/env python3
"""Display one pinned BWM probe trajectory and its recording sites."""

from __future__ import annotations

import argparse
from pathlib import Path

from bwm_probe import BWM_CAMERA_ANGLES, FIXTURE, _load_fixture

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Run the geometry-only BWM probe example."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()

    sites, provenance = _load_fixture(args.fixture)
    with AtlasViewer.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        surface_opacity=0.16,
        camera_angles=BWM_CAMERA_ANGLES,
    ) as viewer:
        viewer.set_probe((sites.positions_um[0], sites.positions_um[-1]), width_px=2)
        viewer.set_probe_sites(sites.positions_um, radius_um=85)
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            insertion = provenance['insertion']
            title = f'BWM probe geometry — {insertion["subject"]} {insertion["probe_name"]}'
            viewer.show(title=title, frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
