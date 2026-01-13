import logging

import datoviz as dvz
import numpy as np
import trimesh

from iblatlas.atlas import AllenAtlas
from iblutil.util import Bunch
from one.remote import aws

logger = logging.getLogger(__name__)


def download_glb_file():
    """Download the Allen brain region meshes GLB file if not already cached."""
    file_path = AllenAtlas._get_cache_dir().joinpath('meshes.glb')
    if not file_path.exists():
        file_path.parent.mkdir(exist_ok=True, parents=True)
        aws.s3_download_file(f'atlas/{file_path.name}', file_path)
    return file_path


class BrainMeshModel:
    """
    Model for Allen brain region meshes.

    Parameters
    ----------
    ba: AllenAtlas, optional
        An instance of the AllenAtlas class. If None, a new instance will be created.

    Attributes
    ----------
    regions: Bunch
        A Bunch object to store loaded brain regions.
    ba: AllenAtlas
        An instance of the AllenAtlas class.
    meshes: trimesh.Scene
        A trimesh scene containing the brain region meshes.
    """

    def __init__(self, ba: AllenAtlas | None = None):

        self.regions = Bunch()
        self.ba = ba or AllenAtlas()
        self.meshes = trimesh.load_scene(download_glb_file())

    def load_mesh(
            self,
            region_id: int,
            hemisphere: str = 'both'
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Load the mesh for a given brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to load.
        hemisphere: str, optional
            The hemisphere to load ('left', 'right', or 'both'). Default is 'both'

        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray]
            A tuple containing:
            - mesh_pos: np.ndarray
                The vertices of the mesh in IBL coordinates.
            - mesh_idx: np.ndarray
                The faces of the mesh.
            - mesh_color: np.ndarray
                The vertex colors of the mesh.
        """
        mesh = self.meshes.geometry[f'{region_id}.obj']
        color = mesh.visual.vertex_colors[0]

        # If hemisphere is specified, slice the mesh accordingly
        if hemisphere != 'both':
            # TODO see if there is a better way to slice
            # Plane to slice the mesh, in CCF coordinates
            plane_origin = self.ba.xyz2ccf([0, 0, 0], ccf_order='apdvml')
            # Update the ml dividing line as the origin is from the 25um atlas
            plane_origin[2] = 5695
            plane_normal = np.array([0.0, 0.0, -1.0]) if hemisphere == 'left' \
                else np.array([0.0, 0.0, 1.0])

            mesh = mesh.slice_plane(
                plane_origin=plane_origin,
                plane_normal=plane_normal,
                cap=True
            )
            mesh.merge_vertices()

        # Vertices, convert to IBL coordinates
        mesh_pos = self.ba.ccf2xyz(mesh.vertices, ccf_order='apdvml')
        mesh_pos = np.ascontiguousarray(mesh_pos, dtype=np.float32)
        # Faces
        mesh_idx = np.ascontiguousarray(mesh.faces.ravel(), dtype=np.uint32)
        # Colors
        mesh_color = np.ascontiguousarray(np.tile(color,
                                                  (mesh_pos.shape[0], 1)).astype(np.uint8))

        self.regions[region_id] = Bunch(hemisphere=hemisphere, color=color)

        return mesh_pos, mesh_idx, mesh_color

    def load_color(self, region_id: int) -> np.ndarray | None:
        """
        Load the default color for a given brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region.

        Returns
        -------
        np.ndarray
            The default color of the brain region as an RGBA array. None if region not loaded.
        """
        if (region := self.regions.get(region_id)) is not None:
            return region.color

    def remove_region(self, region_id: int) -> None:
        """
        Remove a brain region from the model.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to remove.
        """
        if region_id in self.regions:
            del self.regions[region_id]


class BrainMeshController:
    """
    Controller for managing Allen brain region meshes.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray, optional
        The offset to apply to the brain region mesh vertices. If None, the mean position of the
        root brain region will be used.
    scale: float, optional
        The scale factor to apply to the brain region mesh vertices. Default is 200.
    model: BrainMeshModel, optional
        An instance of the BrainMeshModel class. If None, a new instance will be created

    Attributes
    ----------
    model: BrainMeshModel
        The model for managing brain region meshes.
    view: BrainMeshView
        The view for displaying brain region meshes.
    lookup: dict
        A cache for region acronym to Allen ID lookups.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray | None = None,
            scale: float = 200,
            model: BrainMeshModel | None = None
    ):

        self.model = model or BrainMeshModel()
        if offset is None:
            offset = self.model.load_mesh(997)[0].mean(axis=0)
        self.view = BrainMeshView(app, panel, offset, scale)
        self.lookup = {}

    def get_region_id(self, region: int | str | list[int | str]) -> int | list[int]:
        """
        Get the Allen ID for a given brain region acronym or ID.

        Store the lookups in a cache to avoid repeated calls.

        Parameters
        ----------
        region: int, str, or list
            The Allen ID(s) or acronym(s) of the brain region(s).

        Returns
        -------
        int or list[int]
            The Allen ID(s) of the brain region(s).
        """
        def _get_region(r: int | str) -> int:
            if isinstance(r, str):
                if r not in self.lookup:
                    region_id = self.model.ba.regions.acronym2id(r)
                    if len(region_id) == 0:
                        raise ValueError(f"Region acronym '{r}' not found in atlas.")
                    self.lookup[r] = region_id[0]
                return self.lookup[r]
            else:
                return region

        if isinstance(region, list):
            region_ids = []
            for reg in region:
                region_ids.append(_get_region(reg))
            return region_ids
        else:
            return _get_region(region)


    def loaded_regions(self, exclude_root=False) -> list[int]:
        """
        Get a list of currently loaded brain region IDs.

        Parameters
        ----------
        exclude_root: bool, optional
            Whether to exclude the root region (997) from the list. Default is True.

        Returns
        -------
        regions: list[int]
            A list of Allen IDs for the currently loaded brain regions, excluding the root
            region (997).
        """
        regions = self.view.regions.keys()
        if exclude_root:
            regions = [r for r in regions if r != 997]
        return regions

    @property
    def visible_regions(self) -> list[int]:
        """
        Get a list of currently visible brain region IDs.

        Returns
        -------
        list[int]
            A list of Allen IDs for the currently visible brain regions.
        """
        return [k for k, v in self.view.regions.items() if v.visible]

    def add_root(self):
        """Add the root brain region."""
        self.add_region(997, hemisphere='both')
        self.set_alpha(30, 997)

    def add_region(self, region: int | str, hemisphere: str = 'both') -> None:
        """
        Add a brain region.

        Parameters
        ----------
        region: int or str
            The Allen ID or acronym of the brain region to show.
        hemisphere: str, optional
            The hemisphere to show ('left', 'right', or 'both'). Default is 'both'
        """
        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            self.view.add_region(region_id, *self.model.load_mesh(region_id, hemisphere))
        else:
            self.view.show_region(region_id)

    def add_regions(self, regions: list[int | str], hemisphere: str = 'both') -> None:
        """
        Add multiple brain regions.

        Parameters
        ----------
        regions: list
            A list of Allen IDs or acronyms of the brain regions to show.
        hemisphere: str, optional
            The hemisphere to show ('left', 'right', or 'both'). Default is 'both'
        """
        # Root should always be added last to avoid hiding other regions
        region_ids = self.get_region_id(regions)
        if 997 in list(region_ids):
            region_ids.remove(997)
            logger.info("Use add_root() to add the root brain region separately.")

        for region_id in region_ids:
            self.add_region(region_id, hemisphere=hemisphere)

    def show_region(self, region: int | str) -> None:
        """
        Show a brain region.

        Parameters
        ----------
        region: int or str
            The Allen ID or acronym of the brain region to show.
        """
        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot show region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return
        self.view.show_region(region_id)

    def show_regions(self, regions: list[int | str] | None = None) -> None:
        """
        Show multiple brain regions.

        If no regions are specified, shows all loaded regions.

        Parameters
        ----------
        regions: list
            A list of Allen IDs or acronyms of the brain regions to show. If None, shows all
            loaded regions. Default is None.
        """
        regions = regions or self.loaded_regions()
        for region in regions:
            self.show_region(region)

    def hide_region(self, region: int | str) -> None:
        """
        Hide a brain region.

        Parameters
        ----------
        region: int or str
            The Allen ID or acronym of the brain region to update.
        """
        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot hide region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return
        self.view.hide_region(region_id)

    def hide_regions(self, regions: list[int | str] | None = None) -> None:
        """
        Hide multiple brain regions.

        If no regions are specified, hides all loaded regions.

        Parameters
        ----------
        regions: list
            A list of Allen IDs or acronyms of the brain regions to hide. If None, hides
            all loaded regions. Default is None.
        """
        regions = regions or self.loaded_regions(exclude_root=True)
        for region in regions:
            self.hide_region(region)

    def remove_region(self, region: int | str) -> None:
        """
        Remove a brain region.

        Deletes region from both model and view to free up memory.

        Parameters
        ----------
        region: int or str
            The Allen ID or acronym of the brain region to show.
        """
        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot remove region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return
        self.view.remove_region(region_id)
        self.model.remove_region(region_id)

    def remove_regions(self, regions: list[int | str] | None = None) -> None:
        """
        Remove multiple brain regions.

        If no regions are specified, removes all loaded regions.

        Parameters
        ----------
        regions: list, optional
            A list of Allen IDs or acronyms of the brain regions to remove. If None,
            removes all loaded regions. Default is None.
        """
        regions = regions or self.loaded_regions(exclude_root=True)
        for region_id in regions:
            self.remove_region(region_id)

    def set_color(self, color: list | tuple | np.ndarray,
                  region: int | str | None = None) -> None:
        """
        Set the color of a brain region.

        If no region is specified, updates all loaded regions with the given color.

        Parameters
        ----------
        color:
            The new color as an RGB or RGBA array.
        region: int or str, optional
            The Allen ID or acronym of the brain region to update. If None, updates all
            loaded regions. Default is None.
        """
        if len(color) == 3:
            color = np.hstack((color, [255])).astype(np.uint8)
        else:
            color = np.array(color, dtype=np.uint8)

        if region is None:
            for region_id in self.loaded_regions(exclude_root=True):
                self.view.update_color(region_id, color)
            return

        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot update region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return

        self.view.update_color(region_id, color)

    def set_alpha(self, alpha: int, region: int | str | None = None) -> None:
        """
        Set the alpha (transparency) of a brain region.

        If no region is specified, updates all loaded regions with the given alpha.

        Parameters
        ----------
        alpha: int
            The new alpha value (0-255).
        region: int or str, optional
            The Allen ID or acronym of the brain region to update. If None, updates all loaded
            regions. Default is None.
        """
        if region is None:
            for region_id in self.loaded_regions(exclude_root=True):
                self.view.update_alpha(region_id, alpha)
            return

        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot update region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return
        self.view.update_alpha(region_id, alpha)

    def reset_color(self, region: int | str | None = None) -> None:
        """
        Reset the color of a brain region to its default.

        If no region is specified, resets all loaded regions to their default colors.

        Parameters
        ----------
        region: int or str, optional
            The Allen ID or acronym of the brain region to update.If None, resets all loaded
            regions. Default is None.
        """
        if region is None:
            for region_id in self.loaded_regions():
                color = self.model.load_color(region_id)
                self.view.update_color(region_id, color)
            return

        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot reset region {region} as it is not loaded. To load it, "
                           f"use add_region() first.")
            return
        color = self.model.load_color(region_id)
        self.view.update_color(region_id, color)

    def set_hemisphere(self, hemisphere: str, region: int | str | None = None) -> None:
        """
        Set the hemisphere visibility of a brain region.

        If no region is specified, sets all loaded regions to the given hemisphere.

        Parameters
        ----------
        hemisphere: str
            The hemisphere to show ('left', 'right', or 'both').
        region: int or str, optional
            The Allen ID or acronym of the brain region to update. If None, updates all loaded
            regions. Default is None.
        """
        if region is None:
            for region_id in self.loaded_regions(exclude_root=True):
                self.view.update_hemisphere(region_id,
                                            *self.model.load_mesh(region_id, hemisphere)[0:-1])
            return

        region_id = self.get_region_id(region)
        if region_id not in self.loaded_regions():
            logger.warning(f"Cannot update region {region} as it is not loaded. "
                           f"To load it, use add_region() first.")
            return

        self.view.update_hemisphere(region_id, *self.model.load_mesh(region_id, hemisphere)[0:-1])


