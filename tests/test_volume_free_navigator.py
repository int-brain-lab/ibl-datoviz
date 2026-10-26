from dataclasses import replace
from pathlib import Path
from threading import Event
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import (
    MaterializedRegisteredAssets,
    open_anatomy_pack,
    open_intensity_block_pack,
    open_region_catalog,
    open_volume_pack,
)
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.linked_atlas import LinkedSlices
from ibl_datoviz.slice_scheduler import SliceRequest
from tests import FIXTURES
from tests.test_atlas import FakeDatoviz

MESH = FIXTURES / 'mesh-pack-v1' / 'pack'
VOLUME = FIXTURES / 'linked-atlas-v1' / 'volume-pack'
pytestmark = pytest.mark.usefixtures('cpu_slice_visuals')


@pytest.fixture
def source():
    return open_volume_pack(VOLUME).load_volumes()


class VolumeForbiddenDatoviz(FakeDatoviz):
    DVZ_ALPHA_BLENDED = 1

    def dvz_volume(self, *args):
        pytest.fail('volume-free navigator created a volume visual')


@pytest.fixture
def cpu_slice_visuals(monkeypatch, request):
    """Keep real CPU controllers with the tested fake native surface adapter."""
    if request.module.__name__ == __name__ and request.node.name.startswith('test_native_'):
        return

    def layout(component):
        viewer = component.viewer
        viewer._linked = None
        try:
            AtlasViewer._create_layout(viewer)
        finally:
            viewer._linked = component
        component.slice_panels = {axis: object() for axis in ('ap', 'ml', 'dv')}

    def marker(component):
        component.marker_world_um = component.cursor.world_um(component.slice_source)

    def refresh(component, axes=None):
        for axis in ('ap', 'ml', 'dv') if axes is None else axes:
            component.prepared_slices[axis] = component._slice_layers(axis)
        marker(component)

    def create(component):
        component.prepared_slices = {}
        refresh(component)

    monkeypatch.setattr(LinkedSlices, '_create_layout', layout)
    monkeypatch.setattr(LinkedSlices, '_create_slices', create)
    monkeypatch.setattr(LinkedSlices, '_create_cursor_marker', marker)
    monkeypatch.setattr(LinkedSlices, '_update_cursor_marker', marker)
    monkeypatch.setattr(LinkedSlices, '_refresh_slices', refresh)


def test_volume_free_dense_source_has_no_volume_and_preserves_controllers(source):
    native = VolumeForbiddenDatoviz()
    mesh = AtlasMesh.from_pack(MESH)
    with AtlasViewer.from_slice_source(mesh, source, datoviz=native) as navigator:
        assert navigator._linked.volumes is None and not navigator._linked.render_volume
        assert navigator.catalog is source.regions
        assert navigator._linked.volume is None and navigator._linked.volume_field is None
        assert navigator._linked.volume_resolution_label is None
        assert navigator._surface_presentation.alpha_mode == native.DVZ_ALPHA_OPAQUE
        navigator.slices.set_position(ap=1, ml=4, dv=1, units='voxel', select_region=True)
        assert navigator._selected_region_ids == (315,)
        selected = navigator._selected_region_ids
        navigator.slices.set_position(ap=0, ml=4, dv=1, units='voxel')
        assert navigator._selected_region_ids == selected
        np.testing.assert_array_equal(
            navigator._linked.marker_world_um, navigator._linked.cursor.world_um(source)
        )
        assert all(a.shape == b.shape for a, b in navigator._linked.prepared_slices.values())
        navigator.set_mapping('beryl')
        assert navigator._linked.slice_composer.mapping == navigator.tree_model.mapping == 'beryl'
        # The fixture explicitly leaves its motor rows unmapped in Beryl.
        assert navigator._selected_region_ids == ()
        navigator.set_mapping('cosmos')
        navigator.slices.set_position(ap=1, ml=4, dv=1, units='voxel')
        navigator.slices.select_region()
        assert navigator._selected_region_ids == (315,)
        navigator.slices.select_region()
        assert navigator._selected_region_ids == ()
        navigator._probe_presentation.set_path([[-1, 0, 0], [1, 0, 0]])
        navigator._probe_presentation.set_sites([[0, 0, 0]])
        assert navigator.probe is not None and navigator.probe_sites is not None
        loader = navigator._linked._slice_loader
    assert loader._executor._closed
    assert ('destroy_scene',) in native.calls


def test_volume_free_flag_keeps_supplied_volume_as_cpu_source_without_rendering(source):
    with AtlasViewer(
        AtlasMesh.from_pack(MESH),
        source,
        layout='linked',
        render_volume=False,
        datoviz=VolumeForbiddenDatoviz(),
    ) as navigator:
        assert navigator._linked.volumes is source and navigator._linked.slice_source is source
        assert navigator._linked.volume is None and navigator._linked.volume_field is None


