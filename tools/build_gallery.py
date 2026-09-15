#!/usr/bin/env python3
"""Reproduce example screenshots and reports from the gallery manifest."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _load_manifest(path: Path) -> tuple[dict[str, Any], ...]:
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('schema_version') != 1 or not isinstance(document.get('examples'), list):
        raise ValueError('unsupported gallery manifest')
    examples = tuple(document['examples'])
    identifiers = [example.get('id') for example in examples]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise ValueError('every gallery example needs a non-empty id')
    if len(set(identifiers)) != len(identifiers):
        raise ValueError('gallery example ids must be unique')
    return examples


def _resolved_command(
    example: dict[str, Any],
    *,
    repository: Path,
    asset_root: Path,
    volume_root: Path,
    fixture_root: Path,
    output_root: Path,
) -> tuple[list[str], Path]:
    output = output_root / str(example['output'])
    report = output.with_suffix('.json')
    substitutions = {
        'repo': str(repository),
        'asset_root': str(asset_root),
        'volume_root': str(volume_root),
        'fixture_root': str(fixture_root),
        'output': str(output),
        'report': str(report),
    }
    script = repository / str(example['script'])
    arguments = [str(value).format_map(substitutions) for value in example['arguments']]
    return [sys.executable, str(script), *arguments], output


def _environment(repository: Path) -> dict[str, str]:
    environment = os.environ.copy()
    paths = [str(repository)]
    adjacent_assets = repository.parent / 'ibl-anatomy' / 'src'
    if adjacent_assets.is_dir():
        paths.append(str(adjacent_assets))
    existing = environment.get('PYTHONPATH')
    if existing:
        paths.append(existing)
    environment['PYTHONPATH'] = os.pathsep.join(paths)
    return environment


def main() -> int:
    """Run selected gallery entries into an ignored build directory."""
    repository = Path(__file__).resolve().parents[1]
    manifest_path = repository / 'docs' / 'gallery' / 'manifest.json'
    examples = _load_manifest(manifest_path)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--volume-root',
        type=Path,
        default=repository.parent / 'ibl-anatomy' / 'build' / 'allen-ccf-2017-50um',
        help='materialized Allen CCF 50 um volume-pack root',
    )
    parser.add_argument(
        '--asset-root',
        type=Path,
        default=repository.parent / 'ibl-anatomy' / 'build' / 'd070-published',
        help='materialized D070 asset-set root',
    )
    parser.add_argument(
        '--fixture-root',
        type=Path,
        default=repository.parent / 'ibl-anatomy' / 'tests' / 'fixtures',
        help='ibl-anatomy test-fixture root',
    )
    parser.add_argument(
        '--output-root',
        type=Path,
        default=repository / 'build' / 'gallery',
        help='ignored output directory',
    )
    parser.add_argument(
        '--example',
        action='append',
        choices=[str(example['id']) for example in examples],
        help='entry to render; repeat as needed (default: all)',
    )
    parser.add_argument(
        '--publish',
        action='store_true',
        help='copy reviewed outputs to canonical documentation image paths',
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='print commands without running them'
    )
    args = parser.parse_args()

    selected_ids = set(args.example or [str(example['id']) for example in examples])
    selected = tuple(example for example in examples if example['id'] in selected_ids)
    asset_root = args.asset_root.resolve()
    volume_root = args.volume_root.resolve()
    fixture_root = args.fixture_root.resolve()
    output_root = args.output_root.resolve()
    if any(example['asset'] == 'd070' for example in selected) and not asset_root.is_dir():
        parser.error(f'D070 asset root does not exist: {asset_root}')
    if any(example.get('volume') for example in selected) and not volume_root.is_dir():
        parser.error(f'Allen volume root does not exist: {volume_root}')
    if any(example['asset'] == 'synthetic' for example in selected) and not fixture_root.is_dir():
        parser.error(f'fixture root does not exist: {fixture_root}')
    if not args.dry_run:
        output_root.mkdir(parents=True, exist_ok=True)

    environment = _environment(repository)
    for example in selected:
        command, output = _resolved_command(
            example,
            repository=repository,
            asset_root=asset_root,
            volume_root=volume_root,
            fixture_root=fixture_root,
            output_root=output_root,
        )
        print(f'[{example["id"]}] {shlex.join(command)}')
        if args.dry_run:
            continue
        subprocess.run(command, cwd=repository, env=environment, check=True)
        if not output.is_file():
            raise RuntimeError(f'gallery entry {example["id"]} did not create {output}')
        if args.publish and example.get('published_image'):
            destination = (repository / str(example['published_image'])).resolve()
            if repository / 'docs' / 'images' not in destination.parents:
                raise ValueError(f'gallery publish path escapes docs/images: {destination}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output, destination)
            print(f'published {destination.relative_to(repository)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
