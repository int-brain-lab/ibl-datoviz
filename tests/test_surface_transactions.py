import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.components import AtlasRegionValues, ProbeSites
from tests import FIXTURES
from tests.test_atlas import FakeDatoviz


class TransactionNative(FakeDatoviz):
    """Copied native payload state with failures injected at exact setter calls."""

    def __init__(self):
        super().__init__()
        self.colors = self.indices = self.keys = None
        self.mode = None
        self.visible = True
        self.failures = {}
        self.attempts = {}

    def arm(self, **failures):
        self.failures = failures
        self.attempts = {}

    def _fails(self, name):
        self.attempts[name] = self.attempts.get(name, 0) + 1
        return self.attempts[name] in self.failures.get(name, ())

    def dvz_item_state_buffer_update(self, bank, slots, words):
        result = super().dvz_item_state_buffer_update(bank, slots, words)
        return -1 if self._fails('state') else result

    def dvz_visual_set_data_many(self, visual, updates):
        if 'color' in updates and visual.name == 'mesh':
            self.colors = np.array(updates['color'], copy=True)
        return super().dvz_visual_set_data_many(visual, updates)

    def dvz_visual_set_data(self, visual, name, data):
        if name == 'color' and visual.name == 'mesh':
            if self._fails('colors'):
                return -1
            self.colors = np.array(data, copy=True)
        return super().dvz_visual_set_data(visual, name, data)

    def dvz_visual_set_index_data(self, visual, indices):
        if self._fails('indices'):
            return -1
        self.indices = np.array(indices, copy=True)
        return super().dvz_visual_set_index_data(visual, indices)

    def dvz_visual_set_target_link_keys(self, visual, target, channel, keys):
        if self._fails('keys'):
            return -1
        self.keys = np.array(keys, copy=True)
        return super().dvz_visual_set_target_link_keys(visual, target, channel, keys)

    def dvz_visual_set_alpha_mode(self, visual, mode):
        if self._fails('alpha'):
            return -1
        self.mode = mode
        return super().dvz_visual_set_alpha_mode(visual, mode)

    def dvz_visual_set_link_keys(self, visual, channel, keys):
        if self._fails('probe_keys'):
            return -1
        self.probe_keys = np.array(keys, copy=True)
        return super().dvz_visual_set_link_keys(visual, channel, keys)

    def dvz_visual_set_visible(self, visual, visible):
        if self._fails('visibility'):
            return -1
        self.visible = bool(visible)
        return 0


@pytest.fixture
def viewer():
    mesh = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    catalog = open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json')
    with AtlasViewer(mesh, catalog=catalog, datoviz=TransactionNative()) as result:
        yield result


def native_snapshot(viewer):
    native = viewer.dvz
    return (
        native.colors.copy(),
        native.indices.copy(),
        native.keys.copy(),
        native.mode,
        native.visible,
        viewer._surface_state.handle.words.copy(),
        viewer._surface_state.handle.active,
        viewer._surface_state.handle.context_alpha,
    )


def assert_native_restored(viewer, before):
    for current, previous in zip(native_snapshot(viewer), before, strict=True):
        np.testing.assert_array_equal(current, previous)


def select(viewer):
    viewer._apply_selected_region_ids(
        (315,), update_tree=False, update_table=False, clear_mesh=False
    )
    viewer.dvz.mesh_selection = [315]
    viewer._last_mesh_region_ids = (315,)


@pytest.mark.parametrize('failure', ['keys', 'colors', 'visibility'])
def test_region_data_failure_restores_scalar_state_caches_and_selection(viewer, failure):
    previous = AtlasRegionValues.from_arrays([315], [0.5])
    viewer._set_owned_region_data(previous, mapping_reduction='weighted_mean')
    select(viewer)
    before = native_snapshot(viewer)
    cache = viewer._surface_presentation.base_colors
    viewer.dvz.arm(**{failure: (1,)})
    with pytest.raises(RuntimeError):
        viewer._set_owned_region_data(
            AtlasRegionValues.from_arrays([315], [2]),
            opacity=0,
            color_scheme='diverging',
            value_range=(-2, 3),
            mapping_reduction='weighted_mean',
        )
    assert viewer.region_data is previous
    assert viewer._region_value_range is None and viewer._region_color_scheme == 'sequential'
    assert viewer._region_opacity is None
    assert viewer._surface_presentation.base_colors is cache
    assert viewer._selected_region_ids == (315,) and viewer.dvz.mesh_selection == [315]
    assert_native_restored(viewer, before)


def test_scalar_alpha_mode_failure_leaves_prior_payload_and_mode(viewer):
    before = native_snapshot(viewer)
    viewer.dvz.arm(alpha=(1,))
    with pytest.raises(RuntimeError, match='transparency mode'):
        viewer._set_owned_region_data(
            AtlasRegionValues.from_arrays([315], [1]),
            opacity=0.3,
            mapping_reduction='weighted_mean',
        )
    assert viewer.region_data is None
    assert viewer._region_opacity is None
    assert_native_restored(viewer, before)


def test_scalar_update_preserves_gpu_decoration_without_dense_recolor(viewer):
    select(viewer)
    bank = viewer._surface_state.handle
    words = bank.words.copy()
    before = len(viewer.dvz.calls)
    viewer._set_owned_region_data(
        AtlasRegionValues.from_arrays([315], [1]), mapping_reduction='weighted_mean'
    )
    calls = viewer.dvz.calls[before:]
    assert viewer._surface_state.handle is bank
    assert viewer._selected_region_ids == (315,) and bank.active
    np.testing.assert_array_equal(bank.words, words)
    assert len([c for c in calls if c[:3] == ('data', 'mesh', 'color')]) == 1
    assert not any(c[0] == 'state_update' for c in calls)


