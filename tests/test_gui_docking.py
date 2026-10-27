"""Default scientific docks leave sidebars outside the central table split."""

import ctypes
from types import SimpleNamespace

import pytest

from ibl_datoviz.viewer import AtlasViewer
from ibl_datoviz.viewer_layout import ViewerLayout


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
    ViewerLayout(viewer).dock_windows(None)
    assert calls == [
        (b'Regions', 1, 560),
        (b'Layers', 2, 720),
        (b'Observations', 4, 510),
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
    ViewerLayout(viewer).dock_windows(None)
    assert [call[0] for call in calls] == [b'Regions', b'3D atlas']


@pytest.mark.parametrize('layout,explode_shown', [('3d', True), ('linked', False)])
def test_explode_toolbar_is_exclusive_to_3d_layout(layout, explode_shown):
    sliders, buttons, linked_controls = [], [], []
    viewer = SimpleNamespace(
        layout=layout,
        _linked=(
            SimpleNamespace(_draw_viewport_toolbar_gui=lambda _: linked_controls.append('slices'))
            if layout == 'linked'
            else None
        ),
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
    assert linked_controls == (['slices'] if layout == 'linked' else [])


@pytest.mark.parametrize(
    'width,height,scale', [(2240, 1600, 1.25), (1600, 1000, 1.0), (1440, 900, 1.5)]
)
def test_native_actual_dock_bounds_preserve_width_and_narrow_viewport(
    native_datoviz, monkeypatch, width, height, scale
):
    from ibl_anatomy import open_region_catalog  # noqa: PLC0415
    from ibl_datoviz import AtlasMesh, Points  # noqa: PLC0415
    from tests import FIXTURES  # noqa: PLC0415
    from tests.test_atlas import FIXTURE  # noqa: PLC0415

    catalog = open_region_catalog(FIXTURES / 'linked-atlas-v1/volume-pack/regions.json')
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=catalog,
        width=width,
        height=height,
        ui_scale=scale,
        enable_hover=False,
    ) as viewer:
        layer = viewer.add_points(Points((0,), [[0, 0, 0]], viewer.frame, {}))
        viewer.tables.show(layer)
        original = viewer._draw_scientific_layers_gui
        frames = []

        def measure(gui):
            original(gui)
            state = {}
            for name in (b'Regions', b'Layers', b'3D atlas'):
                viewer.dvz.dvz_gui_begin(gui, name, None, 0)
                try:
                    rect = viewer.dvz.DvzRect()
                    assert viewer.dvz.dvz_gui_current_window_rect(gui, ctypes.byref(rect))
                    state[name] = (rect.x, rect.y, rect.width, rect.height)
                finally:
                    viewer.dvz.dvz_gui_end(gui)
            frames.append(state)

        monkeypatch.setattr(viewer, '_draw_scientific_layers_gui', measure)
        viewer.show(frame_count=4)
        state = frames[-1]
        compact = width / scale < 1250
        target = min(360 * scale, width * (0.38 if compact else 0.30))
        assert state[b'Layers'][2] == pytest.approx(target, abs=4)
        assert state[b'3D atlas'][3] >= height * 0.55
        if compact:
            assert state[b'Regions'] == state[b'Layers']
            assert state[b'3D atlas'][2] >= width * 0.60
        else:
            assert state[b'Regions'][0] == 0
            assert state[b'3D atlas'][2] >= width * 0.45
