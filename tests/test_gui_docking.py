"""Default scientific docks leave sidebars outside the central table split."""

import ctypes
from types import SimpleNamespace

import pytest

from ibl_datoviz.viewer import AtlasViewer


@pytest.mark.parametrize('layers,quantity', [(('layer',), None), ((), object())])
def test_default_dock_order_splits_sidebars_before_observations(layers, quantity):
    calls = []
    dvz = SimpleNamespace(
        DVZ_GUI_DOCK_SLOT_LEFT=1,
        DVZ_GUI_DOCK_SLOT_RIGHT=2,
        DVZ_GUI_DOCK_SLOT_BOTTOM=4,
        DVZ_GUI_DOCK_SLOT_CENTER=0,
        dvz_gui_dock_window_once=lambda _gui, *args: calls.append(args),
    )
    viewer = SimpleNamespace(
        dvz=dvz,
        sidebar_width=400,
        ui_scale=1.5,
        viewport=object(),
        layers=layers,
        _regional_quantities=SimpleNamespace(handle=quantity),
        tables=SimpleNamespace(visible=True),
    )
    AtlasViewer._dock_gui_windows(viewer, None)
    assert calls == [
        (b'Regions', 1, 600),
        (b'Layers', 2, 510),
        (b'Observations', 4, 420),
        (b'3D atlas', 0, 0),
    ]


def test_no_observation_split_for_closed_or_empty_window():
    calls = []
    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            DVZ_GUI_DOCK_SLOT_LEFT=1,
            DVZ_GUI_DOCK_SLOT_CENTER=0,
            dvz_gui_dock_window_once=lambda _gui, *args: calls.append(args),
        ),
        sidebar_width=400,
        ui_scale=1,
        viewport=object(),
        layers=(),
        tables=SimpleNamespace(visible=False),
    )
    AtlasViewer._dock_gui_windows(viewer, None)
    assert [call[0] for call in calls] == [b'Regions', b'3D atlas']


@pytest.mark.parametrize('layout,explode_shown', [('3d', True), ('linked', False)])
def test_explode_toolbar_is_exclusive_to_3d_layout(layout, explode_shown):
    sliders, buttons = [], []
    viewer = SimpleNamespace(
        layout=layout,
        anatomy_presentation='detailed',
        selection_presentation='legacy',
        arcball=None,
        _explode_control=ctypes.c_float(0),
        dvz=SimpleNamespace(
            dvz_gui_set_next_item_width=lambda *_: None,
            dvz_gui_slider_float=lambda _gui, name, *_: sliders.append(name) or False,
            dvz_gui_same_line=lambda *_: None,
            dvz_gui_button=lambda _gui, name: buttons.append(name) or False,
        ),
    )
    AtlasViewer._draw_viewport_toolbar_gui(viewer, None)
    assert (b'Explode' in sliders) is explode_shown
    assert buttons == [b'Reset view']
