#!/usr/bin/env python3
"""Compose existing BWM insertions using shared metadata and explicit frame evidence.

Run as ``python -m examples.ibl_recordings ATLAS_ROOT --release RELEASE --pid PID
--frame-evidence frame.json`` in the configured Datoviz environment with the
optional shared reader installed. No discovery, downloads or signal reads occur.
Frame evidence must independently establish source registration; do not copy
atlas frame metadata merely to label unknown source coordinates.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from examples.scientific_common import add_arguments, finish, prepare_viewer
from ibl_datoviz import AtlasViewer, WorldFrame
from ibl_datoviz.ibl import COORDINATE_CONVENTION, BwmSource, prepare_bwm_recording


def _source(args):
    if args.workspace is not None:
        from ibl_ai_agent.access import open_workspace  # noqa: PLC0415 -- optional reader

        return BwmSource.from_workspace(
            open_workspace(args.workspace), coordinate_convention=COORDINATE_CONVENTION,
        )
    return BwmSource.from_release(args.release, coordinate_convention=COORDINATE_CONVENTION)


def _receipt(recording):
    return {
        'source': asdict(recording.source),
        'insertion_id': recording.insertion_id,
        'session_id': recording.session_id,
        'populations': {
            name: {
                'total': len(payload.ids),
                'positioned': int(payload.positioned.sum()),
                'original_ids': list(payload.ids),
                'position_meaning': payload.provenance['position_meaning'],
                'source_validation_status': 'unknown',
            }
            for name in ('channels', 'clusters')
            if (payload := getattr(recording, name)) is not None
        },
        'signal_validation': 'not_requested',
    }


def main():
    """Prepare explicit source insertions before GUI startup and retain original IDs."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument(
        '--release', type=Path, help='exact existing pinned BWM release directory',
    )
    sources.add_argument('--workspace', type=Path, help='existing shared-reader catalog workspace')
    parser.add_argument('--pid', action='append', required=True, help='original insertion UUID')
    parser.add_argument('--frame-evidence', type=Path, required=True,
                        help='WorldFrame JSON with provenance verification method/evidence')
    parser.add_argument('--select-cluster', type=int,
                        help='original cluster ID in --select-pid, otherwise the last --pid')
    parser.add_argument('--select-pid', help='insertion containing --select-cluster')
    args = parser.parse_args()
    if len(set(args.pid)) != len(args.pid):
        parser.error('repeat distinct --pid values; duplicate source attachments are rejected')
    if args.select_pid is not None and args.select_pid not in args.pid:
        parser.error('--select-pid must name one of the supplied --pid values')
    frame_document = json.loads(args.frame_evidence.read_text())
    frame = WorldFrame(**frame_document)
    frame.require_verified()
    source = _source(args)
    recordings = [prepare_bwm_recording(source.insertion(pid), frame=frame) for pid in args.pid]
    options = prepare_viewer(args)
    report = {'recordings': [_receipt(recording) for recording in recordings],
              'reference_space_id': frame.reference_space_id,
              'coordinate_convention': frame.coordinate_convention,
              'frame_evidence': frame_document,
              'native_picking': 'not_requested'}
    with AtlasViewer(**options) as app:
        handles = {
            recording.insertion_id: app.add_recording(
                recording, name=recording.insertion_id, show=('channels', 'clusters'),
            )
            for recording in recordings
        }
        if args.select_cluster is not None:
            pid = args.select_pid or args.pid[-1]
            app.selection.set_observations([handles[pid].clusters.observation(args.select_cluster)])
            report['selection'] = {'insertion_id': pid, 'original_cluster_id': args.select_cluster}
        finish(app, args, report, 'Shared BWM recordings')


if __name__ == '__main__':
    main()
