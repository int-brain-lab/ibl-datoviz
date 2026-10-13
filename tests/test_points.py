import numpy as np
import pytest

from ibl_datoviz.points import PointCollection


def test_points_own_inputs_and_preserve_world_coordinates():
    positions = np.arange(18, dtype=np.float32).reshape(6, 3)[::2]
    colors = np.full((3, 4), 128, np.uint8)
    sizes = np.arange(1, 4, dtype=np.float32)
    points = PointCollection.from_arrays(positions, colors, sizes_px=sizes)
    for source, retained in zip(
        (positions, colors, sizes),
        (points.positions_um, points.colors, points.sizes_px),
        strict=True,
    ):
        assert source.flags.writeable
        assert retained.flags.owndata and retained.flags.c_contiguous
        assert not retained.flags.writeable and not np.shares_memory(source, retained)
    positions[:] = 100
    colors[:] = 0
    sizes[:] = 9
    assert points.positions_um[0, 0] == 0
    assert points.colors[0, 0] == 128
    assert points.sizes_px.tolist() == [1, 2, 3]


def test_empty_points_and_rgb_expansion():
    points = PointCollection.from_arrays(np.empty((0, 3)), np.empty((0, 4), np.uint8))
    assert len(points) == 0
    assert points.sizes_px.shape == (0,)
    points = PointCollection.from_arrays([[1, 2, 3]], [[10, 20, 30]], sizes_px=2)
    assert points.colors.tolist() == [[10, 20, 30, 255]]


@pytest.mark.parametrize('sizes', [0, -1, np.nan, np.inf, [1, 2]])
def test_invalid_sizes_rejected(sizes):
    with pytest.raises(ValueError, match='sizes'):
        PointCollection.from_arrays([[0, 0, 0]], [[0, 0, 0]], sizes_px=sizes)


@pytest.mark.parametrize('colors', [[[256, 0, 0]], [[-1, 0, 0]], [[0.0, 1.0, 2.0]], [[1, 2]]])
def test_invalid_colors_rejected_before_uint8_conversion(colors):
    with pytest.raises(ValueError, match='RGB'):
        PointCollection.from_arrays([[0, 0, 0]], colors)


def test_scalar_lut_matches_clipping_rounding_nan_and_float64_normalization():
    palette = np.repeat(np.arange(256, dtype=np.uint8)[:, None], 3, axis=1)
    values = [-1, 0, 0.5, 1, 2, np.nan]
    points = PointCollection.from_scalars(
        np.zeros((6, 3)), values, palette=palette, value_range=(0, 1)
    )
    assert points.colors[:, 0].tolist() == [0, 0, 128, 255, 255, 0]
    assert points.colors[:, 3].tolist() == [255, 255, 255, 255, 255, 0]
    # JavaScript promotes stored float32 artifacts before normalization.
    values = np.array([0.3], np.float32)
    points = PointCollection.from_scalars(
        [[0, 0, 0]], values, palette=palette, value_range=(0, 0.6 + 1e-7)
    )
    expected = int(np.floor(float(values[0]) / (0.6 + 1e-7) * 255 + 0.5))
    assert points.colors[0, 0] == expected


def test_scalar_palette_interpolates_rgb_channels_before_rounding():
    palette = np.zeros((256, 3), np.uint8)
    palette[1] = [1, 3, 5]
    result = PointCollection.from_scalars(
        [[0, 0, 0]], [0.5 / 255], palette=palette, value_range=(0, 1)
    )
    assert result.colors[0].tolist() == [1, 2, 3, 255]


@pytest.mark.parametrize('bounds', [(1, 1), (2, 1), (0, np.inf)])
def test_invalid_scalar_range_rejected(bounds):
    with pytest.raises(ValueError, match='range'):
        PointCollection.from_scalars(
            [[0, 0, 0]], [1], palette=np.zeros((256, 3), np.uint8), value_range=bounds
        )
