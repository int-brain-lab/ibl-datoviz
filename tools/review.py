#!/usr/bin/env python3
"""Prepare and run contributor tests and the six focused native review examples."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path
from urllib.request import urlopen

REPOSITORY = Path(__file__).resolve().parents[1]
CACHE = REPOSITORY / 'build' / 'review'
CONFIG = CACHE / 'config.json'
ASSETS = REPOSITORY / 'build' / 'atlas-d070'
VOLUME = REPOSITORY / 'build' / 'allen-ccf-2017-50um'
ANATOMY = CACHE / 'anatomy'
EXAMPLES = {
    'surface': ('real_atlas_surface.py', (ASSETS,)),
    'mapping': ('atlas_mapping_switch.py', (ASSETS,)),
    'picking': ('atlas_region_picking.py', (ASSETS,)),
    'probe': ('bwm_probe_geometry.py', (ASSETS,)),
    'firing-rate': ('bwm_probe_firing_rate.py', (ASSETS,)),
    'slices': ('atlas_slice_scroll.py', (ASSETS / 'mesh-pack', VOLUME)),
}


def run(command, **kwargs):
    """Run an argument list without shell interpolation."""
    command = [str(argument) for argument in command]
    print(f'$ {shlex.join(command)}', flush=True)
    return subprocess.run(command, cwd=REPOSITORY, check=True, **kwargs)


def source_pin(name):
    """Read the Git identity actually installed by the locked uv resolution."""
    metadata = distribution(name).read_text('direct_url.json')
    revision = json.loads(metadata or '{}').get('vcs_info', {}).get('commit_id')
    if not revision:
        raise ValueError(f'{name} needs the locked Git install; run uv sync --group dev --locked')
    return revision


def git_revision(checkout):
    """Resolve a checkout identity without printing credentials or remote URLs."""
    return subprocess.check_output(
        ['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True
    ).strip()


def native_library(checkout):
    """Locate a local build, allowing an explicitly selected custom build path."""
    explicit = os.environ.get('DATOVIZ_LIBRARY')
    names = {
        'Darwin': ('libdatoviz.dylib',),
        'Linux': ('libdatoviz.so',),
        'Windows': ('datoviz.dll', 'libdatoviz.dll'),
    }.get(platform.system(), ())
    candidates = ([Path(explicit).expanduser()] if explicit else []) + [
        checkout / 'build' / directory / name
        for directory in ('src', '', 'src/Debug', 'src/Release')
        for name in names
    ]
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise ValueError(
        f'No native Datoviz build found in {checkout}; build Datoviz separately first'
    )


def runtime(checkout):
    """Pair the checkout's facade with its native build and existing runtime environment."""
    checkout = checkout.expanduser().resolve()
    if not (checkout / 'datoviz' / '__init__.py').is_file():
        raise ValueError(f'Not a Datoviz source checkout: {checkout}')
    expected = source_pin('datoviz')
    actual = git_revision(checkout)
    if actual != expected:
        raise ValueError(f'Datoviz HEAD is {actual}; this source snapshot tests {expected}')
    library = native_library(checkout)
    environment = os.environ.copy()
    paths = [str(REPOSITORY), str(checkout)]
    if environment.get('PYTHONPATH'):
        paths.append(environment['PYTHONPATH'])
    environment['PYTHONPATH'] = os.pathsep.join(paths)
    environment['DATOVIZ_LIBRARY'] = str(library)
    environment['IBL_ANATOMY_FIXTURE_ROOT'] = str(ANATOMY / 'tests' / 'fixtures')
    if ASSETS.exists():
        environment['IBL_ATLAS_ASSET_SET_ROOT'] = str(ASSETS)
    # Datoviz's platform environment belongs to its checkout. Never auto-approve .envrc.
    prefix = []
    if (checkout / '.envrc').exists() and shutil.which('direnv'):
        prefix = ['direnv', 'exec', str(checkout)]
    return prefix, environment, library


