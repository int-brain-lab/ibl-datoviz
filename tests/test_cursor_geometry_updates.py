"""Retained cursor geometry follows position changes and failed native writes."""

import ctypes
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasViewer
from ibl_datoviz.linked_atlas import LinkedSlices


class GeometryDesc(ctypes.Structure):
    """Provide addressable geometry arguments without a native allocation."""

    _fields_ = [('center', ctypes.c_float * 3)]


def navigator():
    """Exercise the actual geometry builder with a recording native boundary."""
    viewer = LinkedSlices.__new__(LinkedSlices)
    viewer.viewer = SimpleNamespace(_check=AtlasViewer._check)
    state = SimpleNamespace(position=(0, 0, 0), uploads=[], fail=False, creates=0)
    viewer.cursor = SimpleNamespace(world_um=lambda _: state.position)
    viewer.slice_source = object()
    viewer.viewer.mesh_data = SimpleNamespace(
        display_scale=1, normalize_points=lambda points: points
    )
    viewer.cursor_marker = object()

    def create(_):
        state.creates += 1
        return ctypes.c_void_p(state.creates)

    def upload(*args):
        state.uploads.append(args)
        return -1 if state.fail else 0

    viewer.viewer.dvz = SimpleNamespace(
        dvz_geometry_sphere_desc=GeometryDesc,
        dvz_geometry_cylinder_desc=GeometryDesc,
        DvzColor=lambda *rgba: rgba,
        dvz_geometry_sphere=create,
        dvz_geometry_cylinder=create,
        dvz_geometry_transform=lambda *_: 0,
        dvz_geometry_merge=lambda *_: ctypes.c_void_p(100),
        dvz_geometry_destroy=lambda *_: None,
        dvz_mesh_set_geometry=upload,
        dvz_visual_set_data_many=upload,
    )
    return viewer, state


def test_cursor_geometry_changes_only_with_position_and_retries_failed_write():
    viewer, state = navigator()
    viewer._update_cursor_marker()
    viewer._update_cursor_marker()
    assert state.creates == 4 and len(state.uploads) == 1
    state.position = (1, 2, 3)
    state.fail = True
    with pytest.raises(RuntimeError, match='cursor update'):
        viewer._update_cursor_marker()
    # Even a partial write at the new position requires restoring the old one.
    state.position = (0, 0, 0)
    state.fail = False
    viewer._update_cursor_marker()
    assert len(state.uploads) == 3
    viewer._update_cursor_marker()
    assert len(state.uploads) == 3


def test_crosshair_geometry_tracks_coordinates_and_retries_failed_write():
    viewer, state = navigator()
    viewer._crosshairs = {'ap': object()}
    viewer._crosshair_positions = lambda _: (
        np.asarray([state.position], np.float32),
        np.ones((1, 3), np.float32),
    )
    viewer._update_crosshair('ap')
    viewer._update_crosshair('ap')
    assert len(state.uploads) == 1
    state.position = (1, 0, 0)
    state.fail = True
    with pytest.raises(RuntimeError, match='crosshair update'):
        viewer._update_crosshair('ap')
    state.position = (0, 0, 0)
    state.fail = False
    viewer._update_crosshair('ap')
    assert len(state.uploads) == 3


def test_slice_refresh_preserves_selection_work_without_reuploading_cursor():
    viewer, state = navigator()
    viewer._slice_fields = {'ap': object()}
    viewer._slice_revisions = {'ap': 0}
    viewer._slice_loader = None
    viewer._crosshairs = {'ap': object()}
    viewer._crosshair_positions = lambda _: (np.zeros((1, 3)), np.ones((1, 3)))
    requests = []
    viewer._slice_request = lambda axis: viewer._slice_revisions[axis]
    viewer._prepare_slice = lambda request: request
    viewer._upload_slice_payload = lambda request, _: requests.append(request)
    viewer._refresh_slices()
    uploads = len(state.uploads)
    viewer._refresh_slices()
    assert requests == [1, 2]
    assert len(state.uploads) == uploads
    viewer._refresh_slices(())
    assert requests == [1, 2] and len(state.uploads) == uploads
