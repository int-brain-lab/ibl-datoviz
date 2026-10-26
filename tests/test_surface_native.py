"""Native surface visibility/alpha updates preserve canonical mesh and caller selection."""

import numpy as np
import pytest

from ibl_datoviz import AtlasViewer
from tests.test_atlas import FIXTURE


def test_native_region_hemisphere_empty_restore_and_palette_alpha():
    viewer = None
    try:
        try:
            viewer = AtlasViewer.from_pack(
                FIXTURE, width=256, height=192, palette={-315: (220, 30, 40, 128)}
            )
            pixels = viewer.render_offscreen()
        except RuntimeError as error:
            if 'Unable to load libdatoviz' in str(error) or 'dvz_app() failed' in str(error):
                pytest.skip('native runtime/GPU context unavailable')
            raise
        assert pixels.shape == (192, 256, 4)
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT
        positions, indices = viewer.mesh_data.positions.copy(), viewer.mesh_data.indices.copy()

        def capture():
            viewer.dvz.dvz_view_request_frame(viewer.view)
            assert viewer.dvz.dvz_view_render_once(viewer.view) == 0
            return np.array(viewer.dvz.dvz_view_capture_rgba(viewer.view), copy=True)

        viewer.set_selected_region_ids((-315,))
        viewer.set_hemisphere('right')
        assert viewer.selected_region_ids() == (-315,)
        right = capture()
        assert np.any(right != pixels)
        assert viewer.visible_region_ids() == (315,)
        viewer.set_hemisphere_visible('both', False)
        empty = capture()
        assert np.any(empty != right)
        assert viewer.visible_region_ids() == ()
        viewer.set_hemisphere('both')
        viewer.clear_selection()
        restored = capture()
        np.testing.assert_array_equal(restored, pixels)
        viewer.set_region_color(315, (20, 210, 30), hemisphere='both')
        recolored = capture()
        assert np.any(recolored != pixels)
        viewer.set_region_opacity(-315, 0)
        assert viewer.visible_region_ids() == (315,)
        capture()
        viewer.reset_region_style(-315)
        viewer.reset_region_style(315)
        np.testing.assert_array_equal(capture(), pixels)
        np.testing.assert_array_equal(viewer.mesh_data.positions, positions)
        np.testing.assert_array_equal(viewer.mesh_data.indices, indices)
    finally:
        if viewer is not None:
            viewer.close()
