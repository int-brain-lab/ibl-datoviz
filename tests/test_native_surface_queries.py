"""GPU face identities after retained surface visibility and mapping changes."""

import ctypes
from dataclasses import replace

import numpy as np
import pytest

from ibl_datoviz import AtlasMesh, AtlasViewer
from tests.test_atlas import FIXTURE
from tests.test_smoke import _skip_without_native_datoviz


def query_at(viewer, x, y, request_id):
    dvz = viewer.dvz
    request = dvz.dvz_query_request()
    request.request_id = request_id
    request.target = dvz.DVZ_SCENE_TARGET_FACE
    assert dvz.dvz_panel_query_px(viewer.panel, x, y, ctypes.byref(request)) == 0
    assert dvz.dvz_view_render_once(viewer.view) == 0
    result = dvz.DvzQueryResult()
    while dvz.dvz_scene_poll_query(viewer.scene, ctypes.byref(result)):
        if result.request_id == request_id:
            assert result.status in (
                dvz.DVZ_QUERY_STATUS_HIT,
                dvz.DVZ_QUERY_STATUS_MISS,
                dvz.DVZ_QUERY_STATUS_NO_CAPABLE_VISUAL,
            )
            return bool(result.hit), np.asarray(result.link_key, np.uint64).view(np.int64).item()
    raise AssertionError('native query completed without its requested result')


def test_screen_pan_moves_rendered_surface_and_gpu_query_together():
    """Image framing must move picking with the pixels and reset both together."""
    try:
        with AtlasViewer(AtlasMesh.from_pack(FIXTURE), width=256, height=192) as viewer:
            viewer._create_view(offscreen=True, title='Screen pan query alignment')
            dvz = viewer.dvz
            if not hasattr(dvz, 'DVZ_ARCBALL_FLAGS_SCREEN_PAN'):
                pytest.skip('configured native baseline predates optional image-plane pan')
            assert query_at(viewer, 90, 96, 1) == (True, -315)
            before = np.array(dvz.dvz_view_capture_rgba(viewer.view), copy=True)
            offset = (ctypes.c_float * 2)(2 * 40 / 256, 2 * 24 / 192)
            assert dvz.dvz_arcball_pan(viewer.arcball, offset) == 0
            assert query_at(viewer, 130, 72, 2) == (True, -315)
            after = np.array(dvz.dvz_view_capture_rgba(viewer.view), copy=True)
            np.testing.assert_allclose(after[66:78, 124:136], before[90:102, 84:96], atol=1)
            if hasattr(dvz, 'DVZ_ARCBALL_FLAGS_PROJECTION_ZOOM'):
                assert dvz.dvz_arcball_zoom(viewer.arcball, 1.25) == 0
                assert query_at(viewer, 130.5, 66, 4) == (True, -315)
                magnified = np.array(dvz.dvz_view_capture_rgba(viewer.view), copy=True)
                dvz.dvz_arcball_resize(viewer.arcball, 256, 192)
                shift = (ctypes.c_float * 2)(20, -10)
                assert dvz.dvz_arcball_pan_shift(viewer.arcball, shift) == 0
                assert query_at(viewer, 150.5, 56, 5) == (True, -315)
                moved = np.array(dvz.dvz_view_capture_rgba(viewer.view), copy=True)
                np.testing.assert_allclose(
                    moved[50:62, 145:157], magnified[60:72, 125:137], atol=1
                )
            assert dvz.dvz_arcball_reset(viewer.arcball) == 0
            assert query_at(viewer, 90, 96, 3) == (True, -315)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_native_surface_queries_preserve_signed_keys_across_retained_updates():
    mesh = AtlasMesh.from_pack(FIXTURE)
    presentations = tuple(
        {**p, 'mappings': {**p['mappings'], 'beryl': 8 if p['side'] == 'right' else -8}}
        for p in mesh.presentations
    )
    mesh = replace(mesh, presentations=presentations)
    try:
        with AtlasViewer(mesh, width=256, height=192) as viewer:
            viewer._create_view(offscreen=True, title='Retained face query')
            # This position intersects the left fixture surface with a signed key.
            hit, key = query_at(viewer, 90, 96, 1)
            assert hit and key == -315
            viewer.set_selected_region_ids((key,))
            viewer.hide_region(key)
            assert query_at(viewer, 90, 96, 2) != (True, key)
            assert viewer.selected_region_ids() == (key,)
            viewer.show_region(key)
            assert query_at(viewer, 90, 96, 3) == (True, key)
            viewer.set_region_opacity(key, 0)
            assert query_at(viewer, 90, 96, 4) != (True, key)
            assert viewer.selected_region_ids() == (key,)
            viewer.reset_region_style(key)
            assert query_at(viewer, 90, 96, 5) == (True, key)
            viewer.set_hemisphere_visible('both', False)
            assert not query_at(viewer, 90, 96, 6)[0]
            assert viewer.selected_region_ids() == (key,)
            viewer.set_hemisphere('both')
            assert query_at(viewer, 90, 96, 7) == (True, key)
            viewer.set_mapping('beryl')
            assert query_at(viewer, 90, 96, 8) == (True, -8)
            assert viewer.selected_region_ids() == ()
            viewer.set_mapping('allen')
            assert query_at(viewer, 90, 96, 9) == (True, key)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_gpu_selection_decoration_does_not_hide_authored_face_queries():
    mesh = AtlasMesh.from_pack(FIXTURE)
    try:
        with AtlasViewer(mesh, width=256, height=192, selection_context_opacity=0) as viewer:
            viewer._create_view(offscreen=True, title='Decoration versus authored coverage')
            assert query_at(viewer, 90, 96, 1) == (True, -315)
            # A logical selection with no mesh parts still activates context dimming.
            viewer.set_selected_region_ids((997,))
            assert viewer._surface_state.words.sum() == 0
            assert query_at(viewer, 90, 96, 2) == (True, -315)
            viewer._set_hovered_region_ids((-315,))
            assert query_at(viewer, 90, 96, 3) == (True, -315)
            # Authoring zero opacity remains a real visibility/picking change.
            viewer.set_region_opacity(-315, 0)
            assert query_at(viewer, 90, 96, 4) != (True, -315)
            viewer.reset_region_style(-315)
            viewer.clear_selection()
            assert query_at(viewer, 90, 96, 5) == (True, -315)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
