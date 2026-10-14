import ctypes
from collections import Counter

import numpy as np
import pytest

from ibl_datoviz.points import PointCollection, PointCollectionVisual
from ibl_datoviz.sampled_plane import SampledPlane, SampledPlaneVisual


class PointStyle(ctypes.Structure):
    _fields_ = [('aspect', ctypes.c_int), ('stroke_width_px', ctypes.c_float)]


class FieldDesc(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_int)
        for name in ('dim', 'format', 'semantic', 'color_role', 'height', 'width', 'depth')
    ]


class FieldView(ctypes.Structure):
    _fields_ = [
        ('data', ctypes.c_void_p),
        ('bytes_per_row', ctypes.c_uint64),
        ('rows_per_image', ctypes.c_uint64),
    ]


class Native:
    """Stateful copied-upload fake with one-shot native failure injection."""

    DVZ_ALPHA_OPAQUE = 0
    DVZ_ALPHA_BLENDED = 1
    DVZ_SHAPE_ASPECT_FILLED = 0
    DVZ_IMAGE_SAMPLING_NEAREST = 1
    DVZ_IMAGE_SAMPLING_LINEAR = 0
    DVZ_FIELD_DIM_2D = 2
    DVZ_FIELD_FORMAT_RGBA8_UNORM = 4
    DVZ_FIELD_SEMANTIC_COLOR = 1
    DVZ_COLOR_ROLE_SRGB_COLOR = 1

    def __init__(self):
        self.visuals, self.fields = {}, {}
        self.calls = Counter()
        self.fail = None
        self.next_id = 1

    def status(self, name):
        self.calls[name] += 1
        if self.fail == name:
            self.fail = None
            return -1
        return 0

    def dvz_point(self, scene, flags):
        handle = self.next_id
        self.next_id += 1
        self.visuals[handle] = {}
        self.calls['create_visual'] += 1
        return handle

    dvz_image = dvz_point

    def dvz_point_style_desc(self):
        return PointStyle()

    def dvz_point_set_style(self, visual, style):
        return self.status('style')

    def dvz_visual_set_alpha_mode(self, visual, mode):
        return self.status('alpha')

    def dvz_visual_set_depth_test(self, visual, enabled):
        self.visuals[visual]['depth'] = enabled
        return self.status('depth')

    def dvz_visual_set_data_many(self, visual, data):
        status = self.status('batch')
        if status == 0:
            assert all(len(array) > 0 for array in data.values())
            self.visuals[visual].update({key: np.array(value) for key, value in data.items()})
        return status

    def dvz_visual_set_data(self, visual, key, data):
        status = self.status(key)
        if status == 0:
            self.visuals[visual][key] = np.array(data)
        return status

    def dvz_visual_set_visible(self, visual, visible):
        status = self.status('visible')
        if status == 0:
            self.visuals[visual]['visible'] = visible
        return status

    def dvz_panel_add_visual(self, panel, visual, desc):
        return self.status('attach')

    def dvz_visual_destroy(self, visual):
        self.calls['destroy_visual'] += 1
        del self.visuals[visual]

    def dvz_sampled_field_desc(self):
        return FieldDesc()

    def dvz_field_data_view(self):
        return FieldView()

    def dvz_sampled_field(self, scene, desc):
        if self.status('create_field'):
            return None
        handle = self.next_id
        self.next_id += 1
        extent = ctypes.cast(desc, ctypes.POINTER(FieldDesc)).contents
        self.fields[handle] = np.zeros((extent.height, extent.width, 4), np.uint8)
        return handle

    def dvz_sampled_field_set_data(self, field, view):
        status = self.status('field_upload')
        if status == 0:
            source = ctypes.cast(view, ctypes.POINTER(FieldView)).contents
            pointer = ctypes.cast(source.data, ctypes.POINTER(ctypes.c_uint8))
            shape = self.fields[field].shape
            pixels = np.ctypeslib.as_array(pointer, shape=(int(np.prod(shape)),))
            self.fields[field] = pixels.reshape(shape).copy()
        return status

    def dvz_sampled_field_update_from_array(self, field, pixels):
        if self.status('pixels'):
            raise RuntimeError('pixel update failed')
        assert self.fields[field].shape == pixels.shape
        self.fields[field] = np.array(pixels)
        return field  # Not an integer status code.

    def dvz_visual_set_field(self, visual, slot, field):
        status = self.status('bind_field')
        if status == 0:
            self.visuals[visual]['field'] = field
        return status

    def dvz_image_set_sampling(self, visual, sampling):
        return self.status('sampling')

    def dvz_sampled_field_destroy(self, field):
        self.calls['destroy_field'] += 1
        del self.fields[field]


