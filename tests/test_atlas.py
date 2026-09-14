from __future__ import annotations

import ctypes
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_atlas_assets import open_mesh_pack, open_region_catalog
from ibl_datoviz import (
    AtlasMesh,
    AtlasTreeModel,
    AtlasViewer,
    ProbeSites,
    decode_region_key,
    encode_region_key,
)

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / 'ibl-atlas-assets'
    / 'tests'
    / 'fixtures'
    / 'mesh-pack-v1'
    / 'pack'
)
REGIONS = (
    Path(__file__).resolve().parents[2]
    / 'ibl-atlas-assets'
    / 'tests'
    / 'fixtures'
    / 'atlas-regions-v1'
    / 'regions.json'
)


class FakeItemInteractionDesc(ctypes.Structure):
    _fields_ = [('target', ctypes.c_int)]


class FakeSelectionItem(ctypes.Structure):
    _fields_ = [('link_key', ctypes.c_uint64)]


class FakeDatoviz:
    DvzSelectionItem = FakeSelectionItem
    DVZ_QUERY_CAPABILITY_FACE = 4
    DVZ_SCENE_TARGET_FACE = 4
    DVZ_GUI_DATA_EVENT_SELECTION_CHANGED = 1
    DVZ_GUI_DATA_STYLE_FLAGS_FOREGROUND = 1
    DVZ_GUI_DATA_STYLE_FLAGS_DISABLED = 8
    DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT = 1
    DVZ_GUI_DATA_WIDGET_FLAGS_FILTER = 2
    DVZ_GUI_DATA_SET_FLAGS_RESET_STATE = 1
    DVZ_SEGMENT_CAP_ROUND = 1
    DVZ_PATH_JOIN_ROUND = 1
    DVZ_ALPHA_WBOIT = 2
    DVZ_GUI_TABLE_COLUMN_TEXT = 0
    DVZ_GUI_TABLE_COLUMN_DOUBLE = 2
    DVZ_GUI_TABLE_COLUMN_COLOR = 4
    DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE = 1
    DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE = 2
    DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH = 4

    def __init__(self):
        self.calls = []
        self.mesh_selection = []
        self.tree_selection = []
        self.table_selection = []

    def _handle(self, name):
        value = SimpleNamespace(name=name)
        self.calls.append((name,))
        return value

    @staticmethod
    def DvzColor(*rgba):  # noqa: N802 - mirrors the generated Datoviz type
        return rgba

    def dvz_scene(self):
        return self._handle('scene')

    def dvz_figure(self, *_args):
        return self._handle('figure')

    def dvz_panel_full(self, *_args):
        return self._handle('panel')

    def dvz_panel_set_background_color(self, *_args):
        return 0

    def dvz_mesh(self, *_args):
        return self._handle('mesh')

    def dvz_path(self, *_args):
        return self._handle('path')

    def dvz_sphere(self, *_args):
        return self._handle('sphere')

    def dvz_visual_set_data_many(self, visual, updates):
        self.calls.append(('data_many', visual.name, tuple(updates), updates))
        return 0

    def dvz_visual_set_data(self, visual, name, data):
        self.calls.append(('data', visual.name, name, np.array(data, copy=True)))
        return 0

    def dvz_visual_set_index_data(self, _visual, indices):
        self.calls.append(('indices', np.array(indices, copy=True)))
        return 0

    def dvz_visual_set_query_capabilities(self, *_args):
        return 0

    def dvz_visual_set_alpha_mode(self, visual, mode):
        self.calls.append(('alpha_mode', visual.name, mode))
        return 0

    def dvz_link_channel(self, *_args):
        return self._handle('link_channel')

    def dvz_visual_set_target_link_keys(self, _visual, target, _channel, keys):
        self.calls.append(('link_keys', target, np.array(keys, copy=True)))
        return 0

    def dvz_gui_tree(self, *_args):
        return self._handle('region_tree')

    def dvz_gui_tree_set_rows(self, _tree, keys, parents, labels, names, flags):
        self.calls.append(
            (
                'tree_rows',
                np.array(keys, copy=True),
                np.array(parents, copy=True),
                tuple(labels),
                tuple(names),
                flags,
            )
        )
        return 0

    def dvz_gui_tree_set_swatches(self, _tree, colors):
        self.calls.append(('tree_swatches', np.array(colors, copy=True)))
        return 0

    @staticmethod
    def dvz_gui_data_style():
        return SimpleNamespace(flags=0, row_key=0, foreground=None)

    def dvz_gui_tree_set_styles(self, _tree, styles):
        self.calls.append(('tree_styles', tuple(styles)))
        return 0

    def dvz_gui_tree_set_selection(self, _tree, keys):
        self.tree_selection = [int(key) for key in keys]
        self.calls.append(('tree_selection', tuple(self.tree_selection)))
        return 0

    def dvz_gui_tree_get_selection(self, _tree):
        return list(self.tree_selection)

    def dvz_gui_tree_reveal(self, _tree, key):
        self.calls.append(('tree_reveal', int(key)))
        return 0

    def dvz_gui_tree_expand_to_depth(self, _tree, depth):
        self.calls.append(('tree_depth', depth))
        return 0

    def dvz_gui_tree_destroy(self, *_args):
        self.calls.append(('tree_destroy',))

    def dvz_gui_table(self, _name, columns, flags):
        self.calls.append(('table_create', tuple(columns), flags))
        return SimpleNamespace(name='probe_table')

    def dvz_gui_table_set_rows(self, _table, keys, flags=0):
        self.calls.append(('table_rows', np.array(keys, copy=True), flags))
        return 0

    def dvz_gui_table_set_column_text(self, _table, column, values):
        self.calls.append(('table_text', column, tuple(values)))
        return 0

    def dvz_gui_table_set_column_double(self, _table, column, values):
        self.calls.append(('table_double', column, np.array(values, copy=True)))
        return 0

    def dvz_gui_table_set_column_color(self, _table, column, values):
        self.calls.append(('table_color', column, np.array(values, copy=True)))
        return 0

    def dvz_gui_table_set_selection(self, _table, keys):
        self.table_selection = [int(key) for key in keys]
        self.calls.append(('table_selection', tuple(self.table_selection)))
        return 0

    def dvz_gui_table_get_selection(self, _table):
        return list(self.table_selection)

    def dvz_gui_table_destroy(self, *_args):
        self.calls.append(('table_destroy',))

    def dvz_visual_set_link_keys(self, _visual, _channel, keys):
        self.calls.append(('item_link_keys', np.array(keys, copy=True)))
        return 0

    def dvz_panel_add_visual(self, *_args):
        return 0

    @staticmethod
    def dvz_item_interaction_desc():
        return FakeItemInteractionDesc()

    def dvz_item_interaction(self, *_args):
        return self._handle('interaction')

    def dvz_item_interaction_selection(self, *_args):
        return self._handle('selection')

    def dvz_selection_count(self, _selection):
        return len(self.mesh_selection)

    def dvz_selection_copy(self, _selection, items, count):
        for index, key in enumerate(self.mesh_selection[:count]):
            items[index].link_key = key
        return len(self.mesh_selection)

    def dvz_selection_clear(self, *_args):
        self.mesh_selection = []
        self.calls.append(('selection_clear',))
        return 0

    def dvz_path_set_caps(self, *_args):
        return 0

    def dvz_path_set_join(self, *_args):
        return 0

    def dvz_app_destroy(self, *_args):
        self.calls.append(('destroy_app',))

    def dvz_scene_destroy(self, *_args):
        self.calls.append(('destroy_scene',))


