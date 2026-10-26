"""Controlled native captures for RC4 scientific point and sampled-plane rendering."""

import numpy as np

from ibl_datoviz.components import (
    PointCollection,
    PointCollectionVisual,
    SampledPlane,
    SampledPlaneVisual,
)
from tests import test_component_native

native_components = test_component_native.native_components


def rectangle(z=0, extent=0.8):
    return np.asarray(
        [[-extent, extent, z], [-extent, -extent, z], [extent, extent, z], [extent, -extent, z]],
        dtype=np.float32,
    )


def sampled_plane(color=(255, 0, 0, 128), *, z=0, extent=0.8, shape=(2, 4)):
    return SampledPlane.from_arrays(
        rectangle(z, extent), np.tile(np.asarray(color, np.uint8), (*shape, 1))
    )


def points(positions=((0, 0, 0),), color=(255, 0, 0, 128), size=52):
    positions = np.asarray(positions, np.float32).reshape((-1, 3))
    return PointCollection.from_arrays(
        positions, np.tile(np.asarray(color, np.uint8), (len(positions), 1)), sizes_px=size
    )


def add_plane(context, data, **kwargs):
    display = SampledPlaneVisual(context.dvz, context.scene, context.panel, data, **kwargs)
    context.components.append(display)
    return display


def add_points(context, data):
    display = PointCollectionVisual(
        context.dvz, context.scene, context.panel, data, alpha_mode='wboit'
    )
    context.components.append(display)
    return display


class MeshControl:
    """An unlit ordinary mesh reference, owned only by the test fixture."""

    def __init__(self, context, color, *, z=0, extent=0.8, alpha_mode='opaque'):
        self.dvz = context.dvz
        self.visual = self.dvz.dvz_mesh(context.scene, 0)
        assert self.visual
        context.components.append(self)
        mode = getattr(self.dvz, f'DVZ_ALPHA_{alpha_mode.upper()}')
        material = self.dvz.dvz_material_desc()
        material.model = self.dvz.DVZ_MATERIAL_MODEL_UNLIT
        material.alpha_mode = mode
        assert self.dvz.dvz_visual_set_material(self.visual, material) == 0
        corners = rectangle(z, extent)
        assert (
            self.dvz.dvz_visual_set_data_many(
                self.visual,
                {
                    'position': corners,
                    'normal': np.tile(np.array([0, 0, 1], np.float32), (4, 1)),
                    'color': np.tile(np.asarray(color, np.uint8), (4, 1)),
                },
            )
            == 0
        )
        assert (
            self.dvz.dvz_visual_set_index_data(
                self.visual, np.asarray([0, 1, 2, 2, 1, 3], np.uint32)
            )
            == 0
        )
        assert self.dvz.dvz_visual_set_alpha_mode(self.visual, mode) == 0
        assert self.dvz.dvz_visual_set_depth_test(self.visual, True) == 0
        assert self.dvz.dvz_panel_add_visual(context.panel, self.visual, None) == 0

    def set_visible(self, visible):
        assert self.dvz.dvz_visual_set_visible(self.visual, visible) == 0

    def close(self):
        if self.visual:
            self.dvz.dvz_visual_destroy(self.visual)
            self.visual = None


def assert_changed(first, second, minimum=100):
    assert np.count_nonzero(np.any(first[..., :3] != second[..., :3], axis=2)) > minimum


def test_native_mixed_wboit_order_independence_and_layer_contributions(native_components):
    context = native_components

    def create_layers(reverse):
        factories = (
            lambda: add_points(context, points()),
            lambda: add_plane(
                context,
                sampled_plane((0, 255, 0, 90), z=-0.1),
                depth_policy='physical',
                alpha_mode='wboit',
            ),
            lambda: MeshControl(context, (0, 0, 255, 100), z=0.2, alpha_mode='wboit'),
        )
        return [create() for create in (factories[::-1] if reverse else factories)]

    blank = context.capture()
    layers = create_layers(False)
    forward = context.capture()
    assert_changed(forward, blank)
    # Every family must contribute to the same overlap, so a blank or omitted
    # layer cannot satisfy the order comparison accidentally.
    for layer in layers:
        layer.set_visible(False)
        hidden = context.capture()
        assert_changed(forward, hidden)
        layer.set_visible(True)
        if isinstance(layer, SampledPlaneVisual):
            pixels = layer.data.rgba.copy()
            pixels[..., 3] = 0
            layer.update_pixels(pixels)
            np.testing.assert_array_equal(context.capture(), hidden)
            layer.update_pixels(sampled_plane((0, 255, 0, 90)).rgba)
    for layer in reversed(layers):
        layer.close()
    np.testing.assert_array_equal(context.capture(), blank)
    create_layers(True)
    reverse = context.capture()
    assert np.max(np.abs(forward.astype(np.int16) - reverse.astype(np.int16))) <= 2


def test_native_physical_plane_depth_and_default_overlay(native_components):
    context = native_components
    MeshControl(context, (0, 0, 255, 255), z=-0.3)
    foreground = context.capture()
    assert np.all(foreground[60, 80, :3] == [0, 0, 255])
    physical = add_plane(
        context,
        sampled_plane((255, 0, 0, 255), z=0.3, extent=0.7),
        depth_policy='physical',
        alpha_mode='opaque',
    )
    np.testing.assert_array_equal(context.capture(), foreground)
    physical.update_corners(rectangle(-0.5, 0.7))
    nearer = context.capture()
    assert_changed(nearer, foreground)
    assert np.all(nearer[60, 80, :3] == [255, 0, 0])
    physical.close()
    np.testing.assert_array_equal(context.capture(), foreground)
    # The existing default remains an overlay even behind the opaque mesh.
    add_plane(context, sampled_plane((255, 0, 0, 255), z=0.3, extent=0.7))
    assert np.all(context.capture()[60, 80, :3] == [255, 0, 0])


