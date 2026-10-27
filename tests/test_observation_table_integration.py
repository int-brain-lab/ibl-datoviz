"""Tables, highlights and scientific notifications commit as one operation."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, Points
from tests import FIXTURES
from tests.test_atlas import FIXTURE


@pytest.fixture
def app(native_datoviz):
    regions = FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json'
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=open_region_catalog(regions),
        width=960,
        height=720,
        enable_hover=False,
    ) as viewer:
        yield viewer


def add_points(app, name='Observations'):
    return app.add_points(
        Points((0, 'missing'), [[0, 0, 0], [np.nan, 0, 0]], app.frame, {}),
        name=name,
    )


def test_native_tables_match_selection_before_notification_and_keep_missing_rows(app):
    first, second = add_points(app), add_points(app, 'Other attachment')
    table, other = app.tables.show(first), app.tables.show(second)
    selected = first.observation('missing')
    also_selected = second.observation(0)
    seen = []

    def changed(event):
        seen.append((event, table.selected_refs(), other.selected_refs()))
        assert selected in first._selected

    app.selection.on_changed(changed)
    app.selection.set_observations((selected, also_selected))
    assert seen[-1][1:] == ((selected,), (also_selected,))
    first.set_visible(False)
    app.anatomy.set_mapping('beryl')
    assert len(table.refs) == 2 and table.selected_refs() == (selected,)
    assert app.selection.observations == (selected, also_selected)


def test_highlight_failure_restores_premutated_table_and_scientific_state(app, monkeypatch):
    layer = add_points(app)
    table = app.tables.show(layer)
    first, missing = layer.refs
    app.selection.set_observations((first,))
    previous_revision = app.selection.revision
    # Native input changes the table before its selection event reaches Python.
    table.widget.set_selection(table.selection_keys((missing,)), 'simulate table input')

    original = app.dvz.dvz_visual_set_data
    target_id = int(app.dvz.dvz_visual_id(layer._visual.visual))
    failed = False
    writes = []

    def fail_after_write(visual, attribute, values):
        nonlocal failed
        status = original(visual, attribute, values)
        if attribute == 'color' and int(app.dvz.dvz_visual_id(visual)) == target_id:
            writes.append(np.array(values, copy=True))
            if not failed:
                failed = True
                return -1  # Native colors changed before the failure was reported.
        return status

    monkeypatch.setattr(app.dvz, 'dvz_visual_set_data', fail_after_write)
    with pytest.raises(RuntimeError, match='point colors'):
        app.selection.set_observations((missing,))
    assert failed
    np.testing.assert_array_equal(writes[-1], [[255, 70, 180, 255]])
    assert table.selected_refs() == (first,)
    assert app.selection.observations == (first,)
    assert layer._selected == frozenset((first,))
    assert app.selection.revision == previous_revision


def test_removal_closes_owned_tables_before_the_selection_notification(app):
    layer, other_layer = add_points(app), add_points(app, 'Other')
    table = app.tables.show(layer)
    other = app.tables.show(other_layer)
    first, second = layer.observation(0), other_layer.observation('missing')
    app.selection.set_observations((first, second))
    seen = []
    app.selection.on_changed(lambda event: seen.append((event, table.widget.handle)))
    app.remove_layer(layer)
    assert table.widget.handle is None and seen[-1][1] is None
    with pytest.raises(RuntimeError, match='removed or closed'):
        table.selected_refs()
    assert app.selection.observations == (second,) and other.selected_refs() == (second,)
    empty = app.add_points(Points((), np.empty((0, 3)), app.frame, {}))
    empty_table = app.tables.show(empty)
    app.remove_layer(empty)
    assert empty_table.widget.handle is None
    app.close()
    assert other.widget.handle is None and app.scene is None


def test_gui_table_shutdown_waits_for_native_frame_return(app, monkeypatch):
    layer = add_points(app)
    table = app.tables.show(layer)
    original = app.tables.draw
    reached = []

    def close_in_frame(gui):
        original(gui)
        reached.append(True)
        app.close()
        assert table.widget.handle is not None and not layer._closed

    monkeypatch.setattr(app.tables, 'draw', close_in_frame)
    app.show(frame_count=3)
    assert reached and app._closed and table.widget.handle is None


def test_native_table_reads_reject_foreign_thread_before_native_access(app):
    table = app.tables.show(add_points(app))
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match='owning thread'),
    ):
        pool.submit(table.selected_refs).result()


@pytest.fixture
def scalar_columns(app, monkeypatch):
    """Observe real native copies, including injected failures after mutation."""
    state = {}
    for kind in ('double', 'text'):
        name = f'dvz_gui_table_set_column_{kind}'
        original = getattr(app.dvz, name)

        def record(handle, column, values, *, kind=kind, original=original):
            status = original(handle, column, values)
            if column in (4, 5):
                state[kind] = np.array(values, copy=True) if kind == 'double' else tuple(values)
            return status

        monkeypatch.setattr(app.dvz, name, record)
    return state


def encode(layer, values, *, units='Hz'):
    layer.color_by(values, name='Rate', units=units, cmap='viridis', limits=(1, 10))


def test_active_scalar_updates_retain_table_filter_selection_and_raw_values(
    app, scalar_columns, monkeypatch
):
    layer = add_points(app)
    table = app.tables.show(layer)
    widget, refs = table.widget.handle, table.refs
    app.selection.set_observations((layer.refs[1],))
    revision = app.selection.revision
    assert app.dvz.dvz_gui_table_set_filter(widget, b'missing') == 0
    sort = app.dvz.dvz_gui_table_get_sort(widget)
    monkeypatch.setattr(app.dvz, 'dvz_gui_table_set_rows', lambda *_: pytest.fail('rows reset'))
    for values, units in (([0, np.nan], 'Hz'), ([-5, 99], 'mV')):
        encode(layer, values, units=units)
        np.testing.assert_equal(scalar_columns['double'], values)
        assert layer.scalar_encoding.units == units
        assert table.widget.handle is widget and table.refs == refs
        assert table.selected_refs() == (layer.refs[1],)
        assert app.dvz.dvz_gui_table_get_filter(widget) == 'missing'
        assert app.dvz.dvz_gui_table_get_sort(widget) == sort
    layer.set_color('#112233')
    assert layer.scalar_encoding is None and np.isnan(scalar_columns['double']).all()
    assert scalar_columns['text'] == ('No scalar encoding',) * 2
    assert app.selection.revision == revision


@pytest.mark.parametrize('kind', ['double', 'text', 'visual'])
@pytest.mark.parametrize('action', ['scalar', 'uniform'])
def test_scalar_partial_writes_restore_tables_colors_metadata_and_selection(
    app, scalar_columns, monkeypatch, kind, action
):
    layer = add_points(app)
    table = app.tables.show(layer)
    encode(layer, [0, np.nan])
    old_encoding, old_colors = layer.scalar_encoding, layer._colors
    app.selection.set_observations((layer.refs[1],))
    revision = app.selection.revision
    name = 'dvz_visual_set_data' if kind == 'visual' else f'dvz_gui_table_set_column_{kind}'
    original = getattr(app.dvz, name)
    failed = False

    def fail_once(*args):
        nonlocal failed
        status = original(*args)
        if not failed:
            failed = True
            return -1
        return status

    monkeypatch.setattr(app.dvz, name, fail_once)
    with pytest.raises(RuntimeError):
        if action == 'scalar':
            encode(layer, [5, 6], units='mV')
        else:
            layer.set_color('#112233')
    assert failed and layer.scalar_encoding is old_encoding and layer._colors is old_colors
    np.testing.assert_equal(scalar_columns['double'], [0, np.nan])
    assert scalar_columns['text'] == ('Available', 'Missing (NaN)')
    assert table.selected_refs() == (layer.refs[1],)
    assert app.selection.revision == revision and not app._closed


def test_failed_scalar_table_recovery_closes_owner(app, monkeypatch):
    layer = add_points(app)
    table = app.tables.show(layer)
    monkeypatch.setattr(app.dvz, 'dvz_gui_table_set_column_double', lambda *_: -1)
    with pytest.raises(RuntimeError, match='scalar rollback failed; viewer closed'):
        encode(layer, [1, 2])
    assert app._closed and table.widget.handle is None


@pytest.mark.parametrize('empty', [False, True])
def test_empty_and_all_missing_scalar_tables_retain_complete_population(app, empty):
    layer = (
        app.add_points(Points((), np.empty((0, 3)), app.frame, {})) if empty else add_points(app)
    )
    table = app.tables.show(layer)
    layer.set_visible(False)
    encode(layer, np.full(len(layer.refs), np.nan))
    assert table.refs == layer.refs
    assert layer.scalar_encoding._counts == (0, len(layer.refs), 0, 0)
    layer.set_color('#112233')
    assert not layer.visible and layer.scalar_encoding is None
