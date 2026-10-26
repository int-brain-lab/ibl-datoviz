"""Opt-in signed selection geometry and independent nonpickable atlas context."""

import ctypes

import numpy as np
import pytest

from ibl_anatomy import open_region_catalog
from ibl_datoviz import AtlasMesh, AtlasViewer
from ibl_datoviz.envelope import AtlasEnvelope
from tests import FIXTURES
from tests.test_atlas import FIXTURE, FakeDatoviz
from tests.test_region_selector_gui import InputDatoviz
from tests.test_surface_transactions import (
    TransactionNative,
    assert_native_restored,
    native_snapshot,
)


def make_viewer(**kwargs):
    return AtlasViewer(
        AtlasMesh.from_pack(FIXTURE),
        catalog=open_region_catalog(FIXTURES / 'linked-atlas-v1' / 'volume-pack' / 'regions.json'),
        selection_presentation='focus',
        datoviz=kwargs.pop('datoviz', FakeDatoviz()),
        **kwargs,
    )


def test_focus_signed_faces_and_opaque_draw_preserve_retained_geometry():
    with make_viewer() as viewer:
        original = viewer.mesh_data.indices.copy()
        viewer.set_selected_region_ids((-315,))
        assert viewer.visible_region_ids() == (-315,)
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_OPAQUE
        assert not viewer._surface_state.handle.active
        words = viewer._surface_state.words
        ids = viewer._surface_mesh.face_mapping_ids('allen')
        uploaded = [call[1] for call in viewer.dvz.calls if call[0] == 'indices'][-1]
        np.testing.assert_array_equal(
            uploaded, viewer._surface_mesh.indices.reshape(-1, 3)[ids < 0].reshape(-1)
        )
        presentation_ids = viewer._surface_state._mapped_ids()
        assert np.all(words[presentation_ids > 0] == 0)
        assert np.all(words[presentation_ids < 0] == viewer.dvz.DVZ_ITEM_STATE_SELECTED)
        viewer.set_selection_presentation('all')
        assert viewer.visible_region_ids() == (-315, 315)
        assert viewer.selected_region_ids() == (-315,)
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_OPAQUE
        viewer.set_selection_presentation('isolate')
        assert viewer.visible_region_ids() == (-315,)
        viewer.set_selection_presentation('legacy')
        assert viewer.visible_region_ids() == (-315, 315)
        assert viewer._surface_state.handle.active
        viewer.set_selection_presentation('focus')
        viewer.clear_selection()
        assert viewer.visible_region_ids() == (-315, 315)
        np.testing.assert_array_equal(viewer.mesh_data.indices, original)


def test_focus_authored_alpha_only_considers_rendered_selection():
    with make_viewer(palette={-315: (240, 20, 30, 255), 315: (20, 240, 30, 80)}) as viewer:
        viewer.set_selected_region_ids((-315,))
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_OPAQUE
        viewer.set_region_opacity(-315, 0.5)
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT
        viewer.set_selected_region_ids((315,))
        assert viewer._surface_presentation.alpha_mode == viewer.dvz.DVZ_ALPHA_WBOIT
        viewer.hide_region(315)
        assert viewer.visible_region_ids() == ()


def test_hover_only_updates_sparse_flags_in_focus(monkeypatch):
    with make_viewer() as viewer:
        viewer.set_selected_region_ids((-315,))

        def forbidden(*args, **kwargs):
            raise AssertionError('hover must retain dense geometry and colors')

        monkeypatch.setattr(viewer, '_visible_surface_faces', forbidden)
        monkeypatch.setattr(viewer, '_surface_is_translucent', forbidden)
        before = len(viewer.dvz.calls)
        viewer._set_hovered_region_ids((-315,))
        calls = viewer.dvz.calls[before:]
        assert any(call[0] == 'state_update' for call in calls)
        assert not any(call[0] in ('indices', 'data', 'data_many', 'link_keys') for call in calls)


def envelope(viewer):
    mesh = viewer.mesh_data
    return AtlasEnvelope.from_world_arrays(
        mesh.positions_um,
        mesh.normals,
        mesh.indices,
        mesh,
        reference_space=mesh.reference_space,
        variant='source-native',
    )


