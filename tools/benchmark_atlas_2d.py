#!/usr/bin/env python3
"""Benchmark one isolated native atlas slice in fresh Datoviz processes."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import random
import resource
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import datoviz as dvz
import numpy as np

from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasSliceComposer

if TYPE_CHECKING:
    from collections.abc import Sequence

SCENARIOS = (
    'empty',
    'anatomy',
    'anatomy_annotation',
    'anatomy_annotation_boundaries',
    'complete',
)
TIMING_PREFIX = 'app_frame_timing:'
RESULT_PREFIX = 'atlas_2d_benchmark_result:'


def _parse_key_values(line: str, prefix: str) -> dict[str, int | float | str] | None:
    if not line.startswith(prefix):
        return None
    parsed: dict[str, int | float | str] = {}
    for token in line[len(prefix) :].strip().split():
        if '=' not in token:
            continue
        key, value = token.split('=', 1)
        try:
            number = float(value)
        except ValueError:
            parsed[key] = value
        else:
            parsed[key] = int(number) if number.is_integer() else number
    return parsed


def _slice_quad(shape: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    height, width = (int(value) for value in shape)
    aspect = width / height
    x_extent, y_extent = (0.94, 0.94 / aspect) if aspect >= 1 else (0.94 * aspect, 0.94)
    positions = np.array(
        [
            [-x_extent, -y_extent, 0],
            [-x_extent, +y_extent, 0],
            [+x_extent, -y_extent, 0],
            [+x_extent, +y_extent, 0],
        ],
        dtype=np.float32,
    )
    texcoords = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
    return positions, texcoords


def _map_segments(
    starts: np.ndarray, ends: np.ndarray, positions: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    lower = positions[0, :2]
    extent = positions[3, :2] - lower

    def mapped(values):
        xy = lower + values * extent
        return np.ascontiguousarray(
            np.column_stack((xy, np.full(len(xy), 0.02))), dtype=np.float32
        )

    return mapped(starts), mapped(ends)


def _check(result: int, action: str) -> None:
    if result != 0:
        raise RuntimeError(f'Datoviz {action} failed')


def _add_image(scene, panel, data, positions, texcoords, *, sampling: int, z_layer: int):
    field = dvz.dvz_sampled_field_from_array(
        scene,
        data,
        format=dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
        semantic=dvz.DVZ_FIELD_SEMANTIC_COLOR,
        dim=dvz.DVZ_FIELD_DIM_2D,
    )
    image = dvz.dvz_image(scene, 0)
    if not field or not image:
        raise RuntimeError('slice image creation failed')
    _check(
        dvz.dvz_visual_set_data_many(
            image, {'position': positions, 'texcoords': texcoords}
        ),
        'slice geometry upload',
    )
    _check(dvz.dvz_visual_set_field(image, b'field', field), 'slice field bind')
    _check(dvz.dvz_image_set_sampling(image, sampling), 'slice sampling')
    _check(dvz.dvz_visual_set_depth_test(image, False), 'slice depth disable')
    _check(dvz.dvz_visual_set_alpha_mode(image, dvz.DVZ_ALPHA_BLENDED), 'slice alpha mode')
    attach = dvz.dvz_visual_attach_desc()
    attach.controller_mode = dvz.DVZ_CONTROLLER_APPLY
    attach.coord_space = dvz.DVZ_VISUAL_COORD_DATA
    attach.z_layer = z_layer
    _check(dvz.dvz_panel_add_visual(panel, image, ctypes.byref(attach)), 'slice attach')
    return field, image


def _add_boundaries(scene, panel, starts, ends):
    visual = dvz.dvz_segment(scene, 0)
    if not visual:
        raise RuntimeError('slice boundary creation failed')
    count = len(starts)
    _check(
        dvz.dvz_visual_set_data_many(
            visual,
            {
                'position_start': starts,
                'position_end': ends,
                'color': np.tile(np.array([238, 242, 247, 209], dtype=np.uint8), (count, 1)),
                'stroke_width_px': np.full(count, 0.7, dtype=np.float32),
            },
        ),
        'slice boundaries upload',
    )
    _check(dvz.dvz_visual_set_depth_test(visual, False), 'boundary depth disable')
    _check(dvz.dvz_visual_set_alpha_mode(visual, dvz.DVZ_ALPHA_BLENDED), 'boundary alpha mode')
    attach = dvz.dvz_visual_attach_desc()
    attach.controller_mode = dvz.DVZ_CONTROLLER_APPLY
    attach.coord_space = dvz.DVZ_VISUAL_COORD_DATA
    attach.z_layer = 3
    _check(dvz.dvz_panel_add_visual(panel, visual, ctypes.byref(attach)), 'boundary attach')


def _add_crosshair(scene, panel, positions):
    visual = dvz.dvz_segment(scene, 0)
    if not visual:
        raise RuntimeError('slice crosshair creation failed')
    x0, y0 = positions[0, :2]
    x1, y1 = positions[3, :2]
    starts = np.array([[0, y0, 0.04], [x0, 0, 0.04]], dtype=np.float32)
    ends = np.array([[0, y1, 0.04], [x1, 0, 0.04]], dtype=np.float32)
    _check(
        dvz.dvz_visual_set_data_many(
            visual,
            {
                'position_start': starts,
                'position_end': ends,
                'color': np.tile(np.array([43, 220, 255, 235], dtype=np.uint8), (2, 1)),
                'stroke_width_px': np.full(2, 1.5, dtype=np.float32),
            },
        ),
        'slice crosshair upload',
    )
    _check(dvz.dvz_visual_set_depth_test(visual, False), 'crosshair depth disable')
    _check(dvz.dvz_visual_set_alpha_mode(visual, dvz.DVZ_ALPHA_BLENDED), 'crosshair alpha mode')
    attach = dvz.dvz_visual_attach_desc()
    attach.controller_mode = dvz.DVZ_CONTROLLER_APPLY
    attach.coord_space = dvz.DVZ_VISUAL_COORD_DATA
    attach.z_layer = 10
    _check(dvz.dvz_panel_add_visual(panel, visual, ctypes.byref(attach)), 'crosshair attach')


def _git_revision(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ('git', '-C', str(path), 'rev-parse', 'HEAD'),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _worker(args: argparse.Namespace) -> int:
    volumes = open_volume_pack(args.volume_pack).load_volumes()
    composer = AtlasSliceComposer(volumes, args.mapping)
    size = volumes.grid.shape[('ap', 'ml', 'dv').index(args.axis)]
    index = size // 2 if args.index is None else args.index
    anatomy, annotation = composer.compose_layers(args.axis, index)
    normalized_starts, normalized_ends = composer.boundary_segments(args.axis, index)
    positions, texcoords = _slice_quad(anatomy.shape[:2])
    starts, ends = _map_segments(normalized_starts, normalized_ends, positions)

    scene = dvz.dvz_scene()
    app = None
    try:
        figure = dvz.dvz_figure(scene, args.width, args.height, 0)
        panel = dvz.dvz_panel_full(figure)
        if not figure or not panel:
            raise RuntimeError('slice figure creation failed')
        dvz.dvz_panel_set_background_color(panel, dvz.DvzColor(29, 33, 39, 255))
        _check(dvz.dvz_panel_set_domain(panel, dvz.DVZ_DIM_X, -1.0, 1.0), 'x domain')
        _check(dvz.dvz_panel_set_domain(panel, dvz.DVZ_DIM_Y, -1.0, 1.0), 'y domain')
        view2d = dvz.dvz_panel_view2d_desc()
        view2d.mode = dvz.DVZ_PANEL_VIEW2D_CONTAIN
        view2d.aspect = dvz.DVZ_PANEL_VIEW2D_ASPECT_EQUAL
        _check(dvz.dvz_panel_set_view2d(panel, ctypes.byref(view2d)), '2-D panel view')

        if args.scenario != 'empty':
            _add_image(
                scene,
                panel,
                anatomy,
                positions,
                texcoords,
                sampling=dvz.DVZ_IMAGE_SAMPLING_LINEAR,
                z_layer=0,
            )
        if args.scenario in (
            'anatomy_annotation',
            'anatomy_annotation_boundaries',
            'complete',
        ):
            _add_image(
                scene,
                panel,
                annotation,
                positions,
                texcoords,
                sampling=dvz.DVZ_IMAGE_SAMPLING_NEAREST,
                z_layer=1,
            )
        if args.scenario in ('anatomy_annotation_boundaries', 'complete'):
            _add_boundaries(scene, panel, starts, ends)
        if args.scenario == 'complete':
            _add_crosshair(scene, panel, positions)

        app = dvz.dvz_app(scene)
        view = dvz.dvz_view_window(
            app, figure, args.width, args.height, f'2-D benchmark: {args.scenario}'.encode()
        )
        if not app or not view:
            raise RuntimeError('slice benchmark view creation failed')
        os.environ['DVZ_APP_FRAME_TIMING'] = '0'
        dvz.dvz_app_run(app, args.warmup)
        os.environ['DVZ_APP_FRAME_TIMING'] = '1'
        dvz.dvz_app_run(app, args.frames)
        root = Path(__file__).resolve().parents[1]
        record = {
            'schema_version': 1,
            'scenario': args.scenario,
            'repeat': args.repeat_index,
            'axis': args.axis,
            'index': index,
            'mapping': args.mapping,
            'slice_shape': list(anatomy.shape),
            'slice_bytes': anatomy.nbytes + annotation.nbytes,
            'boundary_segments': len(starts),
            'viewport': {'width': args.width, 'height': args.height},
            'memory': {
                'maximum_resident_set_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            },
            'environment': {
                'platform': platform.platform(),
                'python': platform.python_version(),
                'numpy': np.__version__,
                'git': {
                    'ibl_datoviz': _git_revision(root),
                    'datoviz': _git_revision(root.parents[1] / 'Viz' / 'datoviz'),
                },
            },
        }
        print(f'{RESULT_PREFIX} {json.dumps(record, sort_keys=True)}')
    finally:
        if app is not None:
            dvz.dvz_app_destroy(app)
        dvz.dvz_scene_destroy(scene)
    return 0


def _run_child(args: argparse.Namespace, scenario: str, repeat: int) -> dict:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(args.volume_pack),
        '--worker',
        '--scenario',
        scenario,
        '--repeat-index',
        str(repeat),
        '--axis',
        args.axis,
        '--mapping',
        args.mapping,
        '--warmup',
        str(args.warmup),
        '--frames',
        str(args.frames),
        '--width',
        str(args.width),
        '--height',
        str(args.height),
    ]
    if args.index is not None:
        command.extend(('--index', str(args.index)))
    environment = os.environ.copy()
    environment.update(
        {'DVZ_APP_SCHEDULE': 'continuous', 'DVZ_FPS_CAP': '0', 'DVZ_PRESENT_MODE': 'immediate'}
    )
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True, env=environment
    )
    timing = next(
        (
            parsed
            for line in completed.stdout.splitlines()
            if (parsed := _parse_key_values(line, TIMING_PREFIX)) is not None
        ),
        None,
    )
    payload = next(
        (
            json.loads(line[len(RESULT_PREFIX) :])
            for line in completed.stdout.splitlines()
            if line.startswith(RESULT_PREFIX)
        ),
        None,
    )
    if timing is None or payload is None:
        raise RuntimeError(
            f'benchmark child {scenario}/{repeat} produced no result\n'
            f'stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}'
        )
    if int(timing['frames']) != args.frames:
        raise RuntimeError(
            f'benchmark child rendered {timing["frames"]} frames, expected {args.frames}'
        )
    payload['datoviz_frame_timing_ms'] = timing
    run_ms = float(timing['run_ms'])
    payload['observed_fps'] = 1000.0 / run_ms if run_ms > 0 else None
    return payload


def _scenario_summary(runs: Sequence[dict]) -> dict[str, float | int]:
    summary: dict[str, float | int] = {'repeats': len(runs)}
    for field in ('run_ms', 'frame_ms', 'p50', 'p95', 'p99', 'prepare', 'execute', 'post'):
        summary[f'{field}_median'] = float(
            np.median([float(run['datoviz_frame_timing_ms'][field]) for run in runs])
        )
    summary['observed_fps_median'] = float(np.median([run['observed_fps'] for run in runs]))
    summary['maximum_resident_set_kib_median'] = int(
        np.median([run['memory']['maximum_resident_set_kib'] for run in runs])
    )
    return summary


def _parent(args: argparse.Namespace) -> int:
    runs = []
    jobs = [(scenario, repeat) for scenario in args.scenarios for repeat in range(args.repeats)]
    random.Random(args.seed).shuffle(jobs)
    for scenario, repeat in jobs:
        print(
            f'benchmarking {scenario} ({repeat + 1}/{args.repeats})', file=sys.stderr, flush=True
        )
        runs.append(_run_child(args, scenario, repeat))
    report = {
        'schema_version': 1,
        'benchmark': 'ibl-datoviz-isolated-2d-slice',
        'runs': runs,
        'summary': {
            scenario: _scenario_summary([run for run in runs if run['scenario'] == scenario])
            for scenario in args.scenarios
        },
    }
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + '\n', encoding='utf-8')
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('volume_pack', type=Path)
    parser.add_argument('--axis', choices=('ap', 'ml', 'dv'), default='dv')
    parser.add_argument('--index', type=int)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='allen')
    parser.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--warmup', type=int, default=30)
    parser.add_argument('--frames', type=int, default=120)
    parser.add_argument('--width', type=int, default=900)
    parser.add_argument('--height', type=int, default=720)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--scenario', choices=SCENARIOS, help=argparse.SUPPRESS)
    parser.add_argument('--repeat-index', type=int, default=0, help=argparse.SUPPRESS)
    return parser


def main() -> int:
    """Run one worker or aggregate the isolated slice benchmark."""
    args = _parser().parse_args()
    if args.warmup < 1 or args.frames < 2 or args.repeats < 1:
        raise ValueError('warmup, frames, and repeats must be positive (frames >= 2)')
    if args.worker:
        if args.scenario is None:
            raise ValueError('--worker requires --scenario')
        return _worker(args)
    return _parent(args)


if __name__ == '__main__':
    raise SystemExit(main())
