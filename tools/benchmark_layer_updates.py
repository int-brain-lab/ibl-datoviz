#!/usr/bin/env python3
"""Measure CPU calls for synthetic scientific-layer updates on verified anatomy.

No frame loop or GPU completion is timed. Synthetic observations are benchmark
annotations, never a substitute for recordings or atlas scientific coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter

import numpy as np

from ibl_anatomy import bundled_asset_set, verify_materialized_asset_set
from ibl_datoviz import AtlasViewer, Channels, Paths, Points, Recording, SourceKey, Trajectory

GLYPHS = ('point', 'sphere', 'path')
OPERATIONS = ('visibility', 'color', 'size', 'selection')
NATIVE_CALLS = ('dvz_point', 'dvz_sphere', 'dvz_path', 'dvz_visual_destroy')


class NativeObserver:
    """Delegate native calls and count successful allocations and destroy attempts."""

    def __init__(self, native):
        self.native = native
        self.calls = Counter()
        self.created = Counter()

    def __getattr__(self, name):
        """Instrument allocation boundaries while forwarding other attributes unchanged."""
        original = getattr(self.native, name)
        if name not in NATIVE_CALLS:
            return original

        def observed(*args, **kwargs):
            self.calls[name] += 1
            result = original(*args, **kwargs)
            if name != 'dvz_visual_destroy' and result:
                self.created[name] += 1
            return result

        return observed

    def snapshot(self):
        """Return independent counts without retaining native object pointers."""
        return dict(self.calls), dict(self.created)


def parse_args(argv=None):
    """Require explicit anatomy and bounded, configurable benchmark populations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='verified bundled D070 atlas asset root')
    parser.add_argument('--sizes', nargs='+', type=int, default=[100])
    parser.add_argument('--glyphs', nargs='+', choices=GLYPHS, default=['point', 'sphere'])
    parser.add_argument('--iterations', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=4)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--json', type=Path, dest='json_path')
    args = parser.parse_args(argv)
    if args.iterations < 2 or args.warmup < 0 or any(size < 1 for size in args.sizes):
        parser.error('iterations must be >= 2, warmup >= 0, and all sizes positive')
    if len(set(args.sizes)) != len(args.sizes) or len(set(args.glyphs)) != len(args.glyphs):
        parser.error('sizes and glyphs must be unique')
    if args.seed < 0:
        parser.error('seed must be nonnegative')
    return args


def _delta(after, before):
    return {name: after.get(name, 0) - before.get(name, 0) for name in NATIVE_CALLS}


def measure(operation, observer, *, iterations, warmup, clock=perf_counter):
    """Time alternating changed states; exclude warmup and count measured native calls."""
    for index in range(warmup):
        operation(index % 2)
    before_calls, before_created = observer.snapshot()
    seconds = []
    for index in range(warmup, warmup + iterations):
        started = clock()
        operation(index % 2)
        seconds.append(clock() - started)
    after_calls, after_created = observer.snapshot()
    milliseconds = np.asarray(seconds) * 1000
    return {
        'samples': iterations,
        'warmup_calls': warmup,
        'median_ms': float(np.median(milliseconds)),
        'p95_ms': float(np.percentile(milliseconds, 95)),
        'minimum_ms': float(milliseconds.min()),
        'maximum_ms': float(milliseconds.max()),
        'native_call_attempts': _delta(after_calls, before_calls),
        'successful_visual_allocations': _delta(after_created, before_created),
    }


def _positions(mesh, count, seed):
    generator = np.random.default_rng(seed)
    lower = mesh.positions_um.min(axis=0)
    upper = mesh.positions_um.max(axis=0)
    return generator.uniform(lower, upper, (count, 3))


def _layer(viewer, glyph, positions):
    provenance = {'kind': 'synthetic benchmark annotations', 'scientific_data': False}
    ids = tuple(range(len(positions)))
    if glyph == 'path':
        # Each row is one short independent two-vertex path, not a traced insertion.
        offset = max(float(np.ptp(positions, axis=0).max()), 1.0) * 0.001
        lines = tuple(np.stack((position, position + (0, 0, offset))) for position in positions)
        return viewer.add_paths(
            Paths(ids, lines, viewer.frame, provenance), name='Synthetic paths'
        )
    return viewer.add_points(
        Points(ids, positions, viewer.frame, provenance), name='Synthetic annotations', glyph=glyph
    )


