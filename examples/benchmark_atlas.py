#!/usr/bin/env python3
"""Measure the native adapter on a materialized real atlas asset set."""

from __future__ import annotations

import argparse
import ctypes
import json
import resource
from pathlib import Path
from time import perf_counter

from ibl_anatomy import bundled_asset_set, verify_materialized_asset_set
from ibl_datoviz import AtlasMesh, AtlasTreeModel, AtlasViewer


def _measure_face_queries(viewer: AtlasViewer) -> list[dict]:
    measurements = []
    for request_id in range(1, 4):
        request = viewer.dvz.dvz_query_request()
        request.request_id = request_id
        request.target = viewer.dvz.DVZ_SCENE_TARGET_FACE
        query_start = perf_counter()
        viewer._check(
            viewer.dvz.dvz_panel_query_px(viewer.panel, 450, 360, ctypes.byref(request)),
            'face query',
        )
        queued = perf_counter()
        result = viewer.dvz.DvzQueryResult()
        resolved = False
        frames = 0
        while not resolved and frames < 5:
            viewer._check(viewer.dvz.dvz_view_render_once(viewer.view), 'query frame')
            frames += 1
            while viewer.dvz.dvz_scene_poll_query(viewer.scene, ctypes.byref(result)):
                if result.request_id == request_id:
                    resolved = True
                    break
        if not resolved:
            raise RuntimeError('Datoviz face query did not resolve within five frames')
        measurements.append(
            {
                'queue_seconds': queued - query_start,
                'resolve_seconds': perf_counter() - query_start,
                'frames': frames,
                'hit': bool(result.hit),
                'face_id': int(result.face_id),
            }
        )
    return measurements


def main() -> int:
    """Verify, prepare, and optionally render one pinned atlas asset set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path)
    parser.add_argument('--render', type=Path, metavar='PNG')
    parser.add_argument('--json', type=Path, metavar='REPORT')
    args = parser.parse_args()

    start = perf_counter()
    assets = verify_materialized_asset_set(bundled_asset_set(), args.asset_root)
    verified = perf_counter()
    mesh = AtlasMesh.from_geometry(assets.geometry)
    prepared = perf_counter()

    mappings = {}
    for mapping in mesh.mapping_names:
        model = AtlasTreeModel.from_catalog(assets.regions, mapping)
        mapping_start = perf_counter()
        vertex_ids = mesh.mapping_ids(mapping)
        face_ids = mesh.face_mapping_ids(mapping)
        colors = mesh.colors(mapping, model.palette)
        mappings[mapping] = {
            'seconds': perf_counter() - mapping_start,
            'vertex_region_count': len(set(vertex_ids.tolist())),
            'face_region_count': len(set(face_ids.tolist())),
            'color_bytes': colors.nbytes,
        }

    render_seconds = None
    render_maximum_resident_set_kib = None
    face_queries = []
    if args.render:
        render_start = perf_counter()
        with AtlasViewer(mesh, catalog=assets.regions, width=900, height=720) as viewer:
            viewer.render_offscreen(args.render)
            render_seconds = perf_counter() - render_start
            render_maximum_resident_set_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            face_queries = _measure_face_queries(viewer)

    report = {
        'asset_set_id': bundled_asset_set().asset_set_id,
        'vertices': len(mesh.positions),
        'triangles': len(mesh.indices) // 3,
        'components': len(assets.geometry.ranges),
        'presentations': len(mesh.presentations),
        'verify_decode_seconds': verified - start,
        'adapter_seconds': prepared - verified,
        'mapping_preparation': mappings,
        'offscreen_setup_render_capture_seconds': render_seconds,
        'offscreen_maximum_resident_set_kib': render_maximum_resident_set_kib,
        'center_face_queries': face_queries,
        'maximum_resident_set_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
