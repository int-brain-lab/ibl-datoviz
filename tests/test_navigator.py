from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ibl_atlas_assets import open_volume_pack
from ibl_datoviz.navigator import (
    AtlasCursor,
    compose_atlas_slice,
    mapped_region,
    oriented_slice,
)

VOLUME_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / 'ibl-atlas-assets'
    / 'tests'
    / 'fixtures'
    / 'volume-pack-v1'
    / 'pack'
)


@pytest.fixture
def volumes():
    return open_volume_pack(VOLUME_FIXTURE).load_volumes()


@pytest.mark.parametrize(
    ('axis', 'expected'),
    [
        ('ap', np.arange(15).reshape(5, 3).T),
        ('ml', np.arange(12).reshape(4, 3).T),
        ('dv', np.arange(20).reshape(4, 5)),
    ],
)
def test_oriented_slice_uses_explicit_anatomical_axes(axis, expected):
    source_axes = tuple(item for item in ('ap', 'ml', 'dv') if item != axis)
    actual = oriented_slice(expected.T if axis != 'dv' else expected, source_axes, axis)
    assert np.array_equal(actual, expected)
    assert actual.flags.c_contiguous


def test_cursor_world_and_mapping(volumes):
    cursor = AtlasCursor(2, 2, 1)
    assert np.array_equal(cursor.world_um(volumes), [-39.0, -100.0, 0.0])
    assert cursor.source_index(volumes) == 1
    row = cursor.region(volumes, 'beryl')
    assert row is not None
    assert (row.atlas_id, row.acronym) == (997, 'root')
    assert mapped_region(volumes, 3, 'allen').atlas_id == -997


def test_cursor_replacement_is_bounded(volumes):
    cursor = AtlasCursor.centre(volumes)
    assert cursor.replace('ml', 0, volumes.grid.shape) == AtlasCursor(2, 0, 1)
    with pytest.raises(IndexError, match='outside'):
        cursor.replace('dv', 3, volumes.grid.shape)


def test_composed_slice_is_rgba_and_preserves_void_template(volumes):
    image = compose_atlas_slice(volumes, 'dv', 1, annotation_opacity=1.0)
    assert image.shape == (4, 5, 4)
    assert image.dtype == np.uint8
    assert image.flags.c_contiguous
    assert np.all(image[..., 3] == 255)
    assert tuple(image[2, 2, :3]) == (255, 255, 255)  # right root
    assert len({tuple(pixel) for pixel in image[..., :3].reshape(-1, 3)}) > 3


def test_selection_dims_only_other_mapped_regions(volumes):
    all_regions = compose_atlas_slice(volumes, 'dv', 1, annotation_opacity=1.0)
    selected = compose_atlas_slice(
        volumes,
        'dv',
        1,
        annotation_opacity=1.0,
        selected_region_ids=(997,),
        selection_dim_factor=0.25,
    )
    assert np.array_equal(selected[2, 2], all_regions[2, 2])
    assert np.all(selected[1, 1, :3] < all_regions[1, 1, :3])
    assert np.array_equal(selected[0, 0], all_regions[0, 0])  # void is anatomical grayscale
