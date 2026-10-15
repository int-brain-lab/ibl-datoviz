"""Datoviz v0.4 atlas viewer with explicit native object ownership."""

from __future__ import annotations

import ctypes
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import datoviz as dvz
import numpy as np

from ibl_anatomy import (
    AtlasAssetSet,
    AtlasRegionCatalog,
    MaterializedAtlasAssets,
    bundled_asset_set,
    verify_materialized_asset_set,
)

from .atlas import AtlasMesh
from .context import AnatomicalContext, AtlasContextSurface
from .envelope import AtlasEnvelope
from .gui_data import create_probe_table, create_region_table, create_region_tree
from .insertions import InsertionCollectionVisual
from .ontology import AtlasTreeModel
from .presentation import region_presentation, scalar_colors
from .region_browser import RegionBrowserSidebar
from .region_selector_gui import RegionSelectorGui, selector_from_tree, signed_selection
from .selection import (
    mesh_ids_from_keys,
    probe_selected_ids,
    region_ids_from_keys,
    selected_row_keys,
    selection_decision,
    tree_selection_keys,
)
from .surface_geometry import SurfaceGeometry
from .surface_state import SurfaceState
from .surface_style import SurfaceStyle
from .viewport_input import ViewportInputAdapter

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import ModuleType
    from typing import Literal

    from numpy.typing import NDArray

    from .probe import ProbeSites
    from .regions import AtlasRegionValues


class RegionalView(NamedTuple):
    """Named presentation with viewer-specific tree labels; tuple adapter retained."""

    region_ids: NDArray[np.int64]
    values: NDArray[np.float64]
    weights: NDArray[np.float64]
    labels: tuple[str, ...]
    colors: NDArray[np.uint8]


class ProbeUpload(NamedTuple):
    """One owned upload snapshot for recovery after a native setter failure."""

    positions: NDArray[np.float32]
    colors: NDArray[np.uint8]
    radii: NDArray[np.float32]
    keys: NDArray[np.uint64]

    def attributes(self):
        """Return the native sphere attributes without copying the snapshot."""
        return {'position': self.positions, 'color': self.colors, 'radius': self.radii}