def layer_operations(viewer, layer, glyph):
    """Use only public mutations and alternate two concrete authored states."""
    size = {'point': layer.set_size_px, 'sphere': layer.set_radius_um, 'path': layer.set_width_px}
    refs = ((layer.observation(layer.payload.ids[0]),), ())
    return {
        'visibility': lambda state: layer.set_visible(bool(state)),
        'color': lambda state: layer.set_color(('#ff8844', '#4488ff')[state]),
        'size': lambda state: size[glyph]((4.0, 8.0)[state]),
        'selection': lambda state: viewer.selection.set_observations(refs[state]),
    }


def benchmark_population(viewer, observer, glyph, positions, *, iterations, warmup):
    """Measure one layer, then remove it before the next population is attached."""
    try:
        layer = _layer(viewer, glyph, positions)
    except RuntimeError as error:
        raise RuntimeError(
            f'layer benchmark attachment failed: glyph={glyph}, '
            f'population={len(positions)}: {error}'
        ) from error
    rows = []
    try:
        operations = layer_operations(viewer, layer, glyph)
        for name in OPERATIONS:
            # Leave full visibility for color/size/selection measurements.
            layer.set_visible(True)
            viewer.selection.clear_observations()
            row = {
                'glyph': glyph,
                'population': len(positions),
                'operation': name,
                'positions_sha256': hashlib.sha256(positions.tobytes()).hexdigest(),
            }
            try:
                row.update(
                    measure(operations[name], observer, iterations=iterations, warmup=warmup)
                )
            except RuntimeError as error:
                raise RuntimeError(
                    f'layer benchmark update failed: glyph={glyph}, '
                    f'population={len(positions)}, operation={name}: {error}'
                ) from error
            rows.append(row)
    finally:
        viewer.remove_layer(layer)
    return rows


