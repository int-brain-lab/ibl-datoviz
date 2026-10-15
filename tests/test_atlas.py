from __future__ import annotations

import ctypes
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_mesh_pack, open_region_catalog
from ibl_datoviz import (
    AtlasMesh,
    AtlasRegionValues,
    AtlasTreeModel,
    AtlasViewer,
    ProbeSites,
)
from ibl_datoviz.ontology import decode_region_key, encode_region_key
from tests import FIXTURES

FIXTURE = FIXTURES / 'mesh-pack-v1' / 'pack'
REGIONS = FIXTURES / 'atlas-regions-v1' / 'regions.json'


class FakeItemInteractionDesc(ctypes.Structure):
    _fields_ = [('target', ctypes.c_int)]


class FakeSelectionItem(ctypes.Structure):
    _fields_ = [('link_key', ctypes.c_uint64)]


class FakeTreeTextSpan(ctypes.Structure):
    _fields_ = [('start', ctypes.c_uint32), ('length', ctypes.c_uint32)]


class FakeTreeLayout(ctypes.Structure):
    _fields_ = [('flags', ctypes.c_uint32)] + [
        (name, ctypes.c_float)
        for name in (
            'indent_em',
            'row_padding_em',
            'item_spacing_em',
            'disclosure_gap_em',
            'swatch_gap_em',
            'secondary_gap_em',
        )
    ]


class FakeTreeAnnotation(ctypes.Structure):
    _fields_ = [
        ('flags', ctypes.c_uint32),
        ('row_key', ctypes.c_uint64),
        ('value_text', ctypes.c_char_p),
        ('tooltip', ctypes.c_char_p),
        ('label_span_count', ctypes.c_uint32),
        ('label_spans', ctypes.POINTER(FakeTreeTextSpan)),
        ('secondary_span_count', ctypes.c_uint32),
        ('secondary_spans', ctypes.POINTER(FakeTreeTextSpan)),
    ]


class FakeItemStateBufferDesc(ctypes.Structure):
    _fields_ = [('slot_count', ctypes.c_uint32), ('words', ctypes.POINTER(ctypes.c_uint32))]


class FakeStateStyle(ctypes.Structure):
    _fields_ = [('struct_size', ctypes.c_uint32)]


