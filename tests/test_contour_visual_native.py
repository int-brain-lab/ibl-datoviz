"""Retained native contours survive repeated replacement without slot exhaustion."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz.contour_geometry import ContourComponent, ContourGeometry
from ibl_datoviz.contour_visual import ContourVisual
from tests import test_component_native
from tests.test_volume_free_navigator import VOLUME

native_components = test_component_native.native_components


def geometry(count=1):
    components = []
    for _ in range(count):
        components.append(
            SimpleNamespace(
                atlas_id=-315,
                outer=np.array([[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]),
                holes=(np.array([[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]),),
            )
        )
    return SimpleNamespace(components=tuple(components))


CORNERS = np.array([[-1, -1, 0], [-1, 1, 0], [1, -1, 0], [1, 1, 0]])


def test_native_retained_replacement_holes_empty_restore_and_lifetime(native_components):
    ctx = native_components
    layer = ContourVisual(ctx.dvz, ctx.scene, ctx.panel)
    ctx.components.append(layer)
    for i in range(160):
        layer.stage(geometry(1 + i % 3), {-315: (30, 160, 90)}, np.eye(3), CORNERS)
        layer.activate()
    image = ctx.capture()
    assert len(layer._buffers) == 2
    assert max(b['count'] for b in layer._buffers) == 3
    np.testing.assert_array_equal(image[60, 80, :3], (255, 255, 255))
    np.testing.assert_array_equal(image[60, 135, :3], (30, 160, 90))
    layer.stage(geometry(0), {}, np.eye(3), CORNERS)
    layer.activate()
    np.testing.assert_array_equal(ctx.capture()[60, 135, :3], (255, 255, 255))
    layer.stage(geometry(), {-315: (210, 40, 80)}, np.eye(3), CORNERS)
    layer.activate()
    np.testing.assert_array_equal(ctx.capture()[60, 135, :3], (210, 40, 80))
    layer.close()
    layer.close()
    np.testing.assert_array_equal(ctx.capture()[60, 135, :3], (255, 255, 255))


def test_staging_failure_keeps_accepted_display(native_components, monkeypatch):
    ctx = native_components
    layer = ContourVisual(ctx.dvz, ctx.scene, ctx.panel)
    ctx.components.append(layer)
    layer.stage(geometry(), {-315: (30, 160, 90)}, np.eye(3), CORNERS)
    layer.activate()
    layer.stage(geometry(), {-315: (30, 160, 90)}, np.eye(3), CORNERS)
    layer.activate()  # Both buffers have now been attached.
    before = ctx.capture()
    moved = geometry()
    moved.components[0].outer[:, 0] -= 0.3
    moved.components[0].holes[0][:, 0] -= 0.3
    original = ctx.dvz.dvz_polygons_set_region_fill_color
    monkeypatch.setattr(ctx.dvz, 'dvz_polygons_set_region_fill_color', lambda *_: -1)
    with pytest.raises(RuntimeError, match='contour color'):
        layer.stage(moved, {-315: (210, 40, 80)}, np.eye(3), CORNERS)
    monkeypatch.setattr(ctx.dvz, 'dvz_polygons_set_region_fill_color', original)
    np.testing.assert_array_equal(ctx.capture(), before)
    layer.stage(geometry(), {-315: (210, 40, 80)}, np.eye(3), CORNERS)
    layer.activate()
    assert np.any(ctx.capture() != before)


def test_geometry_budget_rejects_before_native_change(native_components):
    ctx = native_components
    layer = ContourVisual(ctx.dvz, ctx.scene, ctx.panel, max_components=1)
    ctx.components.append(layer)
    with pytest.raises(ValueError, match='budget'):
        layer.stage(geometry(2), {-315: (30, 160, 90)}, np.eye(3), CORNERS)
    assert layer._buffers == []


def test_activation_failure_preserves_hidden_authored_visibility(native_components, monkeypatch):
    ctx = native_components
    layer = ContourVisual(ctx.dvz, ctx.scene, ctx.panel)
    ctx.components.append(layer)
    layer.stage(geometry(), {-315: (30, 160, 90)}, np.eye(3), CORNERS)
    layer.activate(visible=False)
    before = ctx.capture()
    layer.stage(geometry(), {-315: (210, 40, 80)}, np.eye(3), CORNERS)
    setter = ctx.dvz.dvz_visual_set_visible
    calls = 0

    def fail_once(*args):
        nonlocal calls
        calls += 1
        return -1 if calls == 1 else setter(*args)

    monkeypatch.setattr(ctx.dvz, 'dvz_visual_set_visible', fail_once)
    with pytest.raises(RuntimeError, match='visibility'):
        layer.activate()
    np.testing.assert_array_equal(ctx.capture(), before)
    assert layer._active_visible is False


def test_selection_only_reuses_immutable_native_geometry(native_components, monkeypatch):
    ctx = native_components
    layer = ContourVisual(ctx.dvz, ctx.scene, ctx.panel)
    ctx.components.append(layer)
    component = ContourComponent(-315, -315, [[0, 0], [1, 0], [1, 1], [0, 1]], (), False)
    empty = np.empty((0, 2))
    first = ContourGeometry('allen', (component,), empty, empty, empty, empty)
    catalog = open_volume_pack(VOLUME).load_volumes().regions
    selected = first.with_selection(catalog, (-315,))
    assert selected.components[0].outer is first.components[0].outer
    colors = {-315: (30, 160, 90)}
    layer.stage(first, colors, np.eye(3), CORNERS)
    layer.activate()
    before = ctx.capture()
    # A second style occupies the other retained buffer.
    layer.stage(selected, colors, np.eye(3), CORNERS, opacity=0.5)
    layer.activate()
    monkeypatch.setattr(
        ctx.dvz,
        'dvz_polygons_set_region_geometry',
        lambda *_: pytest.fail('cached geometry was uploaded'),
    )
    monkeypatch.setattr(
        ctx.dvz,
        'dvz_polygons_set_region_fill_color',
        lambda *_: pytest.fail('cached palette was uploaded'),
    )
    layer.stage(selected, colors, np.eye(3), CORNERS)
    layer.activate()
    np.testing.assert_array_equal(ctx.capture(), before)
    layer.stage(first, colors, np.eye(3), CORNERS)
    layer.activate()
    np.testing.assert_array_equal(ctx.capture(), before)
