import logging

import datoviz as dvz
import numpy as np

logger = logging.getLogger(__name__)


class PointsModel:
    """
    Model for managing 3D points.

    Attributes
    ----------
    xyz: np.ndarray
        The coordinates of the points.
    values: np.ndarray
        The values associated with the points (for coloring).
    colors: np.ndarray
        The colors of the points.
    alpha: np.ndarray
        The alpha (transparency) values of the points.
    sizes: np.ndarray
        The sizes of the points.
    cmap: str
        The colormap used for coloring the points.
    cmin: float
        The minimum value for the colormap.
    cmax: float
        The maximum value for the colormap.
    """

    def __init__(self):
        self.xyz: np.ndarray | None = None
        self.values: np.ndarray | None = None
        self.colors: np.ndarray | None = None
        self.alpha: np.ndarray | None = None
        self.sizes: np.ndarray | None = None
        self.cmap: str | None = None
        self.cmin: float | None = None
        self.cmax: float | None = None

    def add_points(
            self,
            xyz: np.ndarray,
            values: np.ndarray,
            sizes: np.ndarray | int = 3,
            cmap: str = 'Blues',
            cmin: float | None = None,
            cmax: float | None = None
    ) -> None:
        """
        Add points to the model.

        Parameters
        ----------
        xyz: np.ndarray
            The coordinates of the points.
        values: np.ndarray
            The values associated with the points (for coloring). Either can be given as a value
            per point or as a RGB(A) color per point.
        sizes: np.ndarray or int, optional
            The sizes of the points. Either can be given as a size per point or a single size for
            all points. Default is 3.
        cmap: str, optional
            The colormap to use for the points. Only used if values are given as a single value
            per point. Default is 'Blues'.
        cmin: float, optional
            The minimum value for the colormap. Only used if values are given as a single value
            per point. Default is None.
        cmax: float, optional
            The maximum value for the colormap. Only used if values are given as a single value
            per point. Default is None.
        """
        self.xyz = np.ascontiguousarray(xyz, dtype=np.float32)
        self.values = np.ascontiguousarray(values)
        self.set_size(sizes)
        if values.ndim == 1:
            self.cmap = cmap
            self.cmin = cmin or np.nanmin(self.values)
            self.cmax = cmax or np.nanmax(self.values)
        self.set_values(values)

    def set_values(self, values: np.ndarray) -> None:
        """
        Set the values for the points.

        Parameters
        ----------
        values: The values associated with the points (for coloring). Either can be given as a
            value per point or as a RGB(A) color per point.
        """
        self.values = values

        if values.ndim == 1:
            assert values.shape[0] == self.xyz.shape[0], \
                "Values array must have the same length as the number of points."
            self.compute_colors()
        else:
            assert values.shape[0] == self.xyz.shape[0] and values.shape[1] in (3, 4), \
                "Color array must have shape (N, 3) or (N, 4) where N is the number of points."
            if values.shape[1] == 3:
                self.colors = np.c_[values, np.ones(values.shape[0]) * 255]
            else:
                self.colors = values

    def set_clevels(self, cmin: float | None = None, cmax: float| None = None) -> None:
        """
        Set the color levels for the points.

        If cmin or cmax is None, the min max values from the current values array will be used.

        Parameters
        ----------
        cmin: float, optional
            The minimum value for the colormap.
        cmax: float, optional
            The maximum value for the colormap.
        """
        if self.values.ndim != 1:
            raise ValueError("Color levels can only be set when values are given as a "
                             "single value per point.")

        self.cmin = cmin or np.nanmin(self.values)
        self.cmax = cmax or np.nanmax(self.values)
        self.compute_colors()

    def set_cmap(self, cmap: str) -> None:
        """
        Set the colormap for the points.

        Parameters
        ----------
        cmap: str
            A datoviz colormap name.
        """
        if self.values.ndim != 1:
            raise ValueError("Colormap can only be set when values are given as a single value "
                             "per point.")

        self.cmap = cmap
        self.compute_colors()

    def compute_colors(self) -> None:
        """Compute the colors for the points based on their values and the colormap and levels."""
        self.colors = dvz.cmap(self.cmap, self.values, self.cmin, self.cmax)
        # norm = colors.Normalize(vmin=self.cmin, vmax=self.cmax, clip=True)
        # cmap = matplotlib.colormaps[self.cmap]
        # self.colors = (cmap(norm(self.values)) * 255).astype(np.uint8)
        if self.alpha is not None:
            self.colors[:, 3] = self.alpha

    def set_size(self, sizes: int | float | np.ndarray) -> None:
        """
        Set the sizes of the points.

        Parameters
        ----------
        sizes: np.ndarray or int
            The sizes of the points. Either can be given as a size per point or a single
            size for all points.
        """
        if isinstance(sizes, int | float):
            self.sizes = np.full(self.xyz.shape[0], sizes, dtype=np.float32)
        else:
            assert sizes.shape[0] == self.xyz.shape[0], \
                "Size array must have the same length as the number of points."
            self.sizes = sizes.astype(np.float32)

    def set_alpha(self, alpha: np.ndarray | int) -> None:
        """
        Set the alpha (transparency) of the points.

        Parameters
        ----------
        alpha: np.ndarray or int
            The alpha values of the points. Either can be given as an alpha per point or a single
            alpha for all points.
        """
        if isinstance(alpha, int):
            self.alpha = np.full(self.xyz.shape[0], alpha, dtype=np.uint8)
            self.colors[:, 3] = self.alpha
        else:
            assert alpha.size == self.xyz.shape[0], \
                "Alpha array must have the same length as the number of points."
            self.alpha = alpha.astype(np.uint8)
            self.colors[:, 3] = alpha


