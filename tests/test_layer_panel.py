"""Inspection focus, simple defaults and presentation edits preserve scientific state."""

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, Channels, Recording, SourceKey
from ibl_datoviz.layer_gui import LayerPanel, _noun
from tests import FIXTURES
from tests.test_atlas import FIXTURE
from tests.test_observation_table_integration import add_points, encode


@pytest.fixture
def app(native_datoviz):
    catalog = open_region_catalog(FIXTURES / 'linked-atlas-v1/volume-pack/regions.json')
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=catalog,
        enable_hover=False,
        width=960,
        height=720,
    ) as viewer:
        yield viewer


class Gui:
    def __init__(self):
        self.calls = []
        self.combos = {}
        self.buttons = set()
        self.headers = set()

    def dvz_gui_content_avail(self, _gui, size):
        size[:] = (430, 900)
        return True

    def dvz_gui_text(self, _gui, text):
        self.calls.append(('text', text))

    def dvz_gui_checkbox(self, _gui, label, _value):
        self.calls.append(('checkbox', label))
        return False

    def dvz_gui_combo(self, _gui, label, value, _items, _count):
        self.calls.append(('combo', label))
        if label in self.combos:
            value._obj.value = self.combos.pop(label)
            return True
        return False

    def dvz_gui_button(self, _gui, label):
        self.calls.append(('button', label))
        if label in self.buttons:
            self.buttons.remove(label)
            return True
        return False

    def dvz_gui_collapsing_header(self, _gui, label, _flags):
        self.calls.append(('header', label))
        return label in self.headers

    def dvz_gui_color_edit4(self, _gui, label, _value, flags):
        self.calls.append(('color', label, flags))
        return False

    def dvz_gui_same_line(self, *_args):
        pass

    def dvz_gui_separator_text(self, _gui, label):
        self.calls.append(('section', label))

    def dvz_gui_set_next_item_width(self, _gui, width):
        self.calls.append(('width', width))

    def dvz_gui_slider_float_format(self, *_args):
        self.calls.append(('size',))
        return False


@pytest.fixture
def gui(app, monkeypatch):
    result = Gui()
    for name in dir(result):
        if name.startswith('dvz_gui_'):
            monkeypatch.setattr(app.dvz, name, getattr(result, name))
    return result


def test_default_panel_separates_selection_hides_advanced_fields_and_keeps_scalar_data(app, gui):
    layer = add_points(app)
    encode(layer, [0, np.nan])
    app.selection.set_observations((layer.refs[1],))
    panel = LayerPanel(app)
    panel.draw(None)
    assert ('section', b'Selected point') in gui.calls
    assert ('text', b'No measurement') in gui.calls
    assert ('text', b'Location unavailable') in gui.calls
    assert not any(call[0] == 'size' for call in gui.calls)
    assert not any(call[:2] == ('combo', b'Original ID') for call in gui.calls)
    assert all(call[2] & (1 << 5) for call in gui.calls if call[0] == 'color')
    assert ('header', b'Appearance') in gui.calls
    assert ('header', b'Source and methods') in gui.calls


def test_inspection_is_not_scientific_selection_and_prunes_removed_layer(app, gui):
    first, second = add_points(app), add_points(app, 'Other')
    app.selection.set_observations((first.refs[0],))
    snapshot = app.selection.snapshot()
    panel = LayerPanel(app)
    gui.combos[b'##inspect_layer'] = 1
    panel.draw(None)
    assert panel.active_layer() is second and app.selection.snapshot() == snapshot
    app.remove_layer(second)
    assert panel.active_layer() is first


def test_gui_color_mode_preserves_measurement_table_selection_and_widget(app, gui, monkeypatch):
    layer = add_points(app)
    encode(layer, [0, np.nan])
    data = layer.scalar_data
    table = app.tables.show(layer)
    widget = table.widget.handle
    app.selection.set_observations((layer.refs[0],))
    snapshot = app.selection.snapshot()
    monkeypatch.setattr(
        app.dvz,
        'dvz_gui_table_set_column_double',
        lambda *_: pytest.fail('color mode must not rewrite measurements'),
    )
    panel = LayerPanel(app)
    for mode in (1, 0):
        gui.combos[b'##color_mode'] = mode
        panel.draw(None)
        assert layer.scalar_data is data and table.widget.handle is widget
        assert table.selected_refs() == (layer.refs[0],) and app.selection.snapshot() == snapshot
        assert (layer.scalar_encoding is None) == bool(mode)


def test_clear_selection_only_clears_the_inspected_layer(app, gui):
    first, second = add_points(app), add_points(app, 'Other')
    app.selection.set_observations((first.refs[0], first.refs[1], second.refs[1]))
    panel = LayerPanel(app)
    gui.buttons.add(b'View selected rows')
    panel.draw(None)
    assert app.tables.tables[0]._presentation.selected_only.value
    gui.buttons.add(b'Clear selection##observations')
    panel.draw(None)
    assert app.selection.observations == (second.refs[1],)


def test_recording_inspection_names_are_distinct_and_hide_source_identifiers(app, gui):
    source = SourceKey('test', 'test', '1', 'a' * 64)
    groups = []
    for index in range(2):
        pid = f'00000000-0000-0000-0000-00000000000{index}'
        recording = Recording(
            source, pid, 'session', channels=Channels((0,), [[0, 0, 0]], app.frame, {})
        )
        groups.append(app.add_recording(recording, name=pid, show=('channels',)))
    panel = LayerPanel(app)
    assert panel._layer_name(groups[0].channels) == 'Recording 1 / channels'
    assert panel._layer_name(groups[1].channels) == 'Recording 2 / channels'
    panel.draw(None)
    visible = '\n'.join(str(call) for call in gui.calls)
    assert '00000000-0000' not in visible
    assert panel.active_layer() is groups[0].channels
    assert ('section', b'Selected channel') in gui.calls
    assert app.selection.observations == ()


@pytest.mark.parametrize(
    'kind,expected',
    [('Channels', 'channel'), ('Clusters', 'cluster'), ('Sites', 'site'), ('Points', 'point')],
)
def test_inspector_uses_declared_population_type_independently_of_glyph(kind, expected):
    from types import SimpleNamespace  # noqa: PLC0415

    import ibl_datoviz  # noqa: PLC0415

    payload = getattr(ibl_datoviz, kind)((0,), [[0, 0, 0]], ibl_datoviz.WorldFrame('test'), {})
    layer = SimpleNamespace(payload=payload)
    assert _noun(layer) == expected
    assert _noun(layer, plural=True) == expected + 's'