class FakeDatoviz:
    DVZ_GUI_TREE_LAYOUT_FLAGS_EXACT_SPACING = 1
    DVZ_GUI_TREE_LAYOUT_FLAGS_READABLE_SECONDARY = 2
    DvzSelectionItem = FakeSelectionItem
    DvzGuiTreeTextSpan = FakeTreeTextSpan
    DVZ_GUI_DATA_WIDGET_FLAGS_CONTROLLED = 4
    DVZ_GUI_TREE_ANNOTATION_FLAGS_MISSING = 1
    DVZ_GUI_DATA_EVENT_ROW_CLICKED = 6
    DVZ_GUI_DATA_EVENT_DISCLOSURE_CLICKED = 7
    DVZ_GUI_DATA_EVENT_KEY_PRESSED = 8
    DVZ_GUI_DATA_EVENT_HOVER_CHANGED = 9
    DVZ_GUI_DATA_EVENT_FOCUS_CHANGED = 10
    DVZ_KEY_UP, DVZ_KEY_DOWN, DVZ_KEY_LEFT, DVZ_KEY_RIGHT = 265, 264, 263, 262
    DVZ_KEY_HOME, DVZ_KEY_END, DVZ_KEY_ENTER, DVZ_KEY_SPACE = 268, 269, 257, 32
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
    DVZ_ITEM_STATE_HOVERED = 1
    DVZ_ITEM_STATE_SELECTED = 2
    DVZ_ITEM_STATE_VISUAL_ALPHA = 1
    DVZ_ITEM_STATE_VISUAL_TINT = 2
    DVZ_ALPHA_OPAQUE = 0
    DVZ_ALPHA_WBOIT = 2
    DVZ_GUI_TABLE_COLUMN_TEXT = 0
    DVZ_GUI_TABLE_COLUMN_DOUBLE = 2
    DVZ_GUI_TABLE_COLUMN_COLOR = 4
    DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE = 1
    DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE = 2
    DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH = 4

    def __init__(self, *, fail_on=None):
        self.calls = []
        self.fail_on = fail_on
        self.mesh_selection = []
        self.mesh_hover = None
        self.tree_selection = []
        self.table_selection = []

    def _handle(self, name):
        if name == self.fail_on:
            self.calls.append((f'{name}_failed',))
            return None
        value = SimpleNamespace(name=name)
        self.calls.append((name,))
        return value

    @staticmethod
    def DvzColor(*rgba):  # noqa: N802 - mirrors the generated Datoviz type
        return rgba

    @staticmethod
    def dvz_item_state_buffer_desc():
        return FakeItemStateBufferDesc()

    @staticmethod
    def dvz_selection_visual_style():
        return FakeStateStyle()

    @staticmethod
    def dvz_item_state_visual_style():
        return FakeStateStyle()

    def dvz_item_state_buffer(self, _scene, descriptor):
        bank = self._handle('item_state_buffer')
        if bank is not None:
            desc = descriptor._obj
            bank.words = np.ctypeslib.as_array(desc.words, shape=(desc.slot_count,)).copy()
        return bank

    def dvz_visual_set_item_state_buffer(self, _visual, _bank, indices):
        self.calls.append(('state_binding', np.array(indices, copy=True)))
        return 0

    def dvz_item_state_buffer_update(self, bank, slots, words):
        bank.words[slots] = words
        self.calls.append(('state_update', np.array(slots, copy=True), np.array(words, copy=True)))
        return 0

    def dvz_item_state_buffer_style(self, bank, selection, hovered, active):
        bank.active = bool(active)
        bank.context_alpha = selection._obj.unselected_alpha
        bank.tint_mix = hovered._obj.tint_mix
        self.calls.append(('state_style', bank.active, bank.context_alpha, bank.tint_mix))
        return 0

    def dvz_item_state_buffer_destroy(self, _bank):
        self.calls.append(('state_destroy',))

    def dvz_scene(self):
        return self._handle('scene')

    def dvz_figure(self, *_args):
        return self._handle('figure')

    def dvz_panel_full(self, *_args):
        return self._handle('panel')

    def dvz_panel_set_background_color(self, *_args):
        return 0

    @staticmethod
    def dvz_camera_desc():
        return SimpleNamespace(
            view=SimpleNamespace(eye=[0.0] * 3, target=[0.0] * 3, up=[0.0] * 3),
            projection=SimpleNamespace(fov_y=0.0, near_clip=0.0, far_clip=0.0),
        )

    def dvz_panel_set_camera_desc(self, _panel, camera):
        self.calls.append(
            (
                'camera',
                tuple(camera.view.eye),
                tuple(camera.view.target),
                tuple(camera.view.up),
                camera.projection.fov_y,
                camera.projection.near_clip,
                camera.projection.far_clip,
            )
        )
        return 0

    def dvz_mesh(self, *_args):
        return self._handle('mesh')

    def dvz_scene_default_ambient(self, *_args):
        return SimpleNamespace(name='ambient_light')

    def dvz_light_set_intensity(self, light, intensity):
        self.calls.append(('light_intensity', light.name, intensity))
        return 0

    @staticmethod
    def dvz_phong_material_desc():
        return SimpleNamespace(
            phong=SimpleNamespace(ambient=0.24, diffuse=0.82, specular=0.24, shininess=26.0)
        )

    def dvz_visual_set_material(self, visual, material):
        self.calls.append(
            (
                'material',
                visual.name,
                material.phong.ambient,
                material.phong.diffuse,
                material.phong.specular,
                material.phong.shininess,
            )
        )
        return 0

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

    def dvz_mesh_set_fragment_clip(self, _visual, clip):
        self.calls.append(('fragment_clip', np.array(clip, copy=True)))
        return 0

    def dvz_visual_set_index_data(self, _visual, indices):
        self.calls.append(('indices', np.array(indices, copy=True)))
        return 0

    def dvz_visual_set_visible(self, visual, visible):
        self.calls.append(('visible', visual.name, bool(visible)))
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

    @staticmethod
    def dvz_gui_tree_layout():
        return FakeTreeLayout()

    def dvz_gui_tree_set_layout(self, _tree, layout):
        self.calls.append(('tree_layout', layout._obj.flags, layout._obj.item_spacing_em))
        return 0

    @staticmethod
    def dvz_gui_tree_annotation():
        return FakeTreeAnnotation()

    def dvz_gui_tree_set_projection(self, _tree, keys, depths, branches, selectable):
        self.calls.append(
            (
                'tree_projection',
                *(np.array(data, copy=True) for data in (keys, depths, branches, selectable)),
            )
        )
        return 0

    def dvz_gui_tree_set_expanded(self, _tree, keys):
        self.calls.append(('tree_expanded', tuple(int(key) for key in keys)))
        return 0

    def dvz_gui_tree_set_focus(self, _tree, key):
        self.calls.append(('tree_focus', int(key)))
        return 0

    def dvz_gui_tree_set_annotations(self, _tree, annotations):
        self.calls.append(
            (
                'tree_annotations',
                tuple(
                    {
                        'row_key': row.row_key,
                        'value': row.value_text,
                        'tooltip': row.tooltip,
                        'flags': row.flags,
                        'label': [
                            (row.label_spans[i].start, row.label_spans[i].length)
                            for i in range(row.label_span_count)
                        ],
                        'secondary': [
                            (row.secondary_spans[i].start, row.secondary_spans[i].length)
                            for i in range(row.secondary_span_count)
                        ],
                    }
                    for row in annotations
                ),
            )
        )
        return 0

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

    def dvz_item_interaction_hover(self, *_args):
        return self._handle('hover')

    def dvz_hover_copy(self, _hover, out_item):
        if self.mesh_hover is None:
            return False
        out_item._obj.link_key = self.mesh_hover
        return True

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

    def dvz_arcball_set(self, _arcball, angles):
        self.calls.append(('arcball_set', tuple(float(value) for value in angles)))
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
    assert mesh.explode_offsets.shape == (10, 3)
    np.testing.assert_allclose(mesh.explode_offsets[:6], 0)
    np.testing.assert_allclose(
        mesh.explode_offsets[6:],
        np.tile(np.asarray([2.0, -0.125, 0.125]) * mesh.display_scale, (4, 1)),
    )
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


