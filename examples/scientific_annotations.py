#!/usr/bin/env python3
"""Annotate verified anatomy with viewer-owned generic points and paths.

Run as ``python -m examples.scientific_annotations /existing/atlas/assets`` in
the configured Datoviz environment. Coordinates below are illustrative user
annotations within mesh bounds, not scientific observations or tissue claims.
No IBL reader, dataset download or AI runtime is required.
"""

from __future__ import annotations

import argparse

import numpy as np

from examples.scientific_common import add_arguments, finish, prepare_viewer
from ibl_datoviz import AtlasViewer, Paths, Points


def main():
    """Create stable annotation identities, scalar colors and exact selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument(
        '--endpoint-gaps-px', type=float, nargs=2, metavar=('START', 'END'),
        help='explicit fixed endpoint disk radii; requires a compatible native candidate build',
    )
    args = parser.parse_args()
    options = prepare_viewer(args)
    xyz = options['atlas'].geometry.world_positions()
    minimum, maximum = xyz.min(axis=0), xyz.max(axis=0)
    span = maximum - minimum
    targets = minimum + np.asarray([[0.42, 0.45, 0.50], [0.58, 0.55, 0.45]]) * span
    route = np.stack((targets[0], minimum + np.asarray([0.5, 0.5, 0.4]) * span, targets[1]))
    provenance = {
        'kind': 'user annotation',
        'derivation': 'illustrative coordinates within verified mesh bounds; not measured tissue',
    }
    with AtlasViewer(**options) as app:
        landmarks = app.add_points(
            Points(('target-a', 'target-b'), targets, app.frame, provenance),
            name='Illustrative targets', glyph='point',
        )
        landmarks.set_size_px(8)
        landmarks.color_by(
            [0.2, 0.8], name='Illustrative confidence', units='1',
            cmap='viridis', limits=(0, 1),
        )
        routes = app.add_paths(
            Paths(('route-a',), (route,), app.frame, provenance), name='Illustrative route',
        )
        routes.set_width_px(3)
        if args.endpoint_gaps_px is not None:
            routes.set_endpoint_gaps_px(*args.endpoint_gaps_px)
        app.selection.set_observations([landmarks.observation('target-b')])
        finish(app, args, {
            'kind': 'illustrative user annotations',
            'reference_space_id': app.frame.reference_space_id,
            'coordinate_convention': app.frame.coordinate_convention,
            'point_ids': ['target-a', 'target-b'],
            'point_positions_um': targets.tolist(),
            'path_ids': ['route-a'],
            'endpoint_gaps_px': routes.endpoint_gaps_px,
            'selected_id': 'target-b',
            'native_picking': 'not_requested',
        }, 'Generic scientific annotations')


if __name__ == '__main__':
    main()