class PointsController:
    """
    Controller for managing 3D points.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the point coordinates.
    scale: float, optional
        The scale factor to apply to the point coordinates. Default is 200.

    Attributes
    ----------
    model: PointsModel
        The model for managing point data.
    view: PointsView
        The view for displaying points.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray,
            scale: float = 200
    ):
        self.model = PointsModel()
        self.view = PointsView(app, panel, offset, scale)

    def add_points(
            self,
            xyz: np.ndarray,
            values: np.ndarray,
            sizes: np.ndarray | int | float = 3,
            cmap: str = 'Blues',
            cmin: float | None = None,
            cmax: float | None = None
    ) -> None:
        """
        Add points to the model and update the view.

        Parameters
        ----------
        xyz: np.ndarray
            The coordinates of the points.
        values: np.ndarray
            The values associated with the points (for coloring). Either can be given as a value
            per point or as a RGB(A) color per point.
        sizes: np.ndarray or int, optional
            The sizes of the points. Either can be given as a size per point or a single size
            for all points. Default is 3.
        cmap: str, optional
            The colormap to use for the points. Only used if values are given as a single
            value per point. Default is 'Blues'.
        cmin: float, optional
            The minimum value for the colormap. Only used if values are given as a single
            value per point. Default is None.
        cmax: float, optional
            The maximum value for the colormap. Only used if values are given as a single
            value per point. Default is None.
        """
        self.model.add_points(xyz, values, sizes, cmap=cmap, cmin=cmin, cmax=cmax)
        self.view.update_points(self.model.xyz, self.model.sizes, self.model.colors)

    def set_cmap(self, cmap: str) -> None:
        """
        Set the colormap for the points and update the view.

        Parameters
        ----------
        cmap: str
            A datoviz colormap name.
        """
        self.model.set_cmap(cmap)
        self.view.update_colors(self.model.colors)

    def set_clevels(self, cmin: float | None = None, cmax: float | None = None) -> None:
        """
        Set the color levels for the points and update the view.

        Parameters
        ----------
        cmin: float, optional
            The minimum value for the colormap.
        cmax: float, optional
            The maximum value for the colormap.
        """
        self.model.set_clevels(cmin, cmax)
        self.view.update_colors(self.model.colors)

    def set_values(self, values: np.ndarray) -> None:
        """
        Set the values for the points and update the view.

        Parameters
        ----------
        values: np.ndarray
            The values associated with the points (for coloring). Either can be given as a
            value per point or as a RGB(A) color per point.
        """
        self.model.set_values(values)
        self.view.update_colors(self.model.colors)

    def set_size(self, sizes: int | float | np.ndarray) -> None:
        """
        Set the sizes of the points and update the view.

        Parameters
        ----------
        sizes: int or np.ndarray
            The sizes of the points. Either can be given as a size per point or a single size
            for all points.
        """
        self.model.set_size(sizes)
        self.view.update_sizes(self.model.sizes)

    def set_alpha(self, alpha: int | np.ndarray) -> None:
        """
        Set the alpha (transparency) of the points and update the view.

        Parameters
        ----------
        alpha: int or np.ndarray
            The alpha values of the points. Either can be given as an alpha per point or a single
            alpha for all points.
        """
        self.model.set_alpha(alpha)
        self.view.update_colors(self.model.colors)

    def hide_points(self) -> None:
        """Hide the points in the view."""
        self.view.hide_points()

    def show_points(self) -> None:
        """Show the points in the view."""
        self.view.show_points()

    def remove_points(self) -> None:
        """Remove all points from the view and reset the model."""
        self.view.reset_points()
        self.model = PointsModel()

class PointsView:
    """
    View for displaying 3D points.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the point coordinates.
    scale: float
        The scale factor to apply to the point coordinates.

    Attributes
    ----------
    points: datoviz._visual.Points
        The datoviz points visual.
    visible: bool
        Whether the points are currently visible.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray,
            scale: float
    ):
        self.app = app
        self.panel = panel
        self.offset = offset
        self.scale = scale
        # Add a dummy point to initialize
        self.points = self.app.point(depth_test=True,
                                     position=np.array([[0, 0, 0]], dtype=np.float32),
                                     color=np.array([[0, 0, 0, 0]], dtype=np.uint8)
                                     )
        self.panel.add(self.points)
        self.points.hide()
        self.visible = False

    def reset_points(self) -> None:
        """Reset the points visual to an empty state."""
        self.points.set_data(
            position=np.array([[0, 0, 0]], dtype=np.float32),
            color=np.array([[0, 0, 0, 0]], dtype=np.uint8)
        )
        self.points.hide()
        self.visible = False

    def norm_pos(self, pos: np.ndarray) -> np.ndarray:
        """
        Normalize the point positions by applying the offset and scale.

        Parameters
        ----------
        pos: np.ndarray
            The coordinates of the points.

        Returns
        -------
        np.ndarray
            The normalized coordinates of the points.
        """
        return (pos - self.offset) * self.scale

    def update_points(self, xyz: np.ndarray, sizes: np.ndarray, colors: np.ndarray) -> None:
        """
        Update the points in the view.

        Parameters
        ----------
        xyz: np.ndarray
            The coordinates of the points.
        sizes: np.ndarray
            The sizes of the points.
        colors: np.ndarray
            The colors of the points given as RGBA values.
        """
        self.points.set_data(
            position=self.norm_pos(xyz),
            size=sizes,
            color=colors
        )

        self.points.hide()
        self.points.show()
        self.visible = True

    def show_points(self) -> None:
        """Show the points in the view."""
        if not self.visible:
            self.points.show()
            self.visible = True

    def hide_points(self):
        """Hide the points in the view."""
        if self.visible:
            self.points.hide()
            self.visible = False

    def update_colors(self, colors: np.ndarray) -> None:
        """
        Update the colors of the points in the view.

        Parameters
        ----------
        colors: np.ndarray
            The new colors of the points given as RGBA values.
        """
        self.points.set_color(colors)

    def update_sizes(self, sizes: np.ndarray) -> None:
        """
        Update the sizes of the points in the view.

        Parameters
        ----------
        sizes: np.ndarray
            The new sizes of the points.
        """
        self.points.set_size(sizes)
