from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ibl_datoviz import AtlasViewer, LinkedAtlasNavigator

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / 'ibl-atlas-assets'
    / 'tests'
    / 'fixtures'
    / 'mesh-pack-v1'
    / 'pack'
)
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
            viewer.set_probe([[-1.5, -0.8, -0.8], [0, 0, 0], [2.5, 0.8, 0.8]])
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
        with LinkedAtlasNavigator.from_packs(
            FIXTURE, VOLUME_FIXTURE, width=320, height=240
        ) as navigator:
            navigator.set_cursor(navigator.cursor)
            assert navigator._selected_region_ids == ()
            navigator.select_cursor_region()
            assert navigator.cursor.region(navigator.volumes, 'allen').atlas_id == 315
            assert navigator._selected_region_ids == (315,)
            assert navigator._highlight_region_ids == (315,)
            navigator.select_cursor_region()
            assert navigator._selected_region_ids == ()
            navigator.select_cursor_region()
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
        with LinkedAtlasNavigator.from_anatomy_packs(
            FIXTURE,
            VOLUME_FIXTURE,
            INTENSITY_FIXTURE,
            REGISTERED_FIXTURE / 'anatomy-v2.json',
            width=320,
            height=240,
        ) as navigator:
            assert navigator.slice_resolution_label == '10 um'
            assert navigator.volume_resolution_label == '1 um'
            navigator.set_cursor(navigator.cursor)
            navigator.select_cursor_region()
            rgba = navigator.render_offscreen(output)
    except RuntimeError as error:
        _skip_without_native_datoviz(error)
        raise
    assert rgba.shape == (240, 320, 4)
    assert output.stat().st_size > 0
    assert np.count_nonzero(np.any(rgba[..., :3] != [29, 33, 39], axis=2)) > 200
