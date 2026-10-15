"""Tables, highlights and scientific notifications commit as one operation."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, Points
from tests import FIXTURES
from tests.test_atlas import FIXTURE


@pytest.fixture
def app():
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

    def fail(**_changes):
        raise RuntimeError('injected highlight creation failure')

    monkeypatch.setattr(layer, '_build', fail)
    with pytest.raises(RuntimeError, match='highlight creation'):
        app.selection.set_observations((missing,))
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
