"""Native retained-view checks for both fixed-layout review applications."""

import numpy as np

from examples.linked_atlas_review import SLICE_REPRESENTATIONS, LinkedAtlasReview
from examples.review_common import load_review_slice
from examples.scientific_scene_review import ScientificSceneReview
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasMesh
from ibl_datoviz.components import ProbeSites
from tests.test_atlas import FIXTURE
from tests.test_smoke import _skip_without_native_datoviz


def render(viewer):
    assert viewer.dvz.dvz_view_render_once(viewer.view) == 0
    return np.array(viewer.dvz.dvz_view_capture_rgba(viewer.view), copy=True)


def test_native_scientific_review_changes_layers_in_one_scene_and_view():
    source = FIXTURE.parents[1] / 'linked-atlas-v1' / 'volume-pack'
    volumes = open_volume_pack(source).load_volumes()
    sites = ProbeSites.from_arrays(
        [[-1, 0, 0], [0, 0, 0], [1, 0, 0]], [1, 5, np.nan], [-315, 315, 315]
    )
    try:
        with ScientificSceneReview(
            AtlasMesh.from_pack(FIXTURE),
            catalog=volumes.regions,
            width=320,
            height=240,
            surface_opacity=0.2,
        ) as viewer:
            viewer.configure_review(sites, load_review_slice(source, 'ap'))
            viewer.apply_preset('atlas')
            viewer._create_view(offscreen=True, title='Scientific review regression')
            handles = (viewer.scene, viewer.figure, viewer.panel, viewer.app, viewer.view)
            baseline = render(viewer)
            for preset in ('single-probe', 'mixed', 'atlas'):
                viewer.apply_preset(preset)
                pixels = render(viewer)
                assert all(
                    before is after
                    for before, after in zip(
                        handles,
                        (viewer.scene, viewer.figure, viewer.panel, viewer.app, viewer.view),
                        strict=True,
                    )
                )
                assert pixels.shape == baseline.shape
            np.testing.assert_array_equal(pixels, baseline)
            viewer.apply_preset('mixed')
            viewer.set_point_mode('uniform')
            viewer.set_point_opacity(0.3)
            viewer.set_plane_mode('mask', cutoff=0.4)
            render(viewer)
            viewer.set_layer_visible('plane', False)
            viewer.set_layer_visible('points', False)
            viewer.set_layer_visible('insertions', False)
            np.testing.assert_array_equal(render(viewer), baseline)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise


def test_native_linked_review_retains_all_four_panels_while_updating_layers():
    volumes = open_volume_pack(
        FIXTURE.parents[1] / 'linked-atlas-v1' / 'volume-pack'
    ).load_volumes()
    try:
        with LinkedAtlasReview(
            AtlasMesh.from_pack(FIXTURE), volumes, width=320, height=240
        ) as viewer:
            viewer._create_view(offscreen=True, title='Linked review regression')
            panels = tuple(viewer._linked.slice_panels.values())
            handles = (viewer.scene, viewer.figure, viewer.panel, viewer.app, viewer.view, *panels)
            baseline = render(viewer)
            # Drawing a zero-opacity volume must not change the hidden-volume result.
            assert viewer._linked.volume_opacity == 0
            assert viewer.dvz.dvz_visual_set_visible(viewer._linked.volume, True) == 0
            np.testing.assert_array_equal(render(viewer), baseline)
            viewer.set_volume_opacity(0.1)
            render(viewer)
            viewer._linked.set_volume_opacity(0)
            np.testing.assert_array_equal(render(viewer), baseline)
            for preset in ('labels', 'physical-slice', 'volume-context', 'anatomy', 'overlay'):
                viewer.apply_preset(preset)
                pixels = render(viewer)
                current = (
                    viewer.scene,
                    viewer.figure,
                    viewer.panel,
                    viewer.app,
                    viewer.view,
                    *viewer._linked.slice_panels.values(),
                )
                assert all(before is after for before, after in zip(handles, current, strict=True))
                assert pixels.shape == baseline.shape
            np.testing.assert_array_equal(pixels, baseline)
            cursor = viewer._linked.cursor
            for _, (anatomy, annotations, boundaries) in SLICE_REPRESENTATIONS:
                viewer._linked.set_slice_layers(
                    anatomy=anatomy, annotations=annotations, boundaries=boundaries
                )
                pixels = render(viewer)
                assert viewer._linked.cursor == cursor
                if not annotations:
                    assert np.any(pixels != baseline)
            viewer.apply_preset('physical-slice')
            viewer.configure_physical_plane(axis='ml', layer='annotation', mode='mask', cutoff=0.4)
            viewer._linked.set_cursor(
                viewer._linked.cursor.replace('ml', 0, viewer._linked.slice_source.grid.shape)
            )
            render(viewer)
            viewer.set_volume_opacity(0.1)
            assert not viewer.plane_visible
            render(viewer)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
