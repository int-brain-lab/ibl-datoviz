"""Owned layers preserve scientific rows while native candidates commit atomically."""

from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.layers import LayerHandle, LayerRegistry, UnavailableLayerError
from ibl_datoviz.payloads import (
    Channels,
    Paths,
    Points,
    Recording,
    SourceKey,
    SourceObservationKey,
    WorldFrame,
)

FRAME = WorldFrame('mouse-reference')
SOURCE = SourceKey('test', 'dataset', '1', 'a' * 64)


class FakeVisual:
    def __init__(self, state):
        self.state = state
        self.closed = False
        self._closed = False
        self._visible = state['visible']
        self._insertions = {1: SimpleNamespace(visible=self._visible)}

    def set_visible(self, *args):
        self._visible = bool(args[-1])
        self.state['visible'] = self._visible
        for item in self._insertions.values():
            item.visible = self._visible

    def close(self):
        self.closed = True
        self._closed = True

    def update_colors(self, colors):
        self.state['colors'] = colors

    def update_sizes(self, sizes):
        self.state['size'] = sizes

    update_radius = update_sizes


@pytest.fixture
def registry(monkeypatch):
    def build(layer, **changes):
        return FakeVisual(
            {
                'colors': changes.get('colors', layer._colors),
                'selected': changes.get('selected', layer._selected),
                'visible': changes.get('visible', layer.effective_visible),
                'size': changes.get('size', layer._size),
            }
        )

    monkeypatch.setattr(LayerHandle, '_build', build)
    return LayerRegistry(SimpleNamespace())


def points(ids=(0, 9), *, source=False):
    keys = tuple(SourceObservationKey(SOURCE, 'pid', 'channels', key) for key in ids)
    return Points(ids, [[1, 2, 3], [np.nan, 0, 1]], FRAME, {}, keys if source else None)


def recording(pid='pid'):
    keys = tuple(SourceObservationKey(SOURCE, pid, 'channels', key) for key in (0, 9))
    channels = Channels((0, 9), [[1, 2, 3], [np.nan, 0, 1]], FRAME, {}, keys)
    return Recording(SOURCE, pid, 'eid', channels=channels)


def test_attachment_identity_missing_positions_and_closed_handles(registry):
    payload = points()
    first = registry.add_points(payload)
    second = registry.add_points(payload)
    assert first.observation(0) != second.observation(0)
    assert first.positioned_refs == (first.observation(0),)
    assert len(first.refs) == 2
    registry.update_selection([first.observation(9)])
    assert first._selected == frozenset([first.observation(9)])
    assert not second._selected
    first.set_visible(False)
    assert first._selected
    removed = []
    registry._on_remove = lambda refs: removed.append((refs, first._visual.closed))
    registry.remove_layer(first)
    assert removed == [(first.refs, True)]
    assert not registry.contains(first.refs[0])
    with pytest.raises(RuntimeError, match='closed'):
        first.set_visible(True)
    with pytest.raises(RuntimeError, match='closed'):
        first.observation(0)


def test_scalar_source_alignment_is_not_length_alignment(registry, monkeypatch):
    layer = registry.add_points(points(source=True))
    scalar_colors = np.array([[1, 2, 3, 255], [128, 128, 128, 255]], np.uint8)
    monkeypatch.setattr(registry, '_scalar_colors', lambda *_args: scalar_colors)
    options = dict(name='Rate', units='Hz', cmap='viridis', limits=(0, 10))
    with pytest.raises(ValueError, match='observation_refs'):
        layer.color_by([2, np.nan], **options)
    with pytest.raises(ValueError, match='observation_refs'):
        layer.color_by(
            [2, np.nan], observation_refs=layer.payload.observation_keys[::-1], **options
        )
    layer.color_by([2, np.nan], observation_refs=layer.payload.observation_keys, **options)
    np.testing.assert_equal(layer.scalar_encoding.values, [2, np.nan])
    assert len(layer.scalar_encoding.values) == 2
    layer.set_color('#ffaa00')
    assert layer.scalar_encoding is None


def test_failed_replacement_preserves_state_and_live_visual(registry, monkeypatch):
    layer = registry.add_points(points())
    old = layer._visual

    def fail(*_args, **_kwargs):
        raise RuntimeError('injected native upload failure')

    monkeypatch.setattr(layer._visual, 'update_colors', fail)
    with pytest.raises(RuntimeError, match='injected'):
        layer.set_color('#112233')
    assert layer._visual is old and not old.closed


