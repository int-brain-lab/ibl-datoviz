"""Approved scientific API: generic annotations, without IBL data or an AI runtime.

Callable example using explicitly prepared assets and frames.
The caller supplies verified atlas assets and their validated atlas-world frame.
"""

import numpy as np

from ibl_datoviz import AtlasViewer, Paths, Points


def review_generic_annotations(atlas_assets, atlas_frame, *, anatomical_context=()):
    """Review generic IDs, point/path ownership, styling and exact selection."""
    with AtlasViewer(
        atlas=atlas_assets,
        anatomy='major' if anatomical_context else 'detailed',
        anatomical_context=anatomical_context,
        mapping='beryl',
        layout='3d',
    ) as app:
        landmarks = app.add_points(
            Points(
                ids=('target-a', 'target-b'),
                positions_um=np.array([[0.0, 0.0, 0.0], [100.0, 200.0, 300.0]]),
                frame=atlas_frame,
                provenance={'kind': 'user annotation', 'description': 'Illustrative targets'},
            ),
            name='Targets',
            glyph='point',
        )
        landmarks.set_size_px(8)
        # Values explicitly follow the two IDs above, in the complete payload order.
        landmarks.color_by(
            [0.2, 0.8],
            name='Confidence',
            units='1',
            cmap='viridis',
            limits=(0, 1),
        )
        routes = app.add_paths(
            Paths(
                ids=('route-a',),
                positions_um=(
                    np.array([[0.0, 0.0, 0.0], [50.0, 80.0, 100.0], [100.0, 200.0, 300.0]]),
                ),
                frame=atlas_frame,
                provenance={'kind': 'user annotation', 'description': 'Illustrative route'},
            ),
            name='Candidate routes',
        )
        routes.set_width_px(3)
        app.selection.set_observations([landmarks.observation('target-b')])
        routes.set_visible(False)  # preserves observations and selection
        app.show()
