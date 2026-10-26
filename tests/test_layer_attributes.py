"""In-place scientific attributes retain geometry and compensate partial native writes."""

from collections import Counter
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer, Points
from ibl_datoviz.layers import LayerRegistry
from ibl_datoviz.payloads import SourceObservationKey
from ibl_datoviz.points import PointCollection, PointCollectionVisual
from tests.test_atlas import FIXTURE
from tests.test_layer_visibility import VisibilityNative
from tests.test_owned_layers import FRAME, SOURCE


class AttributeNative(VisibilityNative):
    """Copy candidate attributes before returning an injected failure status."""

    def __init__(self):
        super().__init__()
        self.attribute_attempts = Counter()
        self.attribute_failures = {}
        self.attribute_writes = []

    def arm_attributes(self, **failures):
        self.attribute_attempts.clear()
        self.attribute_failures = failures
        self.attribute_writes.clear()

    def attribute_status(self, name):
        self.attribute_attempts[name] += 1
        return -1 if self.attribute_attempts[name] in self.attribute_failures.get(name, ()) else 0

    def dvz_visual_set_data(self, visual, name, data):
        self.visuals[visual][name] = np.array(data, copy=True)
        self.attribute_writes.append(name)
        return self.attribute_status(name)

    def dvz_visual_set_alpha_mode(self, visual, mode):
        self.visuals[visual]['alpha_mode'] = mode
        self.attribute_writes.append('alpha')
        return self.attribute_status('alpha')


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
        mesh_data=SimpleNamespace(normalize_points=normalize, display_scale=0.1),
        closed=False,
    )
    layers = LayerRegistry(owner, before_mutation=lambda: guards.append(True))

    def close():
        layers.close()
        owner.closed = True

    owner.close = close
    yield layers, native, transforms, guards
    layers.close()


def payload(*, source=False, missing=False):
    ids = ('first', 'missing', 'last')
    keys = tuple(SourceObservationKey(SOURCE, 'pid', 'channels', key) for key in ids)
    xyz = [[1, 2, 3], [np.nan, 0, 0], [4, 5, 6]]
    if missing:
        xyz = [[np.nan, 0, 0]] * 3
    return Points(ids, xyz, FRAME, {}, keys if source else None)


def displayed_colors(layer):
    if layer._glyph == 'point':
        return layer._visual.data.colors
    return layer._visual._storage['color']


def display_positions(layer):
    if layer._glyph == 'point':
        return layer._visual._display_positions
    return layer._visual._storage['position']


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_color_and_size_keep_geometry_and_native_visual(registry, glyph):
    layers, native, transforms, guards = registry
    layer = layers.add_points(payload(), glyph=glyph)
    component, positions = layer._visual, display_positions(layer)
    creation, batches, transformed = (
        native.calls['create_visual'],
        native.calls['batch'],
        len(transforms),
    )
    native.arm_attributes()
    layer.set_color('#11223344')
    assert layer._visual is component and display_positions(layer) is positions
    np.testing.assert_array_equal(displayed_colors(layer), [[17, 34, 51, 68]] * 2)
    if glyph == 'point':
        original_positions = component.data.positions_um
        layer.set_size_px(12)
        assert component.data.positions_um is original_positions
        np.testing.assert_array_equal(component.data.sizes_px, [12, 12])
    else:
        layer.set_radius_um(12)
        np.testing.assert_allclose(component._storage['radius'], [1.2, 1.2])
        assert native.visuals[component.visual]['alpha_mode'] == native.DVZ_ALPHA_WBOIT
    assert layer._visual is component and display_positions(layer) is positions
    assert native.calls['create_visual'] == creation and native.calls['destroy_visual'] == 0
    assert native.calls['batch'] == batches and len(transforms) == transformed
    assert 'position' not in native.attribute_writes
    prior_writes, prior_guards = list(native.attribute_writes), len(guards)
    layer.set_size_px(12) if glyph == 'point' else layer.set_radius_um(12)
    assert native.attribute_writes == prior_writes and len(guards) == prior_guards + 1


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_scalar_and_uniform_edits_preserve_selected_and_unpositioned_rows(
    registry, monkeypatch, glyph
):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(source=True), glyph=glyph)
    selected = (layer.observation('first'), layer.observation('missing'))
    layers.update_selection(selected)
    component = layer._visual
    layer.set_color('#11223344')
    assert layer._selected == frozenset(selected) and layer._visual is component
    np.testing.assert_array_equal(displayed_colors(layer), [[255, 70, 180, 255], [17, 34, 51, 68]])
    colors = np.asarray([[1, 2, 3, 40], [128, 128, 128, 255], [4, 5, 6, 255]], np.uint8)
    monkeypatch.setattr(layers, '_scalar_colors', lambda *_: colors)
    options = dict(name='Rate', units='Hz', cmap='viridis', limits=(0, 10))
    native.arm_attributes()
    with pytest.raises(ValueError, match='observation_refs'):
        layer.color_by(
            [1, np.nan, 3], observation_refs=layer.payload.observation_keys[::-1], **options
        )
    assert not native.attribute_writes
    layer.color_by([1, np.nan, 3], observation_refs=layer.payload.observation_keys, **options)
    assert layer._visual is component and len(layer.scalar_encoding.values) == 3
    np.testing.assert_equal(layer.scalar_encoding.values, [1, np.nan, 3])
    np.testing.assert_array_equal(displayed_colors(layer), [[255, 70, 180, 255], [4, 5, 6, 255]])
    if glyph == 'sphere':
        # Unpositioned and highlighted translucent rows cannot force transparency.
        assert native.visuals[component.visual]['alpha_mode'] == native.DVZ_ALPHA_OPAQUE
    layer.set_color('#abcdef')
    assert layer.scalar_encoding is None and layer._visual is component
    assert layer._selected == frozenset(selected)


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_failed_color_write_restores_native_and_scientific_state(registry, glyph):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(), glyph=glyph)
    component, old_colors = layer._visual, layer._colors
    previous = displayed_colors(layer)
    native.arm_attributes(color=(1,))
    with pytest.raises(RuntimeError, match='colors'):
        layer.set_color('#ff000040')
    assert layer._visual is component and layer._colors is old_colors
    assert displayed_colors(layer) is previous
    np.testing.assert_array_equal(native.visuals[component.visual]['color'], previous)
    assert native.attribute_writes == ['color', 'color']
    assert not layers.viewer.closed


