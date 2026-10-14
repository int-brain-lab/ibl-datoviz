"""GPU face identities after retained surface visibility and mapping changes."""

import ctypes
from dataclasses import replace

import numpy as np

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
