"""Datoviz v0.4 atlas viewer with explicit native object ownership."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

import datoviz as dvz
import numpy as np

from ibl_atlas_assets import (
    AtlasAssetSet,
    AtlasRegionCatalog,
    MaterializedAtlasAssets,
    bundled_asset_set,
    verify_materialized_asset_set,
)

from .atlas import AtlasMesh
from .ontology import AtlasTreeModel, decode_region_key, encode_region_key

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import ModuleType

    from numpy.typing import NDArray


class AtlasViewer:
    """Own one Datoviz scene displaying an immutable atlas mesh pack."""

    def __init__(
        self,
        mesh: AtlasMesh,
        *,
        mapping: str = 'allen',
        palette: Mapping[int, Sequence[int]] | None = None,
        catalog: AtlasRegionCatalog | None = None,
        width: int = 900,
        height: int = 720,
        selection_dim_factor: float = 0.42,
        datoviz: ModuleType | None = None,
    ) -> None:
        if not 0 <= selection_dim_factor <= 1:
            raise ValueError('selection_dim_factor must be between zero and one')
        self.dvz = dvz if datoviz is None else datoviz
        self.mesh_data = mesh
        self.mapping = mapping
        self.catalog = catalog
        self.tree_model = AtlasTreeModel.from_catalog(catalog, mapping) if catalog else None
        self.palette = self.tree_model.palette if palette is None and self.tree_model else palette
        self.width = width
        self.height = height
        self.selection_dim_factor = selection_dim_factor
        self.scene = self.dvz.dvz_scene()
        if not self.scene:
            raise RuntimeError('dvz_scene() failed')
        self.app = None
        self.view = None
        self.arcball = None
        self.interaction = None
        self.region_tree = None
        self.gui = None
        self._mapping_control = ctypes.c_int(mesh.mapping_names.index(mapping))
        self._mapping_items = (ctypes.c_char_p * len(mesh.mapping_names))(
            *(name.title().encode() for name in mesh.mapping_names)
        )
        self._selected_region_ids: tuple[int, ...] = ()
        self._highlight_region_ids: tuple[int, ...] = ()
        self._last_mesh_region_ids: tuple[int, ...] = ()
        self._closed = False
        try:
            self.figure = self.dvz.dvz_figure(self.scene, width, height, 0)
            self.panel = self.dvz.dvz_panel_full(self.figure)
            self.dvz.dvz_panel_set_background_color(self.panel, self.dvz.DvzColor(8, 12, 18, 255))
            self.mesh = self.dvz.dvz_mesh(self.scene, 0)
            if not self.mesh:
                raise RuntimeError('dvz_mesh() failed')
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    self.mesh,
                    {
                        'position': mesh.positions,
                        'normal': mesh.normals,
                        'color': mesh.colors(mapping, self.palette),
                    },
                ),
                'dense mesh upload',
            )
            self._check(
                self.dvz.dvz_visual_set_index_data(self.mesh, mesh.indices),
                'mesh index upload',
            )
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
                    mesh.link_keys(mapping),
                ),
                'mesh region link keys',
            )
            self._check(self.dvz.dvz_panel_add_visual(self.panel, self.mesh, None), 'mesh attach')
            interaction_desc = self.dvz.dvz_item_interaction_desc()
            interaction_desc.target = self.dvz.DVZ_SCENE_TARGET_FACE
            self.interaction = self.dvz.dvz_item_interaction(
                self.panel, ctypes.byref(interaction_desc)
            )
            if not self.interaction:
                raise RuntimeError('dvz_item_interaction() failed')
            self.probe = None
        except Exception:
            self.close()
            raise

    @classmethod
    def from_pack(cls, path: str | Path, **kwargs) -> AtlasViewer:
        """Create a viewer from a verified local mesh pack."""
        return cls(AtlasMesh.from_pack(path), **kwargs)

    @classmethod
    def from_assets(cls, assets: MaterializedAtlasAssets, **kwargs) -> AtlasViewer:
        """Create a viewer from an already verified shared atlas asset graph."""
        if 'catalog' in kwargs:
            raise TypeError('from_assets() supplies the verified region catalog')
        return cls(
            AtlasMesh.from_geometry(assets.geometry), catalog=assets.regions, **kwargs
        )

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

    def set_mapping(
        self, mapping: str, palette: Mapping[int, Sequence[int]] | None = None
    ) -> None:
        """Change presentation colors and link identity without re-uploading geometry."""
        if self._closed:
            raise RuntimeError('viewer is closed')
        effective_palette = self.palette if palette is None else palette
        if self.catalog is not None and palette is None:
            self.tree_model = AtlasTreeModel.from_catalog(self.catalog, mapping)
            effective_palette = self.tree_model.palette
        self._check(
            self.dvz.dvz_visual_set_data(
                self.mesh, 'color', self.mesh_data.colors(mapping, effective_palette)
            ),
            'mapping color update',
        )
        self._check(
            self.dvz.dvz_visual_set_target_link_keys(
                self.mesh,
                self.dvz.DVZ_SCENE_TARGET_FACE,
                self.link_channel,
                self.mesh_data.link_keys(mapping),
            ),
            'mapping link-key update',
        )
        self._check(
            self.dvz.dvz_selection_clear(
                self.dvz.dvz_item_interaction_selection(self.interaction)
            ),
            'mapping selection reset',
        )
        self.mapping = mapping
        self.palette = effective_palette
        self._selected_region_ids = ()
        self._highlight_region_ids = ()
        self._last_mesh_region_ids = ()
        self._mapping_control.value = self.mesh_data.mapping_names.index(mapping)
        if self.region_tree is not None:
            self._replace_region_tree()

    def set_probe(
        self,
        points_um: Sequence[Sequence[float]],
        *,
        color: Sequence[int] = (255, 205, 72, 255),
        width_px: float = 4.0,
    ) -> None:
        """Add or replace a probe trajectory in atlas world micrometres."""
        positions = self.mesh_data.normalize_points(points_um)
        if len(positions) < 2:
            raise ValueError('a probe path needs at least two points')
        rgba = tuple(color) if len(color) == 4 else tuple(color) + (255,)
        colors = np.tile(np.asarray(rgba, dtype=np.uint8), (len(positions), 1))
        widths = np.full(len(positions), width_px, dtype=np.float32)
        if self.probe is None:
            self.probe = self.dvz.dvz_path(self.scene, 0)
            self._check(
                self.dvz.dvz_panel_add_visual(self.panel, self.probe, None), 'probe attach'
            )
            self.dvz.dvz_path_set_caps(
                self.probe, self.dvz.DVZ_SEGMENT_CAP_ROUND, self.dvz.DVZ_SEGMENT_CAP_ROUND
            )
            self.dvz.dvz_path_set_join(self.probe, self.dvz.DVZ_PATH_JOIN_ROUND, 4.0)
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.probe,
                {'position': positions, 'color': colors, 'stroke_width_px': widths},
            ),
            'probe upload',
        )

    def selected_region_ids(self) -> tuple[int, ...]:
        """Return the authoritative signed region selection."""
        return self._selected_region_ids

    def _mesh_selected_region_ids(self) -> tuple[int, ...]:
        selection = self.dvz.dvz_item_interaction_selection(self.interaction)
        count = self.dvz.dvz_selection_count(selection)
        if count == 0:
            return ()
        items = (self.dvz.DvzSelectionItem * count)()
        self.dvz.dvz_selection_copy(selection, items, count)
        signed = []
        for item in items:
            if item.link_key:
                value = np.asarray(item.link_key, dtype=np.uint64).view(np.int64).item()
                signed.append(value)
        return tuple(dict.fromkeys(signed))

    def _tree_selected_region_ids(self) -> tuple[int, ...]:
        if self.region_tree is None:
            return ()
        return tuple(
            decode_region_key(key)
            for key in self.dvz.dvz_gui_tree_get_selection(self.region_tree)
        )

    def set_selected_region_ids(self, region_ids: Sequence[int]) -> None:
        """Select signed or logical atlas regions and highlight their mapped descendants."""
        selected = tuple(dict.fromkeys(int(region_id) for region_id in region_ids if region_id))
        if self.tree_model is not None:
            available = {abs(int(region_id)) for region_id in self.tree_model.region_ids}
            missing = sorted({abs(region_id) for region_id in selected} - available)
            if missing:
                raise ValueError(f'regions are not members of {self.mapping}: {missing}')
        self._apply_selected_region_ids(selected, update_tree=True, clear_mesh=True)

    def clear_selection(self) -> None:
        """Clear tree, surface, and highlight selection state."""
        self.set_selected_region_ids(())

    def _replace_region_tree(self) -> None:
        if self.region_tree is not None:
            self.dvz.dvz_gui_tree_destroy(self.region_tree)
        model = self.tree_model
        if model is None:
            self.region_tree = None
            return
        self.region_tree = self.dvz.dvz_gui_tree(
            b'ibl_atlas_ontology',
            self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER
            | self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not self.region_tree:
            raise RuntimeError('dvz_gui_tree() failed')
        self._check(
            self.dvz.dvz_gui_tree_set_rows(
                self.region_tree,
                model.keys,
                model.parents,
                model.acronyms,
                model.names,
                self.dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
            ),
            'atlas ontology rows',
        )
        self._check(
            self.dvz.dvz_gui_tree_set_swatches(self.region_tree, model.colors),
            'atlas ontology colors',
        )
        styles = []
        for region_id, member in zip(model.region_ids, model.mapping_members, strict=True):
            if member:
                continue
            style = self.dvz.dvz_gui_data_style()
            style.flags = self.dvz.DVZ_GUI_DATA_STYLE_FLAGS_FOREGROUND
            style.row_key = encode_region_key(int(region_id))
            style.foreground = self.dvz.DvzColor(118, 126, 137, 255)
            styles.append(style)
        if styles:
            self._check(
                self.dvz.dvz_gui_tree_set_styles(self.region_tree, styles),
                'atlas ontology hierarchy styles',
            )
        self._check(
            self.dvz.dvz_gui_tree_expand_to_depth(self.region_tree, 3),
            'atlas ontology expansion',
        )
        self._set_tree_selection(self._selected_region_ids)

    def _gui_callback(self, gui, _view, _user_data) -> None:
        self.dvz.dvz_gui_dock_window_once(
            gui, b'Allen mouse brain atlas', self.dvz.DVZ_GUI_DOCK_SLOT_LEFT, 430.0
        )
        if self.dvz.dvz_gui_begin(gui, b'Allen mouse brain atlas', None, 0):
            self.dvz.dvz_gui_text(gui, b'CCF 2017 anatomy')
            if self.dvz.dvz_gui_combo(
                gui,
                b'Mapping##ibl_atlas_mapping',
                ctypes.byref(self._mapping_control),
                self._mapping_items,
                len(self._mapping_items),
            ):
                self.set_mapping(self.mesh_data.mapping_names[self._mapping_control.value])
            if self.dvz.dvz_gui_button(gui, b'Collapse all'):
                self.dvz.dvz_gui_tree_collapse_all(self.region_tree)
            self.dvz.dvz_gui_same_line(gui, 0.0, 8.0)
            if self.dvz.dvz_gui_button(gui, b'Expand 3 levels'):
                self.dvz.dvz_gui_tree_expand_to_depth(self.region_tree, 3)
            self.dvz.dvz_gui_same_line(gui, 0.0, 8.0)
            if self.dvz.dvz_gui_button(gui, b'Clear selection'):
                self.clear_selection()
            self.dvz.dvz_gui_separator_text(gui, b'Region hierarchy')
            _, events, dropped = self.dvz.dvz_gui_tree_draw(gui, self.region_tree)
            tree_changed = dropped > 0 or any(
                event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                for event in events
            )
            self._sync_selection_highlight(tree_changed=tree_changed)
            if self._selected_region_ids:
                self.dvz.dvz_gui_separator_text(gui, b'Selection')
                for region_id in self._selected_region_ids[:6]:
                    label = (
                        self.tree_model.describe(region_id)
                        if self.tree_model
                        else str(region_id)
                    )
                    self.dvz.dvz_gui_text(gui, label.encode())
                if len(self._selected_region_ids) > 6:
                    remaining = len(self._selected_region_ids) - 6
                    self.dvz.dvz_gui_text(gui, f'+ {remaining} more regions'.encode())
        self.dvz.dvz_gui_end(gui)

    def _set_tree_selection(self, region_ids: Sequence[int]) -> None:
        if self.region_tree is None or self.tree_model is None:
            return
        tree_ids = {int(region_id) for region_id in self.tree_model.region_ids}
        keys = np.asarray(
            [
                encode_region_key(-abs(int(region_id)))
                for region_id in region_ids
                if -abs(int(region_id)) in tree_ids
            ],
            dtype=np.uint64,
        )
        self._check(
            self.dvz.dvz_gui_tree_set_selection(self.region_tree, keys),
            'atlas ontology selection sync',
        )
        if len(keys) == 1:
            self._check(
                self.dvz.dvz_gui_tree_reveal(self.region_tree, int(keys[0])),
                'atlas ontology selection reveal',
            )

    def _apply_selected_region_ids(
        self,
        region_ids: tuple[int, ...],
        *,
        update_tree: bool,
        clear_mesh: bool,
    ) -> None:
        if clear_mesh:
            self._check(
                self.dvz.dvz_selection_clear(
                    self.dvz.dvz_item_interaction_selection(self.interaction)
                ),
                'surface selection clear',
            )
            self._last_mesh_region_ids = ()
        if update_tree:
            self._set_tree_selection(region_ids)
        self._selected_region_ids = region_ids
        logical_ids = (
            self.tree_model.expanded_logical_ids(region_ids)
            if self.tree_model is not None
            else tuple(sorted({abs(region_id) for region_id in region_ids if region_id}))
        )
        if logical_ids == self._highlight_region_ids:
            return
        base_colors = self.mesh_data.colors(self.mapping, self.palette)
        colors = base_colors
        if logical_ids:
            mask = np.isin(np.abs(self.mesh_data.mapping_ids(self.mapping)), logical_ids)
            dimmed = base_colors.astype(np.float32)
            dimmed[:, :3] *= self.selection_dim_factor
            colors = np.ascontiguousarray(np.rint(dimmed), dtype=np.uint8)
            colors[mask] = base_colors[mask]
        self._check(
            self.dvz.dvz_visual_set_data(self.mesh, 'color', colors),
            'selection color update',
        )
        self._highlight_region_ids = logical_ids

    def _sync_selection_highlight(self, *, tree_changed: bool = False) -> None:
        if tree_changed:
            self._apply_selected_region_ids(
                self._tree_selected_region_ids(), update_tree=False, clear_mesh=True
            )
            return
        mesh_region_ids = self._mesh_selected_region_ids()
        if mesh_region_ids == self._last_mesh_region_ids:
            return
        self._last_mesh_region_ids = mesh_region_ids
        self._apply_selected_region_ids(
            mesh_region_ids, update_tree=True, clear_mesh=False
        )

    def _create_view(self, *, offscreen: bool, title: str) -> None:
        if self.app is not None:
            raise RuntimeError('viewer already has an active app')
        self.app = self.dvz.dvz_app(self.scene)
        if not self.app:
            raise RuntimeError('dvz_app() failed')
        if offscreen:
            self.view = self.dvz.dvz_view_offscreen(self.app, self.figure, self.width, self.height)
        else:
            self.view = self.dvz.dvz_view_window(
                self.app, self.figure, self.width, self.height, title.encode()
            )
        if not self.view:
            raise RuntimeError('Datoviz view creation failed')
        self.arcball = self.dvz.dvz_view_arcball(self.view, self.panel, None)
        if not self.arcball:
            raise RuntimeError('dvz_view_arcball() failed')
        angles = (ctypes.c_float * 3)(-0.35, 0.25, 0.12)
        self._check(self.dvz.dvz_arcball_set(self.arcball, angles), 'arcball setup')
        if not offscreen and self.catalog is not None:
            self._replace_region_tree()
            config = self.dvz.dvz_gui_config()
            config.gui_flags = self.dvz.DVZ_GUI_FLAGS_DOCKING | self.dvz.DVZ_GUI_FLAGS_DOCKSPACE
            config.default_window_width = 430
            self.gui = self.dvz.dvz_view_gui(self.view, ctypes.byref(config))
            if not self.gui:
                raise RuntimeError('dvz_view_gui() failed')
            self._check(
                self.dvz.dvz_view_set_gui_callback(self.view, self._gui_callback, None),
                'atlas GUI callback',
            )

    def render_offscreen(self, output: str | Path | None = None) -> NDArray[np.uint8]:
        """Render exactly one frame and return a copied RGBA image."""
        self._create_view(offscreen=True, title='')
        self._check(self.dvz.dvz_view_render_once(self.view), 'offscreen render')
        rgba = np.array(self.dvz.dvz_view_capture_rgba(self.view), copy=True)
        if rgba.shape != (self.height, self.width, 4) or rgba.dtype != np.uint8:
            raise RuntimeError(f'unexpected capture shape or dtype: {rgba.shape} {rgba.dtype}')
        background = np.array([8, 12, 18], dtype=np.uint8)
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
        self._create_view(offscreen=False, title=title)
        self.dvz.dvz_app_run(self.app, frame_count)

    def close(self) -> None:
        """Destroy app before scene; scene owns all remaining handles."""
        if self._closed:
            return
        if self.app:
            self.dvz.dvz_app_destroy(self.app)
            self.app = None
        if self.region_tree is not None:
            self.dvz.dvz_gui_tree_destroy(self.region_tree)
            self.region_tree = None
        if self.scene:
            self.dvz.dvz_scene_destroy(self.scene)
            self.scene = None
        self._closed = True

    def __enter__(self) -> AtlasViewer:
        """Return this owned viewer."""
        return self

    def __exit__(self, *_exc_info) -> None:
        """Close this viewer when leaving its context."""
        self.close()

    def __del__(self) -> None:
        """Release native resources as a last-resort safeguard."""
        if hasattr(self, '_closed'):
            self.close()
