#!/usr/bin/env python3
"""Compare independently styled trajectories from pinned real W39 insertions.

Prepare the default input from the canonical channels parquet with
``tools/build_w39_insertions.py``. Coordinates are source XYZ metres converted
to atlas-world micrometres; no fitted trajectory is introduced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from ibl_datoviz import AtlasViewer

DEFAULT_PATHS = Path(__file__).resolve().parents[1] / 'build' / 'w39-insertions' / 'insertions.npz'
DEFAULT_PROVENANCE = DEFAULT_PATHS.with_suffix('.json')
SOURCE_SHA256 = '17dd0a9be89a7eea683d05a6c34170726bde47e66d509aba5217932dbffff52e'
EXPECTED_PATHS = {
    '00a824c0-e060-495f-9ebc-79c82fef4c67': (
        384,
        'c48cd27f3fd768d82058fea7fc81cec5a1c54c3dfac16ac29c03d022f187a1ba',
    ),
    '00a96dee-1e8b-44cc-9cc3-aca704d2b594': (
        384,
        '803551a09e16b4bde14824551a1bb2613d9c341eba92bc7b70d23ff4716576ad',
    ),
    '00c425fd-ec3e-4cd2-b8af-c0bc0c4bdd44': (
        384,
        'fe879239330630c28b5cbcabfa4773166c9b2bf4c201b17d03e5bc58184e9def',
    ),
}
COLORS = ((255, 205, 72, 255), (70, 220, 250, 255), (250, 110, 160, 255))
WIDTHS = (3.0, 5.0, 7.0)


def _load_paths(path: Path, provenance_path: Path) -> tuple[list[tuple[str, np.ndarray]], dict]:
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    if provenance.get('format') != 'ibl-datoviz-w39-insertions-v1':
        raise ValueError('unexpected W39 insertion derivative format')
    if provenance.get('source_sha256') != SOURCE_SHA256:
        raise ValueError('trajectory provenance does not identify the pinned W39 source')
    expected_ids = provenance.get('ids')
    if expected_ids != list(EXPECTED_PATHS):
        raise ValueError('trajectory IDs differ from the pinned W39 example paths')
    expected_coordinates = (
        'source x/y/z metres multiplied by 1e6; no fitted or extrapolated points'
    )
    if provenance.get('coordinates') != expected_coordinates:
        raise ValueError('unexpected trajectory coordinate provenance')
    with np.load(path, allow_pickle=False) as archive:
        paths = []
        for insertion_id in expected_ids:
            source_points = np.asarray(archive[insertion_id], dtype=np.float64)
            if source_points.ndim != 2 or source_points.shape[1] != 3 or len(source_points) < 2:
                raise ValueError(f'insertion {insertion_id} must contain at least two XYZ points')
            if not np.isfinite(source_points).all():
                raise ValueError(f'insertion {insertion_id} contains non-finite coordinates')
            canonical = np.asarray(source_points, dtype='<f8', order='C')
            actual_hash = hashlib.sha256(canonical.tobytes(order='C')).hexdigest()
            expected_count, expected_hash = EXPECTED_PATHS[insertion_id]
            if len(source_points) != expected_count or actual_hash != expected_hash:
                raise ValueError(
                    f'insertion {insertion_id} differs from its pinned trajectory array'
                )
            points = np.asarray(source_points, dtype=np.float32)
            paths.append((insertion_id, points))
        if set(archive.files) != set(expected_ids):
            raise ValueError('trajectory IDs differ from provenance')
    return paths, provenance


def _parse_width(
    value: str, insertion_ids: set[str], parser: argparse.ArgumentParser
) -> tuple[str, float]:
    try:
        insertion_id, width_text = value.rsplit('=', 1)
        width = float(width_text)
    except ValueError:
        parser.error(f'invalid --insertion-width {value!r}; expected PID=PX')
    if insertion_id not in insertion_ids or not np.isfinite(width) or width <= 0:
        parser.error(f'invalid insertion ID or width: {value!r}')
    return insertion_id, width


def main() -> int:
    """Render three source-derived W39 trajectories with separate styles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root', type=Path, help='materialized pinned D070 asset-set root')
    parser.add_argument(
        '--paths',
        type=Path,
        default=DEFAULT_PATHS,
        help='NPZ produced by tools/build_w39_insertions.py',
    )
    parser.add_argument('--provenance', type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument('--mapping', choices=('allen', 'beryl', 'cosmos'), default='beryl')
    parser.add_argument('--hide-insertion', action='append', default=[], metavar='PID')
    parser.add_argument(
        '--insertion-width',
        action='append',
        default=[],
        metavar='PID=PX',
        help='set one path width in pixels; repeat to style multiple paths',
    )
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--ui-scale', type=float, default=1.0)
    args = parser.parse_args()
    paths, provenance = _load_paths(args.paths, args.provenance)
    insertion_ids = set(provenance['ids'])
    unknown_hidden = set(args.hide_insertion).difference(insertion_ids)
    if unknown_hidden:
        parser.error(f'unknown insertion IDs in --hide-insertion: {sorted(unknown_hidden)}')
    widths = dict(zip(provenance['ids'], WIDTHS, strict=True))
    for specification in args.insertion_width:
        insertion_id, width = _parse_width(specification, insertion_ids, parser)
        widths[insertion_id] = width

    with AtlasViewer.from_asset_set(
        args.asset_root,
        mapping=args.mapping,
        surface_opacity=0.16,
        ui_scale=args.ui_scale,
        enable_interaction=True,
    ) as viewer:
        for index, (insertion_id, points) in enumerate(paths):
            viewer._insertion_collection().set_insertion(
                insertion_id,
                points,
                color=COLORS[index % len(COLORS)],
                width_px=widths[insertion_id],
            )
            if insertion_id in args.hide_insertion:
                viewer._insertion_collection().set_visible(insertion_id, False)
        if args.offscreen:
            rgba = viewer.render_offscreen(args.offscreen)
            print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
        else:
            viewer.show(
                title=f'W39 insertion trajectories — {len(paths)} paths', frame_count=args.frames
            )
    print(f'source: {provenance["source_sha256"]} ({len(paths)} trajectories)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
