"""Native rendering/query parity at an original-world hemisphere boundary."""

from dataclasses import replace

import numpy as np

from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.atlas import _MeshPresentationBoundary
from tests.test_native_surface_queries import query_at
from tests.test_smoke import _skip_without_native_datoviz


def crossing_surface():
    """Keep two complete source triangles crossing the original ML=0 plane."""
    positions = np.array(
        [[-0.7, -0.7, 0], [0.7, -0.7, 0], [0.7, 0.7, 0], [-0.7, 0.7, 0]],
        dtype=np.float32,
    )
    return AtlasMesh(
        positions_um=positions * 1000,
        positions=positions.copy(),
        explode_offsets=np.tile(np.array([0.1, 0, 0], np.float32), (4, 1)),
        normals=np.tile(np.array([0, 0, 1], np.float32), (4, 1)),
        indices=np.array([0, 1, 2, 0, 2, 3], np.uint32),
        component_ids=np.zeros(4, np.uint16),
        presentation_ids=np.array([0, 1, 1, 0], np.int32),
        face_presentation_ids=np.array([1, 0], np.int32),
        presentations=tuple(
            {
                'presentation_id': index,
                'side': side,
                'mappings': {'allen': sign * 315, 'beryl': sign * 8, 'cosmos': sign * 997},
            }
            for index, (side, sign) in enumerate((('left', -1), ('right', 1)))
        ),
        reference_space='synthetic-test-only',
        display_scale=0.001,
        _presentation_boundary=_MeshPresentationBoundary(
            'original-world-ml', 0, 0, 'right', ((0, 0, 1),)
        ),
    )


def test_native_coplanar_midline_belongs_to_right_after_rotation_and_side_hiding():
    # The complete source surface lies at original ML=0. This avoids assuming
    # that a perspective framebuffer's central pixel samples the exact plane.
    source = crossing_surface()
    source = replace(
        source, _presentation_boundary=replace(source._presentation_boundary, ml_axis=2)
    )
    try:
        with AtlasViewer(source, width=256, height=192) as viewer:
            viewer._create_view(offscreen=True, title='Original-world hemisphere seam')
            request_id = 0
            for rotation in (0, np.pi):
                viewer.set_camera_angles((0, 0, rotation))
                for hemisphere in ('both', 'left', 'right'):
                    viewer.set_hemisphere(hemisphere)
                    request_id += 1
                    hit, key = query_at(viewer, 128, 96, request_id)
                    if hemisphere == 'left':
                        assert not hit
                    else:
                        assert hit and key == 315
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_native_crossing_faces_cover_both_sides_without_hidden_side_pick_leaks():
    try:
        with AtlasViewer(crossing_surface(), width=256, height=192) as viewer:
            viewer._create_view(offscreen=True, title='Complementary crossing coverage')
            request_id = 0
            for rotation in (0, np.pi):
                viewer.set_camera_angles((0, 0, rotation))
                left_pixel, right_pixel = (127.5, 128.5) if rotation == 0 else (128.5, 127.5)
                for hemisphere in ('both', 'left', 'right'):
                    viewer.set_hemisphere(hemisphere)
                    for side, pixel, expected in (
                        ('left', left_pixel, -315),
                        ('right', right_pixel, 315),
                    ):
                        request_id += 1
                        hit, key = query_at(viewer, pixel, 96, request_id)
                        if hemisphere in ('both', side):
                            assert hit and key == expected
                        else:
                            assert not hit
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_native_boundary_retains_signed_queries_through_mapping_explode_and_decoration():
    source = crossing_surface()
    snapshot = source.positions_um.copy()
    try:
        with AtlasViewer(source, width=256, height=192) as viewer:
            viewer._create_view(offscreen=True, title='Retained hemisphere coverage')
            bank = viewer._surface_state.handle
            clip = viewer._surface_geometry.fragment_clip.copy()
            request_id = 0
            for mapping, region in (('allen', 315), ('beryl', 8), ('cosmos', 997)):
                viewer.set_mapping(mapping)
                for explode in (0, 1):
                    viewer.set_explode(explode)
                    for side, pixel, expected in (('left', 100, -region), ('right', 156, region)):
                        viewer.set_hemisphere(side)
                        viewer.set_selected_region_ids((expected,))
                        viewer._set_hovered_region_ids((expected,))
                        request_id += 1
                        assert query_at(viewer, pixel, 96, request_id) == (True, expected)
                        opposite_pixel = 156 if side == 'left' else 100
                        request_id += 1
                        assert not query_at(viewer, opposite_pixel, 96, request_id)[0]
            assert viewer.mesh_data is source
            assert viewer._surface_state.handle is bank
            np.testing.assert_array_equal(viewer._surface_geometry.fragment_clip, clip)
            np.testing.assert_array_equal(source.positions_um, snapshot)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
