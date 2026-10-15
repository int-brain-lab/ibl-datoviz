"""Pinned GPU queries prove frontmost identities, blockers and native zero rows."""

import ctypes
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import InsertionCollectionVisual, PointCollection, PointCollectionVisual
from ibl_datoviz.layers import LayerObservationRef
from ibl_datoviz.scientific_picking import ScientificPicking
from tests import test_component_native
from tests.test_scientific_native import MeshControl

native_components = test_component_native.native_components


@pytest.fixture
def host(native_components):
    context = native_components
    owner = SimpleNamespace(
        dvz=context.dvz,
        scene=context.scene,
        panel=context.panel,
        layers=[],
        _require_open=lambda: None,
    )
    owner.selection = SimpleNamespace(revision=0, observations=())

    def select(refs):
        owner.selection.observations = refs
        owner.selection.revision += 1

    owner.selection.set_observations = select
    owner._layer_registry = SimpleNamespace(
        contains=lambda ref: any(ref in layer.refs for layer in owner.layers)
    )
    owner.picking = ScientificPicking(owner)
    yield owner, context
    owner.picking.close()


def add_spheres(owner, context, ids, positions, *, attachment):
    dvz = context.dvz
    visual = dvz.dvz_sphere(context.scene, 0)
    assert visual
    positions = np.asarray(positions, np.float32)
    assert (
        dvz.dvz_visual_set_data_many(
            visual,
            {
                'position': positions,
                'radius': np.full(len(ids), 0.15, np.float32),
                'color': np.tile(np.array([255, 0, 0, 255], np.uint8), (len(ids), 1)),
            },
        )
        == 0
    )
    assert dvz.dvz_visual_set_depth_test(visual, True) == 0
    assert dvz.dvz_panel_add_visual(context.panel, visual, None) == 0
    component = SimpleNamespace(visual=visual)
    component.close = lambda: dvz.dvz_visual_destroy(visual)
    context.components.append(component)
    refs = tuple(LayerObservationRef(attachment, value) for value in ids)
    handle = SimpleNamespace(
        _glyph='sphere',
        _closed=False,
        effective_visible=True,
        _visual=component,
        refs=refs,
        positioned_refs=refs,
        name=attachment,
        payload=SimpleNamespace(positioned=np.ones(len(ids), bool)),
    )
    owner.layers.append(handle)
    owner.picking.register(handle, component)
    return handle


def click(owner, context, x=80, y=60):
    assert owner.picking.request(x, y) is not None
    context.capture()
    assert not owner.picking.poll()
    assert owner.picking.status in ('hit', 'miss'), owner.picking.reason
    return owner.selection.observations


def test_native_composed_spheres_exact_ids_visibility_and_attachment_order(host):
    owner, context = host
    near = add_spheres(
        owner, context, (0, '0'), [[-0.5, 0, -0.2], [0, 0, -0.2]], attachment='near'
    )
    far = add_spheres(owner, context, (0,), [[0, 0, 0.3]], attachment='far')
    assert click(owner, context) == (near.refs[1],)
    assert click(owner, context, 40, 60) == (near.refs[0],)
    assert owner.dvz.dvz_visual_set_visible(near._visual.visual, False) == 0
    near.effective_visible = False
    assert click(owner, context) == (far.refs[0],)
    near.effective_visible = True
    assert owner.dvz.dvz_visual_set_visible(near._visual.visual, True) == 0
    assert click(owner, context) == (near.refs[1],)
    owner.picking.unregister(near._visual)
    near._closed = True
    assert owner.dvz.dvz_visual_set_visible(near._visual.visual, False) == 0
    assert click(owner, context) == (far.refs[0],)
    assert click(owner, context, 5, 5) == ()


