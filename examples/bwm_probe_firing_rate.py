#!/usr/bin/env python3
"""Display one BWM probe with sites colored by mean firing rate."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from bwm_probe import BWM_CAMERA_ANGLES, FIXTURE, _load_fixture

from ibl_datoviz import AtlasViewer


def main() -> int:
    """Run the firing-rate site-color example, retaining missing values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    args = parser.parse_args()

    sites, provenance = _load_fixture(args.fixture)
    finite = sites.values[np.isfinite(sites.values)]
    value_range = tuple(float(value) for value in np.quantile(finite, (0.05, 0.95)))
    with AtlasViewer.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        surface_opacity=0.16,
        camera_angles=BWM_CAMERA_ANGLES,
    ) as viewer:
        viewer.set_probe((sites.positions_um[0], sites.positions_um[-1]), width_px=2)
        viewer.set_probe_data(
            sites,
            value_range=value_range,
            radius_um=85,
            color_scheme='sequential',
        )
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            insertion = provenance['insertion']
            title = f'BWM firing rates — {insertion["subject"]} {insertion["probe_name"]}'
            viewer.show(title=title, frame_count=args.frames)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
