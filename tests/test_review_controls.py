"""Shared review preparation and additive retained-viewer controls."""

from pathlib import Path

import numpy as np
import pytest

from examples.review_common import ReviewControls, load_review_slice
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.navigator import SLICE_DISPLAY_AXES, AtlasSliceComposer
from tests.test_atlas import FIXTURE, FakeDatoviz
from tests.test_surface_style import last_colors


@pytest.fixture
def viewer():
    with AtlasViewer(AtlasMesh.from_pack(FIXTURE), datoviz=FakeDatoviz()) as value:
        yield value


def test_surface_layer_toggle_retains_hemispheres_styles_and_selection(viewer):
    viewer.set_hemisphere('left')
    viewer.set_selected_region_ids((-315,))
    camera, panel = viewer.camera_angles, viewer.panel
    viewer.set_surface_visible(False)
    viewer.set_region_opacity(-315, 0.4)
    assert viewer.selected_region_ids() == (-315,)
    viewer.set_mapping('beryl')
    viewer.set_mapping('allen')
    assert not viewer._surface_visible
    assert viewer._surface_style.hemispheres == {'left': True, 'right': False}
    assert viewer.selected_region_ids() == ()  # Existing mapping-reset policy.
    visibility = [call for call in viewer.dvz.calls if call[0] == 'visible']
    assert visibility[-1][2] is False
    viewer.set_surface_visible(True)
    assert viewer.visible_region_ids() == (-315,)
    assert viewer._surface_style.regions[('allen', -315)].opacity == 0.4
    assert viewer.panel is panel and viewer.camera_angles == camera


def test_surface_opacity_failure_restores_public_and_native_state(viewer, monkeypatch):
    viewer.set_selected_region_ids((-315,))
    before = last_colors(viewer.dvz).copy()
    original = viewer.dvz.dvz_visual_set_data
    failed = False

    def fail_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            return -1
        return original(*args)

    monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_data', fail_once)
    with pytest.raises(RuntimeError):
        viewer.set_surface_opacity(0.3)
    assert viewer.surface_opacity == 1
    assert viewer.selected_region_ids() == (-315,)
    np.testing.assert_array_equal(last_colors(viewer.dvz), before)
    viewer.set_surface_opacity(0.3)
    assert viewer.surface_opacity == 0.3


def test_review_reset_is_explicit_and_restores_initial_viewer_state(viewer):
    controls = ReviewControls(viewer)
    panel, scene = viewer.panel, viewer.scene
    viewer.hide_region(-315)
    viewer.set_hemisphere('right')
    viewer.set_surface_opacity(0.2)
    viewer.set_surface_visible(False)
    viewer.set_selected_region_ids((315,))
    viewer.set_camera_angles((1, 0, 0))
    controls.reset()
    assert viewer.panel is panel and viewer.scene is scene
    assert viewer.camera_angles == controls.initial_camera
    assert viewer.visible_region_ids() == (-315, 315)
    assert viewer.surface_opacity == 1 and viewer._surface_visible
    assert not viewer._surface_style.regions and not viewer.selected_region_ids()


@pytest.mark.parametrize('axis', ['ap', 'ml', 'dv'])
@pytest.mark.parametrize('layer', ['anatomy', 'annotation'])
def test_physical_review_slice_matches_oriented_source_pixels_and_affine_edges(axis, layer):
    source = open_volume_pack(
        FIXTURE.parents[1] / 'linked-atlas-v1' / 'volume-pack'
    ).load_volumes()
    composer = AtlasSliceComposer(source, 'allen')
    array_axis = source.grid.array_axes.index(axis)
    index = source.grid.shape[array_axis] // 2
    anatomy, annotation = composer.compose_layers(axis, index, annotation_opacity=1)
    expected = anatomy if layer == 'anatomy' else annotation
    plane = load_review_slice(composer, axis, index, 'allen', layer=layer, opacity=0.5)
    # Continuous anatomy may interpolate; categorical labels must retain exact pixels.
    assert plane.sampling == ('linear' if layer == 'anatomy' else 'nearest')
    np.testing.assert_array_equal(plane.rgba[..., :3], expected[..., :3])
    np.testing.assert_array_equal(plane.rgba[..., 3], np.rint(expected[..., 3] * 0.5))
    affine = np.asarray(source.grid.index_to_world_um_matrix).reshape(4, 4)
    index_corners = np.column_stack((plane.corners_um, np.ones(4))) @ np.linalg.inv(affine).T
    np.testing.assert_allclose(index_corners[:, array_axis], index, atol=1e-5)
    for name in SLICE_DISPLAY_AXES[axis]:
        column = source.grid.array_axes.index(name)
        np.testing.assert_allclose(
            sorted(set(np.round(index_corners[:, column], 5))),
            [-0.5, source.grid.shape[column] - 0.5],
            atol=1e-5,
        )
    assert not plane.rgba.flags.writeable and not plane.corners_um.flags.writeable


@pytest.mark.parametrize('index', [-1, 99999, 1.5, True])
def test_invalid_physical_slice_index_rejected(index):
    with pytest.raises(ValueError, match='index'):
        load_review_slice(
            Path(FIXTURE.parents[1] / 'linked-atlas-v1' / 'volume-pack'), 'ap', index
        )
