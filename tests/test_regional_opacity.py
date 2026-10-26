"""Regional alpha changes share the anatomy transaction and retained handle state."""

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer, RegionValues
from tests.test_atlas import FIXTURE, REGIONS, FakeDatoviz


@pytest.fixture
def quantity():
    fake = FakeDatoviz()
    with AtlasViewer(
        AtlasMesh.from_pack(FIXTURE), catalog=open_region_catalog(REGIONS), datoviz=fake
    ) as app:
        payload = RegionValues(
            allen_region_ids=[-8, 8],
            values=[1, 2],
            weights=[1, 1],
            name='Fixture rate',
            units='Hz',
            weight_name='sites',
            frame=app.frame,
            provenance={'aggregation': 'fixture'},
        )
        handle = app.add_region_values(payload, mapping_reduction='weighted_mean')
        yield app, fake, handle


def test_alpha_survives_recolor_mapping_hide_show_and_removal(quantity):
    app, _, handle = quantity
    handle.set_opacity(0.78)
    handle.color_by('value', cmap='diverging', limits=(0, 3))
    app.anatomy.set_mapping('beryl')
    assert handle.opacity == app._region_opacity == 0.78
    handle.set_visible(False)
    assert app._region_opacity is None
    handle.set_opacity(0)
    assert app._region_opacity is None
    handle.set_visible(True)
    assert handle.opacity == app._region_opacity == 0
    handle.set_opacity(None)
    assert handle.opacity is None and app._region_opacity is None
    handle.set_opacity(1)
    handle.remove()
    assert app._region_opacity is None
    with pytest.raises(RuntimeError, match='removed'):
        handle.set_opacity(0.4)


@pytest.mark.parametrize('invalid', [-0.1, 1.1, np.nan, np.inf, True, '0.5', [0.5]])
def test_invalid_alpha_rejected_before_native_calls(quantity, invalid):
    _, fake, handle = quantity
    before = len(fake.calls)
    with pytest.raises(ValueError, match='opacity'):
        handle.set_opacity(invalid)
    assert handle.opacity is None
    assert len(fake.calls) == before


def test_failed_partial_alpha_upload_restores_handle_and_anatomy(quantity, monkeypatch):
    app, fake, handle = quantity
    handle.set_opacity(0.4)
    original = fake.dvz_visual_set_data
    failed = False

    def fail_after_write(*args):
        nonlocal failed
        result = original(*args)
        if not failed:
            failed = True
            return -1
        return result

    monkeypatch.setattr(fake, 'dvz_visual_set_data', fail_after_write)
    with pytest.raises(RuntimeError, match='region scalar color update'):
        handle.set_opacity(0.8)
    assert failed
    assert handle.opacity == app._region_opacity == 0.4
    assert not app._closed
    handle.set_opacity(0.8)
    assert handle.opacity == app._region_opacity == 0.8