def points(count=3):
    return PointCollection.from_arrays(np.ones((count, 3)), np.ones((count, 4), np.uint8))


def plane(shape=(2, 3, 4), color=1):
    return SampledPlane.from_arrays(
        [[0, 1, 0], [0, 0, 0], [1, 1, 0], [1, 0, 0]], np.full(shape, color, np.uint8)
    )


def test_points_replace_smaller_larger_empty_restored_with_one_visual():
    native = Native()
    display = PointCollectionVisual(native, 'scene', 'panel', points(), transform=lambda x: x * 2)
    handle = display.visual
    np.testing.assert_array_equal(native.visuals[handle]['position'], np.full((3, 3), 2))
    for count in (1, 8, 0, 2):
        display.replace(points(count))
        assert len(display.data) == count
        assert native.visuals[handle]['visible'] == bool(count)
        if count:
            assert {
                len(native.visuals[handle][key]) for key in ('position', 'color', 'diameter_px')
            } == {count}
    assert display.visual == handle and native.calls['create_visual'] == 1
    display.close()
    display.close()
    assert not native.visuals
    with pytest.raises(RuntimeError, match='closed'):
        display.replace(points())


def test_color_only_update_shares_owned_geometry_and_checks_status():
    native = Native()
    transforms = []

    def transform(array):
        transforms.append(array)
        return array

    display = PointCollectionVisual(native, 'scene', 'panel', points(), transform=transform)
    original = display.data
    batches = native.calls['batch']
    colors = np.full((3, 4), 100, np.uint8)
    display.update_colors(colors)
    assert display.data.positions_um is original.positions_um
    assert display.data.sizes_px is original.sizes_px
    assert len(transforms) == 1 and native.calls['batch'] == batches
    assert not np.shares_memory(colors, display.data.colors)
    committed = display.data
    native.fail = 'color'
    with pytest.raises(RuntimeError, match='point colors'):
        display.update_colors(np.full((3, 4), 200, np.uint8))
    assert display.data is committed
    display.update_sizes(8)
    assert display.data.positions_um is committed.positions_um
    assert native.visuals[display.visual]['diameter_px'].tolist() == [8, 8, 8]


def test_authored_visibility_survives_empty_restore():
    native = Native()
    display = PointCollectionVisual(native, 'scene', 'panel', points(0))
    assert display.visual is None
    display.set_visible(False)
    display.replace(points(2))
    assert not native.visuals[display.visual]['visible']
    display.replace(points(0))
    display.set_visible(True)
    assert not native.visuals[display.visual]['visible']
    display.replace(points(1))
    assert native.visuals[display.visual]['visible']


@pytest.mark.parametrize('failure', ['batch', 'visible'])
def test_point_replacement_failure_preserves_prior_payload(failure):
    native = Native()
    display = PointCollectionVisual(native, 'scene', 'panel', points(3))
    before = display.data
    native.fail = failure
    with pytest.raises(RuntimeError):
        display.replace(points(1))
    assert display.data is before
    assert len(native.visuals[display.visual]['position']) == 3


@pytest.mark.parametrize('failure', ['style', 'depth', 'batch', 'attach'])
def test_partial_point_constructor_releases_only_its_resources(failure):
    native = Native()
    native.fail = failure
    with pytest.raises(RuntimeError):
        PointCollectionVisual(native, 'borrowed scene', 'borrowed panel', points())
    assert not native.visuals


def test_plane_updates_extents_empty_restore_and_bounded_resources():
    native = Native()
    display = SampledPlaneVisual(native, 'scene', 'panel', plane(), transform=lambda x: x * 2)
    visual, field = display.visual, display.field
    assert not display.capabilities.depth_test and not display.capabilities.depth_write
    assert native.visuals[visual]['depth'] is False
    display.update_corners(display.data.corners_um + [3, 0, 0])
    assert display.field == field and native.calls['pixels'] == 0
    display.update_pixels(np.full((2, 3, 4), 20, np.uint8))
    assert display.field == field and native.calls['create_field'] == 1
    for width in range(1, 8):
        display.update_pixels(np.full((2, width, 4), width, np.uint8))
        assert len(native.fields) == 1 and len(native.visuals) == 1
    display.replace(None)
    assert not native.visuals[visual]['visible']
    display.replace(plane())
    assert native.visuals[visual]['visible']
    assert display.visual == visual and len(native.fields) == 1
    display.close()
    display.close()
    assert not native.visuals and not native.fields


