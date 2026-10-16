"""Interior centroid navigation preserves exact grid, signed identities and ties."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz.region_navigation import RegionNavigation
from tests.test_volume_free_navigator import VOLUME


@pytest.fixture
def source():
    original = open_volume_pack(VOLUME).load_volumes()
    labels = np.zeros((5, 9, 5), np.uint16)
    return replace(
        original,
        template=np.zeros_like(labels),
        annotation=labels,
        grid=replace(original.grid, shape=labels.shape),
    )


def test_concave_centroid_hole_chooses_actual_interior_with_ap_ml_dv_ties(source):
    positions = [(1, 6, 2), (3, 6, 2), (2, 5, 2), (2, 7, 2)]
    for position in positions:
        source.annotation[position] = 6
    assert source.annotation[2, 6, 2] == 0
    navigation = RegionNavigation(source, chunk_voxels=7)
    assert navigation.anchor('allen', 315) == (1, 6, 2)
    assert source.region_for_source_index(int(source.annotation[1, 6, 2])).atlas_id == 315


def test_disconnected_region_uses_occupied_voxel_not_bbox_center(source):
    source.annotation[0, 6, 0] = source.annotation[4, 6, 4] = 6
    assert RegionNavigation(source, chunk_voxels=9).anchor('allen', 315) == (0, 6, 0)


def test_signed_hemispheres_are_not_pooled(source):
    source.annotation[0, 1, 0] = 5
    source.annotation[4, 1, 4] = 5
    source.annotation[2, 7, 3] = 6
    navigation = RegionNavigation(source)
    assert navigation.anchor('allen', -315) == (0, 1, 0)
    assert navigation.anchor('allen', 315) == (2, 7, 3)


def test_reduced_mapping_aggregates_all_actual_occupied_source_rows(source):
    rows = []
    for row in source.regions.physical('allen'):
        crosswalk = dict(row.mapped_atlas_ids)
        if abs(row.atlas_id) in (8, 315):
            crosswalk['beryl'] = -8 if row.atlas_id < 0 else 8
        rows.append(replace(row, mapped_atlas_ids=MappingProxyType(crosswalk)))
    mappings = dict(source.regions.mappings)
    mappings['allen'] = tuple(rows)
    source = replace(source, regions=replace(source.regions, mappings=MappingProxyType(mappings)))
    source.annotation[0, 6, 0] = 6
    source.annotation[4, 6, 4] = 2
    navigation = RegionNavigation(source, chunk_voxels=11)
    assert navigation.anchor('allen', 8) == (4, 6, 4)
    assert navigation.anchor('beryl', 8) == (0, 6, 0)
    assert navigation.anchor('beryl', 315) is None


def test_void_absent_unmapped_and_legacy_opposite_root_never_choose_a_position(source):
    source.annotation[1, 1, 1] = 3  # Legacy negative root maps to positive reduced root.
    source.annotation[2, 6, 2] = 2  # Reduced-map placeholder root means unmapped.
    navigation = RegionNavigation(source)
    assert navigation.anchor('allen', 0) is None
    assert navigation.anchor('allen', 999999) is None
    assert navigation.anchor('allen', 315) is None
    assert navigation.anchor('beryl', -997) is None
    assert navigation.anchor('beryl', 997) is None
    assert navigation.anchor('beryl', 8) is None
    with pytest.raises(KeyError, match='mapping'):
        navigation.anchor('unknown', 315)


@pytest.mark.parametrize('region_id', [True, np.bool_(False), 3.5, '315', None])
def test_non_integer_scientific_identity_is_rejected(source, region_id):
    with pytest.raises(ValueError, match='signed integer'):
        RegionNavigation(source).anchor('allen', region_id)


def test_unknown_annotation_source_index_is_not_silently_dropped(source):
    source.annotation[0, 0, 0] = 65535
    with pytest.raises(ValueError, match='unknown source index'):
        RegionNavigation(source).anchor('allen', 315)


def test_lazy_source_unavailable_without_reading_or_materializing():
    class LazySource:
        @property
        def annotation(self):
            raise AssertionError('lazy source annotation was accessed')

        def slice(self, *_args):
            raise AssertionError('lazy source was read')

    navigation = RegionNavigation(LazySource())
    assert not navigation.available and 'lazy' in navigation.unavailable_reason
    assert navigation.anchor('allen', 315) is None


def test_bounded_lru_retains_results_including_unavailable_rows(source, monkeypatch):
    navigation = RegionNavigation(source, cache_size=2)
    assert navigation.anchor('allen', 315) is None
    assert navigation.anchor('allen', -315) is None
    # Refresh first entry, so the second entry is evicted by the next lookup.
    assert navigation.anchor('allen', 315) is None
    assert navigation.anchor('allen', 8) is None
    assert list(navigation._anchors) == [('allen', 315), ('allen', 8)]
    monkeypatch.setattr(navigation, '_compute_anchor', lambda *_args: pytest.fail('cache miss'))
    assert navigation.anchor('allen', 315) is None


def test_every_work_array_respects_chunk_bound(source, monkeypatch):
    source.annotation[:, 5:, :] = 6
    navigation = RegionNavigation(source, chunk_voxels=13)
    coordinates = navigation._coordinates
    lengths = []

    def bounded(flat, axis):
        lengths.append(len(flat))
        assert len(flat) <= 13
        return coordinates(flat, axis)

    monkeypatch.setattr(navigation, '_coordinates', bounded)
    anchor = navigation.anchor('allen', 315)
    assert anchor == (2, 6, 2)
    assert len(lengths) > 6


def test_noncontiguous_annotations_do_not_require_full_volume_flattening(source):
    source.annotation[1, 6, 2] = 6
    source = replace(source, annotation=source.annotation[::-1])
    assert not source.annotation.flags.c_contiguous
    assert RegionNavigation(source, chunk_voxels=13).anchor('allen', 315) == (3, 6, 2)


def test_random_sparse_regions_match_exact_brute_force_centroid_scores(source):
    random = np.random.default_rng(409)
    for _ in range(25):
        source.annotation[:] = 0
        mask = random.random(source.annotation.shape) < 0.18
        source.annotation[mask] = 6
        coordinates = np.argwhere(mask).astype(np.int64)
        count, sums = len(coordinates), coordinates.sum(axis=0)
        scores = count * (coordinates * coordinates).sum(axis=1) - 2 * (coordinates * sums).sum(
            axis=1
        )
        expected = tuple(map(int, coordinates[int(scores.argmin())]))
        assert RegionNavigation(source, chunk_voxels=11).anchor('allen', 315) == expected


def test_parallel_queries_share_bounded_thread_safe_cache(source):
    source.annotation[1, 6, 1] = 6
    source.annotation[3, 1, 3] = 5
    navigation = RegionNavigation(source, cache_size=2, chunk_voxels=7)
    with ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(lambda value: navigation.anchor('allen', value), [315, -315, 315]))
    assert result == [(1, 6, 1), (3, 1, 3), (1, 6, 1)]
    assert len(navigation._anchors) == 2


@pytest.mark.parametrize(
    'options',
    [{'cache_size': 0}, {'chunk_voxels': 0}, {'cache_size': True}, {'chunk_voxels': 1.5}],
)
def test_invalid_memory_limits_rejected(source, options):
    with pytest.raises(ValueError, match='positive integer'):
        RegionNavigation(source, **options)


@pytest.mark.parametrize(
    ('positions', 'expected'),
    [
        ([(2, 5, 2), (2, 7, 2)], (2, 5, 2)),
        ([(2, 6, 1), (2, 6, 3)], (2, 6, 1)),
    ],
)
def test_centroid_distance_ties_continue_through_ml_then_dv(source, positions, expected):
    for position in positions:
        source.annotation[position] = 6
    assert RegionNavigation(source, chunk_voxels=1).anchor('allen', 315) == expected


def test_navigation_cache_is_scoped_to_its_exact_source(source):
    source.annotation[1, 6, 1] = 6
    other = replace(source, annotation=np.array(source.annotation, copy=True))
    other.annotation[:] = 0
    other.annotation[3, 7, 3] = 6
    assert RegionNavigation(source).anchor('allen', 315) == (1, 6, 1)
    assert RegionNavigation(other).anchor('allen', 315) == (3, 7, 3)
