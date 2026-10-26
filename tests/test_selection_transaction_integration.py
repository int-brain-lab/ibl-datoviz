"""Scientific selection, native highlights, and retained tables commit atomically."""

from __future__ import annotations

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, LayerObservationRef, Paths, Points
from tests import FIXTURES
from tests.test_atlas import FIXTURE
from tests.test_layer_attributes import displayed_colors


@pytest.fixture
def app(native_datoviz):
    """Use actual native visuals and tables with one scientific selection owner."""
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json'),
        width=640,
        height=480,
        enable_hover=False,
    ) as viewer:
        yield viewer


def point_payload(app, *, missing=False):
    positions = [[np.nan, 0, 0], [np.nan, 0, 0]] if missing else [[0, 0, 0], [50, 0, 0]]
    return Points(('first', 'last'), positions, app.frame, {'kind': 'test annotations'})


def mixed_layers(app):
    first = app.add_points(point_payload(app), name='Point annotations')
    second = app.add_points(point_payload(app), name='Physical sphere annotations', glyph='sphere')
    route = app.add_paths(
        Paths(('route',), ([[0, 0, 0], [50, 50, 50]],), app.frame, {}), name='Route'
    )
    first.set_color('#112233')
    second.set_color('#55667780')
    tables = tuple(app.tables.show(layer) for layer in (first, second, route))
    refs = (first.observation('last'), second.observation('first'), route.observation('route'))
    return (first, second, route), tables, refs


def test_one_event_observes_all_committed_highlights_and_table_selections(app):
    layers, tables, refs = mixed_layers(app)
    first_component, sphere_component = layers[0]._visual, layers[1]._visual
    seen = []

    def changed(event):
        seen.append(event)
        assert tuple(table.selected_refs() for table in tables) == tuple((ref,) for ref in refs)
        assert all(
            layer._selected == frozenset((ref,)) for layer, ref in zip(layers, refs, strict=True)
        )
        np.testing.assert_array_equal(displayed_colors(layers[0])[1], [255, 70, 180, 255])
        np.testing.assert_array_equal(displayed_colors(layers[1])[0], [255, 70, 180, 255])

    app.selection.on_changed(changed)
    previous_revision = app.selection.revision
    app.selection.set_observations(refs)
    assert len(seen) == 1 and app.selection.revision == previous_revision + 1
    assert not app.selection.callback_errors
    assert layers[0]._visual is first_component and layers[1]._visual is sphere_component
    assert app.selection.observations == refs


@pytest.mark.parametrize('failing_attribute', ['color', 'alpha'])
def test_partial_second_layer_write_restores_tables_displays_and_no_event(
    app, monkeypatch, failing_attribute
):
    layers, tables, refs = mixed_layers(app)
    first, sphere, route = layers
    previous_colors = tuple(displayed_colors(layer).copy() for layer in (first, sphere))
    components = tuple(layer._visual for layer in layers)
    previous_revision = app.selection.revision
    previous_alpha = sphere._visual._alpha_mode
    selected = refs if failing_attribute == 'color' else (refs[0], *sphere.refs, refs[2])
    target_id = int(app.dvz.dvz_visual_id(sphere._visual.visual))
    native_colors, native_alpha, events = {}, {}, []
    failed = False
    original_data = app.dvz.dvz_visual_set_data
    original_alpha = app.dvz.dvz_visual_set_alpha_mode

    def upload(visual, name, values):
        nonlocal failed
        status = original_data(visual, name, values)
        visual_id = int(app.dvz.dvz_visual_id(visual))
        if name == 'color':
            native_colors[visual_id] = np.array(values, copy=True)
            if visual_id == target_id and failing_attribute == 'color' and not failed:
                failed = True
                return -1  # A real native write already happened.
        return status

    def alpha(visual, mode):
        nonlocal failed
        status = original_alpha(visual, mode)
        visual_id = int(app.dvz.dvz_visual_id(visual))
        native_alpha[visual_id] = mode
        if visual_id == target_id and failing_attribute == 'alpha' and not failed:
            failed = True
            return -1  # The alpha policy was changed before reporting failure.
        return status

    monkeypatch.setattr(app.dvz, 'dvz_visual_set_data', upload)
    monkeypatch.setattr(app.dvz, 'dvz_visual_set_alpha_mode', alpha)
    app.selection.on_changed(events.append)
    # Native table input may be ahead of committed scientific selection.
    tables[0].widget.set_selection(tables[0].selection_keys((refs[0],)), 'simulate table input')
    with pytest.raises(RuntimeError):
        app.selection.set_observations(selected)

    assert failed and not app._closed
    assert app.selection.observations == () and app.selection.revision == previous_revision
    assert not events and all(table.selected_refs() == () for table in tables)
    assert tuple(layer._visual for layer in layers) == components
    assert all(not layer._selected for layer in layers)
    for layer, previous in zip((first, sphere), previous_colors, strict=True):
        np.testing.assert_array_equal(displayed_colors(layer), previous)
        np.testing.assert_array_equal(
            native_colors[int(app.dvz.dvz_visual_id(layer._visual.visual))], previous
        )
    assert sphere._visual._alpha_mode == previous_alpha
    if failing_attribute == 'alpha':
        assert native_alpha[target_id] == previous_alpha
    assert not route._closed


def test_missing_only_selection_retains_refs_without_uploading_native_attributes(app, monkeypatch):
    missing = app.add_points(point_payload(app, missing=True))
    empty = app.add_points(Points((), np.empty((0, 3)), app.frame, {}))
    table, empty_table = app.tables.show(missing), app.tables.show(empty)
    components = (missing._visual, empty._visual)
    original = app.dvz.dvz_visual_set_data
    uploads = []

    def upload(visual, name, values):
        uploads.append(name)
        return original(visual, name, values)

    monkeypatch.setattr(app.dvz, 'dvz_visual_set_data', upload)
    ref = missing.observation('last')
    app.selection.set_observations((ref,))
    assert app.selection.observations == (ref,) and table.selected_refs() == (ref,)
    assert empty_table.selected_refs() == () and missing._selected == frozenset((ref,))
    assert (missing._visual, empty._visual) == components
    assert not uploads


def test_foreign_and_removed_refs_fail_before_table_or_scientific_mutation(app):
    layer = app.add_points(point_payload(app))
    table = app.tables.show(layer)
    ref = layer.observation('first')
    app.selection.set_observations((ref,))
    foreign = LayerObservationRef('another-viewer', ref.original_id, ref.source_key)
    before = app.selection.snapshot(), app.selection.revision, table.selected_refs()
    with pytest.raises(ValueError, match='foreign|removed|unknown'):
        app.selection.set_observations((foreign,))
    assert (app.selection.snapshot(), app.selection.revision, table.selected_refs()) == before
    app.remove_layer(layer)
    previous = app.selection.snapshot(), app.selection.revision
    with pytest.raises(ValueError, match='foreign|removed|unknown'):
        app.selection.set_observations((ref,))
    assert (app.selection.snapshot(), app.selection.revision) == previous
