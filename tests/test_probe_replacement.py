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
            fake.dvz_visual_set_data_many = lambda *_args: -1
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
