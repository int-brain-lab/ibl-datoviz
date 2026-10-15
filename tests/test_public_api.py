import ibl_datoviz


def test_public_api_is_explicit_and_stable():
    assert ibl_datoviz.__all__ == [
        'Points', 'Paths', 'Channels', 'Clusters', 'Sites', 'Trajectory', 'Recording',
        'WorldFrame', 'SourceKey', 'SourceObservationKey', 'LayerObservationRef',
        'LayerCapabilities', 'UnavailableLayerError',
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
        'InsertionTrajectory',
        'InsertionCollectionVisual',
    ]
    assert all(hasattr(ibl_datoviz, name) for name in ibl_datoviz.__all__)
