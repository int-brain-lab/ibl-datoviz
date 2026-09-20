import ibl_datoviz


def test_public_api_is_explicit_and_stable():
    assert ibl_datoviz.__all__ == [
        'AtlasMesh',
        'AtlasSliceSource',
        'AtlasCursor',
        'AtlasSliceComposer',
        'AtlasRegionValues',
        'AtlasTreeModel',
        'AtlasViewer',
        'LinkedAtlasNavigator',
        'ProbeSites',
        'compose_atlas_slice',
    ]
    assert all(hasattr(ibl_datoviz, name) for name in ibl_datoviz.__all__)
