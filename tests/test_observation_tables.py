"""Exact table identities, transactional native feedback and independent ownership."""

from types import SimpleNamespace

import datoviz as dvz
import numpy as np
import pytest

from ibl_datoviz.layer_gui import draw_scalar_legend, draw_source_details
from ibl_datoviz.layers import LayerObservationRef, ScalarEncoding
from ibl_datoviz.observation_tables import ObservationTables
from ibl_datoviz.payloads import Paths, Points, SourceKey, SourceObservationKey, WorldFrame
from tests.test_atlas import FakeDatoviz


class TableDatoviz(FakeDatoviz):
    def dvz_gui_checkbox(self, *_args):
        return False

    def dvz_gui_table(self, name, columns, flags):
        super().dvz_gui_table(name, columns, flags)
        return SimpleNamespace(selection=[], columns=columns)

    def dvz_gui_table_set_selection(self, table, keys):
        table.selection = list(map(int, keys))
        return 0

    def dvz_gui_table_get_selection(self, table):
        return table.selection

    def dvz_gui_table_draw(self, _gui, table):
        return 0, [SimpleNamespace(type=self.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED)], 0


class Selection:
    def __init__(self):
        self.observations = ()
        self.tables = None
        self.calls = []
        self.fail = False

    def _check_mutation(self):
        pass

    def set_observations(self, refs):
        if self.fail:
            raise RuntimeError('highlight failed')
        self.tables._set_selection(refs)
        self.observations = tuple(refs)
        self.calls.append(tuple(refs))


@pytest.fixture
def context():
    viewer = SimpleNamespace(dvz=TableDatoviz(), layers=[], selection=Selection(), closed=False)
    viewer.close = lambda: setattr(viewer, 'closed', True)
    tables = ObservationTables(viewer)
    viewer.selection.tables = tables
    yield viewer, tables
    tables._close()


def layer(viewer, *, paths=False, source=False):
    frame = WorldFrame('test')
    ids = (0, 'not-positioned', 36)
    keys = None
    if source:
        namespace = SourceKey('IBL', 'BWM', '1', 'a' * 64)
        keys = tuple(SourceObservationKey(namespace, 'pid', 'clusters', value) for value in ids)
    common = dict(
        ids=ids,
        frame=frame,
        provenance={'position_meaning': 'assigned channel'},
        observation_keys=keys,
    )
    if paths:
        payload = Paths(
            positions_um=(
                [[0, 0, 0], [1, 2, 3]],
                [[np.nan, 0, 0], [1, 2, 3]],
                [[2, 3, 4], [3, 4, 5]],
            ),
            **common,
        )
    else:
        payload = Points(positions_um=[[0, 0, 0], [np.nan, 0, 0], [0, 0, 0]], **common)
    attachment = f'attachment-{len(viewer.layers)}'
    refs = tuple(
        LayerObservationRef(attachment, value, None if keys is None else keys[i])
        for i, value in enumerate(ids)
    )
    result = SimpleNamespace(
        payload=payload,
        refs=refs,
        name='Layer',
        _closed=False,
        visible=False,
        scalar_encoding=None,
        scalar_data=None,
        capabilities=SimpleNamespace(width_px=paths),
    )
    viewer.layers.append(result)
    return result


def test_all_rows_original_zero_strings_and_repeated_coordinates_survive(context):
    viewer, tables = context
    first = layer(viewer, source=True)
    viewer.selection.observations = (first.refs[1],)
    table = tables.show(first)
    assert tables.show(first) is table
    assert len(tables.tables) == 1
    assert table.refs == first.refs
    assert table.keys.tolist() == [1, 2, 3]
    assert table.keys.dtype == np.uint64 and not table.keys.flags.writeable
    assert table.selected_refs() == (first.refs[1],)
    columns = {column['title'] for column in table.widget.handle.columns}
    assert {'ID', 'Value', 'Status', 'Location'} <= columns
    assert 'Content SHA256' not in columns
    assert any(
        call[0] == 'table_text' and call[2] == ('0', "'not-positioned'", '36')
        for call in viewer.dvz.calls
    )
    numeric = [call[2] for call in viewer.dvz.calls if call[0] == 'table_double']
    assert np.isnan(numeric[0][1])


def test_paths_expose_path_identity_and_vertices_without_fabricated_position(context):
    viewer, tables = context
    table = tables.show(layer(viewer, paths=True))
    columns = {column['title'] for column in table.widget.handle.columns}
    assert 'Vertices' in columns
    assert not {'ML (µm)', 'AP (µm)', 'DV (µm)'} & columns
    assert len(table.refs) == 3


def test_gui_selection_preserves_other_attachment_and_unopened_layer_selection(context):
    viewer, tables = context
    first, other, unopened = layer(viewer), layer(viewer), layer(viewer)
    table = tables.show(first)
    tables.show(other)
    viewer.selection.set_observations((first.refs[0], other.refs[0], unopened.refs[1]))
    table.widget.handle.selection = [3, 2]
    tables._draw_table(None, table)
    assert viewer.selection.observations == (
        other.refs[0],
        unopened.refs[1],
        first.refs[2],
        first.refs[1],
    )
    assert table.selected_refs() == (first.refs[1], first.refs[2])


