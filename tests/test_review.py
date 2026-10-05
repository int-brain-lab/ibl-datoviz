import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import review


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / 'Datoviz checkout'
    (root / 'datoviz').mkdir(parents=True)
    (root / 'datoviz' / '__init__.py').touch()
    library = root / 'build' / 'src' / 'libdatoviz.dylib'
    library.parent.mkdir(parents=True)
    library.touch()
    monkeypatch.delenv('DATOVIZ_LIBRARY', raising=False)
    monkeypatch.setattr(review.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(review, 'source_pin', lambda _name: 'tested-revision')
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'tested-revision')
    return root, library


def test_runtime_detects_mac_pairing_and_preserves_existing_environment(checkout, monkeypatch):
    root, library = checkout
    monkeypatch.setenv('PYTHONPATH', '/existing/path')
    monkeypatch.setenv('VULKAN_SDK', '/configured/sdk')
    prefix, environment, detected = review.runtime(root)
    assert prefix == []
    assert detected == library
    assert environment['DATOVIZ_LIBRARY'] == str(library)
    assert environment['PYTHONPATH'].split(review.os.pathsep) == [
        str(review.REPOSITORY),
        str(root),
        '/existing/path',
    ]
    assert environment['VULKAN_SDK'] == '/configured/sdk'
    assert environment['IBL_ANATOMY_FIXTURE_ROOT'] == str(review.ANATOMY / 'tests' / 'fixtures')


def test_runtime_rejects_wrong_source_revision(checkout, monkeypatch):
    root, _library = checkout
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'another-revision')
    with pytest.raises(ValueError, match='this source snapshot tests'):
        review.runtime(root)


def test_doctor_rejects_native_loader_fallback(checkout, monkeypatch):
    root, _library = checkout
    monkeypatch.setattr(
        review.subprocess,
        'run',
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps([str(root / 'datoviz' / '__init__.py'), '/stale/library.dylib'])
        ),
    )
    with pytest.raises(ValueError, match='Unexpected loaded library'):
        review.doctor(root)


def test_direnv_wraps_native_commands_without_auto_allow(checkout, monkeypatch):
    root, _library = checkout
    (root / '.envrc').touch()
    monkeypatch.setattr(review.shutil, 'which', lambda _name: '/bin/direnv')
    prefix, _environment, _library = review.runtime(root)
    assert prefix == ['direnv', 'exec', str(root)]


def test_download_verified_cache_needs_no_network(tmp_path, monkeypatch):
    destination = tmp_path / 'cached.nrrd'
    destination.write_bytes(b'correct')
    expected = review.hashlib.sha256(b'correct').hexdigest()

    def unexpected(*_args, **_kwargs):
        raise AssertionError('verified cache was downloaded again')

    monkeypatch.setattr(review, 'urlopen', unexpected)
    review.download('https://example.test/data', destination, expected)
    destination.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Cached source'):
        review.download('https://example.test/data', destination, expected)


def test_download_failed_hash_never_publishes_or_leaves_partial_file(tmp_path, monkeypatch):
    destination = tmp_path / 'download.nrrd'
    monkeypatch.setattr(review, 'urlopen', lambda *_args, **_kwargs: io.BytesIO(b'wrong'))
    with pytest.raises(ValueError, match='wrong SHA256'):
        review.download('https://example.test/data', destination, 'incorrect')
    assert list(tmp_path.iterdir()) == []


def test_setup_failure_preserves_previous_configuration(tmp_path, monkeypatch):
    config = tmp_path / 'config.json'
    config.write_text('{"datoviz": "previous"}')
    monkeypatch.setattr(review, 'CONFIG', config)
    monkeypatch.setattr(review, 'doctor', lambda *_args: None)
    monkeypatch.setattr(review, 'prepare_anatomy', lambda: None)

    def failure():
        raise ValueError('bad downloaded asset')

    monkeypatch.setattr(review, 'prepare_assets', failure)
    monkeypatch.setattr(review.sys, 'argv', ['review.py', 'setup', '--datoviz', str(tmp_path)])
    assert review.main() == 1
    assert config.read_text() == '{"datoviz": "previous"}'


def test_run_all_uses_separate_processes_and_stops_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'configured_checkout', lambda: tmp_path)
    monkeypatch.setattr(review, 'doctor', lambda _root: ([], {'runtime': 'configured'}))
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    commands = []

    def run(command, **kwargs):
        assert kwargs['env'] == {'runtime': 'configured'}
        commands.append(command)
        if len(commands) == 2:
            raise review.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(review, 'run', run)
    monkeypatch.setattr(review.sys, 'argv', ['review.py', 'run', '--frames', '3'])
    assert review.main() == 1
    assert len(commands) == 2
    assert Path(commands[0][1]).name == 'real_atlas_surface.py'
    assert Path(commands[1][1]).name == 'atlas_mapping_switch.py'
    assert commands[0][-2:] == ['--frames', 3]
