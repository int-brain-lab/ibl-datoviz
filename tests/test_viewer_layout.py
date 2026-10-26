"""GUI assembly must unwind native scopes before viewer callback teardown."""

from types import SimpleNamespace

import pytest

from ibl_datoviz.viewer_layout import ViewerLayout


@pytest.mark.parametrize('failing_window', [b'Regions', b'3D atlas'])
def test_gui_failure_closes_active_window_before_callback_unwinds(failing_window):
    calls = []

    def begin(_gui, title, *_args):
        calls.append(('begin', title))
        return True

    def draw(title):
        calls.append(('draw', title))
        if title == failing_window:
            raise RuntimeError('widget failure')

    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            dvz_gui_begin=begin,
            dvz_gui_end=lambda _gui: calls.append(('end',)),
        ),
        viewport=object(),
        _process_gui_frame=lambda: calls.append(('process',)),
        _dock_gui_windows=lambda _gui: calls.append(('dock',)),
        _draw_sidebar_gui=lambda _gui: draw(b'Regions'),
        _draw_viewport_toolbar_gui=lambda _gui: draw(b'3D atlas'),
    )
    with pytest.raises(RuntimeError, match='widget failure'):
        ViewerLayout(viewer).draw_frame(None)
    assert calls[-2:] == [('draw', failing_window), ('end',)]
    assert sum(call[0] == 'begin' for call in calls) == sum(call[0] == 'end' for call in calls)
    assert calls[:2] == [('process',), ('dock',)]


def test_collapsed_region_window_still_processes_async_results_and_other_controls():
    calls = []
    viewer = SimpleNamespace(
        dvz=SimpleNamespace(
            dvz_gui_begin=lambda *_args: False,
            dvz_gui_end=lambda _gui: calls.append('end'),
        ),
        viewport=None,
        _process_gui_frame=lambda: calls.append('process'),
        _dock_gui_windows=lambda _gui: calls.append('dock'),
        _draw_sidebar_gui=lambda _gui: calls.append('sidebar'),
        _draw_auxiliary_gui=lambda _gui: calls.append('auxiliary'),
        _draw_scientific_layers_gui=lambda _gui: calls.append('layers'),
        tables=SimpleNamespace(draw=lambda _gui: calls.append('tables')),
    )
    ViewerLayout(viewer).draw_frame(None)
    assert calls == ['process', 'dock', 'end', 'auxiliary', 'layers', 'tables']
