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


def test_runtime_warns_and_uses_local_checkout(checkout, monkeypatch, capsys):
    root, library = checkout
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'another-revision')
    _prefix, environment, detected = review.runtime(root)
    assert detected == library
    assert environment['PYTHONPATH'].split(review.os.pathsep)[1] == str(root)
    output = capsys.readouterr()
    assert 'Datoviz checkout revision: another-revision' in output.out
    assert 'Pinned revision: tested-revision' in output.out
    assert 'Warning:' in output.err
    assert 'Continuing with the local checkout' in output.err


def test_runtime_rejects_wrong_source_revision_in_strict_mode(checkout, monkeypatch):
    root, _library = checkout
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'another-revision')
    with pytest.raises(ValueError, match='this source snapshot tests'):
        review.runtime(root, strict=True)


def test_runtime_accepts_matching_revision_in_strict_mode(checkout, capsys):
    root, library = checkout
    assert review.runtime(root, strict=True)[2] == library
    assert not capsys.readouterr().err


def test_doctor_rejects_wrong_facade_even_with_unpinned_checkout(checkout, monkeypatch):
    root, library = checkout
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'another-revision')
    monkeypatch.setattr(
        review.subprocess,
        'run',
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps(['/stale/datoviz/__init__.py', str(library)])
        ),
    )
    with pytest.raises(ValueError, match='Unexpected imported Datoviz module'):
        review.doctor(root)


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
    monkeypatch.setattr(review, 'doctor', lambda _root, **_kwargs: ([], {'runtime': 'configured'}))
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    commands = []

    def run(command, **kwargs):
        assert kwargs['env'] == {
            'runtime': 'configured',
            'DVZ_WINDOW_INSTANCE': 'datoviz-automated',
        }
        commands.append(command)
        if len(commands) == 2:
            raise review.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(review, 'run', run)
    monkeypatch.setattr(
        review.sys, 'argv', ['review.py', 'run', 'all', '--frames', '3', '--ui-scale', '1.5']
    )
    assert review.main() == 1
    assert len(commands) == 2
    assert Path(commands[0][1]).name == 'scientific_scene_review.py'
    assert Path(commands[1][1]).name == 'linked_atlas_review.py'
    assert commands[0][-4:] == ['--frames', 3, '--ui-scale', 1.5]


def test_offscreen_review_requires_one_example_and_preserves_spaced_path(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    commands = []
    monkeypatch.setattr(review, 'run', lambda command, **_kwargs: commands.append(command))
    output = tmp_path / 'review with spaces.png'
    args = SimpleNamespace(example='all', frames=3, ui_scale=1.0, offscreen=output)
    with pytest.raises(ValueError, match='one named example'):
        review.run_examples(args, [], {})
    assert not commands
    args.example = 'volume-free'
    review.run_examples(args, [], {})
    assert commands[0][-2:] == ['--offscreen', output]


@pytest.mark.parametrize('command', ['doctor', 'test', 'run'])
def test_strict_commands_reject_revision_before_launch(checkout, monkeypatch, command):
    root, _library = checkout
    monkeypatch.setattr(review, 'configured_checkout', lambda: root)
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'another-revision')
    monkeypatch.setattr(review.sys, 'argv', ['review.py', command, '--strict'])
    assert review.main() == 1


@pytest.mark.parametrize('frames,instance', [(0, 'datoviz'), (3, 'datoviz-automated')])
def test_review_window_identity_distinguishes_manual_and_bounded_runs(
    tmp_path, monkeypatch, frames, instance
):
    monkeypatch.setattr(review, 'configured_checkout', lambda: tmp_path)
    monkeypatch.setattr(
        review,
        'doctor',
        lambda _root, **_kwargs: ([], {'DVZ_WINDOW_INSTANCE': 'inherited-instance'}),
    )
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    launched = []
    monkeypatch.setattr(
        review, 'run', lambda _command, **kwargs: launched.append(kwargs['env'].copy())
    )
    monkeypatch.setattr(
        review.sys, 'argv', ['review.py', 'run', 'picking', '--frames', str(frames)]
    )
    assert review.main() == 0
    assert launched == [{'DVZ_WINDOW_INSTANCE': instance}]


