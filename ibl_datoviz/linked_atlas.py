"""Native four-panel linked atlas navigator."""

from __future__ import annotations

import ctypes
from threading import RLock
from typing import TYPE_CHECKING

import numpy as np

from ibl_atlas_assets import (
    open_intensity_block_pack,
    open_registered_projection,
    open_volume_pack,
)

from .atlas import AtlasMesh
from .atlas_slice_source import AtlasSliceSource
from .latest_wins import LatestWinsExecutor
from .navigator import (
    SLICE_DISPLAY_AXES,
    AtlasCursor,
    AtlasSliceComposer,
    cursor_from_slice_fraction,
    mapped_region,
    slice_index_fraction,
    step_slice_cursor,
)
from .viewer import AtlasViewer

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from numpy.typing import NDArray

    from ibl_atlas_assets import AtlasVolumes


def volume_render_geometry(
    mesh: AtlasMesh, volumes: AtlasVolumes
) -> tuple[NDArray[np.float64], NDArray[np.float64], tuple[int, ...], tuple[bool, ...]]:
    """Return mesh-aligned volume bounds and NumPy-to-UVW axis mapping."""
    matrix = np.asarray(volumes.grid.index_to_world_um_matrix, dtype=np.float64).reshape(4, 4)
    linear = matrix[:3, :3]
    tolerance = max(1.0, float(np.max(np.abs(linear)))) * 1e-10
    world_for_array: list[int] = []
    signs: list[bool] = []
    for column in range(3):
        active = np.flatnonzero(np.abs(linear[:, column]) > tolerance)
        if len(active) != 1:
            raise ValueError('native volume rendering requires an axis-aligned atlas grid')
        world_for_array.append(int(active[0]))
        signs.append(bool(linear[active[0], column] < 0))
    if sorted(world_for_array) != [0, 1, 2]:
        raise ValueError('native volume rendering requires a non-degenerate axis permutation')

    shape = np.asarray(volumes.grid.shape, dtype=np.float64)
    corners = np.array(
        [
            [ap, ml, dv]
            for ap in (-0.5, shape[0] - 0.5)
            for ml in (-0.5, shape[1] - 0.5)
            for dv in (-0.5, shape[2] - 0.5)
        ]
    )
    display = mesh.normalize_points(volumes.grid.index_to_world(corners))
    bounds_min = display.min(axis=0).astype(np.float64)
    bounds_max = display.max(axis=0).astype(np.float64)

    # NumPy (AP, ML, DV) is uploaded as texture (W, V, U), hence reverse array axes.
    texture_to_array = (2, 1, 0)
    axis_order = tuple(world_for_array[array_axis] for array_axis in texture_to_array)
    axis_flip = tuple(signs[array_axis] for array_axis in texture_to_array)
    return bounds_min, bounds_max, axis_order, axis_flip


def grid_resolution_um(grid) -> tuple[float, float, float]:
    """Return AP/ML/DV voxel spacing magnitudes for an axis-aligned grid."""
    linear = np.asarray(grid.index_to_world_um_matrix, dtype=np.float64).reshape(4, 4)[:3, :3]
    return tuple(float(np.linalg.norm(linear[:, index])) for index in range(3))


def _resolution_label(grid) -> str:
    spacing = grid_resolution_um(grid)
    if np.allclose(spacing, spacing[0]):
        return f'{spacing[0]:g} um'
    return ' x '.join(f'{value:g}' for value in spacing) + ' um'


