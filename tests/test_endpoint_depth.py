"""Validate diagnostic geometry, without treating the pinned image defect as desired."""

import numpy as np
import pytest

from tools.diagnose_endpoint_depth import (
    assert_gap_pixels,
    candidate_selection,
    extruded_path_depth,
    gap_positions,
    project,
    projected_line_depth,
)


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


@pytest.mark.parametrize('missing', ['checkout', 'library', 'expected_revision'])
def test_candidate_mode_requires_all_explicit_identities(tmp_path, missing):
    arguments = dict(checkout=tmp_path, library=tmp_path / 'lib.so', expected_revision='a' * 40)
    arguments[missing] = None
    with pytest.raises(ValueError, match='requires --datoviz'):
        candidate_selection(**arguments)


def test_candidate_identity_rejects_abbreviated_revision_and_missing_library(tmp_path):
    with pytest.raises(ValueError, match='full 40-character'):
        candidate_selection(tmp_path, tmp_path / 'lib.so', 'abc123')
    with pytest.raises(ValueError, match='must already exist'):
        candidate_selection(tmp_path, tmp_path / 'lib.so', 'a' * 40)
    (tmp_path / 'datoviz').mkdir()
    (tmp_path / 'datoviz' / '__init__.py').touch()
    library = tmp_path / 'lib.so'
    library.touch()
    assert candidate_selection(tmp_path, library, 'A' * 40) == (tmp_path, library, 'a' * 40)


def test_reentry_geometry_has_a_later_segment_inside_start_marker():
    positions = gap_positions('reentry', 1)
    pixels, _ = project(positions, np.eye(4), 256)
    assert np.linalg.norm(pixels[1] - pixels[0]) > 30
    assert np.linalg.norm(pixels[2] - pixels[0]) < 15
    assert np.linalg.norm(pixels[-1] - pixels[0]) > 30
    assert positions.flags.owndata


@pytest.mark.parametrize(
    ('field', 'value', 'message'),
    [
        ('point_interior_pixels', 0, 'no marker reference'),
        ('white_path_pixels_inside_point', 1, 'crosses a marker'),
        ('white_path_pixels_outside_point', 0, 'erased the external path'),
        ('pink_pixels_after_nearer_mesh', 1, 'through nearer opaque mesh'),
        ('cyan_pixels_after_nearer_mesh', 0, 'does not cover every marker'),
        ('cyan_pixels_after_nearer_mesh', 499, 'does not cover every marker'),
    ],
)
def test_gap_assertions_reject_each_render_failure(field, value, message):
    case = dict(
        name='synthetic',
        geometry='line',
        point_interior_pixels=500,
        white_path_pixels_inside_point=0,
        white_path_pixels_outside_point=100,
        white_path_pixels_total=100,
        pink_pixels_after_nearer_mesh=0,
        cyan_pixels_after_nearer_mesh=500,
    )
    assert_gap_pixels(case)
    case[field] = value
    with pytest.raises(AssertionError, match=message):
        assert_gap_pixels(case)


def test_overlapping_endpoint_gaps_require_short_path_to_disappear():
    case = dict(
        name='short',
        geometry='short',
        point_interior_pixels=500,
        white_path_pixels_inside_point=0,
        white_path_pixels_outside_point=0,
        white_path_pixels_total=0,
        pink_pixels_after_nearer_mesh=0,
        cyan_pixels_after_nearer_mesh=500,
    )
    assert_gap_pixels(case)
    case['white_path_pixels_total'] = 1
    with pytest.raises(AssertionError, match='overlapping gaps'):
        assert_gap_pixels(case)