def test_native_opaque_mesh_blocks_sphere_and_zero_alpha_restores_it(host):
    owner, context = host
    sphere = add_spheres(owner, context, ('target',), [[0, 0, 0.2]], attachment='recording')
    assert click(owner, context) == sphere.refs
    mesh = MeshControl(context, (0, 255, 0, 255), z=-0.3)
    assert (
        owner.dvz.dvz_visual_set_query_capabilities(
            mesh.visual, owner.dvz.DVZ_QUERY_CAPABILITY_ITEM
        )
        == 0
    )
    assert click(owner, context) == ()
    # This is native effective alpha coverage, rather than Python visibility filtering.
    assert (
        owner.dvz.dvz_visual_set_data(
            mesh.visual, 'color', np.tile(np.array([0, 255, 0, 0], np.uint8), (4, 1))
        )
        == 0
    )
    assert click(owner, context) == sphere.refs


@pytest.mark.parametrize('glyph', ['point', 'path'])
def test_native_unsupported_coverage_is_blocked_before_query(host, glyph):
    owner, context = host
    add_spheres(owner, context, (0,), [[0, 0, 0.2]], attachment='recording')
    if glyph == 'point':
        component = PointCollectionVisual(
            owner.dvz,
            owner.scene,
            owner.panel,
            PointCollection.from_arrays([[0, 0, -0.2]], [[255, 0, 0, 255]], sizes_px=24),
        )
        visual = component.visual
        style = owner.dvz.dvz_point_style_desc()
        style.aspect = owner.dvz.DVZ_SHAPE_ASPECT_STROKE
        style.stroke_width_px = 2
        assert owner.dvz.dvz_point_set_style(visual, ctypes.byref(style)) == 0
        owner.picking._external_blockers = lambda: (
            'custom stroked point coverage is unsupported',
        )
    else:
        component = InsertionCollectionVisual(owner.dvz, owner.scene, owner.panel)
        component.set_insertion(1, [[-0.5, 0, -0.2], [0.5, 0, -0.2]])
        visual = component._insertions[1].visual
    context.components.append(component)
    owner.layers.append(
        SimpleNamespace(
            _glyph=glyph,
            effective_visible=True,
            payload=SimpleNamespace(positioned=[True]),
            name='unsupported',
        )
    )
    assert owner.picking.request(80, 60) is None
    assert owner.picking.status == 'unavailable'
    # Demonstrate the pinned native limitation rather than infer it from Python types.
    assert (
        owner.dvz.dvz_visual_set_query_capabilities(visual, owner.dvz.DVZ_QUERY_CAPABILITY_ITEM)
        == 0
    )
    request = owner.dvz.dvz_query_request()
    request.request_id = 999
    request.target = owner.dvz.DVZ_SCENE_TARGET_ITEM
    assert owner.dvz.dvz_panel_query_px(owner.panel, 80, 60, ctypes.byref(request)) == 0
    context.capture()
    native_result = owner.dvz.DvzQueryResult()
    assert owner.dvz.dvz_scene_poll_query(owner.scene, ctypes.byref(native_result))
    assert native_result.request_id == 999
    assert native_result.status == owner.dvz.DVZ_QUERY_STATUS_UNSUPPORTED_VISUAL_FAMILY
    assert not native_result.hit


def test_native_filled_point_footprint_exact_ids_and_transparent_holes(host):
    owner, context = host
    background = add_spheres(owner, context, ('background',), [[0, 0, 0.3]], attachment='behind')
    component = PointCollectionVisual(
        owner.dvz,
        owner.scene,
        owner.panel,
        PointCollection.from_arrays([[0, 0, -0.3]], [[255, 0, 0, 255]], sizes_px=24),
    )
    context.components.append(component)
    ref = LayerObservationRef('filled-point', 0)
    handle = SimpleNamespace(
        _glyph='point',
        _closed=False,
        effective_visible=True,
        _visual=component,
        refs=(ref,),
        positioned_refs=(ref,),
        name='filled point',
        payload=SimpleNamespace(positioned=[True]),
    )
    owner.layers.append(handle)
    owner.picking.register(handle, component)
    assert click(owner, context) == (ref,)
    assert click(owner, context, 90, 60) == (ref,)
    assert click(owner, context, 94, 60) != (ref,)
    # Corners of its bounding square lie outside the circular visible footprint.
    assert click(owner, context, 90, 70) != (ref,)
    component.update_colors([[255, 0, 0, 0]])
    assert click(owner, context) == background.refs
