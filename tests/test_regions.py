import runpy
from pathlib import Path

import numpy as np
import pytest

from ibl_datoviz import AtlasRegionValues

ROOT = Path(__file__).resolve().parents[1]


def test_region_values_validate_and_freeze_arrays():
    data = AtlasRegionValues.from_arrays(
        [-8, 315],
        [2.5, np.nan],
        weights=[3, 4],
        value_name='Mean FR (Hz)',
        weight_name='Sites',
    )
    assert data.allen_region_ids.dtype == np.int64
    assert data.values.dtype == np.float64
    assert data.weights.dtype == np.float64
    assert data.value_name == 'Mean FR (Hz)'
    assert data.weight_name == 'Sites'
    assert not data.values.flags.writeable


@pytest.mark.parametrize(
    ('args', 'kwargs', 'message'),
    [
        (([], []), {}, 'unique nonzero'),
        (([1, 1], [1, 2]), {}, 'unique nonzero'),
        (([0], [1]), {}, 'unique nonzero'),
        (([1], [np.inf]), {}, 'infinities'),
        (([1], [1]), {'weights': [0]}, 'positive for finite'),
    ],
)
def test_region_values_reject_invalid_payload(args, kwargs, message):
    with pytest.raises(ValueError, match=message):
        AtlasRegionValues.from_arrays(*args, **kwargs)


def test_real_bwm_region_summary_is_derived_from_probe_fixture(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'examples'))
    probe_module = runpy.run_path(ROOT / 'examples' / 'bwm_probe.py')
    data, _ = probe_module['_load_fixture'](probe_module['FIXTURE'])
    region_module = runpy.run_path(ROOT / 'examples' / 'bwm_region_activity.py')
    regions = region_module['_aggregate_regions'](data)
    assert len(regions.allen_region_ids) == 7
    assert np.isfinite(regions.values).all()
    assert regions.weights.sum() == 154
    assert regions.value_name == 'Mean site FR (Hz)'
