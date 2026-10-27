#!/usr/bin/env python3
"""Inspect prepared BWM values and return exact selected site IDs to analysis.

Offline fixture only: no service, credentials, discovery, downloads or signals.
The 192 rows are prepared co-located channel groups, not individual neurons.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples.bwm_probe import FIXTURE, _load_fixture
from examples.scientific_common import add_arguments, prepare_viewer
from examples.scientific_scalar_review import ScalarReview
from ibl_anatomy import open_volume_pack


def main():
    """Compose the existing public viewer and export committed source-scoped rows."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument('--volume-root', type=Path, help='existing 50 um pack for linked slices')
    parser.add_argument('--output', type=Path, default=Path('build/analysis-roundtrip'))
    parser.add_argument('--select-site', type=int, action='append', default=[])
    parser.add_argument('--locate-site', type=int, help='explicitly navigate slices to this site')
    parser.add_argument(
        '--figure-dir', type=Path, help='export offline figure bundle instead of GUI'
    )
    args = parser.parse_args()
    if args.figure_dir is not None and args.offscreen is not None:
        parser.error('--figure-dir and --offscreen are mutually exclusive')
    if args.locate_site is not None and args.volume_root is None:
        parser.error('--locate-site requires --volume-root')
    sites, provenance = _load_fixture(FIXTURE)
    options = prepare_viewer(args)
    if args.volume_root is not None:
        options.update(
            layout='linked', volumes=open_volume_pack(args.volume_root).load_volumes(),
            render_volume=False,
        )
    with ScalarReview(**options) as app:
        app.configure(sites, provenance)
        layer = app.site_layer
        app.tables.show(layer)
        selection_path = args.output / 'selection.json'
        changes = []

        def selected(event):
            # This callback runs after tables, highlights and scientific state commit.
            rows = app.selection.to_records()
            changes.append({'revision': event.revision, 'count': len(rows)})
            app.selection.export_json(selection_path)
            print('Selected original site IDs:', [row['original_id'] for row in rows], flush=True)

        subscription = app.selection.on_changed(selected)
        app.selection.set_observations([layer.observation(key) for key in args.select_site])
        app.selection.export_json(selection_path)  # Includes an explicit empty initial selection.
        if args.locate_site is not None:
            app.slices.locate(layer.observation(args.locate_site))
        if args.figure_dir is not None:
            app.export_figure(args.figure_dir, title='BWM prepared site firing rates')
        elif args.offscreen is not None:
            app.render_offscreen(args.offscreen)
        else:
            app.show(title='IBL analysis round trip', frame_count=args.frames)
        subscription.close()
        if app.selection.callback_errors:
            raise RuntimeError(
                'selection export callback failed'
            ) from app.selection.callback_errors[0]
        # Live callbacks already saved the last committed selection, even on window close.
        report = {
            'fixture_sha256': provenance['artifact']['sha256'],
            'population': '192 prepared co-located channel groups; not cluster identities',
            'selection_file': str(selection_path),
            'selection_changes': changes,
            'source_validation': 'unknown', 'alignment_quality': 'unknown',
            'signal_reads': 'not_requested',
        }
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(f'Selection saved to {selection_path}', flush=True)


if __name__ == '__main__':
    main()
