import runpy
from pathlib import Path

import numpy as np
import pytest

from ibl_datoviz import ProbeSites

ROOT = Path(__file__).resolve().parents[1]


def test_probe_sites_normalize_and_freeze_arrays():
    sites = ProbeSites.from_arrays(
        [[1, 2, 3], [4, 5, 6]],
        [0.25, np.nan],
        [-315, 0],
        site_ids=[11, 12],
        labels=['site-a', 'site-b'],
        value_name='Firing rate (Hz)',
    )
    assert sites.positions_um.dtype == np.float32
    assert sites.values.dtype == np.float64
    assert sites.allen_region_ids.dtype == np.int64
    assert sites.site_ids.dtype == np.uint64
    assert sites.labels == ('site-a', 'site-b')
    assert sites.value_name == 'Firing rate (Hz)'
    assert not sites.positions_um.flags.writeable


@pytest.mark.parametrize('strided', [False, True])
@pytest.mark.parametrize('writeable', [False, True])
def test_probe_sites_own_all_numeric_storage(strided, writeable):
    inputs = {
        'positions_um': np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32),
        'values': np.array([0.25, np.nan], dtype=np.float64),
        'allen_region_ids': np.array([-315, 0], dtype=np.int64),
        'site_ids': np.array([11, 12], dtype=np.uint64),
    }
    if strided:
        inputs = {name: np.repeat(array, 2, axis=0)[::2] for name, array in inputs.items()}
    for array in inputs.values():
        array.setflags(write=writeable)
    expected = {name: array.copy() for name, array in inputs.items()}

    sites = ProbeSites.from_arrays(**inputs)

    for name, source in inputs.items():
        retained = getattr(sites, name)
        assert source.flags.writeable == writeable
        assert not np.shares_memory(source, retained)
        assert retained.dtype == source.dtype
        assert retained.flags.c_contiguous
        assert not retained.flags.writeable
        source.setflags(write=True)
        source[...] = 99
        np.testing.assert_array_equal(retained, expected[name])


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [
        ({'positions_um': [], 'values': [], 'allen_region_ids': []}, 'positions'),
        (
            {'positions_um': [[np.inf, 0, 0]], 'values': [1], 'allen_region_ids': [1]},
            'finite',
        ),
        (
            {'positions_um': [[0, 0, 0]], 'values': [np.inf], 'allen_region_ids': [1]},
            'infinities',
        ),
        (
            {'positions_um': [[0, 0, 0]], 'values': [1], 'allen_region_ids': [1.5]},
            'integer array',
        ),
        (
            {
                'positions_um': [[0, 0, 0], [1, 1, 1]],
                'values': [1, 2],
                'allen_region_ids': [1, 2],
                'site_ids': [4, 4],
            },
            'unique positive',
        ),
    ],
)
def test_probe_sites_reject_invalid_payload(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ProbeSites.from_arrays(**kwargs)


def test_real_bwm_probe_fixture_matches_provenance():
    namespace = runpy.run_path(ROOT / 'examples' / 'bwm_probe.py')
    data, provenance = namespace['_load_fixture'](namespace['FIXTURE'])
    assert provenance['dataset'] == {'name': 'bwm_ephys', 'version': '1.1.0'}
    assert provenance['insertion']['pid'] == 'a21bade7-5be7-4a17-a9b9-ddee453e6260'
    assert len(data.site_ids) == 192
    assert np.isfinite(data.values).sum() == 154
    assert data.value_name == 'Mean FR (Hz)'
    assert set(np.unique(data.allen_region_ids)) == {
        -1091,
        -984,
        -771,
        -728,
        -413,
        -354,
        -101,
    }
