"""Lower-level adapters and visuals for explicit native scene composition.

These objects support custom renderers and diagnostic clients. Visuals borrow
caller-owned native scenes and panels and must close before those scenes.
Prefer the viewer-owned scientific payloads and handles in :mod:`ibl_datoviz`
for application code. Legacy probe and regional records remain available here
for clients whose existing linked presentation is not yet migrated.
"""

from .insertions import InsertionCollectionVisual, InsertionTrajectory
from .navigator import AtlasCursor, AtlasSliceComposer, compose_atlas_slice
from .ontology import AtlasTreeModel
from .points import PointCollection, PointCollectionVisual
from .probe import ProbeSites
from .regions import AtlasRegionValues
from .sampled_plane import SampledPlane, SampledPlaneVisual

__all__ = [
    'AtlasCursor',
    'AtlasSliceComposer',
    'compose_atlas_slice',
    'AtlasTreeModel',
    'ProbeSites',
    'AtlasRegionValues',
    'PointCollection',
    'PointCollectionVisual',
    'SampledPlane',
    'SampledPlaneVisual',
    'InsertionTrajectory',
    'InsertionCollectionVisual',
]
