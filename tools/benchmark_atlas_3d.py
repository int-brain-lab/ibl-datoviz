#!/usr/bin/env python3
"""Benchmark isolated 3-D atlas features in fresh Datoviz processes."""

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
from time import perf_counter
from typing import TYPE_CHECKING

import datoviz as dvz
import numpy as np

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer

if TYPE_CHECKING:
    from collections.abc import Sequence

SCENARIOS = (
    'baseline',
    'rotation',
    'interaction_capability_idle',
    'face_query',
    'pointer_hover',
    'pointer_hover_burst',
    'gui_empty',
    'gui_viewport_empty',
    'gui_viewport_surface',
    'gui_tree_small',
    'gui_tree_full',
    'gui_idle',
    'gui_interaction_idle',
    'hover_emphasis_update',
    'selection_update',
    'explode_static',
    'explode_animated',
)
GUI_SCENARIOS = frozenset(
    (
        'gui_empty',
        'gui_viewport_empty',
        'gui_viewport_surface',
        'gui_tree_small',
        'gui_tree_full',
        'gui_idle',
        'gui_interaction_idle',
    )
)
GUI_PROFILE_SCENARIOS = {
    'gui_empty': 'empty',
    'gui_viewport_empty': 'empty_viewport',
    'gui_viewport_surface': 'surface_viewport',
    'gui_tree_small': 'tree',
    'gui_tree_full': 'tree',
}
INTERACTION_SCENARIOS = frozenset(
    (
        'interaction_capability_idle',
        'face_query',
        'pointer_hover',
        'pointer_hover_burst',
        'gui_interaction_idle',
    )
)
TIMING_PREFIX = 'app_frame_timing:'
LATENCY_PREFIX = 'app_interaction_latency:'
RESULT_PREFIX = 'atlas_3d_benchmark_result:'


class _BenchmarkAtlasViewer(AtlasViewer):
    """Atlas viewer with deliberately minimal benchmark-only GUI callbacks."""

    def __init__(self, *args, gui_profile: str, **kwargs):
        self._benchmark_gui_profile = gui_profile
        self._benchmark_empty_figure = None
        super().__init__(*args, **kwargs)

    def _gui_callback(self, gui, _view, _user_data) -> None:
        if self._benchmark_gui_profile not in (
            'empty',
            'empty_viewport',
            'surface_viewport',
            'tree',
        ):
            super()._gui_callback(gui, _view, _user_data)
            return
        if (
            self.dvz.dvz_gui_begin(gui, b'Atlas benchmark', None, 0)
            and self._benchmark_gui_profile == 'tree'
        ):
            self.dvz.dvz_gui_tree_draw(gui, self.region_tree)
        self.dvz.dvz_gui_end(gui)
        if self._benchmark_gui_profile in ('empty_viewport', 'surface_viewport'):
            self.dvz.dvz_gui_viewport_window(self.viewport, b'Benchmark viewport', None, 0)

    def use_empty_benchmark_viewport(self) -> None:
        """Replace the displayed benchmark viewport with a figure containing no visuals."""
        self._benchmark_empty_figure = self.dvz.dvz_figure(
            self.scene, self.width, self.height, 0
        )
        if not self._benchmark_empty_figure:
            raise RuntimeError('empty benchmark figure creation failed')
        panel = self.dvz.dvz_panel_full(self._benchmark_empty_figure)
        if not panel:
            raise RuntimeError('empty benchmark panel creation failed')
        config = self.dvz.dvz_gui_viewport_config()
        self.viewport = self.dvz.dvz_gui_viewport(
            self.gui, self._benchmark_empty_figure, ctypes.byref(config)
        )
        if not self.viewport:
            raise RuntimeError('empty benchmark viewport creation failed')


def _parse_key_values(line: str, prefix: str) -> dict[str, int | float | str] | None:
    """Parse one Datoviz whitespace-separated timing record."""
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


