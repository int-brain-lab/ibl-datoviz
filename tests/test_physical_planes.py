"""CPU contracts for physical sampled planes; rendering is tested separately."""

import ctypes

import numpy as np
import pytest

from ibl_datoviz.sampled_plane import UV, SampledPlane, SampledPlaneVisual
from tests.test_component_visuals import Native, plane


class BufferDesc(ctypes.Structure):
    _fields_ = [('usage', ctypes.c_int), ('stride', ctypes.c_uint32)]


class SamplingDesc(ctypes.Structure):
    _fields_ = [('min_filter', ctypes.c_int), ('mag_filter', ctypes.c_int)]


class MaterialDesc(ctypes.Structure):
    _fields_ = [('model', ctypes.c_int), ('alpha_mode', ctypes.c_int), ('opacity', ctypes.c_float)]


class PhysicalNative(Native):
    """Track mesh resources, descriptors, binding slots and destruction order."""

    DVZ_ALPHA_WBOIT = 2
    DVZ_ALPHA_MASK = 3
    DVZ_FIELD_FILTER_NEAREST = 0
    DVZ_FIELD_FILTER_LINEAR = 1
    DVZ_MATERIAL_MODEL_UNLIT = 0
    DVZ_SCENE_BUFFER_USAGE_INDEX = 2

    def __init__(self):
        super().__init__()
        self.buffers = {}
        self.destroyed = []

    def dvz_mesh(self, scene, flags):
        assert scene == 'borrowed scene'
        if self.status('create_mesh'):
            return None
        return self.dvz_point(scene, flags)

    def dvz_scene_buffer_desc(self):
        return BufferDesc()

    def dvz_scene_buffer(self, scene, desc):
        assert scene == 'borrowed scene'
        if self.status('create_buffer'):
            return None
        descriptor = ctypes.cast(desc, ctypes.POINTER(BufferDesc)).contents
        assert descriptor.usage == self.DVZ_SCENE_BUFFER_USAGE_INDEX
        assert descriptor.stride == np.dtype(np.uint32).itemsize
        handle = self.next_id
        self.next_id += 1
        self.buffers[handle] = None
        return handle

    def dvz_scene_buffer_set_data(self, buffer, data):
        status = self.status('index_upload')
        if status == 0:
            assert data.flags.owndata and not data.flags.writeable
            self.buffers[buffer] = np.array(data)
        return status

    def dvz_visual_set_buffer(self, visual, slot, buffer):
        assert slot == b'index' and buffer in self.buffers
        status = self.status('bind_index')
        if status == 0:
            self.visuals[visual]['index'] = buffer
        return status

    def dvz_material_desc(self):
        return MaterialDesc()

    def dvz_visual_set_material(self, visual, material):
        status = self.status('material')
        if status == 0:
            descriptor = ctypes.cast(material, ctypes.POINTER(MaterialDesc)).contents
            self.visuals[visual]['material'] = (
                descriptor.model,
                descriptor.alpha_mode,
                descriptor.opacity,
            )
        return status

    def dvz_visual_set_alpha_cutoff(self, visual, cutoff):
        status = self.status('cutoff')
        if status == 0:
            self.visuals[visual]['cutoff'] = cutoff
        return status

    def dvz_field_sampling_desc(self):
        return SamplingDesc()

    def dvz_visual_set_field_sampling(self, visual, slot, sampling):
        assert slot == b'texture'
        status = self.status('sampling')
        if status == 0:
            descriptor = ctypes.cast(sampling, ctypes.POINTER(SamplingDesc)).contents
            self.visuals[visual]['sampling'] = (descriptor.min_filter, descriptor.mag_filter)
        return status

    def dvz_visual_set_field(self, visual, slot, field):
        assert slot == b'texture' and field in self.fields
        return super().dvz_visual_set_field(visual, slot, field)

    def dvz_visual_destroy(self, visual):
        self.destroyed.append(('visual', visual))
        super().dvz_visual_destroy(visual)

    def dvz_scene_buffer_destroy(self, buffer):
        assert not any(state.get('index') == buffer for state in self.visuals.values())
        self.destroyed.append(('buffer', buffer))
        self.calls['destroy_buffer'] += 1
        del self.buffers[buffer]

    def dvz_sampled_field_destroy(self, field):
        assert not any(state.get('field') == field for state in self.visuals.values())
        self.destroyed.append(('field', field))
        super().dvz_sampled_field_destroy(field)


