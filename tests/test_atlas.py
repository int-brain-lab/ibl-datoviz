from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / 'ibl-atlas-assets'
    / 'tests'
    / 'fixtures'
    / 'mesh-pack-v1'
    / 'pack'
)


class FakeDatoviz:
    DVZ_QUERY_CAPABILITY_ITEM = 2
    DVZ_SEGMENT_CAP_ROUND = 1
    DVZ_PATH_JOIN_ROUND = 1

    def __init__(self):
        self.calls = []

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

    def dvz_link_channel(self, *_args):
        return self._handle('link_channel')

    def dvz_visual_set_link_keys(self, _visual, _channel, keys):
        self.calls.append(('link_keys', np.array(keys, copy=True)))
        return 0

    def dvz_panel_add_visual(self, *_args):
        return 0

    def dvz_item_interaction(self, *_args):
        return self._handle('interaction')

    def dvz_item_interaction_selection(self, *_args):
        return self._handle('selection')

    @staticmethod
    def dvz_selection_count(_selection):
        return 0

    def dvz_selection_clear(self, *_args):
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


def test_probe_uses_same_display_transform(mesh):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        viewer.set_probe([[-2, 0, 0], [5, 0, 0]])
    probe_upload = [call for call in fake.calls if call[:2] == ('data_many', 'path')]
    assert len(probe_upload) == 1
    positions = probe_upload[0][3]['position']
    np.testing.assert_allclose(positions[:, 0], [-0.8, 0.8])
