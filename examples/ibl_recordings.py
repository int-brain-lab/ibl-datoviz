#!/usr/bin/env python3
"""Compose existing BWM insertions using shared metadata and reviewed frame evidence.

Run as ``python -m examples.ibl_recordings ATLAS_ROOT --release RELEASE --pid PID
[--frame-evidence frame.json]`` in the configured Datoviz environment with the
optional shared reader installed. No discovery, downloads or signal reads occur.
An exact, reviewed producer declaration may supply the frame. Legacy releases
require --frame-evidence identifying the source coordinate convention and atlas reference;
do not copy atlas frame metadata merely to label unknown source coordinates.
An insertion's alignment quality and scientific source validation remain separate.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from examples.scientific_common import add_arguments, finish, prepare_viewer
from ibl_anatomy import open_volume_pack
from ibl_datoviz import AtlasViewer, WorldFrame
from ibl_datoviz.ibl import COORDINATE_CONVENTION, BwmSource, prepare_bwm_recording


def _source(args):
    if args.workspace is not None:
        from ibl_ai_agent.access import open_workspace  # noqa: PLC0415 -- optional reader

        return BwmSource.from_workspace(
            open_workspace(args.workspace),
            coordinate_convention=COORDINATE_CONVENTION,
        )
    return BwmSource.from_release(args.release, coordinate_convention=COORDINATE_CONVENTION)


def _plain(value):
    """Serialize immutable payload provenance without mutating its retained state."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _frame_receipt(frame):
    return {
        'reference_space_id': frame.reference_space_id,
        'coordinate_convention': frame.coordinate_convention,
        'provenance': _plain(frame.provenance),
    }


def _receipt(recording):
    return {
        'source': asdict(recording.source),
        'insertion_id': recording.insertion_id,
        'session_id': recording.session_id,
        'frame_evidence': _frame_receipt(recording.channels.frame),
        'prepared_recording_metadata': _plain(
            recording.provenance.get('prepared_recording_metadata')
        ),
        'source_validation_status': recording.provenance['source_validation_status'],
        'populations': {
            name: {
                'total': len(payload.ids),
                'positioned': int(payload.positioned.sum()),
                'original_ids': list(payload.ids),
                'position_meaning': payload.provenance['position_meaning'],
                'source_validation_status': payload.provenance.get('source_metadata', {}).get(
                    'validation_status',
                    'unknown',
                ),
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
        '--release',
        type=Path,
        help='exact existing pinned BWM release directory',
    )
    sources.add_argument('--workspace', type=Path, help='existing shared-reader catalog workspace')
    parser.add_argument('--pid', action='append', required=True, help='original insertion UUID')
    parser.add_argument(
        '--frame-evidence',
        type=Path,
        help='reviewed legacy WorldFrame JSON; unnecessary when exact reviewed '
        'producer coordinate declarations are available',
    )
    parser.add_argument(
        '--select-cluster',
        type=int,
        help='original cluster ID in --select-pid, otherwise the last --pid',
    )
    parser.add_argument('--select-pid', help='insertion containing --select-cluster')
    parser.add_argument(
        '--volume-root', type=Path, help='existing compatible volume pack for linked slices'
    )
    parser.add_argument(
        '--selection-output', type=Path, metavar='JSON',
        help='save exact source-scoped rows after each committed selection',
    )
    args = parser.parse_args()
    if len(set(args.pid)) != len(args.pid):
        parser.error('repeat distinct --pid values; duplicate source attachments are rejected')
    if args.select_pid is not None and args.select_pid not in args.pid:
        parser.error('--select-pid must name one of the supplied --pid values')
    frame = None
    if args.frame_evidence is not None:
        frame = WorldFrame(**json.loads(args.frame_evidence.read_text()))
        frame.require_verified()
    source = _source(args)
    recordings = [prepare_bwm_recording(source.insertion(pid), frame=frame) for pid in args.pid]
    options = prepare_viewer(args)
    if args.volume_root is not None:
        options.update(
            layout='linked', volumes=open_volume_pack(args.volume_root).load_volumes(),
            render_volume=False,
        )
    accepted_frame = recordings[0].channels.frame
    report = {
        'recordings': [_receipt(recording) for recording in recordings],
        'reference_space_id': accepted_frame.reference_space_id,
        'coordinate_convention': accepted_frame.coordinate_convention,
        'frame_evidence': {
            recording.insertion_id: _frame_receipt(recording.channels.frame)
            for recording in recordings
        },
        'native_picking': 'not_requested',
    }
    with AtlasViewer(**options) as app:
        handles = {
            recording.insertion_id: app.add_recording(
                recording,
                name=recording.insertion_id,
                show=('channels', 'clusters'),
            )
            for recording in recordings
        }
        subscription = None
        if args.selection_output is not None:
            subscription = app.selection.on_changed(
                lambda _event: app.selection.export_json(args.selection_output)
            )
        if args.select_cluster is not None:
            pid = args.select_pid or args.pid[-1]
            app.selection.set_observations(
                [handles[pid].clusters.observation(args.select_cluster)]
            )
            report['selection'] = {'insertion_id': pid, 'original_cluster_id': args.select_cluster}
        if args.selection_output is not None:
            app.selection.export_json(args.selection_output)
        try:
            finish(app, args, report, 'Shared BWM recordings')
        finally:
            if subscription is not None:
                subscription.close()
        if args.selection_output is not None and app.selection.callback_errors:
            raise RuntimeError(
                'selection export callback failed'
            ) from app.selection.callback_errors[0]


if __name__ == '__main__':
    main()