def physical(native, data=None, **kwargs):
    return SampledPlaneVisual(
        native,
        'borrowed scene',
        'borrowed panel',
        data,
        depth_policy='physical',
        **kwargs,
    )


@pytest.mark.parametrize('mode', ['opaque', 'blended', 'wboit', 'mask'])
def test_physical_construction_uses_texture_mesh_depth_and_honest_capabilities(mode):
    native = PhysicalNative()
    display = physical(native, plane(), alpha_mode=mode, alpha_cutoff=0.25)
    state = native.visuals[display.visual]
    assert state['depth'] is True
    assert state['material'] == (
        native.DVZ_MATERIAL_MODEL_UNLIT,
        getattr(native, f'DVZ_ALPHA_{mode.upper()}'),
        1.0,
    )
    assert state['sampling'] == (native.DVZ_FIELD_FILTER_NEAREST,) * 2
    assert state['field'] == display.field
    assert state['visible'] is True
    assert display.capabilities.alpha_modes == ('opaque', 'blended', 'wboit', 'mask')
    assert display.capabilities.depth_test and display.capabilities.sampled_plane_3d
    assert display.capabilities.depth_write == (mode in ('opaque', 'mask'))
    assert display.capabilities.order_independent == (mode == 'wboit')
    assert native.calls['create_mesh'] == native.calls['create_buffer'] == 1
    assert native.calls['alpha'] == 0
    np.testing.assert_array_equal(state['color'], np.full((4, 4), 255, np.uint8))
    np.testing.assert_array_equal(state['texcoords'], UV)
    if mode == 'mask':
        assert state['cutoff'] == 0.25 and display.alpha_cutoff == 0.25
    else:
        assert native.calls['cutoff'] == 0
    display.close()
    display.close()
    assert not native.visuals and not native.fields and not native.buffers
    assert native.calls['destroy_visual'] == native.calls['destroy_buffer'] == 1


def test_transformed_geometry_owns_storage_and_normals_follow_both_triangle_windings():
    native = PhysicalNative()
    transforms = []
    matrix = np.array([[0, 0, -2], [0, 3, 0], [-4, 0, 0]], np.float32)

    def transform(corners):
        transforms.append(corners)
        return corners @ matrix + [10, 20, 30]

    payload = plane()
    display = physical(native, payload, transform=transform)
    np.testing.assert_array_equal(
        native.visuals[display.visual]['position'], payload.corners_um @ matrix + [10, 20, 30]
    )
    indices = native.buffers[display._index_buffer].reshape(2, 3)
    geometry = display._display_geometry
    for triangle in indices:
        a, b, c = geometry['position'][triangle]
        normal = np.cross(b - a, c - a)
        np.testing.assert_allclose(
            geometry['normal'], np.tile(normal / np.linalg.norm(normal), (4, 1))
        )
    for name, array in geometry.items():
        assert array.flags.owndata and array.flags.c_contiguous and not array.flags.writeable, name
    assert not np.shares_memory(geometry['position'], payload.corners_um)
    assert len(transforms) == 1
    display.update_corners(payload.corners_um + [0, 0, 7])
    assert len(transforms) == 2 and native.calls['create_buffer'] == 1
    display.close()


@pytest.mark.parametrize('cutoff', [0, 0.5, 1])
def test_mask_cutoff_inclusive_endpoints_and_default(cutoff):
    native = PhysicalNative()
    display = physical(native, plane(), alpha_mode='mask', alpha_cutoff=cutoff)
    assert native.visuals[display.visual]['cutoff'] == cutoff
    display.close()
    display = physical(native, plane(), alpha_mode='mask')
    assert native.visuals[display.visual]['cutoff'] == 0.5
    display.close()


