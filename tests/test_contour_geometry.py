"""Mapped contour fills, containment and exact partition boundary cancellation."""

from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz.contour_geometry import prepare_contour_geometry, selected_descendants
from tests.test_volume_free_navigator import VOLUME


@pytest.fixture
def catalog():
    return open_volume_pack(VOLUME).load_volumes().regions


def rectangle(x0=0, y0=0, x1=2, y1=2):
    return np.asarray([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)


def component(outer=None, holes=()):
    return SimpleNamespace(outer=rectangle() if outer is None else outer, holes=tuple(holes))


def path(allen_id=315, *components):
    return SimpleNamespace(atlas_ids={'allen': allen_id}, components=components or (component(),))


def segments(starts, ends):
    return {tuple(sorted((tuple(a), tuple(b)))) for a, b in zip(starts, ends, strict=True)}


def coarse(catalog):
    rows = []
    for row in catalog.physical('allen'):
        mapping = dict(row.mapped_atlas_ids)
        if abs(row.atlas_id) in (8, 315):
            mapping['beryl'] = -8 if row.atlas_id < 0 else 8
        rows.append(replace(row, mapped_atlas_ids=MappingProxyType(mapping)))
    mappings = dict(catalog.mappings)
    mappings['allen'] = tuple(rows)
    return replace(catalog, mappings=MappingProxyType(mappings))


def test_owned_immutable_rings_and_boundaries_detach_source_storage(catalog):
    raw = rectangle()
    geometry = prepare_contour_geometry([path(315, component(raw))], catalog, 'allen', [315])
    raw[:] = 999
    np.testing.assert_array_equal(geometry.components[0].outer, rectangle())
    for array in (
        geometry.components[0].outer,
        geometry.boundary_starts,
        geometry.boundary_ends,
        geometry.selection_starts,
        geometry.selection_ends,
    ):
        with pytest.raises(ValueError):
            array.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        geometry.mapping = 'beryl'
    assert geometry.components[0].atlas_id == geometry.components[0].allen_id == 315


def test_holes_nested_islands_and_exact_boundary_policy(catalog):
    source = path(
        315,
        component(rectangle(0, 0, 10, 10), [rectangle(2, 2, 8, 8)]),
        component(rectangle(4, 4, 6, 6)),
    )
    geometry = prepare_contour_geometry([source], catalog, 'allen', [315])
    assert geometry.region_at(1, 1) == 315
    assert geometry.region_at(3, 3) is None
    assert geometry.region_at(5, 5) == 315
    assert geometry.region_at(0, 5) == 315
    assert geometry.region_at(2, 5) == 315
    assert geometry.region_at(-1, 5) is None
    assert len(geometry.boundary_starts) == 12


def test_reverse_paint_order_determines_shared_edge_and_overlap_identity(catalog):
    left = path(315, component(rectangle(0, 0, 2, 2)))
    right = path(-315, component(rectangle(2, 0, 4, 2)))
    geometry = prepare_contour_geometry([left, right], catalog, 'allen')
    assert geometry.region_at(1, 1) == 315
    assert geometry.region_at(3, 1) == -315
    assert geometry.region_at(2, 1) == -315
    assert prepare_contour_geometry([right, left], catalog, 'allen').region_at(2, 1) == 315


def test_same_mapped_region_cancels_shared_edges_and_coalesces_collinear_spans(catalog):
    sources = [
        path(315, component(rectangle(0, 0, 2, 2))),
        path(8, component(rectangle(2, 0, 4, 2))),
    ]
    geometry = prepare_contour_geometry(sources, coarse(catalog), 'beryl', [8])
    assert len(geometry.boundary_starts) == 4
    assert segments(geometry.boundary_starts, geometry.boundary_ends) == {
        ((0.0, 0.0), (4.0, 0.0)),
        ((0.0, 2.0), (4.0, 2.0)),
        ((0.0, 0.0), (0.0, 2.0)),
        ((4.0, 0.0), (4.0, 2.0)),
    }
    assert len(geometry.selection_starts) == 4
    assert all(row.atlas_id == 8 for row in geometry.components)
    assert {row.allen_id for row in geometry.components} == {8, 315}


def test_different_region_border_drawn_once_and_selected_union_has_no_internal_border(catalog):
    sources = [
        path(315, component(rectangle(0, 0, 2, 2))),
        path(8, component(rectangle(2, 0, 4, 2))),
    ]
    geometry = prepare_contour_geometry(sources, catalog, 'allen', [8])
    assert len(geometry.boundary_starts) == 5
    assert len(geometry.selection_starts) == 4
    assert all(row.selected for row in geometry.components)  # 315 is child of signed parent8.


def test_partial_overlaps_at_t_junction_cancel_without_unit_grid_expansion(catalog):
    sources = [
        path(315, component(rectangle(0, 0, 4, 2))),
        path(8, component(rectangle(0, 2, 2, 4))),
        path(8, component(rectangle(2, 2, 4, 4))),
    ]
    geometry = prepare_contour_geometry(sources, coarse(catalog), 'beryl', [8])
    assert len(geometry.boundary_starts) == 4
    assert len(geometry.selection_starts) == 4
    # Long collinear input edges stay bounded by vertices, not by geometric length.
    far = prepare_contour_geometry(
        [path(315, component(rectangle(0, 0, 1000000, 2)))], catalog, 'allen'
    )
    assert len(far.boundary_starts) == 4


def test_selected_hole_island_union_and_unselected_hole_boundary(catalog):
    sources = [
        path(315, component(rectangle(0, 0, 6, 6), [rectangle(2, 2, 4, 4)])),
        path(8, component(rectangle(2, 2, 4, 4))),
    ]
    selected = prepare_contour_geometry(sources, catalog, 'allen', [8])
    assert len(selected.boundary_starts) == 8  # outer4 plus distinctregionhole4
    assert len(selected.selection_starts) == 4
    one = prepare_contour_geometry(sources, catalog, 'allen', [315])
    assert len(one.selection_starts) == 8
    assert one.region_at(3, 3) == 8


def test_parent_expansion_preserves_signed_hemispheres(catalog):
    assert selected_descendants(catalog, 'allen', [8]) == frozenset((8, 315))
    assert selected_descendants(catalog, 'allen', [-8]) == frozenset((-8, -315))
    sources = [path(315), path(-315, component(rectangle(3, 0, 5, 2)))]
    geometry = prepare_contour_geometry(sources, catalog, 'allen', [-8])
    assert [row.selected for row in geometry.components] == [False, True]


def test_absent_reduced_rows_void_and_empty_sections_remain_empty(catalog):
    geometry = prepare_contour_geometry([path(315), path(0)], catalog, 'beryl')
    assert not geometry.components and geometry.region_at(1, 1) is None
    assert geometry.boundary_starts.shape == geometry.selection_ends.shape == (0, 2)
    assert prepare_contour_geometry([], catalog, 'allen').boundary_starts.shape == (0, 2)


@pytest.mark.parametrize(
    'raw',
    [
        [[0, 0], [2, 0], [1, 2], [0, 2]],
        [[0, 0], [2, 0], [2, 1.1], [0, 1.1]],
        [[0, 0], [2, 0], [2, np.nan], [0, 2]],
        [[0, 0], [0, 0], [2, 0], [0, 2]],
    ],
)
def test_non_exact_profile_rejected(catalog, raw):
    with pytest.raises(ValueError):
        prepare_contour_geometry([path(315, component(np.asarray(raw)))], catalog, 'allen')


@pytest.mark.parametrize('point', [(np.nan, 0), (0, np.inf), ([1], 0)])
def test_nonfinite_or_nonscalar_pick_rejected(catalog, point):
    geometry = prepare_contour_geometry([path()], catalog, 'allen')
    with pytest.raises(ValueError):
        geometry.region_at(*point)


def test_explicit_closed_ring_and_reversed_winding_preserve_geometry(catalog):
    raw = rectangle()[::-1]
    raw = np.concatenate([raw, raw[:1]])
    geometry = prepare_contour_geometry([path(315, component(raw))], catalog, 'allen')
    assert geometry.region_at(1, 1) == 315
    assert len(geometry.boundary_starts) == 4


def test_unknown_mapping_source_id_and_boolean_selection_rejected(catalog):
    with pytest.raises(KeyError):
        prepare_contour_geometry([path()], catalog, 'unknown')
    with pytest.raises(KeyError):
        prepare_contour_geometry([path(999999)], catalog, 'allen')
    with pytest.raises(ValueError, match='signed integers'):
        prepare_contour_geometry([path()], catalog, 'allen', [True])


def test_random_label_partitions_match_categorical_boundary_and_selection_oracles(catalog):
    random = np.random.default_rng(419)

    def midpoints(starts, ends):
        result = set()
        for first, last in zip(starts, ends, strict=True):
            count = int(round(np.abs(last - first).sum()))
            for step in range(count):
                point = first + (last - first) * (step + 0.5) / count
                result.add(tuple(point))
        return result

    def oracle(labels):
        result = set()
        for y, x in np.ndindex(labels.shape):
            if not labels[y, x]:
                continue
            for dy, dx, edge in (
                (-1, 0, (x, y - 0.5)),
                (1, 0, (x, y + 0.5)),
                (0, -1, (x - 0.5, y)),
                (0, 1, (x + 0.5, y)),
            ):
                yy, xx = y + dy, x + dx
                if (
                    not (0 <= yy < labels.shape[0] and 0 <= xx < labels.shape[1])
                    or labels[yy, xx] != labels[y, x]
                ):
                    result.add(edge)
        return result

    for _ in range(12):
        labels = random.choice([0, 315, -315, 8], size=(6, 7))
        sources = []
        for atlas_id in (315, -315, 8):
            pieces = [
                component(rectangle(x - 0.5, y - 0.5, x + 0.5, y + 0.5))
                for y, x in np.argwhere(labels == atlas_id)
            ]
            sources.append(path(atlas_id, *pieces))
        geometry = prepare_contour_geometry(sources, catalog, 'allen', [315])
        assert midpoints(geometry.boundary_starts, geometry.boundary_ends) == oracle(labels)
        assert midpoints(geometry.selection_starts, geometry.selection_ends) == oracle(
            labels == 315
        )
        for y, x in np.ndindex(labels.shape):
            assert geometry.region_at(x, y) == (int(labels[y, x]) or None)
