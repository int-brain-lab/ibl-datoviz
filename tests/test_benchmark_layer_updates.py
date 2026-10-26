"""Measurement contracts for explicitly synthetic layer-update benchmarks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    'benchmark_layer_updates', Path(__file__).parents[1] / 'tools' / 'benchmark_layer_updates.py'
)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


@pytest.mark.parametrize(
    'options',
    [
        ['--sizes', '0'],
        ['--iterations', '1'],
        ['--warmup', '-1'],
        ['--seed', '-1'],
        ['--sizes', '10', '10'],
        ['--glyphs', 'point', 'point'],
    ],
)
def test_cli_rejects_unbounded_or_ambiguous_measurement_configuration(options):
    with pytest.raises(SystemExit):
        BENCHMARK.parse_args(['explicit-assets', *options])


def test_native_observer_distinguishes_failed_allocations_from_call_attempts():
    native = SimpleNamespace(dvz_point=lambda *_: None, dvz_path=lambda *_: 'path')
    observer = BENCHMARK.NativeObserver(native)
    assert observer.dvz_point(None, 0) is None
    assert observer.dvz_path(None, 0) == 'path'
    calls, created = observer.snapshot()
    assert calls == {'dvz_point': 1, 'dvz_path': 1}
    assert created == {'dvz_path': 1}


def test_measure_excludes_warmup_times_and_allocations_and_keeps_changed_state_order():
    observer = BENCHMARK.NativeObserver(SimpleNamespace(dvz_point=lambda *_: 'visual'))
    states = []

    def update(state):
        states.append(state)
        observer.dvz_point(None, 0)

    timestamps = iter((10, 10.001, 20, 20.003))
    result = BENCHMARK.measure(
        update, observer, iterations=2, warmup=3, clock=lambda: next(timestamps)
    )
    assert states == [0, 1, 0, 1, 0]
    assert result['samples'] == 2 and result['warmup_calls'] == 3
    assert result['median_ms'] == pytest.approx(2)
    assert result['p95_ms'] == pytest.approx(2.9)
    assert result['native_call_attempts']['dvz_point'] == 2
    assert result['successful_visual_allocations']['dvz_point'] == 2


def test_run_verifies_explicit_anatomy_before_benchmark_and_labels_measurement_limits(
    monkeypatch, tmp_path
):
    args = BENCHMARK.parse_args([str(tmp_path), '--sizes', '3', '--glyphs', 'point'])
    asset_set = SimpleNamespace(
        asset_set_id='verified-atlas',
        expected_geometry_sha256='a' * 64,
        region_catalog=SimpleNamespace(sha256='b' * 64),
    )
    verified = object()
    calls = []
    scenes = []
    population_scenes = []
    group_scenes = []

    class Viewer:
        mesh_data = SimpleNamespace(positions_um=np.array([[-1, -2, -3], [1, 2, 3]]))

        @classmethod
        def from_assets(cls, assets, **kwargs):
            assert assets is verified and not kwargs['enable_interaction']
            calls.append('viewer')
            viewer = cls()
            scenes.append(viewer)
            return viewer

        def __enter__(self):
            return self

        def __exit__(self, *_):
            calls.append('closed')

    def verify(actual, root):
        assert actual is asset_set and root == tmp_path
        calls.append('verified')
        return verified

    def population(viewer, observer, glyph, positions, **kwargs):
        population_scenes.append(viewer)
        assert glyph == 'point' and positions.shape == (3, 3)
        assert np.all(positions >= viewer.mesh_data.positions_um[0])
        assert np.all(positions <= viewer.mesh_data.positions_um[1])
        assert kwargs == {'iterations': 20, 'warmup': 4}
        return [{'operation': 'visibility'}]

    monkeypatch.setattr(BENCHMARK, 'bundled_asset_set', lambda: asset_set)
    monkeypatch.setattr(BENCHMARK, 'verify_materialized_asset_set', verify)
    monkeypatch.setattr(BENCHMARK, 'AtlasViewer', Viewer)
    monkeypatch.setattr(BENCHMARK, 'runtime_identity', lambda: {'native_library': 'explicit'})
    monkeypatch.setattr(BENCHMARK, 'benchmark_population', population)

    def group(viewer, *_args, **_kwargs):
        group_scenes.append(viewer)
        return {'group': True}

    monkeypatch.setattr(BENCHMARK, 'benchmark_group', group)
    report = BENCHMARK.run(args)
    assert calls == ['verified', 'viewer', 'closed', 'viewer', 'closed']
    assert len(scenes) == 2
    assert population_scenes == [scenes[0]] and group_scenes == [scenes[1]]
    assert scenes[0] is not scenes[1]
    assert not report['measurement']['scene_setup_and_teardown_timed']
    assert not report['measurement']['gpu_timing']
    assert not report['measurement']['render_loop']
    assert not report['measurement']['end_to_end_latency']
    assert report['workload']['scientific_data'] is False
    assert report['anatomy']['asset_root'] == str(tmp_path.resolve())
    assert report['anatomy']['expected_geometry_sha256'] == 'a' * 64
    assert report['identity'] == {'native_library': 'explicit'}
    assert len(report['results']) == 2
    json.dumps(report, allow_nan=False)


def test_invalid_anatomy_does_not_start_native_viewer(monkeypatch, tmp_path):
    def reject(*_args):
        raise ValueError('asset hash mismatch')

    monkeypatch.setattr(BENCHMARK, 'verify_materialized_asset_set', reject)
    monkeypatch.setattr(
        BENCHMARK,
        'AtlasViewer',
        SimpleNamespace(
            from_assets=lambda *_args, **_kwargs: pytest.fail(
                'viewer allocated before verification'
            )
        ),
    )
    with pytest.raises(ValueError, match='asset hash mismatch'):
        BENCHMARK.run(BENCHMARK.parse_args([str(tmp_path)]))


def test_cli_json_output_preserves_report_and_printed_values(monkeypatch, tmp_path, capsys):
    report = {'measurement': {'gpu_timing': False}, 'results': [{'median_ms': 1.25}]}
    monkeypatch.setattr(BENCHMARK, 'run', lambda _args: report)
    output = tmp_path / 'nested' / 'report.json'
    assert BENCHMARK.main([str(tmp_path), '--json', str(output)]) == 0
    assert json.loads(output.read_text()) == report
    assert json.loads(capsys.readouterr().out) == report


def test_population_failure_removes_owned_layer_and_propagates_error(monkeypatch):
    removed = []
    layer = SimpleNamespace(
        payload=SimpleNamespace(ids=(0,)),
        observation=lambda identity: identity,
        set_visible=lambda _: None,
        set_color=lambda _: None,
        set_size_px=lambda _: (_ for _ in ()).throw(RuntimeError('native size failure')),
        set_radius_um=lambda _: pytest.fail('point benchmark used physical sphere radius'),
        set_width_px=lambda _: pytest.fail('point benchmark used path width'),
    )
    viewer = SimpleNamespace(
        selection=SimpleNamespace(
            clear_observations=lambda: None, set_observations=lambda _: None
        ),
        remove_layer=removed.append,
    )
    monkeypatch.setattr(BENCHMARK, '_layer', lambda *_args: layer)
    with pytest.raises(RuntimeError, match='native size failure'):
        BENCHMARK.benchmark_population(
            viewer,
            BENCHMARK.NativeObserver(object()),
            'point',
            np.zeros((1, 3)),
            iterations=2,
            warmup=0,
        )
    assert removed == [layer]


@pytest.mark.parametrize('archived', [False, True])
def test_package_git_identity_does_not_inherit_enclosing_checkout(monkeypatch, tmp_path, archived):
    package_root = tmp_path / 'archive' if archived else tmp_path
    package = package_root / 'ibl_datoviz'
    package.mkdir(parents=True)
    module = package / '__init__.py'
    module.write_text('value = 1\n')
    monkeypatch.setattr(
        BENCHMARK.importlib,
        'import_module',
        lambda _name: SimpleNamespace(__file__=str(module), __version__='test'),
    )
    commands = []

    def git(command, **_kwargs):
        commands.append(command)
        if command[-1] == '--show-toplevel':
            return SimpleNamespace(stdout=str(tmp_path) + '\n')
        if archived:
            pytest.fail('archived source inherited enclosing repository revision or dirty state')
        return SimpleNamespace(stdout='a' * 40 + '\n' if command[-1] == 'HEAD' else '')

    monkeypatch.setattr(BENCHMARK.subprocess, 'run', git)
    identity = BENCHMARK._module_identity('ibl_datoviz')
    assert identity['git_revision'] == (None if archived else 'a' * 40)
    assert identity['git_dirty'] is (None if archived else False)
    assert len(commands) == (1 if archived else 3)
    assert len(identity['python_sources_sha256']) == 64