def test_native_mask_holes_cutoff_equality_and_effective_zero_alpha(native_components):
    context = native_components
    rgba = np.tile(np.array([255, 0, 0, 255], np.uint8), (2, 4, 1))
    rgba[..., 3] = [0, 64, 128, 255]
    data = SampledPlane.from_arrays(rectangle(-0.4), rgba)
    display = add_plane(
        context, data, depth_policy='physical', alpha_mode='mask', alpha_cutoff=128 / 255
    )
    # Attach the rear mesh second: surviving mask pixels must also write depth.
    MeshControl(context, (0, 0, 255, 255), z=0.4)
    display.set_visible(False)
    rear = context.capture()
    display.set_visible(True)
    masked = context.capture()
    xs = [32, 64, 96, 128]
    np.testing.assert_array_equal(masked[60, xs[:2]], rear[60, xs[:2]])
    np.testing.assert_array_equal(masked[60, xs[2:], :3], [[255, 0, 0], [255, 0, 0]])

    # Material opacity multiplies texture alpha, while retaining the cutoff.
    material = context.dvz.dvz_material_desc()
    material.model = context.dvz.DVZ_MATERIAL_MODEL_UNLIT
    material.alpha_mode = context.dvz.DVZ_ALPHA_MASK
    material.opacity = 0.5
    assert context.dvz.dvz_visual_set_material(display.visual, material) == 0
    np.testing.assert_array_equal(context.capture(), rear)
    material.opacity = 0
    assert context.dvz.dvz_visual_set_material(display.visual, material) == 0
    np.testing.assert_array_equal(context.capture(), rear)
    display.close()

    # Zero cutoff still discards zero alpha; one cutoff retains alpha equality.
    for cutoff, surviving in ((0, [False, True, True, True]), (1, [False, False, False, True])):
        control = add_plane(
            context, data, depth_policy='physical', alpha_mode='mask', alpha_cutoff=cutoff
        )
        capture = context.capture()
        for x, survives in zip(xs, surviving, strict=True):
            expected = [255, 0, 0] if survives else rear[60, x, :3]
            np.testing.assert_array_equal(capture[60, x, :3], expected)
        control.close()


def test_native_wboit_point_updates_zero_alpha_empty_and_restore(native_components):
    context = native_components
    MeshControl(context, (0, 0, 255, 255), z=0.4)
    rear = context.capture()
    data = points(((0, 0, -0.2),), size=42)
    display = add_points(context, data)
    baseline = context.capture()
    assert_changed(baseline, rear)
    display.update_colors([[255, 0, 0, 0]])
    np.testing.assert_array_equal(context.capture(), rear)
    display.set_visible(False)
    np.testing.assert_array_equal(context.capture(), rear)
    display.set_visible(True)
    display.update_colors(data.colors)
    np.testing.assert_array_equal(context.capture(), baseline)
    display.update_sizes([66])
    assert_changed(context.capture(), baseline)
    display.replace(points(((-0.3, 0, -0.2), (0.3, 0, -0.2)), size=32))
    assert_changed(context.capture(), baseline)
    display.replace(points(()))
    np.testing.assert_array_equal(context.capture(), rear)
    display.replace(data)
    np.testing.assert_array_equal(context.capture(), baseline)
    # An opaque foreground occludes WBOIT points as well as sampled surfaces.
    MeshControl(context, (0, 255, 0, 255), z=-0.5)
    display.set_visible(False)
    front = context.capture()
    display.set_visible(True)
    np.testing.assert_array_equal(context.capture(), front)


def test_native_physical_plane_resize_geometry_empty_restore_and_caller_lifetime(
    native_components,
):
    context = native_components
    MeshControl(context, (0, 0, 255, 255), z=0.4)
    rear = context.capture()
    data = sampled_plane((255, 0, 0, 128), z=-0.2, extent=0.6)
    display = add_plane(context, data, depth_policy='physical', alpha_mode='wboit')
    baseline = context.capture()
    assert_changed(baseline, rear)
    display.update_pixels(sampled_plane((255, 0, 0, 128), shape=(5, 9)).rgba)
    np.testing.assert_array_equal(context.capture(), baseline)
    display.update_corners(rectangle(0.6, 0.6))
    np.testing.assert_array_equal(context.capture(), rear)
    display.update_corners(data.corners_um)
    np.testing.assert_array_equal(context.capture(), baseline)
    display.update_pixels(sampled_plane((0, 255, 0, 128), shape=(5, 9)).rgba)
    recolored = context.capture()
    assert_changed(recolored, baseline)
    display.update_corners(rectangle(-0.2, 0.3))
    assert_changed(context.capture(), recolored)
    display.replace(None)
    np.testing.assert_array_equal(context.capture(), rear)
    display.replace(data)
    np.testing.assert_array_equal(context.capture(), baseline)
    display.close()
    display.close()
    np.testing.assert_array_equal(context.capture(), rear)
    # Construct and render another component in the borrowed scene after close.
    survivor = add_plane(context, data, depth_policy='physical', alpha_mode='wboit')
    np.testing.assert_array_equal(context.capture(), baseline)
    survivor.close()
    np.testing.assert_array_equal(context.capture(), rear)
