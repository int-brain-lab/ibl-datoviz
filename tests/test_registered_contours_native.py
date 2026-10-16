"""Native component/hole rendering for the isolated contour prototype."""

import ctypes
from types import SimpleNamespace

import numpy as np

from examples.registered_contours import add_contours, polygon_descriptor
from tests import test_component_native

native_components = test_component_native.native_components


def square(low, high):
    return np.array([[low, low], [high, low], [high, high], [low, high], [low, low]], np.float64)


def test_prototype_detaches_geometry_and_preserves_holes_islands_and_signed_ids(native_components):
    context = native_components
    outer, hole, island = square(-0.8, 0.8), square(-0.5, 0.5), square(-0.15, 0.15)
    paths = (
        SimpleNamespace(atlas_ids={'allen': -315}, components=(
            SimpleNamespace(outer=outer, holes=(hole,)),
        )),
        SimpleNamespace(atlas_ids={'allen': 315}, components=(
            SimpleNamespace(outer=island, holes=()),
        )),
    )
    _, identities = add_contours(
        context.dvz, context.scene, context.panel, paths,
        {-315: (30, 160, 90), 315: (210, 40, 80)}, stroke_width=0,
    )
    assert identities == (-315, 315)
    # The prototype must detach from the caller's original source arrays.
    for ring in (outer, hole, island):
        ring[:] = 100
    pixels = context.capture()
    np.testing.assert_array_equal(pixels[60, 80, :3], (210, 40, 80))  # nested island
    np.testing.assert_array_equal(pixels[60, 105, :3], (255, 255, 255))  # hole
    np.testing.assert_array_equal(pixels[60, 135, :3], (30, 160, 90))  # exterior
    np.testing.assert_array_equal(pixels[2, 2, :3], (255, 255, 255))


def test_native_set_copies_borrowed_descriptor_buffers_before_render(native_components):
    context = native_components
    dvz = context.dvz
    desc, (buffers, holes) = polygon_descriptor(
        dvz, SimpleNamespace(outer=square(-0.8, 0.8), holes=(square(-0.5, 0.5),))
    )
    polygons = dvz.dvz_polygons(context.scene, 0)
    assert polygons
    assert dvz.dvz_polygons_add_region(polygons, ctypes.byref(desc)) == 0
    assert dvz.dvz_polygons_set_region_fill_color(
        polygons, 0, dvz.DvzColor(30, 160, 90, 255)
    ) == 0
    assert dvz.dvz_polygons_set_region_stroke_width_px(polygons, 0, 0) == 0
    composite = dvz.dvz_polygons_composite(polygons, 0)
    assert composite
    material = dvz.dvz_material_desc()
    material.model = dvz.DVZ_MATERIAL_MODEL_UNLIT
    assert dvz.dvz_visual_set_material(dvz.dvz_composite_visual(composite, b'fill'), material) == 0
    assert dvz.dvz_panel_add_composite(context.panel, composite, None) == 0
    # Mutate the actual descriptor buffers, not only the original source rings.
    for ring in buffers:
        ring[:] = 100
    del desc, buffers, holes
    pixels = context.capture()
    np.testing.assert_array_equal(pixels[60, 80, :3], (255, 255, 255))
    np.testing.assert_array_equal(pixels[60, 135, :3], (30, 160, 90))


def test_descriptor_changes_only_display_y_and_keeps_source_buffers(native_components):
    ring = square(1, 3)
    before = ring.copy()
    desc, (buffers, holes) = polygon_descriptor(
        native_components.dvz, SimpleNamespace(outer=ring, holes=())
    )
    assert desc.outer.count == len(ring) and desc.hole_count == len(holes) == 0
    np.testing.assert_array_equal(ring, before)
    np.testing.assert_array_equal(buffers[0][:, 0], ring[:, 0])
    np.testing.assert_array_equal(buffers[0][:, 1], -ring[:, 1])
