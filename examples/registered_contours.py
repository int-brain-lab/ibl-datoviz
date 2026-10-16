#!/usr/bin/env python3
"""Review shared exact 10 µm contours independently of the linked workspace.

This prototype reads explicit local assets. It does not provide picking, coarse
mapping unions, navigation or a replacement scientific label source.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np

from ibl_anatomy import open_anatomy_pack, open_region_catalog

DEFAULT_SECTIONS = (('coronal', 660), ('sagittal', 566), ('horizontal', 393))


def check(status, context):
    """Reject native failures before recording a successful prototype run."""
    if status != 0:
        raise RuntimeError(f'{context}: native status {status}')


def polygon_descriptor(dvz, component):
    """Borrow owned plane buffers only until the native copy operation returns."""
    rings = [
        np.array(ring, dtype=np.float64, order='C', copy=True)
        for ring in (component.outer, *component.holes)
    ]
    for ring in rings:
        ring[:, 1] *= -1  # SVG v points down; native view2d y points up.
    descriptor = dvz.dvz_polygon_desc()
    descriptor.outer.xy = ctypes.c_void_p(rings[0].ctypes.data)
    descriptor.outer.count = len(rings[0])
    holes = (dvz.DvzPolygonRing * (len(rings) - 1))()
    for hole, ring in zip(holes, rings[1:], strict=True):
        hole.xy = ctypes.c_void_p(ring.ctypes.data)
        hole.count = len(ring)
    descriptor.holes = holes
    descriptor.hole_count = len(holes)
    return descriptor, (rings, holes)


def add_contours(dvz, scene, panel, contours, colors, *, stroke_width=0.6):
    """Create one scene-owned polygon set from shared components and holes.

    Private positive native keys index a side table of signed Allen IDs. Native
    polygon storage copies every borrowed ring; temporary arrays need not outlive
    each add_region call. The scene releases the set and generated visuals.
    """
    polygons = dvz.dvz_polygons(scene, 0)
    if not polygons:
        raise RuntimeError('polygon set creation failed')
    identities = []
    for path in contours:
        allen_id = path.atlas_ids['allen']
        color = dvz.DvzColor(*colors[allen_id], 255)
        for component in path.components:
            descriptor, storage = polygon_descriptor(dvz, component)
            index = dvz.dvz_polygons_add_region(polygons, ctypes.byref(descriptor))
            if index == 0xFFFFFFFF:
                raise RuntimeError(f'polygon component rejected for Allen {allen_id}')
            # Keep borrowed arrays alive through the native geometry copy.
            del storage
            identities.append(allen_id)
            check(dvz.dvz_polygons_set_region_id(polygons, index, len(identities)), 'region key')
            check(dvz.dvz_polygons_set_region_fill_color(polygons, index, color), 'region fill')
            check(
                dvz.dvz_polygons_set_region_stroke_color(
                    polygons, index, dvz.DvzColor(215, 225, 233, 140)
                ),
                'region stroke',
            )
            check(
                dvz.dvz_polygons_set_region_stroke_width_px(polygons, index, stroke_width),
                'stroke width',
            )
    check(dvz.dvz_polygons_set_stroke_join(polygons, dvz.DVZ_PATH_JOIN_ROUND, 4.0), 'round joins')
    composite = dvz.dvz_polygons_composite(polygons, 0)
    if not composite:
        raise RuntimeError('polygon composite creation failed')
    fill = dvz.dvz_composite_visual(composite, b'fill')
    stroke = dvz.dvz_composite_visual(composite, b'stroke')
    if not fill or not stroke:
        raise RuntimeError('polygon composite roles unavailable')
    material = dvz.dvz_material_desc()
    material.model = dvz.DVZ_MATERIAL_MODEL_UNLIT
    material.alpha_mode = dvz.DVZ_ALPHA_OPAQUE
    check(dvz.dvz_visual_set_material(fill, material), 'unlit fill material')
    check(dvz.dvz_visual_set_depth_test(fill, False), 'fill depth')
    check(dvz.dvz_visual_set_depth_test(stroke, False), 'stroke depth')
    check(dvz.dvz_visual_set_alpha_mode(stroke, dvz.DVZ_ALPHA_BLENDED), 'stroke blending')
    attach = dvz.dvz_visual_attach_desc()
    attach.coord_space = dvz.DVZ_VISUAL_COORD_DATA
    check(dvz.dvz_panel_add_composite(panel, composite, ctypes.byref(attach)), 'attach contours')
    return polygons, tuple(identities)


def configure_panel(dvz, panel, projection, zoom, samples):
    """Preserve physical aspect and source orientation without changing geometry."""
    check(dvz.dvz_panel_set_background_color(panel, dvz.DvzColor(29, 33, 39, 255)), 'background')
    x, y, width, height = projection.manifest['view_box']
    view = dvz.dvz_panel_view2d_desc()
    view.mode = dvz.DVZ_PANEL_VIEW2D_CONTAIN
    view.aspect = dvz.DVZ_PANEL_VIEW2D_ASPECT_EQUAL
    view.padding = 0.04
    view.domain_x[:] = (x + width / 2 - width / (2 * zoom), x + width / 2 + width / (2 * zoom))
    view.domain_y[:] = (
        -y - height / 2 - height / (2 * zoom),
        -y - height / 2 + height / (2 * zoom),
    )
    view.has_domain_x = view.has_domain_y = True
    check(dvz.dvz_panel_set_view2d(panel, ctypes.byref(view)), 'equal slice domain')
    if samples > 1:
        msaa = dvz.dvz_msaa_desc()
        msaa.enabled = True
        msaa.sample_count = samples
        check(dvz.dvz_panel_set_msaa(panel, ctypes.byref(msaa)), 'slice MSAA')


def run(args):  # noqa: PLR0912, PLR0915 - bounded standalone native experiment.
    """Verify/decode before opening a scene and emit an explicit evidence receipt."""
    import datoviz as dvz  # noqa: PLC0415 - load native runtime only when executing.
    import datoviz._ctypes as native  # noqa: PLC0415 - record loaded binary identity.

    from ibl_anatomy import decode_registered_contours  # noqa: PLC0415 - development API.

    anatomy = open_anatomy_pack(
        args.anatomy,
        reference_space_id=args.reference_space_id,
        grid_id=args.grid_id,
    )
    anatomy.verify()
    catalog = open_region_catalog(args.regions)
    if catalog.reference_space_id != anatomy.reference_space_id:
        raise ValueError('region catalog and contour reference spaces differ')
    colors = {
        row.atlas_id: tuple(bytes.fromhex(row.color_hex.removeprefix('#')))
        for row in catalog.physical('allen')
    }
    prepared, receipts = [], []
    for name, index in DEFAULT_SECTIONS:
        projection = anatomy.projections[name]
        started = time.perf_counter()
        section = projection.load_slice(index)
        loaded = time.perf_counter()
        contours = decode_registered_contours(section)
        decoded = time.perf_counter()
        prepared.append((projection, contours))
        receipts.append(
            {
                'projection': name,
                'index': index,
                'world_coordinate_um': section.world_coordinate_um,
                'load_ms': 1000 * (loaded - started),
                'decode_ms': 1000 * (decoded - loaded),
                'paths': len(contours),
                'components': sum(len(p.components) for p in contours),
                'holes': sum(len(c.holes) for p in contours for c in p.components),
                'vertices': sum(
                    len(r) for p in contours for c in p.components for r in (c.outer, *c.holes)
                ),
                'plane_index_to_world_um': projection.plane_index_to_world_um,
            }
        )
    scene = app = None
    try:
        scene = dvz.dvz_scene()
        if not scene:
            raise RuntimeError('scene creation failed')
        figure = dvz.dvz_figure(scene, args.width, args.height, 0)
        if not figure:
            raise RuntimeError('figure creation failed')
        grid = dvz.dvz_figure_grid(figure, 1, 3)
        if not grid:
            raise RuntimeError('grid creation failed')
        for column, ((projection, contours), receipt) in enumerate(
            zip(prepared, receipts, strict=True)
        ):
            panel = dvz.dvz_grid_panel(grid, 0, column)
            if not panel:
                raise RuntimeError('panel creation failed')
            configure_panel(dvz, panel, projection, args.zoom, args.samples)
            started = time.perf_counter()
            _, ids = add_contours(dvz, scene, panel, contours, colors, stroke_width=args.stroke)
            receipt['native_prepare_ms'] = 1000 * (time.perf_counter() - started)
            receipt['component_identity_sha256'] = hashlib.sha256(
                np.array(ids, dtype='<i8').tobytes()
            ).hexdigest()
        app = dvz.dvz_app(scene)
        if not app:
            raise RuntimeError('native app creation failed')
        if args.offscreen:
            view = dvz.dvz_view_offscreen(app, figure, args.width, args.height)
        else:
            view = dvz.dvz_view_window(
                app,
                figure,
                args.width,
                args.height,
                b'Exact shared contours: coronal | sagittal | horizontal',
            )
        if not view:
            raise RuntimeError('native view creation failed')
        started = time.perf_counter()
        check(dvz.dvz_view_render_once(view), 'initial contour render')
        first_ms = 1000 * (time.perf_counter() - started)
        timings = []
        for _ in range(5):
            started = time.perf_counter()
            check(dvz.dvz_view_render_once(view), 'warm contour render')
            timings.append(1000 * (time.perf_counter() - started))
        if args.offscreen:
            args.offscreen.parent.mkdir(parents=True, exist_ok=True)
            check(dvz.dvz_view_capture_png(view, str(args.offscreen).encode()), 'contour capture')
        else:
            dvz.dvz_app_run(app, args.frames)
        report = {
            'prototype': 'exact-registered-contours-v1',
            'anatomy_pack': anatomy.pack_id,
            'reference_space_id': anatomy.reference_space_id,
            'grid_id': anatomy.grid_id,
            'manifest_sha256': hashlib.sha256(
                (args.anatomy / 'manifest.json').read_bytes()
            ).hexdigest(),
            'regions_sha256': hashlib.sha256(args.regions.read_bytes()).hexdigest(),
            'geometry_profile': 'exact-cell-edge',
            'mapping': 'allen',
            'reader_sha256': hashlib.sha256(
                Path(decode_registered_contours.__code__.co_filename).read_bytes()
            ).hexdigest(),
            'native_library_sha256': hashlib.sha256(
                Path(native.dvz._name).read_bytes()
            ).hexdigest(),
            'panels_left_to_right': receipts,
            'zoom': args.zoom,
            'width': args.width,
            'height': args.height,
            'stroke_width_px': args.stroke,
            'requested_msaa_samples': args.samples,
            'initial_render_ms': first_ms,
            'warm_render_ms': timings,
            'process_peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**2 if sys.platform == 'darwin' else 1024),
            'limitations': [
                'prototype only; no picking or navigation',
                'fine Allen boundaries; mapped/selection unions are a later stage',
            ],
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(
            json.dumps(
                {'initial_render_ms': first_ms, 'warm_render_ms': timings, 'sections': receipts},
                indent=2,
            )
        )
        return report
    finally:
        if app:
            dvz.dvz_app_destroy(app)
        if scene:
            dvz.dvz_scene_destroy(scene)


def main():
    """Accept only explicit local anatomy, catalog and legacy identity inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('anatomy', type=Path)
    parser.add_argument('--regions', type=Path, required=True)
    parser.add_argument('--reference-space-id', required=True)
    parser.add_argument('--grid-id', required=True)
    parser.add_argument('--offscreen', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--width', type=int, default=1800)
    parser.add_argument('--height', type=int, default=700)
    parser.add_argument('--zoom', type=float, default=1.0)
    parser.add_argument('--stroke', type=float, default=0.6)
    parser.add_argument('--samples', type=int, choices=(1, 4, 8), default=4)
    args = parser.parse_args()
    if args.frames < 0 or args.width <= 0 or args.height <= 0:
        parser.error('frames must be nonnegative and dimensions positive')
    if not math.isfinite(args.zoom) or args.zoom <= 0:
        parser.error('zoom must be finite and positive')
    if not math.isfinite(args.stroke) or args.stroke < 0:
        parser.error('stroke must be finite and nonnegative')
    run(args)


if __name__ == '__main__':
    main()
