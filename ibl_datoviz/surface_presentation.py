"""Owned anatomical surface presentation and atomic native-write recovery."""

from __future__ import annotations

from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

from .surface_style import SurfaceStyle

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy.typing import NDArray

    from .viewer import AtlasViewer


@dataclass(frozen=True, slots=True)
class SurfacePresentationState:
    """Authored styles and last successfully applied native presentation state."""

    style: SurfaceStyle
    visible: bool
    face_mask: NDArray[np.bool_]
    uploaded_face_mask: NDArray[np.bool_]
    uploaded_face_mapping: str
    base_colors: NDArray[np.uint8] | None
    base_is_translucent: bool
    last_emphasis: tuple | None
    alpha_mode: int | None


@dataclass(frozen=True, slots=True)
class SurfaceSnapshot:
    """Retained scientific state and an immutable owned native color payload."""

    viewer_state: Mapping[str, object]
    presentation: SurfacePresentationState
    colors: NDArray[np.uint8]
    mapping_control: int
    probe_state: tuple


class SurfacePresentation:
    """Own surface styles/caches and coordinate rollback of dependent presentation."""

    def __init__(self, viewer: AtlasViewer, mesh, mapping):
        self.viewer = viewer
        self.style = SurfaceStyle(mesh)
        self.visible = True
        self.face_mask = np.ones(len(mesh.face_presentation_ids), dtype=bool)
        self.uploaded_face_mask = self.face_mask.copy()
        self.uploaded_face_mapping = mapping
        self.base_colors = None
        self.base_is_translucent = False
        self.last_emphasis = None
        self.alpha_mode = None

    def snapshot(self) -> SurfaceSnapshot:
        """Retain public state, caches and owned native payloads before mutations."""
        names = (
            'mapping',
            'selection_presentation',
            'anatomy_presentation',
            'context_opacity',
            '_selection_face_state',
            'palette',
            'tree_model',
            '_selector_model',
            '_selector_mapping',
            'region_data',
            '_region_value_range',
            '_region_color_scheme',
            '_region_opacity',
            'surface_opacity',
            '_selected_region_ids',
            '_hovered_region_ids',
            '_highlight_region_ids',
            '_last_mesh_region_ids',
        )
        state = MappingProxyType({name: getattr(self.viewer, name) for name in names})
        presentation = SurfacePresentationState(
            **{field.name: getattr(self, field.name) for field in fields(SurfacePresentationState)}
        )
        colors = self.base_colors
        if colors is None:
            colors = self.viewer._display_surface_colors()
        # Immutable backing bytes prevent a caller from re-enabling writes to
        # the retained rollback payload, including through a view of the array.
        colors = np.frombuffer(np.ascontiguousarray(colors).tobytes(), dtype=np.uint8).reshape(
            colors.shape
        )
        return SurfaceSnapshot(
            state,
            presentation,
            colors,
            self.viewer._mapping_control.value,
            self.viewer._probe_presentation.snapshot_state(),
        )

    def restore(self, snapshot: SurfaceSnapshot, widgets=()):
        """Restore geometry, identity, colors and mode; close on any rollback failure."""
        try:
            for name, value in snapshot.viewer_state.items():
                setattr(self.viewer, name, value)
            for field in fields(SurfacePresentationState):
                setattr(self, field.name, getattr(snapshot.presentation, field.name))
            self.viewer._probe_presentation.restore_state(snapshot.probe_state)
            self.viewer._mapping_control.value = snapshot.mapping_control
            mask = self.uploaded_face_mask
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_index_data(
                    self.viewer.mesh,
                    self.viewer._surface_mesh.indices.reshape(-1, 3)[mask].reshape(-1).copy(),
                ),
                'surface transaction index rollback',
            )
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_target_link_keys(
                    self.viewer.mesh,
                    self.viewer.dvz.DVZ_SCENE_TARGET_FACE,
                    self.viewer.link_channel,
                    self.viewer._surface_mesh.face_mapping_ids(self.uploaded_face_mapping)[mask]
                    .view(np.uint64)
                    .copy(),
                ),
                'surface transaction key rollback',
            )
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_data(self.viewer.mesh, 'color', snapshot.colors),
                'surface transaction color rollback',
            )
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_alpha_mode(self.viewer.mesh, self.alpha_mode),
                'surface transaction alpha rollback',
            )
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_visible(
                    self.viewer.mesh, self.visible and bool(np.any(self.face_mask))
                ),
                'surface transaction visibility rollback',
            )
            self.viewer._probe_presentation.restore_keys()
            self.viewer._selection_envelope_visible = None
            self.viewer._update_selection_envelope_visibility()
            self.viewer._surface_state.invalidate()
            self.last_emphasis = None
            self.viewer._update_surface_emphasis()
            for widget in widgets:
                getattr(self.viewer, f'_replace_{widget}')()
            if self.viewer._selector_gui is not None and self.viewer.region_tree is not None:
                self.viewer._selector_gui.model = self.viewer._selector_model
                self.viewer._selector_gui.value_name = (
                    self.viewer.region_data.value_name
                    if self.viewer.region_data is not None
                    else 'Value'
                )
                self.viewer._selector_gui.upload(self.viewer._selector_model)
        except Exception as rollback_error:
            self.viewer.close()
            raise RuntimeError(
                'surface transaction rollback failed; viewer closed'
            ) from rollback_error

    def commit_style(self, candidate, *, opacity=None):
        """Apply one authored style candidate, restoring all native writes on failure."""
        self.viewer._invalidate_picking()
        snapshot = self.snapshot()
        self.style = candidate
        if opacity is not None:
            self.viewer.surface_opacity = opacity
        try:
            mask = self.viewer._visible_surface_faces(self.viewer.mapping)
            colors = self.viewer._display_surface_colors()
            self.viewer._upload_surface_faces(mask, self.viewer.mapping)
            self.viewer._check(
                self.viewer.dvz.dvz_visual_set_data(self.viewer.mesh, 'color', colors),
                'region style colors',
            )
            self.face_mask = mask
            self.viewer._invalidate_surface_emphasis_cache(colors)
            self.viewer._clear_surface_hover()
            self.viewer._update_surface_emphasis()
        except Exception:
            if not self.viewer._closed:
                self.restore(snapshot)
            raise
