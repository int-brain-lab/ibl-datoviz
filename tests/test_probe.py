import numpy as np
import pytest

from ibl_datoviz import ProbeSites


def test_probe_sites_normalize_and_freeze_arrays():
    sites = ProbeSites.from_arrays(
        [[1, 2, 3], [4, 5, 6]],
        [0.25, np.nan],
        [-315, 0],
        site_ids=[11, 12],
        labels=['site-a', 'site-b'],
    )
    assert sites.positions_um.dtype == np.float32
    assert sites.values.dtype == np.float64
    assert sites.allen_region_ids.dtype == np.int64
    assert sites.site_ids.dtype == np.uint64
    assert sites.labels == ('site-a', 'site-b')
    assert not sites.positions_um.flags.writeable


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