def test_gui_unknown_key_rejected_and_native_pre_mutation_rolled_back(context):
    viewer, tables = context
    first = layer(viewer)
    table = tables.show(first)
    viewer.selection.set_observations((first.refs[0],))
    table.widget.handle.selection = [999]
    with pytest.raises(ValueError, match='unknown row key'):
        tables._draw_table(None, table)
    assert table.widget.handle.selection == [1]
    assert viewer.selection.observations == (first.refs[0],)


def test_gui_highlight_failure_restores_native_pre_mutation(context):
    viewer, tables = context
    first = layer(viewer)
    table = tables.show(first)
    viewer.selection.set_observations((first.refs[0],))
    viewer.selection.fail = True
    table.widget.handle.selection = [2]
    with pytest.raises(RuntimeError, match='highlight failed'):
        tables._draw_table(None, table)
    assert table.widget.handle.selection == [1]
    assert viewer.selection.observations == (first.refs[0],)


def test_partial_multi_table_upload_restores_all_from_authoritative_state(context, monkeypatch):
    viewer, tables = context
    first, second = layer(viewer), layer(viewer)
    one, two = tables.show(first), tables.show(second)
    viewer.selection.set_observations((first.refs[0], second.refs[1]))
    original = viewer.dvz.dvz_gui_table_set_selection
    failed = False

    def fail_once(table, keys):
        nonlocal failed
        original(table, keys)
        if table is two.widget.handle and not failed:
            failed = True
            return -1
        return 0

    monkeypatch.setattr(viewer.dvz, 'dvz_gui_table_set_selection', fail_once)
    with pytest.raises(RuntimeError, match='selection failed'):
        tables._set_selection((first.refs[2],))
    assert one.widget.handle.selection == [1]
    assert two.widget.handle.selection == [2]
    assert not viewer.closed


def test_rollback_failure_closes_viewer(context, monkeypatch):
    viewer, tables = context
    tables.show(layer(viewer))
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_table_set_selection', lambda *_args: -1)
    with pytest.raises(RuntimeError, match='rollback failed; viewer closed'):
        tables._set_selection(())
    assert viewer.closed


@pytest.mark.parametrize(
    'setter',
    [
        'dvz_gui_table_set_rows',
        'dvz_gui_table_set_column_text',
        'dvz_gui_table_set_column_double',
        'dvz_gui_table_set_selection',
    ],
)
def test_failed_creation_releases_handle_and_publishes_no_table(context, monkeypatch, setter):
    viewer, tables = context
    first = layer(viewer)
    monkeypatch.setattr(viewer.dvz, setter, lambda *_args: -1)
    with pytest.raises(RuntimeError):
        tables.show(first)
    assert not tables.tables
    assert sum(call[0] == 'table_destroy' for call in viewer.dvz.calls) == 1


def test_removed_and_foreign_layers_rejected_and_close_is_idempotent(context):
    viewer, tables = context
    first, second = layer(viewer), layer(viewer)
    one, two = tables.show(first), tables.show(second)
    tables._remove(first.refs)
    assert one.widget.handle is None and two.widget.handle is not None
    viewer.layers.remove(first)
    with pytest.raises(ValueError, match='foreign'):
        tables.show(first)
    tables._close()
    tables._close()
    assert not tables.tables
    assert sum(call[0] == 'table_destroy' for call in viewer.dvz.calls) == 2


def test_native_widget_keeps_full_rows_and_exact_string_selection(native_datoviz):
    viewer = SimpleNamespace(dvz=dvz, layers=[], selection=Selection())
    tables = ObservationTables(viewer)
    first = layer(viewer)
    try:
        table = tables.show(first)
        tables._set_selection((first.refs[1], first.refs[0]))
        assert set(table.selected_refs()) == {first.refs[1], first.refs[0]}
        assert len(table.keys) == 3
    finally:
        tables._close()


def test_id_type_and_repr_keep_string_zero_and_control_characters_unambiguous(context):
    viewer, tables = context
    first = layer(viewer)
    first.payload = Points((0, '0', '\x00\n'), [[0, 0, 0]] * 3, first.payload.frame, {})
    tables.show(first)
    text_columns = [call[2] for call in viewer.dvz.calls if call[0] == 'table_text']
    assert ('0', "'0'", "'\\x00\\n'") in text_columns
    assert ('integer', 'string', 'string') not in text_columns


def test_show_reopens_retained_widget_and_selects_its_layer(context):
    viewer, tables = context
    first, second = layer(viewer), layer(viewer)
    one, two = tables.show(first), tables.show(second)
    tables._opened.value = False
    assert tables.show(first) is one
    assert tables._opened.value and tables._active == 0
    assert len(tables.tables) == 2 and two.widget.handle is not None


