"""IBL atlas visualization components for Datoviz v0.4."""

from .atlas import AtlasMesh
from .atlas_slice_source import AtlasSliceSource
from .envelope import AtlasEnvelope
from .linked_atlas import LinkedAtlasNavigator
from .navigator import (
    AtlasCursor,
    AtlasSliceComposer,
    compose_atlas_slice,
)
from .ontology import AtlasTreeModel
from .points import PointCollection, PointCollectionVisual
from .probe import ProbeSites
from .regions import AtlasRegionValues
from .sampled_plane import SampledPlane, SampledPlaneVisual
from .viewer import AtlasViewer

__all__ = [
    'AtlasMesh',
    'AtlasEnvelope',
    'AtlasSliceSource',
    'AtlasCursor',
    'AtlasSliceComposer',
    'AtlasRegionValues',
    'AtlasTreeModel',
    'AtlasViewer',
    'LinkedAtlasNavigator',
    'ProbeSites',
    'compose_atlas_slice',
    'PointCollection',
    'PointCollectionVisual',
    'SampledPlane',
    'SampledPlaneVisual',
]

__version__ = '0.2.0.dev0'
