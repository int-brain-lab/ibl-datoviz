"""Validate diagnostic geometry, without treating the pinned image defect as desired."""

import numpy as np
import pytest

from tools.diagnose_endpoint_depth import extruded_path_depth, project, projected_line_depth


@pytest.mark.parametrize('depths', [(0.2, 0.8), (0.8, 0.2), (0.5, 0.5)])
def test_original_projected_line_preserves_endpoint_depths(depths):
    length = 93.5
    actual = projected_line_depth(np.array([0, length]), length, *depths)
    np.testing.assert_allclose(actual, depths, rtol=0, atol=1e-15)
    # Reversing the same segment preserves depth at each screen position.
    distances = np.array([3.0, 25.0, 60.0])
    np.testing.assert_allclose(
        projected_line_depth(distances, length, *depths),
        projected_line_depth(length - distances, length, *depths[::-1]),
        rtol=0,
        atol=1e-15,
    )


@pytest.mark.parametrize('delta', [-0.001, 0.001])
def test_cap_depth_drift_measurement_matches_projected_geometry(delta):
    # This validates the diagnostic model, not acceptance of the native image.
    start, length, extension = 0.995, 100.0, 4.5
    end = start + delta
    extended = extruded_path_depth(np.array([0, length]), length, start, end, extension)
    drift = delta * extension / (length + 2 * extension)
    np.testing.assert_allclose(extended - [start, end], [drift, -drift], atol=1e-15)


def test_original_depth_correction_cannot_prioritize_a_flat_marker_disk():
    marker_depth = 0.995
    # The original endpoint is exact, but a genuinely nearer part of the path
    # remains nearer five screen pixels inside the marker footprint.
    assert projected_line_depth(0, 100, marker_depth, 0.994) == marker_depth
    assert projected_line_depth(5, 100, marker_depth, 0.994) < marker_depth
    assert projected_line_depth(5, 100, marker_depth, 0.996) > marker_depth


def test_diagnostic_camera_maps_center_and_clip_planes_to_device_depth():
    positions = np.array([[0, 0, 0], [0, 0, 3 - 0.01], [0, 0, 3 - 100]])
    original = positions.copy()
    pixels, depths = project(positions, np.eye(4), 256)
    np.testing.assert_allclose(pixels, np.full((3, 2), 128))
    np.testing.assert_allclose(depths[1:], [0, 1], atol=3e-14)
    assert 0 < depths[0] < 1
    np.testing.assert_array_equal(positions, original)
