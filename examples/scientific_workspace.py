#!/usr/bin/env python3
"""Compose explicit local data in one linked scientific workspace.

No discovery, downloads, signal reads or scientific aggregation occur here.
Without a release, points are illustrative annotations within verified mesh bounds.
Regional values, when requested, must be supplied as an explicit prepared JSON payload.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from examples.ibl_recordings import _receipt, _source
from examples.scientific_common import add_arguments, finish, prepare_viewer
from ibl_anatomy import open_anatomy_pack, open_intensity_block_pack, open_volume_pack
from ibl_datoviz import AtlasSliceSource, AtlasViewer, Paths, Points, RegionValues, WorldFrame
from ibl_datoviz.ibl import prepare_bwm_recording


def _illustrative_annotations(app):
    """Prepare local annotations without representing them as measured data."""
    xyz = app.mesh_data.positions_um
    minimum, maximum = xyz.min(axis=0), xyz.max(axis=0)
    targets = minimum + np.array([[0.42, 0.45, 0.50], [0.58, 0.55, 0.45]]) * (maximum - minimum)
    provenance = {'kind': 'illustrative annotations; not measured observations'}
    landmarks = app.add_points(
        Points((0, 'target-b'), targets, app.frame, provenance),
        name='Illustrative targets',
    )
    landmarks.set_size_px(12)
    route = app.add_paths(
        Paths(('route',), (targets,), app.frame, provenance), name='Optional route'
    )
    route.set_visible(False)
    app.tables.show(landmarks)


def _slice_options(args, parser):
    """Prepare one explicit source; sparse or incompatible assets never fall back."""
    if bool(args.intensity_pack) != bool(args.anatomy_pack):
        parser.error('--intensity-pack and --anatomy-pack must be supplied together')
    if args.slice_renderer == 'contours' and args.anatomy_pack is None:
        parser.error('contours require explicit --intensity-pack and --anatomy-pack')
    options = {}
    volumes = open_volume_pack(args.volume_pack).load_volumes()
    options.update(
        layout='linked', volumes=volumes, render_volume=False, slice_renderer=args.slice_renderer
    )
    if args.anatomy_pack is not None:
        intensity = open_intensity_block_pack(args.intensity_pack)
        anatomy = open_anatomy_pack(
            args.anatomy_pack,
            reference_space_id=intensity.reference_space_id,
            grid_id=intensity.grid_id,
        )
        options['slice_source'] = AtlasSliceSource(
            intensity,
            {p.world_slice_axis: p for p in anatomy.projections.values()},
            volumes.regions,
        )
    return options


def _arguments():
    """Declare the offline client inputs and parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument('--volume-pack', type=Path, required=True)
    parser.add_argument('--intensity-pack', type=Path)
    parser.add_argument('--anatomy-pack', type=Path)
    parser.add_argument('--slice-renderer', choices=('raster', 'contours'), default='raster')
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument('--release', type=Path, help='existing BWM release directory')
    sources.add_argument('--workspace', type=Path, help='existing shared-reader workspace')
    parser.add_argument('--pid', action='append', default=[])
    parser.add_argument('--frame-evidence', type=Path)
    parser.add_argument('--region-values', type=Path, help='prepared RegionValues JSON')
    parser.add_argument('--region-mapping-reduction', choices=('weighted_mean',))
    parser.add_argument('--plane', action='append', choices=('ap', 'ml', 'dv'), default=[])
    args = parser.parse_args()
    if bool(args.region_values) != bool(args.region_mapping_reduction):
        parser.error(
            '--region-values requires an explicit --region-mapping-reduction weighted_mean'
        )
    return parser, args


def main():
    """Prepare data before opening the GUI and retain one viewer/controller model."""
    parser, args = _arguments()
    if bool(args.release or args.workspace) != bool(args.pid):
        parser.error(
            '--release or --workspace and one or more distinct --pid values must be '
            'supplied together'
        )
    if len(set(args.pid)) != len(args.pid):
        parser.error('duplicate insertion IDs are not supported')
    if args.frame_evidence is not None and args.release is None and args.workspace is None:
        parser.error('--frame-evidence requires --release or --workspace')
    slice_options = _slice_options(args, parser)
    options = prepare_viewer(args)
    options.update(slice_options)
    frame = None
    if args.frame_evidence is not None:
        frame = WorldFrame(**json.loads(args.frame_evidence.read_text()))
        frame.require_verified()
    recordings = []
    if args.release is not None or args.workspace is not None:
        source = _source(args)
        recordings = [
            prepare_bwm_recording(source.insertion(pid), frame=frame) for pid in args.pid
        ]
    regional = None
    if args.region_values is not None:
        document = json.loads(args.region_values.read_text())
        document['frame'] = WorldFrame(**document['frame'])
        regional = RegionValues(**document)
        options['anatomy'] = 'detailed'
    report = {'recordings': [_receipt(recording) for recording in recordings]}
    with AtlasViewer(**options) as app:
        if recordings:
            for recording in recordings:
                handle = app.add_recording(
                    recording, name=recording.insertion_id, show=('channels', 'clusters')
                )
                app.tables.show(handle.clusters)
        else:
            _illustrative_annotations(app)
        if regional is not None:
            quantity = app.add_region_values(
                regional, mapping_reduction=args.region_mapping_reduction
            )
            quantity.color_by('value', cmap='sequential')
            report['regional_quantity'] = {
                'name': quantity.name,
                'units': quantity.payload.units,
                'mapping_reduction': args.region_mapping_reduction,
                'source_rows': len(quantity.payload.values),
            }
        for axis in args.plane:
            app.slices.show_plane(axis, in_3d=True)
        report.update(
            layout=app.layout,
            cursor_voxel_apmldv=list(app.slices.position.index),
            cursor_world_mlapdv_um=list(app.slices.position.world_um),
            plane_axes=list(app._slice_planes.visible_axes),
            observation_picking_unavailable=app.picking.unavailable_reason,
            signal_reads='not_requested',
        )
        finish(app, args, report, 'Linked scientific workspace')


if __name__ == '__main__':
    main()
