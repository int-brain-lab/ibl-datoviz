"""Offline verified assets and bounded execution for scientific API examples."""

from __future__ import annotations

import json
from pathlib import Path

import ibl_anatomy
from ibl_datoviz.atlas import AtlasMesh
from ibl_datoviz.context import DEFAULT_CONTEXT_LANDMARKS, AtlasContextSurface


def add_arguments(parser):
    """Add explicit asset inputs and shared presentation/output settings."""
    parser.add_argument('atlas_root', type=Path, help='existing verified atlas asset directory')
    parser.add_argument('--context-root', type=Path, help='existing major surface directory')
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--frames', type=int, default=0, help='zero runs until closed')
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--report', type=Path, metavar='JSON')
    parser.add_argument('--ui-scale', type=float, default=1.0)
    parser.add_argument('--width', type=int, default=2240)
    parser.add_argument('--height', type=int, default=1600)


def prepare_viewer(args):
    """Verify local assets and prepare context before constructing native resources."""
    if args.frames < 0:
        raise ValueError('frames must be nonnegative')
    assets = ibl_anatomy.verify_materialized_asset_set(
        ibl_anatomy.bundled_asset_set(), args.atlas_root,
    )
    context = []
    if args.context_root is not None:
        mesh = AtlasMesh.from_geometry(assets.geometry)
        catalog = ibl_anatomy.bundled_surface_catalog()
        surfaces = ibl_anatomy.load_surface_catalog(args.context_root, catalog)
        context = [
            AtlasContextSurface.from_geometry(
                geometry, mesh,
                color=tuple(bytes.fromhex(member.color_hex.removeprefix('#'))),
                name=member.name,
            )
            for member, geometry in zip(catalog.members, surfaces, strict=True)
            if member.asset.source_allen_id in DEFAULT_CONTEXT_LANDMARKS
        ]
    return {
        'atlas': assets,
        'anatomy': 'major' if context else 'detailed',
        'anatomical_context': context,
        'mapping': args.mapping,
        'layout': '3d',
        'width': args.width,
        'height': args.height,
        'ui_scale': args.ui_scale,
        'context_opacity': 0.04,
        'surface_opacity': 0.18,
        'camera_angles': (-1.15, -0.20, 2.50),
        'enable_hover': False,
        'selection_presentation': 'all',
    }


def finish(viewer, args, report, title):
    """Run the existing frame loop or capture once, then write an explicit receipt."""
    if args.offscreen is not None:
        args.offscreen.parent.mkdir(parents=True, exist_ok=True)
        viewer.render_offscreen(args.offscreen)
    else:
        viewer.show(title=title, frame_count=args.frames)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