@pytest.fixture(scope='module')
def mesh():
    return AtlasMesh.from_pack(FIXTURE)


def test_mesh_pack_preserves_signed_presentation_identity(mesh):
    assert mesh.reference_space == 'allen-ccf-2017'
    assert mesh.positions.shape == (10, 3)
    assert mesh.positions.dtype == np.float32
    assert mesh.normals.shape == (10, 3)
    assert mesh.normals.dtype == np.float32
    assert mesh.indices.shape == (36,)
    assert mesh.indices.dtype == np.uint32
    assert mesh.mapping_names == ('allen', 'beryl', 'cosmos')
    np.testing.assert_array_equal(mesh.presentation_ids, [0, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    np.testing.assert_array_equal(
        mesh.mapping_ids('allen'), [-315, 315, 315, 315, 315, 315, 315, 315, 315, 315]
    )
    np.testing.assert_array_equal(mesh.mapping_ids('beryl'), np.zeros(10, dtype=np.int64))
    np.testing.assert_array_equal(
        mesh.face_mapping_ids('allen'),
        [-315, -315, -315, -315, 315, 315, 315, 315, 315, 315, 315, 315],
    )
    np.testing.assert_array_equal(
        mesh.link_keys('allen').view(np.int64), mesh.face_mapping_ids('allen')
    )


def test_mapping_palette_accepts_signed_and_unsigned_region_keys(mesh):
    colors = mesh.colors('allen', {-315: (10, 20, 30), 315: (40, 50, 60, 70)})
    np.testing.assert_array_equal(colors[0], [10, 20, 30, 255])
    np.testing.assert_array_equal(colors[1:], np.tile([40, 50, 60, 70], (9, 1)))
    np.testing.assert_array_equal(mesh.colors('beryl'), np.tile([90, 98, 108, 255], (10, 1)))
    with pytest.raises(KeyError, match='unknown atlas mapping'):
        mesh.mapping_ids('unknown')


def test_viewer_switches_mapping_without_geometry_upload(mesh):
    fake = FakeDatoviz()
    viewer = AtlasViewer(mesh, datoviz=fake, width=100, height=80)
    initial_uploads = [call for call in fake.calls if call[0] in {'data_many', 'indices'}]
    assert len(initial_uploads) == 2
    positions_id = id(mesh.positions)

    viewer.set_mapping('beryl')

    assert id(mesh.positions) == positions_id
    later_uploads = [call for call in fake.calls if call[0] in {'data_many', 'indices'}]
    assert later_uploads == initial_uploads
    assert [call[2] for call in fake.calls if call[0] == 'data'] == ['color']
    assert viewer.mapping == 'beryl'
    assert viewer.selected_region_ids() == ()
    viewer.close()
    assert fake.calls[-1] == ('destroy_scene',)

    with pytest.raises(ValueError, match='selection_dim_factor'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), selection_dim_factor=1.1)
    with pytest.raises(ValueError, match='surface_opacity'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), surface_opacity=-0.1)
    with pytest.raises(ValueError, match='surface_opacity'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), surface_opacity=np.nan)


