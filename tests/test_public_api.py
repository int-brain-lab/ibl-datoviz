"""Scientific and native-component namespaces have distinct supported contracts."""

import ibl_datoviz
from ibl_datoviz import components


def test_scientific_api_has_one_viewer_and_owned_handles():
    required = {
        'AtlasViewer',
        'AtlasMesh',
        'AtlasEnvelope',
        'AtlasSliceSource',
        'Points',
        'Paths',
        'Channels',
        'Clusters',
        'Sites',
        'Trajectory',
        'Recording',
        'WorldFrame',
        'RegionValues',
        'LayerHandle',
        'RecordingHandle',
        'RegionalQuantityHandle',
        'LayerObservationRef',
        'LayerCapabilities',
        'UnavailableLayerError',
        'SourceKey',
        'SourceObservationKey',
        'SelectionState',
        'SelectionEvent',
        'SelectionSubscription',
        'MappedRegionValues',
    }
    assert set(ibl_datoviz.__all__) == required
    assert len(ibl_datoviz.__all__) == len(required)
    assert all(hasattr(ibl_datoviz, name) for name in required)
    assert not hasattr(ibl_datoviz, 'LinkedAtlasNavigator')
    assert '__new__' not in ibl_datoviz.AtlasViewer.__dict__
    for name in (
        'set_probe',
        'set_probe_sites',
        'set_probe_data',
        'set_region_data',
        'set_insertion',
        'set_insertion_color',
        'remove_insertion',
    ):
        assert not hasattr(ibl_datoviz.AtlasViewer, name)


def test_native_components_are_explicitly_separate():
    assert not set(components.__all__) & set(ibl_datoviz.__all__)
    assert all(hasattr(components, name) for name in components.__all__)
    assert all(not hasattr(ibl_datoviz, name) for name in components.__all__)