class AtlasViewer:
    """Own one Datoviz scene displaying an immutable atlas mesh pack."""

    def __init__(  # noqa: PLR0912, PLR0915
        self,
        mesh: AtlasMesh,
        *,
        mapping: str = 'allen',
        palette: Mapping[int, Sequence[int]] | None = None,
        catalog: AtlasRegionCatalog | None = None,
        width: int = 900,
        height: int = 720,
        camera_angles: Sequence[float] = (-0.35, 0.25, 0.12),
        explode: float = 0.0,
        selection_dim_factor: float = 0.42,
        selection_context_opacity: float = 0.18,
        selection_presentation: str = 'legacy',
        selection_envelope: AtlasEnvelope | None = None,
        surface_opacity: float = 1.0,
        anatomy_presentation: str = 'detailed',
        anatomical_context: Sequence[AtlasContextSurface] = (),
        context_opacity: float = 0.12,
        ui_scale: float = 1.0,
        sidebar_width: float = 400.0,
        tree_root_acronym: str = 'grey',
        enable_interaction: bool = True,
        enable_hover: bool = True,
        fit_workarea: bool = False,
        datoviz: ModuleType | None = None,
    ) -> None:
        if anatomy_presentation not in ('major', 'detailed'):
            raise ValueError('anatomy presentation must be major or detailed')
        if not np.isfinite(context_opacity) or not 0 <= context_opacity <= 1:
            raise ValueError('context opacity must be between zero and one')
        if selection_presentation not in ('legacy', 'focus', 'isolate', 'all'):
            raise ValueError('selection presentation must be legacy, focus, isolate or all')
        if not np.isfinite(selection_dim_factor) or not 0 <= selection_dim_factor <= 1:
            raise ValueError('selection_dim_factor must be between zero and one')
        if not np.isfinite(selection_context_opacity) or not 0 <= selection_context_opacity <= 1:
            raise ValueError('selection_context_opacity must be between zero and one')
        if not np.isfinite(explode) or not 0 <= explode <= 1:
            raise ValueError('explode must be between zero and one')
        if not np.isfinite(surface_opacity) or not 0 <= surface_opacity <= 1:
            raise ValueError('surface_opacity must be between zero and one')
        if not np.isfinite(ui_scale) or ui_scale <= 0:
            raise ValueError('ui_scale must be finite and positive')
        if not np.isfinite(sidebar_width) or sidebar_width <= 0:
            raise ValueError('sidebar_width must be finite and positive')
        if not tree_root_acronym:
            raise ValueError('tree_root_acronym must not be empty')
        if mapping not in mesh.mapping_names:
            raise ValueError(f'unknown atlas mapping: {mapping}')
        self.camera_angles = self._validated_camera_angles(camera_angles)
        self.dvz = dvz if datoviz is None else datoviz
        self.mesh_data = mesh
        self._surface_geometry = SurfaceGeometry.from_mesh(mesh)
        self._surface_mesh = self._surface_geometry.mesh
        self._surface_style = SurfaceStyle(self._surface_mesh)
        self._surface_visible = True
        self._surface_face_mask = np.ones(
            len(self._surface_mesh.face_presentation_ids), dtype=bool
        )
        self._uploaded_face_mask = self._surface_face_mask.copy()
        self._uploaded_face_mapping = mapping
        self._anatomical_context = None
        self.anatomy_presentation = anatomy_presentation
        self.context_opacity = float(context_opacity)
        self._insertions = None
        self._surface_state = None
        self.mapping = mapping
        self.catalog = catalog
        self.tree_model = AtlasTreeModel.from_catalog(catalog, mapping) if catalog else None
        self.palette = self.tree_model.palette if palette is None and self.tree_model else palette
        self.width = width
        self.height = height
        self.explode = float(explode)
        self.selection_presentation = selection_presentation
        self.selection_envelope = None
        self._selection_envelope_visual = None
        self._selection_envelope_visible = False
        self._selection_face_state = None
        self.selection_dim_factor = selection_dim_factor
        self.selection_context_opacity = selection_context_opacity
        self.surface_opacity = surface_opacity
        self.ui_scale = float(ui_scale)
        self.sidebar_width = float(sidebar_width)
        self._sidebar = RegionBrowserSidebar(self)
        self.tree_root_acronym = tree_root_acronym
        self.enable_interaction = bool(enable_interaction)
        self.enable_hover = bool(enable_hover)
        self.fit_workarea = bool(fit_workarea)
        self._closed = False
        self._gui_callback_depth = 0
        self._close_pending = False
        self._gui_callback_error = None
        self.scene = None
        self.app, self.view, self.arcball, self.arcball_controller = None, None, None, None
        self.figure, self.panel, self.mesh, self.probe = None, None, None, None
        self.host_figure = None
        self.viewport = None
        self.interaction = None
        self._viewport_input = None
        self.region_tree, self.region_table = None, None
        self.probe_table = None
        self._gui_widgets = {}
        self._selector_model = self._selector_gui = None
        self._selector_mapping = None
        self.gui = None
        self.probe_sites = None
        self._probe_sites_pending = None
        self._probe_pending = None
        self._probe_upload: ProbeUpload | None = None
        self.probe_data: ProbeSites | None = None
        self.region_data: AtlasRegionValues | None = None
        self._probe_colors: NDArray[np.uint8] | None = None
        self._region_value_range: tuple[float, float] | None = None
        self._region_color_scheme: Literal['diverging', 'sequential'] = 'sequential'
        self._region_opacity: float | None = None
        self._mapping_control, self._tree_filter = (
            ctypes.c_int(mesh.mapping_names.index(mapping)),
            ctypes.create_string_buffer(256),
        )
        self._explode_control = ctypes.c_float(self.explode)
        self._mapping_items = (ctypes.c_char_p * len(mesh.mapping_names))(
            *(name.title().encode() for name in mesh.mapping_names)
        )
        self._selected_region_ids: tuple[int, ...] = ()
        self._hovered_region_ids: tuple[int, ...] = ()
        self._highlight_region_ids: tuple[int, ...] = ()
        self._last_surface_emphasis: tuple[tuple[int, ...], tuple[int, ...], str] | None = None
        self._surface_base_colors_cache: NDArray[np.uint8] | None = None
        self._surface_base_is_translucent = False
        self._surface_alpha_mode: int | None = None
        self._last_mesh_region_ids: tuple[int, ...] = ()
        try:
            self.scene = self.dvz.dvz_scene()
            if not self.scene:
                raise RuntimeError('dvz_scene() failed')
            self._create_layout()
            self._create_surface()
            if anatomical_context:
                self.set_anatomical_context(anatomical_context)
            if selection_envelope is not None:
                self.set_selection_envelope(selection_envelope)
            if self.enable_interaction:
                interaction_desc = self.dvz.dvz_item_interaction_desc()
                interaction_desc.target = self.dvz.DVZ_SCENE_TARGET_FACE
                interaction_desc.hover_enabled = self.enable_hover
                interaction_desc.selection_enabled = True
                self.interaction = self.dvz.dvz_item_interaction(
                    self.panel, ctypes.byref(interaction_desc)
                )
                if not self.interaction:
                    raise RuntimeError('dvz_item_interaction() failed')
        except Exception:
            # Avoid virtual dispatch into a partially initialized subclass.
            AtlasViewer.close(self)
            raise

    def _create_layout(self) -> None:
        """Create the figure and primary 3-D panel."""
        self.figure = self.dvz.dvz_figure(self.scene, self.width, self.height, 0)
        if not self.figure:
            raise RuntimeError('dvz_figure() failed')
        self.panel = self.dvz.dvz_panel_full(self.figure)
        if not self.panel:
            raise RuntimeError('dvz_panel_full() failed')
        self.dvz.dvz_panel_set_background_color(self.panel, self.dvz.DvzColor(29, 33, 39, 255))
        self._configure_3d_camera()

    def _configure_3d_camera(self) -> None:
        """Apply an explicit perspective camera to the normalized atlas geometry."""
        camera = self.dvz.dvz_camera_desc()
        camera.view.eye[:] = (0.0, 0.0, 3.0)
        camera.view.target[:] = (0.0, 0.0, 0.0)
        camera.view.up[:] = (0.0, 1.0, 0.0)
        camera.projection.fov_y = 0.72
        camera.projection.near_clip = 0.01
        camera.projection.far_clip = 100.0
        self._check(
            self.dvz.dvz_panel_set_camera_desc(self.panel, camera),
            '3-D perspective camera setup',
        )

    @classmethod
    def from_pack(cls, path: str | Path, **kwargs) -> AtlasViewer:
        """Create a viewer from a verified local mesh pack."""
        return cls(AtlasMesh.from_pack(path), **kwargs)

    @classmethod
    def from_assets(cls, assets: MaterializedAtlasAssets, **kwargs) -> AtlasViewer:
        """Create a viewer from an already verified shared atlas asset graph."""
        if 'catalog' in kwargs:
            raise TypeError('from_assets() supplies the verified region catalog')
        return cls(AtlasMesh.from_geometry(assets.geometry), catalog=assets.regions, **kwargs)

    @classmethod
    def from_asset_set(
        cls,
        root: str | Path,
        *,
        asset_set: AtlasAssetSet | None = None,
        **kwargs,
    ) -> AtlasViewer:
        """Verify a materialized shared asset set and create its linked viewer."""
        lock = bundled_asset_set() if asset_set is None else asset_set
        return cls.from_assets(verify_materialized_asset_set(lock, root), **kwargs)

    @staticmethod
    def _check(result: int, action: str) -> None:
        if result != 0:
            raise RuntimeError(f'Datoviz {action} failed')

    @staticmethod
    def _validated_camera_angles(angles: Sequence[float]) -> tuple[float, float, float]:
        values = np.asarray(angles, dtype=np.float32)
        if values.shape != (3,) or not np.isfinite(values).all():
            raise ValueError('camera angles must contain three finite Euler angles')
        return tuple(float(value) for value in values)

    def set_camera_angles(self, angles: Sequence[float]) -> None:
        """Set stored arcball Euler angles and update an active view immediately."""
        self._require_open()
        self.camera_angles = self._validated_camera_angles(angles)
        if self.arcball is not None:
            native = (ctypes.c_float * 3)(*self.camera_angles)
            self._check(self.dvz.dvz_arcball_set(self.arcball, native), 'arcball update')

    def _surface_colors(
        self,
        mapping: str,
        palette: Mapping[int, Sequence[int]] | None,
    ) -> NDArray[np.uint8]:
        colors = self._surface_mesh.colors(mapping, palette)
        colors = self._surface_style.apply(mapping, colors)
        if self.surface_opacity == 1:
            return colors
        colors = colors.copy()
        colors[:, 3] = np.rint(colors[:, 3].astype(np.float32) * self.surface_opacity).astype(
            np.uint8
        )
        return colors

    def _create_surface(self) -> None:
        self.mesh = self.dvz.dvz_mesh(self.scene, 0)
        if not self.mesh:
            raise RuntimeError('dvz_mesh() failed')
        # Datoviz's physically linear defaults use a deliberately weak ambient
        # term.  That is too directional for an atlas, where every camera angle
        # must retain anatomical context and categorical colors must stay
        # legible.  Use a broad fill light and a restrained Phong response.
        ambient_light = self.dvz.dvz_scene_default_ambient(self.scene)
        if not ambient_light:
            raise RuntimeError('Datoviz scene has no default ambient light')
        self._check(
            self.dvz.dvz_light_set_intensity(ambient_light, 0.65),
            'atlas ambient light setup',
        )
        material = self.dvz.dvz_phong_material_desc()
        material.phong.ambient = 1.0
        material.phong.diffuse = 0.45
        material.phong.specular = 0.08
        material.phong.shininess = 24.0
        self._check(
            self.dvz.dvz_visual_set_material(self.mesh, material),
            'atlas surface material setup',
        )
        surface_colors = self._display_surface_colors()
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.mesh,
                {
                    'position': self._surface_mesh.exploded_positions(self.explode),
                    'normal': self._surface_mesh.normals,
                    'color': surface_colors,
                },
            ),
            'dense mesh upload',
        )
        self._invalidate_surface_emphasis_cache(surface_colors)
        self._update_surface_alpha_mode()
        self._check(
            self.dvz.dvz_visual_set_index_data(self.mesh, self._surface_mesh.indices),
            'mesh index upload',
        )
        if self._surface_geometry.requires_fragment_clip:
            self._check(
                self.dvz.dvz_mesh_set_fragment_clip(
                    self.mesh, self._surface_geometry.fragment_clip
                ),
                'source hemisphere fragment coverage',
            )
        if self.enable_interaction:
            self._check(
                self.dvz.dvz_visual_set_query_capabilities(
                    self.mesh, self.dvz.DVZ_QUERY_CAPABILITY_FACE
                ),
                'mesh picking capability',
            )
        self.link_channel = self.dvz.dvz_link_channel(self.scene, b'atlas-region')
        self._check(
            self.dvz.dvz_visual_set_target_link_keys(
                self.mesh,
                self.dvz.DVZ_SCENE_TARGET_FACE,
                self.link_channel,
                self._surface_mesh.link_keys(self.mapping),
            ),
            'mesh region link keys',
        )
        self._check(self.dvz.dvz_panel_add_visual(self.panel, self.mesh, None), 'mesh attach')
        self._surface_state = SurfaceState(self)
        mask = self._visible_surface_faces(self.mapping)
        if not np.all(mask):
            self._upload_surface_faces(mask, self.mapping)
        self._surface_face_mask = mask

    def _authored_surface_alpha(self, mapping=None, palette=None):
        active = self.mapping if mapping is None else mapping
        palette = self.palette if palette is None else palette
        if self.region_data is None:
            colors = self._surface_style.apply(active, self._surface_mesh.colors(active, palette))
        else:
            prepared = self._region_value_view(
                self.region_data,
                active,
                self._region_value_range,
                self._region_color_scheme,
                1.0 if self._region_opacity is None else self._region_opacity,
            )
            colors = self._region_surface_colors(
                active,
                prepared.region_ids,
                prepared.colors,
                context_opacity=1.0,
            )
        return colors[:, 3].copy()

    def _visible_surface_faces(self, mapping, palette=None, *, include_selection=True):
        mask = self._surface_style.visible_faces(mapping)
        alpha = self._authored_surface_alpha(mapping, palette)
        presentation_alpha = np.full(len(self._surface_mesh.presentations), 255, np.uint8)
        np.minimum.at(presentation_alpha, self._surface_mesh.presentation_ids, alpha)
        mask &= presentation_alpha[self._surface_mesh.face_presentation_ids] > 0
        if self.anatomy_presentation == 'major':
            selected = self._signed_focus_ids()
            mask &= np.isin(self._surface_mesh.face_mapping_ids(mapping), selected)
        elif include_selection and self._selection_focus_active():
            mask &= np.isin(self._surface_mesh.face_mapping_ids(mapping), self._signed_focus_ids())
        return mask

    def _upload_surface_faces(self, mask, mapping):
        """Filter render triangle indices and matching signed face keys together."""
        previous = self._uploaded_face_mask
        old_mapping = self._uploaded_face_mapping
        was_visible = self._surface_visible and bool(np.any(self._surface_face_mask))
        try:
            if np.any(mask):
                if not np.array_equal(mask, previous):
                    indices = self._surface_mesh.indices.reshape(-1, 3)[mask].reshape(-1).copy()
                    self._check(
                        self.dvz.dvz_visual_set_index_data(self.mesh, indices),
                        'visible surface indices',
                    )
                keys = self._surface_mesh.face_mapping_ids(mapping)[mask].view(np.uint64).copy()
                self._check(
                    self.dvz.dvz_visual_set_target_link_keys(
                        self.mesh,
                        self.dvz.DVZ_SCENE_TARGET_FACE,
                        self.link_channel,
                        keys,
                    ),
                    'visible surface keys',
                )
            self._check(
                self.dvz.dvz_visual_set_visible(
                    self.mesh, self._surface_visible and bool(np.any(mask))
                ),
                'surface visibility',
            )
        except Exception as error:
            try:
                indices = self._surface_mesh.indices.reshape(-1, 3)[previous].reshape(-1).copy()
                self._check(
                    self.dvz.dvz_visual_set_index_data(self.mesh, indices),
                    'surface index rollback',
                )
                self._check(
                    self.dvz.dvz_visual_set_target_link_keys(
                        self.mesh,
                        self.dvz.DVZ_SCENE_TARGET_FACE,
                        self.link_channel,
                        self._surface_mesh.face_mapping_ids(old_mapping)[previous]
                        .view(np.uint64)
                        .copy(),
                    ),
                    'surface key rollback',
                )
                self._check(
                    self.dvz.dvz_visual_set_visible(self.mesh, was_visible),
                    'surface visibility rollback',
                )
            except Exception:
                self.close()
                raise RuntimeError('surface rollback failed; viewer closed') from error
            raise
        if np.any(mask):
            self._uploaded_face_mask = mask.copy()
            self._uploaded_face_mapping = mapping

    def _surface_transaction_snapshot(self):
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
            '_surface_style',
            '_surface_visible',
            'surface_opacity',
            '_surface_face_mask',
            '_uploaded_face_mask',
            '_uploaded_face_mapping',
            '_surface_base_colors_cache',
            '_surface_base_is_translucent',
            '_last_surface_emphasis',
            '_surface_alpha_mode',
            '_selected_region_ids',
            '_hovered_region_ids',
            '_highlight_region_ids',
            '_last_mesh_region_ids',
            '_probe_upload',
            '_probe_colors',
        )
        state = {name: getattr(self, name) for name in names}
        colors = self._surface_base_colors_cache
        if colors is None:
            colors = self._display_surface_colors()
        state['colors'] = np.array(colors, order='C', copy=True)
        state['mapping_control'] = self._mapping_control.value
        return state

    def _restore_surface_transaction(self, snapshot, widgets=()):
        """Restore geometry, identity, colors and mode; close on any rollback failure."""
        try:
            for name, value in snapshot.items():
                if name not in ('colors', 'mapping_control'):
                    setattr(self, name, value)
            self._mapping_control.value = snapshot['mapping_control']
            mask = self._uploaded_face_mask
            self._check(
                self.dvz.dvz_visual_set_index_data(
                    self.mesh, self._surface_mesh.indices.reshape(-1, 3)[mask].reshape(-1).copy()
                ),
                'surface transaction index rollback',
            )
            self._check(
                self.dvz.dvz_visual_set_target_link_keys(
                    self.mesh,
                    self.dvz.DVZ_SCENE_TARGET_FACE,
                    self.link_channel,
                    self._surface_mesh.face_mapping_ids(self._uploaded_face_mapping)[mask]
                    .view(np.uint64)
                    .copy(),
                ),
                'surface transaction key rollback',
            )
            self._check(
                self.dvz.dvz_visual_set_data(self.mesh, 'color', snapshot['colors']),
                'surface transaction color rollback',
            )
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(self.mesh, self._surface_alpha_mode),
                'surface transaction alpha rollback',
            )
            self._check(
                self.dvz.dvz_visual_set_visible(
                    self.mesh, self._surface_visible and bool(np.any(self._surface_face_mask))
                ),
                'surface transaction visibility rollback',
            )
            if self.probe_data is not None and self._probe_upload is not None:
                self._check(
                    self.dvz.dvz_visual_set_link_keys(
                        self.probe_sites, self.link_channel, self._probe_upload.keys
                    ),
                    'surface transaction probe key rollback',
                )
            self._selection_envelope_visible = None
            self._update_selection_envelope_visibility()
            self._surface_state.invalidate()
            self._last_surface_emphasis = None
            self._update_surface_emphasis()
            for widget in widgets:
                getattr(self, f'_replace_{widget}')()
            if self._selector_gui is not None and self.region_tree is not None:
                self._selector_gui.model = self._selector_model
                self._selector_gui.value_name = (
                    self.region_data.value_name if self.region_data is not None else 'Value'
                )
                self._selector_gui.upload(self._selector_model)
        except Exception as rollback_error:
            self.close()
            raise RuntimeError(
                'surface transaction rollback failed; viewer closed'
            ) from rollback_error

    def _commit_surface_style(self, candidate, *, opacity=None):
        snapshot = self._surface_transaction_snapshot()
        self._surface_style = candidate
        if opacity is not None:
            self.surface_opacity = opacity
        try:
            mask = self._visible_surface_faces(self.mapping)
            colors = self._display_surface_colors()
            self._upload_surface_faces(mask, self.mapping)
            self._check(
                self.dvz.dvz_visual_set_data(self.mesh, 'color', colors), 'region style colors'
            )
            self._surface_face_mask = mask
            self._invalidate_surface_emphasis_cache(colors)
            self._clear_surface_hover()
            self._update_surface_emphasis()
        except Exception:
            if not self._closed:
                self._restore_surface_transaction(snapshot)
            raise

    def set_anatomical_context(self, surfaces):
        """Replace independently prepared major surfaces without changing selection.

        Coarse clicks select their true signed source Allen parent when present
        in the current ontology; use the Regions tree for fine mapped anatomy.
        Context stays at original world positions while the translucent fine
        selected overlay follows atlas explosion.
        """
        self._require_open()
        surfaces = tuple(surfaces)
        if any(
            not isinstance(s, AtlasContextSurface)
            or s.geometry.mesh.reference_space != self.mesh_data.reference_space
            for s in surfaces
        ):
            raise ValueError('context surfaces must share the atlas reference space')
        candidate = AnatomicalContext(self, surfaces)
        previous = self._anatomical_context
        try:
            candidate.update()
            if previous is not None:
                for entry in previous.entries:
                    self._check(
                        self.dvz.dvz_visual_set_visible(entry.visual, False),
                        'previous anatomy context hide',
                    )
        except Exception:
            candidate.close()
            if previous is not None:
                try:
                    previous.update(force=True)
                except Exception as error:
                    self.close()
                    raise RuntimeError('context rollback failed; viewer closed') from error
            raise
        self._anatomical_context = candidate
        if previous is not None:
            previous.close()

    def set_context_opacity(self, opacity):
        """Set coarse context opacity, preserving selection and authored colors."""
        self._require_open()
        if not np.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('context opacity must be between zero and one')
        snapshot = self._surface_transaction_snapshot()
        try:
            self.context_opacity = float(opacity)
            self._update_anatomical_context()
        except Exception:
            self._restore_surface_transaction(snapshot)
            raise

    def set_anatomy_presentation(self, presentation):
        """Choose actual major surfaces or the detailed atlas geometry."""
        self._require_open()
        if presentation not in ('major', 'detailed'):
            raise ValueError('anatomy presentation must be major or detailed')
        snapshot = self._surface_transaction_snapshot()
        self.anatomy_presentation = presentation
        try:
            self._commit_surface_style(self._surface_style.copy())
        except Exception:
            if not self._closed:
                self._restore_surface_transaction(snapshot)
            raise

    def _update_anatomical_context(self):
        if self._anatomical_context is not None:
            self._anatomical_context.update()

    def _selection_focus_active(self):
        return self.selection_presentation in ('focus', 'isolate') and bool(
            self._selected_region_ids
        )

    def _signed_focus_ids(self, region_ids=None):
        """Expand ontology descendants on each explicitly selected anatomical side."""
        selected = self._selected_region_ids if region_ids is None else region_ids
        included = set()
        for region_id in selected:
            descendants = (
                self.tree_model.expanded_logical_ids((region_id,))
                if self.tree_model is not None
                else (abs(region_id),)
            )
            included.update((-1 if region_id < 0 else 1) * value for value in descendants)
        return tuple(sorted(included))

    def set_selection_presentation(self, mode):
        """Choose signed focus, isolation, full atlas, or legacy bilateral dimming."""
        self._require_open()
        if mode not in ('legacy', 'focus', 'isolate', 'all'):
            raise ValueError('selection presentation must be legacy, focus, isolate or all')
        if mode == self.selection_presentation:
            return
        snapshot = self._surface_transaction_snapshot()
        try:
            self.selection_presentation = mode
            self._surface_state.invalidate()
            self._last_surface_emphasis = None
            self._update_surface_emphasis()
            self._clear_surface_hover()
        except Exception:
            if not self._closed:
                self._restore_surface_transaction(snapshot)
            raise

    def set_selection_envelope(self, envelope: AtlasEnvelope | None):
        """Attach a prepared neutral context shell, excluded from scientific picking."""
        self._require_open()
        if envelope is not None and (
            not isinstance(envelope, AtlasEnvelope)
            or envelope.reference_space != self.mesh_data.reference_space
        ):
            raise ValueError('selection envelope must share the atlas reference space')
        previous = self._selection_envelope_visual
        old_envelope = self.selection_envelope
        candidate = None
        try:
            if envelope is not None:
                candidate = self.dvz.dvz_mesh(self.scene, 0)
                if not candidate:
                    raise RuntimeError('selection envelope creation failed')
                self._check(
                    self.dvz.dvz_visual_set_visible(candidate, False), 'context shell hide'
                )
                colors = np.tile(
                    np.array((170, 180, 192, 15), np.uint8), (len(envelope.positions), 1)
                )
                self._check(
                    self.dvz.dvz_visual_set_data_many(
                        candidate,
                        {
                            'position': envelope.positions,
                            'normal': envelope.normals,
                            'color': colors,
                        },
                    ),
                    'context shell geometry',
                )
                self._check(
                    self.dvz.dvz_visual_set_index_data(candidate, envelope.indices),
                    'context shell indices',
                )
                self._check(
                    self.dvz.dvz_visual_set_query_capabilities(candidate, 0),
                    'nonpickable context shell',
                )
                self._check(
                    self.dvz.dvz_visual_set_alpha_mode(candidate, self.dvz.DVZ_ALPHA_WBOIT),
                    'context shell transparency',
                )
                self._check(
                    self.dvz.dvz_panel_add_visual(self.panel, candidate, None),
                    'context shell attach',
                )
            self.selection_envelope = envelope
            self._selection_envelope_visual = candidate
            self._selection_envelope_visible = False
            self._update_selection_envelope_visibility()
            if previous is not None:
                self._check(
                    self.dvz.dvz_visual_set_visible(previous, False), 'previous context shell hide'
                )
                self.dvz.dvz_visual_destroy(previous)
        except Exception:
            self.selection_envelope = old_envelope
            self._selection_envelope_visual = previous
            self._selection_envelope_visible = None
            try:
                if candidate is not None:
                    self._check(
                        self.dvz.dvz_visual_set_visible(candidate, False),
                        'failed context shell hide',
                    )
                self._update_selection_envelope_visibility()
                if candidate is not None:
                    self.dvz.dvz_visual_destroy(candidate)
            except Exception as error:
                self.close()
                raise RuntimeError('context shell rollback failed; viewer closed') from error
            raise

    def _update_selection_envelope_visibility(self):
        # A whole reference envelope has no signed presentations. Hide it for
        # side filtering or explosion rather than show misleading context.
        visible = (
            self._surface_visible
            and self.selection_presentation == 'focus'
            and bool(self._selected_region_ids)
            and self.explode == 0
            and all(self._surface_style.hemispheres.values())
        )
        if (
            self._selection_envelope_visual is not None
            and bool(visible) != self._selection_envelope_visible
        ):
            self._check(
                self.dvz.dvz_visual_set_visible(self._selection_envelope_visual, visible),
                'context shell visibility',
            )
        self._selection_envelope_visible = bool(
            visible and self._selection_envelope_visual is not None
        )

    def set_region_visible(self, region_id, visible, *, hemisphere=None):
        """Show/hide signed mapped faces; optional hemisphere expands an absolute ID."""
        self._require_open()
        candidate = self._surface_style.copy()
        candidate.set_region(self.mapping, region_id, hemisphere=hemisphere, visible=visible)
        self._commit_surface_style(candidate)

    def set_surface_visible(self, visible):
        """Toggle the whole surface while retaining region and hemisphere styles."""
        self._require_open()
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('surface visibility must be boolean')
        snapshot = self._surface_transaction_snapshot()
        try:
            self._check(
                self.dvz.dvz_visual_set_visible(
                    self.mesh, bool(visible) and bool(np.any(self._surface_face_mask))
                ),
                'surface visibility',
            )
            self._surface_visible = bool(visible)
            self._update_selection_envelope_visibility()
            self._update_anatomical_context()
            if not visible:
                self._clear_surface_hover()
        except Exception:
            self._restore_surface_transaction(snapshot)
            raise

    def set_surface_opacity(self, opacity):
        """Update surface opacity without changing geometry, camera or selection."""
        self._require_open()
        if not np.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('surface opacity must be finite and between zero and one')
        self._commit_surface_style(self._surface_style.copy(), opacity=float(opacity))

    def reset_surface_style(self):
        """Reset all region overrides and show both hemispheres, retaining the camera."""
        self._require_open()
        self._commit_surface_style(SurfaceStyle(self._surface_mesh))

    def show_region(self, region_id, *, hemisphere=None):
        """Restore mapped-region faces without changing color or opacity."""
        self.set_region_visible(region_id, True, hemisphere=hemisphere)

    def hide_region(self, region_id, *, hemisphere=None):
        """Suppress mapped-region faces and their native picking targets."""
        self.set_region_visible(region_id, False, hemisphere=hemisphere)

    def set_region_color(self, region_id, color, *, hemisphere=None):
        """Override 3-D region RGB(A); scientific values and table colors stay intact."""
        self._require_open()
        candidate = self._surface_style.copy()
        candidate.set_region(self.mapping, region_id, hemisphere=hemisphere, color=color)
        self._commit_surface_style(candidate)

    def set_region_opacity(self, region_id, opacity, *, hemisphere=None):
        """Multiply authored region alpha, preserving it through hover/selection."""
        self._require_open()
        candidate = self._surface_style.copy()
        candidate.set_region(self.mapping, region_id, hemisphere=hemisphere, opacity=opacity)
        self._commit_surface_style(candidate)

    def reset_region_style(self, region_id, *, hemisphere=None):
        """Reset region overrides in the current mapping, preserving hemisphere controls."""
        self._require_open()
        candidate = self._surface_style.copy()
        candidate.reset_region(self.mapping, region_id, hemisphere=hemisphere)
        self._commit_surface_style(candidate)

    def set_hemisphere_visible(self, hemisphere, visible):
        """Filter source-bound left/right presentations without changing the atlas mesh."""
        self._require_open()
        candidate = self._surface_style.copy()
        candidate.set_hemisphere_visible(hemisphere, visible)
        self._commit_surface_style(candidate)

    def set_hemisphere(self, hemisphere):
        """Show left, right or both anatomical hemispheres."""
        self._require_open()
        if hemisphere not in ('left', 'right', 'both'):
            raise ValueError('hemisphere must be left, right or both')
        candidate = self._surface_style.copy()
        for side in ('left', 'right'):
            candidate.set_hemisphere_visible(side, hemisphere in ('both', side))
        self._commit_surface_style(candidate)

    def visible_region_ids(self):
        """Return signed IDs with visible faces in the current mapping."""
        ids = self._surface_mesh.face_mapping_ids(self.mapping)[self._surface_face_mask]
        return tuple(int(value) for value in np.unique(ids) if value)

    def set_explode(self, amount: float) -> None:
        """Explode mesh components along their canonical centroid displacement vectors."""
        self._require_open()
        if not np.isfinite(amount) or not 0 <= amount <= 1:
            raise ValueError('explode must be between zero and one')
        amount = float(amount)
        if amount == self.explode:
            self._explode_control.value = amount
            return
        previous = self.explode
        try:
            self._check(
                self.dvz.dvz_visual_set_data(
                    self.mesh, 'position', self._surface_mesh.exploded_positions(amount)
                ),
                'mesh explode position update',
            )
            self.explode = self._explode_control.value = amount
            self._update_selection_envelope_visibility()
        except Exception as error:
            self.explode = self._explode_control.value = previous
            try:
                self._check(
                    self.dvz.dvz_visual_set_data(
                        self.mesh, 'position', self._surface_mesh.exploded_positions(previous)
                    ),
                    'mesh explode position rollback',
                )
                self._selection_envelope_visible = None
                self._update_selection_envelope_visibility()
            except Exception:
                self.close()
                raise RuntimeError('explode rollback failed; viewer closed') from error
            raise

    def set_mapping(
        self, mapping: str, palette: Mapping[int, Sequence[int]] | None = None
    ) -> None:
        """Change presentation colors and link identity transactionally."""
        self._require_open()
        model = AtlasTreeModel.from_catalog(self.catalog, mapping) if self.catalog else None
        effective_palette = self.palette if palette is None else palette
        if model is not None and palette is None:
            effective_palette = model.palette
        surface_colors = self._display_surface_colors(mapping, effective_palette)
        mask = self._visible_surface_faces(mapping, effective_palette, include_selection=False)
        snapshot = self._surface_transaction_snapshot()
        widgets = []
        try:
            self._upload_surface_faces(mask, mapping)
            self._check(
                self.dvz.dvz_visual_set_data(self.mesh, 'color', surface_colors),
                'mapping color update',
            )
            self.mapping, self.palette, self.tree_model = mapping, effective_palette, model
            self._surface_face_mask = mask
            self._selected_region_ids = self._hovered_region_ids = self._highlight_region_ids = ()
            self._invalidate_surface_emphasis_cache(surface_colors)
            self._update_surface_alpha_mode()
            self._mapping_control.value = self.mesh_data.mapping_names.index(mapping)
            if self.region_tree is not None:
                widgets.append('region_tree')
                self._replace_region_tree()
            if self.probe_data is not None:
                mapped_ids = self._mapped_probe_region_ids()
                self._check(
                    self.dvz.dvz_visual_set_link_keys(
                        self.probe_sites, self.link_channel, mapped_ids.view(np.uint64)
                    ),
                    'probe site mapping link keys',
                )
                if self._probe_upload is not None:
                    keys = np.array(mapped_ids.view(np.uint64), copy=True)
                    keys.setflags(write=False)
                    self._probe_upload = self._probe_upload._replace(keys=keys)
                if self.probe_table is not None:
                    widgets.append('probe_table')
                    self._replace_probe_table()
            if self.region_data is not None and self.region_table is not None:
                widgets.append('region_table')
                self._replace_region_table()
            self._clear_surface_hover()
            self._update_surface_emphasis()
            # Committed native selection is unchanged until every other setter
            # and GUI replacement has succeeded.
            if self.interaction is not None:
                self._check(
                    self.dvz.dvz_selection_clear(
                        self.dvz.dvz_item_interaction_selection(self.interaction)
                    ),
                    'mapping selection reset',
                )
            self._last_mesh_region_ids = ()
        except Exception:
            if not self._closed:
                self._restore_surface_transaction(snapshot, widgets)
            raise

    def _display_surface_colors(
        self,
        mapping: str | None = None,
        palette: Mapping[int, Sequence[int]] | None = None,
    ) -> NDArray[np.uint8]:
        """Return canonical or scalar-colored surface vertices for the active mapping."""
        active_mapping = self.mapping if mapping is None else mapping
        active_palette = self.palette if palette is None else palette
        if self.region_data is None:
            colors = self._surface_colors(active_mapping, active_palette)
        else:
            presentation = self._mapped_region_values(active_mapping)
            colors = self._region_surface_colors(
                active_mapping, presentation.region_ids, presentation.colors
            )
        if self.anatomy_presentation == 'major':
            colors = colors.copy()
            colors[:, 3] = np.minimum(colors[:, 3], round(255 * 0.18))
        return colors

    def _region_surface_colors(
        self,
        mapping: str,
        region_ids: NDArray[np.int64],
        value_colors: NDArray[np.uint8],
        *,
        context_opacity: float | None = None,
    ) -> NDArray[np.uint8]:
        """Expand one color per presentation region to dense mesh vertices."""
        opacity = self.surface_opacity if context_opacity is None else context_opacity
        alpha = int(round(255 * opacity))
        lookup = np.tile(
            np.asarray((100, 112, 130, alpha), dtype=np.uint8),
            (len(self._surface_mesh.presentations), 1),
        )
        by_region = dict(zip(region_ids, value_colors, strict=True))
        for presentation in self._surface_mesh.presentations:
            mapped_id = presentation['mappings'][mapping]
            color = by_region.get(mapped_id)
            if color is not None:
                lookup[presentation['presentation_id']] = color
        return self._surface_style.apply(
            mapping,
            np.ascontiguousarray(lookup[self._surface_mesh.presentation_ids]),
            alpha_scale=opacity,
        )

    def set_region_data(
        self,
        data: AtlasRegionValues,
        *,
        value_range: tuple[float, float] | None = None,
        color_scheme: Literal['diverging', 'sequential'] = 'sequential',
        opacity: float | None = None,
        mapping_reduction: Literal['weighted_mean'],
    ) -> None:
        """Color surfaces, explicitly reducing mapping collisions by weighted mean."""
        self._require_open()
        if self.catalog is None:
            raise ValueError('linked region data requires an atlas region catalog')
        if color_scheme not in ('diverging', 'sequential'):
            raise ValueError(f'unknown region color scheme: {color_scheme}')
        if mapping_reduction != 'weighted_mean':
            raise ValueError(f'unknown region mapping reduction: {mapping_reduction}')
        if opacity is not None and (not np.isfinite(opacity) or not 0 <= opacity <= 1):
            raise ValueError('region opacity must be between zero and one')
        prepared = self._region_value_view(data, self.mapping, value_range, color_scheme, opacity)
        surface_colors = self._region_surface_colors(
            self.mapping, prepared.region_ids, prepared.colors
        )
        snapshot = self._surface_transaction_snapshot()
        widgets = []
        try:
            self.region_data = data
            self._region_value_range = value_range
            self._region_color_scheme = color_scheme
            self._region_opacity = opacity
            mask = self._visible_surface_faces(self.mapping)
            self._upload_surface_faces(mask, self.mapping)
            self._check(
                self.dvz.dvz_visual_set_data(self.mesh, 'color', surface_colors),
                'region scalar color update',
            )
            self._surface_face_mask = mask
            self._highlight_region_ids = ()
            self._invalidate_surface_emphasis_cache(surface_colors)
            self._update_surface_alpha_mode()
            selected = self._selected_region_ids
            if selected or self._hovered_region_ids:
                self._apply_selected_region_ids(
                    selected, update_tree=False, update_table=False, clear_mesh=False
                )
            if self.gui is not None:
                widgets.append('region_table')
                self._replace_region_table()
            if self._selector_gui is not None:
                candidate = self._selector_gui.candidate()
                candidate.values = self._selector_values(candidate)
                candidate._repair_focus()
                self._selector_gui.value_name = data.value_name
                self._selector_gui.commit(candidate)
                self._selector_model = candidate
        except Exception:
            if not self._closed:
                self._restore_surface_transaction(snapshot, widgets)
            raise

    def _mapped_region_values(self, mapping: str | None = None) -> RegionalView:
        """Return the active weighted-mean regional presentation."""
        data = self.region_data
        if data is None or self.catalog is None:
            empty_i = np.empty(0, dtype=np.int64)
            empty_f = np.empty(0, dtype=np.float64)
            empty_c = np.empty((0, 4), dtype=np.uint8)
            return RegionalView(empty_i, empty_f, empty_f, (), empty_c)
        active_mapping = self.mapping if mapping is None else mapping
        return self._region_value_view(
            data,
            active_mapping,
            self._region_value_range,
            self._region_color_scheme,
            self._region_opacity,
        )

    def _region_value_view(
        self,
        data: AtlasRegionValues,
        mapping: str,
        value_range: tuple[float, float] | None,
        color_scheme: Literal['diverging', 'sequential'],
        opacity: float | None,
    ) -> RegionalView:
        """Build one weighted-mean mapping presentation without mutating state."""
        assert self.catalog is not None
        presentation = region_presentation(
            self.catalog,
            mapping,
            data,
            value_range,
            color_scheme,
            self.surface_opacity if opacity is None else opacity,
        )
        model = (
            self.tree_model
            if self.tree_model is not None and self.tree_model.mapping == mapping
            else None
        )
        labels = tuple(
            model.describe(int(region_id)) if model else str(region_id)
            for region_id in presentation.region_ids
        )
        return RegionalView(
            presentation.region_ids,
            presentation.values,
            presentation.weights,
            labels,
            presentation.colors,
        )

    def _insertion_collection(self):
        self._require_open()
        if self._insertions is None:
            self._insertions = InsertionCollectionVisual(
                self.dvz, self.scene, self.panel, transform=self.mesh_data.normalize_points
            )
        return self._insertions

    def set_insertion(self, insertion_id, points_um, *, color=(255, 205, 72, 255), width_px=4.0):
        """Add/replace an independently identified opaque trajectory in world micrometres."""
        self._insertion_collection().set_insertion(
            insertion_id, points_um, color=color, width_px=width_px
        )

    def set_insertion_color(self, insertion_id, color):
        """Change one trajectory's opaque RGB(A) color."""
        self._insertion_collection().set_color(insertion_id, color)

    def set_insertion_width(self, insertion_id, width_px):
        """Change one trajectory's stroke width in pixels."""
        self._insertion_collection().set_width(insertion_id, width_px)

    def set_insertion_visible(self, insertion_id, visible):
        """Show/hide one insertion, independently of atlas visibility and selection."""
        self._insertion_collection().set_visible(insertion_id, visible)

    def remove_insertion(self, insertion_id):
        """Remove one insertion and its native path, preserving unrelated trajectories."""
        self._insertion_collection().remove(insertion_id)

    @property
    def insertion_ids(self):
        """Return independent insertion identities in insertion order."""
        self._require_open()
        return () if self._insertions is None else self._insertions.ids

    def set_probe(
        self,
        points_um: Sequence[Sequence[float]],
        *,
        color: Sequence[int] = (255, 205, 72, 255),
        width_px: float = 4.0,
    ) -> None:
        """Add or replace a probe trajectory in atlas world micrometres."""
        self._require_open()
        positions = self.mesh_data.normalize_points(points_um)
        if len(positions) < 2:
            raise ValueError('a probe path needs at least two points')
        if not np.isfinite(width_px) or width_px <= 0:
            raise ValueError('probe width must be finite and positive')
        raw_color = np.asarray(color)
        if (
            raw_color.shape not in ((3,), (4,))
            or not np.issubdtype(raw_color.dtype, np.integer)
            or np.any(raw_color < 0)
            or np.any(raw_color > 255)
        ):
            raise ValueError('probe color must contain three or four 8-bit integer channels')
        rgba = tuple(int(channel) for channel in raw_color)
        if len(rgba) == 3:
            rgba += (255,)
        colors = np.tile(np.asarray(rgba, dtype=np.uint8), (len(positions), 1))
        widths = np.full(len(positions), width_px, dtype=np.float32)
        probe = self.probe
        if probe is None:
            probe = self._probe_pending
            if probe is None:
                probe = self.dvz.dvz_path(self.scene, 0)
                if not probe:
                    raise RuntimeError('dvz_path() failed')
                self._probe_pending = probe
            self._check(
                self.dvz.dvz_path_set_caps(
                    probe, self.dvz.DVZ_SEGMENT_CAP_ROUND, self.dvz.DVZ_SEGMENT_CAP_ROUND
                ),
                'probe caps',
            )
            self._check(
                self.dvz.dvz_path_set_join(probe, self.dvz.DVZ_PATH_JOIN_ROUND, 4.0),
                'probe join',
            )
        self._check(
            self.dvz.dvz_visual_set_data_many(
                probe,
                {'position': positions, 'color': colors, 'stroke_width_px': widths},
            ),
            'probe upload',
        )
        if self.probe is None:
            self._check(self.dvz.dvz_panel_add_visual(self.panel, probe, None), 'probe attach')
        self.probe = probe
        self._probe_pending = None

    def set_probe_sites(
        self,
        points_um: Sequence[Sequence[float]],
        *,
        values: Sequence[float] | None = None,
        colors: Sequence[Sequence[int]] | None = None,
        value_range: tuple[float, float] | None = None,
        radius_um: float = 45.0,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> None:
        """Replace sites and clear any typed payload and its linked table on success."""
        self._upload_probe_sites(
            points_um,
            values=values,
            colors=colors,
            value_range=value_range,
            radius_um=radius_um,
            color_scheme=color_scheme,
        )
        self.probe_data = None
        self._probe_colors = None
        self._replace_probe_table()

    def _upload_probe_sites(
        self,
        points_um,
        *,
        values=None,
        colors=None,
        value_range=None,
        radius_um=45.0,
        color_scheme='diverging',
        mapped_ids=None,
    ) -> None:
        """Validate and upload geometry and link identity before committing typed state."""
        self._require_open()
        positions = self.mesh_data.normalize_points(points_um)
        count = len(positions)
        if not np.isfinite(radius_um) or radius_um <= 0:
            raise ValueError('probe site radius must be finite and positive')
        if values is not None and colors is not None:
            raise ValueError('provide probe values or colors, not both')

        if colors is not None:
            raw_colors = np.asarray(colors)
            if (
                raw_colors.ndim != 2
                or raw_colors.shape[0] != count
                or raw_colors.shape[1] not in (3, 4)
                or not np.issubdtype(raw_colors.dtype, np.integer)
                or np.any(raw_colors < 0)
                or np.any(raw_colors > 255)
            ):
                raise ValueError('probe colors must have shape (n, 3) or (n, 4)')
            rgba = np.asarray(raw_colors, dtype=np.uint8)
            if rgba.shape[1] == 3:
                rgba = np.column_stack((rgba, np.full(count, 255, dtype=np.uint8)))
            rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
        elif values is not None:
            scalar = np.asarray(values, dtype=np.float64)
            if scalar.shape != (count,) or np.isinf(scalar).any():
                raise ValueError('probe values must have shape (n,) and contain no infinities')
            rgba = self._probe_value_colors(scalar, value_range, color_scheme)
        else:
            rgba = np.tile(np.asarray((255, 205, 72, 255), dtype=np.uint8), (count, 1))

        radii = np.full(count, radius_um * self.mesh_data.display_scale, dtype=np.float32)
        keys = (
            np.zeros(count, dtype=np.uint64) if mapped_ids is None else mapped_ids.view(np.uint64)
        )
        snapshot = ProbeUpload(
            *(np.array(array, order='C', copy=True) for array in (positions, rgba, radii, keys))
        )
        for array in snapshot:
            array.setflags(write=False)
        self._commit_probe_upload(snapshot)

    def _commit_probe_upload(self, snapshot: ProbeUpload) -> None:
        """Commit geometry and identities, restoring the prior snapshot on failure."""
        previous = self._probe_upload
        visual = self.probe_sites
        if visual is None:
            visual = self._probe_sites_pending
            if visual is None:
                visual = self.dvz.dvz_sphere(self.scene, 0)
                if not visual:
                    raise RuntimeError('dvz_sphere() failed')
                # Scene owns the candidate even if a setter or attachment fails.
                self._probe_sites_pending = visual
        try:
            self._check(
                self.dvz.dvz_visual_set_data_many(visual, snapshot.attributes()),
                'probe sites upload',
            )
            self._check(
                self.dvz.dvz_visual_set_link_keys(visual, self.link_channel, snapshot.keys),
                'probe site link keys',
            )
            if self.probe_sites is None:
                self._check(
                    self.dvz.dvz_panel_add_visual(self.panel, visual, None),
                    'probe sites attach',
                )
        except Exception as error:
            if previous is not None:
                try:
                    self._check(
                        self.dvz.dvz_visual_set_data_many(visual, previous.attributes()),
                        'probe sites geometry rollback',
                    )
                    self._check(
                        self.dvz.dvz_visual_set_link_keys(
                            visual, self.link_channel, previous.keys
                        ),
                        'probe sites identity rollback',
                    )
                except Exception:
                    self.close()
                    raise RuntimeError('probe sites rollback failed; viewer closed') from error
            raise
        self.probe_sites = visual
        self._probe_sites_pending = None
        self._probe_upload = snapshot

    def set_probe_data(
        self,
        data: ProbeSites,
        *,
        value_range: tuple[float, float] | None = None,
        radius_um: float = 45.0,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> None:
        """Display a typed probe payload and link its Allen labels to atlas presentation."""
        self._require_open()
        if self.catalog is None:
            raise ValueError('linked probe data requires an atlas region catalog')
        mapped_ids = self._mapped_probe_region_ids(data)
        colors = self._probe_value_colors(data.values, value_range, color_scheme)
        self._upload_probe_sites(
            data.positions_um, colors=colors, radius_um=radius_um, mapped_ids=mapped_ids
        )
        self.probe_data = data
        self._probe_colors = colors
        if self.gui is not None:
            self._replace_probe_table()

    def _mapped_probe_region_ids(self, data: ProbeSites | None = None) -> NDArray[np.int64]:
        payload = self.probe_data if data is None else data
        if payload is None or self.catalog is None:
            return np.empty(0, dtype=np.int64)
        try:
            mapped = self.catalog.map_allen_ids(payload.allen_region_ids, self.mapping)
        except KeyError as error:
            raise ValueError(str(error)) from error
        return np.ascontiguousarray(
            [0 if region_id is None else region_id for region_id in mapped], dtype=np.int64
        )

    @staticmethod
    def _probe_value_colors(
        values: NDArray[np.float64],
        value_range: tuple[float, float] | None,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> NDArray[np.uint8]:
        return scalar_colors(values, value_range, color_scheme)

    def selected_region_ids(self) -> tuple[int, ...]:
        """Return the authoritative signed region selection."""
        return self._selected_region_ids

    def _emphasis_region_ids(self) -> tuple[int, ...]:
        """Return committed identities that may dim unselected regions."""
        return self._selected_region_ids

    def _mesh_hovered_region_ids(self) -> tuple[int, ...]:
        """Return the signed region identity under the retained 3-D hover query."""
        if getattr(self, '_viewport_input', None) is not None and self._viewport_input.suspended:
            self._clear_surface_hover()
            return ()
        if self.interaction is None or not self.enable_hover:
            return ()
        hover = self.dvz.dvz_item_interaction_hover(self.interaction)
        if not hover:
            return ()
        item = self.dvz.DvzSelectionItem()
        if not self.dvz.dvz_hover_copy(hover, ctypes.byref(item)) or not item.link_key:
            return ()
        signed = np.asarray(item.link_key, dtype=np.uint64).view(np.int64).item()
        return (int(signed),) if signed else ()

    def _clear_surface_hover(self) -> None:
        """Discard transient native and Python hover while preserving selection."""
        if self.interaction is not None:
            hover = self.dvz.dvz_item_interaction_hover(self.interaction)
            item = self.dvz.DvzSelectionItem()
            if hover and self.dvz.dvz_hover_copy(hover, ctypes.byref(item)):
                self._check(self.dvz.dvz_hover_clear(hover), 'surface hover clear')
        self._set_hovered_region_ids(())
        self._hovered_region_label = None

    def _set_hovered_region_ids(self, region_ids: Sequence[int]) -> bool:
        """Set transient hover emphasis without changing committed selection."""
        if not self.enable_hover:
            region_ids = ()
        hovered = tuple(dict.fromkeys(int(region_id) for region_id in region_ids if region_id))
        if hovered == self._hovered_region_ids:
            return False
        self._hovered_region_ids = hovered
        self._update_surface_emphasis()
        return True

    def _sync_viewport_hover(self, hovered: bool) -> None:
        """Synchronize transient hover from a plain 3-D viewport."""
        if hovered:
            self._set_hovered_region_ids(self._mesh_hovered_region_ids())
        else:
            model = self._selector_model
            region = model.by_id.get(model.hover) if model is not None else None
            self._set_hovered_region_ids((region.atlas_id,) if region else ())

    def _mesh_selected_region_ids(self) -> tuple[int, ...]:
        if self.interaction is None:
            return ()
        selection = self.dvz.dvz_item_interaction_selection(self.interaction)
        count = self.dvz.dvz_selection_count(selection)
        if count == 0:
            return ()
        items = (self.dvz.DvzSelectionItem * count)()
        self.dvz.dvz_selection_copy(selection, items, count)
        return mesh_ids_from_keys([item.link_key for item in items])

    def _tree_selected_region_ids(self) -> tuple[int, ...]:
        if self.region_tree is None:
            return ()
        return region_ids_from_keys(self._gui_widgets['region_tree'].selected_keys())

    def set_selected_region_ids(self, region_ids: Sequence[int]) -> None:
        """Select signed or logical atlas regions and highlight their mapped descendants."""
        self._require_open()
        selected = tuple(dict.fromkeys(int(region_id) for region_id in region_ids if region_id))
        if self.tree_model is not None:
            available = {abs(int(region_id)) for region_id in self.tree_model.region_ids}
            missing = sorted({abs(region_id) for region_id in selected} - available)
            if missing:
                raise ValueError(f'regions are not members of {self.mapping}: {missing}')
        self._apply_selected_region_ids(
            selected, update_tree=True, update_table=True, clear_mesh=True
        )

    def clear_selection(self) -> None:
        """Clear tree, surface, and highlight selection state."""
        self.set_selected_region_ids(())

    def _close_gui_widget(self, name: str, kind: str) -> None:
        """Coordinate helper destruction, including partially initialized viewers."""
        owner = getattr(self, '_gui_widgets', {}).pop(name, None)
        handle = getattr(self, name, None)
        setattr(self, name, None)
        if owner is not None:
            owner.close()
        elif handle is not None:
            getattr(self.dvz, f'dvz_gui_{kind}_destroy')(handle)

    def _retain_gui_widget(self, name: str, owner) -> None:
        if not hasattr(self, '_gui_widgets'):
            self._gui_widgets = {}
        self._gui_widgets[name] = owner
        setattr(self, name, owner.handle)

    def _replace_probe_table(self) -> None:
        self._close_gui_widget('probe_table', 'table')
        data = self.probe_data
        if data is None:
            return
        mapped_ids = self._mapped_probe_region_ids()
        labels = tuple(
            self.tree_model.describe(region_id) if self.tree_model else str(region_id)
            for region_id in mapped_ids
        )
        self._retain_gui_widget(
            'probe_table',
            create_probe_table(self.dvz, data, mapped_ids, labels, self._probe_colors),
        )
        self._set_probe_table_selection(self._selected_region_ids)

    def _probe_table_selected_region_ids(self) -> tuple[int, ...]:
        if self.probe_table is None or self.probe_data is None:
            return ()
        widget = self._gui_widgets['probe_table']
        return probe_selected_ids(widget.rows.keys, widget.rows.region_ids, widget.selected_keys())

    def _set_probe_table_selection(self, region_ids: Sequence[int]) -> None:
        if self.probe_table is None or self.probe_data is None:
            return
        logical_ids = (
            self.tree_model.expanded_logical_ids(tuple(region_ids))
            if self.tree_model is not None
            else tuple(abs(int(region_id)) for region_id in region_ids)
        )
        rows = self._gui_widgets['probe_table'].rows
        keys = selected_row_keys(rows.keys, rows.region_ids, logical_ids)
        self._gui_widgets['probe_table'].set_selection(keys, 'probe table selection sync')

    def _replace_region_table(self) -> None:
        self._close_gui_widget('region_table', 'table')
        data = self.region_data
        if data is None:
            return
        view = self._mapped_region_values()
        self._retain_gui_widget(
            'region_table',
            create_region_table(
                self.dvz,
                data,
                view.region_ids,
                view.values,
                view.weights,
                view.labels,
                view.colors,
            ),
        )
        self._set_region_table_selection(self._selected_region_ids)

    def _region_table_selected_region_ids(self) -> tuple[int, ...]:
        if self.region_table is None:
            return ()
        return region_ids_from_keys(self._gui_widgets['region_table'].selected_keys())

    def _set_region_table_selection(self, region_ids: Sequence[int]) -> None:
        if self.region_table is None:
            return
        available = self._gui_widgets['region_table'].rows.region_ids
        logical_ids = (
            self.tree_model.expanded_logical_ids(tuple(region_ids))
            if self.tree_model is not None
            else tuple(abs(int(region_id)) for region_id in region_ids)
        )
        keys = selected_row_keys(available.view(np.uint64), available, logical_ids)
        self._gui_widgets['region_table'].set_selection(keys, 'region table selection sync')

    def _replace_region_tree(self) -> None:
        self._close_gui_widget('region_tree', 'tree')
        if self.tree_model is None:
            return
        self._retain_gui_widget(
            'region_tree',
            create_region_tree(
                self.dvz,
                self.tree_model,
                self.tree_root_acronym,
                self._tree_filter.value,
                controlled=True,
            ),
        )
        model = (
            self._selector_model.copy()
            if self._selector_model is not None and self._selector_mapping == self.mapping
            else selector_from_tree(self.tree_model, self.tree_root_acronym, self._selector_model)
        )
        RegionSelectorGui.sync_selection(model, self._selected_region_ids)
        model.values = self._selector_values(model)
        try:
            self._selector_gui = RegionSelectorGui(
                self._gui_widgets['region_tree'],
                model,
                value_name=self.region_data.value_name
                if self.region_data is not None
                else 'Value',
            )
        except Exception:
            self._close_gui_widget('region_tree', 'tree')
            raise
        self._selector_model, self._selector_mapping = model, self.mapping

    def _selector_values(self, model):
        values = {}
        presentation = self._mapped_region_values()
        # Values are authored per signed region, as in the web reference. Never
        # substitute the other hemisphere for an absent canonical-left value.
        available = {region.atlas_id: region.id for region in model.regions}
        for region_id, value in zip(presentation.region_ids, presentation.values, strict=True):
            if int(region_id) in available:
                values[available[int(region_id)]] = float(value)
        return values

    def _gui_callback(self, gui, _view, _user_data) -> None:
        """Keep native resources alive until GUI scopes and the app frame unwind."""
        if self._closed or self._close_pending:
            return
        self._gui_callback_depth += 1
        try:
            self._draw_gui_frame(gui)
        except Exception as error:
            if self._close_pending and self.app is not None:
                # ctypes cannot propagate callback exceptions to app_run's caller.
                self._gui_callback_error = error
                return
            raise
        finally:
            self._gui_callback_depth -= 1
            if self._close_pending and self._gui_callback_depth == 0 and self.app is None:
                # Direct controlled-widget calls have no native app frame to resume.
                self.close()

    def _draw_gui_frame(self, gui) -> None:
        """Draw one GUI frame with balanced native window and child scopes."""
        self._process_gui_frame()
        self.dvz.dvz_gui_dock_window_once(
            gui,
            b'Regions',
            self.dvz.DVZ_GUI_DOCK_SLOT_LEFT,
            self.sidebar_width * self.ui_scale,
        )
        if self.viewport is not None:
            self.dvz.dvz_gui_dock_window_once(
                gui, b'3D atlas', self.dvz.DVZ_GUI_DOCK_SLOT_CENTER, 0.0
            )
        # Dear ImGui NoScrollbar | NoScrollWithMouse: child panes own scrolling.
        visible = self.dvz.dvz_gui_begin(gui, b'Regions', None, (1 << 3) | (1 << 4))
        try:
            if visible:
                self._draw_sidebar_gui(gui)
        finally:
            self.dvz.dvz_gui_end(gui)
        if self.viewport is not None:
            # Reopening the same ImGui window appends the image below this toolbar.
            visible = self.dvz.dvz_gui_begin(gui, b'3D atlas', None, 0)
            try:
                if visible:
                    self._draw_viewport_toolbar_gui(gui)
            finally:
                self.dvz.dvz_gui_end(gui)
            self.dvz.dvz_gui_viewport_window(self.viewport, b'3D atlas', None, 0)
            hovered = ctypes.c_bool()
            mouse_pos = (ctypes.c_float * 2)()
            viewport_size = (ctypes.c_float * 2)()
            if self.dvz.dvz_gui_viewport_mouse(
                self.viewport, mouse_pos, viewport_size, ctypes.byref(hovered)
            ):
                self._sync_viewport_hover(bool(hovered.value))
            if hovered.value and getattr(self, '_hovered_region_label', None):
                self.dvz.dvz_gui_tooltip(gui, self._hovered_region_label.encode())

        self._draw_auxiliary_gui(gui)

    def _draw_sidebar_gui(self, gui) -> None:
        """Keep the browser permanent; scene controls live in an ordinary window."""
        try:
            self._sidebar.header(gui)
            self._sidebar.scene(gui)
            region_table_changed, table_changed = self._draw_data_tables_gui(gui)
            candidate = self._selector_gui.candidate()
            candidate.values = self._selector_values(candidate)
            self._selector_gui.value_name = (
                self.region_data.value_name if self.region_data is not None else 'Value'
            )
            self._selector_gui.controls(gui, candidate, self._tree_filter, self._sidebar)
        except Exception:
            self._restore_sidebar_feedback()
            raise
        tree_visible = self.dvz.dvz_gui_begin_child(
            gui, b'Atlas region hierarchy', 0.0, self._sidebar.reserve_tree(gui), 0
        )
        try:
            self._sidebar.tree_rect = self._sidebar.rect(gui)
            self._selector_gui.upload(candidate)
            events = ()
            if tree_visible:
                result, events, dropped = self.dvz.dvz_gui_tree_draw(gui, self.region_tree)
                self._check(result, 'region selector draw')
                if dropped:
                    raise RuntimeError('region selector input batch dropped')
            self._selector_gui.intents(candidate, events)
        except Exception:
            self._restore_sidebar_feedback()
            raise
        finally:
            self.dvz.dvz_gui_end_child(gui)
        try:
            if self._sidebar.footer(gui):
                candidate.set_selected(())
            self._sync_selection_highlight(
                tree_changed=candidate.selected != self._selector_model.selected,
                table_changed=table_changed,
                region_table_changed=region_table_changed,
                candidate=candidate,
            )
        except Exception:
            self._restore_sidebar_feedback()
            raise
        self._sidebar.details(gui)

    def _restore_sidebar_feedback(self):
        """Restore retained widgets after a partially failing frame update."""
        try:
            self._selector_gui.upload(self._selector_model)
            self._set_probe_table_selection(self._selected_region_ids)
            self._set_region_table_selection(self._selected_region_ids)
            self._tree_filter.value = self._selector_model.query.encode()
        except Exception as rollback_error:
            self.close()
            raise RuntimeError(
                'region selector rollback failed; viewer closed'
            ) from rollback_error

    def _draw_sidebar_controls_gui(self, gui) -> None:
        """Draw all optional scene controls in the explicit Scene window."""
        self._draw_extra_gui(gui)

    def _draw_viewport_toolbar_gui(self, gui) -> None:
        """Keep frequent 3-D presentation actions beside the atlas."""
        self.dvz.dvz_gui_set_next_item_width(gui, 160.0)
        if self.dvz.dvz_gui_slider_float(
            gui,
            b'Explode selected region' if self.anatomy_presentation == 'major' else b'Explode',
            ctypes.byref(self._explode_control),
            0.0,
            1.0,
        ):
            self.set_explode(self._explode_control.value)
        self.dvz.dvz_gui_same_line(gui, 0.0, 8.0)
        if self.dvz.dvz_gui_button(gui, b'Reset view') and self.arcball is not None:
            self._check(self.dvz.dvz_arcball_reset(self.arcball), 'camera reset')
            self.set_camera_angles(self.camera_angles)
        if self.anatomy_presentation == 'detailed' and self.selection_presentation != 'legacy':
            modes = ('focus', 'isolate', 'all')
            current = ctypes.c_int(modes.index(self.selection_presentation))
            labels = (ctypes.c_char_p * 3)(b'Focus selection', b'Isolate selection', b'Show all')
            self.dvz.dvz_gui_set_next_item_width(gui, 160.0 * self.ui_scale)
            if self.dvz.dvz_gui_combo(
                gui, b'##selection_presentation', ctypes.byref(current), labels, 3
            ):
                self.set_selection_presentation(modes[current.value])

    def _draw_auxiliary_gui(self, _gui) -> None:
        """Draw optional nonmodal windows independently of sidebar visibility."""

    def _process_gui_frame(self) -> None:
        """Apply owner-thread work independently of visible controls or windows."""

    def _draw_extra_gui(self, _gui) -> None:
        """Draw optional controls supplied by specialized viewers."""

    def _draw_data_tables_gui(self, gui):
        """Draw retained tables in a separate window without consuming browser space."""
        if self.region_table is None and self.probe_table is None:
            return False, False
        visible = self._sidebar._window(gui, b'Data table', None, details=True)
        changes = [False, False]
        try:
            if visible:
                for index, (title, table) in enumerate(
                    (
                        (b'Region values', self.region_table),
                        (b'Probe sites', self.probe_table),
                    )
                ):
                    if table is None:
                        continue
                    self.dvz.dvz_gui_separator_text(gui, title)
                    result, events, dropped = self.dvz.dvz_gui_table_draw(gui, table)
                    self._check(result, 'data table draw')
                    if dropped:
                        raise RuntimeError('data table input batch dropped')
                    changes[index] = any(
                        event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                        for event in events
                    )
        finally:
            self.dvz.dvz_gui_end(gui)
        return tuple(changes)

    def _set_tree_selection(self, region_ids: Sequence[int]) -> None:
        if self.region_tree is None or self.tree_model is None:
            return
        if self._selector_gui is not None:
            candidate = self._selector_gui.candidate()
            self._selector_gui.sync_selection(candidate, region_ids)
            try:
                self._selector_gui.commit(candidate)
            except Exception:
                # commit already attempts native rollback; a second failure closes.
                try:
                    self._selector_gui.upload(self._selector_model)
                except Exception:
                    self.close()
                raise
            self._selector_model = candidate
            return
        keys = tree_selection_keys(region_ids, self._gui_widgets['region_tree'].rows.region_ids)
        self._gui_widgets['region_tree'].set_selection(keys, 'atlas ontology selection sync')

    def _apply_selected_region_ids(
        self,
        region_ids: tuple[int, ...],
        *,
        update_tree: bool,
        update_table: bool,
        clear_mesh: bool,
    ) -> None:
        snapshot = (
            self._surface_transaction_snapshot()
            if self.selection_presentation != 'legacy' or self.anatomy_presentation == 'major'
            else None
        )
        try:
            if update_tree:
                self._set_tree_selection(region_ids)
            if update_table:
                self._set_probe_table_selection(region_ids)
                self._set_region_table_selection(region_ids)
            self._selected_region_ids = region_ids
            self._update_surface_emphasis()
            if clear_mesh and self.interaction is not None:
                self._check(
                    self.dvz.dvz_selection_clear(
                        self.dvz.dvz_item_interaction_selection(self.interaction)
                    ),
                    'surface selection clear',
                )
                self._last_mesh_region_ids = ()
        except Exception:
            if snapshot is not None and not self._closed:
                self._restore_surface_transaction(snapshot)
                self._set_tree_selection(self._selected_region_ids)
                self._set_probe_table_selection(self._selected_region_ids)
                self._set_region_table_selection(self._selected_region_ids)
            raise

    def _update_surface_emphasis(self) -> None:
        """Fade non-selected regions and brighten hover without affecting unrelated regions."""
        self._update_anatomical_context()
        face_state = (
            self.mapping,
            self._selected_region_ids,
            self.selection_presentation,
            self.anatomy_presentation,
        )
        if (
            self.anatomy_presentation == 'major'
            or self.selection_presentation != 'legacy'
            or self._selection_face_state is not None
        ) and face_state != self._selection_face_state:
            mask = self._visible_surface_faces(self.mapping)
            if not np.array_equal(mask, self._surface_face_mask):
                self._upload_surface_faces(mask, self.mapping)
                self._surface_face_mask = mask
            self._selection_face_state = face_state
        self._update_selection_envelope_visibility()
        selected_ids = (
            self.tree_model.expanded_logical_ids(self._selected_region_ids)
            if self.tree_model is not None
            else tuple(
                sorted({abs(region_id) for region_id in self._selected_region_ids if region_id})
            )
        )
        hovered_ids = (
            self.tree_model.expanded_logical_ids(self._hovered_region_ids)
            if self.tree_model is not None
            else tuple(
                sorted({abs(region_id) for region_id in self._hovered_region_ids if region_id})
            )
        )
        if self.selection_presentation != 'legacy' or self.anatomy_presentation == 'major':
            selected_ids = self._signed_focus_ids()
            hovered_ids = self._signed_focus_ids(self._hovered_region_ids)
        state = (selected_ids, hovered_ids, self.selection_presentation)
        if state == self._last_surface_emphasis:
            return
        if (
            self._last_surface_emphasis is None
            or self._last_surface_emphasis[0] != selected_ids
            or self._last_surface_emphasis[2] != self.selection_presentation
        ):
            self._update_surface_alpha_mode()
        self._surface_state.update(
            selected_ids,
            hovered_ids,
            selection_active=(
                bool(self._selected_region_ids)
                and self.selection_presentation == 'legacy'
                and self.anatomy_presentation != 'major'
            ),
        )
        self._highlight_region_ids = selected_ids
        self._last_surface_emphasis = state

    def _update_surface_alpha_mode(self) -> None:
        """Honor effective palette, regional and selection alpha in native mode."""
        mode = (
            self.dvz.DVZ_ALPHA_WBOIT
            if self._surface_is_translucent()
            else self.dvz.DVZ_ALPHA_OPAQUE
        )
        if mode == self._surface_alpha_mode:
            return
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.mesh, mode),
            'surface transparency mode',
        )
        self._surface_alpha_mode = mode

    def _surface_is_translucent(self):
        if self._surface_base_colors_cache is None:
            self._invalidate_surface_emphasis_cache(self._display_surface_colors())
        if self.anatomy_presentation == 'major' or self.selection_presentation != 'legacy':
            vertices = np.unique(
                self._surface_mesh.indices.reshape(-1, 3)[self._surface_face_mask]
            )
            return bool(np.any(self._surface_base_colors_cache[vertices, 3] < 255))
        return (
            self.surface_opacity < 1
            or bool(self._selected_region_ids)
            or self._surface_base_is_translucent
        )

    def _invalidate_surface_emphasis_cache(
        self, base_colors: NDArray[np.uint8] | None = None
    ) -> None:
        """Invalidate derived surface styling after canonical color or mapping changes."""
        self._surface_base_colors_cache = base_colors
        self._surface_base_is_translucent = (
            bool(np.any(base_colors[:, 3] < 255)) if base_colors is not None else False
        )
        self._last_surface_emphasis = None

    def _sync_selection_highlight(
        self,
        *,
        tree_changed: bool = False,
        table_changed: bool = False,
        region_table_changed: bool = False,
        candidate=None,
    ) -> None:
        decision = selection_decision(
            region_table_changed=region_table_changed,
            table_changed=table_changed,
            tree_changed=tree_changed,
        )
        if decision is None:
            mesh_region_ids = self._mesh_selected_region_ids()
            decision = selection_decision(
                mesh_changed=mesh_region_ids != self._last_mesh_region_ids
            )
            if decision is None:
                if candidate is not None:
                    self._commit_selector_frame(candidate, self._selected_region_ids, None)
                return
            if candidate is None:
                self._last_mesh_region_ids = mesh_region_ids
            region_ids = mesh_region_ids
        else:
            readers = {
                'region_table': self._region_table_selected_region_ids,
                'probe_table': self._probe_table_selected_region_ids,
                'tree': self._tree_selected_region_ids,
            }
            region_ids = (
                signed_selection(candidate, self._selected_region_ids)
                if candidate is not None and decision.source == 'tree'
                else readers[decision.source]()
            )
        if candidate is not None:
            self._commit_selector_frame(candidate, region_ids, decision)
            return
        self._apply_selected_region_ids(
            region_ids,
            update_tree=decision.update_tree,
            update_table=decision.update_tables,
            clear_mesh=decision.clear_mesh,
        )
        if decision.sync_probe_table:
            self._set_probe_table_selection(self._selected_region_ids)
        if decision.sync_region_table:
            self._set_region_table_selection(self._selected_region_ids)

    def _commit_selector_frame(self, candidate, region_ids, decision):
        """Commit navigation and the winning host selection as one recoverable batch."""
        previous = self._selector_model
        selected, hovered = self._selected_region_ids, self._hovered_region_ids
        last_mesh = self._last_mesh_region_ids
        if decision is not None and decision.source != 'tree':
            candidate.selected = previous.selected.copy()
            candidate.anchor = previous.anchor
        self._selector_gui.sync_selection(candidate, region_ids, preserve_anchor=True)
        try:
            self._selector_gui.commit(candidate)
            self._selector_model = candidate
            if decision is not None:
                self._apply_selected_region_ids(
                    region_ids,
                    update_tree=False,
                    update_table=decision.update_tables,
                    clear_mesh=False,
                )
                if decision.sync_probe_table:
                    self._set_probe_table_selection(region_ids)
                if decision.sync_region_table:
                    self._set_region_table_selection(region_ids)
            if candidate.hover is not None or candidate.hover != previous.hover:
                region = candidate.by_id.get(candidate.hover)
                self._set_hovered_region_ids((region.atlas_id,) if region else ())
            if decision is not None:
                if decision.clear_mesh and self.interaction is not None:
                    self._check(
                        self.dvz.dvz_selection_clear(
                            self.dvz.dvz_item_interaction_selection(self.interaction)
                        ),
                        'surface selection clear',
                    )
                    self._last_mesh_region_ids = ()
                elif decision.source == 'mesh':
                    self._last_mesh_region_ids = tuple(region_ids)
        except Exception:
            self._selector_gui.model = self._selector_model = previous
            self._selected_region_ids, self._hovered_region_ids = selected, hovered
            self._last_mesh_region_ids = last_mesh
            try:
                self._selector_gui.upload(previous)
                self._set_probe_table_selection(selected)
                self._set_region_table_selection(selected)
                self._restore_selection_feedback()
            except Exception as rollback_error:
                self.close()
                raise RuntimeError(
                    'region selector frame rollback failed; viewer closed'
                ) from rollback_error
            raise

    def _restore_selection_feedback(self):
        """Force restored physical selection and hover back into presentation."""
        # A failed setter can mutate native pixels before reporting failure.
        self._last_surface_emphasis = None
        self._surface_state.invalidate()
        self._update_surface_emphasis()

    def _create_window_view(self, figure, title):
        if not self.fit_workarea:
            return self.dvz.dvz_view_window(
                self.app, figure, self.width, self.height, title.encode()
            )
        descriptor = self.dvz.dvz_view_desc(self.dvz.DVZ_VIEW_WINDOW)
        descriptor.size_policy = self.dvz.DVZ_VIEW_SIZE_HOST_LOGICAL_PX
        descriptor.size_width = self.width
        descriptor.size_height = self.height
        descriptor.title = title.encode()
        descriptor.fit_workarea = True
        return self.dvz.dvz_view(self.app, figure, ctypes.byref(descriptor))

    def _create_view(self, *, offscreen: bool, title: str) -> None:  # noqa: PLR0912, PLR0915
        if self.app is not None:
            raise RuntimeError('viewer already has an active app')
        if not offscreen and self.catalog is not None:
            app_config = self.dvz.dvz_app_config()
            app_config.font_ui_size_px = 18.0
            self.app = self.dvz.dvz_app_with_config(self.scene, ctypes.byref(app_config))
        else:
            self.app = self.dvz.dvz_app(self.scene)
        if not self.app:
            raise RuntimeError('dvz_app() failed')
        if offscreen:
            self.view = self.dvz.dvz_view_offscreen(self.app, self.figure, self.width, self.height)
            if not self.view:
                raise RuntimeError('Datoviz view creation failed')
            self.arcball = self.dvz.dvz_view_arcball(self.view, self.panel, None)
        elif self.catalog is None:
            self.view = self._create_window_view(self.figure, title)
            if not self.view:
                raise RuntimeError('Datoviz view creation failed')
            self.arcball = self.dvz.dvz_view_arcball(self.view, self.panel, None)
        else:
            self.host_figure = self.dvz.dvz_figure(self.scene, self.width, self.height, 0)
            if not self.host_figure:
                raise RuntimeError('Datoviz host figure creation failed')
            host_panel = self.dvz.dvz_panel_full(self.host_figure)
            if not host_panel:
                raise RuntimeError('Datoviz host panel creation failed')
            self.dvz.dvz_panel_set_background_color(host_panel, self.dvz.DvzColor(24, 27, 32, 255))
            self.view = self._create_window_view(self.host_figure, title)
        if not self.view:
            raise RuntimeError('Datoviz view creation failed')
        self._check(
            self.dvz.dvz_view_set_user_scale(self.view, self.ui_scale),
            'view user scale',
        )
        if not offscreen and self.catalog is not None:
            if not hasattr(self.dvz, 'dvz_hover_copy'):
                raise RuntimeError(
                    'interactive atlas hover requires current Datoviz v0.4 Python bindings; '
                    'put the Datoviz source checkout on PYTHONPATH when using a development '
                    'libdatoviz build'
                )
            self._replace_region_tree()
            if self.probe_data is not None:
                self._replace_probe_table()
            if self.region_data is not None:
                self._replace_region_table()
            config = self.dvz.dvz_gui_config()
            config.gui_flags = (
                self.dvz.DVZ_GUI_FLAGS_DOCKING
                | self.dvz.DVZ_GUI_FLAGS_DOCKSPACE
                | self.dvz.DVZ_GUI_FLAGS_NAV_KEYBOARD
            )
            config.default_window_width = 430
            self.gui = self.dvz.dvz_view_gui(self.view, ctypes.byref(config))
            if not self.gui:
                raise RuntimeError('dvz_view_gui() failed')
            viewport_config = self.dvz.dvz_gui_viewport_config()
            viewport_config.viewport_flags = self.dvz.DVZ_GUI_VIEWPORT_FLAGS_FORWARD_INPUT
            self.viewport = self.dvz.dvz_gui_viewport(
                self.gui, self.figure, ctypes.byref(viewport_config)
            )
            if not self.viewport:
                raise RuntimeError('dvz_gui_viewport() failed')
            if self.interaction is not None:
                router = self.dvz.dvz_gui_viewport_input(self.viewport)
                if not router:
                    raise RuntimeError('dvz_gui_viewport_input() failed')
                self._viewport_input = ViewportInputAdapter(self, router)
                self._viewport_input.subscribe()
            self.arcball_controller = self.dvz.dvz_arcball(self.scene, None)
            if not self.arcball_controller:
                raise RuntimeError('dvz_arcball() failed')
            self.arcball = self.dvz.dvz_controller_arcball(self.arcball_controller)
            if not self.arcball:
                raise RuntimeError('dvz_controller_arcball() failed')
            self._check(
                self.dvz.dvz_panel_bind_controller(
                    self.panel, self.arcball_controller, self.dvz.DVZ_DIM_MASK_XYZ
                ),
                'arcball panel binding',
            )
            self._check(
                self.dvz.dvz_panel_connect_input(
                    self.panel, self.dvz.dvz_gui_viewport_input(self.viewport)
                ),
                'embedded viewport input connection',
            )
            self._check(
                self.dvz.dvz_view_set_gui_callback(self.view, self._gui_callback, None),
                'atlas GUI callback',
            )
        if not self.arcball:
            raise RuntimeError('dvz arcball creation failed')
        angles = (ctypes.c_float * 3)(*self.camera_angles)
        self._check(self.dvz.dvz_arcball_set(self.arcball, angles), 'arcball setup')

    def render_offscreen(self, output: str | Path | None = None) -> NDArray[np.uint8]:
        """Render exactly one frame and return a copied RGBA image."""
        self._require_open()
        self._create_view(offscreen=True, title='')
        self._check(self.dvz.dvz_view_render_once(self.view), 'offscreen render')
        rgba = np.array(self.dvz.dvz_view_capture_rgba(self.view), copy=True)
        if rgba.shape != (self.height, self.width, 4) or rgba.dtype != np.uint8:
            raise RuntimeError(f'unexpected capture shape or dtype: {rgba.shape} {rgba.dtype}')
        background = np.array([29, 33, 39], dtype=np.uint8)
        if not np.any(rgba[..., :3] != background):
            raise RuntimeError('offscreen atlas capture is blank')
        if output is not None:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._check(
                self.dvz.dvz_view_capture_png(self.view, str(path).encode()), 'PNG capture'
            )
        return rgba

    def show(self, *, title: str = 'IBL atlas', frame_count: int = 0) -> None:
        """Run an interactive arcball and region-picking view."""
        self._require_open()
        self._create_view(offscreen=False, title=title)
        try:
            self.dvz.dvz_app_run(self.app, frame_count)
        finally:
            if self._close_pending:
                self.close()
        if self._gui_callback_error is not None:
            error, self._gui_callback_error = self._gui_callback_error, None
            raise error

    def _require_open(self) -> None:
        """Reject operations that require live native viewer state."""
        if self._closed:
            raise RuntimeError('viewer is closed')

    def close(self) -> None:
        """Destroy app before scene; scene owns all remaining handles."""
        if getattr(self, '_closed', False):
            return
        if getattr(self, '_gui_callback_depth', 0):
            self._close_pending = True
            if getattr(self, 'app', None) is not None:
                self.dvz.dvz_app_stop(self.app)
            return
        datoviz = getattr(self, 'dvz', None)
        if getattr(self, '_insertions', None) is not None:
            self._insertions.close()
            self._insertions = None
        if getattr(self, '_viewport_input', None) is not None:
            self._viewport_input.close()
            self._viewport_input = None
        if datoviz is not None and getattr(self, 'viewport', None) is not None:
            self.dvz.dvz_panel_connect_input(self.panel, None)
            self.dvz.dvz_gui_viewport_destroy(self.viewport)
            self.viewport = None
        if datoviz is not None and getattr(self, 'app', None):
            self.dvz.dvz_app_destroy(self.app)
            self.app = None
        if datoviz is not None:
            self._close_gui_widget('region_tree', 'tree')
            self._close_gui_widget('probe_table', 'table')
            self._close_gui_widget('region_table', 'table')
        if getattr(self, '_anatomical_context', None) is not None:
            self._anatomical_context.close()
            self._anatomical_context = None
        if getattr(self, '_surface_state', None) is not None:
            self._surface_state.close()
            self._surface_state = None
        if datoviz is not None and getattr(self, 'scene', None):
            self.dvz.dvz_scene_destroy(self.scene)
            self.scene = None
        self._closed = True
        self._close_pending = False

    def __enter__(self) -> AtlasViewer:
        """Return this owned viewer."""
        return self

    def __exit__(self, *_exc_info) -> None:
        """Close this viewer when leaving its context."""
        self.close()

    def __del__(self) -> None:
        """Release native resources as a last-resort safeguard."""
        if hasattr(self, '_closed'):
            with suppress(Exception):
                AtlasViewer.close(self)
