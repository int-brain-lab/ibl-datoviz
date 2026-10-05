import numpy as np
import pytest

from ibl_datoviz.presentation import region_presentation, scalar_colors
from ibl_datoviz.regions import AtlasRegionValues


@pytest.mark.parametrize(
    ('scheme', 'middle'), [('diverging', (247, 247, 247)), ('sequential', (45, 180, 170))]
)
def test_constant_scalars_use_palette_midpoint(scheme, middle):
    colors = scalar_colors(np.array([3, 3, np.nan]), None, scheme)
    np.testing.assert_array_equal(colors, [(*middle, 255), (*middle, 255), (110, 116, 126, 255)])
    assert colors.dtype == np.uint8
    assert colors.flags.c_contiguous


def test_all_nan_scalars_use_missing_gray():
    colors = scalar_colors(np.full(3, np.nan), None)
    np.testing.assert_array_equal(colors, np.tile((110, 116, 126, 255), (3, 1)))


def test_explicit_range_interpolates_and_clips():
    colors = scalar_colors(np.array([-2, 0, 1, 2, 4]), (0, 2))
    np.testing.assert_array_equal(
        colors,
        [
            (49, 116, 178, 255),
            (49, 116, 178, 255),
            (247, 247, 247, 255),
            (203, 45, 62, 255),
            (203, 45, 62, 255),
        ],
    )
    quarter = scalar_colors(np.array([0.5]), (0, 2), 'sequential')
    np.testing.assert_array_equal(quarter, [[66, 125, 175, 255]])


@pytest.mark.parametrize('values', [[np.inf], [-np.inf], [[1, 2]]])
def test_invalid_scalar_arrays_are_rejected(values):
    with pytest.raises(ValueError, match='one-dimensional.*infinities'):
        scalar_colors(np.array(values), None)


@pytest.mark.parametrize('limits', [(0, 0), (2, 1), (0, np.inf), (np.nan, 1), (0,), (0, 1, 2)])
def test_invalid_explicit_ranges_are_rejected(limits):
    with pytest.raises(ValueError, match='probe value range'):
        scalar_colors(np.array([1.0]), limits)


def test_invalid_color_scheme_is_rejected():
    with pytest.raises(ValueError, match='unknown probe color scheme'):
        scalar_colors(np.array([1.0]), None, 'unknown')


class MappingCatalog:
    def __init__(self, mapping):
        self.mapping = mapping

    def map_allen_ids(self, region_ids, mapping):
        if mapping != 'beryl':
            raise KeyError(mapping)
        return [self.mapping[int(region_id)] for region_id in region_ids]


def test_region_collisions_preserve_hemispheres_finite_means_and_total_weights():
    data = AtlasRegionValues.from_arrays(
        [-1, -2, -3, 1, 2, 3, 4, 5],
        [2, 8, np.nan, 4, 12, np.nan, 99, 100],
        weights=[1, 3, 20, 3, 1, 5, 1, 1],
    )
    catalog = MappingCatalog({-1: -10, -2: -10, -3: -10, 1: 10, 2: 10, 3: 20, 4: 0, 5: None})
    view = region_presentation(catalog, 'beryl', data, (0, 10), 'diverging', 0.5)
    np.testing.assert_array_equal(view.region_ids, [-10, 10, 20])
    np.testing.assert_array_equal(view.values, [6.5, 6, np.nan])
    np.testing.assert_array_equal(view.weights, [24, 4, 5])
    np.testing.assert_array_equal(view.colors[:, 3], [128, 128, 128])
    np.testing.assert_array_equal(view.colors[-1, :3], [110, 116, 126])
    assert view.region_ids.dtype == np.int64
    assert view.values.dtype == view.weights.dtype == np.float64


@pytest.mark.parametrize('opacity', [0, 1])
def test_region_opacity_endpoints(opacity):
    data = AtlasRegionValues.from_arrays([1], [3])
    view = region_presentation(MappingCatalog({1: 1}), 'beryl', data, None, 'sequential', opacity)
    np.testing.assert_array_equal(view.colors, [[45, 180, 170, 255 * opacity]])


@pytest.mark.parametrize('opacity', [-0.1, 1.1, np.nan, np.inf])
def test_invalid_opacity_is_rejected(opacity):
    data = AtlasRegionValues.from_arrays([1], [3])
    with pytest.raises(ValueError, match='region opacity'):
        region_presentation(MappingCatalog({1: 1}), 'beryl', data, None, 'diverging', opacity)


def test_omitted_regions_produce_empty_presentation():
    data = AtlasRegionValues.from_arrays([1, 2], [3, np.nan])
    view = region_presentation(
        MappingCatalog({1: 0, 2: None}), 'beryl', data, None, 'diverging', 1
    )
    assert view.region_ids.shape == view.values.shape == view.weights.shape == (0,)
    assert view.colors.shape == (0, 4)


def test_unknown_mapping_is_reported_as_value_error():
    data = AtlasRegionValues.from_arrays([1], [3])
    with pytest.raises(ValueError, match='unknown'):
        region_presentation(MappingCatalog({1: 1}), 'unknown', data, None, 'diverging', 1)
