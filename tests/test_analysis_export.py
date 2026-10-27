"""Analysis exports preserve exact scientific scope, typed IDs and missing rows."""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import (
    AtlasMesh,
    AtlasViewer,
    Paths,
    Points,
    Sites,
    SourceKey,
    SourceObservationKey,
)
from tests import FIXTURES
from tests.test_atlas import FIXTURE


@pytest.fixture
def app(native_datoviz):
    with AtlasViewer(
        atlas=AtlasMesh.from_pack(FIXTURE),
        catalog=open_region_catalog(FIXTURES / 'linked-atlas-v1/volume-pack/regions.json'),
        width=960, height=720, enable_hover=False,
    ) as viewer:
        yield viewer


def source_layer(app, recording='first'):
    source = SourceKey('IBL', 'fixture', '1', 'a' * 64)
    keys = tuple(SourceObservationKey(source, recording, 'clusters', key) for key in (0, '0'))
    layer = app.add_points(Points(
        (0, '0'), [[0, 0, 0], [np.nan, 1, 2]], app.frame,
        {'position_meaning': 'fixture', 'notes': ['original']}, keys,
        allen_region_ids=np.array([-315, 0]),
    ), name='Cluster <values>')
    layer.color_by(
        [2.125, np.nan], name='Rate', units='Hz', cmap='viridis', limits=(1, 3),
        observation_refs=keys,
    )
    return layer


def test_records_keep_order_typed_ids_source_scope_missingness_and_hidden_rows(app, tmp_path):
    first, second = source_layer(app), source_layer(app, 'second')
    refs = (second.refs[0], first.refs[1], first.refs[0])
    app.selection.set_observations(refs)
    first.set_visible(False)
    first.set_color('#eeeeee')
    revision = app.selection.revision
    records = app.selection.to_records()
    assert [row['original_id'] for row in records] == [0, '0', 0]
    assert [row['original_id_type'] for row in records] == ['int', 'str', 'int']
    assert [row['source_key']['recording_id'] for row in records] == ['second', 'first', 'first']
    assert records[1]['position_um'] == [None, 1.0, 2.0]
    assert records[1]['positioned'] is False
    assert records[1]['measurement'] == {
        'name': 'Rate', 'units': 'Hz', 'value': None, 'status': 'missing',
    }
    assert records[2]['measurement']['value'] == 2.125
    assert records[2]['allen_region_id'] == -315
    assert records[2]['effective_visible'] is False
    records[2]['provenance']['notes'].append('changed')
    assert first.payload.provenance['notes'] == ('original',)
    path = app.selection.export_json(tmp_path / 'nested' / 'selection.json')
    document = json.loads(path.read_text())
    assert document['schema'] == 'ibl-datoviz-selection-v1'
    assert document['observations'][2]['provenance']['notes'] == ['original']
    assert app.selection.revision == revision and app.selection.observations == refs


def test_failed_atomic_selection_write_preserves_previous_file(app, tmp_path, monkeypatch):
    from ibl_datoviz import analysis_export  # noqa: PLC0415

    path = app.selection.export_json(tmp_path / 'selection.json')
    previous = path.read_bytes()
    layer = source_layer(app)
    app.selection.set_observations((layer.refs[0],))

    def fail_replace(*_args):
        raise OSError('fixture replacement failure')

    monkeypatch.setattr(analysis_export.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='replacement'):
        app.selection.export_json(path)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


def test_callback_can_export_committed_rows_and_subscription_closes(app, tmp_path):
    layer = source_layer(app)
    path = tmp_path / 'live.json'
    subscription = app.selection.on_changed(lambda _event: app.selection.export_json(path))
    app.selection.set_observations((layer.refs[1],))
    assert app.selection.callback_errors == ()
    assert json.loads(path.read_text())['observations'][0]['original_id'] == '0'
    subscription.close()
    app.selection.clear()
    assert len(json.loads(path.read_text())['observations']) == 1
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match='owning thread'),
    ):
        pool.submit(app.selection.to_records).result()
    app.close()
    with pytest.raises(RuntimeError, match='closed'):
        app.selection.to_records()


