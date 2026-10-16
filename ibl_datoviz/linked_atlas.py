"""Native four-panel linked atlas navigator."""

from __future__ import annotations

import ctypes
from contextlib import suppress
from typing import TYPE_CHECKING, NoReturn

import numpy as np

from ibl_anatomy import (
    MaterializedRegisteredAssets,
    open_anatomy_pack,
    open_intensity_block_pack,
    open_registered_projection,
    open_volume_pack,
)

from .atlas import AtlasMesh
from .atlas_slice_source import AtlasSliceSource
from .auto_slice import AutoSliceNavigation
from .contour_visual import ContourVisual
from .navigator import (
    SLICE_DISPLAY_AXES,
    AtlasCursor,
    AtlasSliceComposer,
    cursor_from_slice_fraction,
    mapped_region,
    slice_index_fraction,
    step_slice_cursor,
)
from .slice_input import SliceInputAdapter
from .slice_planes import SlicePlanes
from .slice_preparation import PreparedSliceLayers, SlicePreparation
from .slice_scheduler import SliceRequest, SliceScheduler
from .viewer import AtlasViewer

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from numpy.typing import NDArray

    from ibl_anatomy import AtlasVolumes


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
        mesh: AtlasMesh | None = None,
        volumes: AtlasVolumes | None = None,
        *,
        atlas=None,
        layout='linked',
        slice_source=None,
        slice_renderer='raster',
        render_volume: bool = True,
        mapping: str = 'allen',
        width: int = 1280,
        height: int = 900,
        annotation_opacity: float = 1.0,
        volume_opacity: float = 0.24,
        boundary_opacity: float = 0.82,
        boundary_width_px: float = 0.7,
        boundary_color: tuple[int, int, int] = (238, 242, 247),
        slice_background: tuple[int, int, int] = (29, 33, 39),
        surface_opacity: float = 1.0,
        palette=None,
        datoviz: ModuleType | None = None,
        **kwargs,
    ) -> None:
        if layout != 'linked':
            raise ValueError('LinkedAtlasNavigator requires layout="linked"')
        mesh, supplied_catalog = self._resolve_atlas(mesh, atlas, kwargs.pop('catalog', None))
        if palette is not None:
            raise ValueError('linked atlas slices require the verified catalog palette')
        if render_volume and volumes is None:
            raise ValueError('render_volume=True requires atlas volumes')
        slice_source = volumes if slice_source is None else slice_source
        if slice_source is None:
            raise ValueError('volume-free navigation requires an explicit slice_source')
        if slice_renderer not in ('raster', 'contours'):
            raise ValueError('slice_renderer must be raster or contours')
        if slice_renderer == 'contours' and not callable(
            getattr(slice_source, 'contour_slice', None)
        ):
            raise ValueError('contours require an exact registered contour slice source')
        self.slice_renderer = slice_renderer
        self._contour_visuals = {}
        self._accepted_contours = {}
        if volumes is not None and mesh.reference_space != volumes.regions.reference_space_id:
            raise ValueError('mesh and volume reference spaces differ')
        if mesh.reference_space != slice_source.regions.reference_space_id:
            raise ValueError('mesh and slice reference spaces differ')
        slice_reference = getattr(
            slice_source.grid, 'reference_space_id', slice_source.regions.reference_space_id
        )
        if mesh.reference_space != slice_reference:
            raise ValueError('mesh and slice grid reference spaces differ')
        catalog = volumes.regions if render_volume else slice_source.regions
        if supplied_catalog is not None and (
            supplied_catalog.reference_space_id != catalog.reference_space_id
            or any(
                tuple(supplied_catalog.physical(name)) != tuple(catalog.physical(name))
                for name in mesh.mapping_names
            )
        ):
            raise ValueError('linked layout catalog must match its slice source catalog')
        for atlas_mapping in mesh.mapping_names:
            if atlas_mapping not in catalog.mappings:
                raise ValueError(f'mesh mapping is absent from atlas catalog: {atlas_mapping}')
            catalog_ids = {row.atlas_id for row in catalog.physical(atlas_mapping)}
            mesh_ids = {
                int(region_id)
                for region_id in np.unique(mesh.mapping_ids(atlas_mapping))
                if region_id != 0
            }
            missing = sorted(mesh_ids - catalog_ids)
            if missing:
                raise ValueError(
                    f'mesh {atlas_mapping} IDs are absent from atlas catalog: {missing}'
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
        self.render_volume = bool(render_volume)
        self.volume = self.volume_field = None
        self._auto_slice = None
        self.slice_source = slice_source
        self.slice_resolution_label = _resolution_label(slice_source.grid)
        self.volume_resolution_label = _resolution_label(volumes.grid) if render_volume else None
        self.cursor = AtlasCursor.centre(slice_source)
        self.slice_composer = AtlasSliceComposer(slice_source, mapping)
        self._slice_preparation = SlicePreparation(slice_source, mapping)
        self._slice_revisions = {axis: 0 for axis in ('ap', 'ml', 'dv')}
        self._slice_source_id = str(
            getattr(slice_source, 'grid_id', getattr(slice_source.grid, 'grid_id', 'atlas-grid'))
        )
        self._slice_loader = None
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
        self._slice_shapes: dict[str, tuple[int, ...]] = {}
        self._annotation_fields: dict[str, object] = {}
        self._slice_images: dict[str, object] = {}
        self._annotation_images: dict[str, object] = {}
        self._hover_fields: dict[str, object] = {}
        self._hover_images: dict[str, object] = {}
        self._boundary_visuals: dict[str, object] = {}
        self._selection_visuals: dict[str, tuple] = {}
        self._selection_contours: dict[str, tuple] = {}
        self._crosshairs: dict[str, object] = {}
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
        self._slice_input = None
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
        try:
            super().__init__(
                mesh,
                layout='linked',
                mapping=mapping,
                catalog=catalog,
                width=width,
                height=height,
                surface_opacity=surface_opacity,
                datoviz=datoviz,
                **kwargs,
            )
            if slice_source is not volumes:
                self._slice_loader = SliceScheduler(
                    self._slice_preparation,
                    notify=self._notify_slice_ready,
                    max_workers=3,
                )
            self._auto_slice = AutoSliceNavigation(slice_source, notify=self._notify_slice_ready)
            self._slice_planes = SlicePlanes(self, slice_source, source_id=self._slice_source_id)
            self._create_slices()
            if self.render_volume:
                self._create_anatomical_volume()
            self._create_cursor_marker()
        except Exception:
            self.close()
            raise

    @classmethod
    def from_pack(cls, path: str | Path, **kwargs) -> NoReturn:
        """Reject the surface-only factory, which cannot supply atlas volumes."""
        raise TypeError(
            'LinkedAtlasNavigator.from_pack() requires atlas volumes; '
            'use from_packs(), from_multiresolution_packs(), or from_anatomy_packs()'
        )

    @classmethod
    def from_assets(cls, assets: object, **kwargs) -> NoReturn:
        """Reject the surface-only factory, which cannot supply atlas volumes."""
        raise TypeError(
            'LinkedAtlasNavigator.from_assets() requires atlas volumes; '
            'use from_packs(), from_registered_assets(), from_multiresolution_packs(), '
            'or from_anatomy_packs()'
        )

    @classmethod
    def from_asset_set(
        cls,
        root: str | Path,
        *,
        asset_set: object | None = None,
        **kwargs,
    ) -> NoReturn:
        """Reject the surface-only factory, which cannot supply atlas volumes."""
        raise TypeError(
            'LinkedAtlasNavigator.from_asset_set() requires atlas volumes; '
            'use from_packs(), from_registered_assets(), from_multiresolution_packs(), '
            'or from_anatomy_packs()'
        )

    @classmethod
    def from_packs(
        cls, mesh_pack: str | Path, volume_pack: str | Path, **kwargs
    ) -> LinkedAtlasNavigator:
        """Create a navigator from verified mesh and volume packs."""
        volumes = open_volume_pack(volume_pack).load_volumes()
        return cls(AtlasMesh.from_pack(mesh_pack), volumes, **kwargs)

    @classmethod
    def from_slice_source(cls, mesh: AtlasMesh, slice_source, **kwargs) -> LinkedAtlasNavigator:
        """Use compatible explicit atlas slices without constructing a 3-D volume."""
        if kwargs.pop('render_volume', False):
            raise ValueError('from_slice_source() requires render_volume=False')
        return cls(mesh, slice_source=slice_source, render_volume=False, **kwargs)

    @classmethod
    def from_registered_slices(
        cls,
        mesh_pack: str | Path,
        intensity_pack: str | Path,
        assets: MaterializedRegisteredAssets,
        *,
        catalog,
        **kwargs,
    ) -> LinkedAtlasNavigator:
        """Use verified registered slices and an explicit catalog without a volume pack.

        Materialized registered assets provide projection readers, not a region
        catalog. Supply the independently verified catalog used by those assets.
        Existing reader errors for absent sections remain explicit.
        """
        if not isinstance(assets, MaterializedRegisteredAssets):
            raise TypeError('assets must be verified MaterializedRegisteredAssets')
        projections = {
            projection.world_slice_axis: projection for projection in assets.projections.values()
        }
        if len(assets.projections) != 3 or set(projections) != {'ap', 'ml', 'dv'}:
            raise ValueError('registered assets must contain one ap/ml/dv projection')
        intensity = open_intensity_block_pack(intensity_pack)
        slices = AtlasSliceSource(intensity, projections, catalog)
        return cls.from_slice_source(AtlasMesh.from_pack(mesh_pack), slices, **kwargs)

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

    @classmethod
    def from_registered_assets(
        cls,
        mesh_pack: str | Path,
        volume_pack: str | Path,
        intensity_pack: str | Path,
        assets: MaterializedRegisteredAssets,
        **kwargs,
    ) -> LinkedAtlasNavigator:
        """Use an ``ibl-anatomy`` verified registered-asset result.

        The caller materializes or verifies the immutable root graph through
        ``ibl-anatomy``. Datoviz consumes the resulting projection readers without
        inferring files from an Ephys Atlas URL layout.
        """
        if not isinstance(assets, MaterializedRegisteredAssets):
            raise TypeError('assets must be verified MaterializedRegisteredAssets')
        volumes = open_volume_pack(volume_pack).load_volumes()
        intensity = open_intensity_block_pack(intensity_pack)
        projections = {
            projection.world_slice_axis: projection for projection in assets.projections.values()
        }
        if set(projections) != {'ap', 'ml', 'dv'}:
            raise ValueError('registered assets must contain one ap/ml/dv projection')
        slices = AtlasSliceSource(intensity, projections, volumes.regions)
        return cls(AtlasMesh.from_pack(mesh_pack), volumes, slice_source=slices, **kwargs)

    @classmethod
    def from_anatomy_packs(
        cls,
        mesh_pack: str | Path,
        volume_pack: str | Path,
        intensity_pack: str | Path,
        anatomy_pack: str | Path,
        **kwargs,
    ) -> LinkedAtlasNavigator:
        """Use a complete registered anatomy pack for high-resolution slices.

        The bounded dense ``volume_pack`` remains the 3-D ray-casting source. The
        projection-native ``intensity_pack`` and ``anatomy_pack`` provide lazy slices on
        their shared grid, so no complete high-resolution volume is uploaded to the GPU.
        """
        volumes = open_volume_pack(volume_pack).load_volumes()
        intensity = open_intensity_block_pack(intensity_pack)
        anatomy = open_anatomy_pack(
            anatomy_pack,
            reference_space_id=intensity.reference_space_id,
            grid_id=intensity.grid_id,
        )
        projections = {
            projection.world_slice_axis: projection for projection in anatomy.projections.values()
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
        self._configure_3d_camera()
        if self.slice_renderer == 'contours':
            for panel in self.slice_panels.values():
                msaa = self.dvz.dvz_msaa_desc()
                msaa.enabled, msaa.sample_count = True, 4
                self._check(
                    self.dvz.dvz_panel_set_msaa(panel, ctypes.byref(msaa)), 'contour slice MSAA'
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
            request = self._slice_request(axis)
            payload = self._prepare_slice(request)
            anatomy_data, annotation_data = payload.anatomy, payload.annotation
            self._slice_planes.update(axis, request, payload)
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
            self._slice_shapes[axis] = anatomy_data.shape
            self._slice_images[axis] = image

            if self.slice_renderer == 'raster':
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
                    self.dvz.dvz_visual_set_alpha_mode(
                        annotation_image, self.dvz.DVZ_ALPHA_BLENDED
                    ),
                    'annotation alpha mode',
                )
                attach.z_layer = 1
                self._check(
                    self.dvz.dvz_panel_add_visual(panel, annotation_image, ctypes.byref(attach)),
                    'annotation attach',
                )
                self._annotation_fields[axis] = annotation_field
                self._annotation_images[axis] = annotation_image

                hover_data = np.zeros_like(annotation_data)
                hover_field = self.dvz.dvz_sampled_field_from_array(
                    self.scene,
                    hover_data,
                    format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                    semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                    dim=self.dvz.DVZ_FIELD_DIM_2D,
                )
                hover_image = self.dvz.dvz_image(self.scene, 0)
                if not hover_image:
                    raise RuntimeError('dvz hover image() failed')
                self._check(
                    self.dvz.dvz_visual_set_data_many(
                        hover_image, {'position': positions, 'texcoords': texcoords}
                    ),
                    f'{axis} hover geometry upload',
                )
                self._check(
                    self.dvz.dvz_visual_set_field(hover_image, b'field', hover_field),
                    'hover field bind',
                )
                self._check(
                    self.dvz.dvz_image_set_sampling(
                        hover_image, self.dvz.DVZ_IMAGE_SAMPLING_NEAREST
                    ),
                    'hover nearest sampling',
                )
                self._check(self.dvz.dvz_visual_set_depth_test(hover_image, False), 'hover depth')
                self._check(
                    self.dvz.dvz_visual_set_alpha_mode(hover_image, self.dvz.DVZ_ALPHA_BLENDED),
                    'hover alpha mode',
                )
                attach.z_layer = 2
                self._check(
                    self.dvz.dvz_panel_add_visual(panel, hover_image, ctypes.byref(attach)),
                    'hover attach',
                )
                self._hover_fields[axis] = hover_field
                self._hover_images[axis] = hover_image

            boundaries = self.dvz.dvz_segment(self.scene, 0)
            if not boundaries:
                raise RuntimeError('slice boundary segment creation failed')
            boundary_starts, boundary_ends = self._map_boundary_segments(
                axis, payload.boundary_starts, payload.boundary_ends
            )
            self._upload_boundaries(
                boundaries, boundary_starts, boundary_ends, 'slice boundaries upload'
            )
            self._check(self.dvz.dvz_visual_set_depth_test(boundaries, False), 'boundary depth')
            self._check(
                self.dvz.dvz_visual_set_alpha_mode(boundaries, self.dvz.DVZ_ALPHA_BLENDED),
                'boundary alpha mode',
            )
            attach.z_layer = 3
            self._check(
                self.dvz.dvz_panel_add_visual(panel, boundaries, ctypes.byref(attach)),
                'slice boundaries attach',
            )
            self._boundary_visuals[axis] = boundaries

            outlines = []
            for layer in range(2):
                outline = self.dvz.dvz_segment(self.scene, 0)
                if not outline:
                    raise RuntimeError('slice selection outline creation failed')
                self._check(
                    self.dvz.dvz_visual_set_depth_test(outline, False), 'selection outline depth'
                )
                self._check(
                    self.dvz.dvz_visual_set_alpha_mode(outline, self.dvz.DVZ_ALPHA_BLENDED),
                    'selection outline alpha',
                )
                attach.z_layer = 4 + layer
                self._check(
                    self.dvz.dvz_panel_add_visual(panel, outline, ctypes.byref(attach)),
                    'selection outline attach',
                )
                outlines.append(outline)
            self._selection_visuals[axis] = tuple(outlines)
            self._upload_selection_outline(axis, payload)

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
            if self.slice_renderer == 'contours':
                self._contour_visuals[axis] = ContourVisual(self.dvz, self.scene, panel)
                self._stage_contours(axis, payload, opacity=request.annotation_opacity)
                self._contour_visuals[axis].activate(visible=request.annotation_visible)
                self._accepted_contours[axis] = (request, payload)
                self._refresh_boundaries(axis)

    def _slice_rgba(self, axis: str) -> NDArray[np.uint8]:
        index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        return self.slice_composer.compose(
            axis,
            index,
            annotation_opacity=self.annotation_opacity,
            selected_region_ids=self._selected_region_ids,
            selection_dim_factor=1.0,
        )

    def _slice_request(self, axis: str, index: int | None = None) -> SliceRequest:
        """Capture mutable presentation state on the owner thread."""
        if index is None:
            index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        selected_ids = (
            self._signed_focus_ids()
            if getattr(self, 'tree_model', None) is not None
            else tuple(self._selected_region_ids)
        )
        return SliceRequest(
            axis=axis,
            index=index,
            revision=self._slice_revisions[axis],
            source_id=self._slice_source_id,
            mapping=self.mapping,
            annotation_opacity=self.annotation_opacity,
            anatomy_visible=self.anatomy_visible,
            annotation_visible=self.annotation_visible,
            selected_region_ids=selected_ids,
            selection_dim_factor=1.0,
            renderer=self.slice_renderer,
        )

    def _slice_layers(
        self, axis: str, index: int | None = None
    ) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
        payload = self._prepare_slice(self._slice_request(axis, index))
        return payload.anatomy, payload.annotation

    def _prepare_slice(self, request: SliceRequest) -> PreparedSliceLayers:
        """Retain the adapter; workers use the independent preparation object."""
        return self._slice_preparation(request)

    def _notify_slice_ready(self, _axis: str) -> None:
        """Wake the owner thread after a worker finishes a current request."""
        if (
            self.view is not None
            and not self._closed
            and self.dvz.dvz_view_post(self.view, self._slice_post_callback, None) != 0
        ):
            self.dvz.dvz_view_wake(self.view)

    def _upload_slice_payload(self, request: SliceRequest, payload: PreparedSliceLayers) -> None:
        """Upload one fully prepared slice payload on the view owner thread."""
        axis = request.axis
        if self.slice_renderer == 'contours':
            if (
                request.source_id != self._slice_source_id
                or request.mapping != self.mapping
                or request.renderer != self.slice_renderer
                or request.revision != self._slice_revisions[axis]
            ):
                return
            if payload.contours is None or payload.contours.mapping != request.mapping:
                raise ValueError('contour payload differs from its captured request')
            self._stage_contours(axis, payload, opacity=request.annotation_opacity)
        anatomy, annotation = payload.anatomy, payload.annotation
        expected = self._slice_shapes[axis]
        if anatomy.shape != expected or annotation.shape != expected:
            raise RuntimeError(
                f'{axis} slice payload extent changed: expected {expected}, '
                f'got anatomy {anatomy.shape} and annotation {annotation.shape}'
            )
        self.dvz.dvz_sampled_field_update_from_array(
            self._slice_fields[axis],
            anatomy,
            format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
            semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
            dim=self.dvz.DVZ_FIELD_DIM_2D,
        )
        if self.slice_renderer == 'raster':
            self.dvz.dvz_sampled_field_update_from_array(
                self._annotation_fields[axis],
                annotation,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )
        starts, ends = self._map_boundary_segments(
            axis, payload.boundary_starts, payload.boundary_ends
        )
        self._upload_boundaries(
            self._boundary_visuals[axis], starts, ends, f'{axis} prepared boundaries update'
        )
        self._upload_selection_outline(axis, payload)
        self._slice_planes.update(axis, request, payload)
        if self.slice_renderer == 'contours':
            self._contour_visuals[axis].activate(visible=request.annotation_visible)
            self._accepted_contours[axis] = (request, payload)

    def _stage_contours(self, axis, payload, *, opacity):
        if payload.contours is None:
            raise ValueError('exact contour geometry is missing')
        colors = {
            row.atlas_id: tuple(bytes.fromhex(row.color_hex.removeprefix('#')))
            for row in self.catalog.physical(payload.contours.mapping)
        }
        corners, _ = self._slice_quad(axis)
        self._contour_visuals[axis].stage(
            payload.contours,
            colors,
            payload.svg_to_fraction,
            corners,
            opacity=opacity,
        )

    def _refresh_hover_overlays(self, axes=None) -> None:
        """Update lightweight region-tint layers without recomposing base slices."""
        if self.slice_renderer == 'contours':
            # Exact geometry supplies hover identity; no raster tint/lookup on the owner thread.
            return
        if not self._hover_fields:
            return
        refresh_axes = tuple(self._hover_fields) if axes is None else tuple(axes)
        indices = dict(zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True))
        for axis in refresh_axes:
            mask = self.slice_composer.region_mask(axis, indices[axis], self._hovered_region_ids)
            overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
            overlay[mask] = (255, 222, 92, 104)
            self.dvz.dvz_sampled_field_update_from_array(
                self._hover_fields[axis],
                overlay,
                format=self.dvz.DVZ_FIELD_FORMAT_RGBA8_UNORM,
                semantic=self.dvz.DVZ_FIELD_SEMANTIC_COLOR,
                dim=self.dvz.DVZ_FIELD_DIM_2D,
            )

    def _drain_prepared_slices(self, _view, _user_data) -> None:
        """Apply prepared slice payloads on the Datoviz view owner thread."""
        try:
            self._drain_auto_slice()
        except Exception as error:
            # This method is also a native post callback: ctypes cannot forward
            # upload failures to show(), so retain the error and stop the loop.
            self._slice_error = self._gui_callback_error = error
            self._close_pending = True
            if getattr(self, 'app', None) is not None:
                self.dvz.dvz_app_stop(self.app)
            return
        if self._slice_loader is None or self._closed:
            return
        try:
            ready = self._slice_loader.drain_ready()
        except Exception as error:  # callback boundaries must not leak exceptions
            self._slice_error = error
            # Other axes (and failures) remain queued; retry on the owner thread
            # even if every worker notification arrived in this frame.
            self.dvz.dvz_view_request_frame(self.view)
            return
        for item in ready:
            try:
                self._upload_slice_payload(item.request, item.payload)
                if self._hovered_region_ids:
                    self._refresh_hover_overlays((item.request.axis,))
            except Exception as error:
                # Native post callbacks cannot propagate exceptions. Stop the
                # frame loop and let show() release resources after it returns.
                self._slice_error = self._gui_callback_error = error
                self._close_pending = True
                if getattr(self, 'app', None) is not None:
                    self.dvz.dvz_app_stop(self.app)
                return
        if ready:
            self._slice_error = None
            self.dvz.dvz_view_request_frame(self.view)

    def _slice_fraction(self, axis, index):
        if self.slice_renderer == 'raster':
            return slice_index_fraction(self.slice_source.grid, axis, index)
        grid = self.slice_source.grid
        column, row = grid.array_axes.index(axis), grid.world_axes.index(axis)
        fraction = (index + 0.5) / grid.shape[column]
        matrix = np.asarray(grid.index_to_world_um_matrix).reshape(4, 4)
        return float(fraction if matrix[row, column] > 0 else 1 - fraction)

    def _crosshair_positions(self, axis: str) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        positions, _ = self._slice_quad(axis)
        x0, y0 = positions[0, :2]
        x1, y1 = positions[3, :2]
        coordinates = dict(zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True))
        x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
        x_fraction = self._slice_fraction(x_axis, coordinates[x_axis])
        y_fraction = self._slice_fraction(y_axis, coordinates[y_axis])
        x = x0 + x_fraction * (x1 - x0)
        y = y0 + y_fraction * (y1 - y0)
        starts = np.array([[x, y0, 0.02], [x0, y, 0.02]], dtype=np.float32)
        ends = np.array([[x, y1, 0.02], [x1, y, 0.02]], dtype=np.float32)
        return starts, ends

    def _boundary_rgba(self) -> NDArray[np.uint8]:
        """Return the current boundary color, including visibility and opacity."""
        alpha = round(255 * self.boundary_opacity) if self.boundaries_visible else 0
        return np.asarray((*self.boundary_color, alpha), dtype=np.uint8)

    def _boundary_positions(
        self,
        axis: str,
        *,
        composer: AtlasSliceComposer | None = None,
        index: int | None = None,
    ) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        """Map normalized atlas boundary segments onto one displayed slice quad."""
        composer = self.slice_composer if composer is None else composer
        if index is None:
            index = self.cursor.as_index()[('ap', 'ml', 'dv').index(axis)]
        if self.slice_renderer == 'contours' and axis in self._accepted_contours:
            payload = self._accepted_contours[axis][1]
            starts, ends = payload.boundary_starts, payload.boundary_ends
        else:
            starts, ends = composer.boundary_segments(axis, index)
        return self._map_boundary_segments(axis, starts, ends)

    def _map_boundary_segments(
        self, axis: str, starts: NDArray[np.float32], ends: NDArray[np.float32]
    ) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
        """Map normalized boundary segments using the current displayed quad."""
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
        self._upload_boundaries(
            self._boundary_visuals[axis], starts, ends, f'{axis} slice boundaries update'
        )

    def _upload_selection_outline(self, axis, payload=None):
        if payload is not None:
            self._selection_contours[axis] = (payload.selection_starts, payload.selection_ends)
        starts, ends = self._map_boundary_segments(axis, *self._selection_contours[axis])
        for visual, color, width in zip(
            self._selection_visuals[axis],
            ((7, 16, 25, 255), (255, 255, 255, 255)),
            (4.0, 1.5),
            strict=True,
        ):
            self._upload_boundaries(
                visual, starts, ends, 'slice selection outline', color=color, width=width
            )

    def _upload_boundaries(self, visual, starts, ends, context: str, *, color=None, width=None):
        """Hide empty layers; native attribute setters require nonzero counts."""
        count = len(starts)
        if count:
            self._check(
                self.dvz.dvz_visual_set_data_many(
                    visual,
                    {
                        'position_start': starts,
                        'position_end': ends,
                        'color': np.tile(
                            self._boundary_rgba() if color is None else color, (count, 1)
                        ).astype(np.uint8),
                        'stroke_width_px': np.full(
                            count,
                            self.boundary_width_px if width is None else width,
                            dtype=np.float32,
                        ),
                    },
                ),
                context,
            )
        # Keeping previous nonempty storage is safe while hidden. A subsequent
        # nonempty upload replaces it before making the layer visible again.
        self._check(self.dvz.dvz_visual_set_visible(visual, bool(count)), f'{context} visibility')

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
        if not self.render_volume or self.volume_opacity <= 0:
            super()._update_surface_alpha_mode()
            return
        # The bounded volume route still composes through source-over blending.
        mode = self.dvz.DVZ_ALPHA_BLENDED
        if mode == self._surface_alpha_mode:
            return
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.mesh, mode),
            'surface transparency mode',
        )
        self._surface_alpha_mode = mode

    def _create_cursor_marker(self) -> None:
        self.cursor_marker = self.dvz.dvz_mesh(self.scene, 0)
        if not self.cursor_marker:
            raise RuntimeError('3-D cursor visual creation failed')
        material = self.dvz.dvz_phong_material_desc()
        material.phong.ambient = 0.35
        material.phong.diffuse = 0.75
        material.phong.specular = 0.35
        material.phong.shininess = 32.0
        self._check(
            self.dvz.dvz_visual_set_material(self.cursor_marker, material),
            '3-D cursor material',
        )
        self._check(
            self.dvz.dvz_visual_set_depth_test(self.cursor_marker, True),
            '3-D cursor depth',
        )
        self._check(
            self.dvz.dvz_visual_set_alpha_mode(self.cursor_marker, self.dvz.DVZ_ALPHA_OPAQUE),
            '3-D cursor alpha mode',
        )
        self._update_cursor_marker()
        self._check(
            self.dvz.dvz_panel_add_visual(self.panel, self.cursor_marker, None),
            '3-D cursor attach',
        )

    def _update_cursor_marker(self) -> None:
        world = np.asarray(self.cursor.world_um(self.slice_source), dtype=np.float32).reshape(1, 3)
        position = self.mesh_data.normalize_points(world)[0]
        desc = self.dvz.dvz_geometry_sphere_desc()
        desc.center[:] = position
        # Fixed atlas-space size: zoom and perspective provide physical depth cues.
        desc.radius = 120.0 * self.mesh_data.display_scale
        desc.color = self.dvz.DvzColor(43, 220, 255, 255)
        geometry = self.dvz.dvz_geometry_sphere(ctypes.byref(desc))
        if not geometry:
            raise RuntimeError('3-D cursor sphere creation failed')
        parts = [geometry]
        merged = None
        try:
            for axis in range(3):
                cylinder = self.dvz.dvz_geometry_cylinder_desc()
                cylinder.radius = 28.0 * self.mesh_data.display_scale
                cylinder.height = 900.0 * self.mesh_data.display_scale
                cylinder.color = self.dvz.DvzColor(94, 174, 192, 255)
                rod = self.dvz.dvz_geometry_cylinder(ctypes.byref(cylinder))
                if not rod:
                    raise RuntimeError('3-D cursor cylinder creation failed')
                parts.append(rod)
                transform = np.eye(4)
                transform[:3, :3] = np.roll(np.eye(3), (axis + 1) % 3, axis=0)
                transform[:3, 3] = position
                matrix = ((ctypes.c_double * 4) * 4)(*map(tuple, transform.T))
                self._check(
                    self.dvz.dvz_geometry_transform(rod, matrix), '3-D cursor axis transform'
                )
            pointers = (type(geometry) * len(parts))(*parts)
            merged = self.dvz.dvz_geometry_merge(len(parts), pointers)
            if not merged:
                raise RuntimeError('3-D cursor geometry merge failed')
            # The mesh copies the geometry; the scene owns the visual.
            self._check(
                self.dvz.dvz_mesh_set_geometry(self.cursor_marker, merged),
                '3-D cursor update',
            )
        finally:
            if merged:
                self.dvz.dvz_geometry_destroy(merged)
            for part in parts:
                self.dvz.dvz_geometry_destroy(part)

    def _refresh_slices(self, axes=None) -> None:
        if not self._slice_fields:
            return
        refresh_axes = tuple(self._slice_fields) if axes is None else tuple(axes)
        for axis in refresh_axes:
            self._slice_revisions[axis] += 1
            request = self._slice_request(axis)
            if self._slice_loader is not None and self.view is not None:
                self._slice_loader.submit(request)
            else:
                payload = self._prepare_slice(request)
                self._upload_slice_payload(request, payload)
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
        for images in (self._slice_images, self._annotation_images, self._hover_images):
            if axis not in images:
                continue
            visual = images[axis]
            self._check(
                self.dvz.dvz_visual_set_data(visual, 'position', positions),
                f'{axis} slice zoom',
            )
        if self.slice_renderer == 'contours' and axis in self._accepted_contours:
            request, payload = self._accepted_contours[axis]
            self._stage_contours(axis, payload, opacity=request.annotation_opacity)
            self._contour_visuals[axis].activate(visible=request.annotation_visible)
        self._refresh_boundaries(axis)
        self._upload_selection_outline(axis)
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
        self._require_open()
        if not isinstance(cursor, AtlasCursor):
            raise TypeError('cursor must be AtlasCursor')
        if not isinstance(select_region, (bool, np.bool_)):
            raise ValueError('select_region must be boolean')
        current = cursor.as_index()
        # Validate the complete candidate before changing any retained/control state.
        for axis, value in zip(('ap', 'ml', 'dv'), current, strict=True):
            cursor.replace(axis, value, self.slice_source.grid.shape)
        self._cancel_auto_slice()
        old_cursor = self.cursor
        before = self.slices._snapshot()
        snapshot = self._surface_transaction_snapshot()
        self.selection._hold_events += 1
        try:
            self.cursor = cursor
            for axis, value in zip(('ap', 'ml', 'dv'), current, strict=True):
                self._cursor_controls[axis].value = value
            if select_region:
                ids = self._cursor_selection_ids()
                if ids is not None:
                    self._apply_selected_region_ids(
                        ids, update_tree=True, update_table=True, clear_mesh=True
                    )
                else:
                    # Pending geometry is unknown, not confirmed background.
                    self._refresh_slices()
            else:
                changed_axes = tuple(
                    axis
                    for axis, previous, after in zip(
                        ('ap', 'ml', 'dv'), old_cursor.as_index(), current, strict=True
                    )
                    if previous != after
                )
                self._refresh_slices(changed_axes)
        except Exception:
            self.cursor = old_cursor
            for axis, value in zip(('ap', 'ml', 'dv'), old_cursor.as_index(), strict=True):
                self._cursor_controls[axis].value = value
            self._restore_linked_transaction(snapshot)
            raise
        finally:
            self.selection._hold_events -= 1
        if select_region:
            self.selection._publish('regions')
        self.slices._publish(before)

    def set_cursor_from_slice_data(
        self, axis: str, x: float, y: float, *, select_region: bool = False
    ) -> bool:
        """Move the cursor from one slice panel's data coordinates.

        Returns ``False`` when the coordinate lies outside the rendered image.
        """
        self._require_open()
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
        cursor = self.cursor
        if self.slice_renderer == 'contours':
            accepted = self._accepted_contours.get(axis)
            if accepted is None or accepted[0].mapping != self.mapping:
                return None
            cursor = cursor.replace(axis, accepted[0].index, self.slice_source.grid.shape)
            grid = self.slice_source.grid
            matrix = np.asarray(grid.index_to_world_um_matrix).reshape(4, 4)
            for name, fraction in zip(
                SLICE_DISPLAY_AXES[axis], ((x - x0) / (x1 - x0), (y - y0) / (y1 - y0)), strict=True
            ):
                column, row = grid.array_axes.index(name), grid.world_axes.index(name)
                raw_fraction = 1 - fraction if matrix[row, column] < 0 else fraction
                # Quad edges represent half cells. Boundary ties choose the
                # increasing array-index cell, with the exterior edge clamped.
                index = int(
                    np.clip(np.floor(raw_fraction * grid.shape[column]), 0, grid.shape[column] - 1)
                )
                cursor = cursor.replace(name, index, grid.shape)
            return cursor
        return cursor_from_slice_fraction(
            cursor,
            axis,
            float((x - x0) / (x1 - x0)),
            float((y - y0) / (y1 - y0)),
            self.slice_source.grid,
        )

    def _cursor_selection_ids(self):
        if self.slice_renderer == 'contours':
            available, region_id = self._contour_region_query()
            if not available:
                return None
            return () if region_id is None else (region_id,)
        row = self.cursor.region(self.slice_source, self.mapping)
        return () if row is None or row.atlas_id == 0 else (row.atlas_id,)

    def _contour_region_under_cursor(self):
        return self._contour_region_query()[1]

    def _contour_region_query(self):
        coordinates = dict(zip(('ap', 'ml', 'dv'), self.cursor.as_index(), strict=True))
        for axis, (request, _) in self._accepted_contours.items():
            if request.index != coordinates[axis] or request.mapping != self.mapping:
                continue
            x_axis, y_axis = SLICE_DISPLAY_AXES[axis]
            corners, _ = self._slice_quad(axis)
            fraction = np.asarray(
                (
                    self._slice_fraction(x_axis, coordinates[x_axis]),
                    self._slice_fraction(y_axis, coordinates[y_axis]),
                )
            )
            point = corners[0, :2] + fraction * (corners[3, :2] - corners[0, :2])
            return True, self._contour_region_at(axis, *point)
        return False, None

    def _contour_region_at(self, axis, x, y):
        accepted = self._accepted_contours.get(axis)
        if accepted is None or accepted[0].mapping != self.mapping:
            return None
        corners, _ = self._slice_quad(axis)
        low, high = corners[0, :2], corners[3, :2]
        fraction = (np.asarray((x, y)) - low) / (high - low)
        if np.any(fraction < 0) or np.any(fraction > 1):
            return None
        inverse = np.linalg.inv(np.asarray(accepted[1].svg_to_fraction).reshape(3, 3))
        svg = inverse @ (*fraction, 1)
        return accepted[1].contours.region_at(*svg[:2])

    def _set_slice_hover(self, axis: str | None, x: float = 0.0, y: float = 0.0) -> bool:
        """Update the transient slice marker and region readout."""
        cursor = self._cursor_at_slice_data(axis, x, y) if axis is not None else None
        row = None
        label = None
        if cursor is not None:
            if self.slice_renderer == 'contours':
                region_id = self._contour_region_at(axis, x, y)
                row = next(
                    (r for r in self.catalog.physical(self.mapping) if r.atlas_id == region_id),
                    None,
                )
            else:
                cached_lookup = getattr(
                    self.slice_source, 'cached_annotation_index_at_world', None
                )
                source_index = (
                    cached_lookup(cursor.world_um(self.slice_source), preferred_axis=axis)
                    if cached_lookup is not None
                    else cursor.source_index(self.slice_source)
                )
                if source_index is None:
                    label = 'loading…'
                else:
                    row = mapped_region(self.slice_source, source_index, self.mapping)
            if label is None:
                label = 'unmapped' if row is None else f'{row.acronym} — {row.name}'
        region_ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
        if cursor is None:
            model = getattr(self, '_selector_model', None)
            region = model.by_id.get(model.hover) if model is not None else None
            region_ids = (region.atlas_id,) if region is not None else ()
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
        return changed

    def step_slice(self, axis: str, delta: int) -> bool:
        """Step one slice plane without changing committed region selection."""
        self._require_open()
        if axis not in self.slice_panels or not delta:
            return False
        cursor = step_slice_cursor(self.cursor, axis, int(delta), self.slice_source.grid.shape)
        if cursor == self.cursor:
            return False
        self.set_cursor(cursor, select_region=False)
        return True

    def toggle_cursor_region_selection(self) -> None:
        """Toggle the region under the current AP/ML/DV cursor."""
        self._require_open()
        if self.slice_renderer == 'contours':
            available, region_id = self._contour_region_query()
            if not available:
                return
            ids = () if region_id is None else (region_id,)
        else:
            row = self.cursor.region(self.slice_source, self.mapping)
            ids = () if row is None or row.atlas_id == 0 else (row.atlas_id,)
        if ids == self._selected_region_ids:
            ids = ()
        self._apply_selected_region_ids(ids, update_tree=True, update_table=True, clear_mesh=True)
        self.selection._publish('regions')

    def select_cursor_region(self) -> None:
        """Toggle the cursor region; retained as the public convenience name."""
        self._require_open()
        self.toggle_cursor_region_selection()

    def _restore_linked_transaction(self, snapshot, *, composer_mapping=None, widgets=()):
        """Restore both presentation domains, superseding rejected slice requests."""
        if self._closed:
            return
        try:
            self._restore_surface_transaction(snapshot, widgets)
            if composer_mapping is not None:
                self.slice_composer.set_mapping(composer_mapping)
            self._set_tree_selection(self._selected_region_ids)
            self._set_probe_table_selection(self._selected_region_ids)
            self._set_region_table_selection(self._selected_region_ids)
            # Mapping/selection setters may already have cleared native picks.
            # Acknowledge that native state without dropping restored host IDs on
            # the next frame; programmatic selection remains authoritative.
            self._last_mesh_region_ids = self._mesh_selected_region_ids()
            if hasattr(self, '_slice_fields'):
                # Revisions advance again so workers cannot apply rejected state.
                self._refresh_slices()
                self._refresh_hover_overlays()
        except Exception as rollback_error:
            self.close()
            raise RuntimeError(
                'linked transaction rollback failed; viewer closed'
            ) from rollback_error

    def set_mapping(self, mapping: str, palette=None) -> None:
        """Switch all mesh, slice, cursor, and ontology identities together."""
        self._require_open()
        if palette is not None:
            raise ValueError('linked atlas slices require the verified catalog palette')
        self._cancel_auto_slice()
        snapshot = self._surface_transaction_snapshot()
        previous_mapping = self.slice_composer.mapping
        widgets = tuple(
            name
            for name in ('region_tree', 'probe_table', 'region_table')
            if getattr(self, name) is not None
        )
        self.selection._hold_events += 1
        try:
            super().set_mapping(mapping)
            self.slice_composer.set_mapping(mapping)
            self._refresh_slices()
        except Exception:
            self._restore_linked_transaction(
                snapshot, composer_mapping=previous_mapping, widgets=widgets
            )
            raise
        finally:
            self.selection._hold_events -= 1
        self.selection._publish('mapping')

    def _apply_selected_region_ids(self, region_ids, **kwargs) -> None:
        self._cancel_auto_slice()
        snapshot = self._surface_transaction_snapshot()
        self.selection._hold_events += 1
        try:
            super()._apply_selected_region_ids(region_ids, **kwargs)
            if hasattr(self, '_slice_fields'):
                self._refresh_slices()
        except Exception:
            self._restore_linked_transaction(snapshot)
            raise
        finally:
            self.selection._hold_events -= 1
        # The outer public setter/gesture publishes after its remaining work.

    def _restore_selection_feedback(self):
        """Replace rejected slice revisions and restore every transient hover layer."""
        super()._restore_selection_feedback()
        self._refresh_slices()
        self._refresh_hover_overlays()

    def _set_hovered_region_ids(self, region_ids) -> bool:
        """Brighten transient hover across 3-D and lightweight slice overlays."""
        changed = super()._set_hovered_region_ids(region_ids)
        if changed:
            self._refresh_hover_overlays()
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

    def _cancel_auto_slice(self):
        if getattr(self, '_auto_slice', None) is not None:
            self._auto_slice.cancel()

    def _region_list_intent(self, effect, candidate):
        if self._auto_slice is None:
            return
        target = effect.get('target', effect.get('id'))
        row = candidate.by_id.get(target)
        selected = self._selected_region_ids
        signed_id = next(
            (value for value in selected if row is not None and abs(value) == abs(row.atlas_id)),
            None,
        )
        # A deselection or clear cancels old work without jumping to another row.
        if target not in candidate.selected:
            signed_id = None
        self._auto_slice.request(self.mapping, signed_id)

    def _drain_auto_slice(self, *_args):
        if getattr(self, '_auto_slice', None) is None or self._closed:
            return
        anchor = self._auto_slice.drain()
        if anchor is not None:
            self.set_cursor(AtlasCursor(*anchor), select_region=False)

    def _draw_viewport_toolbar_gui(self, gui):
        super()._draw_viewport_toolbar_gui(gui)
        enabled = ctypes.c_bool(self._auto_slice.enabled)
        self.dvz.dvz_gui_same_line(gui, 0.0, 12.0 * self.ui_scale)
        if self.dvz.dvz_gui_checkbox(gui, b'Auto-slice selected region', ctypes.byref(enabled)):
            self.slices.set_auto_slice(enabled.value)
        if self._auto_slice.status:
            self.dvz.dvz_gui_same_line(gui, 0.0, 12.0 * self.ui_scale)
            if self._auto_slice.navigation.available:
                self.dvz.dvz_gui_text(gui, self._auto_slice.status.encode())
            else:
                self.dvz.dvz_gui_text(gui, b'Unavailable for this source')
                self.dvz.dvz_gui_same_line(gui, 0.0, 4.0 * self.ui_scale)
                self._sidebar.icon(
                    gui, b'##auto_slice_source_info', 'INFO', self._auto_slice.status
                )
        changed = False
        labels = (b'Coronal (AP)', b'Sagittal (ML)', b'Horizontal (DV)')
        width, _ = self._sidebar.available(gui)
        gap = 12.0 * self.ui_scale
        slider_width = max(1.0, (width - 2.0 * gap) / 3.0 - 150.0 * self.ui_scale)
        for index, (axis, size, label) in enumerate(
            zip(('ap', 'ml', 'dv'), self.slice_source.grid.shape, labels, strict=True)
        ):
            if index:
                self.dvz.dvz_gui_same_line(gui, 0.0, gap)
            self.dvz.dvz_gui_set_next_item_width(gui, slider_width)
            changed |= self.dvz.dvz_gui_slider_int(
                gui, label, ctypes.byref(self._cursor_controls[axis]), 0, size - 1
            )
        if changed:
            self.set_cursor(
                AtlasCursor(*(self._cursor_controls[a].value for a in ('ap', 'ml', 'dv')))
            )

    def _draw_cursor_gui(self, gui) -> None:
        """Draw compact, always-visible cursor and selection controls."""
        world = self.cursor.world_um(self.slice_source)
        if self.slice_renderer == 'contours':
            region_id = self._contour_region_under_cursor()
            row = next(
                (r for r in self.catalog.physical(self.mapping) if r.atlas_id == region_id), None
            )
        else:
            row = self.cursor.region(self.slice_source, self.mapping)
        region = 'unmapped' if row is None else f'{row.acronym} — {row.name}'
        volume_label = (
            f'3-D {self.volume_resolution_label}' if self.render_volume else '3-D volume disabled'
        )
        self.dvz.dvz_gui_separator_text(gui, b'Cursor and selection')
        self.dvz.dvz_gui_text(
            gui,
            f'Slices {self.slice_resolution_label} | {volume_label}'.encode(),
        )
        self.dvz.dvz_gui_text(
            gui,
            f'ML {world[0]:.0f} · AP {world[1]:.0f} · DV {world[2]:.0f} um'.encode(),
        )
        self.dvz.dvz_gui_text(gui, region.encode())
        if row is not None and row.atlas_id != 0:
            selected = self._selected_region_ids == (row.atlas_id,)
            action = 'Deselect' if selected else 'Select'
            label = f'{action} {row.acronym}##cursor_region_selection'.encode()
            if self.dvz.dvz_gui_button(gui, label):
                self.toggle_cursor_region_selection()
        hover_source = self._hovered_slice_axis.upper() if self._hovered_slice_axis else '3-D'
        hover_label = self._hovered_region_label or '—'
        self.dvz.dvz_gui_text(gui, f'Hover ({hover_source}): {hover_label}'.encode())

    def _draw_layer_gui(self, gui) -> None:  # noqa: PLR0912 - declarative GUI controls
        """Draw optional layer controls in a compact collapsible section."""
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
            self.set_slice_layers(anatomy=bool(self._anatomy_visible_control.value))
        if self.dvz.dvz_gui_checkbox(
            gui, b'Annotation slice layer', ctypes.byref(self._annotation_visible_control)
        ):
            self.set_slice_layers(annotations=bool(self._annotation_visible_control.value))
        if self.dvz.dvz_gui_checkbox(
            gui, b'Region boundaries', ctypes.byref(self._boundaries_visible_control)
        ):
            self.set_slice_layers(boundaries=bool(self._boundaries_visible_control.value))
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
        if self.volume and self.dvz.dvz_gui_slider_float(
            gui,
            b'Volume opacity',
            ctypes.byref(self._volume_opacity_control),
            0.0,
            1.0,
        ):
            self.set_volume_opacity(float(self._volume_opacity_control.value))

    def set_slice_plane(self, axis, *, in_3d=True):
        """Present accepted slice pixels as paired physical planes in the 3-D panel."""
        self._require_open()
        self._slice_planes.show(axis, visible=in_3d)

    def set_slice_layers(self, *, anatomy=None, annotations=None, boundaries=None):
        """Change slice layers in the existing panels without moving the cursor."""
        self._require_open()
        updates = {}
        for name, value in (
            ('anatomy', anatomy),
            ('annotation', annotations),
            ('boundaries', boundaries),
        ):
            if value is not None:
                if not isinstance(value, (bool, np.bool_)):
                    raise ValueError('slice layer visibility must be boolean')
                updates[name] = bool(value)
        previous = {name: getattr(self, f'{name}_visible') for name in updates}
        try:
            for name, value in updates.items():
                setattr(self, f'{name}_visible', value)
                getattr(self, f'_{name}_visible_control').value = value
            if any(
                previous[name] != updates[name]
                for name in ('anatomy', 'annotation')
                if name in updates
            ):
                self._refresh_slices()
            elif 'boundaries' in updates and previous['boundaries'] != updates['boundaries']:
                for axis in self._boundary_visuals:
                    self._refresh_boundaries(axis)
        except Exception as error:
            for name, value in previous.items():
                setattr(self, f'{name}_visible', value)
                getattr(self, f'_{name}_visible_control').value = value
            try:
                self._refresh_slices()
            except Exception:
                self.close()
                raise RuntimeError('slice layer rollback failed; navigator closed') from error
            raise

    def set_volume_opacity(self, opacity):
        """Change volume opacity in the existing 3D panel, including zero to hide."""
        self._require_open()
        if not np.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('volume opacity must be finite and between zero and one')
        if not self.volume:
            if opacity:
                raise ValueError('volume rendering is disabled')
            return
        previous, mode = self.volume_opacity, self._surface_alpha_mode
        try:
            self._check(
                self.dvz.dvz_volume_set_opacity(self.volume, float(opacity)), 'volume opacity'
            )
            self.volume_opacity = float(opacity)
            self._volume_opacity_control.value = float(opacity)
            self._update_surface_alpha_mode()
        except Exception as error:
            self.volume_opacity = previous
            self._volume_opacity_control.value = previous
            try:
                self._check(
                    self.dvz.dvz_volume_set_opacity(self.volume, previous), 'volume rollback'
                )
                self._check(
                    self.dvz.dvz_visual_set_alpha_mode(self.mesh, mode), 'surface alpha rollback'
                )
                self._surface_alpha_mode = mode
            except Exception:
                self.close()
                raise RuntimeError('volume opacity rollback failed; navigator closed') from error
            raise

    def _process_gui_frame(self) -> None:
        super()._process_gui_frame()
        self._drain_auto_slice()
        if self._slice_loader is not None:
            self._drain_prepared_slices(self.view, None)

    def _draw_plane_controls(self, gui):
        for axis in ('ap', 'ml', 'dv'):
            control = ctypes.c_bool(axis in self._slice_planes.visible_axes)
            if self.dvz.dvz_gui_checkbox(
                gui, f'{axis.upper()} plane in 3-D'.encode(), ctypes.byref(control)
            ):
                self.slices.show_plane(axis, in_3d=control.value)

    def _draw_extra_gui(self, gui) -> None:
        self._draw_cursor_gui(gui)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Slices and 3-D layers', 0):
            self._draw_layer_gui(gui)
            planes = getattr(self, '_slice_planes', None)
            if planes is not None:
                self._draw_plane_controls(gui)
        if self.dvz.dvz_gui_collapsing_header(gui, b'Controls and orientation', 0):
            self.dvz.dvz_gui_text(gui, b'AP: ML -> right, dorsal up')
            self.dvz.dvz_gui_text(gui, b'ML: AP -> right, dorsal up')
            self.dvz.dvz_gui_text(gui, b'DV: ML -> right, anterior up')
            self.dvz.dvz_gui_text(gui, b'Slices: wheel moves; Ctrl+wheel zooms')
            self.dvz.dvz_gui_text(gui, b'3-D: left-drag orbits; wheel zooms')
        if self._slice_error is not None:
            self.dvz.dvz_gui_text(gui, f'Slice load failed: {self._slice_error}'.encode())

    def _create_view(self, *, offscreen: bool, title: str) -> None:
        super()._create_view(offscreen=offscreen, title=title)
        if offscreen:
            return
        self._input_router = self.dvz.dvz_gui_viewport_input(self.viewport)
        if not self._input_router:
            raise RuntimeError('dvz_view_input() failed')
        self._slice_input = SliceInputAdapter(self, self._input_router)
        self._input_callback = self._slice_input.callback
        self._slice_input.subscribe()
        self._input_subscription = self._slice_input.subscription

    def _pointer_figure_position(self, pointer) -> tuple[float, float] | None:
        """Retain the coordinate adapter for raw logical-window pointers."""
        adapter = self._slice_input or SliceInputAdapter(self, self._input_router)
        return adapter.pointer_figure_position(pointer)

    def close(self) -> None:
        """Guard and defer shutdown before releasing slice subscriptions or workers."""
        if getattr(self, '_closed', False):
            return
        # A failed constructor may have created a scheduler before base viewer
        # state exists. Fully initialized viewers must pass all mutation guards.
        if hasattr(self, '_closed'):
            self._require_open()
        if getattr(self, '_gui_callback_depth', 0):
            super().close()
            return
        for visual in getattr(self, '_contour_visuals', {}).values():
            visual.close()
        self._contour_visuals = {}
        self._accepted_contours = {}
        if getattr(self, '_auto_slice', None) is not None:
            self._auto_slice.close()
            self._auto_slice = None
        if getattr(self, '_slice_loader', None) is not None:
            self._slice_loader.close()
            self._slice_loader = None
        if getattr(self, '_slice_planes', None) is not None:
            self._slice_planes.close()
        if getattr(self, '_slice_input', None) is not None:
            self._slice_input.close()
            self._slice_input = None
            self._input_subscription = 0
            self._input_callback = None
        elif getattr(self, '_input_subscription', 0) and self._input_router:
            self.dvz.dvz_input_unsubscribe(self._input_router, self._input_subscription)
            self._input_subscription = 0
        super().close()

    def __del__(self) -> None:
        """Release slice workers and native resources as a last resort."""
        with suppress(Exception):
            LinkedAtlasNavigator.close(self)