@pytest.mark.parametrize('strict', [False, True])
def test_recipe_test_arguments_preserve_pytest_expression(tmp_path, monkeypatch, strict):
    monkeypatch.setattr(review, 'configured_checkout', lambda: tmp_path)
    (tmp_path / 'tests' / 'fixtures').mkdir(parents=True)
    monkeypatch.setattr(review, 'ANATOMY', tmp_path)
    monkeypatch.setattr(review, 'git_revision', lambda _root: 'anatomy-revision')
    monkeypatch.setattr(review, 'source_pin', lambda _name: 'anatomy-revision')
    checked = []
    launched = []

    def doctor(_root, *, strict=False):
        checked.append(strict)
        return [], {}

    monkeypatch.setattr(review, 'doctor', doctor)

    def run(command, **kwargs):
        assert kwargs['env']['DVZ_WINDOW_INSTANCE'] == 'datoviz-automated'
        launched.append(command)

    monkeypatch.setattr(review, 'run', run)
    pytest_args = ['tests/test_probe.py', '-q', '-k', 'ownership or copied']
    monkeypatch.setattr(
        review.sys,
        'argv',
        ['review.py', 'test', '--', *(['--strict'] if strict else []), *pytest_args],
    )
    assert review.main() == 0
    assert checked == [strict]
    assert launched == [[review.sys.executable, '-m', 'pytest', *pytest_args]]


def test_benchmark_uses_remembered_assets_and_preserves_arguments(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'configured_checkout', lambda: tmp_path)
    monkeypatch.setattr(review, 'doctor', lambda _root, **_kwargs: (['runtime'], {}))
    monkeypatch.setattr(review, 'ASSETS', tmp_path / 'assets with spaces')
    review.ASSETS.mkdir()
    launched = []
    monkeypatch.setattr(
        review, 'run', lambda command, **kwargs: launched.append((command, kwargs['env']))
    )
    arguments = ['--scenarios', 'gui_pointer_hover', '--json', 'build/report with spaces.json']
    monkeypatch.setattr(review.sys, 'argv', ['review.py', 'benchmark', '--', *arguments])
    assert review.main() == 0
    command, environment = launched[0]
    assert command == [
        'runtime',
        review.sys.executable,
        review.REPOSITORY / 'tools' / 'benchmark_atlas_3d.py',
        review.ASSETS / 'mesh-pack',
        '--regions',
        review.ASSETS / 'regions.json',
        *arguments,
    ]
    assert environment['DVZ_WINDOW_INSTANCE'] == 'datoviz-automated'


@pytest.mark.parametrize(
    'choice,script', [('1', 'scientific_scene_review.py'), ('2', 'linked_atlas_review.py')]
)
def test_numbered_apps_dispatch_one_fixed_layout(tmp_path, monkeypatch, choice, script):
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    commands = []
    monkeypatch.setattr(review, 'run', lambda command, **_kwargs: commands.append(command))
    args = SimpleNamespace(example=choice, frames=3, ui_scale=1.5, offscreen=None, preset=None)
    review.run_examples(args, [], {})
    assert len(commands) == 1 and Path(commands[0][1]).name == script
    assert commands[0][-4:] == ['--frames', 3, '--ui-scale', 1.5]


def test_default_review_opens_only_app_one(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    monkeypatch.setattr(review, 'configured_checkout', lambda: tmp_path)
    monkeypatch.setattr(review, 'doctor', lambda *_args, **_kwargs: ([], {}))
    commands = []
    monkeypatch.setattr(review, 'run', lambda command, **_kwargs: commands.append(command))
    monkeypatch.setattr(review.sys, 'argv', ['review.py', 'run'])
    assert review.main() == 0
    assert len(commands) == 1 and Path(commands[0][1]).name == 'scientific_scene_review.py'


def test_numbered_preset_and_spaced_capture_path_forward_without_shell(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    commands = []
    monkeypatch.setattr(review, 'run', lambda command, **_kwargs: commands.append(command))
    output = tmp_path / 'mixed scene.png'
    args = SimpleNamespace(example='1', preset='mixed', frames=0, ui_scale=1.0, offscreen=output)
    review.run_examples(args, [], {})
    assert commands[0][4:6] == ['--preset', 'mixed']
    assert commands[0][-2:] == ['--offscreen', output]


@pytest.mark.parametrize('choice', ['all', 'surface'])
def test_preset_requires_one_numbered_app(tmp_path, monkeypatch, choice):
    monkeypatch.setattr(review, 'ASSETS', tmp_path)
    monkeypatch.setattr(review, 'VOLUME', tmp_path)
    monkeypatch.setattr(review, 'run', lambda *_args, **_kwargs: pytest.fail('unexpected launch'))
    with pytest.raises(ValueError, match='preset'):
        review.run_examples(
            SimpleNamespace(
                example=choice, preset='mixed', frames=0, ui_scale=1.0, offscreen=None
            ),
            [],
            {},
        )