@pytest.mark.parametrize(
    'points',
    [
        [],
        [0, 1, 2],
        [[0, 1]],
        [[0, 1, 2, 3]],
        [[np.nan, 0, 0]],
        [[np.inf, 0, 0]],
        [[-np.inf, 0, 0]],
    ],
)
def test_mesh_rejects_invalid_world_points(mesh, points):
    with pytest.raises(ValueError, match='points must'):
        mesh.normalize_points(points)


def test_explode_uses_canonical_component_displacements(mesh):
    assert mesh.exploded_positions(0) is mesh.positions
    np.testing.assert_allclose(
        mesh.exploded_positions(0.5), mesh.positions + 0.5 * mesh.explode_offsets
    )
    assert mesh.exploded_positions(0.5).dtype == np.float32
    with pytest.raises(ValueError, match='between zero and one'):
        mesh.exploded_positions(1.1)


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


@pytest.mark.parametrize(
    ('stage', 'message', 'destroy_count'),
    [
        ('scene', 'dvz_scene', 0),
        ('figure', 'dvz_figure', 1),
        ('panel', 'dvz_panel_full', 1),
        ('mesh', 'dvz_mesh', 1),
        ('interaction', 'dvz_item_interaction', 1),
    ],
)
def test_viewer_constructor_failure_releases_scene(mesh, stage, message, destroy_count):
    fake = FakeDatoviz(fail_on=stage)
    with pytest.raises(RuntimeError, match=message):
        AtlasViewer(mesh, datoviz=fake)
    assert sum(call == ('destroy_scene',) for call in fake.calls) == destroy_count


def test_invalid_mapping_fails_before_native_allocation(mesh):
    fake = FakeDatoviz()
    with pytest.raises(ValueError, match='unknown atlas mapping'):
        AtlasViewer(mesh, datoviz=fake, mapping='unknown')
    assert ('scene',) not in fake.calls


def test_constructor_cleanup_avoids_partial_subclass_dispatch(mesh):
    class PartialViewer(AtlasViewer):
        def close(self):
            raise AssertionError('partial subclass close must not be dispatched')

    fake = FakeDatoviz(fail_on='figure')
    with pytest.raises(RuntimeError, match='dvz_figure'):
        PartialViewer(mesh, datoviz=fake)
    assert sum(call == ('destroy_scene',) for call in fake.calls) == 1


def test_context_manager_exception_closes_viewer(mesh):
    fake = FakeDatoviz()
    with pytest.raises(RuntimeError, match='body failure'), AtlasViewer(mesh, datoviz=fake):
        raise RuntimeError('body failure')
    assert sum(call == ('destroy_scene',) for call in fake.calls) == 1


def test_closed_viewer_rejects_native_operations(mesh):
    fake = FakeDatoviz()
    viewer = AtlasViewer(mesh, datoviz=fake)
    viewer.close()
    viewer.close()
    assert sum(call == ('destroy_scene',) for call in fake.calls) == 1
    before = len(fake.calls)
    region_data = AtlasRegionValues.from_arrays([-315], [1.0])
    probe_data = ProbeSites.from_arrays([[0, 0, 0]], [1.0], [-315])
    operations = (
        lambda: viewer.set_camera_angles((0, 0, 0)),
        lambda: viewer.set_explode(0.2),
        lambda: viewer.set_mapping('beryl'),
        lambda: viewer.set_probe([[0, 0, 0], [1, 1, 1]]),
        lambda: viewer.set_probe_sites([[0, 0, 0]]),
        lambda: viewer.set_probe_data(probe_data),
        lambda: viewer.set_region_data(region_data, mapping_reduction='weighted_mean'),
        lambda: viewer.set_selected_region_ids((-315,)),
        lambda: viewer.render_offscreen(),
        lambda: viewer.show(),
    )
    for operation in operations:
        with pytest.raises(RuntimeError, match='viewer is closed'):
            operation()
    assert len(fake.calls) == before


def test_minimal_surface_viewer_can_disable_item_interaction(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, enable_interaction=False) as viewer:
        assert viewer.interaction is None
        assert ('interaction',) not in fake.calls
        assert viewer._mesh_hovered_region_ids() == ()
        assert viewer._mesh_selected_region_ids() == ()


def test_viewer_explode_updates_only_positions(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, explode=0.25) as viewer:
        render_mesh = viewer._surface_mesh
        initial = next(call for call in fake.calls if call[:2] == ('data_many', 'mesh'))[3]
        np.testing.assert_allclose(initial['position'], render_mesh.exploded_positions(0.25))
        before = len(fake.calls)

        viewer.set_explode(0.75)

        updates = fake.calls[before:]
        assert len(updates) == 1
        assert updates[0][:3] == ('data', 'mesh', 'position')
        np.testing.assert_allclose(updates[0][3], render_mesh.exploded_positions(0.75))
        assert viewer.explode == 0.75
        assert viewer._explode_control.value == pytest.approx(0.75)

        viewer.set_explode(0.75)
        assert fake.calls[before:] == updates
        with pytest.raises(ValueError, match='between zero and one'):
            viewer.set_explode(-0.1)