@pytest.mark.parametrize('failure', ['bind_field', 'sampling', 'visible'])
def test_plane_extent_replacement_failure_restores_old_binding_and_pixels(failure):
    native = Native()
    display = SampledPlaneVisual(native, 'scene', 'panel', plane())
    before, field = display.data, display.field
    native.fail = failure
    with pytest.raises(RuntimeError):
        display.replace(plane((3, 2, 4), 9))
    assert display.data is before and display.field == field
    assert native.visuals[display.visual]['field'] == field
    assert len(native.fields) == 1
    np.testing.assert_array_equal(native.fields[field], before.rgba)


def test_plane_in_place_failure_restores_pixels_and_geometry():
    native = Native()
    display = SampledPlaneVisual(native, 'scene', 'panel', plane())
    before = display.data
    native.fail = 'sampling'
    with pytest.raises(RuntimeError):
        display.replace(plane(color=42))
    assert display.data is before
    np.testing.assert_array_equal(native.fields[display.field], before.rgba)


@pytest.mark.parametrize(
    'failure', ['batch', 'create_field', 'field_upload', 'bind_field', 'sampling', 'attach']
)
def test_partial_plane_constructor_releases_visual_and_field(failure):
    native = Native()
    native.fail = failure
    with pytest.raises(RuntimeError):
        SampledPlaneVisual(native, 'scene', 'panel', plane())
    assert not native.visuals and not native.fields


@pytest.mark.parametrize('mode', ['mask', 'depth_peel'])
def test_unsupported_alpha_rejected_before_creating_native_resources(mode):
    native = Native()
    with pytest.raises(ValueError):
        PointCollectionVisual(native, 'scene', 'panel', points(), alpha_mode=mode)
    with pytest.raises(ValueError):
        SampledPlaneVisual(native, 'scene', 'panel', plane(), alpha_mode=mode)
    assert not native.visuals and not native.fields


def test_overlay_wboit_rejected_before_creating_native_resources():
    native = Native()
    with pytest.raises(ValueError):
        SampledPlaneVisual(native, 'scene', 'panel', plane(), alpha_mode='wboit')
    assert not native.visuals and not native.fields


def test_required_plane_depth_fails_without_overlay_fallback():
    native = Native()
    with pytest.raises(ValueError, match='3D depth'):
        SampledPlaneVisual(native, 'scene', 'panel', plane(), depth_policy='depth')
    assert not native.visuals


def test_point_failed_rollback_closes_component_without_destroying_caller_scene(monkeypatch):
    native = Native()
    display = PointCollectionVisual(native, 'scene', 'panel', points())
    monkeypatch.setattr(native, 'dvz_visual_set_data_many', lambda *args: -1)
    with pytest.raises(RuntimeError, match='rollback failed; component closed'):
        display.replace(points(1))
    assert not native.visuals
    with pytest.raises(RuntimeError, match='closed'):
        display.set_visible(True)


def test_plane_failed_rollback_releases_both_candidate_and_prior_fields(monkeypatch):
    native = Native()
    display = SampledPlaneVisual(native, 'scene', 'panel', plane())
    monkeypatch.setattr(native, 'dvz_image_set_sampling', lambda *args: -1)
    with pytest.raises(RuntimeError, match='rollback failed; component closed'):
        display.replace(plane((3, 2, 4), 9))
    assert not native.visuals and not native.fields


def test_plane_null_update_handle_is_reported_without_committing_payload(monkeypatch):
    native = Native()
    display = SampledPlaneVisual(native, 'scene', 'panel', plane())
    before = display.data
    monkeypatch.setattr(native, 'dvz_sampled_field_update_from_array', lambda *args: None)
    with pytest.raises(RuntimeError, match='pixel update returned no handle'):
        display.update_pixels(np.full((2, 3, 4), 42, np.uint8))
    assert display.data is before
    np.testing.assert_array_equal(native.fields[display.field], before.rgba)
