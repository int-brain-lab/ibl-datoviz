from __future__ import annotations

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasViewer
from ibl_datoviz.components import ProbeSites
from tests import FIXTURES

FIXTURE = FIXTURES / 'mesh-pack-v1' / 'pack'
VOLUME_FIXTURE = FIXTURE.parents[1] / 'linked-atlas-v1' / 'volume-pack'
INTENSITY_FIXTURE = FIXTURE.parents[1] / 'intensity-blocks-v1' / 'pack'
REGISTERED_FIXTURE = FIXTURE.parents[1] / 'linked-registered-slices-v1' / 'pack'


def _skip_without_native_datoviz(error: RuntimeError) -> None:
    if 'dvz_app() failed' in str(error) or 'Unable to load libdatoviz' in str(error):
        pytest.skip('Datoviz native runtime or GPU context is unavailable')


def test_offscreen_atlas_smoke(tmp_path):
    output = tmp_path / 'atlas.png'
    try:
        with AtlasViewer.from_pack(FIXTURE, width=256, height=192) as viewer:
            viewer._probe_presentation.set_path([[-1.5, -0.8, -0.8], [0, 0, 0], [2.5, 0.8, 0.8]])
            rgba = viewer.render_offscreen(output)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (192, 256, 4)
    assert rgba.dtype == np.uint8
    assert output.stat().st_size > 0
    assert np.count_nonzero(np.any(rgba[..., :3] != [29, 33, 39], axis=2)) > 40


def test_offscreen_linked_atlas_smoke(tmp_path):
    output = tmp_path / 'linked-atlas.png'
    try:
        with AtlasViewer.from_packs(FIXTURE, VOLUME_FIXTURE, width=320, height=240) as navigator:
            navigator._linked.set_cursor(navigator._linked.cursor)
            assert navigator._selected_region_ids == ()
            navigator._linked.select_cursor_region()
            assert (
                navigator._linked.cursor.region(navigator._linked.volumes, 'allen').atlas_id == 315
            )
            assert navigator._selected_region_ids == (315,)
            assert navigator._highlight_region_ids == (315,)
            navigator._linked.select_cursor_region()
            assert navigator._selected_region_ids == ()
            navigator._linked.select_cursor_region()
            rgba = navigator.render_offscreen(output)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (240, 320, 4)
    assert output.stat().st_size > 0
    assert np.count_nonzero(np.any(rgba[..., :3] != [29, 33, 39], axis=2)) > 200


def test_offscreen_multiresolution_atlas_smoke(tmp_path):
    output = tmp_path / 'multiresolution-atlas.png'
    try:
        with AtlasViewer.from_anatomy_packs(
            FIXTURE,
            VOLUME_FIXTURE,
            INTENSITY_FIXTURE,
            REGISTERED_FIXTURE / 'anatomy-v2.json',
            width=320,
            height=240,
        ) as navigator:
            assert navigator._linked.slice_resolution_label == '10 um'
            assert navigator._linked.volume_resolution_label == '1 um'
            navigator._linked.set_cursor(navigator._linked.cursor)
            navigator._linked.select_cursor_region()
            rgba = navigator.render_offscreen(output)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (240, 320, 4)
    assert output.stat().st_size > 0
    assert np.count_nonzero(np.any(rgba[..., :3] != [29, 33, 39], axis=2)) > 200


def test_offscreen_probe_sites_replacement(tmp_path):
    catalog = open_region_catalog(FIXTURE.parents[1] / 'atlas-regions-v1' / 'regions.json')
    data = ProbeSites.from_arrays([[-1, 0, 0], [1, 0, 0]], [1, 2], [-8, 8])
    try:
        with AtlasViewer.from_pack(FIXTURE, catalog=catalog, width=256, height=192) as viewer:
            viewer._probe_presentation.set_data(data)
            viewer._probe_presentation.set_sites([[0, 0, 0]])
            viewer.set_mapping('beryl')
            assert viewer._probe_presentation.data is None
            viewer.set_mapping('allen')
            viewer._probe_presentation.set_data(data)
            rgba = viewer.render_offscreen(tmp_path / 'probe-sites.png')
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (192, 256, 4)
    assert np.count_nonzero(np.any(rgba[..., :3] != [29, 33, 39], axis=2)) > 40


def test_offscreen_linked_boundaries_mapping_empty_and_restore(tmp_path):
    output = tmp_path / 'boundaries-restored.png'
    try:
        # Beryl collapses this fixture's boundaries, including initial creation.
        with AtlasViewer.from_packs(
            FIXTURE, VOLUME_FIXTURE, mapping='beryl', width=320, height=240
        ) as navigator:
            for axis in ('ap', 'ml', 'dv'):
                assert len(navigator._linked._boundary_positions(axis)[0]) == 0
                navigator._linked._refresh_boundaries(axis)
            navigator.render_offscreen()
            navigator.set_mapping('allen')
            assert len(navigator._linked._boundary_positions('dv')[0]) > 0
            navigator._check(navigator.dvz.dvz_view_render_once(navigator.view), 'Allen render')
            navigator.set_mapping('beryl')
            navigator._linked._refresh_boundaries('dv')
            navigator._check(navigator.dvz.dvz_view_render_once(navigator.view), 'Beryl render')
            navigator.set_mapping('allen')
            navigator._check(navigator.dvz.dvz_view_render_once(navigator.view), 'restored render')
            rgba = np.array(navigator.dvz.dvz_view_capture_rgba(navigator.view), copy=True)
            navigator._check(
                navigator.dvz.dvz_view_capture_png(navigator.view, str(output).encode()),
                'restored capture',
            )
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (240, 320, 4)
    assert output.stat().st_size > 0
