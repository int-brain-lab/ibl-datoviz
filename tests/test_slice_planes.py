"""Physical plane geometry shares the exact oriented-slice pixel contract."""

from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy.volume_pack import AtlasVolumeGrid
from ibl_datoviz.navigator import SLICE_DISPLAY_AXES, oriented_slice
from ibl_datoviz.slice_planes import SlicePlanes, slice_plane_corners
from ibl_datoviz.slice_preparation import PreparedSliceLayers
from ibl_datoviz.slice_scheduler import SliceRequest


def grid(signs=(1, 1, 1)):
    ap, ml, dv = signs
    matrix = np.array(
        [[0, ml * 20, 0, 100], [ap * 10, 0, 0, 200], [0, 0, dv * 30, 300], [0, 0, 0, 1]], float
    )
    return AtlasVolumeGrid((3, 4, 5), tuple(matrix.ravel()))


@pytest.mark.parametrize('axis', ['ap', 'ml', 'dv'])
@pytest.mark.parametrize('signs', list(product((-1, 1), repeat=3)))
def test_every_oriented_pixel_center_matches_plane_world_coordinate(axis, signs):
    source = grid(signs)
    values = np.arange(np.prod(source.shape)).reshape(source.shape)
    fixed = source.array_axes.index(axis)
    raw = np.take(values, 1, axis=fixed)
    axes = tuple(name for name in source.array_axes if name != axis)
    image = oriented_slice(raw, axes, axis, grid=source)
    corners = slice_plane_corners(source, axis, 1)
    height, width = image.shape
    for row, column in np.ndindex(image.shape):
        u, v = (column + 0.5) / width, (row + 0.5) / height
        world = corners[0] + u * (corners[2] - corners[0]) + v * (corners[1] - corners[0])
        index = source.world_to_index(world)
        np.testing.assert_allclose(index, np.rint(index), atol=1e-10)
        assert values[tuple(np.rint(index).astype(int))] == image[row, column]


@pytest.mark.parametrize(
    'axis,index,exception',
    [
        ('bad', 0, ValueError),
        ('ap', True, ValueError),
        ('ap', -0.5, ValueError),
        ('ap', 3, IndexError),
    ],
)
def test_invalid_plane_coordinate_rejected(axis, index, exception):
    with pytest.raises(exception):
        slice_plane_corners(grid(), axis, index)


def test_sheared_grid_is_rejected_instead_of_misregistered():
    source = grid()
    affine = np.array(source.index_to_world_um_matrix).reshape(4, 4)
    affine[2, 0] = 0.1
    with pytest.raises(ValueError, match='axis-aligned'):
        slice_plane_corners(
            replace(source, index_to_world_um_matrix=tuple(affine.ravel())), 'ap', 1
        )


class FakePlane:
    created = []
    fail_on = None

    def __init__(self, _dvz, _scene, _panel, data, **options):
        if len(self.created) == self.fail_on:
            raise RuntimeError('injected second plane failure')
        self.data, self.options, self.closed = data, options, False
        self.created.append(self)

    def close(self):
        self.closed = True


@pytest.fixture
def manager(monkeypatch):
    FakePlane.created, FakePlane.fail_on = [], None
    monkeypatch.setattr('ibl_datoviz.slice_planes.SampledPlaneVisual', FakePlane)
    owner = SimpleNamespace(
        _require_open=lambda: None,
        dvz=None,
        scene=None,
        panel=None,
        mesh_data=SimpleNamespace(normalize_points=lambda v: v),
        picking=SimpleNamespace(invalidate=lambda: None),
    )
    return SlicePlanes(owner, SimpleNamespace(grid=grid()), source_id='grid')


def prepared(axis='ap', index=1, revision=0):
    request = SliceRequest(axis, index, revision, source_id='grid')
    x, y = SLICE_DISPLAY_AXES[axis]
    shape = dict(zip(grid().array_axes, grid().shape, strict=True))
    pixels = np.zeros((shape[y], shape[x], 4), np.uint8)
    pixels[..., 3] = 255
    return request, PreparedSliceLayers(pixels, pixels, np.zeros((0, 2)), np.zeros((0, 2)))


def test_hidden_updates_retain_exact_request_and_show_builds_physical_sampling_pair(manager):
    request, payload = prepared(index=0)
    manager.update('ap', request, payload)
    assert not FakePlane.created and not manager.visible_axes
    # Geometry comes from the accepted payload request, not another current cursor.
    manager.viewer.cursor = SimpleNamespace(ap=2)
    manager.show('ap')
    assert manager.visible_axes == ('ap',)
    first, second = manager._planes['ap']
    np.testing.assert_array_equal(first.data.corners_um, slice_plane_corners(grid(), 'ap', 0))
    assert first.data.sampling == 'linear' and second.data.sampling == 'nearest'
    assert first.options['depth_policy'] == second.options['depth_policy'] == 'physical'
    assert first.options['alpha_mode'] == second.options['alpha_mode'] == 'wboit'
    manager.show('ap', False)
    assert first.closed and second.closed and not manager.visible_axes
    manager.show('ap')
    assert manager._planes['ap'][0] is not first


def test_failed_pair_replacement_preserves_old_pixels_geometry_and_request(manager):
    request, payload = prepared()
    manager.update('ap', request, payload)
    manager.show('ap')
    previous = manager._planes['ap']
    FakePlane.fail_on = len(FakePlane.created) + 1
    changed_request, changed_payload = prepared(index=2, revision=1)
    with pytest.raises(RuntimeError, match='second plane failure'):
        manager.update('ap', changed_request, changed_payload)
    assert manager._planes['ap'] is previous
    assert not any(item.closed for item in previous)
    assert FakePlane.created[-1].closed
    assert manager._accepted['ap'] == (request, payload)


def test_old_async_payload_cannot_replace_newer_plane(manager):
    request, payload = prepared(index=2, revision=4)
    manager.update('ap', request, payload)
    manager.show('ap')
    current = manager._planes['ap']
    assert not manager.update('ap', *prepared(index=0, revision=3))
    assert manager._planes['ap'] is current
    with pytest.raises(ValueError, match='different requests'):
        manager.update('ap', replace(request, index=0), payload)
    with pytest.raises(ValueError, match='different source'):
        manager.update('ap', replace(request, source_id='other'), payload)


def test_extent_and_axis_failure_do_not_publish(manager):
    request, payload = prepared()
    with pytest.raises(ValueError, match='axis'):
        manager.update('ml', request, payload)
    with pytest.raises(ValueError, match='extent'):
        manager.update('ap', request, replace(payload, anatomy=payload.anatomy[:1]))
    assert not manager._accepted
    with pytest.raises(ValueError, match='no accepted'):
        manager.show('ap')


def test_close_owns_all_pairs_and_is_idempotent(manager):
    for axis in ('ap', 'ml', 'dv'):
        manager.update(axis, *prepared(axis=axis))
        manager.show(axis)
    manager.close()
    manager.close()
    assert all(component.closed for component in FakePlane.created)
    assert not manager._planes and not manager._accepted
    with pytest.raises(RuntimeError, match='closed'):
        manager.show('ap')
