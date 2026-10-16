"""Exact registered-source identity, coordinate transforms and bounded decoding."""

from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest

import ibl_anatomy
from ibl_datoviz import AtlasSliceSource
from ibl_datoviz.contour_source import projection_fraction_transform
from ibl_datoviz.navigator import SLICE_DISPLAY_AXES
from tests.test_atlas_slice_source import _Grid, _Intensity, _Projection, _Regions


@pytest.fixture
def source():
    intensity = _Intensity()
    intensity.clear_cache = lambda: None
    return AtlasSliceSource(
        intensity,
        {axis: _Projection(axis) for axis in ('ap', 'ml', 'dv')},
        _Regions(),
        section_cache_size=2,
    )


@pytest.fixture
def decoder(monkeypatch):
    calls = []

    def decode(section):
        calls.append(section.slice_index)
        ring = np.asarray([[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]], dtype=np.float64)
        return (
            SimpleNamespace(
                atlas_ids={'allen': 8}, components=(SimpleNamespace(outer=ring, holes=()),)
            ),
        )

    monkeypatch.setattr(ibl_anatomy, 'decode_registered_contours', decode, raising=False)
    return calls


@pytest.mark.parametrize('axis', ['ap', 'ml', 'dv'])
@pytest.mark.parametrize('signs', list(product((-1, 1), repeat=3)))
def test_svg_half_cell_edges_and_centers_match_world_increasing_image_fractions(axis, signs):
    matrix = np.array(_Grid.index_to_world_um_matrix, dtype=float).reshape(4, 4)
    for column, name in enumerate(_Grid.array_axes):
        world = _Grid.world_axes.index(name)
        matrix[world, column] = signs[column] * 10
    grid = SimpleNamespace(
        shape=_Grid.shape,
        array_axes=_Grid.array_axes,
        world_axes=_Grid.world_axes,
        index_to_world_um_matrix=tuple(matrix.ravel()),
    )
    projection = _Projection(axis)
    plane = np.zeros((4, 4))
    plane[3, 3] = 1
    plane[:3, 3] = matrix[:3, 3]
    for column, name in enumerate((axis, *SLICE_DISPLAY_AXES[axis])):
        plane[:3, column] = matrix[:3, _Grid.array_axes.index(name)]
    projection.plane_index_to_world_um = tuple(plane.ravel())
    transform = np.asarray(projection_fraction_transform(grid, axis, projection)).reshape(3, 3)
    width, height = projection.slice_shape
    for u, v in ((-0.5, -0.5), (width - 0.5, height - 0.5), (0, 0), (width - 1, height - 1)):
        actual = transform @ np.asarray([u, v, 1.0])
        expected = []
        for coordinate, size, name in zip(
            (u, v), (width, height), SLICE_DISPLAY_AXES[axis], strict=True
        ):
            fraction = (coordinate + 0.5) / size
            direction = plane[_Grid.world_axes.index(name), 1 + len(expected)]
            expected.append(fraction if direction > 0 else 1 - fraction)
        np.testing.assert_allclose(actual, (*expected, 1), atol=1e-12)
        np.testing.assert_allclose(np.linalg.inv(transform) @ actual, (u, v, 1), atol=1e-12)


def test_source_cache_reuses_exact_section_and_bounds_entry_count(source, decoder):
    first = source.contour_slice('ap', 0)
    assert first is source.contour_slice('ap', 0)
    assert decoder == [0]
    assert source.contour_cache_info() == (1, 80)
    source.contour_slice('ap', 1)
    source.contour_slice('ml', 0)
    assert source.contour_cache_info() == (2, 160)
    source.contour_slice('ap', 0)
    assert decoder == [0, 1, 0, 0]
    assert len(first.svg_to_fraction) == 9


def test_source_cache_byte_bound_and_oversized_entries_are_not_retained(source, decoder):
    source._contour_cache_limit = 120
    source.contour_slice('ap', 0)
    source.contour_slice('ap', 1)
    assert source.contour_cache_info() == (1, 80)
    source._contour_cache_limit = 79
    source.clear_cache()
    source.contour_slice('ap', 0)
    source.contour_slice('ap', 0)
    assert source.contour_cache_info() == (0, 0)
    assert decoder == [0, 1, 0, 0]


