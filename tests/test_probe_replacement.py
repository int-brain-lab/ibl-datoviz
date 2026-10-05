import ctypes

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, ProbeSites
from tests.test_atlas import FIXTURE, REGIONS, FakeDatoviz


@pytest.fixture
def mesh():
    return AtlasMesh.from_pack(FIXTURE)


@pytest.mark.parametrize('count', [1, 2])
def test_raw_replacement_clears_typed_links_and_table(mesh, count):
    fake = FakeDatoviz()
    data = ProbeSites.from_arrays([[0, 0, 0], [1, 0, 0]], [1, 2], [-8, 8], site_ids=[11, 12])
    with AtlasViewer(mesh, catalog=open_region_catalog(REGIONS), datoviz=fake) as viewer:
        viewer.gui = object()
        viewer.set_probe_data(data)
        viewer.set_selected_region_ids([-8])
        old_table = viewer.probe_table
        assert old_table is not None
        viewer.set_probe_sites([[0, 0, 0]] * count)
        assert viewer.probe_data is None
        assert viewer._probe_colors is None
        assert viewer.probe_table is None
        assert viewer._probe_table_selected_region_ids() == ()
        keys = [call[1] for call in fake.calls if call[0] == 'item_link_keys'][-1]
        np.testing.assert_array_equal(keys, np.zeros(count, dtype=np.uint64))
        link_count = sum(call[0] == 'item_link_keys' for call in fake.calls)
        viewer.set_mapping('beryl')
        assert sum(call[0] == 'item_link_keys' for call in fake.calls) == link_count
        viewer.set_mapping('allen')
        viewer.set_probe_data(data)
        assert viewer.probe_data is data
        assert viewer.probe_table is not None
        fake.table_selection = [12]
        viewer._sync_selection_highlight(table_changed=True)
        assert viewer.selected_region_ids() == (8,)


def test_rejected_replacement_preserves_typed_state(mesh):
    fake = FakeDatoviz()
    data = ProbeSites.from_arrays([[0, 0, 0]], [1], [-8])
    with AtlasViewer(mesh, catalog=open_region_catalog(REGIONS), datoviz=fake) as viewer:
        viewer.gui = object()
        viewer.set_probe_data(data)
        table, colors = viewer.probe_table, viewer._probe_colors
        with pytest.raises(ValueError, match='radius'):
            viewer.set_probe_sites([[0, 0, 0]], radius_um=-1)
        assert viewer.probe_data is data
        assert viewer.probe_table is table
        assert viewer._probe_colors is colors
        with pytest.raises(RuntimeError, match='upload'):
            original = fake.dvz_visual_set_data_many
            failed = False

            def fail_once(*args):
                nonlocal failed
                if not failed:
                    failed = True
                    return -1
                return original(*args)

            fake.dvz_visual_set_data_many = fail_once
            viewer.set_probe_sites([[0, 0, 0]])
        assert viewer.probe_data is data
        assert viewer.probe_table is table


@pytest.mark.parametrize('failure', ['path', 'caps', 'join', 'sphere', 'links'])
def test_probe_native_failures_reported(mesh, failure):
    fake = FakeDatoviz(fail_on=failure)
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        if failure in ('caps', 'join'):
            setattr(fake, f'dvz_path_set_{failure}', lambda *_args: -1)
        if failure == 'links':
            fake.dvz_visual_set_link_keys = lambda *_args: -1
        with pytest.raises(RuntimeError):
            if failure in ('path', 'caps', 'join'):
                viewer.set_probe([[0, 0, 0], [1, 0, 0]])
            else:
                viewer.set_probe_sites([[0, 0, 0]])
        assert viewer.probe_data is None


class StatefulProbeDatoviz(FakeDatoviz):
    def __init__(self):
        super().__init__()
        self.attributes = None
        self.keys = None
        self.fail_next = None

    def dvz_visual_set_data_many(self, visual, updates):
        if visual.name == 'sphere':
            self.attributes = {name: array.copy() for name, array in updates.items()}
            if self.fail_next == 'geometry':
                self.fail_next = None
                return -1
        return super().dvz_visual_set_data_many(visual, updates)

    def dvz_visual_set_link_keys(self, visual, channel, keys):
        self.keys = keys.copy()
        if self.fail_next == 'keys':
            self.fail_next = None
            return -1
        return super().dvz_visual_set_link_keys(visual, channel, keys)


