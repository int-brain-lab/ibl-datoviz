"""Accepted prepared pixels and request geometry render together in the native scene."""

from types import SimpleNamespace

import numpy as np

from ibl_anatomy.volume_pack import AtlasVolumeGrid
from ibl_datoviz.slice_planes import SlicePlanes
from ibl_datoviz.slice_preparation import PreparedSliceLayers
from ibl_datoviz.slice_scheduler import SliceRequest
from tests import test_component_native

native_components = test_component_native.native_components


def test_native_physical_plane_updates_prepared_pair_and_hides_without_scene_teardown(
    native_components,
):
    context = native_components
    affine = np.array([[0, 0.4, 0, -0.6], [0.4, 0, 0, -0.4], [0, 0, 0.2, -0.4], [0, 0, 0, 1]])
    grid = AtlasVolumeGrid((3, 4, 5), tuple(affine.ravel()))
    viewer = SimpleNamespace(
        dvz=context.dvz,
        scene=context.scene,
        panel=context.panel,
        _require_open=lambda: None,
        mesh_data=SimpleNamespace(normalize_points=lambda v: v),
    )
    manager = SlicePlanes(viewer, SimpleNamespace(grid=grid), source_id='test')
    context.components.append(manager)
    white = context.capture()

    def prepare(color):
        anatomy = np.tile(np.asarray(color, np.uint8), (3, 4, 1))
        annotation = np.zeros_like(anatomy)
        return PreparedSliceLayers(anatomy, annotation, np.zeros((0, 2)), np.zeros((0, 2)))

    first = SliceRequest('dv', 2, 0, source_id='test')
    manager.update('dv', first, prepare((255, 0, 0, 255)))
    manager.show('dv')
    red = context.capture()
    np.testing.assert_array_equal(red[60, 80, :3], [255, 0, 0])
    second = SliceRequest('dv', 0, 1, source_id='test')
    manager.update('dv', second, prepare((0, 0, 255, 255)))
    np.testing.assert_allclose(manager._planes['dv'][0].data.corners_um[:, 2], -0.4)
    blue = context.capture()
    np.testing.assert_array_equal(blue[60, 80, :3], [0, 0, 255])
    manager.show('dv', False)
    np.testing.assert_array_equal(context.capture(), white)
    manager.show('dv')
    np.testing.assert_array_equal(context.capture(), blue)
    manager.close()
    np.testing.assert_array_equal(context.capture(), white)