def test_context_is_neutral_nonpickable_and_obeys_isolate_explode_hemispheres(monkeypatch):
    with make_viewer() as viewer:
        queries = []
        monkeypatch.setattr(
            viewer.dvz,
            'dvz_visual_set_query_capabilities',
            lambda visual, flags: queries.append(flags) or 0,
        )
        shell = envelope(viewer)
        viewer.set_selection_envelope(shell)
        assert viewer.selection_envelope is shell
        assert not viewer._selection_envelope_visible
        assert queries == [0]
        viewer.set_selected_region_ids((-315,))
        assert viewer._selection_envelope_visible
        viewer.set_selection_presentation('isolate')
        assert not viewer._selection_envelope_visible
        viewer.set_selection_presentation('focus')
        viewer.set_explode(0.25)
        assert not viewer._selection_envelope_visible
        viewer.set_explode(0)
        assert viewer._selection_envelope_visible
        viewer.set_hemisphere('left')
        assert not viewer._selection_envelope_visible
        viewer.set_hemisphere('both')
        assert viewer._selection_envelope_visible
        viewer.set_surface_visible(False)
        assert not viewer._selection_envelope_visible
        viewer.set_surface_visible(True)
        assert viewer._selection_envelope_visible
        viewer.clear_selection()
        assert not viewer._selection_envelope_visible


@pytest.mark.parametrize('failure', ['indices', 'keys', 'alpha', 'state', 'visibility'])
def test_failed_focus_selection_restores_geometry_keys_alpha_flags_and_ids(failure):
    native = TransactionNative()
    with make_viewer(
        datoviz=native, palette={-315: (240, 20, 30, 255), 315: (20, 240, 30, 80)}
    ) as viewer:
        before = native_snapshot(viewer)
        native.arm(**{failure: (1,)})
        with pytest.raises(RuntimeError):
            viewer.set_selected_region_ids((-315,))
        assert viewer.selected_region_ids() == ()
        assert viewer.visible_region_ids() == (-315, 315)
        assert not viewer._closed
        assert_native_restored(viewer, before)


def test_focus_mapping_clear_restores_whole_atlas_and_styles():
    with make_viewer() as viewer:
        viewer.set_selected_region_ids((-315,))
        viewer.set_mapping('cosmos')
        assert viewer.selected_region_ids() == ()
        assert viewer.visible_region_ids() == (-315, 315)


def test_focus_parent_descendants_preserve_selected_side():
    with make_viewer() as viewer:
        viewer.set_selected_region_ids((-8,))
        assert viewer._signed_focus_ids() == (-315, -8)
        assert viewer.visible_region_ids() == (-315,)
        viewer.set_selected_region_ids((8,))
        assert viewer._signed_focus_ids() == (8, 315)
        assert viewer.visible_region_ids() == (315,)
        viewer.set_selected_region_ids((-8, 8))
        assert viewer.visible_region_ids() == (-315, 315)


@pytest.mark.parametrize('operation', ['presentation', 'style', 'mapping', 'empty'])
def test_focus_failures_preserve_committed_masks_and_authoring(operation):
    native = TransactionNative()
    with make_viewer(datoviz=native) as viewer:
        viewer.set_selected_region_ids((-315,))
        before = native_snapshot(viewer)
        native.arm(visibility=(1,))
        changes = {
            'presentation': lambda: viewer.set_selection_presentation('all'),
            'style': lambda: viewer.set_region_opacity(-315, 0),
            'mapping': lambda: viewer.set_mapping('cosmos'),
            'empty': lambda: viewer.set_selected_region_ids((12345,)),
        }
        # No catalog validation is needed to exercise an empty native face set.
        if operation == 'empty':
            viewer.tree_model = None
        with pytest.raises(RuntimeError):
            changes[operation]()
        assert viewer.selection_presentation == 'focus'
        assert viewer.mapping == 'allen'
        assert viewer.selected_region_ids() == (-315,)
        assert viewer.visible_region_ids() == (-315,)
        assert not viewer._surface_presentation.style.regions
        assert_native_restored(viewer, before)


@pytest.mark.parametrize('rollback_fails', [False, True])
def test_explode_failure_restores_positions_controls_and_context_or_closes(
    monkeypatch, rollback_fails
):
    with make_viewer() as viewer:
        viewer.set_selection_envelope(envelope(viewer))
        viewer.set_selected_region_ids((-315,))
        original = viewer.dvz.dvz_visual_set_visible
        attempts = []

        def fail_shell(visual, visible):
            if visual is viewer._selection_envelope_visual:
                attempts.append(bool(visible))
                if len(attempts) == 1 or rollback_fails:
                    return -1
            return original(visual, visible)

        monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_visible', fail_shell)
        with pytest.raises(RuntimeError):
            viewer.set_explode(0.5)
        assert viewer.explode == 0
        assert viewer._explode_control.value == 0
        assert viewer._closed == rollback_fails
        if not rollback_fails:
            assert viewer._selection_envelope_visible
            positions = [
                call[3] for call in viewer.dvz.calls if call[:3] == ('data', 'mesh', 'position')
            ]
            np.testing.assert_array_equal(
                positions[-1], viewer._surface_mesh.exploded_positions(0)
            )


