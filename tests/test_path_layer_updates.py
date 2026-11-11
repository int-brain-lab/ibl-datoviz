"""Retained path mutations preserve handles and recover partial collection writes."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import Paths
from tests.test_layer_attributes import registry as attribute_registry
from tests.test_owned_layers import FRAME

registry = attribute_registry


def add_paths(layers):
    return layers.add_paths(
        Paths(
            ('first', 'missing', 'last'),
            (np.ones((2, 3)), np.full((2, 3), np.nan), np.full((3, 3), 2.0)),
            FRAME,
            {},
        )
    )


def snapshots(route, native):
    return {
        key: {
            name: values.copy()
            for name, values in native.visuals[item.visual].items()
            if isinstance(values, np.ndarray)
        }
        for key, item in route._visual._insertions.items()
    }


def assert_native_equal(route, native, expected):
    for key, values in expected.items():
        for name, value in values.items():
            np.testing.assert_array_equal(
                native.visuals[route._visual._insertions[key].visual][name], value
            )


def test_color_width_and_selection_preserve_path_handles_gaps_visibility_and_queries(registry):
    layers, native, transforms, _guards = registry
    registered, unregistered = [], []
    layers.viewer.picking = SimpleNamespace(
        register=lambda *args: registered.append(args),
        unregister=lambda *args: unregistered.append(args),
        invalidate=lambda: None,
    )
    native.dvz_path_set_endpoint_gaps = lambda *_args: 0
    route = add_paths(layers)
    route.set_endpoint_gaps_px(4, 6)
    route.set_visible(False)
    component = route._visual
    items = dict(component._insertions)
    positions = {key: item.display_positions for key, item in items.items()}
    allocations = native.calls['create_visual']
    destructions = native.calls['destroy_visual']
    registrations = len(registered), len(unregistered)
    transformed = len(transforms)
    native.arm_attributes()
    route.set_color('#112233')
    route.set_width_px(9)
    layers.update_selection((route.refs[1], route.refs[2]))
    assert route._visual is component and component._insertions.keys() == items.keys()
    for key, item in items.items():
        assert component._insertions[key] is item
        assert item.display_positions is positions[key]
        assert item.endpoint_gaps_px == (4, 6) and not item.visible
        assert item.data.width_px == 9
    np.testing.assert_array_equal(items[1].data.color, (17, 34, 51, 255))
    np.testing.assert_array_equal(items[3].data.color, (255, 70, 180, 255))
    assert native.calls['create_visual'] == allocations
    assert native.calls['destroy_visual'] == destructions
    assert (len(registered), len(unregistered)) == registrations
    assert len(transforms) == transformed and 'position' not in native.attribute_writes
    layers.update_selection(())
    for item in items.values():
        np.testing.assert_array_equal(item.data.color, (17, 34, 51, 255))
    native.arm_attributes()
    layers.update_selection((route.refs[1],))
    layers.update_selection(())
    assert not native.attribute_writes


@pytest.mark.parametrize('missing_row', [0, 1, 2])
def test_compact_colors_follow_original_path_keys_with_missing_rows(registry, missing_row):
    layers, native, _transforms, _guards = registry
    positions = [np.full((2, 3), row + 1.0) for row in range(3)]
    positions[missing_row][:] = np.nan
    route = layers.add_paths(Paths(('a', 'b', 'c'), tuple(positions), FRAME, {}))
    positioned = [row for row in range(3) if row != missing_row]
    route.set_color('#123456')
    layers.update_selection((route.refs[positioned[-1]], route.refs[missing_row]))
    for row in positioned:
        item = route._visual._insertions[row + 1]
        expected = (255, 70, 180, 255) if row == positioned[-1] else (18, 52, 86, 255)
        np.testing.assert_array_equal(native.visuals[item.visual]['color'], [expected] * 2)


@pytest.mark.parametrize('attribute', ['color', 'stroke_width_px'])
def test_partial_second_path_attribute_failure_restores_every_attempted_path(registry, attribute):
    layers, native, _transforms, _guards = registry
    route = add_paths(layers)
    component, colors, size = route._visual, route._colors, route._size
    before = snapshots(route, native)
    native.arm_attributes(**{attribute: (2,)})
    with pytest.raises(RuntimeError, match='insertion'):
        route.set_color('#123456') if attribute == 'color' else route.set_width_px(12)
    assert route._visual is component and route._colors is colors and route._size == size
    assert not layers.viewer.closed
    assert_native_equal(route, native, before)


@pytest.mark.parametrize('attribute', ['color', 'stroke_width_px'])
def test_deleted_path_after_failed_local_restoration_closes_owner(registry, attribute):
    layers, native, _transforms, _guards = registry
    route = add_paths(layers)
    native.arm_attributes(**{attribute: (2, 3)})
    with pytest.raises(RuntimeError, match='path attributes rollback failed; owner closed'):
        route.set_color('#123456') if attribute == 'color' else route.set_width_px(12)
    assert route._closed and route._visual._closed and layers.viewer.closed
    assert not native.visuals
