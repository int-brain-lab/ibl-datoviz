"""The review client presents the hash-checked fixture without new aggregation."""

from types import SimpleNamespace

import numpy as np

from examples.bwm_probe import FIXTURE, _load_fixture
from examples.scientific_scalar_review import ScalarReview
from ibl_datoviz import WorldFrame


def test_scalar_review_preserves_fixture_values_ids_source_and_missing_meaning():
    sites, provenance = _load_fixture(FIXTURE)
    encodings, tables = [], []

    class Layer:
        def __init__(self, payload):
            self.payload = payload

        def set_size_px(self, value):
            assert value == 12

        def color_by(self, values, **options):
            encodings.append((np.array(values, copy=True), options))

    app = SimpleNamespace(
        frame=WorldFrame('test'),
        add_points=lambda payload, **_options: Layer(payload),
        tables=SimpleNamespace(show=tables.append),
    )
    app.encode_values = lambda: ScalarReview.encode_values(app)
    ScalarReview.configure(app, sites, provenance)
    payload = app.site_layer.payload
    assert payload.ids == tuple(sites.site_ids)
    np.testing.assert_equal(payload.positions_um, sites.positions_um)
    np.testing.assert_equal(payload.allen_region_ids, sites.allen_region_ids)
    np.testing.assert_equal(encodings[0][0], sites.values)
    options = encodings[0][1]
    assert options['units'] == 'Hz' and options['cmap'] == 'viridis'
    assert options['observation_refs'] == payload.observation_keys
    np.testing.assert_allclose(options['limits'], np.nanquantile(sites.values, [0.05, 0.95]))
    assert all(
        key.original_id == site
        for key, site in zip(payload.observation_keys, sites.site_ids, strict=True)
    )
    assert all(
        key.source.content_sha256 == provenance['artifact']['sha256']
        for key in payload.observation_keys
    )
    assert 'no good unit' in payload.provenance['scalar_missing_meaning']
    assert tables == []  # Data is opened on demand, not imposed on startup.