def test_clear_cache_releases_contours_and_keeps_the_intensity_lifecycle(
    source, decoder, monkeypatch
):
    cleared = []
    monkeypatch.setattr(source._pack, 'clear_cache', lambda: cleared.append(True), raising=False)
    source.contour_slice('ap', 0)
    source.clear_cache()
    assert cleared == [True]
    assert source.contour_cache_info() == (0, 0)


@pytest.mark.parametrize(
    ('axis', 'index', 'error'),
    [
        ('bad', 0, ValueError),
        ('ap', True, TypeError),
        ('ap', 1.5, TypeError),
        ('ap', -1, IndexError),
        ('ap', 3, IndexError),
    ],
)
def test_wrong_axis_or_section_index_rejected_before_decoding(source, decoder, axis, index, error):
    with pytest.raises(error):
        source.contour_slice(axis, index)
    assert not decoder


def test_transport_cannot_substitute_a_different_section(source, decoder, monkeypatch):
    projection = source._projections['ap']
    load = projection.load_slice
    monkeypatch.setattr(
        projection, 'load_slice', lambda index: replace(load(index), slice_index=index + 1)
    )
    with pytest.raises(ValueError, match='requested index'):
        source.contour_slice('ap', 0)
    assert not decoder


def test_missing_shared_reader_fails_without_raster_fallback(source, monkeypatch):
    monkeypatch.delattr(ibl_anatomy, 'decode_registered_contours', raising=False)
    with pytest.raises(RuntimeError, match='shared numerical contour reader'):
        source.contour_slice('ap', 0)


@pytest.mark.parametrize('extent', [0, -1, np.nan, np.inf])
def test_projection_nonfinite_or_degenerate_extent_is_rejected(extent):
    projection = _Projection('ap')
    projection.manifest = {'view_box': (-0.5, -0.5, extent, 5)}
    with pytest.raises(ValueError, match='extents'):
        projection_fraction_transform(_Grid(), 'ap', projection)


def test_projection_shape_and_missing_world_derivative_are_rejected():
    projection = _Projection('ap')
    projection.slice_shape = (99, 5)
    with pytest.raises(ValueError, match='shape'):
        projection_fraction_transform(_Grid(), 'ap', projection)
    projection = _Projection('ap')
    plane = np.asarray(projection.plane_index_to_world_um).reshape(4, 4).copy()
    plane[0, 1] = 0
    projection.plane_index_to_world_um = tuple(plane.ravel())
    with pytest.raises(ValueError, match='extents'):
        projection_fraction_transform(_Grid(), 'ap', projection)


def test_numpy_integer_section_is_normalized_for_strict_shared_reader(
    source, decoder, monkeypatch
):
    projection = source._projections['ap']
    load = projection.load_slice

    def strict(index):
        assert type(index) is int
        return load(index)

    monkeypatch.setattr(projection, 'load_slice', strict)
    assert source.contour_slice('ap', np.int64(1)).paths
    assert decoder == [1]


@pytest.mark.parametrize('axis', ['ap', 'ml', 'dv'])
def test_annotation_reuses_exact_numeric_rings_without_mutation(source, monkeypatch, axis):
    projection = source._projections[axis]
    expected = source._annotation(axis, 0)
    source.clear_cache()
    section = projection.load_slice(0)
    paths = ibl_anatomy.decode_registered_contours(section)
    monkeypatch.setattr('ibl_anatomy.decode_registered_contours', lambda _: paths)
    source.contour_slice(axis, 0)
    before = [ring.copy() for p in paths for c in p.components for ring in (c.outer, *c.holes)]
    monkeypatch.setattr(projection, 'load_slice', lambda *_: pytest.fail('duplicate section load'))
    monkeypatch.setattr(
        'ibl_datoviz.atlas_slice_source.parse_svg_path',
        lambda *_: pytest.fail('duplicate SVG parse'),
    )
    np.testing.assert_array_equal(source._annotation(axis, 0), expected)
    after = [ring for p in paths for c in p.components for ring in (c.outer, *c.holes)]
    for old, new in zip(before, after, strict=True):
        np.testing.assert_array_equal(old, new)