def benchmark_group(viewer, observer, positions, *, iterations, warmup):
    """Measure a synthetic recording mask over N sphere rows plus one path."""
    provenance = {'kind': 'synthetic benchmark grouping', 'scientific_data': False}
    digest = hashlib.sha256(positions.tobytes()).hexdigest()
    source = SourceKey('benchmark', 'synthetic-annotations', '1', digest)
    path = np.stack((positions[0], positions[0] + (0, 0, 1)))
    recording = Recording(
        source,
        'synthetic-group',
        'synthetic-session',
        channels=Channels(tuple(range(len(positions))), positions, viewer.frame, provenance),
        path=Trajectory(positions_um=path, frame=viewer.frame, provenance=provenance),
        provenance=provenance,
    )
    group = viewer.add_recording(recording, name='Synthetic benchmark group')
    try:
        result = measure(
            lambda state: group.set_visible(bool(state)),
            observer,
            iterations=iterations,
            warmup=warmup,
        )
        return {
            'glyph': 'recording-group',
            'population': len(positions),
            'operation': 'group_visibility',
            'geometry': {'sphere_observations': len(positions), 'two_vertex_paths': 1},
            'positions_sha256': digest,
            **result,
        }
    finally:
        viewer.remove_recording(group)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _module_identity(name):
    module = importlib.import_module(name)
    path = Path(module.__file__).resolve()
    result = {
        'module_path': str(path),
        'version': getattr(module, '__version__', None),
        'git_revision': None,
        'git_dirty': None,
    }
    try:
        checkout = subprocess.run(
            ['git', '-C', str(path.parent), 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=True,
        )
        if Path(checkout.stdout.strip()).resolve() != path.parent.parent:
            raise ValueError('package is nested inside another checkout')
        revision = subprocess.run(
            ['git', '-C', str(path.parent), 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
        )
        status = subprocess.run(
            ['git', '-C', str(path.parent), 'status', '--porcelain', '--untracked-files=no'],
            capture_output=True,
            text=True,
            check=True,
        )
        result.update(git_revision=revision.stdout.strip(), git_dirty=bool(status.stdout))
    except (OSError, ValueError, subprocess.CalledProcessError):
        result.update(git_revision=None, git_dirty=None)
    digest = hashlib.sha256()
    for source in sorted(path.parent.rglob('*.py')):
        digest.update(str(source.relative_to(path.parent)).encode())
        digest.update(source.read_bytes())
    result['python_sources_sha256'] = digest.hexdigest()
    return result


def runtime_identity():
    """Record loaded package paths/source identities and the actual native binary."""
    native = importlib.import_module('datoviz._ctypes')
    library = Path(native.dvz._name).expanduser().resolve()
    return {
        'python': sys.version,
        'numpy_version': np.__version__,
        'platform': platform.platform(),
        'packages': {name: _module_identity(name) for name in ('ibl_datoviz', 'datoviz')},
        'native_library': {
            'path': str(library),
            'sha256': _sha256(library) if library.is_file() else None,
        },
        'benchmark_script_sha256': _sha256(Path(__file__)),
    }


def run(args):
    """Verify requested anatomy, then measure synthetic public API update calls."""
    import datoviz as dvz  # noqa: PLC0415 - defer native runtime selection to execution.

    asset_set = bundled_asset_set()
    assets = verify_materialized_asset_set(asset_set, args.asset_root)
    observer = NativeObserver(dvz)
    rows = []
    for count in args.sizes:
        # Native scene storage can retain historical visual IDs after destruction.
        # Isolate each glyph/population, and the group, in a fresh scene. Setup
        # and scene destruction remain outside every measured public call.
        for glyph in args.glyphs:
            with AtlasViewer.from_assets(
                assets, datoviz=observer, enable_interaction=False
            ) as viewer:
                positions = _positions(viewer.mesh_data, count, args.seed)
                rows.extend(
                    benchmark_population(
                        viewer,
                        observer,
                        glyph,
                        positions,
                        iterations=args.iterations,
                        warmup=args.warmup,
                    )
                )
        with AtlasViewer.from_assets(assets, datoviz=observer, enable_interaction=False) as viewer:
            positions = _positions(viewer.mesh_data, count, args.seed)
            rows.append(
                benchmark_group(
                    viewer,
                    observer,
                    positions,
                    iterations=args.iterations,
                    warmup=args.warmup,
                )
            )
    identity = runtime_identity()

    return {
        'schema_version': 1,
        'measurement': {
            'scope': 'owner-thread CPU public API call duration',
            'units': 'milliseconds',
            'clock': 'perf_counter',
            'gpu_timing': False,
            'render_loop': False,
            'end_to_end_latency': False,
            'native_observer_overhead_included': True,
            'scene_isolation': 'fresh scene per glyph/population and recording-group case',
            'scene_setup_and_teardown_timed': False,
            'p95_method': 'NumPy percentile, linear interpolation',
            'allocation_counts': 'successful visual creation; destroy counts are call attempts',
        },
        'workload': {
            'kind': 'synthetic annotations and synthetic recording group',
            'scientific_data': False,
            'seed': args.seed,
            'sizes': args.sizes,
            'glyphs': args.glyphs,
            'iterations': args.iterations,
            'warmup': args.warmup,
            'coordinates': 'uniform samples in verified atlas mesh bounds, world micrometres',
            'path_geometry': 'one independent two-vertex path per annotation',
        },
        'anatomy': {
            'asset_root': str(args.asset_root.resolve()),
            'asset_set_id': asset_set.asset_set_id,
            'expected_geometry_sha256': asset_set.expected_geometry_sha256,
            'region_catalog_sha256': asset_set.region_catalog.sha256,
        },
        'identity': identity,
        'results': rows,
    }


def main(argv=None):
    """Print the bounded benchmark report and optionally save it as JSON."""
    args = parse_args(argv)
    report = run(args)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    print(encoded)
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(encoded + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
