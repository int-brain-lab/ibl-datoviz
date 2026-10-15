"""IBL atlas visualization components for Datoviz v0.4."""

from .atlas import AtlasMesh
from .atlas_slice_source import AtlasSliceSource
from .envelope import AtlasEnvelope
from .insertions import InsertionCollectionVisual, InsertionTrajectory
from .layers import LayerCapabilities, LayerObservationRef, UnavailableLayerError
from .linked_atlas import LinkedAtlasNavigator
from .navigator import (
    AtlasCursor,
    AtlasSliceComposer,
    compose_atlas_slice,
)
from .ontology import AtlasTreeModel
from .payloads import (
    Channels,
    Clusters,
    Paths,
    Points,
    Recording,
    Sites,
    SourceKey,
    SourceObservationKey,
    Trajectory,
    WorldFrame,
)
from .points import PointCollection, PointCollectionVisual
from .probe import ProbeSites
from .regional_quantities import RegionValues
from .regions import AtlasRegionValues
from .sampled_plane import SampledPlane, SampledPlaneVisual
from .viewer import AtlasViewer

__all__ = [
    'Points', 'Paths', 'Channels', 'Clusters', 'Sites', 'Trajectory', 'Recording',
    'WorldFrame', 'SourceKey', 'SourceObservationKey', 'LayerObservationRef',
    'LayerCapabilities', 'UnavailableLayerError',
    'AtlasMesh',
    'AtlasEnvelope',
    'AtlasSliceSource',
    'AtlasCursor',
    'AtlasSliceComposer',
    'AtlasRegionValues',
    'RegionValues',
    'AtlasTreeModel',
    'AtlasViewer',
    'LinkedAtlasNavigator',
    'ProbeSites',
    'compose_atlas_slice',
    'PointCollection',
    'PointCollectionVisual',
    'SampledPlane',
    'SampledPlaneVisual',
    'InsertionTrajectory',
    'InsertionCollectionVisual',
]

__version__ = '0.2.0.dev0'
