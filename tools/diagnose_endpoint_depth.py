"""Capture synthetic native point/path depth cases without anatomy.

Run ``uv run --frozen tools/diagnose_endpoint_depth.py``. The configured native
checkout must match the immutable dependency pin. Output is diagnostic evidence,
not a visual acceptance test; no current rendering defect is asserted as desired.
Candidate checks require explicit source, library and full revision identities;
``--endpoint-gaps`` asserts the opt-in public endpoint gap API at 15 logical pixels.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
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


def gap_positions(kind, sign):
    """Return owned synthetic geometry exposing both endpoint exclusion disks."""
    start = [0, 0, 0]
    end = [0.7, 0.15, sign * 0.55]
    if kind == 'short':
        return np.array([start, [0.08, 0.015, sign * 0.05]], np.float32)
    if kind in ('reentry', 'reentry-end'):
        positions = np.array([start, end, [0.005, 0.005, 0.05], [-0.6, 0.1, 0.2]], np.float32)
        return positions if kind == 'reentry' else positions[::-1].copy()
    return np.array([start, end], np.float32)


def candidate_selection(checkout, library, expected_revision):
    """Require all explicit candidate identities, including an unambiguous Git SHA."""
    if checkout is None or library is None or expected_revision is None:
        raise ValueError('candidate mode requires --datoviz, --library and --expected-revision')
    if re.fullmatch(r'[0-9a-fA-F]{40}', expected_revision) is None:
        raise ValueError('--expected-revision must be a full 40-character Git SHA')
    checkout, library = checkout.expanduser().resolve(), library.expanduser().resolve()
    if not (checkout / 'datoviz' / '__init__.py').is_file() or not library.is_file():
        raise ValueError('candidate checkout and native library must already exist')
    return checkout, library, expected_revision.lower()


def assert_gap_pixels(case):
    """Require exclusion, surviving external geometry and genuine mesh occlusion."""
    if case['point_interior_pixels'] == 0:
        raise AssertionError(f'{case["name"]}: no marker reference pixels')
    if case['white_path_pixels_inside_point'] != 0:
        raise AssertionError(f'{case["name"]}: white path crosses a marker interior')
    if case['white_path_pixels_after_nearer_mesh'] != 0:
        raise AssertionError(f'{case["name"]}: path appears through nearer opaque mesh')
    if case['pink_pixels_after_nearer_mesh'] != 0:
        raise AssertionError(f'{case["name"]}: marker appears through nearer opaque mesh')
    if case['cyan_pixels_after_nearer_mesh'] != case['point_interior_pixels']:
        raise AssertionError(
            f'{case["name"]}: nearer opaque mesh does not cover every marker interior'
        )
    if case['geometry'] != 'short' and case['white_path_pixels_outside_point'] == 0:
        raise AssertionError(f'{case["name"]}: endpoint gaps erased the external path')
    if case['geometry'] == 'short' and case['white_path_pixels_total'] != 0:
        raise AssertionError(f'{case["name"]}: overlapping gaps left a visible short path')


def check(status, context):
    """Reject a failed native operation immediately."""
    if status != 0:
        raise RuntimeError(f'{context}: native status {status}')


def capture_case(  # noqa: PLR0915
    dvz, output, sign, order, angle_index, angles, alpha_mode, *, gaps=None, geometry='line'
):
    """Render point-only, combined, and opaque-mesh-occluded frames."""
    from ibl_datoviz.components import (  # noqa: PLC0415
        InsertionCollectionVisual,
        PointCollection,
        PointCollectionVisual,
    )

    size = 256
    scene = dvz.dvz_scene()
    app = point = paths = occluder = None
    name = f'slope{sign:+d}-{order}-camera{angle_index}-{alpha_mode}'
    if gaps is not None:
        name += f'-{geometry}-gaps{gaps[0]:g}-{gaps[1]:g}'
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
        positions = gap_positions(geometry, sign)

        marker_positions = positions[:1]
        if gaps is not None:
            marker_positions = positions[[i for i, gap in zip((0, -1), gaps, strict=True) if gap]]

        def add_point():
            return PointCollectionVisual(
                dvz,
                scene,
                panel,
                PointCollection.from_arrays(
                    marker_positions,
                    [[255, 70, 180, 255]] * len(marker_positions),
                    sizes_px=30,
                ),
                alpha_mode=alpha_mode,
            )

        def add_path():
            if gaps is not None:
                return GapPath(dvz, scene, panel, positions, gaps)
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
        pixels, depths = project(positions[[0, -1]], model, size)

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
        if gaps is not None:
            # Cover both markers with a camera-facing nearer opaque rectangle.
            centers = np.column_stack((positions[[0, -1]], np.ones(2))) @ model.T
            square[:, 0] = np.array([-1, 1, 1, -1]) * 2.0
            square[:, 1] = np.array([-1, -1, 1, 1]) * 2.0
            square[:, 2] = max(0.8, float(centers[:, 2].max()) + 0.4)
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
            'geometry': geometry,
            'endpoint_gaps_px': list(gaps) if gaps is not None else None,
            'white_path_pixels_outside_point': int(np.count_nonzero(~mask & white)),
            'white_path_pixels_total': int(np.count_nonzero(white)),
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
            'white_path_pixels_after_nearer_mesh': int(
                np.count_nonzero(np.min(occluded[..., :3], axis=2) > 230)
            ),
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


class GapPath:
    """Own a public native path for the candidate-only API diagnostic."""

    def __init__(self, dvz, scene, panel, positions, gaps):
        self.dvz = dvz
        self.visual = dvz.dvz_path(scene, 0)
        if not self.visual:
            raise RuntimeError('native path unavailable')
        try:
            check(dvz.dvz_visual_set_alpha_mode(self.visual, dvz.DVZ_ALPHA_OPAQUE), 'path alpha')
            check(dvz.dvz_visual_set_depth_test(self.visual, True), 'path depth')
            check(
                dvz.dvz_path_set_caps(
                    self.visual, dvz.DVZ_SEGMENT_CAP_ROUND, dvz.DVZ_SEGMENT_CAP_ROUND
                ),
                'path caps',
            )
            check(dvz.dvz_path_set_join(self.visual, dvz.DVZ_PATH_JOIN_ROUND, 4.0), 'path join')
            self.attributes = {
                'position': positions.copy(),
                'color': np.tile(np.array([255, 255, 255, 255], np.uint8), (len(positions), 1)),
                'stroke_width_px': np.full(len(positions), 6, np.float32),
            }
            check(dvz.dvz_visual_set_data_many(self.visual, self.attributes), 'path attributes')
            check(dvz.dvz_path_set_endpoint_gaps(self.visual, *gaps), 'endpoint gaps')
            check(dvz.dvz_panel_add_visual(panel, self.visual, None), 'path attach')
        except Exception:
            self.close()
            raise

    def set_visible(self, _identity, visible):
        """Match the visibility operation used by the pinned comparison scene."""
        check(self.dvz.dvz_visual_set_visible(self.visual, visible), 'path visibility')

    def close(self):
        """Release the path before its borrowed scene is destroyed."""
        self.dvz.dvz_visual_destroy(self.visual)


def main():  # noqa: PLR0912, PLR0915
    """Load the strict configured pairing and save independently inspectable cases."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('build/endpoint-depth'))
    parser.add_argument(
        '--datoviz', type=Path, help='pinned source checkout; defaults to review setup'
    )
    parser.add_argument(
        '--library', type=Path, help='existing native library; never builds Datoviz'
    )
    parser.add_argument('--expected-revision', help='explicit candidate full Git SHA')
    parser.add_argument('--endpoint-gaps', action='store_true', help='assert candidate gap API')
    parser.add_argument('--start-gap', type=float, choices=(0, 15), default=15)
    parser.add_argument('--end-gap', type=float, choices=(0, 15), default=15)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    from review import CONFIG, doctor, git_revision, source_pin  # noqa: PLC0415

    config = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    candidate = args.expected_revision is not None or args.endpoint_gaps
    checkout = args.datoviz or config.get('datoviz')
    if candidate:
        try:
            checkout, selected_library, expected = candidate_selection(
                args.datoviz, args.library, args.expected_revision
            )
        except ValueError as exc:
            parser.error(str(exc))
        if args.endpoint_gaps and not (args.start_gap or args.end_gap):
            parser.error('--endpoint-gaps requires at least one nonzero gap')
        if git_revision(checkout) != expected:
            parser.error('candidate checkout HEAD does not match --expected-revision')
    if args.library:
        os.environ['DATOVIZ_LIBRARY'] = str(args.library.expanduser().resolve())
    if not args.worker:
        if checkout is None:
            parser.error('configure review setup first or supply --datoviz PATH')
        if candidate:
            # Candidate runs inherit an already established graphics runtime.
            # Do not run or approve a checkout's .envrc implicitly.
            prefix, environment = [], os.environ.copy()
            environment['PYTHONPATH'] = os.pathsep.join(
                [
                    str(Path(__file__).resolve().parents[1]),
                    str(checkout),
                    environment.get('PYTHONPATH', ''),
                ]
            )
            environment['DATOVIZ_LIBRARY'] = str(selected_library)
        else:
            prefix, environment = doctor(Path(checkout), strict=True)
        candidate_args = []
        if candidate:
            candidate_args = ['--library', str(selected_library), '--expected-revision', expected]
            if args.endpoint_gaps:
                candidate_args += [
                    '--endpoint-gaps',
                    '--start-gap',
                    str(args.start_gap),
                    '--end-gap',
                    str(args.end_gap),
                ]
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
                *candidate_args,
            ],
            env=environment,
            check=True,
        )
        return
    import datoviz as dvz  # noqa: PLC0415
    import datoviz._ctypes as native  # noqa: PLC0415

    revision = git_revision(Path(dvz.__file__).resolve().parent.parent)
    if candidate:
        metadata = tomllib.loads(
            (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text()
        )
        pin = metadata['tool']['uv']['sources']['datoviz']['rev']
    else:
        pin = source_pin('datoviz')
    expected = expected if candidate else pin
    if revision != expected:
        raise RuntimeError(f'Imported native source is {revision}; expected {expected}')
    if not Path(dvz.__file__).resolve().is_relative_to(Path(checkout).resolve()):
        raise RuntimeError(f'Imported source is outside requested checkout: {dvz.__file__}')
    if args.library and Path(native.dvz._name).resolve() != args.library.expanduser().resolve():
        raise RuntimeError(f'Loaded library differs from --library: {native.dvz._name}')
    if args.endpoint_gaps and not hasattr(dvz, 'dvz_path_set_endpoint_gaps'):
        raise RuntimeError('candidate does not expose public dvz_path_set_endpoint_gaps')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = []
    for alpha in ('blended', 'opaque'):
        for sign in (-1, 1):
            for order in ('point-first', 'path-first'):
                for index, angles in enumerate(
                    ((0.0, 0.0, 0.0), (0.3, 0.4, 0.0), (-0.4, -0.5, 0.2))
                ):
                    geometries = (
                        ('line', 'reentry', 'reentry-end', 'short')
                        if args.endpoint_gaps
                        else ('line',)
                    )
                    for geometry in geometries:
                        case = capture_case(
                            dvz,
                            args.output,
                            sign,
                            order,
                            index,
                            angles,
                            alpha,
                            gaps=(args.start_gap, args.end_gap) if args.endpoint_gaps else None,
                            geometry=geometry,
                        )
                        cases.append(case)
                        if args.endpoint_gaps:
                            assert_gap_pixels(case)
                        print(
                            f'{case["name"]}: '
                            f'{case["white_path_pixels_inside_point"]} white pixels; '
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
        'candidate': candidate,
        'expected_revision': expected,
        'endpoint_gap_assertions': args.endpoint_gaps,
        'cases': cases,
        'limitations': [
            (
                'Native captures use the explicitly selected candidate engine.'
                if candidate
                else 'Native captures use the unchanged pinned engine; '
                'no corrected shader is rendered.'
            ),
            'Depth errors are analytical predictions, not a depth-buffer readback.',
            'Correct centerline depth alone cannot enforce complete marker coverage when '
            'a nearer part of the 3D path crosses the constant-depth marker disk.',
        ],
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
