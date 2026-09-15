from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from ibl_atlas_assets import RegisteredSlice, RegisteredSlicePath
from ibl_datoviz import AtlasSliceSource, parse_svg_path
from ibl_datoviz.navigator import oriented_slice


@dataclass(frozen=True)
class _Region:
    index: int
    atlas_id: int


class _Regions:
    reference_space_id = 'allen-ccf-2017'

    def physical(self, mapping):
        assert mapping == 'allen'
        return (_Region(0, 0), _Region(1, -8), _Region(2, 8))


class _Grid:
    shape = (3, 4, 5)
    array_axes = ('ap', 'ml', 'dv')
    world_axes = ('ml', 'ap', 'dv')
    reference_space_id = 'allen-ccf-2017'
    grid_id = 'allen-ccf-2017-test'
    index_to_world_um_matrix = (
        0,
        10,
        0,
        -15,
        10,
        0,
        0,
        -10,
        0,
        0,
        -10,
        20,
        0,
        0,
        0,
        1,
    )

    def index_to_world(self, indices):
        values = np.asarray(indices, dtype=np.float64)
        matrix = np.asarray(self.index_to_world_um_matrix).reshape(4, 4)
        return values @ matrix[:3, :3].T + matrix[:3, 3]

    def world_to_index(self, world):
        values = np.asarray(world, dtype=np.float64)
        inverse = np.linalg.inv(np.asarray(self.index_to_world_um_matrix).reshape(4, 4))
        return values @ inverse[:3, :3].T + inverse[:3, 3]


class _Intensity:
    grid = _Grid()
    value_range = (0, 1000)
    recommended_display_range = (10, 900)

    def read_section(self, axis, index):
        axis_index = self.grid.array_axes.index(axis)
        shape = tuple(size for offset, size in enumerate(self.grid.shape) if offset != axis_index)
        axes = tuple(item for item in self.grid.array_axes if item != axis)
        return SimpleNamespace(values=np.full(shape, index, dtype=np.uint16), array_axes=axes)


class _Projection:
    reference_space_id = _Grid.reference_space_id
    grid_id = _Grid.grid_id

    def __init__(self, axis):
        self.world_slice_axis = axis
        self.slice_count = _Grid.shape[_Grid.array_axes.index(axis)]
        self.slice_shape = tuple(
            _Grid.shape[_Grid.array_axes.index(anatomical_axis)]
            for anatomical_axis in {'ap': ('ml', 'dv'), 'ml': ('ap', 'dv'), 'dv': ('ml', 'ap')}[
                axis
            ]
        )
        self.manifest = {'view_box': (-0.5, -0.5, *self.slice_shape)}

    def index_to_world(self, values):
        section, x, y = values
        x_axis, y_axis = {'ap': ('ml', 'dv'), 'ml': ('ap', 'dv'), 'dv': ('ml', 'ap')}[
            self.world_slice_axis
        ]
        indices = np.zeros(3)
        for axis, value in ((self.world_slice_axis, section), (x_axis, x), (y_axis, y)):
            array_index = _Grid.array_axes.index(axis)
            indices[array_index] = value
        return _Grid().index_to_world(indices)

    def load_slice(self, index):
        width, height = self.slice_shape
        region_id = -8 if index == 0 else 8
        outer = f'M-.5 -.5h{width}v{height}h-{width}z'
        hole = 'M.5 .5h1v1h-1z' if height > 2 and width > 2 else ''
        path = RegisteredSlicePath(
            MappingProxyType(
                {
                    'allen': region_id,
                    'beryl': -997 if region_id < 0 else 997,
                    'cosmos': -997 if region_id < 0 else 997,
                }
            ),
            'evenodd',
            outer + hole,
        )
        world = self.index_to_world((index, 0, 0))
        coordinate = world[_Grid.world_axes.index(self.world_slice_axis)]
        return RegisteredSlice(index, coordinate, (path,))


@pytest.fixture
def source():
    projections = {axis: _Projection(axis) for axis in ('ap', 'ml', 'dv')}
    return AtlasSliceSource(_Intensity(), projections, _Regions(), section_cache_size=2)


def test_svg_parser_preserves_relative_hole_rings_and_rejects_bad_input():
    rings = parse_svg_path('M-.5-.5h4v3h-4zM.5.5h1v1h-1z')
    assert len(rings) == 2
    assert rings[0][0] == (-0.5, -0.5)
    with pytest.raises(ValueError, match='separator'):
        parse_svg_path('M0 0@L1 0L1 1z')
    with pytest.raises(ValueError, match='closed'):
        parse_svg_path('M0 0L1 0L1 1')


@pytest.mark.parametrize('axis', ('ap', 'ml', 'dv'))
def test_registered_annotation_reorients_to_exact_screen_geometry(source, axis):
    raw = source.slice('annotation', axis, 0)
    screen = oriented_slice(raw.values, raw.array_axes, axis, grid=source.grid)
    assert screen.shape == tuple(reversed(source._projections[axis].slice_shape))
    assert screen[0, 0] == 1
    assert np.count_nonzero(screen == 0) == 1


def test_lazy_source_uses_display_window_world_lookup_and_bounded_cache(source):
    assert source.value_range == (0, 1000)
    assert source.recommended_display_range == (10, 900)
    for index in range(3):
        source.slice('annotation', 'ap', index)
    assert source.cache_info()[0] == 2
    world = source.grid.index_to_world((1, 2, 0))
    assert int(source.annotation_index_at_world(world)) == 2
    assert source.region_for_source_index(2).atlas_id == 8
    assert source.first_right_ml_index == 2


def test_cached_world_lookup_never_loads_a_missing_section(source):
    world = source.grid.index_to_world((1, 2, 0))
    assert source.cached_annotation_index_at_world(world) is None
    source.slice('annotation', 'ml', 2)
    assert source.cached_annotation_index_at_world(world, preferred_axis='ml') == 2


def test_source_rejects_incompatible_projection_affine():
    projections = {axis: _Projection(axis) for axis in ('ap', 'ml', 'dv')}
    projections['ap'].index_to_world = lambda values: np.zeros(3)
    with pytest.raises(ValueError, match='affine differs'):
        AtlasSliceSource(_Intensity(), projections, _Regions())
