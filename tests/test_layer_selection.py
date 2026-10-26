"""Atomic retained selection highlights, exact attachment indexes and failure recovery."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import Channels, Clusters, Paths, Recording
from ibl_datoviz.layers import LayerHandle, LayerObservationRef, LayerRegistry
from tests.test_layer_attributes import (
    AttributeNative,
    display_positions,
    displayed_colors,
    payload,
)
from tests.test_owned_layers import FRAME, SOURCE


@pytest.fixture
def registry():
    native, transforms, guards = AttributeNative(), [], []

    def normalize(positions):
        transforms.append(positions)
        return positions * 0.1

    owner = SimpleNamespace(
        dvz=native,
        scene='scene',
        panel='panel',
        closed=False,
        mesh_data=SimpleNamespace(normalize_points=normalize, display_scale=0.1),
    )
    layers = LayerRegistry(owner, before_mutation=lambda: guards.append(True))

    def close():
        layers.close()
        owner.closed = True

    owner.close = close
    yield layers, native, transforms, guards
    layers.close()


def points(layers, glyph='point'):
    return layers.add_points(payload(source=True), glyph=glyph)


def paths(layers):
    return layers.add_paths(Paths(('path',), (np.ones((2, 3)),), FRAME, {}))


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_selection_retains_visual_geometry_and_authored_scalar_encoding(
    registry, monkeypatch, glyph
):
    layers, native, transforms, _guards = registry
    layer = points(layers, glyph)
    authored = np.asarray([[1, 2, 3, 40], [128, 128, 128, 255], [4, 5, 6, 40]], np.uint8)
    monkeypatch.setattr(layers, '_scalar_colors', lambda *_: authored)
    layer.color_by(
        [1, np.nan, 3],
        name='Rate',
        units='Hz',
        cmap='viridis',
        limits=(0, 10),
        observation_refs=layer.payload.observation_keys,
    )
    component, positions, encoding = layer._visual, display_positions(layer), layer.scalar_encoding
    creation, batches, transformed = (
        native.calls['create_visual'],
        native.calls['batch'],
        len(transforms),
    )
    native.arm_attributes()
    selected = (
        layer.observation('first'),
        layer.observation('missing'),
        layer.observation('last'),
    )
    layers.update_selection(selected)
    assert layer._visual is component and display_positions(layer) is positions
    assert layer._selected == frozenset(selected)
    np.testing.assert_array_equal(displayed_colors(layer), [[255, 70, 180, 255]] * 2)
    if glyph == 'sphere':
        assert component._alpha_mode == native.DVZ_ALPHA_OPAQUE
    layers.update_selection(())
    assert layer._visual is component and display_positions(layer) is positions
    assert not layer._selected and layer.scalar_encoding is encoding and layer._colors is authored
    np.testing.assert_array_equal(displayed_colors(layer), authored[[0, 2]])
    if glyph == 'sphere':
        assert component._alpha_mode == native.DVZ_ALPHA_WBOIT
    assert native.calls['create_visual'] == creation and native.calls['destroy_visual'] == 0
    assert native.calls['batch'] == batches and len(transforms) == transformed
    assert 'position' not in native.attribute_writes


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_missing_only_and_repeated_selection_never_uploads_colors(registry, glyph):
    layers, native, _transforms, _guards = registry
    layer = points(layers, glyph)
    component = layer._visual
    layer.set_visible(False)
    native.arm_attributes()
    missing = layer.observation('missing')
    layers.update_selection((missing,))
    layers.update_selection((missing, missing))
    assert layer._selected == frozenset((missing,)) and not layer.visible
    layers.update_selection(())
    assert not layer._selected and layer._visual is component
    assert not native.attribute_writes


def test_same_original_ids_in_distinct_attachments_have_independent_selection(registry):
    layers, native, _transforms, _guards = registry
    first, second = points(layers), points(layers)
    assert first.observation('first') != second.observation('first')
    layers.update_selection((first.observation('first'), second.observation('missing')))
    assert first._selected == frozenset((first.observation('first'),))
    assert second._selected == frozenset((second.observation('missing'),))
    np.testing.assert_array_equal(displayed_colors(first)[0], [255, 70, 180, 255])
    np.testing.assert_array_equal(displayed_colors(second), [[64, 220, 250, 255]] * 2)
    foreign = LayerObservationRef('another-attachment', 'first', first.refs[0].source_key)
    native.arm_attributes()
    with pytest.raises(ValueError, match='foreign or removed'):
        layers.update_selection((first.observation('first'), foreign))
    assert not native.attribute_writes


def test_partial_second_layer_failure_restores_both_native_displays_and_selection(registry):
    layers, native, _transforms, _guards = registry
    first, second = points(layers), points(layers)
    components = first._visual, second._visual
    before = [displayed_colors(layer).copy() for layer in (first, second)]
    native.arm_attributes(color=(2,))
    with pytest.raises(RuntimeError, match='point colors'):
        layers.update_selection((first.observation('first'), second.observation('last')))
    assert not first._selected and not second._selected
    assert (first._visual, second._visual) == components
    for layer, colors in zip((first, second), before, strict=True):
        np.testing.assert_array_equal(displayed_colors(layer), colors)
        np.testing.assert_array_equal(native.visuals[layer._visual.visual]['color'], colors)
    assert not layers.viewer.closed


def test_sphere_alpha_failure_restores_prior_point_and_sphere_policy(registry):
    layers, native, _transforms, _guards = registry
    first, second = points(layers), points(layers, 'sphere')
    second.set_color('#11223344')
    before = [displayed_colors(layer).copy() for layer in (first, second)]
    components = first._visual, second._visual
    native.arm_attributes(alpha=(1,))
    with pytest.raises(RuntimeError, match='sphere alpha'):
        layers.update_selection((first.refs[0], second.refs[0], second.refs[2]))
    assert not first._selected and not second._selected
    assert (first._visual, second._visual) == components
    assert second._visual._alpha_mode == native.DVZ_ALPHA_WBOIT
    assert native.visuals[second._visual.visual]['alpha_mode'] == native.DVZ_ALPHA_WBOIT
    for layer, colors in zip((first, second), before, strict=True):
        np.testing.assert_array_equal(native.visuals[layer._visual.visual]['color'], colors)


def test_path_candidate_failure_precedes_any_live_point_color_write(registry):
    layers, native, _transforms, _guards = registry
    point, route = points(layers), paths(layers)
    old_point, old_route = point._visual, route._visual
    native.arm_attributes()
    native.fail = 'batch'
    with pytest.raises(RuntimeError, match='insertion upload'):
        layers.update_selection((point.refs[0], route.refs[0]))
    assert point._visual is old_point and route._visual is old_route
    assert not point._selected and not route._selected
    assert 'color' not in native.attribute_writes
    assert len(native.visuals) == 2


def test_partial_point_failure_discards_staged_paths_and_restores_original_handles(registry):
    layers, native, _transforms, _guards = registry
    point, route = points(layers), paths(layers)
    old_point, old_route = point._visual, route._visual
    old_visuals = set(native.visuals)
    native.arm_attributes(color=(1,))
    with pytest.raises(RuntimeError, match='point colors'):
        layers.update_selection((point.refs[0], route.refs[0]))
    assert point._visual is old_point and route._visual is old_route
    assert not point._selected and not route._selected
    assert set(native.visuals) == old_visuals


def test_closed_failing_component_is_not_read_during_global_recovery(registry):
    layers, native, _transforms, _guards = registry
    first, second, route = points(layers), points(layers), paths(layers)
    native.arm_attributes(color=(2, 3))
    with pytest.raises(RuntimeError, match='selection highlight rollback failed; owner closed'):
        layers.update_selection((first.refs[0], second.refs[0], route.refs[0]))
    assert layers.viewer.closed and layers._closed and not native.visuals
    assert all(layer._closed for layer in (first, second, route))
    assert not first._selected and not second._selected and not route._selected
    assert not layers._ref_layers


def test_selection_invalidates_pending_query_before_native_writes_and_after_failed_intent(
    registry,
):
    layers, native, _transforms, _guards = registry
    layer = points(layers)
    invalidated = []
    pending = SimpleNamespace(value='pending')

    def invalidate():
        invalidated.append(list(native.attribute_writes))
        pending.value = None

    layers.viewer.picking = SimpleNamespace(invalidate=invalidate, unregister=lambda _: None)
    native.arm_attributes(color=(1,))
    with pytest.raises(RuntimeError, match='point colors'):
        layers.update_selection((layer.refs[0],))
    assert pending.value is None and invalidated == [[]]
    assert not layer._selected


def test_reference_index_publishes_only_successful_attachments_and_prunes_before_callback(
    registry, monkeypatch
):
    layers, native, _transforms, _guards = registry
    first = points(layers)
    original = dict(layers._ref_layers)
    native.fail = 'batch'
    with pytest.raises(RuntimeError, match='point attributes'):
        points(layers)
    assert layers._ref_layers == original
    real_build = LayerHandle._build

    def fail_second_population(layer, **kwargs):
        if layer.name == 'clusters':
            raise RuntimeError('second population failure')
        return real_build(layer, **kwargs)

    monkeypatch.setattr(LayerHandle, '_build', fail_second_population)
    recording = Recording(
        SOURCE,
        'pid',
        'eid',
        channels=Channels((1,), [[1, 2, 3]], FRAME, {}),
        clusters=Clusters((1,), [[3, 2, 1]], FRAME, {}),
    )
    with pytest.raises(RuntimeError, match='second population'):
        layers.add_recording(recording, show=('channels', 'clusters'))
    assert layers._ref_layers == original and layers.layers == (first,)
    removed = []
    layers._on_remove = lambda refs: removed.append(
        (refs, any(layers.contains(ref) for ref in refs))
    )
    layers.remove_layer(first)
    assert removed == [(first.refs, False)] and not layers._ref_layers
    assert not layers.contains(LayerObservationRef('bad', 1, {}))


def test_recording_reference_index_preserves_other_attachments_on_removal(registry):
    layers, _native, _transforms, _guards = registry
    first = points(layers)
    group = layers.add_recording(
        Recording(SOURCE, 'pid', 'eid', channels=Channels((1,), [[1, 2, 3]], FRAME, {})),
        show=('channels',),
    )
    refs = group.channels.refs
    assert all(layers.contains(ref) for ref in (*first.refs, *refs))
    removed = []
    layers._on_remove = lambda values: removed.append(
        tuple(layers.contains(ref) for ref in values)
    )
    layers.remove_recording(group)
    assert removed == [(False,)] and all(layers.contains(ref) for ref in first.refs)
    assert not any(layers.contains(ref) for ref in refs)
    layers.close()
    assert not layers._ref_layers