@pytest.mark.parametrize('cutoff', [None, 'bad', np.nan, np.inf, -0.01, 1.01])
def test_invalid_mask_cutoff_fails_before_native_allocation(cutoff):
    native = PhysicalNative()
    with pytest.raises(ValueError, match='cutoff'):
        physical(native, plane(), alpha_mode='mask', alpha_cutoff=cutoff)
    assert not native.calls


def test_invalid_alpha_and_overlay_modes_do_not_allocate():
    native = PhysicalNative()
    with pytest.raises(ValueError, match='alpha'):
        physical(native, plane(), alpha_mode='depth_peel')
    for mode in ('opaque', 'wboit', 'mask'):
        with pytest.raises(ValueError, match='overlay'):
            SampledPlaneVisual(native, 'scene', 'panel', plane(), alpha_mode=mode)
    assert not native.calls


@pytest.mark.parametrize(
    'failure',
    [
        'create_mesh',
        'create_buffer',
        'index_upload',
        'bind_index',
        'material',
        'cutoff',
        'depth',
        'batch',
        'create_field',
        'field_upload',
        'bind_field',
        'sampling',
        'visible',
        'attach',
    ],
)
def test_failed_constructor_releases_mesh_index_and_field_without_borrowed_handles(failure):
    native = PhysicalNative()
    native.fail = failure
    with pytest.raises(RuntimeError):
        physical(native, plane(), alpha_mode='mask')
    assert not native.visuals and not native.fields and not native.buffers


def test_updates_retain_index_and_visual_resize_fields_and_restore_authored_visibility():
    native = PhysicalNative()
    display = physical(native, alpha_mode='mask', alpha_cutoff=0.7)
    assert not native.calls
    display.set_visible(False)
    display.replace(plane())
    visual, index, field = display.visual, display._index_buffer, display.field
    display.update_corners(display.data.corners_um + [2, 0, 0])
    assert display.field == field and native.calls['pixels'] == 0
    display.update_pixels(np.full((2, 3, 4), 90, np.uint8))
    assert display.field == field and native.calls['pixels'] == 1
    for width in (4, 1, 6, 2):
        display.update_pixels(np.full((2, width, 4), width, np.uint8))
        assert len(native.fields) == len(native.buffers) == len(native.visuals) == 1
    display.replace(None)
    display.set_visible(True)
    assert native.visuals[visual]['visible'] is False
    display.replace(plane())
    assert native.visuals[visual]['visible'] is True
    assert native.visuals[visual]['cutoff'] == 0.7
    assert display.visual == visual and display._index_buffer == index
    assert native.calls['create_mesh'] == native.calls['create_buffer'] == 1
    display.replace(
        SampledPlane.from_arrays(display.data.corners_um, display.data.rgba, sampling='linear')
    )
    assert native.visuals[visual]['sampling'] == (native.DVZ_FIELD_FILTER_LINEAR,) * 2
    display.close()
    assert not native.visuals and not native.fields and not native.buffers


@pytest.mark.parametrize(
    ('resized', 'failure'),
    [(True, failure) for failure in ('batch', 'field_upload', 'bind_field', 'sampling', 'visible')]
    + [(False, failure) for failure in ('batch', 'sampling', 'visible')],
)
def test_replacement_rolls_back_geometry_pixels_sampling_binding_and_visibility(resized, failure):
    native = PhysicalNative()
    transforms = []

    def transform(corners):
        transforms.append(corners)
        return corners * 2

    display = physical(native, plane(), transform=transform, alpha_mode='mask', alpha_cutoff=0.8)
    before, field, index = display.data, display.field, display._index_buffer
    snapshot = dict(native.visuals[display.visual])
    replacement = SampledPlane.from_arrays(
        before.corners_um + [0, 0, 3],
        np.full((4, 5, 4) if resized else before.rgba.shape, 20, np.uint8),
        sampling='linear',
    )
    native.fail = failure
    with pytest.raises(RuntimeError):
        display.replace(replacement)
    assert display.data is before and display.field == field and display._index_buffer == index
    state = native.visuals[display.visual]
    for key in ('position', 'normal', 'color', 'texcoords'):
        np.testing.assert_array_equal(state[key], snapshot[key])
    for key in ('field', 'index', 'sampling', 'visible', 'cutoff'):
        assert state[key] == snapshot[key]
    np.testing.assert_array_equal(native.fields[field], before.rgba)
    assert len(transforms) == 2  # Rollback reuses the transformed snapshot.
    assert len(native.fields) == len(native.visuals) == len(native.buffers) == 1
    display.close()