class BrainMeshView:
    """
    View for displaying Allen brain region meshes.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the brain region mesh vertices.
    scale: float
        The scale factor to apply to the brain region mesh vertices.

    Attributes
    ----------
    regions: Bunch
        A Bunch object to store brain region visuals and their properties.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray,
            scale: float
    ):

        # TODO look into recycling visuals to save memory/ using shape collection
        self.regions = Bunch()
        self.offset = offset
        self.app = app
        self.panel = panel
        self.scale = scale

    def norm_pos(self, pos):
        """
        Normalize the brain region mesh vertices by applying the offset and scale.

        Parameters
        ----------
        pos: np.ndarray
            The vertices of the brain region mesh.

        Returns
        -------
        np.ndarray
            The normalized vertices of the brain region mesh.
        """
        return (pos - self.offset) * self.scale

    def remove_root(self):
        """Remove the root brain region from the panel."""
        region = self.regions.get(997, None)
        if region is not None:
            self.panel.remove(region.visual)

    def add_root(self):
        """Add the root brain region to the panel."""
        region = self.regions.get(997, None)
        if region is not None:
            self.panel.add(region.visual)
            if region.visible:
                region.visual.show()
            else:
                region.visual.hide()

    def add_region(
            self,
            region_id: int,
            vertices: np.ndarray,
            faces: np.ndarray,
            colors: np.ndarray,
    ) -> None:
        """
        Add a brain region mesh to the panel.

        If root region is already present, it is temporarily removed to ensure correct
        rendering order.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region.
        vertices: np.ndarray
            The vertices of the mesh.
        faces: np.ndarray
            The faces of the mesh.
        colors: np.ndarray
            The vertex colors of the mesh.
        """
        if self.regions.get(region_id) is not None:
            return

        if region_id != 997:
            self.remove_root()
        visual = self.app.mesh(indexed=True, lighting=True, cull='back')

        visual.set_data(
            position=self.norm_pos(vertices),
            color=colors,
            index=faces,
            compute_normals=True,
        )

        self.regions[region_id] = Bunch(
            visual=visual,
            visible=True,
            color=colors[0])

        self.panel.add(visual)
        if region_id != 997:
            self.add_root()

        visual.hide()
        visual.show()

    def show_region(self, region_id: int) -> None:
        """
        Show a brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to show.
        """
        if (region := self.regions.get(region_id)) is None:
            return
        if not region.visible:
            region.visual.show()
            region.visible = True

    def hide_region(self, region_id: int) -> None:
        """
        Hide a brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to hide.
        """
        if (region := self.regions.get(region_id)) is None:
            return
        if region.visible:
            region.visual.hide()
            region.visible = False

    def remove_region(self, region_id: int) -> None:
        """
        Remove a brain region from the panel and destroy its visual.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to remove.
        """
        if (region := self.regions.get(region_id)) is None:
            return

        self.panel.remove(region.visual)
        del region.visual
        # TODO figure out what should be done to properly free resources on datoviz side
        # region.visual.destroy()
        del self.regions[region_id]

    def update_alpha(self, region_id: int, alpha: int) -> None:
        """
        Update the alpha (transparency) of a brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to update.
        alpha: int
            The new alpha value (0-255).
        """
        if (region := self.regions.get(region_id)) is None:
            return
        region.color[3] = alpha
        region.visual.set_color(np.tile(region.color,
                                        (region.visual.count, 1)).astype(np.uint8))

    def update_color(self, region_id: int, color: np.ndarray) -> None:
        """
        Update the color of a brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to update.
        color: np.ndarray
            The new color as an RGBA array.
        """
        if (region := self.regions.get(region_id)) is None:
            return

        region.color = color
        region.visual.set_color(np.tile(region.color,
                                        (region.visual.count, 1)).astype(np.uint8))

    def update_hemisphere(self, region_id: int, vertices: np.ndarray, faces: np.ndarray) -> None:
        """
        Update the hemisphere visibility of a brain region.

        Parameters
        ----------
        region_id: int
            The Allen ID of the brain region to update.
        vertices: np.ndarray
            The vertices of the mesh.
        faces: np.ndarray
            The faces of the mesh.
        """
        if (region := self.regions.get(region_id)) is None:
            return

        region.visual.set_data(
            position=self.norm_pos(vertices),
            color=np.tile(region.color, (vertices.shape[0], 1)).astype(np.uint8),
            index=faces,
            compute_normals=True,
        )
