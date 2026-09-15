"""Native four-panel linked atlas navigator."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

import numpy as np

from ibl_atlas_assets import open_volume_pack

from .atlas import AtlasMesh
from .navigator import (
    SLICE_DISPLAY_AXES,
    AtlasCursor,
    AtlasSliceComposer,
    cursor_from_slice_fraction,
    slice_index_fraction,
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


class LinkedAtlasNavigator(AtlasViewer):
    """Link orthogonal atlas slices, the ontology, and native 3-D anatomy."""

    def __init__(
        self,
        mesh: AtlasMesh,
        volumes: AtlasVolumes,
        *,
        mapping: str = 'allen',
        width: int = 1280,
        height: int = 900,
        annotation_opacity: float = 0.58,
        volume_opacity: float = 0.24,
        surface_opacity: float = 0.22,
        datoviz: ModuleType | None = None,
        **kwargs,
    ) -> None:
        if mesh.reference_space != volumes.regions.reference_space_id:
            raise ValueError('mesh and volume reference spaces differ')
        if not np.isfinite(annotation_opacity) or not 0 <= annotation_opacity <= 1:
            raise ValueError('annotation_opacity must be between zero and one')
        if not np.isfinite(volume_opacity) or not 0 <= volume_opacity <= 1:
            raise ValueError('volume_opacity must be between zero and one')
        self.volumes = volumes
        self.cursor = AtlasCursor.centre(volumes)
        self.slice_composer = AtlasSliceComposer(volumes, mapping)
        self.annotation_opacity = float(annotation_opacity)
        self.volume_opacity = float(volume_opacity)
        self._slice_fields: dict[str, object] = {}
        self._slice_images: dict[str, object] = {}
        self._crosshairs: dict[str, object] = {}
        self._cursor_controls = {
            axis: ctypes.c_int(value)
            for axis, value in zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True)
        }
        self._annotation_opacity_control = ctypes.c_float(self.annotation_opacity)
        self._volume_opacity_control = ctypes.c_float(self.volume_opacity)
        self._input_router = None
        self._input_subscription = 0
        self._input_callback = None
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
            self.dvz.dvz_panel_set_background_color(panel, self.dvz.DvzColor(8, 12, 18, 255))

    def _slice_quad(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
        sizes = dict(zip(('ap', 'ml', 'dv'), self.volumes.grid.shape, strict=True))
        aspect = sizes[x_axis] / sizes[y_axis]
        x_extent, y_extent = (0.94, 0.94 / aspect) if aspect >= 1 else (0.94 * aspect, 0.94)
        positions = np.array(
            [
                [-x_extent, -y_extent, 0],
                [-x_extent, +y_extent, 0],
                [+x_extent, -y_extent, 0],
                [+x_extent, +y_extent, 0],
            ],
            dtype=np.float32,
        )
        texcoords = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
        return positions, texcoords

    def _create_slices(self) -> None:
        for axis, panel in self.slice_panels.items():
            image_data = self._slice_rgba(axis)
            field = self.dvz.dvz_sampled_field_from_array(
                self.scene,
                image_data,
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
            self._check(self.dvz.dvz_visual_set_depth_test(image, False), 'slice depth disable')
            self._check(self.dvz.dvz_panel_add_visual(panel, image, None), 'slice attach')
            self._slice_fields[axis] = field
            self._slice_images[axis] = image

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
                self.dvz.dvz_panel_add_visual(panel, crosshair, None), 'slice crosshair attach'
            )
            self._crosshairs[axis] = crosshair

    def _slice_rgba(self, axis: str) -> NDArray[np.uint8]:
        index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        return self.slice_composer.compose(
            axis,
            index,
            annotation_opacity=self.annotation_opacity,
            selected_region_ids=self._selected_region_ids,
            selection_dim_factor=self.selection_dim_factor,
        )

    def _crosshair_positions(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]
        coordinates = dict(zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True))
        x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
        x_fraction = slice_index_fraction(self.volumes.grid, x_axis, coordinates[x_axis])
        y_fraction = slice_index_fraction(self.volumes.grid, y_axis, coordinates[y_axis])
        x = x0 + x_fraction * (x1 - x0)
        y = y0 + y_fraction * (y1 - y0)
        starts = np.array([[x, y0, 0.02], [x0, y, 0.02]], dtype=np.float32)
        ends = np.array([[x, y1, 0.02], [x1, y, 0.02]], dtype=np.float32)
        return starts, ends

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

    def _create_cursor_marker(self) -> None:
        self.cursor_marker = self.dvz.dvz_sphere(self.scene, 0)
        if not self.cursor_marker:
            raise RuntimeError('dvz_sphere() failed')
        self._check(
            self.dvz.dvz_panel_add_visual(self.panel, self.cursor_marker, None),
            '3-D cursor attach',
        )
        self._update_cursor_marker()

    def _update_cursor_marker(self) -> None:
        world = np.asarray(self.cursor.world_um(self.volumes), dtype=np.float32).reshape(1, 3)
        position = self.mesh_data.normalize_points(world)
        radius = np.array([85.0 * self.mesh_data.display_scale], dtype=np.float32)
        color = np.array([[43, 220, 255, 255]], dtype=np.uint8)
        self._check(
            self.dvz.dvz_visual_set_data_many(
                self.cursor_marker, {'position': position, 'radius': radius, 'color': color}
            ),
            '3-D cursor update',
        )

    def _refresh_slices(self) -> None:
        if not self._slice_fields:
            return
        for axis, field in self._slice_fields.items():
            self._check(
                self.dvz.dvz_sampled_field_update_from_array(
                    field,
                    self._slice_rgba(axis),
                    format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                    semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                    dim=self.dvz.DVZ_FIELD_DIM_2D,
                ),
                f'{axis} slice update',
            )
            starts, ends = self._crosshair_positions(axis)
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    self._crosshairs[axis],
                    {'position_start': starts, 'position_end': ends},
                ),
                f'{axis} crosshair update',
            )
        self._update_cursor_marker()

    def set_cursor(self, cursor: AtlasCursor, *, select_region: bool = True) -> None:
        """Move the AP/ML/DV cursor and refresh all linked panels."""
        for axis, value in zip(('ap', 'ml', 'dv'), cursor.as_index(), strict=True):
            cursor.replace(axis, value, self.volumes.grid.shape)
            self._cursor_controls[axis].value = value
        self.cursor = cursor
        if select_region:
            row = cursor.region(self.volumes, self.mapping)
            ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
            self._apply_selected_region_ids(
                ids, update_tree=True, update_table=True, clear_mesh=True
            )
        else:
            self._refresh_slices()

    def set_cursor_from_slice_data(self, axis: str, x: float, y: float) -> bool:
        """Move the cursor from one slice panel's data coordinates.

        Returns ``False`` when the coordinate lies outside the rendered image.
        """
        if axis not in self.slice_panels or not np.isfinite((x, y)).all():
            return False
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]
        if x < x0 or x > x1 or y < y0 or y > y1:
            return False
        cursor = cursor_from_slice_fraction(
            self.cursor,
            axis,
            float((x - x0) / (x1 - x0)),
            float((y - y0) / (y1 - y0)),
            self.volumes.grid,
        )
        self.set_cursor(cursor)
        return True

    def set_mapping(self, mapping: str, palette=None) -> None:
        """Switch all mesh, slice, cursor, and ontology identities together."""
        super().set_mapping(mapping, palette)
        self.slice_composer.set_mapping(mapping)
        self._refresh_slices()

    def _apply_selected_region_ids(self, region_ids, **kwargs) -> None:
        super()._apply_selected_region_ids(region_ids, **kwargs)
        if hasattr(self, '_slice_fields'):
            self._refresh_slices()

    def _draw_extra_gui(self, gui) -> None:
        self.dvz.dvz_gui_separator_text(gui, b'Linked atlas cursor')
        self.dvz.dvz_gui_text(gui, b'AP: ML -> right, dorsal up')
        self.dvz.dvz_gui_text(gui, b'ML: AP -> right, dorsal up')
        self.dvz.dvz_gui_text(gui, b'DV: ML -> right, anterior up')
        changed = False
        for axis, size in zip(('ap', 'ml', 'dv'), self.volumes.grid.shape, strict=True):
            changed |= self.dvz.dvz_gui_slider_int(
                gui, axis.upper().encode(), ctypes.byref(self._cursor_controls[axis]), 0, size - 1
            )
        if changed:
            self.set_cursor(
                AtlasCursor(*(self._cursor_controls[axis].value for axis in ('ap', 'ml', 'dv')))
            )
        if self.dvz.dvz_gui_slider_float(
            gui,
            b'Annotation opacity',
            ctypes.byref(self._annotation_opacity_control),
            0.0,
            1.0,
        ):
            self.annotation_opacity = float(self._annotation_opacity_control.value)
            self._refresh_slices()
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
        world = self.cursor.world_um(self.volumes)
        row = self.cursor.region(self.volumes, self.mapping)
        region = 'unmapped' if row is None else f'{row.acronym} — {row.name}'
        self.dvz.dvz_gui_text(
            gui,
            f'ML {world[0]:.0f} · AP {world[1]:.0f} · DV {world[2]:.0f} um'.encode(),
        )
        self.dvz.dvz_gui_text(gui, region.encode())

    def _create_view(self, *, offscreen: bool, title: str) -> None:
        super()._create_view(offscreen=offscreen, title=title)
        if offscreen:
            return
        self._input_router = self.dvz.dvz_view_input(self.view)
        if not self._input_router:
            raise RuntimeError('dvz_view_input() failed')

        def on_input(_router, event_ptr, _user_data) -> None:
            event = event_ptr.contents
            if event.type != self.dvz.DVZ_INPUT_EVENT_POINTER:
                return
            pointer = event.content.pointer
            if pointer.type != self.dvz.DVZ_POINTER_EVENT_CLICK:
                return
            for axis, panel in self.slice_panels.items():
                figure_pos = (ctypes.c_double * 2)(float(pointer.pos[0]), float(pointer.pos[1]))
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
                if self.set_cursor_from_slice_data(axis, float(data_pos[0]), float(data_pos[1])):
                    self.dvz.dvz_view_request_frame(self.view)
                    return

        self._input_callback = on_input
        self._input_subscription = self.dvz.dvz_input_subscribe_event(
            self._input_router, self._input_callback, None
        )
        if self._input_subscription == 0:
            raise RuntimeError('dvz_input_subscribe_event() failed')

    def close(self) -> None:
        """Unsubscribe slice input before releasing the base viewer."""
        if getattr(self, '_input_subscription', 0) and self._input_router:
            self.dvz.dvz_input_unsubscribe(self._input_router, self._input_subscription)
            self._input_subscription = 0
        super().close()
