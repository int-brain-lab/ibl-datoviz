"""Native context coverage, scientific parent identity and fine-overlay isolation."""

from types import SimpleNamespace

import numpy as np

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.context import AtlasContextSurface
from tests import FIXTURES
from tests.test_atlas import FIXTURE
from tests.test_native_surface_queries import query_at
from tests.test_smoke import _skip_without_native_datoviz


def test_native_major_context_parent_keys_and_visible_coverage_across_mapping():
    mesh = AtlasMesh.from_pack(FIXTURE)
    source = SimpleNamespace(
        positions_um=mesh.positions_um,
        normals=mesh.normals,
        indices=mesh.indices,
        asset=SimpleNamespace(
            reference_space_id=mesh.reference_space,
            variant='source-native',
            source_allen_id=8,
        ),
    )
    context = AtlasContextSurface.from_geometry(source, mesh, color=(140, 180, 210))
    try:
        with AtlasViewer(
            mesh,
            width=256,
            height=192,
            anatomical_context=[context],
            anatomy_presentation='major',
            context_opacity=0.04,
            catalog=open_region_catalog(
                FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json'
            ),
        ) as viewer:
            pixels = viewer.render_offscreen()
            assert not np.any(viewer._surface_presentation.face_mask)
            assert query_at(viewer, 90, 96, 1) == (True, -8)
            viewer.set_mapping('beryl')
            # This fixture has no fine Beryl surface; context must retain the
            # actual displayed source parent, rather than inventing fine IDs.
            assert query_at(viewer, 90, 96, 2) == (True, -8)
            viewer.set_hemisphere('right')
            assert not query_at(viewer, 90, 96, 3)[0]
            viewer.set_hemisphere('both')
            viewer.set_context_opacity(0)
            assert not query_at(viewer, 90, 96, 4)[0]
            viewer.set_context_opacity(0.04)
            viewer.set_mapping('allen')
            viewer.dvz.dvz_view_request_frame(viewer.view)
            assert viewer.dvz.dvz_view_render_once(viewer.view) == 0
            restored = np.array(viewer.dvz.dvz_view_capture_rgba(viewer.view), copy=True)
            np.testing.assert_array_equal(restored, pixels)
            viewer.set_selected_region_ids((-315,))
            assert viewer.visible_region_ids() == (-315,)
            assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT
            assert np.max(viewer._surface_presentation.base_colors[:, 3]) <= 46
            viewer.set_surface_visible(False)
            assert not query_at(viewer, 90, 96, 5)[0]
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