def test_unscoped_paths_and_site_memberships_do_not_invent_source_ids(app, tmp_path):
    path = app.add_paths(Paths(('line',), ([[0, 0, 0], [1, 2, 3]],), app.frame, {}))
    key = SourceObservationKey(SourceKey('IBL', 'fixture', '1', 'b' * 64), 'pid', 'channels', 0)
    site = app.add_points(Sites((0,), [[0, 0, 0]], app.frame, {}, memberships=((key,),)))
    app.selection.set_observations((path.refs[0], site.refs[0]))
    rows = app.selection.to_records()
    assert rows[0]['source_key'] is None and rows[0]['measurement'] is None
    assert rows[0]['position_um'] == [[0, 0, 0], [1, 2, 3]]
    assert rows[1]['memberships'][0]['original_id'] == 0
    app.selection.clear()
    app.selection.set_regions((-315,), mapping='allen')
    document = json.loads(app.selection.export_json(tmp_path / 'regions.json').read_text())
    assert document['regions'] == [{'mapping': 'allen', 'signed_region_id': -315}]
    assert document['observations'] == []


def test_figure_bundle_has_embedded_image_legend_and_exact_source_receipt(app, tmp_path):
    layer = source_layer(app)
    app.selection.set_observations((layer.refs[0], layer.refs[1]))
    before = app.selection.snapshot()
    bundle = app.export_figure(tmp_path / 'figure', title='Rates < & >')
    assert app.selection.snapshot() == before
    root = ET.fromstring((bundle / 'figure.svg').read_text())
    texts = ''.join(root.itertext())
    assert 'Rates < & >' in texts and 'Rate (Hz)' in texts and '1 missing' in texts
    image = root.find('{http://www.w3.org/2000/svg}g/{http://www.w3.org/2000/svg}image')
    assert image.attrib['{http://www.w3.org/1999/xlink}href'].startswith('data:image/png;base64,')
    receipt = json.loads((bundle / 'provenance.json').read_text())
    assert receipt['image_size_px'] == [960, 720]
    assert receipt['selected_observations'][1]['original_id'] == '0'
    assert receipt['layers'][0]['source_keys'][0]['recording_id'] == 'first'
    assert receipt['layers'][0]['measurement']['missing'] == 1
    assert receipt['layers'][0]['measurement']['values_sha256'] == hashlib.sha256(
        layer.scalar_data.values.tobytes()
    ).hexdigest()
    for name, digest in receipt['files'].items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == digest
    with pytest.raises(RuntimeError, match='fresh viewer'):
        app.export_figure(tmp_path / 'again')


def test_figure_rejects_existing_directory_and_invalid_title_before_native_creation(app, tmp_path):
    with pytest.raises(FileExistsError):
        app.export_figure(tmp_path)
    with pytest.raises(ValueError, match='title'):
        app.export_figure(tmp_path / 'new', title='')
    assert app.app is None and not (tmp_path / 'new').exists()


def test_failed_native_figure_capture_does_not_publish_bundle(app, tmp_path, monkeypatch):
    monkeypatch.setattr(app.dvz, 'dvz_view_capture_png', lambda *_args: -1)
    with pytest.raises(RuntimeError, match='PNG capture'):
        app.export_figure(tmp_path / 'failed')
    assert not (tmp_path / 'failed').exists()


def test_analysis_example_exports_actual_fixture_ids_and_missingness(
    native_datoviz, tmp_path, monkeypatch
):
    from examples import analysis_roundtrip as client  # noqa: PLC0415

    monkeypatch.setattr(client, 'prepare_viewer', lambda _args: {
        'atlas': AtlasMesh.from_pack(FIXTURE),
        'catalog': open_region_catalog(FIXTURES / 'linked-atlas-v1/volume-pack/regions.json'),
        'width': 640, 'height': 480, 'enable_hover': False,
    })
    monkeypatch.setattr(sys, 'argv', [
        'analysis-roundtrip', str(tmp_path), '--output', str(tmp_path / 'analysis'),
        '--select-site', '383', '--select-site', '381',
        '--figure-dir', str(tmp_path / 'figure'),
        '--report', str(tmp_path / 'report.json'),
    ])
    client.main()
    records = json.loads((tmp_path / 'analysis/selection.json').read_text())['observations']
    assert [row['original_id'] for row in records] == [383, 381]
    assert records[0]['measurement']['value'] is None
    assert records[1]['measurement']['value'] == 7.617520014444987
    assert all(row['source_key']['population'] == 'co-located-channel-groups' for row in records)
    receipt = json.loads((tmp_path / 'figure/provenance.json').read_text())
    assert receipt['selected_observations'] == records
    report = json.loads((tmp_path / 'report.json').read_text())
    assert report['selection_changes'] == [{'revision': 1, 'count': 2}]