class LinkedAtlasNavigator(AtlasViewer):
    """Link orthogonal atlas slices, the ontology, and native 3-D anatomy."""

    def __init__(  # noqa: PLR0912, PLR0915
        self,
        mesh: AtlasMesh,
        volumes: AtlasVolumes,
        *,
        slice_source=None,
        mapping: str = 'allen',
        width: int = 1280,
        height: int = 900,
        annotation_opacity: float = 0.58,
        volume_opacity: float = 0.24,
        boundary_opacity: float = 0.82,
        boundary_width_px: float = 0.7,
        boundary_color: tuple[int, int, int] = (238, 242, 247),
        slice_background: tuple[int, int, int] = (29, 33, 39),
        surface_opacity: float = 0.22,
        palette=None,
        datoviz: ModuleType | None = None,
        **kwargs,
    ) -> None:
        if palette is not None:
            raise ValueError('linked atlas slices require the verified catalog palette')
        slice_source = volumes if slice_source is None else slice_source
        if mesh.reference_space != volumes.regions.reference_space_id:
            raise ValueError('mesh and volume reference spaces differ')
        if mesh.reference_space != slice_source.regions.reference_space_id:
            raise ValueError('mesh and slice reference spaces differ')
        for atlas_mapping in mesh.mapping_names:
            if atlas_mapping not in volumes.regions.mappings:
                raise ValueError(f'mesh mapping is absent from volume catalog: {atlas_mapping}')
            catalog_ids = {row.atlas_id for row in volumes.regions.physical(atlas_mapping)}
            mesh_ids = {
                int(region_id)
                for region_id in np.unique(mesh.mapping_ids(atlas_mapping))
                if region_id != 0
            }
            missing = sorted(mesh_ids - catalog_ids)
            if missing:
                raise ValueError(
                    f'mesh {atlas_mapping} IDs are absent from volume catalog: {missing}'
                )
        if not np.isfinite(annotation_opacity) or not 0 <= annotation_opacity <= 1:
            raise ValueError('annotation_opacity must be between zero and one')
        if not np.isfinite(volume_opacity) or not 0 <= volume_opacity <= 1:
            raise ValueError('volume_opacity must be between zero and one')
        if not np.isfinite(boundary_opacity) or not 0 <= boundary_opacity <= 1:
            raise ValueError('boundary_opacity must be between zero and one')
        if not np.isfinite(boundary_width_px) or boundary_width_px <= 0:
            raise ValueError('boundary_width_px must be finite and positive')
        if len(boundary_color) != 3 or any(
            int(value) != value or not 0 <= value <= 255 for value in boundary_color
        ):
            raise ValueError('boundary_color must contain three 8-bit values')
        if len(slice_background) != 3 or any(
            int(value) != value or not 0 <= value <= 255 for value in slice_background
        ):
            raise ValueError('slice_background must contain three 8-bit values')
        self.volumes = volumes
        self.slice_source = slice_source
        self.slice_resolution_label = _resolution_label(slice_source.grid)
        self.volume_resolution_label = _resolution_label(volumes.grid)
        self.cursor = AtlasCursor.centre(slice_source)
        self.slice_composer = AtlasSliceComposer(slice_source, mapping)
        self._slice_prepare_lock = RLock()
        self._slice_loader = (
            LatestWinsExecutor(
                self._prepare_slice,
                notify=self._notify_slice_ready,
                max_workers=3,
            )
            if slice_source is not volumes
            else None
        )
        self._slice_post_callback = self._drain_prepared_slices
        self._slice_error: Exception | None = None
        self.annotation_opacity = float(annotation_opacity)
        self.volume_opacity = float(volume_opacity)
        self.boundary_opacity = float(boundary_opacity)
        self.boundary_width_px = float(boundary_width_px)
        self.boundary_color = tuple(int(value) for value in boundary_color)
        self.slice_background = tuple(int(value) for value in slice_background)
        self.anatomy_visible = True
        self.annotation_visible = True
        self.boundaries_visible = True
        self._slice_fields: dict[str, object] = {}
        self._annotation_fields: dict[str, object] = {}
        self._slice_images: dict[str, object] = {}
        self._annotation_images: dict[str, object] = {}
        self._boundary_visuals: dict[str, object] = {}
        self._crosshairs: dict[str, object] = {}
        self._hover_markers: dict[str, object] = {}
        self._cursor_controls = {
            axis: ctypes.c_int(value)
            for axis, value in zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True)
        }
        self._annotation_opacity_control = ctypes.c_float(self.annotation_opacity)
        self._volume_opacity_control = ctypes.c_float(self.volume_opacity)
        self._anatomy_visible_control = ctypes.c_bool(self.anatomy_visible)
        self._annotation_visible_control = ctypes.c_bool(self.annotation_visible)
        self._boundaries_visible_control = ctypes.c_bool(self.boundaries_visible)
        self._boundary_opacity_control = ctypes.c_float(self.boundary_opacity)
        self._input_router = None
        self._input_subscription = 0
        self._input_callback = None
        self._hovered_slice_axis, self._hovered_slice_position, self._hovered_region_label = (
            None,
            None,
            None,
        )
        self._slice_zoom = {axis: 1.0 for axis in ('ap', 'ml', 'dv')}
        self._slice_wheel_accumulator = {axis: 0.0 for axis in ('ap', 'ml', 'dv')}
        super().__init__(
            mesh,
            mapping=mapping,
            catalog=volumes.regions,
            width=width,
            height=height,
            surface_opacity=surface_opacity,
            datoviz=datoviz,
            **kwargs,
        )
        try:
            self._create_slices()
            self._create_anatomical_volume()
            self._create_cursor_marker()
        except Exception:
            self.close()
            raise

    @classmethod
    def from_packs(
        cls, mesh_pack: str | Path, volume_pack: str | Path, **kwargs
    ) -> LinkedAtlasNavigator:
        """Create a navigator from verified mesh and volume packs."""
        volumes = open_volume_pack(volume_pack).load_volumes()
        return cls(AtlasMesh.from_pack(mesh_pack), volumes, **kwargs)

    @classmethod
    def from_multiresolution_packs(
        cls,
        mesh_pack: str | Path,
        volume_pack: str | Path,
        intensity_pack: str | Path,
        registered_projections: dict[str, str | Path],
        **kwargs,
    ) -> LinkedAtlasNavigator:
        """Use registered high-resolution slices with an independent dense 3-D volume."""
        volumes = open_volume_pack(volume_pack).load_volumes()
        intensity = open_intensity_block_pack(intensity_pack)
        projections = {
            axis: open_registered_projection(path) for axis, path in registered_projections.items()
        }
        slices = AtlasSliceSource(intensity, projections, volumes.regions)
        return cls(AtlasMesh.from_pack(mesh_pack), volumes, slice_source=slices, **kwargs)

    def _create_layout(self) -> None:
        self.figure = self.dvz.dvz_figure(self.scene, self.width, self.height, 0)
        grid = self.dvz.dvz_figure_grid(self.figure, 2, 2)
        if not grid:
            raise RuntimeError('dvz_figure_grid() failed')
        self.slice_panels = {
            'ap': self.dvz.dvz_grid_panel(grid, 0, 0),
            'ml': self.dvz.dvz_grid_panel(grid, 0, 1),
            'dv': self.dvz.dvz_grid_panel(grid, 1, 0),
        }
        self.panel = self.dvz.dvz_grid_panel(grid, 1, 1)
        panels = (*self.slice_panels.values(), self.panel)
        if any(not panel for panel in panels):
            raise RuntimeError('dvz_grid_panel() failed')
        for panel in panels:
            self.dvz.dvz_panel_set_background_color(
                panel, self.dvz.DvzColor(*self.slice_background, 255)
            )
        for panel in self.slice_panels.values():
            self._check(
                self.dvz.dvz_panel_set_domain(panel, self.dvz.DVZ_DIM_X, -1.0, 1.0),
                'slice horizontal domain',
            )
            self._check(
                self.dvz.dvz_panel_set_domain(panel, self.dvz.DVZ_DIM_Y, -1.0, 1.0),
                'slice vertical domain',
            )
            view = self.dvz.dvz_panel_view2d_desc()
            view.mode = self.dvz.DVZ_PANEL_VIEW2D_CONTAIN
            view.aspect = self.dvz.DVZ_PANEL_VIEW2D_ASPECT_EQUAL
            view.padding = 0.0
            self._check(
                self.dvz.dvz_panel_set_view2d(panel, ctypes.byref(view)),
                'slice equal-aspect view',
            )

    def _slice_quad(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
        sizes = dict(zip(('ap', 'ml', 'dv'), self.slice_source.grid.shape, strict=True))
        aspect = sizes[x_axis] / sizes[y_axis]
        x_extent, y_extent = (0.94, 0.94 / aspect) if aspect >= 1 else (0.94 * aspect, 0.94)
        zoom = self._slice_zoom.get(axis, 1.0)
        positions = np.array(
            [
                [-x_extent * zoom, -y_extent * zoom, 0],
                [-x_extent * zoom, +y_extent * zoom, 0],
                [+x_extent * zoom, -y_extent * zoom, 0],
                [+x_extent * zoom, +y_extent * zoom, 0],
            ],
            dtype=np.float32,
        )
        texcoords = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
        return positions, texcoords

    def _create_slices(self) -> None:  # noqa: PLR0915
        for axis, panel in self.slice_panels.items():
            attach = self.dvz.dvz_visual_attach_desc()
            attach.controller_mode = self.dvz.DVZ_CONTROLLER_APPLY
            attach.coord_space = self.dvz.DVZ_VISUAL_COORD_DATA
            anatomy_data, annotation_data = self._slice_layers(axis)
            field = self.dvz.dvz_sampled_field_from_array(
                self.scene,
                anatomy_data,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )
            image = self.dvz.dvz_image(self.scene, 0)
            if not image:
                raise RuntimeError('dvz_image() failed')
            positions, texcoords = self._slice_quad(axis)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    image, {'position': positions, 'texcoords': texcoords}
                ),
                f'{axis} slice geometry upload',
            )
            self._check(self.dvz.dvz_visual_set_field(image, b'field', field), 'slice field bind')
            self._check(
                self.dvz.dvz_image_set_sampling(image, self.dvz.DVZ_IMAGE_SAMPLING_LINEAR),
                'anatomy linear sampling',
            )
            self._check(self.dvz.dvz_visual_set_depth_test(image, False), 'slice depth disable')
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(image, self.dvz.DVZ_ALPHA_BLENDED),
                'slice alpha mode',
            )
            attach.z_layer = 0
            self._check(
                self.dvz.dvz_panel_add_visual(panel, image, ctypes.byref(attach)), 'slice attach'
            )
            self._slice_fields[axis] = field
            self._slice_images[axis] = image

            annotation_field = self.dvz.dvz_sampled_field_from_array(
                self.scene,
                annotation_data,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )
            annotation_image = self.dvz.dvz_image(self.scene, 0)
            if not annotation_image:
                raise RuntimeError('dvz annotation image() failed')
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    annotation_image, {'position': positions, 'texcoords': texcoords}
                ),
                f'{axis} annotation geometry upload',
            )
            self._check(
                self.dvz.dvz_visual_set_field(annotation_image, b'field', annotation_field),
                'annotation field bind',
            )
            self._check(
                self.dvz.dvz_image_set_sampling(
                    annotation_image, self.dvz.DVZ_IMAGE_SAMPLING_NEAREST
                ),
                'annotation nearest sampling',
            )
            self._check(
                self.dvz.dvz_visual_set_depth_test(annotation_image, False),
                'annotation depth disable',
            )
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(annotation_image, self.dvz.DVZ_ALPHA_BLENDED),
                'annotation alpha mode',
            )
            attach.z_layer = 1
            self._check(
                self.dvz.dvz_panel_add_visual(panel, annotation_image, ctypes.byref(attach)),
                'annotation attach',
            )
            self._annotation_fields[axis] = annotation_field
            self._annotation_images[axis] = annotation_image

            boundaries = self.dvz.dvz_segment(self.scene, 0)
            if not boundaries:
                raise RuntimeError('slice boundary segment creation failed')
            boundary_starts, boundary_ends = self._boundary_positions(axis)
            boundary_count = len(boundary_starts)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    boundaries,
                    {
                        'position_start': boundary_starts,
                        'position_end': boundary_ends,
                        'color': np.tile(self._boundary_rgba(), (boundary_count, 1)),
                        'stroke_width_px': np.full(
                            boundary_count, self.boundary_width_px, dtype=np.float32
                        ),
                    },
                ),
                'slice boundaries upload',
            )
            self._check(self.dvz.dvz_visual_set_depth_test(boundaries, False), 'boundary depth')
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(boundaries, self.dvz.DVZ_ALPHA_BLENDED),
                'boundary alpha mode',
            )
            attach.z_layer = 2
            self._check(
                self.dvz.dvz_panel_add_visual(panel, boundaries, ctypes.byref(attach)),
                'slice boundaries attach',
            )
            self._boundary_visuals[axis] = boundaries

            crosshair = self.dvz.dvz_segment(self.scene, 0)
            if not crosshair:
                raise RuntimeError('dvz_segment() failed')
            starts, ends = self._crosshair_positions(axis)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    crosshair,
                    {
                        'position_start': starts,
                        'position_end': ends,
                        'color': np.tile(np.array([43, 220, 255, 235], dtype=np.uint8), (2, 1)),
                        'stroke_width_px': np.full(2, 1.5, dtype=np.float32),
                    },
                ),
                'slice crosshair upload',
            )
            self._check(self.dvz.dvz_visual_set_depth_test(crosshair, False), 'crosshair depth')
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(crosshair, self.dvz.DVZ_ALPHA_BLENDED),
                'crosshair alpha mode',
            )
            attach.z_layer = 10
            self._check(
                self.dvz.dvz_panel_add_visual(panel, crosshair, ctypes.byref(attach)),
                'slice crosshair attach',
            )
            self._crosshairs[axis] = crosshair

            hover = self.dvz.dvz_point(self.scene, 0)
            if not hover:
                raise RuntimeError('slice hover marker creation failed')
            point_style = self.dvz.dvz_point_style_desc()
            point_style.aspect = self.dvz.DVZ_SHAPE_ASPECT_FILLED
            point_style.stroke_width_px = 0.0
            self._check(
                self.dvz.dvz_point_set_style(hover, ctypes.byref(point_style)),
                'slice hover marker style',
            )
            self._check(self.dvz.dvz_visual_set_depth_test(hover, False), 'hover marker depth')
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(hover, self.dvz.DVZ_ALPHA_BLENDED),
                'hover marker alpha mode',
            )
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    hover,
                    {
                        'position': np.zeros((1, 3), dtype=np.float32),
                        'color': np.array([[255, 255, 255, 0]], dtype=np.uint8),
                        'diameter_px': np.zeros(1, dtype=np.float32),
                    },
                ),
                'slice hover marker upload',
            )
            attach.z_layer = 11
            self._check(
                self.dvz.dvz_panel_add_visual(panel, hover, ctypes.byref(attach)),
                'hover marker attach',
            )
            self._hover_markers[axis] = hover

    def _slice_rgba(self, axis: str) -> NDArray[np.uint8]:
        index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        return self.slice_composer.compose(
            axis,
            index,
            annotation_opacity=self.annotation_opacity,
            selected_region_ids=self._emphasis_region_ids(),
            selection_dim_factor=self.selection_dim_factor,
        )

    def _slice_layers(self, axis: str) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
        with self._slice_prepare_lock:
            index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
            anatomy, annotation = self.slice_composer.compose_layers(
                axis,
                index,
                annotation_opacity=self.annotation_opacity,
                selected_region_ids=self._emphasis_region_ids(),
                selection_dim_factor=self.selection_dim_factor,
            )
            if not self.anatomy_visible:
                anatomy[..., 3] = 0
            if not self.annotation_visible:
                annotation[..., 3] = 0
            return anatomy, annotation

    def _prepare_slice(self, axis: str):
        """Prepare one complete slice payload without touching Datoviz state."""
        anatomy, annotation = self._slice_layers(axis)
        with self._slice_prepare_lock:
            starts, ends = self._boundary_positions(axis)
            colors = np.tile(self._boundary_rgba(), (len(starts), 1))
            widths = np.full(len(starts), self.boundary_width_px, dtype=np.float32)
        return anatomy, annotation, starts, ends, colors, widths

    def _notify_slice_ready(self, _axis: str) -> None:
        """Wake the owner thread after a worker finishes a current request."""
        if (
            self.view is not None
            and not self._closed
            and self.dvz.dvz_view_post(self.view, self._slice_post_callback, None) != 0
        ):
            self.dvz.dvz_view_wake(self.view)

    def _drain_prepared_slices(self, _view, _user_data) -> None:
        """Apply prepared slice payloads on the Datoviz view owner thread."""
        if self._slice_loader is None or self._closed:
            return
        try:
            ready = self._slice_loader.drain_ready()
        except Exception as error:  # callback boundaries must not leak exceptions
            self._slice_error = error
            return
        for item in ready:
            axis = item.key
            anatomy, annotation, starts, ends, colors, widths = item.result
            self.dvz.dvz_sampled_field_update_from_array(
                self._slice_fields[axis],
                anatomy,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )
            self.dvz.dvz_sampled_field_update_from_array(
                self._annotation_fields[axis],
                annotation,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    self._boundary_visuals[axis],
                    {
                        'position_start': starts,
                        'position_end': ends,
                        'color': colors,
                        'stroke_width_px': widths,
                    },
                ),
                f'{axis} prepared boundaries update',
            )
        if ready:
            self._slice_error = None
            self.dvz.dvz_view_request_frame(self.view)

    def _crosshair_positions(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]
        coordinates = dict(zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True))
        x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
        x_fraction = slice_index_fraction(self.slice_source.grid, x_axis, coordinates[x_axis])
        y_fraction = slice_index_fraction(self.slice_source.grid, y_axis, coordinates[y_axis])
        x = x0 + x_fraction * (x1 - x0)
        y = y0 + y_fraction * (y1 - y0)
        starts = np.array([[x, y0, 0.02], [x0, y, 0.02]], dtype=np.float32)
        ends = np.array([[x, y1, 0.02], [x1, y, 0.02]], dtype=np.float32)
        return starts, ends

    def _boundary_rgba(self) -> NDArray[np.uint8]:
        """Return the current boundary color, including visibility and opacity."""
        alpha = round(255 * self.boundary_opacity) if self.boundaries_visible else 0
        return np.asarray((*self.boundary_color, alpha), dtype=np.uint8)

    def _boundary_positions(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        """Map normalized atlas boundary segments onto one displayed slice quad."""
        index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        starts, ends = self.slice_composer.boundary_segments(axis, index)
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]

        def transform(values):
            result = np.zeros((len(values), 3), dtype=np.float32)
            result[:, 0] = x0 + values[:, 0] * (x1 - x0)
            result[:, 1] = y0 + values[:, 1] * (y1 - y0)
            result[:, 2] = 0.01
            return np.ascontiguousarray(result)

        return transform(starts), transform(ends)

    def _refresh_boundaries(self, axis: str) -> None:
        """Upload the current slice's cached, mapping-aware boundary segments."""
        starts, ends = self._boundary_positions(axis)
        count = len(starts)
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self._boundary_visuals[axis],
                {
                    'position_start': starts,
                    'position_end': ends,
                    'color': np.tile(self._boundary_rgba(), (count, 1)),
                    'stroke_width_px': np.full(count, self.boundary_width_px, dtype=np.float32),
                },
            ),
            f'{axis} slice boundaries update',
        )

    def _create_anatomical_volume(self) -> None:
        self.volume_field = self.dvz.dvz_sampled_field_from_array(
            self.scene,
            self.volumes.template,
            format=self.dvz.DVZ_FIELD_FORMAT_R16_UNORM,
            semantic=self.dvz.DVZ_FIELD_SEMANTIC_SCALAR,
            dim=self.dvz.DVZ_FIELD_DIM_3D,
        )
        self.volume = self.dvz.dvz_volume(self.scene, 0)
        if not self.volume:
            raise RuntimeError('dvz_volume() failed')
        self._check(
            self.dvz.dvz_visual_set_field(self.volume, b'field', self.volume_field),
            'anatomical volume field bind',
        )
        bounds_min, bounds_max, axis_order, axis_flip = volume_render_geometry(
            self.mesh_data, self.volumes
        )
        self._check(
            self.dvz.dvz_volume_set_bounds(
                self.volume,
                (ctypes.c_double * 3)(*bounds_min),
                (ctypes.c_double * 3)(*bounds_max),
            ),
            'anatomical volume bounds',
        )
        self._check(
            self.dvz.dvz_volume_set_axis_mapping(
                self.volume,
                (ctypes.c_uint32 * 3)(*axis_order),
                (ctypes.c_bool * 3)(*axis_flip),
            ),
            'anatomical volume axis mapping',
        )
        low, high = np.percentile(self.volumes.template, (2.0, 99.5)) / 65535.0
        if high <= low:
            high = min(1.0, low + 1 / 65535.0)
        self._check(
            self.dvz.dvz_volume_set_value_range(self.volume, float(low), float(high)),
            'anatomical volume value range',
        )
        alpha = (self.dvz.DvzVolumeAlphaStop * 4)()
        for stop, position, opacity in zip(
            alpha, (0.0, 0.12, 0.45, 1.0), (0.0, 0.0, 0.26, 0.82), strict=True
        ):
            stop.position = position
            stop.alpha = opacity
        self._check(
            self.dvz.dvz_volume_set_alpha_stops(self.volume, alpha, len(alpha)),
            'anatomical volume transfer opacity',
        )
        self._check(
            self.dvz.dvz_volume_set_render_mode(self.volume, self.dvz.DVZ_VOLUME_RENDER_COMPOSITE),
            'anatomical volume composite mode',
        )
        self._check(
            self.dvz.dvz_volume_set_sampling(self.volume, self.dvz.DVZ_VOLUME_SAMPLING_LINEAR),
            'anatomical volume linear sampling',
        )
        self._check(self.dvz.dvz_volume_set_step_count(self.volume, 160), 'volume step count')
        self._check(
            self.dvz.dvz_volume_set_opacity(self.volume, self.volume_opacity), 'volume opacity'
        )
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.volume, self.dvz.DVZ_ALPHA_BLENDED),
            'volume alpha mode',
        )
        self._check(self.dvz.dvz_panel_add_visual(self.panel, self.volume, None), 'volume attach')
        self._update_surface_alpha_mode()

    def _update_surface_alpha_mode(self) -> None:
        mode = (
            self.dvz.DVZ_ALPHA_BLENDED
            if self.volume_opacity > 0
            else self.dvz.DVZ_ALPHA_WBOIT
            if self.surface_opacity < 1
            else self.dvz.DVZ_ALPHA_OPAQUE
        )
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.mesh, mode),
            'surface transparency mode',
        )

    def _create_cursor_marker(self) -> None:
        self.cursor_marker = self.dvz.dvz_segment(self.scene, 0)
        self.cursor_dot = self.dvz.dvz_point(self.scene, 0)
        if not self.cursor_marker or not self.cursor_dot:
            raise RuntimeError('3-D cursor visual creation failed')
        self._check(
            self.dvz.dvz_visual_set_depth_test(self.cursor_marker, False),
            '3-D cursor depth disable',
        )
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.cursor_marker, self.dvz.DVZ_ALPHA_BLENDED),
            '3-D cursor alpha mode',
        )
        self._check(
            self.dvz.dvz_visual_set_depth_test(self.cursor_dot, False),
            '3-D cursor dot depth disable',
        )
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.cursor_dot, self.dvz.DVZ_ALPHA_BLENDED),
            '3-D cursor dot alpha mode',
        )
        point_style = self.dvz.dvz_point_style_desc()
        point_style.aspect = self.dvz.DVZ_SHAPE_ASPECT_FILLED
        point_style.stroke_width_px = 0.0
        self._check(
            self.dvz.dvz_point_set_style(self.cursor_dot, ctypes.byref(point_style)),
            '3-D cursor dot style',
        )
        attach = self.dvz.dvz_visual_attach_desc()
        attach.z_layer = 2
        attach.controller_mode = self.dvz.DVZ_CONTROLLER_APPLY
        attach.coord_space = self.dvz.DVZ_VISUAL_COORD_DATA
        self._check(
            self.dvz.dvz_panel_add_visual(self.panel, self.cursor_marker, ctypes.byref(attach)),
            '3-D cursor attach',
        )
        attach.z_layer = 3
        self._check(
            self.dvz.dvz_panel_add_visual(self.panel, self.cursor_dot, ctypes.byref(attach)),
            '3-D cursor dot attach',
        )
        self._update_cursor_marker()

    def _update_cursor_marker(self) -> None:
        world = np.asarray(self.cursor.world_um(self.slice_source), dtype=np.float32).reshape(1, 3)
        position = self.mesh_data.normalize_points(world)[0]
        half_length = 600.0 * self.mesh_data.display_scale
        starts = np.tile(position, (3, 1))
        ends = np.tile(position, (3, 1))
        starts[np.arange(3), np.arange(3)] -= half_length
        ends[np.arange(3), np.arange(3)] += half_length
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.cursor_marker,
                {
                    'position_start': np.ascontiguousarray(starts, dtype=np.float32),
                    'position_end': np.ascontiguousarray(ends, dtype=np.float32),
                    'color': np.tile(np.array([43, 220, 255, 255], dtype=np.uint8), (3, 1)),
                    'stroke_width_px': np.full(3, 3.0, dtype=np.float32),
                },
            ),
            '3-D cursor update',
        )
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.cursor_dot,
                {
                    'position': position.reshape(1, 3),
                    'color': np.array([[43, 220, 255, 255]], dtype=np.uint8),
                    'diameter_px': np.array([13.0], dtype=np.float32),
                },
            ),
            '3-D cursor dot update',
        )

    def _refresh_slices(self, axes=None) -> None:
        if not self._slice_fields:
            return
        refresh_axes = tuple(self._slice_fields) if axes is None else tuple(axes)
        if self._slice_loader is not None and self.view is not None:
            for axis in refresh_axes:
                self._slice_loader.request(axis, axis)
        else:
            for axis in refresh_axes:
                anatomy, annotation = self._slice_layers(axis)
                self.dvz.dvz_sampled_field_update_from_array(
                    self._slice_fields[axis],
                    anatomy,
                    format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                    semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                    dim=self.dvz.DVZ_FIELD_DIM_2D,
                )
                self.dvz.dvz_sampled_field_update_from_array(
                    self._annotation_fields[axis],
                    annotation,
                    format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                    semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                    dim=self.dvz.DVZ_FIELD_DIM_2D,
                )
                self._refresh_boundaries(axis)
        for axis in self._slice_fields:
            starts, ends = self._crosshair_positions(axis)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    self._crosshairs[axis],
                    {'position_start': starts, 'position_end': ends},
                ),
                f'{axis} crosshair update',
            )
        self._update_cursor_marker()

    def _update_slice_geometry(self, axis: str) -> None:
        """Upload one slice's zoomed quad and aligned overlays."""
        positions, _ = self._slice_quad(axis)
        for visual in (self._slice_images[axis], self._annotation_images[axis]):
            self._check(
                self.dvz.dvz_visual_set_data(visual, 'position', positions),
                f'{axis} slice zoom',
            )
        self._refresh_boundaries(axis)
        starts, ends = self._crosshair_positions(axis)
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self._crosshairs[axis], {'position_start': starts, 'position_end': ends}
            ),
            f'{axis} crosshair zoom',
        )

    def set_cursor(self, cursor: AtlasCursor, *, select_region: bool = False) -> None:
        """Move the AP/ML/DV cursor and refresh all linked panels.

        Cursor navigation is deliberately independent from committed region
        selection.  Callers handling an explicit selection gesture (for
        example a click in a slice) can opt in with ``select_region=True``.
        """
        previous = self.cursor.as_index()
        current = cursor.as_index()
        for axis, value in zip(('ap', 'ml', 'dv'), current, strict=True):
            cursor.replace(axis, value, self.slice_source.grid.shape)
            self._cursor_controls[axis].value = value
        self.cursor = cursor
        if select_region:
            row = cursor.region(self.slice_source, self.mapping)
            ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
            self._apply_selected_region_ids(
                ids, update_tree=True, update_table=True, clear_mesh=True
            )
        else:
            changed_axes = tuple(
                axis
                for axis, before, after in zip(('ap', 'ml', 'dv'), previous, current, strict=True)
                if before != after
            )
            self._refresh_slices(changed_axes)

    def set_cursor_from_slice_data(
        self, axis: str, x: float, y: float, *, select_region: bool = False
    ) -> bool:
        """Move the cursor from one slice panel's data coordinates.

        Returns ``False`` when the coordinate lies outside the rendered image.
        """
        cursor = self._cursor_at_slice_data(axis, x, y)
        if cursor is None:
            return False
        self.set_cursor(cursor, select_region=select_region)
        return True

    def _cursor_at_slice_data(self, axis: str, x: float, y: float) -> AtlasCursor | None:
        """Return the atlas location under a slice point without mutating navigation."""
        if axis not in self.slice_panels or not np.isfinite((x, y)).all():
            return None
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]
        if x < x0 or x > x1 or y < y0 or y > y1:
            return None
        return cursor_from_slice_fraction(
            self.cursor,
            axis,
            float((x - x0) / (x1 - x0)),
            float((y - y0) / (y1 - y0)),
            self.slice_source.grid,
        )

    def _set_slice_hover(self, axis: str | None, x: float = 0.0, y: float = 0.0) -> bool:
        """Update the transient slice marker and region readout."""
        cursor = self._cursor_at_slice_data(axis, x, y) if axis is not None else None
        row = None
        label = None
        if cursor is not None:
            cached_lookup = getattr(self.slice_source, 'cached_annotation_index_at_world', None)
            source_index = (
                cached_lookup(cursor.world_um(self.slice_source), preferred_axis=axis)
                if cached_lookup is not None
                else cursor.source_index(self.slice_source)
            )
            if source_index is None:
                label = 'loading…'
            else:
                row = mapped_region(self.slice_source, source_index, self.mapping)
                label = 'unmapped' if row is None else f'{row.acronym} — {row.name}'
        region_ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
        position = (x, y) if cursor is not None else None
        changed = (
            axis != self._hovered_slice_axis
            or position != self._hovered_slice_position
            or label != self._hovered_region_label
        )
        self._hovered_slice_axis = axis
        self._hovered_slice_position = position
        self._hovered_region_label = label
        self._set_hovered_region_ids(region_ids)
        for marker_axis, marker in self._hover_markers.items():
            visible = marker_axis == axis and cursor is not None
            position = np.array([[x, y, 0.04]], dtype=np.float32)
            color = np.array([[255, 255, 255, 230 if visible else 0]], dtype=np.uint8)
            diameter = np.array([9.0 if visible else 0.0], dtype=np.float32)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    marker, {'position': position, 'color': color, 'diameter_px': diameter}
                ),
                'slice hover marker update',
            )
        return changed

    def step_slice(self, axis: str, delta: int) -> bool:
        """Step one slice plane without changing committed region selection."""
        if axis not in self.slice_panels or not delta:
            return False
        cursor = step_slice_cursor(self.cursor, axis, int(delta), self.slice_source.grid.shape)
        if cursor == self.cursor:
            return False
        self.set_cursor(cursor, select_region=False)
        return True

    def select_cursor_region(self) -> None:
        """Commit the region under the current AP/ML/DV cursor."""
        row = self.cursor.region(self.slice_source, self.mapping)
        ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
        self._apply_selected_region_ids(ids, update_tree=True, update_table=True, clear_mesh=True)

    def set_mapping(self, mapping: str, palette=None) -> None:
        """Switch all mesh, slice, cursor, and ontology identities together."""
        if palette is not None:
            raise ValueError('linked atlas slices require the verified catalog palette')
        super().set_mapping(mapping)
        with self._slice_prepare_lock:
            self.slice_composer.set_mapping(mapping)
        self._refresh_slices()

    def _apply_selected_region_ids(self, region_ids, **kwargs) -> None:
        super()._apply_selected_region_ids(region_ids, **kwargs)
        if hasattr(self, '_slice_fields'):
            self._refresh_slices()

    def _set_hovered_region_ids(self, region_ids) -> bool:
        """Apply transient hover emphasis to every linked visual panel."""
        changed = super()._set_hovered_region_ids(region_ids)
        if changed and self._slice_fields:
            self._refresh_slices()
        return changed

    def _sync_viewport_hover(self, hovered: bool) -> None:
        """Prefer direct slice hover, otherwise synchronize the retained 3-D query."""
        if not hovered:
            self._set_slice_hover(None)
            return
        if self._hovered_slice_axis is not None:
            return
        region_ids = self._mesh_hovered_region_ids()
        self._set_hovered_region_ids(region_ids)
        if region_ids and self.tree_model is not None:
            self._hovered_region_label = self.tree_model.describe(region_ids[0])
        else:
            self._hovered_region_label = None

    def _draw_extra_gui(self, gui) -> None:  # noqa: PLR0912 - declarative GUI controls
        if self._slice_loader is not None:
            self._drain_prepared_slices(self.view, None)
        self.dvz.dvz_gui_separator_text(gui, b'Linked atlas cursor')
        self.dvz.dvz_gui_text(gui, b'AP: ML -> right, dorsal up')
        self.dvz.dvz_gui_text(gui, b'ML: AP -> right, dorsal up')
        self.dvz.dvz_gui_text(gui, b'DV: ML -> right, anterior up')
        self.dvz.dvz_gui_text(gui, b'3-D: left-drag to orbit; wheel to zoom')
        self.dvz.dvz_gui_text(
            gui,
            f'Slices {self.slice_resolution_label} | 3-D {self.volume_resolution_label}'.encode(),
        )
        changed = False
        for axis, size in zip(('ap', 'ml', 'dv'), self.slice_source.grid.shape, strict=True):
            changed |= self.dvz.dvz_gui_slider_int(
                gui, axis.upper().encode(), ctypes.byref(self._cursor_controls[axis]), 0, size - 1
            )
        if changed:
            self.set_cursor(
                AtlasCursor(*(self._cursor_controls[axis].value for axis in ('ap', 'ml', 'dv'))),
                select_region=False,
            )
        if self.dvz.dvz_gui_button(gui, b'Select cursor region'):
            self.select_cursor_region()
        if self.dvz.dvz_gui_slider_float(
            gui,
            b'Annotation opacity',
            ctypes.byref(self._annotation_opacity_control),
            0.0,
            1.0,
        ):
            self.annotation_opacity = float(self._annotation_opacity_control.value)
            self._refresh_slices()
        if self.dvz.dvz_gui_checkbox(
            gui, b'Anatomy slice layer', ctypes.byref(self._anatomy_visible_control)
        ):
            self.anatomy_visible = bool(self._anatomy_visible_control.value)
            self._refresh_slices()
        if self.dvz.dvz_gui_checkbox(
            gui, b'Annotation slice layer', ctypes.byref(self._annotation_visible_control)
        ):
            self.annotation_visible = bool(self._annotation_visible_control.value)
            self._refresh_slices()
        if self.dvz.dvz_gui_checkbox(
            gui, b'Region boundaries', ctypes.byref(self._boundaries_visible_control)
        ):
            self.boundaries_visible = bool(self._boundaries_visible_control.value)
            for axis in self._boundary_visuals:
                self._refresh_boundaries(axis)
        if self.dvz.dvz_gui_slider_float(
            gui,
            b'Boundary opacity',
            ctypes.byref(self._boundary_opacity_control),
            0.0,
            1.0,
        ):
            self.boundary_opacity = float(self._boundary_opacity_control.value)
            for axis in self._boundary_visuals:
                self._refresh_boundaries(axis)
        if self.dvz.dvz_gui_slider_float(
            gui,
            b'Volume opacity',
            ctypes.byref(self._volume_opacity_control),
            0.0,
            1.0,
        ):
            self.volume_opacity = float(self._volume_opacity_control.value)
            self._check(
                self.dvz.dvz_volume_set_opacity(self.volume, self.volume_opacity),
                'volume opacity update',
            )
            self._update_surface_alpha_mode()
        world = self.cursor.world_um(self.slice_source)
        row = self.cursor.region(self.slice_source, self.mapping)
        region = 'unmapped' if row is None else f'{row.acronym} — {row.name}'
        self.dvz.dvz_gui_text(
            gui,
            f'ML {world[0]:.0f} · AP {world[1]:.0f} · DV {world[2]:.0f} um'.encode(),
        )
        self.dvz.dvz_gui_text(gui, region.encode())
        hover_source = self._hovered_slice_axis.upper() if self._hovered_slice_axis else '3-D'
        hover_label = self._hovered_region_label or '—'
        self.dvz.dvz_gui_text(gui, f'Hover ({hover_source}): {hover_label}'.encode())
        if self._slice_error is not None:
            self.dvz.dvz_gui_text(gui, f'Slice load failed: {self._slice_error}'.encode())

    def _create_view(self, *, offscreen: bool, title: str) -> None:  # noqa: PLR0915
        super()._create_view(offscreen=offscreen, title=title)
        if offscreen:
            return
        self._input_router = self.dvz.dvz_gui_viewport_input(self.viewport)
        if not self._input_router:
            raise RuntimeError('dvz_view_input() failed')

        def slice_data_at_pointer(pointer):
            figure_position = self._pointer_figure_position(pointer)
            if figure_position is None:
                return None
            for axis, panel in self.slice_panels.items():
                figure_pos = (ctypes.c_double * 2)(*figure_position)
                panel_pos = (ctypes.c_double * 2)()
                inside = self.dvz.dvz_panel_transform_point(
                    panel,
                    self.dvz.DVZ_PANEL_COORD_FIGURE_PX,
                    self.dvz.DVZ_PANEL_COORD_PANEL_PX,
                    figure_pos,
                    panel_pos,
                )
                if not inside:
                    continue
                data_pos = (ctypes.c_double * 2)()
                if not self.dvz.dvz_panel_position_to_data(
                    panel, self.dvz.DVZ_PANEL_COORD_PANEL_PX, panel_pos, data_pos
                ):
                    continue
                return axis, float(data_pos[0]), float(data_pos[1])
            return None

        def on_input(_router, event_ptr, _user_data) -> None:  # noqa: PLR0911, PLR0912
            event = event_ptr.contents
            if event.type == self.dvz.DVZ_INPUT_EVENT_KEYBOARD:
                keyboard = event.content.keyboard
                if (
                    keyboard.type
                    not in (
                        self.dvz.DVZ_KEYBOARD_EVENT_PRESS,
                        self.dvz.DVZ_KEYBOARD_EVENT_REPEAT,
                    )
                    or self._hovered_slice_axis is None
                ):
                    return
                step = (
                    1
                    if keyboard.key in (self.dvz.DVZ_KEY_RIGHT_BRACKET, self.dvz.DVZ_KEY_PAGE_UP)
                    else -1
                )
                if keyboard.key not in (
                    self.dvz.DVZ_KEY_LEFT_BRACKET,
                    self.dvz.DVZ_KEY_RIGHT_BRACKET,
                    self.dvz.DVZ_KEY_PAGE_UP,
                    self.dvz.DVZ_KEY_PAGE_DOWN,
                ):
                    return
                if keyboard.mods & self.dvz.DVZ_KEY_MODIFIER_SHIFT:
                    step *= 5
                if self.step_slice(self._hovered_slice_axis, step):
                    self.dvz.dvz_view_request_frame(self.view)
                return
            if event.type != self.dvz.DVZ_INPUT_EVENT_POINTER:
                return
            pointer = event.content.pointer
            hit = slice_data_at_pointer(pointer)
            if hit is None:
                if pointer.type == self.dvz.DVZ_POINTER_EVENT_MOVE and self._set_slice_hover(None):
                    self.dvz.dvz_view_request_frame(self.view)
                return
            axis, x, y = hit
            if pointer.type == self.dvz.DVZ_POINTER_EVENT_MOVE:
                if self._set_slice_hover(axis, x, y):
                    self.dvz.dvz_view_request_frame(self.view)
                return
            if pointer.type == self.dvz.DVZ_POINTER_EVENT_WHEEL:
                amount = float(pointer.content.w.dir[1])
                if pointer.mods & self.dvz.DVZ_KEY_MODIFIER_CONTROL:
                    if amount:
                        factor = 1.08**amount
                        self._slice_zoom[axis] = float(
                            np.clip(self._slice_zoom[axis] * factor, 1.0, 8.0)
                        )
                        self._update_slice_geometry(axis)
                        self.dvz.dvz_view_request_frame(self.view)
                    return
                if amount:
                    sensitivity = 10.0 if pointer.mods & self.dvz.DVZ_KEY_MODIFIER_SHIFT else 2.0
                    self._slice_wheel_accumulator[axis] += amount * sensitivity
                    step = int(np.trunc(self._slice_wheel_accumulator[axis]))
                    self._slice_wheel_accumulator[axis] -= step
                    if step and self.step_slice(axis, step):
                        self.dvz.dvz_view_request_frame(self.view)
                return
            if pointer.type == self.dvz.DVZ_POINTER_EVENT_DOUBLE_CLICK:
                self._slice_zoom[axis] = 1.0
                self._update_slice_geometry(axis)
                self.dvz.dvz_view_request_frame(self.view)
                return
            if (
                pointer.type == self.dvz.DVZ_POINTER_EVENT_CLICK
                and pointer.button == self.dvz.DVZ_POINTER_BUTTON_LEFT
                and self.set_cursor_from_slice_data(axis, x, y, select_region=False)
            ):
                self.dvz.dvz_view_request_frame(self.view)

        self._input_callback = on_input
        self._input_subscription = self.dvz.dvz_input_subscribe_event(
            self._input_router, self._input_callback, None
        )
        if self._input_subscription == 0:
            raise RuntimeError('dvz_input_subscribe_event() failed')

    def _pointer_figure_position(self, pointer) -> tuple[float, float] | None:
        """Convert raw logical-window pointer coordinates to figure layout pixels."""
        window_width, window_height = (float(value) for value in pointer.window_size)
        content_scale = float(pointer.content_scale)
        content_scale_x = content_scale_y = (
            content_scale if np.isfinite(content_scale) and content_scale > 0 else 1.0
        )
        resize = self.dvz.DvzInputResizeEvent()
        if self.dvz.dvz_input_router_last_resize(self._input_router, ctypes.byref(resize)):
            if not np.isfinite(window_width) or window_width <= 0:
                window_width = float(resize.window_width)
            if not np.isfinite(window_height) or window_height <= 0:
                window_height = float(resize.window_height)
            if resize.content_scale_x > 0:
                content_scale_x = float(resize.content_scale_x)
            if resize.content_scale_y > 0:
                content_scale_y = float(resize.content_scale_y)
        figure_x = ctypes.c_float()
        figure_y = ctypes.c_float()
        converted = self.dvz.dvz_figure_window_to_layout(
            self.figure,
            float(pointer.pos[0]),
            float(pointer.pos[1]),
            window_width,
            window_height,
            content_scale_x,
            content_scale_y,
            ctypes.byref(figure_x),
            ctypes.byref(figure_y),
        )
        return (figure_x.value, figure_y.value) if converted else None

    def close(self) -> None:
        """Unsubscribe slice input before releasing the base viewer."""
        if getattr(self, '_slice_loader', None) is not None:
            self._slice_loader.close()
            self._slice_loader = None
        if getattr(self, '_input_subscription', 0) and self._input_router:
            self.dvz.dvz_input_unsubscribe(self._input_router, self._input_subscription)
            self._input_subscription = 0
        super().close()
