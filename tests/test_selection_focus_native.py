"""Native opaque selection pixels and shell-independent signed FACE queries."""

import ctypes

import numpy as np

from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.envelope import AtlasEnvelope
from tests.test_atlas import FIXTURE
from tests.test_native_surface_queries import query_at
from tests.test_smoke import _skip_without_native_datoviz


def test_native_focus_matches_opaque_signed_isolation_and_nonpickable_context():
    mesh = AtlasMesh.from_pack(FIXTURE)
    try:
        with AtlasViewer(mesh, width=256, height=192, selection_presentation='focus') as viewer:
            original = viewer.render_offscreen()

            def capture():
                viewer.dvz.dvz_view_request_frame(viewer.view)
                assert viewer.dvz.dvz_view_render_once(viewer.view) == 0
                return np.array(viewer.dvz.dvz_view_capture_rgba(viewer.view), copy=True)

            viewer.set_hemisphere('left')
            opaque_left = capture()
            assert np.any(original != opaque_left)
            viewer.set_hemisphere('both')
            viewer.set_selected_region_ids((-315,))
            assert viewer._surface_alpha_mode == viewer.dvz.DVZ_ALPHA_OPAQUE
            np.testing.assert_array_equal(capture(), opaque_left)
            assert query_at(viewer, 90, 96, 1) == (True, -315)

            # Synthetic prepared shell deliberately overlaps the scientific mesh;
            # it carries no identities and cannot replace a scientific FACE hit.
            shell = AtlasEnvelope.from_world_arrays(
                mesh.positions_um * 1.05,
                mesh.normals,
                mesh.indices,
                mesh,
                reference_space=mesh.reference_space,
                variant='source-native',
            )
            viewer.set_selection_envelope(shell)
            assert viewer._selection_envelope_visible
            assert query_at(viewer, 90, 96, 2) == (True, -315)
            viewer.set_selection_presentation('isolate')
            assert not viewer._selection_envelope_visible
            np.testing.assert_array_equal(capture(), opaque_left)
            viewer.set_selection_presentation('all')
            assert viewer.selected_region_ids() == (-315,)
            np.testing.assert_array_equal(capture(), original)
            viewer.set_selection_presentation('focus')
            viewer.clear_selection()
            assert not viewer._selection_envelope_visible
            np.testing.assert_array_equal(capture(), original)
            assert query_at(viewer, 90, 96, 3) == (True, -315)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_native_double_click_and_button_restore_the_configured_initial_view(monkeypatch):
    """Reset must restore the actual startup frame even after later programmatic poses."""
    try:
        with AtlasViewer(
            AtlasMesh.from_pack(FIXTURE), width=256, height=192, camera_angles=(0.2, -0.4, 2.5)
        ) as viewer:
            viewer.set_selected_region_ids((-315,))
            viewer.set_explode(0.2)
            initial = viewer.render_offscreen()
            dvz = viewer.dvz

            def capture():
                dvz.dvz_view_request_frame(viewer.view)
                assert dvz.dvz_view_render_once(viewer.view) == 0
                return np.array(dvz.dvz_view_capture_rgba(viewer.view), copy=True)

            def move():
                viewer.set_camera_angles((-0.4, 0.3, 0.7))
                assert dvz.dvz_arcball_pan(viewer.arcball, (ctypes.c_float * 2)(0.2, -0.1)) == 0
                assert dvz.dvz_arcball_zoom(viewer.arcball, 2.0) == 0
                assert np.any(capture() != initial)

            move()
            event = dvz.DvzPointerEvent()
            event.type = dvz.DVZ_POINTER_EVENT_DOUBLE_CLICK
            assert dvz.dvz_arcball_pointer(viewer.arcball, ctypes.byref(event))
            np.testing.assert_array_equal(capture(), initial)

            # Both entry points must use that same registered startup pose.
            move()
            monkeypatch.setattr(dvz, 'dvz_gui_set_next_item_width', lambda *_: None)
            monkeypatch.setattr(dvz, 'dvz_gui_slider_float', lambda *_: False)
            monkeypatch.setattr(dvz, 'dvz_gui_same_line', lambda *_: None)
            monkeypatch.setattr(dvz, 'dvz_gui_button', lambda *_: True)
            viewer._draw_viewport_toolbar_gui(None)
            np.testing.assert_array_equal(capture(), initial)
            assert viewer.selected_region_ids() == (-315,)
            assert viewer.explode == 0.2
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
