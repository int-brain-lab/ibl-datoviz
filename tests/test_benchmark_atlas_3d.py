from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / 'tools' / 'benchmark_atlas_3d.py'
SPEC = importlib.util.spec_from_file_location('benchmark_atlas_3d', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


def test_parse_datoviz_timing_record():
    parsed = BENCHMARK._parse_key_values(
        'app_frame_timing: view=0 frames=120 run_ms=2.5 p95=3.75',
        BENCHMARK.TIMING_PREFIX,
    )
    assert parsed == {'view': 0, 'frames': 120, 'run_ms': 2.5, 'p95': 3.75}
    assert BENCHMARK._parse_key_values('unrelated output', BENCHMARK.TIMING_PREFIX) is None


def test_distribution_uses_milliseconds():
    summary = BENCHMARK._distribution([0.001, 0.002, 0.003])
    assert summary['mean_ms'] == pytest.approx(2.0)
    assert summary['median_ms'] == pytest.approx(2.0)
    assert summary['minimum_ms'] == pytest.approx(1.0)
    assert summary['maximum_ms'] == pytest.approx(3.0)


def test_scenario_summary_preserves_repeat_count():
    runs = [
        {
            'observed_fps': fps,
            'datoviz_frame_timing_ms': {
                'run_ms': run,
                'frame_ms': 2,
                'p50': 2,
                'p95': 3,
                'p99': 4,
                'canvas': 1.5,
                'prepare': 0.1,
                'gui_frame': 0.02,
                'gui_viewport': 0.03,
                'prepare_other': 0.05,
                'scene_total': 0.2,
                'execute': 0.3,
                'post': 0.4,
                'query': 0.35,
                'query_count': 2,
                'callback': 0.25,
                'canvas_overhead': 0.5,
            },
            'memory': {'maximum_resident_set_kib': 100},
            'timing': {'mutation': {'median_ms': 0.2}},
        }
        for run, fps in ((4, 250), (5, 200), (6, 166.666))
    ]
    summary = BENCHMARK._scenario_summary(runs)
    assert summary['repeats'] == 3
    assert summary['run_ms_median'] == pytest.approx(5)
    assert summary['observed_fps_median'] == pytest.approx(200)
    assert summary['gui_viewport_median'] == pytest.approx(0.03)
    assert summary['query_median'] == pytest.approx(0.35)
    assert summary['query_count_median'] == 2
