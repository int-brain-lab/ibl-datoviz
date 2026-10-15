"""Prepared regional handles reuse native color transactions and exact selection."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasRegionValues, AtlasViewer, Points
from ibl_datoviz.regional_quantities import RegionValues
from tests import FIXTURES
from tests.test_atlas import FIXTURE


@pytest.fixture
def app():
    catalog = open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json')
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=catalog,
        width=640,
        height=480,
        enable_hover=False,
    ) as viewer:
        yield viewer


def quantity(app):
    return RegionValues(
        allen_region_ids=[-997, -8],
        values=[2.0, np.nan],
        weights=[3.0, 9.0],
        name='Prepared rate',
        units='Hz',
        weight_name='neurons',
        frame=app.frame,
        provenance={'source': 'synthetic native integration fixture'},
    )


def test_restore_previous_legacy_scalar_data_in_current_mapping(app):
    previous = AtlasRegionValues.from_arrays([-997, -8], [4.0, 8.0], weights=[1.0, 2.0])
    app.set_region_data(
        previous,
        value_range=(0, 10),
        color_scheme='diverging',
        opacity=0.4,
        mapping_reduction='weighted_mean',
    )
    handle = app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
    assert app.region_data is not previous
    assert app.region_data.value_name == 'Prepared rate [Hz]'
    app.anatomy.set_mapping('beryl')
    handle.set_visible(False)
    assert app.mapping == 'beryl' and app.region_data is previous
    expected = app._display_surface_colors().copy()
    np.testing.assert_array_equal(app._surface_base_colors_cache, expected)
    assert app._region_value_range == (0, 10)
    assert app._region_color_scheme == 'diverging' and app._region_opacity == 0.4
    handle.set_visible(True)
    handle.color_by('value', cmap='diverging', limits=(0, 4))
    handle.remove()
    assert app.region_data is previous and app.mapping == 'beryl'
    np.testing.assert_array_equal(app._surface_base_colors_cache, expected)


def test_clear_to_anatomy_colors_preserves_exact_observation_and_region_selection(app):
    layer = app.add_points(Points((0,), [[0, 0, 0]], app.frame, {}))
    ref = layer.observation(0)
    app.selection.set_observations((ref,))
    app.selection.set_regions((-8,), mapping='allen')
    selection, revision = app.selection.snapshot(), app.selection.revision
    expected = app._display_surface_colors().copy()
    handle = app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
    handle.set_visible(False)
    assert app.region_data is None and app.region_table is None
    np.testing.assert_array_equal(app._surface_base_colors_cache, expected)
    handle.set_visible(True)
    handle.remove()
    assert app.region_data is None and app.region_table is None
    assert app.selection.snapshot() == selection and app.selection.revision == revision
    np.testing.assert_array_equal(app._surface_base_colors_cache, expected)


def test_exclusive_ownership_blocks_second_quantity_and_legacy_setter(app):
    handle = app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
    for visible in (True, False):
        handle.set_visible(visible)
        with pytest.raises(ValueError, match='already attached'):
            app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
        with pytest.raises((ValueError, RuntimeError), match='regional|quantity|attached'):
            app.set_region_data(
                AtlasRegionValues.from_arrays([-8], [42.0]), mapping_reduction='weighted_mean'
            )
    handle.remove()
    app.set_region_data(
        AtlasRegionValues.from_arrays([-8], [42.0]), mapping_reduction='weighted_mean'
    )


@pytest.mark.parametrize('operation', ['color', 'hide', 'remove'])
def test_failed_native_color_upload_preserves_handle_and_anatomy_state(
    app, monkeypatch, operation
):
    handle = app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
    before_data = app.region_data
    before_colors = app._surface_base_colors_cache.copy()
    before_selection = app.selection.snapshot()
    original = app.dvz.dvz_visual_set_data
    fail_once = True

    def upload(visual, field, data):
        nonlocal fail_once
        if field == 'color' and fail_once:
            fail_once = False
            return -1
        return original(visual, field, data)

    monkeypatch.setattr(app.dvz, 'dvz_visual_set_data', upload)
    with pytest.raises(RuntimeError):
        if operation == 'color':
            handle.color_by('value', cmap='diverging', limits=(0, 4))
        elif operation == 'hide':
            handle.set_visible(False)
        else:
            handle.remove()
    assert not app._closed and not handle._closed and handle.visible
    assert app._regional_quantities.handle is handle
    assert handle.cmap == 'sequential' and handle.limits is None
    assert app.region_data is before_data
    assert app.selection.snapshot() == before_selection
    np.testing.assert_array_equal(app._surface_base_colors_cache, before_colors)


def test_coverage_read_is_allowed_in_committed_callbacks_and_rejects_foreign_threads(app):
    handle = app.add_region_values(quantity(app), mapping_reduction='weighted_mean')
    seen = []
    app.selection.on_changed(lambda _event: seen.append(handle.mapped()))
    app.selection.set_regions((-8,), mapping='allen')
    assert not app.selection.callback_errors
    assert seen[0].mapping == 'allen'
    assert seen[0].declared_weights.tolist() == [3.0, 9.0]
    assert seen[0].finite_weights.tolist() == [3.0, 0.0]
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handle.mapped)
        with pytest.raises(RuntimeError, match='owning thread'):
            future.result()
    app.close()
    assert handle._closed
    with pytest.raises(RuntimeError, match='closed'):
        handle.mapped()