def doctor(checkout):
    """Check the loaded facade/library rather than trusting installed version metadata."""
    prefix, environment, library = runtime(checkout)
    code = (
        'import json, datoviz; import datoviz._ctypes as native; '
        'print(json.dumps([datoviz.__file__, native.dvz._name]))'
    )
    result = subprocess.run(
        [*prefix, sys.executable, '-c', code],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    module, loaded = json.loads(result.stdout.strip())
    if not Path(module).resolve().is_relative_to(checkout.resolve()):
        raise ValueError(f'Unexpected imported Datoviz module: {module}')
    if Path(loaded).resolve() != library:
        raise ValueError(f'Unexpected loaded library: {loaded}; expected {library}')
    print(f'Datoviz source: {module}\nNative library: {loaded}')
    print('Runtime imports passed; the test command checks actual native rendering.')
    return prefix, environment


def prepare_anatomy():
    """Fetch pinned builders and fixtures into the ignored cache, without adjacent repos."""
    revision = source_pin('ibl-anatomy')
    if not (ANATOMY / '.git').exists():
        ANATOMY.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', ANATOMY])
    has_head = (
        subprocess.run(
            ['git', '-C', str(ANATOMY), 'rev-parse', '--verify', 'HEAD'],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if not has_head:
        run(
            [
                'git',
                '-C',
                ANATOMY,
                'fetch',
                '--depth',
                '1',
                'https://github.com/int-brain-lab/ibl-anatomy.git',
                revision,
            ]
        )
        run(['git', '-C', ANATOMY, 'checkout', '--detach', 'FETCH_HEAD'])
    if git_revision(ANATOMY) != revision:
        raise ValueError(f'Anatomy cache differs from locked revision {revision}: {ANATOMY}')
    dirty = subprocess.check_output(
        ['git', '-C', str(ANATOMY), 'status', '--porcelain'], text=True
    ).strip()
    if dirty:
        raise ValueError(f'Anatomy cache has local edits; move it aside before setup: {ANATOMY}')


def download(url, destination, expected):
    """Reuse verified bytes or download and verify atomically before publishing."""
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Cached source has the wrong SHA256: {destination}')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            digest = hashlib.sha256()
            print(f'Downloading {destination.name}', flush=True)
            with urlopen(url, timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
            output.close()
            if digest.hexdigest() != expected:
                raise ValueError(f'Download has the wrong SHA256: {url}')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)


def builder_constants(builder):
    """Read source identities from the pinned upstream builder, avoiding duplicate pins."""
    return {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(builder.read_text()).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }


def prepare_assets():
    """Verify or materialize D070 and build the bounded 50 um pack."""
    from ibl_anatomy import (  # noqa: PLC0415
        bundled_asset_set,
        materialize_asset_set,
        open_volume_pack,
        verify_materialized_asset_set,
    )

    lock = bundled_asset_set()
    if ASSETS.exists():
        verify_materialized_asset_set(lock, ASSETS)
    else:
        print('Materializing verified D070 surface assets', flush=True)
        materialize_asset_set(lock, ASSETS)
    builder = ANATOMY / 'tools' / 'build_allen_volume_pack.py'
    constants = builder_constants(builder)
    if not VOLUME.exists():
        sources = CACHE / 'sources'
        template, annotation = (
            sources / f'{name}_50.nrrd' for name in ('average_template', 'annotation')
        )
        download(constants['_TEMPLATE_URL'], template, constants['_TEMPLATE_SHA256'])
        download(constants['_ANNOTATION_URL'], annotation, constants['_ANNOTATION_SHA256'])
        with tempfile.TemporaryDirectory(dir=CACHE) as temporary:
            output = Path(temporary) / 'pack'
            run(
                [
                    'uv',
                    'run',
                    '--frozen',
                    '--with',
                    'pynrrd==1.1.3',
                    'python',
                    builder,
                    template,
                    annotation,
                    ASSETS / 'regions.json',
                    output,
                ]
            )
            open_volume_pack(output).verify()
            output.rename(VOLUME)
    pack = open_volume_pack(VOLUME)
    pack.verify()
    if tuple(pack.grid.shape) != constants['_SHAPE']:
        raise ValueError(f'Review volume has the wrong grid: {VOLUME}')
    catalog_sha = hashlib.sha256((ASSETS / 'regions.json').read_bytes()).hexdigest()
    if pack.manifest['region_catalog']['sha256'] != catalog_sha:
        raise ValueError(f'Review volume catalog differs from D070: {VOLUME}')
    print(f'Review assets ready: {ASSETS}\nSlices ready: {VOLUME}')


def configured_checkout():
    """Read the local setup choice; no workstation paths are tracked in the repository."""
    if not CONFIG.is_file():
        raise ValueError('Run setup --datoviz /path/to/datoviz first')
    return Path(json.loads(CONFIG.read_text())['datoviz'])


def setup_review(checkout, *, tests_only=False):
    """Save a working local pairing only after the requested assets are prepared."""
    checkout = checkout.expanduser().resolve()
    doctor(checkout)
    prepare_anatomy()
    if not tests_only:
        prepare_assets()
    CACHE.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({'datoviz': str(checkout)}, indent=2) + '\n')
    print('Setup complete.\nTests: uv run --frozen tools/review.py test')
    if tests_only:
        print('For review data, rerun setup without --tests-only.')
    else:
        print('Review: uv run --frozen tools/review.py run')


def main():
    """Prepare once, then run unit/native tests or focused real-data examples."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('setup', help='prepare fixtures, runtime pairing and review data')
    setup.add_argument(
        '--datoviz', type=Path, required=True, help='separately built Datoviz checkout'
    )
    setup.add_argument('--tests-only', action='store_true', help='skip real-data downloads/builds')
    commands.add_parser('doctor', help='report and check the configured local Datoviz pairing')
    tests = commands.add_parser(
        'test', help='run pytest with cached fixtures and native environment'
    )
    tests.add_argument('pytest_args', nargs=argparse.REMAINDER)
    review = commands.add_parser('run', help='open a focused example, or all six in review order')
    review.add_argument('example', nargs='?', default='all', choices=['all', *EXAMPLES])
    review.add_argument(
        '--frames', type=int, default=0, help='zero runs until each window is closed'
    )
    args = parser.parse_args()
    try:
        if args.command == 'setup':
            setup_review(args.datoviz, tests_only=args.tests_only)
            return 0
        checkout = configured_checkout()
        prefix, environment = doctor(checkout)
        if args.command == 'doctor':
            return 0
        if args.command == 'test':
            if not (ANATOMY / 'tests' / 'fixtures').is_dir():
                raise ValueError('Cached fixtures are missing; rerun setup')
            if git_revision(ANATOMY) != source_pin('ibl-anatomy'):
                raise ValueError('Cached fixture revision differs; rerun setup with a fresh cache')
            arguments = args.pytest_args
            if arguments and arguments[0] == '--':
                arguments = arguments[1:]
            run([*prefix, sys.executable, '-m', 'pytest', *(arguments or ['-q'])], env=environment)
        else:
            if not ASSETS.exists() or not VOLUME.exists():
                raise ValueError('Review data is missing; rerun setup without --tests-only')
            names = tuple(EXAMPLES) if args.example == 'all' else (args.example,)
            for name in names:
                script, arguments = EXAMPLES[name]
                print(f'Opening {name}; close its window to continue.', flush=True)
                run(
                    [
                        *prefix,
                        sys.executable,
                        REPOSITORY / 'examples' / script,
                        *arguments,
                        '--frames',
                        args.frames,
                    ],
                    env=environment,
                )
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        print(f'Review setup: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
