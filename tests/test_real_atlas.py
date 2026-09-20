from __future__ import annotations

import os
from pathlib import Path

import pytest

from ibl_anatomy import (
    bundled_asset_set,
    bundled_registered_asset_set,
    verify_materialized_asset_set,
    verify_materialized_registered_asset_set,
)
from ibl_datoviz import AtlasMesh


@pytest.mark.skipif(
    'IBL_ATLAS_ASSET_SET_ROOT' not in os.environ,
    reason='requires an explicitly materialized real D070 asset set',
)
def test_real_d070_asset_set_matches_native_adapter() -> None:
    assets = verify_materialized_asset_set(
        bundled_asset_set(), Path(os.environ['IBL_ATLAS_ASSET_SET_ROOT'])
    )
    mesh = AtlasMesh.from_geometry(assets.geometry)
    assert mesh.positions.shape == (486_674, 3)
    assert mesh.indices.shape == (2_899_935,)
    assert len(set(mesh.presentation_ids.tolist())) == 1_130
    assert len(set(mesh.face_presentation_ids.tolist())) == 1_130
    assert mesh.positions_um[:, 0].min() < 0 < mesh.positions_um[:, 0].max()


@pytest.mark.skipif(
    'IBL_REGISTERED_ASSET_SET_ROOT' not in os.environ,
    reason='requires an explicitly materialized registered 10 um asset set',
)
def test_real_registered_asset_set_matches_slice_adapter_contract() -> None:
    assets = verify_materialized_registered_asset_set(
        bundled_registered_asset_set(), Path(os.environ['IBL_REGISTERED_ASSET_SET_ROOT'])
    )
    projections = {
        projection.world_slice_axis: projection for projection in assets.projections.values()
    }
    assert assets.pack_id == 'ibl-atlas-projections-05b9f3f85db9'
    assert (assets.file_count, assets.encoded_bytes) == (59, 5_700_497)
    assert set(projections) == {'ap', 'ml', 'dv'}
    assert projections['ap'].slice_shape == (1140, 800)
    assert projections['ml'].slice_shape == (1320, 800)
    assert projections['dv'].slice_shape == (1140, 1320)
