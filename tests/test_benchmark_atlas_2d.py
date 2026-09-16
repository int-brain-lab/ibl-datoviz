from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).parents[1] / 'tools' / 'benchmark_atlas_2d.py'
SPEC = importlib.util.spec_from_file_location('benchmark_atlas_2d', MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


def test_parse_datoviz_timing_record():
    parsed = BENCHMARK._parse_key_values(
        'app_frame_timing: frames=120 run_ms=2.5 p95=3.75', BENCHMARK.TIMING_PREFIX
    )
    assert parsed == {'frames': 120, 'run_ms': 2.5, 'p95': 3.75}
    assert BENCHMARK._parse_key_values('unrelated', BENCHMARK.TIMING_PREFIX) is None


def test_slice_quad_preserves_aspect_and_extent():
    wide, texcoords = BENCHMARK._slice_quad((100, 200))
    tall, _ = BENCHMARK._slice_quad((200, 100))
    assert np.ptp(wide[:, 0]) == pytest.approx(1.88)
    assert np.ptp(wide[:, 1]) == pytest.approx(0.94)
    assert np.ptp(tall[:, 0]) == pytest.approx(0.94)
    assert np.ptp(tall[:, 1]) == pytest.approx(1.88)
    assert texcoords.shape == (4, 2)


def test_map_segments_uses_slice_quad_coordinates():
    positions, _ = BENCHMARK._slice_quad((100, 100))
    starts, ends = BENCHMARK._map_segments(
        np.array([[0.0, 0.0]], dtype=np.float32),
        np.array([[1.0, 1.0]], dtype=np.float32),
        positions,
    )
    assert np.allclose(starts[0, :2], positions[0, :2])
    assert np.allclose(ends[0, :2], positions[3, :2])
    assert starts[0, 2] == pytest.approx(0.02)