def test_translucent_surface_uses_wboit_and_preserves_alpha(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, surface_opacity=0.25) as viewer:
        initial = next(call for call in fake.calls if call[:2] == ('data_many', 'mesh'))[3]
        np.testing.assert_array_equal(initial['color'][:, 3], [64] * len(mesh.positions))
        assert ('alpha_mode', 'mesh', fake.DVZ_ALPHA_WBOIT) in fake.calls

        viewer.set_mapping('beryl')
        mapping_colors = [call for call in fake.calls if call[:3] == ('data', 'mesh', 'color')][-1]
        np.testing.assert_array_equal(mapping_colors[3][:, 3], [64] * len(mesh.positions))

        viewer.set_selected_region_ids([-315])
        color_calls = [call for call in fake.calls if call[:3] == ('data', 'mesh', 'color')]
        selected_colors = color_calls[-1]
        np.testing.assert_array_equal(selected_colors[3][:, 3], [64] * len(mesh.positions))


def test_probe_uses_same_display_transform(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_probe([[-2, 0, 0], [5, 0, 0]])
    probe_upload = [call for call in fake.calls if call[:2] == ('data_many', 'path')]
    assert len(probe_upload) == 1
    positions = probe_upload[0][3]['position']
    np.testing.assert_allclose(positions[:, 0], [-0.8, 0.8])


def test_probe_sites_use_world_transform_and_scalar_colors(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_probe_sites(
            [[-2, 0, 0], [1.5, 0, 0], [5, 0, 0]],
            values=[-1, np.nan, 1],
            value_range=(-1, 1),
            radius_um=0.25,
        )
    upload = next(call for call in fake.calls if call[:2] == ('data_many', 'sphere'))[3]
    np.testing.assert_allclose(upload['position'][:, 0], [-0.8, 0, 0.8])
    np.testing.assert_array_equal(upload['color'][0], [49, 116, 178, 255])
    np.testing.assert_array_equal(upload['color'][1], [110, 116, 126, 255])
    np.testing.assert_array_equal(upload['color'][2], [203, 45, 62, 255])
    np.testing.assert_allclose(upload['radius'], np.full(3, 0.25 * mesh.display_scale))

    with AtlasViewer(mesh, datoviz=FakeDatoviz()) as viewer:
        with pytest.raises(ValueError, match='values or colors'):
            viewer.set_probe_sites([[0, 0, 0]], values=[1], colors=[[1, 2, 3]])
        with pytest.raises(ValueError, match='probe colors'):
            viewer.set_probe_sites([[0, 0, 0]], colors=[[300, 2, 3]])
        with pytest.raises(ValueError, match='value range'):
            viewer.set_probe_sites([[0, 0, 0]], values=[1], value_range=(1, 1))


def test_typed_probe_sites_link_table_and_mapping(mesh):
    catalog = open_region_catalog(REGIONS)
    data = ProbeSites.from_arrays(
        [[-2, 0, 0], [1.5, 0, 0], [5, 0, 0]],
        [-1, 0, 1],
        [-8, 8, 0],
        site_ids=[11, 12, 13],
        labels=['left', 'right', 'outside'],
    )
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        viewer.set_probe_data(data, value_range=(-1, 1))
        item_keys = next(call for call in fake.calls if call[0] == 'item_link_keys')[1]
        np.testing.assert_array_equal(item_keys.view(np.int64), [-8, 8, 0])

        viewer._replace_region_tree()
        viewer._replace_probe_table()
        assert next(call for call in fake.calls if call[0] == 'table_text')[2] == (
            'left',
            'right',
            'outside',
        )
        fake.table_selection = [11]
        viewer._sync_selection_highlight(table_changed=True)
        assert viewer.selected_region_ids() == (-8,)
        assert fake.tree_selection == [encode_region_key(-8)]

        viewer.set_mapping('beryl')
        item_keys = [call for call in fake.calls if call[0] == 'item_link_keys'][-1][1]
        np.testing.assert_array_equal(item_keys.view(np.int64), [997, 997, 0])

    with (
        AtlasViewer(mesh, datoviz=FakeDatoviz()) as viewer,
        pytest.raises(ValueError, match='region catalog'),
    ):
        viewer.set_probe_data(data)

    unknown = ProbeSites.from_arrays([[0, 0, 0]], [1], [123456789])
    with (
        AtlasViewer(mesh, catalog=catalog, datoviz=FakeDatoviz()) as viewer,
        pytest.raises(ValueError, match='absent'),
    ):
        viewer.set_probe_data(unknown)


def test_region_tree_model_preserves_signed_identity_and_canonical_colors():
    model = AtlasTreeModel.from_catalog(open_region_catalog(REGIONS), 'allen')
    np.testing.assert_array_equal(model.region_ids, [-997, -8])
    np.testing.assert_array_equal(model.parents, [2**32 - 1, 0])
    assert model.acronyms == ('root', 'grey')
    assert model.names == ('root', 'Basic cell groups and regions')
    np.testing.assert_array_equal(model.colors[1], [191, 218, 227, 255])
    assert model.palette[-8] == (191, 218, 227, 255)
    assert model.palette[8] == (191, 218, 227, 255)
    assert model.selectable_region_ids == {-997, -8}
    assert model.expanded_logical_ids((-997,)) == (8, 997)
    assert model.describe(8) == 'grey — Basic cell groups and regions'
    for region_id in model.region_ids:
        assert decode_region_key(encode_region_key(int(region_id))) == region_id


def test_viewer_uploads_catalog_to_one_retained_tree_batch(mesh):
    fake = FakeDatoviz()
    catalog = open_region_catalog(REGIONS)
    with AtlasViewer(mesh, datoviz=fake, catalog=catalog) as viewer:
        viewer._replace_region_tree()
        row_call = next(call for call in fake.calls if call[0] == 'tree_rows')
        assert row_call[3:] == (
            ('root', 'grey'),
            ('root', 'Basic cell groups and regions'),
            fake.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
        )
        np.testing.assert_array_equal(row_call[2], [2**32 - 1, 0])
        assert sum(call[0] == 'tree_rows' for call in fake.calls) == 1


def test_viewer_uses_one_authoritative_selection_source(mesh):
    fake = FakeDatoviz()
    catalog = open_region_catalog(REGIONS)
    with AtlasViewer(mesh, datoviz=fake, catalog=catalog) as viewer:
        viewer._replace_region_tree()
        fake.tree_selection = [encode_region_key(-8)]
        fake.mesh_selection = [encode_region_key(-997)]

        viewer._sync_selection_highlight(tree_changed=True)

        assert viewer.selected_region_ids() == (-8,)
        assert fake.mesh_selection == []

        fake.mesh_selection = [encode_region_key(-997)]
        viewer._sync_selection_highlight()

        assert viewer.selected_region_ids() == (-997,)
        assert fake.tree_selection == [encode_region_key(-997)]

        fake.mesh_selection = []
        viewer._sync_selection_highlight()

        assert viewer.selected_region_ids() == ()
        assert fake.tree_selection == []


def test_programmatic_selection_highlights_descendants(mesh):
    fake = FakeDatoviz()
    catalog = open_region_catalog(REGIONS)
    with AtlasViewer(mesh, datoviz=fake, catalog=catalog) as viewer:
        viewer._replace_region_tree()
        viewer.set_selected_region_ids([-997])

        assert viewer.selected_region_ids() == (-997,)
        assert viewer._highlight_region_ids == (8, 997)
        assert fake.tree_selection == [encode_region_key(-997)]

        with pytest.raises(ValueError, match='not members of allen'):
            viewer.set_selected_region_ids([123456])


def test_viewer_constructs_from_verified_assets():
    fake = FakeDatoviz()
    assets = SimpleNamespace(
        geometry=open_mesh_pack(FIXTURE).load_geometry(),
        regions=open_region_catalog(REGIONS),
    )
    with AtlasViewer.from_assets(assets, datoviz=fake) as viewer:
        assert viewer.catalog is assets.regions
        assert viewer.mesh_data.reference_space == assets.regions.reference_space_id
    with pytest.raises(TypeError, match='verified region catalog'):
        AtlasViewer.from_assets(assets, datoviz=fake, catalog=assets.regions)