def test_failed_in_place_upload_restores_pixels_even_if_native_mutated_before_failure(monkeypatch):
    native = PhysicalNative()
    display = physical(native, plane())
    before = display.data

    def mutate_then_fail(field, pixels):
        native.fields[field] = np.array(pixels)

    monkeypatch.setattr(native, 'dvz_sampled_field_update_from_array', mutate_then_fail)
    with pytest.raises(RuntimeError, match='pixel update returned no handle'):
        display.update_pixels(np.full(before.rgba.shape, 150, np.uint8))
    assert display.data is before
    np.testing.assert_array_equal(native.fields[display.field], before.rgba)
    display.close()


def test_partially_failed_geometry_upload_restores_all_vertex_attributes(monkeypatch):
    native = PhysicalNative()
    display = physical(native, plane())
    before = display.data
    snapshot = dict(display._display_geometry)
    upload = native.dvz_visual_set_data_many
    failed = False

    def mutate_then_fail_once(visual, geometry):
        nonlocal failed
        if not failed:
            failed = True
            native.visuals[visual]['position'] = np.array(geometry['position'])
            native.visuals[visual]['normal'] = np.zeros_like(geometry['normal'])
            return -1
        return upload(visual, geometry)

    monkeypatch.setattr(native, 'dvz_visual_set_data_many', mutate_then_fail_once)
    with pytest.raises(RuntimeError, match='plane geometry failed'):
        display.update_corners(before.corners_um + [1, 2, 3])
    assert display.data is before
    for key, array in snapshot.items():
        np.testing.assert_array_equal(native.visuals[display.visual][key], array)
    display.close()


def test_failed_rollback_closes_component_and_releases_old_and_candidate_fields(monkeypatch):
    native = PhysicalNative()
    display = physical(native, plane())
    monkeypatch.setattr(native, 'dvz_visual_set_field_sampling', lambda *args: -1)
    with pytest.raises(RuntimeError, match='rollback failed; component closed'):
        display.replace(plane((4, 5, 4), 15))
    assert not native.visuals and not native.buffers and not native.fields
    with pytest.raises(RuntimeError, match='closed'):
        display.replace(plane())


@pytest.mark.parametrize('mutation', ['warped', 'collapsed'])
def test_nonplanar_or_degenerate_display_transform_fails_before_native_allocation(mutation):
    native = PhysicalNative()

    def transform(corners):
        positions = corners.copy()
        if mutation == 'warped':
            positions[3, 2] += 1
        else:
            positions[:, 1] = 0
        return positions

    with pytest.raises(ValueError, match='planar plane'):
        physical(native, plane(), transform=transform)
    assert not native.calls


def test_existing_hidden_snapshot_survives_failed_restore():
    native = PhysicalNative()
    display = physical(native, plane())
    field = display.field
    display.replace(None)
    native.fail = 'visible'
    with pytest.raises(RuntimeError):
        display.replace(plane((4, 5, 4), 15))
    assert display.data is None and display.field == field
    assert native.visuals[display.visual]['visible'] is False
    display.replace(plane())
    display.close()


def test_failed_creation_from_empty_can_retry_without_leaking_index_buffer():
    native = PhysicalNative()
    display = physical(native)
    native.fail = 'attach'
    with pytest.raises(RuntimeError):
        display.replace(plane())
    assert not native.visuals and not native.buffers and not native.fields
    display.replace(plane())
    assert display.visual and display.field and display._index_buffer
    display.close()