def test_removed_empty_layer_closes_its_table(context):
    viewer, tables = context
    first = layer(viewer)
    first.payload = Points((), np.empty((0, 3)), first.payload.frame, {})
    first.refs = ()
    table = tables.show(first)
    first._closed = True
    tables._remove(())
    assert table.widget.handle is None and not tables.tables


def test_dropped_native_input_restores_authoritative_selection(context, monkeypatch):
    viewer, tables = context
    first = layer(viewer)
    table = tables.show(first)
    viewer.selection.set_observations((first.refs[0],))
    table.widget.handle.selection = [2]
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_table_draw', lambda *_args: (0, [], 1))
    with pytest.raises(RuntimeError, match='input batch dropped'):
        tables._draw_table(None, table)
    assert table.widget.handle.selection == [1]


def test_draw_uses_bool_window_contract_and_one_active_native_table(context, monkeypatch):
    import ctypes  # noqa: PLC0415 - native window contract

    viewer, tables = context
    first, second = layer(viewer), layer(viewer)
    tables.show(first)
    tables.show(second)
    windows, drawn, ended = [], [], []

    def window(_gui, title, opened, flags):
        assert title == b'Observations' and flags == 0
        assert isinstance(opened._obj, ctypes.c_bool)
        windows.append(opened._obj)
        return True

    monkeypatch.setattr(viewer.dvz, 'dvz_gui_begin', window, raising=False)
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_text', lambda *_args: None, raising=False)
    monkeypatch.setattr(
        viewer.dvz, 'dvz_gui_end', lambda *_args: ended.append(True), raising=False
    )
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_combo', lambda *_args: False, raising=False)
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_collapsing_header', lambda *_: False, raising=False)
    monkeypatch.setattr('ibl_datoviz.layer_gui._text', lambda *_: None)
    monkeypatch.setattr(tables, '_draw_table', lambda _gui, table: drawn.append(table.layer))
    tables.draw(None)
    assert len(windows) == len(ended) == 1
    assert drawn == [second]
    tables._opened.value = False
    tables.draw(None)
    assert len(windows) == 1


def test_scalar_columns_keep_raw_clipped_values_missingness_and_unpositioned_rows(context):
    viewer, tables = context
    first = layer(viewer)
    first.scalar_encoding = ScalarEncoding(
        np.array([0.0, np.nan, 50.0]), 'Rate', 'Hz', 'sequential', (1.0, 10.0), '#808080'
    )
    first.scalar_data = first.scalar_encoding
    table = tables.show(first)
    numeric = [call for call in viewer.dvz.calls if call[0] == 'table_double']
    np.testing.assert_equal(numeric[0][2], [0, np.nan, 50])
    assert table.refs == first.refs
    assert any(
        call[0] == 'table_text' and call[2] == ('Available', 'Missing (NaN)', 'Available')
        for call in viewer.dvz.calls
    )
    assert first.scalar_encoding._counts == (2, 1, 1, 1)
    assert table.widget.handle.columns[1]['title'] == 'Value'


def test_local_table_keeps_position_meaning_without_source_keys(context, monkeypatch):
    viewer, tables = context
    table = tables.show(layer(viewer))
    messages = []
    monkeypatch.setattr(
        viewer.dvz, 'dvz_gui_text', lambda _g, m: messages.append(m.decode()), raising=False
    )
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_collapsing_header', lambda *_: True, raising=False)
    monkeypatch.setattr('ibl_datoviz.layer_gui._text', lambda _v, _g, m: messages.append(m))
    draw_source_details(viewer, None, table.layer)
    assert 'assigned channel' in messages


def test_legend_distinguishes_missing_scalar_from_missing_coordinates(context, monkeypatch):
    viewer, _tables = context
    first = layer(viewer)
    first.scalar_encoding = ScalarEncoding(
        np.array([0.0, 2.0, np.nan]), 'Rate', 'Hz', 'sequential', (1.0, 10.0), '#80808000'
    )
    first._registry = SimpleNamespace(_scalar_colors=lambda *_: np.zeros((3, 4), np.uint8))
    viewer.ui_scale = 1
    viewer.selection.observations = first.refs
    messages, swatches = [], []
    monkeypatch.setattr('ibl_datoviz.layer_gui._text', lambda _v, _g, m: messages.append(m))
    monkeypatch.setattr(
        viewer.dvz, 'dvz_gui_text', lambda _g, m: messages.append(m.decode()), raising=False
    )
    monkeypatch.setattr(viewer.dvz, 'dvz_gui_same_line', lambda *_: None, raising=False)
    monkeypatch.setattr(
        viewer.dvz,
        'dvz_gui_color_edit4',
        lambda _g, _k, rgba, _f: swatches.append(tuple(rgba)),
        raising=False,
    )
    draw_scalar_legend(viewer, None, first, 'test')
    text = '\n'.join(messages)
    assert 'Rate (Hz)' in text
    assert '1 missing values' in text and 'not drawn' in text
    assert 'Selected' not in text  # Selection now has its own inspector section.
    assert len(swatches) == 4 and swatches[-1][3] == 0