def test_volume_free_surface_alpha_uses_base_policy(source, monkeypatch):
    with AtlasViewer.from_slice_source(
        AtlasMesh.from_pack(MESH), source, datoviz=VolumeForbiddenDatoviz()
    ) as navigator:
        delegated = []
        monkeypatch.setattr(
            AtlasViewer, '_update_surface_alpha_mode_base', lambda self: delegated.append(self)
        )
        navigator._update_surface_alpha_mode()
        assert delegated == [navigator]


def test_positive_opacity_volume_preserves_existing_blended_surface_policy():
    navigator = AtlasViewer.__new__(AtlasViewer)
    navigator._linked = LinkedSlices.__new__(LinkedSlices)
    navigator._linked.viewer = navigator
    navigator._linked.render_volume = True
    navigator._linked.volume_opacity = 0.24
    navigator._surface_presentation = SimpleNamespace(alpha_mode=None)
    navigator.dvz = VolumeForbiddenDatoviz()
    navigator.mesh = SimpleNamespace(name='mesh')
    navigator._update_surface_alpha_mode()
    assert navigator._surface_presentation.alpha_mode == navigator.dvz.DVZ_ALPHA_BLENDED


@pytest.mark.parametrize(
    ('kwargs', 'message'),
    [({}, 'requires atlas volumes'), ({'render_volume': False}, 'explicit slice_source')],
)
def test_missing_source_fails_before_native_allocation(kwargs, message):
    native = VolumeForbiddenDatoviz()
    with pytest.raises(ValueError, match=message):
        AtlasViewer(AtlasMesh.from_pack(MESH), layout='linked', datoviz=native, **kwargs)
    assert native.calls == []


def test_slice_source_factory_rejects_volume_enable(source):
    with pytest.raises(ValueError, match='render_volume=False'):
        AtlasViewer.from_slice_source(AtlasMesh.from_pack(MESH), source, render_volume=True)


def test_slice_reference_and_catalog_validation_precede_native_creation(source):
    mesh = AtlasMesh.from_pack(MESH)
    bad = replace(source, regions=replace(source.regions, reference_space_id='wrong-space'))
    with pytest.raises(ValueError, match='slice reference spaces'):
        AtlasViewer.from_slice_source(mesh, bad)
    incompatible = open_volume_pack(FIXTURES / 'volume-pack-v1' / 'pack').load_volumes()
    with pytest.raises(ValueError, match='IDs are absent'):
        AtlasViewer.from_slice_source(mesh, incompatible)


def verified_assets():
    return MaterializedRegisteredAssets(
        Path('/verified'),
        'registered-pack',
        MappingProxyType({}),
        MappingProxyType(
            {axis: SimpleNamespace(world_slice_axis=axis) for axis in ('ap', 'ml', 'dv')}
        ),
        3,
        42,
    )


def test_registered_slice_factory_never_opens_dense_volume_pack(monkeypatch):
    assets, catalog, intensity, mesh, source = (
        verified_assets(),
        object(),
        object(),
        object(),
        object(),
    )
    monkeypatch.setattr(
        'ibl_datoviz.viewer.open_volume_pack',
        lambda *args: pytest.fail('volume-free registered factory opened a dense volume pack'),
    )
    monkeypatch.setattr('ibl_datoviz.viewer.open_intensity_block_pack', lambda path: intensity)
    monkeypatch.setattr('ibl_datoviz.viewer.AtlasMesh.from_pack', lambda path: mesh)

    def slices(actual_intensity, projections, actual_catalog):
        assert actual_intensity is intensity and actual_catalog is catalog
        assert projections == dict(assets.projections)
        return source

    def init(self, actual_mesh, actual_volumes=None, **kwargs):
        self.inputs = actual_mesh, actual_volumes, kwargs

    monkeypatch.setattr('ibl_datoviz.viewer.AtlasSliceSource', slices)
    monkeypatch.setattr(AtlasViewer, '__init__', init)
    navigator = AtlasViewer.from_registered_slices('mesh', 'intensity', assets, catalog=catalog)
    assert navigator.inputs == (
        mesh,
        None,
        {'layout': 'linked', 'slice_source': source, 'render_volume': False},
    )


def test_registered_slice_factory_requires_verified_assets():
    with pytest.raises(TypeError, match='verified MaterializedRegisteredAssets'):
        AtlasViewer.from_registered_slices('mesh', 'intensity', object(), catalog=object())