@pytest.mark.parametrize('prior_typed', [False, True])
@pytest.mark.parametrize('failure', ['geometry', 'keys'])
def test_probe_sites_failed_setter_restores_owned_upload_and_retries(mesh, prior_typed, failure):
    fake = StatefulProbeDatoviz()
    data = ProbeSites.from_arrays([[0, 0, 0], [1, 0, 0]], [1, 2], [-8, 8])
    with AtlasViewer(mesh, catalog=open_region_catalog(REGIONS), datoviz=fake) as viewer:
        viewer.gui = object()
        if prior_typed:
            viewer.set_probe_data(data)
            viewer.set_mapping('beryl')
        else:
            colors = np.array([[1, 2, 3, 255], [4, 5, 6, 255]], dtype=np.uint8)
            viewer.set_probe_sites(data.positions_um, colors=colors)
            colors[:] = 99
        previous = viewer._probe_upload
        handle, table, payload = viewer.probe_sites, viewer.probe_table, viewer.probe_data
        fake.fail_next = failure
        with pytest.raises(RuntimeError, match='probe site'):
            if prior_typed:
                viewer.set_probe_sites([[4, 5, 6]])
            else:
                viewer.set_probe_data(data)
        assert viewer.probe_sites is handle
        assert viewer.probe_table is table
        assert viewer.probe_data is payload
        assert viewer._probe_upload is previous
        for name, array in previous.attributes().items():
            np.testing.assert_array_equal(fake.attributes[name], array)
            assert not array.flags.writeable
        np.testing.assert_array_equal(fake.keys, previous.keys)
        if prior_typed:
            viewer.set_probe_sites([[4, 5, 6]])
            assert viewer.probe_data is None
            assert viewer.probe_table is None
            assert len(fake.keys) == 1
        else:
            viewer.set_probe_data(data)
            assert viewer.probe_data is data
            assert viewer.probe_table is not None
        assert viewer.probe_sites is handle


def test_probe_sites_rollback_failure_closes_viewer(mesh):
    fake = FakeDatoviz()
    viewer = AtlasViewer(mesh, datoviz=fake)
    viewer.set_probe_sites([[0, 0, 0]])
    fake.dvz_visual_set_data_many = lambda *_args: -1
    with pytest.raises(RuntimeError, match='rollback failed; viewer closed'):
        viewer.set_probe_sites([[1, 0, 0]])
    assert viewer._closed
    viewer.close()
    assert sum(call[0] == 'destroy_scene' for call in fake.calls) == 1


@pytest.mark.parametrize('kind', ['path', 'sphere'])
def test_null_native_probe_constructor_is_retryable(mesh, kind, monkeypatch):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        constructor = getattr(fake, f'dvz_{kind}')
        monkeypatch.setattr(fake, f'dvz_{kind}', lambda *_args: ctypes.POINTER(ctypes.c_int)())
        points = [[0, 0, 0], [1, 0, 0]]
        setter = viewer.set_probe if kind == 'path' else viewer.set_probe_sites
        with pytest.raises(RuntimeError, match=f'dvz_{kind}'):
            setter(points)
        assert getattr(viewer, 'probe' if kind == 'path' else 'probe_sites') is None
        monkeypatch.setattr(fake, f'dvz_{kind}', constructor)
        setter(points)
        assert getattr(viewer, 'probe' if kind == 'path' else 'probe_sites') is not None


@pytest.mark.parametrize('kind', ['path', 'sphere'])
def test_probe_attachment_failure_reuses_pending_scene_owned_visual(mesh, kind, monkeypatch):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        original = fake.dvz_panel_add_visual
        monkeypatch.setattr(fake, 'dvz_panel_add_visual', lambda *_args: -1)
        points = [[0, 0, 0], [1, 0, 0]]
        setter = viewer.set_probe if kind == 'path' else viewer.set_probe_sites
        with pytest.raises(RuntimeError, match='attach'):
            setter(points)
        alias = 'probe' if kind == 'path' else 'probe_sites'
        pending = '_probe_pending' if kind == 'path' else '_probe_sites_pending'
        handle = getattr(viewer, pending)
        assert handle is not None
        assert getattr(viewer, alias) is None
        monkeypatch.setattr(fake, f'dvz_{kind}', lambda *_args: pytest.fail('allocated again'))
        monkeypatch.setattr(fake, 'dvz_panel_add_visual', original)
        setter(points)
        assert getattr(viewer, alias) is handle
        assert getattr(viewer, pending) is None


@pytest.mark.parametrize('failure', ['geometry', 'keys'])
def test_first_sites_upload_failure_reuses_unattached_candidate(mesh, failure, monkeypatch):
    fake = StatefulProbeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        fake.fail_next = failure
        with pytest.raises(RuntimeError, match='probe site'):
            viewer.set_probe_sites([[0, 0, 0]])
        pending = viewer._probe_sites_pending
        assert pending is not None
        assert viewer.probe_sites is None
        assert viewer._probe_upload is None
        monkeypatch.setattr(fake, 'dvz_sphere', lambda *_args: pytest.fail('allocated again'))
        viewer.set_probe_sites([[1, 0, 0], [2, 0, 0]])
        assert viewer.probe_sites is pending
        assert viewer._probe_sites_pending is None
        assert len(fake.keys) == 2


@pytest.mark.parametrize('setter', ['dvz_path_set_caps', 'dvz_path_set_join'])
def test_path_setup_failure_reuses_unattached_candidate(mesh, setter, monkeypatch):
    fake = FakeDatoviz()
    with AtlasViewer(mesh, datoviz=fake) as viewer:
        original = getattr(fake, setter)
        monkeypatch.setattr(fake, setter, lambda *_args: -1)
        with pytest.raises(RuntimeError, match='probe'):
            viewer.set_probe([[0, 0, 0], [1, 0, 0]])
        pending = viewer._probe_pending
        assert pending is not None
        assert viewer.probe is None
        monkeypatch.setattr(fake, 'dvz_path', lambda *_args: pytest.fail('allocated again'))
        monkeypatch.setattr(fake, setter, original)
        viewer.set_probe([[0, 0, 0], [1, 0, 0]])
        assert viewer.probe is pending
        assert viewer._probe_pending is None
