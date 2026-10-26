"""Retained visibility changes preserve native identity and compensate partial writes."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer, Channels, Clusters, Paths, Points, Recording
from ibl_datoviz.layers import LayerRegistry
from tests.test_atlas import FIXTURE
from tests.test_component_visuals import Native
from tests.test_owned_layers import FRAME, SOURCE


class VisibilityNative(Native):
    """A failed visibility setter can mutate native state before returning an error."""

    DVZ_ALPHA_WBOIT = 2
    DVZ_SEGMENT_CAP_ROUND = 1
    DVZ_PATH_JOIN_ROUND = 1
    dvz_sphere = Native.dvz_point
    dvz_path = Native.dvz_point

    def __init__(self):
        super().__init__()
        self.visibility_writes = []
        self.failed_attempts = set()

    def arm(self, *attempts):
        self.visibility_writes.clear()
        self.failed_attempts = set(attempts)

    def dvz_visual_set_visible(self, visual, visible):
        self.visibility_writes.append((visual, bool(visible)))
        self.visuals[visual]['visible'] = bool(visible)
        return -1 if len(self.visibility_writes) in self.failed_attempts else 0

    def dvz_path_set_caps(self, *_args):
        return 0

    def dvz_path_set_join(self, *_args):
        return 0


@pytest.fixture
def registry():
    native, transforms, guards = VisibilityNative(), [], []

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
    registry = LayerRegistry(owner, before_mutation=lambda: guards.append(True))

    def close():
        registry.close()
        owner.closed = True

    owner.close = close
    yield registry, native, transforms, guards
    registry.close()


def attach(registry, glyph):
    if glyph == 'path':
        return registry.add_paths(
            Paths(('first', 'second'), (np.ones((2, 3)), np.ones((3, 3))), FRAME, {})
        )
    return registry.add_points(Points((0, 1), np.ones((2, 3)), FRAME, {}), glyph=glyph)


def handles(layer):
    component = layer._visual
    if layer._glyph == 'path':
        return tuple(item.visual for item in component._insertions.values())
    return (component.visual,) if component.visual else ()


@pytest.mark.parametrize('glyph', ['point', 'sphere', 'path'])
def test_visibility_keeps_visuals_geometry_and_uploads(registry, glyph):
    layers, native, transforms, _guards = registry
    layer = attach(layers, glyph)
    component, visual_ids = layer._visual, handles(layer)
    old_arrays = {
        visual: {
            key: value
            for key, value in native.visuals[visual].items()
            if isinstance(value, np.ndarray)
        }
        for visual in visual_ids
    }
    creation, batches, transformed = (
        native.calls['create_visual'],
        native.calls['batch'],
        len(transforms),
    )
    native.arm()
    layer.set_visible(False)
    assert not layer.visible
    assert all(not native.visuals[visual]['visible'] for visual in visual_ids)
    layer.set_visible(True)
    assert layer.visible and layer._visual is component and handles(layer) == visual_ids
    assert native.calls['create_visual'] == creation and native.calls['destroy_visual'] == 0
    assert native.calls['batch'] == batches and len(transforms) == transformed
    for visual, values in old_arrays.items():
        for key, value in values.items():
            assert native.visuals[visual][key] is value


@pytest.mark.parametrize('glyph', ['point', 'sphere', 'path'])
def test_partial_native_visibility_failure_restores_failing_visual(registry, glyph):
    layers, native, _transforms, _guards = registry
    layer = attach(layers, glyph)
    component, visual_ids = layer._visual, handles(layer)
    native.arm(2 if glyph == 'path' else 1)
    with pytest.raises(RuntimeError, match='visibility'):
        layer.set_visible(False)
    assert layer.visible and layer._visual is component and handles(layer) == visual_ids
    assert all(native.visuals[visual]['visible'] for visual in visual_ids)
    assert len(native.visibility_writes) == (4 if glyph == 'path' else 2)
    assert not layers.viewer.closed


def test_recording_visibility_rolls_back_successful_and_failing_children(registry):
    layers, native, _transforms, _guards = registry
    payload = Recording(
        SOURCE,
        'pid',
        'eid',
        channels=Channels((0,), [[1, 2, 3]], FRAME, {}),
        clusters=Clusters((1,), [[3, 2, 1]], FRAME, {}),
    )
    group = layers.add_recording(payload, show=('channels', 'clusters'))
    components = tuple(layer._visual for layer in group.layers)
    visual_ids = tuple(visual for layer in group.layers for visual in handles(layer))
    native.arm(2)
    with pytest.raises(RuntimeError, match='visibility'):
        group.set_visible(False)
    assert group.visible and all(
        layer.visible and layer.effective_visible for layer in group.layers
    )
    assert tuple(layer._visual for layer in group.layers) == components
    assert all(native.visuals[visual]['visible'] for visual in visual_ids)
    assert native.visibility_writes == [
        (visual_ids[0], False),
        (visual_ids[1], False),
        (visual_ids[1], True),
        (visual_ids[0], True),
    ]


def test_child_visibility_while_group_hidden_changes_only_authored_state(registry):
    layers, native, _transforms, guards = registry
    group = layers.add_recording(
        Recording(SOURCE, 'pid', 'eid', channels=Channels((0,), [[1, 2, 3]], FRAME, {})),
        show=('channels',),
    )
    layer = group.channels
    group.set_visible(False)
    native.arm()
    layer.set_visible(False)
    layer.set_visible(True)
    assert layer.visible and not layer.effective_visible
    assert not native.visibility_writes
    before = len(guards)
    layer.set_visible(True)
    group.set_visible(False)
    assert len(guards) == before + 2 and not native.visibility_writes
    group.set_visible(True)
    assert layer.effective_visible and len(native.visibility_writes) == 1


def test_failed_visibility_rollback_closes_owner_and_releases_layers(registry):
    layers, native, _transforms, _guards = registry
    layer = attach(layers, 'point')
    native.arm(1, 2)
    with pytest.raises(RuntimeError, match='visibility rollback failed; owner closed'):
        layer.set_visible(False)
    assert layers.viewer.closed and layers._closed and layer._closed
    assert not native.visuals


def test_empty_population_visibility_keeps_complete_observations_without_native_work(registry):
    layers, native, _transforms, _guards = registry
    layer = layers.add_points(Points(('missing',), [[np.nan, 0, 0]], FRAME, {}))
    component = layer._visual
    native.arm()
    layer.set_visible(False)
    layer.set_visible(True)
    assert layer.visible and layer.refs[0].original_id == 'missing'
    assert layer._visual is component and not component.visual
    assert not native.visibility_writes and not native.visuals


def test_native_visibility_keeps_exact_picking_registration(native_datoviz):
    with AtlasViewer(AtlasMesh.from_pack(FIXTURE)) as viewer:
        layer = viewer.add_points(Points(('cell',), [[0, 0, 0]], viewer.frame, {}))
        component = layer._visual
        visual_id = int(viewer.dvz.dvz_visual_id(component.visual))
        registration = viewer.picking._registrations[visual_id]
        next_key = viewer.picking._next_key
        result = SimpleNamespace(
            scene_id=int(viewer.dvz.dvz_scene_id(viewer.scene)),
            panel_id=int(viewer.dvz.dvz_panel_id(viewer.panel)),
            hit=True,
            status=viewer.dvz.DVZ_QUERY_STATUS_HIT,
            visual_id=visual_id,
            item_id=0,
            link_channel=viewer.picking._channel_id,
            link_key=int(registration.keys[0]),
        )
        assert viewer.picking.resolve(result) == layer.observation('cell')
        layer.set_visible(False)
        assert viewer.picking.resolve(result) is None
        layer.set_visible(True)
        assert layer._visual is component
        assert viewer.picking._registrations[visual_id] is registration
        assert viewer.picking._next_key == next_key
        assert viewer.picking.resolve(result) == layer.observation('cell')