def test_camera_angles_are_validated_stored_and_applied(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, camera_angles=(0.1, 0.2, 0.3)) as viewer:
        camera = next(call for call in fake.calls if call[0] == 'camera')
        assert camera[1:4] == ((0.0, 0.0, 3.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        np.testing.assert_allclose(camera[4:], (0.72, 0.01, 100.0))
        np.testing.assert_allclose(viewer.camera_angles, (0.1, 0.2, 0.3))
        viewer.arcball = SimpleNamespace(name='arcball')
        viewer.set_camera_angles((-0.4, 0.5, 0.6))
        np.testing.assert_allclose(fake.calls[-1][1], (-0.4, 0.5, 0.6))
        with pytest.raises(ValueError, match='three finite'):
            viewer.set_camera_angles((0, np.nan, 0))

    with pytest.raises(ValueError, match='selection_dim_factor'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), selection_dim_factor=1.1)
    with pytest.raises(ValueError, match='selection_context_opacity'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), selection_context_opacity=-0.1)
    with pytest.raises(ValueError, match='surface_opacity'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), surface_opacity=-0.1)
    with pytest.raises(ValueError, match='surface_opacity'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), surface_opacity=np.nan)
    with pytest.raises(ValueError, match='ui_scale'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), ui_scale=0)
    with pytest.raises(ValueError, match='sidebar_width'):
        AtlasViewer(mesh, datoviz=FakeDatoviz(), sidebar_width=0)


def test_translucent_surface_uses_wboit_and_preserves_alpha(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, surface_opacity=0.25) as viewer:
        render_mesh = viewer._surface_mesh
        initial = next(call for call in fake.calls if call[:2] == ('data_many', 'mesh'))[3]
        np.testing.assert_array_equal(initial['color'][:, 3], [64] * len(render_mesh.positions))
        assert ('alpha_mode', 'mesh', fake.DVZ_ALPHA_WBOIT) in fake.calls
        assert ('light_intensity', 'ambient_light', 0.65) in fake.calls
        assert ('material', 'mesh', 1.0, 0.45, 0.08, 24.0) in fake.calls

        viewer.set_mapping('beryl')
        mapping_colors = [call for call in fake.calls if call[:3] == ('data', 'mesh', 'color')][-1]
        np.testing.assert_array_equal(mapping_colors[3][:, 3], [64] * len(render_mesh.positions))

        viewer.set_mapping('allen')
        viewer.set_selected_region_ids([-315])
        color_calls = [call for call in fake.calls if call[:3] == ('data', 'mesh', 'color')]
        selected_colors = color_calls[-1]
        np.testing.assert_array_equal(selected_colors[3][:, 3], [64] * len(render_mesh.positions))


def test_private_render_omits_unused_extreme_vertex_without_changing_source_normalization(mesh):
    extreme = np.array([[1000.0, 250.0, -400.0]], dtype=np.float32)
    source = replace(
        mesh,
        positions_um=np.vstack((mesh.positions_um, extreme)),
        positions=np.vstack((mesh.positions, np.array([[80.0, 30.0, -50.0]], np.float32))),
        explode_offsets=np.vstack((mesh.explode_offsets, np.zeros((1, 3), np.float32))),
        normals=np.vstack((mesh.normals, np.array([[0.0, 0.0, 1.0]], np.float32))),
        component_ids=np.append(mesh.component_ids, mesh.component_ids[-1]),
        presentation_ids=np.append(mesh.presentation_ids, mesh.presentation_ids[-1]),
    )
    canonical_positions = source.positions_um.copy()
    canonical_indices = source.indices.copy()
    points = np.array([[1000.0, 250.0, -400.0], [0.0, 0.0, 0.0]], np.float32)
    centre = (source.positions_um.min(axis=0) + source.positions_um.max(axis=0)) / 2
    expected = np.ascontiguousarray((points - centre) * source.display_scale, dtype=np.float32)
    np.testing.assert_array_equal(source.normalize_points(points), expected)

    fake = FakeDatoviz()
    with AtlasViewer(source, datoviz=fake) as viewer:
        render = viewer._surface_geometry
        assert viewer.mesh_data is source
        assert len(source.positions_um) == len(mesh.positions_um) + 1
        assert len(render.mesh.positions_um) != len(source.positions_um)
        assert len(source.positions_um) - 1 not in render.source_vertex_indices
        assert render.fragment_clip.shape == (len(render.mesh.positions), 2)
        state_binding = next(call[1] for call in fake.calls if call[0] == 'state_binding')
        np.testing.assert_array_equal(state_binding, render.mesh.presentation_ids)
        assert len(state_binding) == len(render.fragment_clip)
        clip_upload = next(call[1] for call in fake.calls if call[0] == 'fragment_clip')
        np.testing.assert_array_equal(clip_upload, render.fragment_clip)
        viewer.set_probe(points)
        probe_upload = next(call for call in fake.calls if call[:2] == ('data_many', 'path'))
        np.testing.assert_array_equal(probe_upload[3]['position'], expected)
        np.testing.assert_array_equal(source.normalize_points(points), expected)
    np.testing.assert_array_equal(source.positions_um, canonical_positions)
    np.testing.assert_array_equal(source.indices, canonical_indices)