def test_registered_slice_factory_builds_real_lazy_source_without_dense_pack(monkeypatch):
    root = FIXTURES / 'linked-registered-slices-v1' / 'pack'
    intensity = open_intensity_block_pack(FIXTURES / 'intensity-blocks-v1' / 'pack')
    anatomy = open_anatomy_pack(
        root / 'anatomy-v2.json',
        reference_space_id=intensity.reference_space_id,
        grid_id=intensity.grid_id,
    )
    assets = MaterializedRegisteredAssets(
        root, 'synthetic-registered', {}, anatomy.projections, 3, 42
    )
    catalog = open_region_catalog(VOLUME / 'regions.json')
    monkeypatch.setattr(
        'ibl_datoviz.viewer.open_volume_pack',
        lambda *args: pytest.fail('registered slices opened a dense volume pack'),
    )
    with AtlasViewer.from_registered_slices(
        MESH,
        FIXTURES / 'intensity-blocks-v1' / 'pack',
        assets,
        catalog=catalog,
        datoviz=VolumeForbiddenDatoviz(),
    ) as navigator:
        assert navigator._linked.volumes is None and navigator._linked.volume is None
        assert navigator.catalog is catalog
        assert navigator._linked.slice_resolution_label == '10 um'
        assert navigator._linked._slice_loader is not None
        assert all(
            anatomy.shape[-1] == 4 for anatomy, _ in navigator._linked.prepared_slices.values()
        )


def test_volume_free_gui_omits_volume_opacity_control(source, monkeypatch):
    native = VolumeForbiddenDatoviz()
    labels = []
    monkeypatch.setattr(
        native,
        'dvz_gui_slider_float',
        lambda gui, label, *args: labels.append(label) or False,
        raising=False,
    )
    monkeypatch.setattr(native, 'dvz_gui_checkbox', lambda *args: False, raising=False)
    with AtlasViewer.from_slice_source(
        AtlasMesh.from_pack(MESH), source, datoviz=native
    ) as navigator:
        navigator._linked._draw_layer_gui(object())
    assert b'Annotation opacity' in labels and b'Volume opacity' not in labels


def test_volume_free_worker_failure_keeps_missing_section_explicit(source):
    class MissingSection:
        def __getattr__(self, name):
            return getattr(source, name)

        def slice(self, volume, axis, index):
            if index == 0:
                raise FileNotFoundError('registered section is absent')
            return source.slice(volume, axis, index)

    with AtlasViewer.from_slice_source(
        AtlasMesh.from_pack(MESH), MissingSection(), datoviz=VolumeForbiddenDatoviz()
    ) as navigator:
        notified = Event()
        navigator._linked._slice_loader._executor._notify = lambda axis: notified.set()
        navigator._linked._slice_loader.submit(SliceRequest('ap', 0, 1))
        assert notified.wait(2)
        with pytest.raises(FileNotFoundError, match='section is absent'):
            navigator._linked._slice_loader.drain_ready()
        loader = navigator._linked._slice_loader
    assert loader._executor._closed


def test_native_volume_free_linked_navigator_has_only_2d_fields(source):
    try:
        import datoviz as dvz  # noqa: PLC0415 - unavailable native runtime is a test skip.

        fields = []

        class Guard:
            def __getattr__(self, name):
                return getattr(dvz, name)

            def dvz_volume(self, *args):
                pytest.fail('volume-free navigator allocated a native volume')

            def dvz_sampled_field_from_array(self, scene, data, **kwargs):
                assert kwargs.get('dim') == dvz.DVZ_FIELD_DIM_2D
                assert data.ndim == 3 and data.shape[-1] == 4
                fields.append(kwargs)
                return dvz.dvz_sampled_field_from_array(scene, data, **kwargs)

        with AtlasViewer.from_slice_source(
            AtlasMesh.from_pack(MESH), source, width=320, height=240, datoviz=Guard()
        ) as navigator:
            assert navigator._linked.volume is None and navigator._linked.volume_field is None
            navigator.slices.set_position(ap=1, ml=4, dv=1, units='voxel', select_region=True)
            assert navigator._selected_region_ids == (315,)
            navigator.set_mapping('beryl')
            navigator.set_mapping('allen')
            navigator._probe_presentation.set_path([[-1, 0, 0], [1, 0, 0]])
            navigator._probe_presentation.set_sites([[0, 0, 0]])
            pixels = navigator.render_offscreen()
            assert pixels.shape == (240, 320, 4)
            assert np.count_nonzero(np.any(pixels[..., :3] != [29, 33, 39], axis=2)) > 200
            assert fields and all(item['dim'] == dvz.DVZ_FIELD_DIM_2D for item in fields)
    except RuntimeError as error:
        if 'dvz_app() failed' in str(error) or 'Unable to load libdatoviz' in str(error):
            pytest.skip('Datoviz native runtime or GPU context is unavailable')
        raise
