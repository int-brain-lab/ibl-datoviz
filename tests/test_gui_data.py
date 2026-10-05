import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasRegionValues, AtlasTreeModel, AtlasViewer, ProbeSites
from ibl_datoviz.gui_data import create_probe_table, create_region_table, create_region_tree
from tests.test_atlas import FIXTURE, REGIONS, FakeDatoviz


def create_widget(kind, fake):
    if kind == 'tree':
        model = AtlasTreeModel.from_catalog(open_region_catalog(REGIONS), 'allen')
        return create_region_tree(fake, model, 'grey', b'')
    if kind == 'probe':
        data = ProbeSites.from_arrays([[1, 2, 3]], [4], [-8], site_ids=[11])
        return create_probe_table(fake, data, np.array([-8]), ('region',), np.zeros((1, 4)))
    data = AtlasRegionValues.from_arrays([-8], [4])
    return create_region_table(
        fake, data, data.allen_region_ids, data.values, data.weights, ('region',), np.zeros((1, 4))
    )


@pytest.mark.parametrize('kind', ['tree', 'probe', 'region'])
def test_widget_owns_handle_and_rows_and_closes_once(kind):
    fake = FakeDatoviz()
    owner = create_widget(kind, fake)
    native_kind = 'tree' if kind == 'tree' else 'table'
    assert owner.handle is not None
    assert owner.rows.keys.dtype == np.uint64
    assert owner.rows.region_ids.dtype == np.int64
    owner.close()
    owner.close()
    assert owner.handle is None
    assert sum(call[0] == f'{native_kind}_destroy' for call in fake.calls) == 1


@pytest.mark.parametrize('kind', ['tree', 'probe', 'region'])
def test_widget_constructor_failure_has_no_handle_to_destroy(kind):
    native_kind = 'tree' if kind == 'tree' else 'table'
    fake = FakeDatoviz()
    setattr(fake, f'dvz_gui_{native_kind}', lambda *_args: None)
    with pytest.raises(RuntimeError, match=f'dvz_gui_{native_kind}'):
        create_widget(kind, fake)
    assert not any(call[0] == f'{native_kind}_destroy' for call in fake.calls)


@pytest.mark.parametrize(
    ('kind', 'setter'),
    [
        ('tree', 'dvz_gui_tree_set_rows'),
        ('tree', 'dvz_gui_tree_set_swatches'),
        ('tree', 'dvz_gui_tree_expand_to_depth'),
        ('probe', 'dvz_gui_table_set_rows'),
        ('probe', 'dvz_gui_table_set_column_text'),
        ('probe', 'dvz_gui_table_set_column_double'),
        ('probe', 'dvz_gui_table_set_column_color'),
        ('region', 'dvz_gui_table_set_rows'),
        ('region', 'dvz_gui_table_set_column_double'),
    ],
)
def test_widget_upload_failure_destroys_new_handle(kind, setter, monkeypatch):
    fake = FakeDatoviz()
    monkeypatch.setattr(fake, setter, lambda *_args: -1)
    with pytest.raises(RuntimeError, match='Datoviz .* failed'):
        create_widget(kind, fake)
    native_kind = 'tree' if kind == 'tree' else 'table'
    assert sum(call[0] == f'{native_kind}_destroy' for call in fake.calls) == 1


def test_viewer_failed_replacement_and_repeated_close_do_not_double_destroy(monkeypatch):
    mesh = AtlasMesh.from_pack(FIXTURE)
    fake = FakeDatoviz()
    viewer = AtlasViewer(mesh, catalog=open_region_catalog(REGIONS), datoviz=fake)
    viewer._replace_region_tree()
    monkeypatch.setattr(fake, 'dvz_gui_tree_set_rows', lambda *_args: -1)
    with pytest.raises(RuntimeError, match='atlas ontology rows'):
        viewer._replace_region_tree()
    assert viewer.region_tree is None
    assert 'region_tree' not in viewer._gui_widgets
    viewer.close()
    viewer.close()
    assert sum(call[0] == 'tree_destroy' for call in fake.calls) == 2