def test_hover_uses_gpu_state_without_changing_authored_colors(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        before = len(fake.calls)
        viewer._set_hovered_region_ids((315,))
        np.testing.assert_array_equal(
            viewer._surface_state.words, [fake.DVZ_ITEM_STATE_HOVERED] * len(mesh.presentations)
        )
        assert viewer.selected_region_ids() == ()
        assert viewer._highlight_region_ids == ()
        assert viewer._surface_state.handle.tint_mix == 0.28
        assert not any(call[:3] == ('data', 'mesh', 'color') for call in fake.calls[before:])
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids(())
        np.testing.assert_array_equal(
            viewer._surface_state.words, [fake.DVZ_ITEM_STATE_SELECTED] * len(mesh.presentations)
        )
        assert viewer.selected_region_ids() == (-315,)
        assert viewer._highlight_region_ids == (315,)


def test_selection_context_and_hover_have_independent_gpu_bits(mesh):
    presentations = tuple(
        {**p, 'mappings': {**p['mappings'], 'allen': -315 if p['presentation_id'] == 0 else 997}}
        for p in mesh.presentations
    )
    fake = FakeDatoviz()
    with AtlasViewer(
        replace(mesh, presentations=presentations), datoviz=fake, selection_context_opacity=0.18
    ) as viewer:
        before = len(fake.calls)
        viewer.set_selected_region_ids((-315,))
        np.testing.assert_array_equal(
            viewer._surface_state.words, [fake.DVZ_ITEM_STATE_SELECTED, 0]
        )
        assert viewer._surface_state.handle.active
        assert viewer._surface_state.handle.context_alpha == 0.18
        viewer._set_hovered_region_ids((997,))
        np.testing.assert_array_equal(
            viewer._surface_state.words,
            [fake.DVZ_ITEM_STATE_SELECTED, fake.DVZ_ITEM_STATE_HOVERED],
        )
        viewer.clear_selection()
        assert not viewer._surface_state.handle.active
        np.testing.assert_array_equal(
            viewer._surface_state.words, [0, fake.DVZ_ITEM_STATE_HOVERED]
        )
        assert not any(call[:3] == ('data', 'mesh', 'color') for call in fake.calls[before:])
        assert [c[2] for c in fake.calls if c[:2] == ('alpha_mode', 'mesh')] == [
            fake.DVZ_ALPHA_OPAQUE,
            fake.DVZ_ALPHA_WBOIT,
            fake.DVZ_ALPHA_OPAQUE,
        ]


def test_interaction_reuses_bank_and_vertex_indices_across_mapping(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        bank, indices = viewer._surface_state.handle, viewer._surface_state.indices
        before = len(fake.calls)
        viewer._set_hovered_region_ids((315,))
        viewer.set_selected_region_ids((-315,))
        viewer.set_mapping('beryl')
        assert viewer._surface_state.handle is bank
        assert viewer._surface_state.indices is indices
        assert indices.flags.owndata
        assert viewer._surface_state._mapping == 'beryl'
        assert not bank.active
        np.testing.assert_array_equal(bank.words, np.zeros(len(mesh.presentations), np.uint32))
        assert not any(c[0] in ('state_binding', 'item_state_buffer') for c in fake.calls[before:])


@pytest.mark.parametrize('mapping', ['allen', 'beryl', 'cosmos'])
def test_surface_state_slots_preserve_mapping_membership(mesh, mapping):
    with AtlasViewer(mesh, datoviz=FakeDatoviz(), mapping=mapping) as viewer:
        for selected in ((), (0,), (997,), (315, 997), (99999999,)):
            viewer._surface_state.update(selected, (), selection_active=bool(selected))
            expected = [
                2
                if p['mappings'][mapping] is not None
                and abs(int(p['mappings'][mapping])) in selected
                and int(p['mappings'][mapping]) != 0
                else 0
                for p in mesh.presentations
            ]
            np.testing.assert_array_equal(viewer._surface_state.words, expected)


def test_region_data_changes_authored_colors_without_rebinding_state(mesh):
    catalog = open_region_catalog(REGIONS)
    data = AtlasRegionValues.from_arrays([-997, -8], [1.0, 2.5])
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        initial_base, bank = viewer._surface_base_colors_cache, viewer._surface_state.handle
        viewer._set_hovered_region_ids((315,))
        viewer.set_region_data(data, value_range=(0, 5), mapping_reduction='weighted_mean')
        assert viewer._surface_base_colors_cache is not initial_base
        assert viewer._surface_state.handle is bank
        color_updates = [c for c in fake.calls if c[:3] == ('data', 'mesh', 'color')]
        np.testing.assert_array_equal(viewer._surface_base_colors_cache, color_updates[-1][3])


def test_region_data_uses_readable_neutral_context(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake, surface_opacity=0.08) as viewer:
        colors = viewer._region_surface_colors(
            'allen', np.empty(0, dtype=np.int64), np.empty((0, 4), dtype=np.uint8)
        )
        np.testing.assert_array_equal(colors[:, :3], [[100, 112, 130]] * len(colors))
        np.testing.assert_array_equal(colors[:, 3], [20] * len(colors))


def test_mesh_hover_reads_item_interaction_hover_identity(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        assert viewer._mesh_hovered_region_ids() == ()
        fake.mesh_hover = encode_region_key(-315)
        assert viewer._mesh_hovered_region_ids() == (-315,)


def test_probe_uses_same_display_transform(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_probe([[-2, 0, 0], [5, 0, 0]])
    probe_upload = [call for call in fake.calls if call[:2] == ('data_many', 'path')]
    assert len(probe_upload) == 1
    positions = probe_upload[0][3]['position']
    np.testing.assert_allclose(positions[:, 0], [-0.8, 0.8])


@pytest.mark.parametrize(
    ('points', 'kwargs', 'message'),
    [
        ([[0, 0, np.nan], [1, 1, 1]], {}, 'finite coordinates'),
        ([[0, 0, 0], [1, 1, 1]], {'width_px': 0}, 'finite and positive'),
        ([[0, 0, 0], [1, 1, 1]], {'width_px': np.nan}, 'finite and positive'),
        ([[0, 0, 0], [1, 1, 1]], {'width_px': np.inf}, 'finite and positive'),
        ([[0, 0, 0], [1, 1, 1]], {'color': (1, 2)}, '8-bit integer'),
        ([[0, 0, 0], [1, 1, 1]], {'color': (1.5, 2, 3)}, '8-bit integer'),
        ([[0, 0, 0], [1, 1, 1]], {'color': (1, 2, 256)}, '8-bit integer'),
        ([[0, 0, 0], [1, 1, 1]], {'color': (True, False, True)}, '8-bit integer'),
    ],
)
def test_probe_rejects_invalid_upload_inputs_before_allocation(mesh, points, kwargs, message):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer, pytest.raises(ValueError, match=message):
        viewer.set_probe(points, **kwargs)
    assert not any(call[0] == 'path' for call in fake.calls)


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

    second_fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=second_fake) as viewer:
        with pytest.raises(ValueError, match='values or colors'):
            viewer.set_probe_sites([[0, 0, 0]], values=[1], colors=[[1, 2, 3]])
        with pytest.raises(ValueError, match='probe colors'):
            viewer.set_probe_sites([[0, 0, 0]], colors=[[300, 2, 3]])
        with pytest.raises(ValueError, match='value range'):
            viewer.set_probe_sites([[0, 0, 0]], values=[1], value_range=(1, 1))
        with pytest.raises(ValueError, match='color scheme'):
            viewer.set_probe_sites([[0, 0, 0]], values=[1], color_scheme='unknown')

        viewer.set_probe_sites(
            [[0, 0, 0], [1, 0, 0]],
            values=[0, 1],
            value_range=(0, 1),
            color_scheme='sequential',
        )
        sequential = [call for call in second_fake.calls if call[:2] == ('data_many', 'sphere')][
            -1
        ][3]
        np.testing.assert_array_equal(sequential['color'][0], [88, 70, 180, 255])
        np.testing.assert_array_equal(sequential['color'][1], [253, 231, 73, 255])


@pytest.mark.parametrize(
    ('points', 'kwargs', 'message'),
    [
        ([[np.inf, 0, 0]], {}, 'finite coordinates'),
        ([[0, 0, 0]], {'radius_um': 0}, 'finite and positive'),
        ([[0, 0, 0]], {'radius_um': np.nan}, 'finite and positive'),
        ([[0, 0, 0]], {'radius_um': np.inf}, 'finite and positive'),
        ([[0, 0, 0]], {'values': [np.inf]}, 'no infinities'),
        ([[0, 0, 0]], {'values': [-np.inf]}, 'no infinities'),
        ([[0, 0, 0]], {'values': [1], 'value_range': (0,)}, 'exactly two'),
        ([[0, 0, 0]], {'colors': [[1.5, 2, 3]]}, 'probe colors'),
        ([[0, 0, 0]], {'colors': [[True, False, True]]}, 'probe colors'),
    ],
)
def test_probe_sites_reject_invalid_upload_inputs_before_allocation(mesh, points, kwargs, message):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer, pytest.raises(ValueError, match=message):
        viewer.set_probe_sites(points, **kwargs)
    assert not any(call[0] == 'sphere' for call in fake.calls)


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
        np.testing.assert_array_equal(item_keys.view(np.int64), [0, 0, 0])

    with (
        AtlasViewer(mesh, datoviz=FakeDatoviz()) as viewer,
        pytest.raises(ValueError, match='region catalog'),
    ):
        viewer.set_probe_data(data)

    unknown = ProbeSites.from_arrays([[0, 0, 0]], [1], [123456789])
    with (
        AtlasViewer(mesh, catalog=catalog, datoviz=FakeDatoviz()) as viewer,
        pytest.raises(ValueError, match='unknown signed Allen'),
    ):
        viewer.set_probe_data(unknown)


def test_region_values_color_surface_and_follow_mapping(mesh):
    catalog = open_region_catalog(REGIONS)
    data = AtlasRegionValues.from_arrays(
        [-997, -8],
        [1.0, 2.5],
        weights=[1, 3],
        value_name='Mean FR (Hz)',
        weight_name='Sites',
    )
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        viewer.set_selected_region_ids([-8])
        viewer.set_region_data(data, value_range=(0, 5), mapping_reduction='weighted_mean')
        assert viewer.selected_region_ids() == (-8,)
        assert viewer._highlight_region_ids == (8,)
        assert [call for call in fake.calls if call[:3] == ('data', 'mesh', 'color')]

        viewer._replace_region_tree()
        viewer._replace_region_table()
        row_call = [call for call in fake.calls if call[0] == 'table_rows'][-1]
        np.testing.assert_array_equal(row_call[1].view(np.int64), [-997, -8])
        fake.table_selection = [encode_region_key(-8)]
        viewer._sync_selection_highlight(region_table_changed=True)
        assert viewer.selected_region_ids() == (-8,)

        viewer.set_mapping('beryl')
        row_call = [call for call in fake.calls if call[0] == 'table_rows'][-1]
        np.testing.assert_array_equal(row_call[1].view(np.int64), [997])

    with (
        AtlasViewer(mesh, datoviz=FakeDatoviz()) as viewer,
        pytest.raises(ValueError, match='region catalog'),
    ):
        viewer.set_region_data(data, mapping_reduction='weighted_mean')

    fake = FakeDatoviz()
    unknown = AtlasRegionValues.from_arrays([123456], [1])
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        with pytest.raises(ValueError, match='unknown signed Allen'):
            viewer.set_region_data(unknown, mapping_reduction='weighted_mean')
        assert viewer.region_data is None
        with pytest.raises(ValueError, match='region opacity'):
            viewer.set_region_data(
                data,
                opacity=1.1,
                mapping_reduction='weighted_mean',
            )
        assert viewer.region_data is None
        with pytest.raises(ValueError, match='value range'):
            viewer.set_region_data(
                data,
                value_range=(1, 1),
                mapping_reduction='weighted_mean',
            )
        assert viewer.region_data is None


def test_mapping_change_clears_all_linked_selection_state(mesh):
    catalog = open_region_catalog(REGIONS)
    sites = ProbeSites.from_arrays(
        [[-1, 0, 0], [1, 0, 0]],
        [1, 2],
        [-8, 8],
        site_ids=[11, 12],
    )
    regions = AtlasRegionValues.from_arrays([-997, -8], [1, 2], weights=[1, 1])
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        viewer.set_probe_data(sites)
        viewer.set_region_data(regions, mapping_reduction='weighted_mean')
        viewer._replace_region_tree()
        viewer._replace_probe_table()
        viewer._replace_region_table()
        viewer.set_selected_region_ids([-8])

        viewer.set_mapping('beryl')

        assert viewer.selected_region_ids() == ()
        assert viewer._highlight_region_ids == ()
        assert fake.tree_selection == []
        assert fake.table_selection == []
        item_keys = [call for call in fake.calls if call[0] == 'item_link_keys'][-1][1]
        np.testing.assert_array_equal(item_keys.view(np.int64), [0, 0])
        region_rows = [call for call in fake.calls if call[0] == 'table_rows'][-1][1]
        np.testing.assert_array_equal(region_rows.view(np.int64), [997])


def test_replacing_payloads_rebuilds_tables_without_changing_atlas_selection(mesh):
    catalog = open_region_catalog(REGIONS)
    first_sites = ProbeSites.from_arrays([[0, 0, 0]], [1], [-8], site_ids=[11])
    next_sites = ProbeSites.from_arrays([[1, 0, 0]], [2], [8], site_ids=[21])
    first_regions = AtlasRegionValues.from_arrays([-8], [1])
    next_regions = AtlasRegionValues.from_arrays([-997], [2])
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        viewer.gui = SimpleNamespace(name='gui')
        viewer.set_probe_data(first_sites)
        viewer.set_region_data(first_regions, mapping_reduction='weighted_mean')
        viewer.set_selected_region_ids([-8])
        destroy_count = sum(call[0] == 'table_destroy' for call in fake.calls)

        viewer.set_probe_data(next_sites)
        viewer.set_region_data(next_regions, mapping_reduction='weighted_mean')

        assert viewer.selected_region_ids() == (-8,)
        assert sum(call[0] == 'table_destroy' for call in fake.calls) == destroy_count + 2
        probe_rows = [call for call in fake.calls if call[0] == 'table_rows'][-2][1]
        region_rows = [call for call in fake.calls if call[0] == 'table_rows'][-1][1]
        np.testing.assert_array_equal(probe_rows, [21])
        np.testing.assert_array_equal(region_rows.view(np.int64), [-997])
        assert fake.table_selection == []


def test_region_recolor_uses_presentation_lookup_not_per_region_vertex_masks(mesh, monkeypatch):
    catalog = open_region_catalog(REGIONS)
    data = AtlasRegionValues.from_arrays([-997, -8], [1, 2])
    fake = FakeDatoviz()
    with AtlasViewer(mesh, catalog=catalog, datoviz=fake) as viewer:
        monkeypatch.setattr(
            type(mesh),
            'mapping_ids',
            lambda *_args: pytest.fail('regional recolor scanned vertex mapping IDs'),
        )
        viewer.set_region_data(data, mapping_reduction='weighted_mean')


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
    np.testing.assert_array_equal(model.subtree_row_indices('grey'), [1])
    with pytest.raises(ValueError, match='expected one'):
        model.subtree_row_indices('missing')
    assert model.expanded_logical_ids((-997,)) == (8, 997)
    assert model.describe(8) == 'grey — Basic cell groups and regions'
    for region_id in model.region_ids:
        assert decode_region_key(encode_region_key(int(region_id))) == region_id


def test_region_expansion_preserves_nonmember_parents_unknown_ids_and_hemispheres():
    model = AtlasTreeModel.from_catalog(open_region_catalog(REGIONS), 'allen')
    model = replace(model, mapping_members=np.array([False, True]))
    assert model.expanded_logical_ids(()) == ()
    assert model.expanded_logical_ids((-997,)) == (8, 997)
    assert model.expanded_logical_ids((997, -997, 8, 0, 12345)) == (8, 997, 12345)
    assert model.expanded_logical_ids((-8,)) == (8,)
    replacement = replace(model, mapping_members=np.array([True, False]))
    assert replacement.expanded_logical_ids((997,)) == (997,)
    assert replacement.expanded_logical_ids((-8,)) == (8,)


def test_viewer_uploads_catalog_to_one_retained_tree_batch(mesh):
    fake = FakeDatoviz()
    catalog = open_region_catalog(REGIONS)
    with AtlasViewer(mesh, datoviz=fake, catalog=catalog) as viewer:
        viewer._replace_region_tree()
        row_call = next(call for call in fake.calls if call[0] == 'tree_rows')
        assert row_call[3:] == (
            ('grey',),
            ('Basic cell groups and regions',),
            fake.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
        )
        np.testing.assert_array_equal(row_call[2], [2**32 - 1])
        assert ('alpha_mode', 'mesh', fake.DVZ_ALPHA_OPAQUE) in fake.calls
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

        fake.mesh_selection = [encode_region_key(-8)]
        viewer._sync_selection_highlight()

        assert viewer.selected_region_ids() == (-8,)
        assert fake.tree_selection == [encode_region_key(-8)]

        fake.mesh_selection = []
        viewer._sync_selection_highlight()

        assert viewer.selected_region_ids() == ()
        assert fake.tree_selection == []


def test_programmatic_selection_highlights_descendants(mesh):
    fake = FakeDatoviz()
    catalog = open_region_catalog(REGIONS)
    with AtlasViewer(mesh, datoviz=fake, catalog=catalog) as viewer:
        viewer._replace_region_tree()
        viewer.set_selected_region_ids([-8])

        assert viewer.selected_region_ids() == (-8,)
        assert viewer._highlight_region_ids == (8,)
        assert fake.tree_selection == [encode_region_key(-8)]

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


def test_hover_can_be_disabled_without_disabling_click_selection(mesh):
    fake = FakeDatoviz()
    descriptor = None
    original = fake.dvz_item_interaction

    def interaction(panel, desc):
        nonlocal descriptor
        descriptor = desc._obj
        return original(panel, desc)

    fake.dvz_item_interaction = interaction
    with AtlasViewer(mesh, datoviz=fake, enable_hover=False) as viewer:
        assert descriptor.hover_enabled is False
        assert descriptor.selection_enabled is True
        fake.mesh_hover = encode_region_key(-315)
        assert viewer._mesh_hovered_region_ids() == ()
        assert not viewer._set_hovered_region_ids((-315,))
        assert viewer._hovered_region_ids == ()
        fake.mesh_selection = [encode_region_key(-315)]
        assert viewer._mesh_selected_region_ids() == (-315,)


def test_interaction_never_rebuilds_vertex_membership_or_reuploads_base_colors(mesh, monkeypatch):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:

        def unexpected_scan(*_args, **_kwargs):
            pytest.fail('interaction expanded region membership across mesh vertices')

        monkeypatch.setattr(AtlasMesh, 'mapping_ids', unexpected_scan)
        before = len(fake.calls)
        viewer._set_hovered_region_ids((315,))
        viewer.set_selected_region_ids((-315,))
        viewer._set_hovered_region_ids(())
        calls = fake.calls[before:]
        assert any(c[0] == 'state_update' for c in calls)
        assert not any(c[0] in ('data', 'data_many', 'indices', 'state_binding') for c in calls)
        assert viewer._surface_state.handle.active