def _distribution(values: Sequence[float]) -> dict[str, float]:
    """Summarize measured Python mutation durations in milliseconds."""
    samples = np.asarray(values, dtype=np.float64) * 1e3
    if len(samples) == 0:
        return {}
    return {
        'mean_ms': float(samples.mean()),
        'median_ms': float(np.median(samples)),
        'p95_ms': float(np.percentile(samples, 95)),
        'p99_ms': float(np.percentile(samples, 99)),
        'minimum_ms': float(samples.min()),
        'maximum_ms': float(samples.max()),
    }


def _git_revision(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ('git', '-C', str(path), 'rev-parse', 'HEAD'),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _gpu_description() -> str | None:
    try:
        result = subprocess.run(
            (
                'nvidia-smi',
                '--query-gpu=name,driver_version',
                '--format=csv,noheader',
            ),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return '; '.join(line.strip() for line in result.stdout.splitlines() if line.strip()) or None


def _worker(args: argparse.Namespace) -> int:  # noqa: PLR0915
    if args.scenario in GUI_SCENARIOS and args.regions is None:
        raise ValueError(f'{args.scenario} requires --regions')

    load_start = perf_counter()
    mesh = AtlasMesh.from_pack(args.mesh_pack)
    mesh_loaded = perf_counter()
    catalog = open_region_catalog(args.regions) if args.scenario in GUI_SCENARIOS else None
    catalog_loaded = perf_counter()

    interaction = args.scenario in INTERACTION_SCENARIOS
    initial_explode = 0.5 if args.scenario == 'explode_static' else 0.0
    viewer_start = perf_counter()
    viewer_class = _BenchmarkAtlasViewer if args.scenario in GUI_PROFILE_SCENARIOS else AtlasViewer
    viewer_kwargs = {}
    if args.scenario in GUI_PROFILE_SCENARIOS:
        viewer_kwargs['gui_profile'] = GUI_PROFILE_SCENARIOS[args.scenario]
    if args.scenario == 'gui_tree_small':
        viewer_kwargs['tree_root_acronym'] = 'VISp'
    viewer = viewer_class(
        mesh,
        catalog=catalog,
        width=args.width,
        height=args.height,
        enable_interaction=interaction,
        explode=initial_explode,
        **viewer_kwargs,
    )
    viewer_created = perf_counter()

    callback_errors: list[str] = []
    mutation_seconds: list[float] = []
    measuring = [False]
    callback_index = [0]
    query_results = {'queued': 0, 'resolved': 0, 'hits': 0}
    pointer_results = {'emitted': 0, 'hover_hit_frames': 0, 'hover_changes': 0}
    previous_hover = [()]
    measured_request_start = [sys.maxsize]
    region_id = next(
        (int(value) for value in np.unique(mesh.mapping_ids('allen')) if int(value) != 0),
        0,
    )

    def on_frame(_view, _user_data) -> None:  # noqa: PLR0912
        index = callback_index[0]
        callback_index[0] += 1
        started = perf_counter()
        try:
            if args.scenario == 'rotation':
                viewer.set_camera_angles(
                    (
                        -0.35 + 0.18 * np.sin(index * 0.031),
                        0.25 + 0.22 * np.cos(index * 0.023),
                        0.12,
                    )
                )
            elif args.scenario == 'explode_animated':
                viewer.set_explode(0.5 + 0.5 * np.sin(index * 0.047))
            elif args.scenario == 'selection_update':
                viewer.set_selected_region_ids((region_id,) if index % 2 else ())
            elif args.scenario == 'hover_emphasis_update':
                viewer._set_hovered_region_ids((region_id,) if index % 2 else ())
            elif args.scenario == 'face_query':
                result = dvz.DvzQueryResult()
                while dvz.dvz_scene_poll_query(viewer.scene, ctypes.byref(result)):
                    if result.request_id >= measured_request_start[0]:
                        query_results['resolved'] += 1
                        query_results['hits'] += int(bool(result.hit))
                request = dvz.dvz_query_request()
                request.request_id = index + 1
                request.target = dvz.DVZ_SCENE_TARGET_FACE
                viewer._check(
                    dvz.dvz_panel_query_px(
                        viewer.panel,
                        args.width // 2,
                        args.height // 2,
                        ctypes.byref(request),
                    ),
                    'benchmark face query',
                )
                if measuring[0]:
                    query_results['queued'] += 1
            elif args.scenario in ('pointer_hover', 'pointer_hover_burst'):
                hover = viewer._mesh_hovered_region_ids()
                if measuring[0]:
                    pointer_results['hover_hit_frames'] += int(bool(hover))
                    pointer_results['hover_changes'] += int(hover != previous_hover[0])
                previous_hover[0] = hover
                events_per_frame = 4 if args.scenario == 'pointer_hover_burst' else 1
                for event_index in range(events_per_frame):
                    phase = (index + event_index / events_per_frame) * 0.071
                    x = args.width * (0.5 + 0.22 * np.sin(phase))
                    y = args.height * (0.5 + 0.18 * np.sin(phase * 1.37))
                    viewer._check(
                        dvz.dvz_view_emit_pointer(
                            viewer.view,
                            dvz.DVZ_POINTER_EVENT_MOVE,
                            x,
                            y,
                            args.width,
                            args.height,
                            dvz.DVZ_POINTER_BUTTON_NONE,
                            dvz.DVZ_KEY_MODIFIER_NONE,
                        ),
                        'benchmark pointer move',
                    )
                    if measuring[0]:
                        pointer_results['emitted'] += 1
        except Exception as error:  # ctypes callbacks cannot propagate exceptions safely
            callback_errors.append(f'{type(error).__name__}: {error}')
        finally:
            if measuring[0]:
                mutation_seconds.append(perf_counter() - started)

    try:
        view_start = perf_counter()
        viewer._create_view(offscreen=False, title=f'3-D benchmark: {args.scenario}')
        viewer_created_view = perf_counter()
        if args.scenario == 'gui_viewport_empty':
            viewer.use_empty_benchmark_viewport()
        if args.scenario in ('pointer_hover', 'pointer_hover_burst'):
            viewer._check(
                dvz.dvz_view_emit_resize(
                    viewer.view,
                    args.width,
                    args.height,
                    args.width,
                    args.height,
                    1.0,
                    1.0,
                ),
                'benchmark pointer viewport size',
            )
        viewer._check(
            dvz.dvz_view_set_frame_callback(viewer.view, on_frame, None),
            'benchmark frame callback',
        )

        os.environ['DVZ_APP_FRAME_TIMING'] = '0'
        dvz.dvz_app_run(viewer.app, args.warmup)
        warmed = perf_counter()
        mutation_seconds.clear()
        measured_request_start[0] = callback_index[0] + 1
        measuring[0] = True
        os.environ['DVZ_APP_FRAME_TIMING'] = '1'
        measured_start = perf_counter()
        dvz.dvz_app_run(viewer.app, args.frames)
        measured_end = perf_counter()
        measuring[0] = False
        if args.scenario == 'face_query':
            viewer._check(
                dvz.dvz_view_set_frame_callback(viewer.view, None, None),
                'benchmark frame callback clear',
            )
            os.environ['DVZ_APP_FRAME_TIMING'] = '0'
            dvz.dvz_app_run(viewer.app, 1)
            result = dvz.DvzQueryResult()
            while dvz.dvz_scene_poll_query(viewer.scene, ctypes.byref(result)):
                if result.request_id >= measured_request_start[0]:
                    query_results['resolved'] += 1
                    query_results['hits'] += int(bool(result.hit))
        if callback_errors:
            raise RuntimeError(callback_errors[0])

        root = Path(__file__).resolve().parents[1]
        record = {
            'schema_version': 1,
            'scenario': args.scenario,
            'repeat': args.repeat_index,
            'mode': 'window',
            'viewport': {'width': args.width, 'height': args.height},
            'configuration': {
                'mapping': 'allen',
                'catalog': catalog is not None,
                'interaction': interaction,
                'gui_profile': GUI_PROFILE_SCENARIOS.get(args.scenario),
                'tree_root_acronym': 'VISp' if args.scenario == 'gui_tree_small' else 'grey',
                'initial_explode': initial_explode,
                'mutation_upload_bytes_per_frame': (
                    mesh.positions.nbytes
                    if args.scenario == 'explode_animated'
                    else len(mesh.positions) * 4
                    if args.scenario in ('hover_emphasis_update', 'selection_update')
                    else 0
                ),
                'requested_present_mode': os.environ.get('DVZ_PRESENT_MODE'),
            },
            'asset': {
                'mesh_pack': str(args.mesh_pack.resolve()),
                'vertices': len(mesh.positions),
                'triangles': len(mesh.indices) // 3,
                'components': int(len(np.unique(mesh.component_ids))),
                'presentations': len(mesh.presentations),
            },
            'environment': {
                'platform': platform.platform(),
                'python': platform.python_version(),
                'numpy': np.__version__,
                'datoviz_module': str(Path(dvz.__file__).resolve()),
                'gpu': _gpu_description(),
                'git': {
                    'ibl_datoviz': _git_revision(root),
                    'datoviz': _git_revision(root.parents[1] / 'Viz' / 'datoviz'),
                },
            },
            'timing': {
                'mesh_load_seconds': mesh_loaded - load_start,
                'catalog_load_seconds': catalog_loaded - mesh_loaded,
                'viewer_create_seconds': viewer_created - viewer_start,
                'view_create_seconds': viewer_created_view - view_start,
                'warmup_seconds': warmed - viewer_created_view,
                'warmup_frames': args.warmup,
                'measured_wall_seconds': measured_end - measured_start,
                'measured_frames': args.frames,
                'mutation': _distribution(mutation_seconds),
            },
            'memory': {
                'maximum_resident_set_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            },
            'queries': query_results if args.scenario == 'face_query' else None,
            'pointer': (
                pointer_results
                if args.scenario in ('pointer_hover', 'pointer_hover_burst')
                else None
            ),
        }
        print(f'{RESULT_PREFIX} {json.dumps(record, sort_keys=True)}')
    finally:
        viewer.close()
    return 0


def _run_child(args: argparse.Namespace, scenario: str, repeat: int) -> dict:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        str(args.mesh_pack),
        '--worker',
        '--scenario',
        scenario,
        '--repeat-index',
        str(repeat),
        '--warmup',
        str(args.warmup),
        '--frames',
        str(args.frames),
        '--width',
        str(args.width),
        '--height',
        str(args.height),
    ]
    if args.regions is not None:
        command.extend(('--regions', str(args.regions)))
    environment = os.environ.copy()
    environment.update(
        {
            'DVZ_APP_SCHEDULE': 'continuous',
            'DVZ_FPS_CAP': '0',
            'DVZ_PRESENT_MODE': 'immediate',
        }
    )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    timing = next(
        (
            parsed
            for line in completed.stdout.splitlines()
            if (parsed := _parse_key_values(line, TIMING_PREFIX)) is not None
        ),
        None,
    )
    latency = next(
        (
            parsed
            for line in completed.stdout.splitlines()
            if (parsed := _parse_key_values(line, LATENCY_PREFIX)) is not None
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
            f'benchmark child {scenario}/{repeat} produced no timing record\n'
            f'stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}'
        )
    if int(timing['frames']) != args.frames:
        raise RuntimeError(
            f'benchmark child {scenario}/{repeat} rendered {timing["frames"]} of '
            f'{args.frames} requested frames; the window may have been closed'
        )
    payload['datoviz_frame_timing_ms'] = timing
    payload['datoviz_interaction_latency_ms'] = latency
    run_ms = float(timing['run_ms'])
    payload['observed_fps'] = 1000.0 / run_ms if run_ms > 0 else None
    return payload


def _scenario_summary(runs: Sequence[dict]) -> dict[str, float | int]:
    """Aggregate repeat medians without hiding individual child measurements."""
    fields = (
        'run_ms',
        'frame_ms',
        'p50',
        'p95',
        'p99',
        'canvas',
        'prepare',
        'gui_frame',
        'gui_viewport',
        'prepare_other',
        'scene_total',
        'execute',
        'post',
        'query',
        'callback',
        'canvas_overhead',
    )
    summary: dict[str, float | int] = {'repeats': len(runs)}
    for field in fields:
        values = [
            float(run['datoviz_frame_timing_ms'][field])
            for run in runs
            if field in run['datoviz_frame_timing_ms']
        ]
        if values:
            summary[f'{field}_median'] = float(np.median(values))
    query_counts = [
        int(run['datoviz_frame_timing_ms']['query_count'])
        for run in runs
        if 'query_count' in run['datoviz_frame_timing_ms']
    ]
    if query_counts:
        summary['query_count_median'] = int(np.median(query_counts))
    latency_fields = (
        'samples',
        'input_to_render_start_p50_ms',
        'input_to_render_start_p95_ms',
        'input_to_render_start_p99_ms',
        'input_to_submit_p50_ms',
        'input_to_submit_p95_ms',
        'input_to_submit_p99_ms',
    )
    for field in latency_fields:
        values = [
            float(run['datoviz_interaction_latency_ms'][field])
            for run in runs
            if run.get('datoviz_interaction_latency_ms') is not None
            and field in run['datoviz_interaction_latency_ms']
        ]
        if values:
            summary[f'interaction_{field}_median'] = float(np.median(values))
    pointer_fields = ('emitted', 'hover_hit_frames', 'hover_changes')
    for field in pointer_fields:
        values = [int(run['pointer'][field]) for run in runs if run.get('pointer') is not None]
        if values:
            summary[f'pointer_{field}_median'] = int(np.median(values))
    summary['observed_fps_median'] = float(np.median([run['observed_fps'] for run in runs]))
    run_values = [float(run['datoviz_frame_timing_ms']['run_ms']) for run in runs]
    fps_values = [float(run['observed_fps']) for run in runs]
    summary['run_ms_minimum'] = min(run_values)
    summary['run_ms_maximum'] = max(run_values)
    summary['observed_fps_minimum'] = min(fps_values)
    summary['observed_fps_maximum'] = max(fps_values)
    summary['maximum_resident_set_kib_median'] = int(
        np.median([run['memory']['maximum_resident_set_kib'] for run in runs])
    )
    mutation = [run['timing']['mutation'].get('median_ms') for run in runs]
    summary['mutation_median_ms'] = float(np.median([value for value in mutation if value]))
    return summary


def _parent(args: argparse.Namespace) -> int:
    if any(scenario in GUI_SCENARIOS for scenario in args.scenarios) and args.regions is None:
        raise ValueError('GUI scenarios require --regions')
    runs = []
    jobs = [(scenario, repeat) for scenario in args.scenarios for repeat in range(args.repeats)]
    random.Random(args.seed).shuffle(jobs)
    for scenario, repeat in jobs:
        print(
            f'benchmarking {scenario} ({repeat + 1}/{args.repeats})',
            file=sys.stderr,
            flush=True,
        )
        runs.append(_run_child(args, scenario, repeat))
    report = {
        'schema_version': 1,
        'benchmark': 'ibl-datoviz-3d-feature-ladder',
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
    parser.add_argument('mesh_pack', type=Path)
    parser.add_argument('--regions', type=Path)
    parser.add_argument('--scenarios', nargs='+', choices=SCENARIOS, default=list(SCENARIOS))
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--seed', type=int, default=0, help='scenario-order randomization seed')
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
    """Run one worker or aggregate the requested fresh-process benchmark suite."""
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