def test_replacing_visible_shell_failure_restores_actual_old_visual(monkeypatch):
    with make_viewer() as viewer:
        visibility = {}
        destroyed = []

        def track_visibility(visual, visible):
            visibility[id(visual)] = bool(visible)
            return 0

        monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_visible', track_visibility)
        monkeypatch.setattr(
            viewer.dvz,
            'dvz_visual_destroy',
            lambda visual: destroyed.append(visual),
            raising=False,
        )
        first = envelope(viewer)
        viewer.set_selection_envelope(first)
        viewer.set_selected_region_ids((-315,))
        previous = viewer._selection_envelope_visual
        assert visibility[id(previous)]
        failed = []

        def fail_after_hiding_previous(visual, visible):
            track_visibility(visual, visible)
            if visual is previous and not visible and not failed:
                failed.append(visual)
                return -1
            return 0

        monkeypatch.setattr(viewer.dvz, 'dvz_visual_set_visible', fail_after_hiding_previous)
        with pytest.raises(RuntimeError):
            viewer.set_selection_envelope(envelope(viewer))
        assert viewer.selection_envelope is first
        assert viewer._selection_envelope_visual is previous
        assert viewer._selection_envelope_visible
        assert visibility[id(previous)]
        assert len(destroyed) == 1 and destroyed[0] is not previous
        assert not visibility[id(destroyed[0])]


def test_fit_workarea_is_explicit_host_logical_window_descriptor(monkeypatch):
    class Descriptor(ctypes.Structure):
        _fields_ = [
            ('size_policy', ctypes.c_int),
            ('size_width', ctypes.c_double),
            ('size_height', ctypes.c_double),
            ('title', ctypes.c_char_p),
            ('fit_workarea', ctypes.c_bool),
        ]

    with make_viewer(fit_workarea=True, width=2800, height=2000) as viewer:
        native = viewer.dvz
        monkeypatch.setattr(native, 'DVZ_VIEW_WINDOW', 1, raising=False)
        monkeypatch.setattr(native, 'DVZ_VIEW_SIZE_HOST_LOGICAL_PX', 1, raising=False)
        monkeypatch.setattr(native, 'dvz_view_desc', lambda kind: Descriptor(), raising=False)
        descriptors = []
        monkeypatch.setattr(
            native,
            'dvz_view',
            lambda app, figure, desc: descriptors.append(desc._obj) or 'window',
            raising=False,
        )
        assert viewer._create_window_view(viewer.figure, '3D atlas') == 'window'
        descriptor = descriptors[0]
        assert descriptor.size_policy == native.DVZ_VIEW_SIZE_HOST_LOGICAL_PX
        assert (descriptor.size_width, descriptor.size_height) == (2800, 2000)
        assert descriptor.title == b'3D atlas'
        assert descriptor.fit_workarea


def test_reset_view_keeps_selection_styles_and_explode(monkeypatch):
    native = InputDatoviz()
    with make_viewer(datoviz=native) as viewer:
        viewer.set_selected_region_ids((-315,))
        viewer.set_region_color(-315, (210, 40, 50))
        viewer.set_explode(0.4)
        viewer.arcball = object()
        native.buttons = {b'Reset view'}
        monkeypatch.setattr(native, 'dvz_gui_slider_float', lambda *args: False, raising=False)
        reset = []
        monkeypatch.setattr(
            native, 'dvz_arcball_reset', lambda arcball: reset.append(arcball) or 0, raising=False
        )
        monkeypatch.setattr(
            viewer,
            'set_camera_angles',
            lambda *_: pytest.fail('Reset must use the native initial pose, not a later pose'),
        )
        viewer._draw_viewport_toolbar_gui(None)
        assert reset == [viewer.arcball]
        assert viewer.selected_region_ids() == (-315,)
        assert viewer.explode == 0.4
        assert viewer._surface_presentation.style.regions[('allen', -315)].color == (210, 40, 50)
        assert native.combo_values[b'##selection_presentation'] == 0
