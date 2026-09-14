from __future__ import annotations

import os
from pathlib import Path

import pytest

from ibl_atlas_assets import bundled_asset_set, verify_materialized_asset_set
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