def test_recording_group_visibility_duplicate_source_and_unavailable_layers(registry):
    group = registry.add_recording(recording(), show=('channels',))
    child = group.channels
    child.set_visible(False)
    group.set_visible(False)
    child.set_visible(True)
    assert child.visible and not child.effective_visible
    group.set_visible(True)
    assert child.effective_visible
    with pytest.raises(UnavailableLayerError):
        _ = group.clusters
    with pytest.raises(ValueError, match='already attached'):
        registry.add_recording(recording(), show=('channels',))
    with pytest.raises(ValueError, match='generic'):
        registry.remove_layer(child)
    other = registry.add_recording(recording('other'), show=('channels',))
    assert group.channels.observation(0).source_key != other.channels.observation(0).source_key
    registry.remove_recording(group)
    assert registry.recordings == (other,)
    with pytest.raises(RuntimeError, match='closed'):
        _ = group.channels


def test_recording_composition_rolls_back_partial_attachment(registry, monkeypatch):
    from ibl_datoviz.payloads import Clusters  # noqa: PLC0415

    original = LayerHandle._build
    built = []

    def build(layer, **kwargs):
        if layer.name == 'clusters':
            raise RuntimeError('injected second population failure')
        visual = original(layer, **kwargs)
        built.append(visual)
        return visual

    monkeypatch.setattr(LayerHandle, '_build', build)
    prepared = recording()
    clusters = Clusters((0,), [[1, 2, 3]], FRAME, {})
    prepared = Recording(SOURCE, 'pid', 'eid', channels=prepared.channels, clusters=clusters)
    with pytest.raises(RuntimeError, match='second population'):
        registry.add_recording(prepared, show=('channels', 'clusters'))
    assert built and all(visual.closed for visual in built)
    assert not registry.layers and not registry.recordings


def test_selection_candidate_failure_rolls_back_all_layers(registry, monkeypatch):
    first, second = registry.add_points(points()), registry.add_points(points())
    old = (first._visual, second._visual)

    def fail(**_kwargs):
        raise RuntimeError('second highlight failure')

    monkeypatch.setattr(second, '_build', fail)
    with pytest.raises(RuntimeError, match='highlight'):
        registry.update_selection([first.observation(0), second.observation(0)])
    assert not first._selected and not second._selected
    assert (first._visual, second._visual) == old
    assert not any(visual.closed for visual in old)


def test_capability_and_mutation_guard(registry):
    point = registry.add_points(points())
    sphere = registry.add_points(points(), glyph='sphere')
    path = registry.add_paths(Paths(('route',), ([[0, 0, 0], [1, 2, 3]],), FRAME, {}))
    with pytest.raises(ValueError, match='unsupported'):
        point.set_radius_um(20)
    with pytest.raises(ValueError, match='unsupported'):
        sphere.set_size_px(4)
    with pytest.raises(ValueError, match='unsupported'):
        path.color_by([1], name='x', units='1', cmap='magma', limits=(0, 1))
    with pytest.raises(ValueError, match='opaque'):
        path.set_color('#ff000040')
    assert point.capabilities.native_picking and sphere.capabilities.native_picking
    assert not path.capabilities.native_picking

    def reject():
        raise RuntimeError('foreign thread or reentrant write')

    registry._before_mutation = reject
    with pytest.raises(RuntimeError, match='foreign thread'):
        point.set_visible(False)
    assert point.visible
    registry.close()  # shutdown must remain possible after mutation rejection
    assert point._closed and sphere._closed and path._closed


@pytest.fixture
def native_registry(native_datoviz):
    import datoviz as dvz  # noqa: PLC0415

    scene = dvz.dvz_scene()
    assert scene
    app = registry = None
    try:
        figure = dvz.dvz_figure(scene, 160, 120, 0)
        panel = dvz.dvz_panel_full(figure)
        app = dvz.dvz_app(scene)
        if not app:
            pytest.skip('native graphics runtime unavailable')
        view = dvz.dvz_view_offscreen(app, figure, 160, 120)
        assert view
        viewer = SimpleNamespace(
            dvz=dvz,
            scene=scene,
            panel=panel,
            mesh_data=SimpleNamespace(normalize_points=lambda xyz: xyz * 0.1, display_scale=0.1),
        )
        registry = LayerRegistry(viewer)
        yield registry, lambda: dvz.dvz_view_render_once(view)
    finally:
        if registry is not None:
            registry.close()
        if app:
            dvz.dvz_app_destroy(app)
        dvz.dvz_scene_destroy(scene)


