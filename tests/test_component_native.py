"""Native pixel and retained-range checks for independent components."""

import ctypes
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import (
    PointCollection,
    PointCollectionVisual,
    SampledPlane,
    SampledPlaneVisual,
)


@pytest.fixture
def native_components():
    scene = app = None
    components = []
    try:
        try:
            import datoviz as dvz  # noqa: PLC0415 - unavailable native runtime is a fixture skip.

            scene = dvz.dvz_scene()
            assert scene
            figure = dvz.dvz_figure(scene, 160, 120, 0)
            assert figure
            panel = dvz.dvz_panel_full(figure)
            assert panel
            assert dvz.dvz_panel_set_background_color(panel, dvz.DvzColor(255, 255, 255, 255)) == 0
            app = dvz.dvz_app(scene)
            if not app:
                pytest.skip('Datoviz native runtime or GPU context is unavailable')
            view = dvz.dvz_view_offscreen(app, figure, 160, 120)
            assert view
        except RuntimeError as error:
            if 'Unable to load libdatoviz' in str(error):
                pytest.skip('Datoviz native runtime or GPU context is unavailable')
            raise

        def capture():
            assert dvz.dvz_view_render_once(view) == 0
            pixels = np.array(dvz.dvz_view_capture_rgba(view), copy=True)
            assert pixels.shape == (120, 160, 4) and pixels.dtype == np.uint8
            return pixels

        yield SimpleNamespace(
            dvz=dvz, scene=scene, panel=panel, capture=capture, components=components
        )
    finally:
        for component in reversed(components):
            component.close()
        if app:
            dvz.dvz_app_destroy(app)
        if scene:
            dvz.dvz_scene_destroy(scene)


def point_payload(count):
    positions = np.zeros((count, 3), np.float32)
    positions[:, 0] = np.linspace(-0.8, -0.2, count)
    return PointCollection.from_arrays(
        positions, np.tile(np.array([220, 30, 30, 255], np.uint8), (count, 1)), sizes_px=15
    )


def plane_payload(shape=(2, 3, 4), color=(20, 180, 40, 255)):
    return SampledPlane.from_arrays(
        [[0.1, 0.7, 0], [0.1, -0.7, 0], [0.8, 0.7, 0], [0.8, -0.7, 0]],
        np.tile(np.asarray(color, np.uint8), (*shape[:2], 1)),
    )


def assert_retained_count(dvz, visual, count):
    item_range = dvz.DvzItemRange()
    assert dvz.dvz_visual_get_item_range(visual, ctypes.byref(item_range))
    assert item_range.first_item == 0 and item_range.item_count == count


def test_native_point_replacement_color_visibility_and_empty_restore(native_components):
    context = native_components
    display = PointCollectionVisual(context.dvz, context.scene, context.panel, point_payload(3))
    context.components.append(display)
    plane = SampledPlaneVisual(context.dvz, context.scene, context.panel, plane_payload())
    context.components.append(plane)
    baseline = context.capture()
    assert np.count_nonzero(np.any(baseline[..., :3] != 255, axis=2)) > 100
    assert_retained_count(context.dvz, display.visual, 3)
    display.update_colors(np.tile([30, 30, 220, 255], (3, 1)))
    recolored = context.capture()
    assert np.count_nonzero(baseline != recolored) > 30
    display.set_visible(False)
    hidden = context.capture()
    assert np.count_nonzero(hidden != recolored) > 30
    display.set_visible(True)
    np.testing.assert_array_equal(context.capture(), recolored)
    for count in (1, 6):
        display.replace(point_payload(count))
        assert_retained_count(context.dvz, display.visual, count)
        assert not np.array_equal(context.capture(), hidden)
    display.replace(point_payload(0))
    np.testing.assert_array_equal(context.capture(), hidden)
    display.replace(point_payload(3))
    np.testing.assert_array_equal(context.capture(), baseline)
    display.close()
    display.close()
    # Caller scene/panel/app remain usable, and the closed component no longer draws.
    np.testing.assert_array_equal(context.capture(), hidden)


def test_native_plane_field_update_resize_empty_and_close(native_components):
    context = native_components
    display = SampledPlaneVisual(context.dvz, context.scene, context.panel, plane_payload())
    context.components.append(display)
    baseline = context.capture()
    assert np.count_nonzero(np.any(baseline[..., :3] != 255, axis=2)) > 100
    old_field = context.dvz.dvz_sampled_field_id(display.field)
    display.update_pixels(plane_payload(color=(40, 50, 210, 255)).rgba)
    assert context.dvz.dvz_sampled_field_id(display.field) == old_field
    recolored = context.capture()
    assert np.count_nonzero(recolored != baseline) > 100
    display.update_pixels(plane_payload((5, 7, 4), (40, 50, 210, 255)).rgba)
    assert context.dvz.dvz_sampled_field_id(display.field) != old_field
    np.testing.assert_array_equal(context.capture(), recolored)
    display.set_visible(False)
    hidden = context.capture()
    assert np.all(hidden[..., :3] == 255)
    display.set_visible(True)
    np.testing.assert_array_equal(context.capture(), recolored)
    display.replace(None)
    np.testing.assert_array_equal(context.capture(), hidden)
    display.replace(plane_payload())
    np.testing.assert_array_equal(context.capture(), baseline)
    display.close()
    display.close()
    np.testing.assert_array_equal(context.capture(), hidden)
