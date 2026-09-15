"""Datoviz v0.4 atlas viewer with explicit native object ownership."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

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
from .ontology import ROOT_PARENT, AtlasTreeModel, decode_region_key, encode_region_key

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import ModuleType
    from typing import Literal

    from numpy.typing import NDArray

    from .probe import ProbeSites
    from .regions import AtlasRegionValues


class AtlasViewer:
    """Own one Datoviz scene displaying an immutable atlas mesh pack."""

    def __init__(  # noqa: PLR0915
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
        surface_opacity: float = 1.0,
        ui_scale: float = 1.0,
        sidebar_width: float = 340.0,
        tree_root_acronym: str = 'grey',
        enable_interaction: bool = True,
        datoviz: ModuleType | None = None,
    ) -> None:
        if not np.isfinite(selection_dim_factor) or not 0 <= selection_dim_factor <= 1:
            raise ValueError('selection_dim_factor must be between zero and one')
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
        self.camera_angles = self._validated_camera_angles(camera_angles)
        self.dvz = dvz if datoviz is None else datoviz
        self.mesh_data = mesh
        self.mapping = mapping
        self.catalog = catalog
        self.tree_model = AtlasTreeModel.from_catalog(catalog, mapping) if catalog else None
        self.palette = self.tree_model.palette if palette is None and self.tree_model else palette
        self.width = width
        self.height = height
        self.explode = float(explode)
        self.selection_dim_factor = selection_dim_factor
        self.surface_opacity = surface_opacity
        self.ui_scale = float(ui_scale)
        self.sidebar_width = float(sidebar_width)
        self.tree_root_acronym = tree_root_acronym
        self.enable_interaction = bool(enable_interaction)
        self.scene = self.dvz.dvz_scene()
        if not self.scene:
            raise RuntimeError('dvz_scene() failed')
        self.app, self.view, self.arcball, self.arcball_controller = None, None, None, None
        self.host_figure = None
        self.viewport = None
        self.interaction = None
        self.region_tree, self.region_table = None, None
        self.probe_table = None
        self.gui = None
        self.probe_sites = None
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
        self._last_surface_emphasis: tuple[tuple[int, ...], tuple[int, ...]] | None = None
        self._surface_base_colors_cache: NDArray[np.uint8] | None = None
        self._surface_mapping_ids_cache: NDArray[np.int64] | None = None
        self._surface_dimmed_colors_cache: NDArray[np.uint8] | None = None
        self._surface_emphasis_work: NDArray[np.uint8] | None = None
        self._surface_alpha_mode: int | None = None
        self._last_mesh_region_ids: tuple[int, ...] = ()
        self._closed = False
        try:
            self._create_layout()
            self._create_surface()
            if self.enable_interaction:
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

    def _create_layout(self) -> None:
        """Create the figure and primary 3-D panel."""
        self.figure = self.dvz.dvz_figure(self.scene, self.width, self.height, 0)
        self.panel = self.dvz.dvz_panel_full(self.figure)
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
        self.camera_angles = self._validated_camera_angles(angles)
        if self.arcball is not None:
            native = (ctypes.c_float * 3)(*self.camera_angles)
            self._check(self.dvz.dvz_arcball_set(self.arcball, native), 'arcball update')

    def _surface_colors(
        self,
        mapping: str,
        palette: Mapping[int, Sequence[int]] | None,
    ) -> NDArray[np.uint8]:
        colors = self.mesh_data.colors(mapping, palette)
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
        surface_colors = self._display_surface_colors()
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.mesh,
                {
                    'position': self.mesh_data.exploded_positions(self.explode),
                    'normal': self.mesh_data.normals,
                    'color': surface_colors,
                },
            ),
            'dense mesh upload',
        )
        self._invalidate_surface_emphasis_cache(surface_colors)
        self._update_surface_alpha_mode()
        self._check(
            self.dvz.dvz_visual_set_index_data(self.mesh, self.mesh_data.indices),
            'mesh index upload',
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
                self.mesh_data.link_keys(self.mapping),
            ),
            'mesh region link keys',
        )
        self._check(self.dvz.dvz_panel_add_visual(self.panel, self.mesh, None), 'mesh attach')

    def set_explode(self, amount: float) -> None:
        """Explode mesh components along their canonical centroid displacement vectors."""
        if self._closed:
            raise RuntimeError('viewer is closed')
        if not np.isfinite(amount) or not 0 <= amount <= 1:
            raise ValueError('explode must be between zero and one')
        amount = float(amount)
        self._explode_control.value = amount
        if amount == self.explode:
            return
        self._check(
            self.dvz.dvz_visual_set_data(
                self.mesh, 'position', self.mesh_data.exploded_positions(amount)
            ),
            'mesh explode position update',
        )
        self.explode = amount

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
        surface_colors = self._display_surface_colors(mapping, effective_palette)
        self._check(
            self.dvz.dvz_visual_set_data(self.mesh, 'color', surface_colors),
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
        if self.interaction is not None:
            self._check(
                self.dvz.dvz_selection_clear(
                    self.dvz.dvz_item_interaction_selection(self.interaction)
                ),
                'mapping selection reset',
            )
        self.mapping = mapping
        self.palette = effective_palette
        self._selected_region_ids = ()
        self._hovered_region_ids = ()
        self._highlight_region_ids = ()
        self._invalidate_surface_emphasis_cache(surface_colors)
        self._last_mesh_region_ids = ()
        self._mapping_control.value = self.mesh_data.mapping_names.index(mapping)
        if self.region_tree is not None:
            self._replace_region_tree()
        if self.probe_data is not None:
            mapped_ids = self._mapped_probe_region_ids()
            self._check(
                self.dvz.dvz_visual_set_link_keys(
                    self.probe_sites, self.link_channel, mapped_ids.view(np.uint64)
                ),
                'probe site mapping link keys',
            )
            if self.probe_table is not None:
                self._replace_probe_table()
        if self.region_data is not None and self.region_table is not None:
            self._replace_region_table()

    def _display_surface_colors(
        self,
        mapping: str | None = None,
        palette: Mapping[int, Sequence[int]] | None = None,
    ) -> NDArray[np.uint8]:
        """Return canonical or scalar-colored surface vertices for the active mapping."""
        active_mapping = self.mapping if mapping is None else mapping
        active_palette = self.palette if palette is None else palette
        if self.region_data is None:
            return self._surface_colors(active_mapping, active_palette)
        region_ids, _, _, _, value_colors = self._mapped_region_values(active_mapping)
        return self._region_surface_colors(active_mapping, region_ids, value_colors)

    def _region_surface_colors(
        self,
        mapping: str,
        region_ids: NDArray[np.int64],
        value_colors: NDArray[np.uint8],
    ) -> NDArray[np.uint8]:
        """Expand one color per presentation region to dense mesh vertices."""
        alpha = int(round(255 * self.surface_opacity))
        lookup = np.tile(
            np.asarray((46, 52, 62, alpha), dtype=np.uint8),
            (len(self.mesh_data.presentations), 1),
        )
        by_region = dict(zip(region_ids, value_colors, strict=True))
        for presentation in self.mesh_data.presentations:
            mapped_id = presentation['mappings'][mapping]
            color = by_region.get(mapped_id)
            if color is not None:
                lookup[presentation['presentation_id']] = color
        return np.ascontiguousarray(lookup[self.mesh_data.presentation_ids])

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
        if self.catalog is None:
            raise ValueError('linked region data requires an atlas region catalog')
        if color_scheme not in ('diverging', 'sequential'):
            raise ValueError(f'unknown region color scheme: {color_scheme}')
        if mapping_reduction != 'weighted_mean':
            raise ValueError(f'unknown region mapping reduction: {mapping_reduction}')
        if opacity is not None and (not np.isfinite(opacity) or not 0 <= opacity <= 1):
            raise ValueError('region opacity must be between zero and one')
        prepared = self._region_value_view(data, self.mapping, value_range, color_scheme, opacity)
        surface_colors = self._region_surface_colors(self.mapping, prepared[0], prepared[4])
        self._check(
            self.dvz.dvz_visual_set_data(self.mesh, 'color', surface_colors),
            'region scalar color update',
        )
        self.region_data = data
        self._region_value_range = value_range
        self._region_color_scheme = color_scheme
        self._region_opacity = opacity
        selected = self._selected_region_ids
        self._highlight_region_ids = ()
        self._invalidate_surface_emphasis_cache(surface_colors)
        if selected or self._hovered_region_ids:
            self._apply_selected_region_ids(
                selected, update_tree=False, update_table=False, clear_mesh=False
            )
        if self.gui is not None:
            self._replace_region_table()

    def _mapped_region_values(
        self, mapping: str | None = None
    ) -> tuple[
        NDArray[np.int64],
        NDArray[np.float64],
        NDArray[np.float64],
        tuple[str, ...],
        NDArray[np.uint8],
    ]:
        """Return the active weighted-mean regional presentation."""
        data = self.region_data
        if data is None or self.catalog is None:
            empty_i = np.empty(0, dtype=np.int64)
            empty_f = np.empty(0, dtype=np.float64)
            empty_c = np.empty((0, 4), dtype=np.uint8)
            return empty_i, empty_f, empty_f, (), empty_c
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
    ) -> tuple[
        NDArray[np.int64],
        NDArray[np.float64],
        NDArray[np.float64],
        tuple[str, ...],
        NDArray[np.uint8],
    ]:
        """Build one weighted-mean mapping presentation without mutating state."""
        assert self.catalog is not None
        try:
            mapped_ids = self.catalog.map_allen_ids(data.allen_region_ids, mapping)
        except KeyError as error:
            raise ValueError(str(error)) from error
        grouped: dict[int, list[tuple[float, float]]] = {}
        for mapped_id, value, weight in zip(mapped_ids, data.values, data.weights, strict=True):
            if mapped_id is None or mapped_id == 0:
                continue
            grouped.setdefault(mapped_id, []).append((float(value), float(weight)))
        region_ids = np.ascontiguousarray(sorted(grouped), dtype=np.int64)
        values = np.empty(len(region_ids), dtype=np.float64)
        weights = np.empty(len(region_ids), dtype=np.float64)
        for index, region_id in enumerate(region_ids):
            entries = grouped[int(region_id)]
            weights[index] = sum(weight for _, weight in entries)
            finite = [(value, weight) for value, weight in entries if np.isfinite(value)]
            values[index] = (
                sum(value * weight for value, weight in finite)
                / sum(weight for _, weight in finite)
                if finite
                else np.nan
            )
        model = (
            self.tree_model
            if self.tree_model is not None and self.tree_model.mapping == mapping
            else None
        )
        labels = tuple(
            model.describe(int(region_id)) if model else str(region_id) for region_id in region_ids
        )
        colors = self._probe_value_colors(values, value_range, color_scheme)
        effective_opacity = self.surface_opacity if opacity is None else opacity
        if effective_opacity < 1:
            colors = colors.copy()
            colors[:, 3] = np.rint(colors[:, 3] * effective_opacity).astype(np.uint8)
        return region_ids, values, weights, labels, colors

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
        """Add or replace probe sites, optionally colored by one scalar feature."""
        positions = self.mesh_data.normalize_points(points_um)
        count = len(positions)
        if count == 0:
            raise ValueError('probe sites cannot be empty')
        if radius_um <= 0:
            raise ValueError('probe site radius must be positive')
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
            if scalar.shape != (count,):
                raise ValueError('probe values must have shape (n,)')
            rgba = self._probe_value_colors(scalar, value_range, color_scheme)
        else:
            rgba = np.tile(np.asarray((255, 205, 72, 255), dtype=np.uint8), (count, 1))

        radii = np.full(count, radius_um * self.mesh_data.display_scale, dtype=np.float32)
        if self.probe_sites is None:
            self.probe_sites = self.dvz.dvz_sphere(self.scene, 0)
            if not self.probe_sites:
                raise RuntimeError('dvz_sphere() failed')
            self._check(
                self.dvz.dvz_panel_add_visual(self.panel, self.probe_sites, None),
                'probe sites attach',
            )
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.probe_sites,
                {'position': positions, 'color': rgba, 'radius': radii},
            ),
            'probe sites upload',
        )

    def set_probe_data(
        self,
        data: ProbeSites,
        *,
        value_range: tuple[float, float] | None = None,
        radius_um: float = 45.0,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> None:
        """Display a typed probe payload and link its Allen labels to atlas presentation."""
        if self.catalog is None:
            raise ValueError('linked probe data requires an atlas region catalog')
        mapped_ids = self._mapped_probe_region_ids(data)
        colors = self._probe_value_colors(data.values, value_range, color_scheme)
        self.set_probe_sites(data.positions_um, colors=colors, radius_um=radius_um)
        self.probe_data = data
        self._probe_colors = colors
        self._check(
            self.dvz.dvz_visual_set_link_keys(
                self.probe_sites, self.link_channel, mapped_ids.view(np.uint64)
            ),
            'probe site link keys',
        )
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
        if color_scheme not in ('diverging', 'sequential'):
            raise ValueError(f'unknown probe color scheme: {color_scheme}')
        finite = np.isfinite(values)
        if value_range is None:
            if not np.any(finite):
                limits = (0.0, 1.0)
            else:
                limits = (float(np.min(values[finite])), float(np.max(values[finite])))
        else:
            limits = (float(value_range[0]), float(value_range[1]))
        constant = value_range is None and limits[1] == limits[0]
        if (
            not np.isfinite(limits).all()
            or (limits[1] < limits[0])
            or (value_range is not None and limits[1] == limits[0])
        ):
            raise ValueError('probe value range must be finite and increasing')

        t = (
            np.full(len(values), 0.5, dtype=np.float64)
            if constant
            else np.clip((values - limits[0]) / (limits[1] - limits[0]), 0.0, 1.0)
        )
        if color_scheme == 'sequential':
            low = np.asarray((88, 70, 180), dtype=np.float64)
            middle = np.asarray((45, 180, 170), dtype=np.float64)
            high = np.asarray((253, 231, 73), dtype=np.float64)
        else:
            low = np.asarray((49, 116, 178), dtype=np.float64)
            middle = np.asarray((247, 247, 247), dtype=np.float64)
            high = np.asarray((203, 45, 62), dtype=np.float64)
        rgb = np.empty((len(values), 3), dtype=np.float64)
        lower = t <= 0.5
        rgb[lower] = low + (middle - low) * (2 * t[lower, None])
        rgb[~lower] = middle + (high - middle) * (2 * t[~lower, None] - 1)
        rgb[~finite] = (110, 116, 126)
        return np.ascontiguousarray(
            np.column_stack((np.rint(rgb), np.full(len(values), 255))), dtype=np.uint8
        )

    def selected_region_ids(self) -> tuple[int, ...]:
        """Return the authoritative signed region selection."""
        return self._selected_region_ids

    def _emphasis_region_ids(self) -> tuple[int, ...]:
        """Return committed identities that may dim unselected regions."""
        return self._selected_region_ids

    def _mesh_hovered_region_ids(self) -> tuple[int, ...]:
        """Return the signed region identity under the retained 3-D hover query."""
        if self.interaction is None:
            return ()
        hover = self.dvz.dvz_item_interaction_hover(self.interaction)
        if not hover:
            return ()
        item = self.dvz.DvzSelectionItem()
        if not self.dvz.dvz_hover_copy(hover, ctypes.byref(item)) or not item.link_key:
            return ()
        signed = np.asarray(item.link_key, dtype=np.uint64).view(np.int64).item()
        return (int(signed),) if signed else ()

    def _set_hovered_region_ids(self, region_ids: Sequence[int]) -> bool:
        """Set transient hover emphasis without changing committed selection."""
        hovered = tuple(dict.fromkeys(int(region_id) for region_id in region_ids if region_id))
        if hovered == self._hovered_region_ids:
            return False
        self._hovered_region_ids = hovered
        self._update_surface_emphasis()
        return True

    def _sync_viewport_hover(self, hovered: bool) -> None:
        """Synchronize transient hover from a plain 3-D viewport."""
        self._set_hovered_region_ids(self._mesh_hovered_region_ids() if hovered else ())

    def _mesh_selected_region_ids(self) -> tuple[int, ...]:
        if self.interaction is None:
            return ()
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
            decode_region_key(key) for key in self.dvz.dvz_gui_tree_get_selection(self.region_tree)
        )

    def set_selected_region_ids(self, region_ids: Sequence[int]) -> None:
        """Select signed or logical atlas regions and highlight their mapped descendants."""
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

    def _replace_probe_table(self) -> None:
        if self.probe_table is not None:
            self.dvz.dvz_gui_table_destroy(self.probe_table)
        data = self.probe_data
        if data is None:
            self.probe_table = None
            return
        columns = [
            {
                'column_id': 1,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Site',
            },
            {
                'column_id': 2,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': 'DV (µm)',
                'format': '%.0f',
            },
            {
                'column_id': 3,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.value_name,
                'format': '%.3f',
            },
            {
                'column_id': 4,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Region',
            },
            {'column_id': 5, 'type': self.dvz.DVZ_GUI_TABLE_COLUMN_COLOR, 'title': ''},
        ]
        self.probe_table = self.dvz.dvz_gui_table(
            b'ibl_probe_sites',
            columns,
            self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER
            | self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not self.probe_table:
            raise RuntimeError('dvz_gui_table() failed')
        mapped_ids = self._mapped_probe_region_ids()
        region_labels = tuple(
            self.tree_model.describe(region_id) if self.tree_model else str(region_id)
            for region_id in mapped_ids
        )
        setters = (
            (
                self.dvz.dvz_gui_table_set_rows,
                (self.probe_table, data.site_ids, self.dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE),
                'probe table rows',
            ),
            (
                self.dvz.dvz_gui_table_set_column_text,
                (self.probe_table, 1, data.labels),
                'probe table labels',
            ),
            (
                self.dvz.dvz_gui_table_set_column_double,
                (self.probe_table, 2, data.positions_um[:, 2].astype(np.float64)),
                'probe table depth',
            ),
            (
                self.dvz.dvz_gui_table_set_column_double,
                (self.probe_table, 3, data.values),
                'probe table values',
            ),
            (
                self.dvz.dvz_gui_table_set_column_text,
                (self.probe_table, 4, region_labels),
                'probe table regions',
            ),
            (
                self.dvz.dvz_gui_table_set_column_color,
                (self.probe_table, 5, self._probe_colors),
                'probe table colors',
            ),
        )
        for setter, args, action in setters:
            self._check(setter(*args), action)
        self._set_probe_table_selection(self._selected_region_ids)

    def _probe_table_selected_region_ids(self) -> tuple[int, ...]:
        if self.probe_table is None or self.probe_data is None:
            return ()
        selected_keys = set(self.dvz.dvz_gui_table_get_selection(self.probe_table))
        mapped_ids = self._mapped_probe_region_ids()
        return tuple(
            dict.fromkeys(
                int(region_id)
                for site_id, region_id in zip(self.probe_data.site_ids, mapped_ids, strict=True)
                if int(site_id) in selected_keys and region_id
            )
        )

    def _set_probe_table_selection(self, region_ids: Sequence[int]) -> None:
        if self.probe_table is None or self.probe_data is None:
            return
        logical_ids = (
            self.tree_model.expanded_logical_ids(tuple(region_ids))
            if self.tree_model is not None
            else tuple(abs(int(region_id)) for region_id in region_ids)
        )
        mapped_ids = self._mapped_probe_region_ids()
        keys = self.probe_data.site_ids[np.isin(np.abs(mapped_ids), logical_ids)]
        self._check(
            self.dvz.dvz_gui_table_set_selection(self.probe_table, keys),
            'probe table selection sync',
        )

    def _replace_region_table(self) -> None:
        if self.region_table is not None:
            self.dvz.dvz_gui_table_destroy(self.region_table)
        data = self.region_data
        if data is None:
            self.region_table = None
            return
        columns = [
            {
                'column_id': 1,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Region',
            },
            {
                'column_id': 2,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.value_name,
                'format': '%.3f',
            },
            {
                'column_id': 3,
                'type': self.dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': self.dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.weight_name,
                'format': '%.0f',
            },
            {'column_id': 4, 'type': self.dvz.DVZ_GUI_TABLE_COLUMN_COLOR, 'title': ''},
        ]
        self.region_table = self.dvz.dvz_gui_table(
            b'ibl_region_values',
            columns,
            self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER
            | self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not self.region_table:
            raise RuntimeError('dvz_gui_table() failed')
        region_ids, values, weights, labels, colors = self._mapped_region_values()
        keys = np.ascontiguousarray(region_ids.view(np.uint64))
        setters = (
            (
                self.dvz.dvz_gui_table_set_rows,
                (self.region_table, keys, self.dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE),
                'region table rows',
            ),
            (
                self.dvz.dvz_gui_table_set_column_text,
                (self.region_table, 1, labels),
                'region table labels',
            ),
            (
                self.dvz.dvz_gui_table_set_column_double,
                (self.region_table, 2, values),
                'region table values',
            ),
            (
                self.dvz.dvz_gui_table_set_column_double,
                (self.region_table, 3, weights),
                'region table weights',
            ),
            (
                self.dvz.dvz_gui_table_set_column_color,
                (self.region_table, 4, colors),
                'region table colors',
            ),
        )
        for setter, args, action in setters:
            self._check(setter(*args), action)
        self._set_region_table_selection(self._selected_region_ids)

    def _region_table_selected_region_ids(self) -> tuple[int, ...]:
        if self.region_table is None:
            return ()
        return tuple(
            decode_region_key(key)
            for key in self.dvz.dvz_gui_table_get_selection(self.region_table)
        )

    def _set_region_table_selection(self, region_ids: Sequence[int]) -> None:
        if self.region_table is None:
            return
        available, _, _, _, _ = self._mapped_region_values()
        logical_ids = (
            self.tree_model.expanded_logical_ids(tuple(region_ids))
            if self.tree_model is not None
            else tuple(abs(int(region_id)) for region_id in region_ids)
        )
        keys = np.ascontiguousarray(
            available[np.isin(np.abs(available), logical_ids)].view(np.uint64)
        )
        self._check(
            self.dvz.dvz_gui_table_set_selection(self.region_table, keys),
            'region table selection sync',
        )

    def _replace_region_tree(self) -> None:
        if self.region_tree is not None:
            self.dvz.dvz_gui_tree_destroy(self.region_tree)
        model = self.tree_model
        if model is None:
            self.region_tree = None
            return
        self.region_tree = self.dvz.dvz_gui_tree(
            b'ibl_atlas_ontology',
            self.dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not self.region_tree:
            raise RuntimeError('dvz_gui_tree() failed')
        row_indices = model.subtree_row_indices(self.tree_root_acronym)
        old_to_new = {int(old): new for new, old in enumerate(row_indices)}
        parents = np.ascontiguousarray(
            [
                ROOT_PARENT
                if int(model.parents[old]) == ROOT_PARENT
                or int(model.parents[old]) not in old_to_new
                else old_to_new[int(model.parents[old])]
                for old in row_indices
            ],
            dtype=np.uint32,
        )
        labels = tuple(model.acronyms[index] for index in row_indices)
        names = tuple(model.names[index] for index in row_indices)
        self._check(
            self.dvz.dvz_gui_tree_set_rows(
                self.region_tree,
                model.keys[row_indices],
                parents,
                labels,
                names,
                self.dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
            ),
            'atlas ontology rows',
        )
        self._check(
            self.dvz.dvz_gui_tree_set_swatches(self.region_tree, model.colors[row_indices]),
            'atlas ontology colors',
        )
        if self._tree_filter.value:
            self._check(
                self.dvz.dvz_gui_tree_set_filter(self.region_tree, self._tree_filter.value),
                'atlas ontology filter restore',
            )
        styles = []
        for region_id, member in zip(
            model.region_ids[row_indices], model.mapping_members[row_indices], strict=True
        ):
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

    def _gui_callback(self, gui, _view, _user_data) -> None:  # noqa: PLR0912, PLR0915
        self.dvz.dvz_gui_dock_window_once(
            gui,
            b'Allen mouse brain atlas',
            self.dvz.DVZ_GUI_DOCK_SLOT_LEFT,
            self.sidebar_width,
        )
        if self.viewport is not None:
            self.dvz.dvz_gui_dock_window_once(
                gui, b'Atlas views', self.dvz.DVZ_GUI_DOCK_SLOT_CENTER, 0.0
            )
        if self.dvz.dvz_gui_begin(gui, b'Allen mouse brain atlas', None, 0):
            self.dvz.dvz_gui_text(gui, b'CCF 2017 anatomy')
            if self.catalog is not None and self.dvz.dvz_gui_slider_float(
                gui,
                b'Explode regions',
                ctypes.byref(self._explode_control),
                0.0,
                1.0,
            ):
                self.set_explode(self._explode_control.value)
            if self.dvz.dvz_gui_combo(
                gui,
                b'Mapping##ibl_atlas_mapping',
                ctypes.byref(self._mapping_control),
                self._mapping_items,
                len(self._mapping_items),
            ):
                self.set_mapping(self.mesh_data.mapping_names[self._mapping_control.value])
            if self.dvz.dvz_gui_button(gui, b'Clear region selection'):
                self.clear_selection()
            self._draw_extra_gui(gui)
            if self.dvz.dvz_gui_button(gui, b'Collapse all'):
                self.dvz.dvz_gui_tree_collapse_all(self.region_tree)
            self.dvz.dvz_gui_same_line(gui, 0.0, 8.0)
            if self.dvz.dvz_gui_button(gui, b'Expand all'):
                self._check(
                    self.dvz.dvz_gui_tree_expand_all(self.region_tree),
                    'atlas ontology expansion',
                )
            self.dvz.dvz_gui_same_line(gui, 0.0, 8.0)
            if self.dvz.dvz_gui_button(gui, b'Expand 3 levels'):
                self.dvz.dvz_gui_tree_expand_to_depth(self.region_tree, 3)
            if self._selected_region_ids:
                self.dvz.dvz_gui_separator_text(gui, b'Selection')
                for region_id in self._selected_region_ids[:6]:
                    label = (
                        self.tree_model.describe(region_id) if self.tree_model else str(region_id)
                    )
                    self.dvz.dvz_gui_text(gui, label.encode())
                if len(self._selected_region_ids) > 6:
                    remaining = len(self._selected_region_ids) - 6
                    self.dvz.dvz_gui_text(gui, f'+ {remaining} more regions'.encode())
            if self.dvz.dvz_gui_input_text(
                gui, b'Filter regions', self._tree_filter, len(self._tree_filter)
            ):
                self._check(
                    self.dvz.dvz_gui_tree_set_filter(self.region_tree, self._tree_filter.value),
                    'atlas ontology filter',
                )
            self.dvz.dvz_gui_separator_text(gui, b'Region hierarchy')
            scroll_tree = self.region_table is None and self.probe_table is None
            tree_visible = True
            if scroll_tree:
                tree_visible = self.dvz.dvz_gui_begin_child(
                    gui, b'Atlas region hierarchy', 0.0, 0.0, 0
                )
            events = ()
            if tree_visible:
                _, events, _dropped = self.dvz.dvz_gui_tree_draw(gui, self.region_tree)
            if scroll_tree:
                self.dvz.dvz_gui_end_child(gui)
            tree_changed = any(
                event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED for event in events
            )
            table_changed = False
            region_table_changed = False
            if self.region_table is not None:
                self.dvz.dvz_gui_separator_text(gui, b'Region values')
                _, region_events, _region_dropped = self.dvz.dvz_gui_table_draw(
                    gui, self.region_table
                )
                region_table_changed = any(
                    event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                    for event in region_events
                )
            if self.probe_table is not None:
                self.dvz.dvz_gui_separator_text(gui, b'Probe sites')
                _, table_events, _table_dropped = self.dvz.dvz_gui_table_draw(
                    gui, self.probe_table
                )
                table_changed = any(
                    event.type == self.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                    for event in table_events
                )
            self._sync_selection_highlight(
                tree_changed=tree_changed,
                table_changed=table_changed,
                region_table_changed=region_table_changed,
            )
        self.dvz.dvz_gui_end(gui)
        if self.viewport is not None:
            self.dvz.dvz_gui_viewport_window(self.viewport, b'Atlas views', None, 0)
            hovered = ctypes.c_bool()
            mouse_pos = (ctypes.c_float * 2)()
            viewport_size = (ctypes.c_float * 2)()
            if self.dvz.dvz_gui_viewport_mouse(
                self.viewport, mouse_pos, viewport_size, ctypes.byref(hovered)
            ):
                self._sync_viewport_hover(bool(hovered.value))
            if hovered.value and getattr(self, '_hovered_region_label', None):
                self.dvz.dvz_gui_tooltip(gui, self._hovered_region_label.encode())

    def _draw_extra_gui(self, _gui) -> None:
        """Draw optional controls supplied by specialized viewers."""

    def _set_tree_selection(self, region_ids: Sequence[int]) -> None:
        if self.region_tree is None or self.tree_model is None:
            return
        row_indices = self.tree_model.subtree_row_indices(self.tree_root_acronym)
        tree_ids = {int(self.tree_model.region_ids[index]) for index in row_indices}
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
        update_table: bool,
        clear_mesh: bool,
    ) -> None:
        if clear_mesh and self.interaction is not None:
            self._check(
                self.dvz.dvz_selection_clear(
                    self.dvz.dvz_item_interaction_selection(self.interaction)
                ),
                'surface selection clear',
            )
            self._last_mesh_region_ids = ()
        if update_tree:
            self._set_tree_selection(region_ids)
        if update_table:
            self._set_probe_table_selection(region_ids)
            self._set_region_table_selection(region_ids)
        self._selected_region_ids = region_ids
        self._update_surface_emphasis()

    def _update_surface_emphasis(self) -> None:
        """Fade non-selected regions and brighten hover without affecting unrelated regions."""
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
        state = (selected_ids, hovered_ids)
        if state == self._last_surface_emphasis:
            return
        self._update_surface_alpha_mode()
        base_colors, mapping_ids = self._surface_emphasis_inputs()
        if self._surface_emphasis_work is None:
            self._surface_emphasis_work = np.empty_like(base_colors)
        colors = self._surface_emphasis_work
        np.copyto(colors, base_colors)
        if selected_ids:
            mask = np.isin(mapping_ids, selected_ids)
            if self._surface_dimmed_colors_cache is None:
                dimmed = base_colors.astype(np.float32)
                dimmed[:, :3] *= self.selection_dim_factor
                dimmed[:, 3] = 0
                self._surface_dimmed_colors_cache = np.ascontiguousarray(
                    np.rint(dimmed), dtype=np.uint8
                )
            np.copyto(colors, self._surface_dimmed_colors_cache)
            colors[mask] = base_colors[mask]
            colors[mask, 3] = np.maximum(colors[mask, 3], 220)
        if hovered_ids:
            hover_mask = np.isin(mapping_ids, hovered_ids)
            hovered_rgb = 0.72 * base_colors[hover_mask, :3].astype(np.float32) + 0.28 * 255
            colors[hover_mask, :3] = np.rint(hovered_rgb).astype(np.uint8)
            colors[hover_mask, 3] = np.maximum(base_colors[hover_mask, 3], 235)
        self._check(
            self.dvz.dvz_visual_set_data(self.mesh, 'color', colors),
            'selection and hover color update',
        )
        self._highlight_region_ids = selected_ids
        self._last_surface_emphasis = state

    def _update_surface_alpha_mode(self) -> None:
        """Use transparency only when requested explicitly or required by selection."""
        selection_active = bool(getattr(self, '_selected_region_ids', ()))
        mode = (
            self.dvz.DVZ_ALPHA_WBOIT
            if self.surface_opacity < 1 or selection_active
            else self.dvz.DVZ_ALPHA_OPAQUE
        )
        if mode == self._surface_alpha_mode:
            return
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.mesh, mode),
            'surface transparency mode',
        )
        self._surface_alpha_mode = mode

    def _invalidate_surface_emphasis_cache(
        self, base_colors: NDArray[np.uint8] | None = None
    ) -> None:
        """Invalidate derived surface styling after canonical color or mapping changes."""
        self._surface_base_colors_cache = base_colors
        self._surface_mapping_ids_cache = None
        self._surface_dimmed_colors_cache = None
        self._surface_emphasis_work = None
        self._last_surface_emphasis = None

    def _surface_emphasis_inputs(self) -> tuple[NDArray[np.uint8], NDArray[np.int64]]:
        """Return cached canonical colors and absolute region IDs for interactive styling."""
        if self._surface_base_colors_cache is None:
            self._surface_base_colors_cache = self._display_surface_colors()
        if self._surface_mapping_ids_cache is None:
            self._surface_mapping_ids_cache = np.ascontiguousarray(
                np.abs(self.mesh_data.mapping_ids(self.mapping)), dtype=np.int64
            )
        return self._surface_base_colors_cache, self._surface_mapping_ids_cache

    def _sync_selection_highlight(
        self,
        *,
        tree_changed: bool = False,
        table_changed: bool = False,
        region_table_changed: bool = False,
    ) -> None:
        if region_table_changed:
            self._apply_selected_region_ids(
                self._region_table_selected_region_ids(),
                update_tree=True,
                update_table=False,
                clear_mesh=True,
            )
            self._set_probe_table_selection(self._selected_region_ids)
            return
        if table_changed:
            self._apply_selected_region_ids(
                self._probe_table_selected_region_ids(),
                update_tree=True,
                update_table=False,
                clear_mesh=True,
            )
            return
        if tree_changed:
            self._apply_selected_region_ids(
                self._tree_selected_region_ids(),
                update_tree=False,
                update_table=True,
                clear_mesh=True,
            )
            return
        mesh_region_ids = self._mesh_selected_region_ids()
        if mesh_region_ids == self._last_mesh_region_ids:
            return
        self._last_mesh_region_ids = mesh_region_ids
        self._apply_selected_region_ids(
            mesh_region_ids, update_tree=True, update_table=True, clear_mesh=False
        )

    def _create_view(self, *, offscreen: bool, title: str) -> None:  # noqa: PLR0912, PLR0915
        if self.app is not None:
            raise RuntimeError('viewer already has an active app')
        self.app = self.dvz.dvz_app(self.scene)
        if not self.app:
            raise RuntimeError('dvz_app() failed')
        if offscreen:
            self.view = self.dvz.dvz_view_offscreen(self.app, self.figure, self.width, self.height)
            if not self.view:
                raise RuntimeError('Datoviz view creation failed')
            self.arcball = self.dvz.dvz_view_arcball(self.view, self.panel, None)
        elif self.catalog is None:
            self.view = self.dvz.dvz_view_window(
                self.app, self.figure, self.width, self.height, title.encode()
            )
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
            self.view = self.dvz.dvz_view_window(
                self.app, self.host_figure, self.width, self.height, title.encode()
            )
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
            config.gui_flags = self.dvz.DVZ_GUI_FLAGS_DOCKING | self.dvz.DVZ_GUI_FLAGS_DOCKSPACE
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
        self._create_view(offscreen=False, title=title)
        self.dvz.dvz_app_run(self.app, frame_count)

    def close(self) -> None:
        """Destroy app before scene; scene owns all remaining handles."""
        if self._closed:
            return
        if self.viewport is not None:
            self.dvz.dvz_panel_connect_input(self.panel, None)
            self.dvz.dvz_gui_viewport_destroy(self.viewport)
            self.viewport = None
        if self.app:
            self.dvz.dvz_app_destroy(self.app)
            self.app = None
        if self.region_tree is not None:
            self.dvz.dvz_gui_tree_destroy(self.region_tree)
            self.region_tree = None
        if self.probe_table is not None:
            self.dvz.dvz_gui_table_destroy(self.probe_table)
            self.probe_table = None
        if self.region_table is not None:
            self.dvz.dvz_gui_table_destroy(self.region_table)
            self.region_table = None
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