def test_native_point_sphere_path_scalar_and_zero_positioned(native_registry):
    registry, render = native_registry
    point = registry.add_points(points())
    sphere = registry.add_points(points(), glyph='sphere')
    path = registry.add_paths(Paths(('route',), ([[0, 0, 0], [1, 2, 3]],), FRAME, {}))
    assert len(point._visual.data) == 1
    assert len(sphere._visual.data) == 1
    np.testing.assert_allclose(sphere._visual._storage['radius'], [2.0])
    np.testing.assert_allclose(point._visual._display_positions, [[0.1, 0.2, 0.3]])
    assert path._visual.ids == (1,)
    point.color_by([5, np.nan], name='Rate', units='Hz', cmap='viridis', limits=(0, 10))
    assert point._visual.data.colors.shape == (1, 4)
    assert render() == 0
    registry.update_selection([sphere.observation(9), point.observation(0)])
    np.testing.assert_equal(point._visual.data.colors, [[255, 70, 180, 255]])
    point.set_visible(False)
    sphere.set_radius_um(10)
    path.set_width_px(4)
    assert render() == 0
    missing = registry.add_points(Points((0,), [[np.nan, np.nan, np.nan]], FRAME, {}))
    assert missing.refs and not missing.positioned_refs and not missing._visual.visual
    registry.update_selection([missing.observation(0)])
    assert render() == 0
    registry.remove_layer(path)
    assert render() == 0


def test_endpoint_gap_style_survives_layer_rebuilds_and_rejects_unsupported_runtime(
    registry, monkeypatch
):
    route = registry.add_paths(Paths(('route',), ([[0, 0, 0], [1, 2, 3]],), FRAME, {}))
    registry.viewer.dvz = SimpleNamespace()
    initial = route._visual
    with pytest.raises(RuntimeError, match='compatible native'):
        route.set_endpoint_gaps_px(4, 4)
    assert route._visual is initial and not initial.closed
    assert route.endpoint_gaps_px == (0, 0)
    registry.viewer.dvz.dvz_path_set_endpoint_gaps = lambda *_: 0
    real_build = LayerHandle._build
    gaps = []

    def build(layer, **kwargs):
        gaps.append(kwargs.get('endpoint_gaps', layer.endpoint_gaps_px))
        return real_build(layer, **kwargs)

    monkeypatch.setattr(LayerHandle, '_build', build)
    route.set_endpoint_gaps_px(4, 6)
    route.set_width_px(9)
    route.set_color('#ff0000')
    route.set_visible(False)
    registry.update_selection([route.observation('route')])
    assert gaps == [(4, 6)] * 4
    assert route.endpoint_gaps_px == (4, 6)
    with pytest.raises(ValueError, match='endpoint gaps'):
        route.set_endpoint_gaps_px(-1, 3)
    with pytest.raises(ValueError, match='unsupported'):
        registry.add_points(points()).set_endpoint_gaps_px(4, 4)
    prior = route._visual
    monkeypatch.setattr(route, '_build', lambda **_: (_ for _ in ()).throw(RuntimeError('upload')))
    with pytest.raises(RuntimeError, match='upload'):
        route.set_endpoint_gaps_px(1, 2)
    assert route._visual is prior and not prior.closed
    assert route.endpoint_gaps_px == (4, 6)


def test_native_endpoint_gap_candidate_style_rebuilds_and_baseline_rejection(native_registry):
    registry, render = native_registry
    route = registry.add_paths(Paths(('route',), ([[0, 0, 0], [1, 2, 3]],), FRAME, {}))
    old = route._visual
    xyz = route.payload.positions_um[0].copy()
    if not hasattr(registry.viewer.dvz, 'dvz_path_set_endpoint_gaps'):
        with pytest.raises(RuntimeError, match='compatible native'):
            route.set_endpoint_gaps_px(4, 6)
        assert route._visual is old
        assert route.endpoint_gaps_px == (0, 0)
        return
    route.set_endpoint_gaps_px(4, 6)
    assert old._closed
    route.set_width_px(5)
    route.set_color('#ff0000')
    route.set_visible(False)
    registry.update_selection([route.observation('route')])
    route.set_visible(True)
    assert route.endpoint_gaps_px == (4, 6)
    assert route._visual._insertions[1].endpoint_gaps_px == (4, 6)
    np.testing.assert_array_equal(route.payload.positions_um[0], xyz)
    assert render() == 0
    route.set_endpoint_gaps_px(0, 0)
    assert route._visual._insertions[1].endpoint_gaps_px == (0, 0)
    assert render() == 0
