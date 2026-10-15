"""Capture synthetic native point/path depth cases without anatomy or engine changes.

Run ``uv run --frozen tools/diagnose_endpoint_depth.py``. The configured native
checkout must match the immutable dependency pin. Output is diagnostic evidence,
not a visual acceptance test; no current rendering defect is asserted as desired.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np


def projected_line_depth(distance_px, length_px, start_depth, end_depth):
    """Return affine device depth along the original projected centerline."""
    return start_depth + np.asarray(distance_px) / length_px * (end_depth - start_depth)


def extruded_path_depth(distance_px, length_px, start_depth, end_depth, extension_px):
    """Model equal end extensions retaining the unextended endpoint depths."""
    fraction = (np.asarray(distance_px) + extension_px) / (length_px + 2 * extension_px)
    return start_depth + fraction * (end_depth - start_depth)


def project(positions, model, size):
    """Project the explicit perspective camera used by this isolated scene."""
    transformed = np.column_stack((positions, np.ones(len(positions)))) @ model.T
    view_z = transformed[:, 2] - 3.0
    scale = 1 / np.tan(0.72 / 2)
    xy = transformed[:, :2] * scale / -view_z[:, None]
    xy[:, 1] *= -1
    pixels = (xy + 1) * size / 2
    near, far = 0.01, 100.0
    depth = far / (far - near) + far * near / ((far - near) * view_z)
    return pixels, depth


def check(status, context):
    """Reject a failed native operation immediately."""
    if status != 0:
        raise RuntimeError(f'{context}: native status {status}')


def capture_case(dvz, output, sign, order, angle_index, angles, alpha_mode):  # noqa: PLR0915
    """Render point-only, combined, and opaque-mesh-occluded frames."""
    from ibl_datoviz import (  # noqa: PLC0415
        InsertionCollectionVisual,
        PointCollection,
        PointCollectionVisual,
    )

    size = 256
    scene = dvz.dvz_scene()
    app = point = paths = occluder = None
    name = f'slope{sign:+d}-{order}-camera{angle_index}-{alpha_mode}'
    try:
        figure = dvz.dvz_figure(scene, size, size, 0)
        panel = dvz.dvz_panel_full(figure)
        check(
            dvz.dvz_panel_set_background_color(panel, dvz.DvzColor(29, 33, 39, 255)), 'background'
        )
        camera = dvz.dvz_camera_desc()
        camera.view.eye[:] = (0, 0, 3)
        camera.view.target[:] = (0, 0, 0)
        camera.view.up[:] = (0, 1, 0)
        camera.projection.fov_y = 0.72
        camera.projection.near_clip = 0.01
        camera.projection.far_clip = 100
        check(dvz.dvz_panel_set_camera_desc(panel, camera), 'camera')
        positions = np.array([[0, 0, 0], [0.7, 0.15, sign * 0.55]], np.float32)

        def add_point():
            return PointCollectionVisual(
                dvz,
                scene,
                panel,
                PointCollection.from_arrays([[0, 0, 0]], [[255, 70, 180, 255]], sizes_px=30),
                alpha_mode=alpha_mode,
            )

        def add_path():
            collection = InsertionCollectionVisual(dvz, scene, panel)
            collection.set_insertion('path', positions, color=(255, 255, 255, 255), width_px=6)
            return collection

        if order == 'point-first':
            point, paths = add_point(), add_path()
        else:
            paths, point = add_path(), add_point()
        app = dvz.dvz_app(scene)
        if not app:
            raise RuntimeError('native graphics runtime unavailable')
        view = dvz.dvz_view_offscreen(app, figure, size, size)
        if not view:
            raise RuntimeError('offscreen view unavailable')
        arcball = dvz.dvz_view_arcball(view, panel, None)
        check(dvz.dvz_arcball_initial(arcball, (ctypes.c_float * 3)(*angles)), 'arcball')
        native_model = ((ctypes.c_float * 4) * 4)()
        check(dvz.dvz_arcball_model(arcball, native_model), 'arcball model')
        model = np.ctypeslib.as_array(native_model).T.copy()
        pixels, depths = project(positions, model, size)

        def capture(suffix):
            check(dvz.dvz_view_render_once(view), 'render')
            rgba = np.array(dvz.dvz_view_capture_rgba(view), copy=True)
            path = output / f'{name}-{suffix}.png'
            check(dvz.dvz_view_capture_png(view, str(path).encode()), 'PNG capture')
            return rgba

        paths.set_visible('path', False)
        reference = capture('point')
        paths.set_visible('path', True)
        combined = capture('combined')
        # A real opaque mesh, in front of the endpoint in camera space. Inverse
        # model keeps it camera-facing under all three actual arcball angles.
        square = np.array(
            [
                [-0.24, -0.24, 0.8, 1],
                [0.24, -0.24, 0.8, 1],
                [0.24, 0.24, 0.8, 1],
                [-0.24, 0.24, 0.8, 1],
            ]
        )
        vertices = np.ascontiguousarray((square @ np.linalg.inv(model).T)[:, :3], np.float32)
        occluder = dvz.dvz_mesh(scene, 0)
        material = dvz.dvz_material_desc()
        material.model, material.alpha_mode = dvz.DVZ_MATERIAL_MODEL_UNLIT, dvz.DVZ_ALPHA_OPAQUE
        material.opacity = 1
        check(dvz.dvz_visual_set_material(occluder, material), 'mesh material')
        check(dvz.dvz_visual_set_depth_test(occluder, True), 'mesh depth')
        check(
            dvz.dvz_visual_set_data_many(
                occluder,
                {
                    'position': vertices,
                    'normal': np.tile(np.array([0, 0, 1], np.float32), (4, 1)),
                    'color': np.tile(np.array([30, 190, 220, 255], np.uint8), (4, 1)),
                },
            ),
            'mesh attributes',
        )
        check(
            dvz.dvz_visual_set_index_data(occluder, np.array([0, 1, 2, 0, 2, 3], np.uint32)),
            'mesh indices',
        )
        check(dvz.dvz_panel_add_visual(panel, occluder, None), 'mesh attach')
        occluded = capture('occluded')

        # Fully colored reference pixels avoid counting point antialiasing.
        mask = (reference[..., 0] > 240) & (reference[..., 1] < 90)
        white = np.min(combined[..., :3], axis=2) > 230
        pink_occluded = (occluded[..., 0] > 240) & (occluded[..., 1] < 90)
        cyan_occluded = (occluded[..., 1] > 160) & (occluded[..., 2] > 190)
        length = float(np.linalg.norm(pixels[1] - pixels[0]))
        extension = 6 / 2 + 1.5  # stroke.glsl round-cap support, including AA
        current = float(extruded_path_depth(0, length, *depths, extension))
        corrected_inside = float(projected_line_depth(5, length, *depths))
        return {
            'name': name,
            'world_positions': positions.tolist(),
            'angles': angles,
            'attachment_order': order,
            'point_alpha': alpha_mode,
            'projected_endpoints_px': pixels.tolist(),
            'endpoint_device_depths': depths.tolist(),
            'projected_length_px': length,
            'round_cap_support_px': extension,
            'path_depth_at_shared_endpoint_model': current,
            'path_endpoint_depth_error_model': current - float(depths[0]),
            'corrected_path_depth_5px_into_disk_model': corrected_inside,
            'corrected_path_minus_point_depth_5px_into_disk_model': (
                corrected_inside - float(depths[0])
            ),
            'point_interior_pixels': int(mask.sum()),
            'white_path_pixels_inside_point': int(np.count_nonzero(mask & white)),
            'pink_pixels_after_nearer_mesh': int(np.count_nonzero(mask & pink_occluded)),
            'cyan_pixels_after_nearer_mesh': int(np.count_nonzero(mask & cyan_occluded)),
        }
    finally:
        if point is not None:
            point.close()
        if paths is not None:
            paths.close()
        if occluder:
            dvz.dvz_visual_destroy(occluder)
        if app:
            dvz.dvz_app_destroy(app)
        dvz.dvz_scene_destroy(scene)


def main():
    """Load the strict configured pairing and save independently inspectable cases."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build/endpoint-depth'))
    parser.add_argument(
        '--datoviz', type=Path, help='pinned source checkout; defaults to review setup'
    )
    parser.add_argument(
        '--library', type=Path, help='existing native library; never builds Datoviz'
    )
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    from review import CONFIG, doctor, git_revision, source_pin  # noqa: PLC0415

    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    checkout = args.datoviz or config.get('datoviz')
    if args.library:
        os.environ['DATOVIZ_LIBRARY'] = str(args.library.expanduser().resolve())
    if not args.worker:
        if checkout is None:
            parser.error('configure review setup first or supply --datoviz PATH')
        prefix, environment = doctor(Path(checkout), strict=True)
        subprocess.run(
            [
                *prefix,
                sys.executable,
                str(Path(__file__).resolve()),
                '--worker',
                '--output',
                str(args.output.resolve()),
                '--datoviz',
                str(Path(checkout).expanduser().resolve()),
            ],
            env=environment,
            check=True,
        )
        return
    import datoviz as dvz  # noqa: PLC0415
    import datoviz._ctypes as native  # noqa: PLC0415

    revision = git_revision(Path(dvz.__file__).resolve().parent.parent)
    pin = source_pin('datoviz')
    if revision != pin:
        raise RuntimeError(f'Imported native source is {revision}; locked pin is {pin}')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = []
    for alpha in ('blended', 'opaque'):
        for sign in (-1, 1):
            for order in ('point-first', 'path-first'):
                for index, angles in enumerate(
                    ((0.0, 0.0, 0.0), (0.3, 0.4, 0.0), (-0.4, -0.5, 0.2))
                ):
                    case = capture_case(dvz, args.output, sign, order, index, angles, alpha)
                    cases.append(case)
                    print(
                        f'{case["name"]}: {case["white_path_pixels_inside_point"]} white pixels; '
                        f'{case["pink_pixels_after_nearer_mesh"]} pink behind mesh',
                        flush=True,
                    )
    with Path(native.dvz._name).open('rb') as library:
        library_digest = hashlib.file_digest(library, 'sha256').hexdigest()
    report = {
        'configured_checkout': str(checkout) if checkout else None,
        'imported_source': str(Path(dvz.__file__).resolve()),
        'source_revision': revision,
        'native_library': str(native.dvz._name),
        'native_library_sha256': library_digest,
        'pin': pin,
        'cases': cases,
        'limitations': [
            'Native captures use the unchanged pinned engine; no corrected shader is rendered.',
            'Depth errors are analytical predictions, not a depth-buffer readback.',
            'Correct centerline depth alone cannot enforce complete marker coverage when '
            'a nearer part of the 3D path crosses the constant-depth marker disk.',
        ],
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