def test_sphere_alpha_failure_after_color_upload_restores_both_attributes(registry):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(), glyph='sphere')
    component, storage, colors = layer._visual, layer._visual._storage, layer._colors
    native.arm_attributes(alpha=(1,))
    with pytest.raises(RuntimeError, match='sphere alpha'):
        layer.set_color('#ff000040')
    assert layer._visual is component and component._storage is storage and layer._colors is colors
    assert component._alpha_mode == native.DVZ_ALPHA_OPAQUE
    assert native.visuals[component.visual]['alpha_mode'] == native.DVZ_ALPHA_OPAQUE
    np.testing.assert_array_equal(native.visuals[component.visual]['color'], storage['color'])
    assert native.attribute_writes == ['color', 'alpha', 'alpha', 'color']


@pytest.mark.parametrize('glyph,attribute', [('point', 'diameter_px'), ('sphere', 'radius')])
def test_failed_size_upload_restores_prior_radius_and_geometry(registry, glyph, attribute):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(), glyph=glyph)
    component, positions, old_size = layer._visual, display_positions(layer), layer._size
    stored = component.data if glyph == 'point' else component._storage
    previous = native.visuals[component.visual][attribute].copy()
    native.arm_attributes(**{attribute: (1,)})
    with pytest.raises(RuntimeError, match='sizes|radius'):
        layer.set_size_px(12) if glyph == 'point' else layer.set_radius_um(12)
    assert layer._size == old_size and layer._visual is component
    assert display_positions(layer) is positions
    assert (component.data if glyph == 'point' else component._storage) is stored
    np.testing.assert_array_equal(native.visuals[component.visual][attribute], previous)


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_unrecoverable_color_failure_closes_component_and_owner(registry, glyph):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(), glyph=glyph)
    component = layer._visual
    native.arm_attributes(color=(1, 2))
    with pytest.raises(RuntimeError, match='colors rollback failed; component closed'):
        layer.set_color('#11223344')
    assert component._closed and layer._closed and layers.viewer.closed
    assert not native.visuals


def test_failed_sphere_alpha_recovery_also_restores_colors_before_cleanup(registry):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(), glyph='sphere')
    native.arm_attributes(alpha=(1, 2))
    with pytest.raises(RuntimeError, match='colors rollback failed; component closed'):
        layer.set_color('#11223344')
    assert native.attribute_writes == ['color', 'alpha', 'alpha', 'color']
    assert layer._closed and layers.viewer.closed and not native.visuals


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_empty_populations_keep_complete_metadata_without_creating_native_storage(
    registry, monkeypatch, glyph
):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(payload(missing=True), glyph=glyph)
    component = layer._visual
    monkeypatch.setattr(layers, '_scalar_colors', lambda *_: np.ones((3, 4), np.uint8))
    native.arm_attributes()
    layer.set_color('#abcdef')
    layer.set_size_px(12) if glyph == 'point' else layer.set_radius_um(12)
    layer.color_by([1, np.nan, 3], name='Rate', units='Hz', cmap='viridis', limits=(0, 10))
    assert layer._visual is component and not component.visual
    assert len(layer.refs) == len(layer.scalar_encoding.values) == 3 and layer._size == 12
    assert not native.attribute_writes and not native.visuals


def test_low_level_point_failed_attribute_recovery_closes_only_owned_component():
    native = AttributeNative()
    component = PointCollectionVisual(
        native,
        'borrowed-scene',
        'borrowed-panel',
        PointCollection.from_arrays(np.ones((2, 3)), np.ones((2, 4), np.uint8)),
    )
    native.arm_attributes(diameter_px=(1, 2))
    with pytest.raises(RuntimeError, match='point sizes rollback failed; component closed'):
        component.update_sizes(20)
    assert component._closed and component.data is None and not native.visuals
    with pytest.raises(RuntimeError, match='closed'):
        component.update_colors(np.ones((2, 4), np.uint8))


@pytest.mark.parametrize('glyph', ['point', 'sphere'])
def test_native_attribute_changes_retain_exact_query_identity(native_datoviz, glyph):
    with AtlasViewer(AtlasMesh.from_pack(FIXTURE)) as viewer:
        layer = viewer.add_points(Points(('cell',), [[0, 0, 0]], viewer.frame, {}), glyph=glyph)
        component = layer._visual
        visual_id = int(viewer.dvz.dvz_visual_id(component.visual))
        registration = viewer.picking._registrations[visual_id]
        next_key = viewer.picking._next_key
        layer.set_color('#11223344')
        layer.set_size_px(12) if glyph == 'point' else layer.set_radius_um(12)
        layer.color_by([2], name='Rate', units='Hz', cmap='viridis', limits=(0, 10))
        assert layer._visual is component and viewer.picking._next_key == next_key
        assert viewer.picking._registrations[visual_id] is registration
