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


@pytest.mark.parametrize('strided', [False, True])
@pytest.mark.parametrize('writeable', [False, True])
def test_region_values_own_all_numeric_storage(strided, writeable):
    inputs = {
        'allen_region_ids': np.array([-8, 315], dtype=np.int64),
        'values': np.array([2.5, np.nan], dtype=np.float64),
        'weights': np.array([3, 4], dtype=np.float64),
    }
    if strided:
        inputs = {name: np.repeat(array, 2)[::2] for name, array in inputs.items()}
    for array in inputs.values():
        array.setflags(write=writeable)
    expected = {name: array.copy() for name, array in inputs.items()}

    data = AtlasRegionValues.from_arrays(**inputs)

    for name, source in inputs.items():
        retained = getattr(data, name)
        assert source.flags.writeable == writeable
        assert not np.shares_memory(source, retained)
        assert retained.dtype == source.dtype
        assert retained.flags.c_contiguous
        assert not retained.flags.writeable
        source.setflags(write=True)
        source[...] = 99
        np.testing.assert_array_equal(retained, expected[name])


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
