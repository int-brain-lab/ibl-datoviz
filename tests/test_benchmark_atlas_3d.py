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
            'datoviz_interaction_latency_ms': {
                'samples': 120,
                'input_to_render_start_p50_ms': 0.4,
                'input_to_render_start_p95_ms': 0.8,
                'input_to_render_start_p99_ms': 1.0,
                'input_to_submit_p50_ms': 2.4,
                'input_to_submit_p95_ms': 2.8,
                'input_to_submit_p99_ms': 3.0,
            },
            'pointer': {'emitted': 120, 'hover_hit_frames': 80, 'hover_changes': 12},
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
    assert summary['interaction_samples_median'] == pytest.approx(120)
    assert summary['interaction_input_to_submit_p95_ms_median'] == pytest.approx(2.8)
    assert summary['pointer_emitted_median'] == 120
    assert summary['pointer_hover_changes_median'] == 12


def test_gui_decomposition_scenarios_are_profiled_without_interaction():
    assert set(BENCHMARK.GUI_PROFILE_SCENARIOS) == {
        'gui_empty',
        'gui_viewport_empty',
        'gui_viewport_surface',
        'gui_tree_small',
        'gui_tree_full',
    }
    assert set(BENCHMARK.GUI_PROFILE_SCENARIOS) <= BENCHMARK.GUI_SCENARIOS
    assert not (set(BENCHMARK.GUI_PROFILE_SCENARIOS) & BENCHMARK.INTERACTION_SCENARIOS)
    assert 'pointer_hover' in BENCHMARK.INTERACTION_SCENARIOS
    assert 'pointer_hover_burst' in BENCHMARK.INTERACTION_SCENARIOS