@pytest.mark.parametrize('failure', ['keys', 'colors', 'visibility', 'alpha'])
def test_style_failure_restores_authored_state_colors_and_native_mode(viewer, failure):
    before = native_snapshot(viewer)
    cache = viewer._surface_presentation.base_colors
    style = viewer._surface_presentation.style
    viewer.dvz.arm(**{failure: (1,)})
    with pytest.raises(RuntimeError):
        viewer.set_region_opacity(315, 0.5)
    assert viewer._surface_presentation.style is style and not style.regions
    assert viewer._surface_presentation.base_colors is cache
    assert_native_restored(viewer, before)


@pytest.mark.parametrize('failure', ['indices', 'keys', 'colors', 'visibility', 'state'])
def test_mapping_failure_restores_identity_palette_tree_caches_and_native_selection(
    viewer, failure
):
    select(viewer)
    before = native_snapshot(viewer)
    model, palette, cache = (
        viewer.tree_model,
        viewer.palette,
        viewer._surface_presentation.base_colors,
    )
    viewer.dvz.arm(**{failure: (1,)})
    with pytest.raises(RuntimeError):
        viewer.set_mapping('cosmos', palette={315: (10, 20, 30, 0), -315: (40, 50, 60, 255)})
    assert viewer.mapping == 'allen' and viewer.tree_model is model and viewer.palette is palette
    assert viewer._surface_presentation.base_colors is cache
    assert viewer._mapping_control.value == viewer.mesh_data.mapping_names.index('allen')
    assert viewer._selected_region_ids == (315,) and viewer.dvz.mesh_selection == [315]
    assert viewer._last_mesh_region_ids == (315,)
    assert_native_restored(viewer, before)


def test_mapping_alpha_failure_preserves_opaque_state(viewer):
    before = native_snapshot(viewer)
    viewer.dvz.arm(alpha=(1,))
    with pytest.raises(RuntimeError):
        viewer.set_mapping('cosmos', palette={315: (10, 20, 30, 128)})
    assert viewer.mapping == viewer.tree_model.mapping == 'allen'
    assert_native_restored(viewer, before)


def test_successful_explicit_palette_mapping_updates_tree_identity(viewer):
    viewer.set_mapping('cosmos', palette={315: (10, 20, 30, 128)})
    assert viewer.mapping == viewer.tree_model.mapping == 'cosmos'
    assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT


def test_mapping_probe_identity_failure_restores_owned_keys_and_committed_selection(viewer):
    viewer._probe_presentation.set_data(ProbeSites.from_arrays([[0, 0, 0]], [1], [315]))
    select(viewer)
    snapshot = native_snapshot(viewer)
    probe_snapshot = viewer._probe_presentation.upload
    native_probe_keys = viewer.dvz.probe_keys.copy()
    viewer.dvz.arm(probe_keys=(1,))
    with pytest.raises(RuntimeError, match='probe site mapping link keys'):
        viewer.set_mapping('beryl')
    assert viewer.mapping == viewer.tree_model.mapping == 'allen'
    assert viewer._probe_presentation.upload is probe_snapshot
    assert viewer._selected_region_ids == (315,) and viewer.dvz.mesh_selection == [315]
    np.testing.assert_array_equal(viewer.dvz.probe_keys, native_probe_keys)
    assert_native_restored(viewer, snapshot)


def test_mapping_selection_clear_failure_preserves_public_selection(viewer, monkeypatch):
    select(viewer)
    snapshot = native_snapshot(viewer)
    monkeypatch.setattr(viewer.dvz, 'dvz_selection_clear', lambda *args: -1)
    with pytest.raises(RuntimeError, match='mapping selection reset'):
        viewer.set_mapping('cosmos')
    assert viewer.mapping == viewer.tree_model.mapping == 'allen'
    assert viewer._selected_region_ids == (315,) and viewer.dvz.mesh_selection == [315]
    assert_native_restored(viewer, snapshot)


@pytest.mark.parametrize('operation', ['style', 'mapping', 'scalar'])
def test_failed_alpha_rollback_closes_viewer(operation, viewer):
    viewer.dvz.arm(alpha=(1, 2))
    with pytest.raises(RuntimeError, match='rollback failed; viewer closed'):
        if operation == 'style':
            viewer.set_region_opacity(315, 0.5)
        elif operation == 'mapping':
            viewer.set_mapping('cosmos', palette={315: (10, 20, 30, 128)})
        else:
            viewer._set_owned_region_data(
                AtlasRegionValues.from_arrays([315], [1]),
                opacity=0.3,
                mapping_reduction='weighted_mean',
            )
    assert viewer._closed and viewer.scene is None
    assert ('destroy_scene',) in viewer.dvz.calls


def test_zero_alpha_palette_filters_canonical_midline_faces_through_selection():
    mesh = AtlasMesh.from_pack(FIXTURES / 'mesh-pack-v1' / 'pack')
    native = TransactionNative()
    with AtlasViewer(
        mesh, datoviz=native, palette={-315: (10, 20, 30, 0), 315: (40, 50, 60, 255)}
    ) as viewer:
        render = viewer._surface_mesh
        assert np.any(mesh.face_mapping_ids('allen') < 0)
        assert np.all(native.keys.view(np.int64) > 0)
        assert len(native.keys) == np.count_nonzero(render.face_mapping_ids('allen') > 0)
        viewer._apply_selected_region_ids(
            (-315,), update_tree=False, update_table=False, clear_mesh=False
        )
        assert np.all(native.keys.view(np.int64) > 0)
        assert np.all(native.colors[render.mapping_ids('allen') < 0, 3] == 0)
