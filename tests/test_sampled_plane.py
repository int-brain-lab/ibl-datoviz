import numpy as np
import pytest

from ibl_datoviz.sampled_plane import UV, SampledPlane


def test_plane_owns_world_corners_and_pixels_with_documented_orientation():
    corners = np.array([[-1, 4, 2], [-1, 4, -2], [1, 4, 2], [1, 4, -2]], np.float32)
    pixels = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)
    plane = SampledPlane.from_arrays(corners, pixels)
    np.testing.assert_array_equal(plane.corners_um, corners)
    np.testing.assert_array_equal(UV, [[0, 0], [0, 1], [1, 0], [1, 1]])
    for source, retained in ((corners, plane.corners_um), (pixels, plane.rgba)):
        assert source.flags.writeable and not retained.flags.writeable
        assert retained.flags.owndata and retained.flags.c_contiguous
        assert not np.shares_memory(source, retained)
    pixels[:] = 0
    corners[:] = 10
    assert plane.rgba[0, 0, 1] == 1
    assert plane.corners_um[0, 1] == 4


@pytest.mark.parametrize(
    'corners',
    [
        np.zeros((4, 3)),
        [[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 1]],
        [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 2, 0]],
        [[0, 0, np.nan]] * 4,
    ],
)
def test_bad_rectangle_rejected(corners):
    with pytest.raises(ValueError, match='plane'):
        SampledPlane.from_arrays(corners, np.zeros((2, 2, 4), np.uint8))


@pytest.mark.parametrize('shape', [(0, 2, 4), (2, 2, 3), (2, 2)])
def test_invalid_pixels_rejected(shape):
    with pytest.raises(ValueError, match='pixels'):
        SampledPlane.from_arrays(
            [[0, 1, 0], [0, 0, 0], [1, 1, 0], [1, 0, 0]], np.zeros(shape, np.uint8)
        )
