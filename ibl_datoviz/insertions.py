import logging

import datoviz as dvz
import numpy as np

from iblutil.util import Bunch

logger = logging.getLogger(__name__)

class InsertionModel:
    """
    Model for managing 3D insertions.

    Attributes
    ----------
    insertions: Bunch
        A Bunch object to store insertion data.
    visible_insertions: list
        A list of IDs of visible insertions.
    """

    def __init__(self):
        self.insertions = Bunch()
        self.visible_insertions = list()

    def show_insertion(self, pid: int | str) -> None:
        """
        Add an insertion to the visible insertions list.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to add.
        """
        if pid not in self.visible_insertions:
            self.visible_insertions.append(pid)

    def hide_insertion(self, pid: int | str) -> None:
        """
        Remove an insertion from the visible insertions list.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to remove.
        """
        if pid in self.visible_insertions:
            self.visible_insertions.remove(pid)

    def add_insertion(
            self,
            xyz: np.ndarray,
            pid: int | str,
            width: int,
            color: list | tuple | np.ndarray
    ) -> None:
        """
        Add an insertion to the model.

        Parameters
        ----------
        xyz: np.ndarray
            The coordinates of the insertion. Needs to at least have two coordinates for tip
            and base
        pid: int or str
            The ID of the insertion.
        width: int | np.ndarray
            The width of the insertion. Can either be a single width for the entire insertion
            or a width per point.
        color: list, tuple, or np.ndarray
            The color of the insertion as an RGBA array. Can either be a single color for the
            entire insertion or a color per point.
        """
        self.insertions[pid] = Bunch(xyz=xyz)
        self.set_width(pid, width)
        self.set_color(pid, color)

        self.visible_insertions.append(pid)

    def load_insertions(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """
        Load the visible insertions and prepare data for the view.

        Returns
        -------
        xyz: np.ndarray
            The coordinates of the visible insertions.
        colors: np.ndarray
            The colors of the visible insertions.
        widths: np.ndarray
            The widths of the visible insertions.
        n_groups: int
            The number of visible insertions (used for grouping in the view).
        """
        n_groups = len(self.visible_insertions)

        if n_groups == 0:
            # Return empty arrays if no insertions are visible
            return (
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 4), dtype=np.uint8),
                np.empty(0, dtype=np.float32),
                0
            )

        # Calculate total number of points
        total_points = sum(self.insertions[pid].xyz.shape[0] for pid in self.visible_insertions)

        # Preallocate arrays
        xyz = np.empty((total_points, 3), dtype=np.float32)
        colors = np.empty((total_points, 4), dtype=np.uint8)
        widths = np.empty(total_points, dtype=np.float32)

        # Fill arrays
        idx = 0
        for pid in self.visible_insertions:
            ins = self.insertions[pid]
            n_points = ins.xyz.shape[0]

            # Copy coordinates
            xyz[idx:idx + n_points] = ins.xyz

            # Handle colors (per-point or single color)
            if ins.color.ndim == 1:
                # Single color for entire insertion
                color = ins.color if ins.color.shape[0] == 4 else np.append(ins.color, 255)
                colors[idx:idx + n_points] = color
            # Per-point colors
            elif ins.color.shape[1] == 3:
                colors[idx:idx + n_points] = np.c_[ins.color, np.full(n_points, 255)]
            else:
                colors[idx:idx + n_points] = ins.color

            # Handle widths (per-point or single width)
            if ins.width.shape[0] == 1:
                # Single width for entire insertion
                widths[idx:idx + n_points] = ins.width[0]
            else:
                # Per-point widths
                widths[idx:idx + n_points] = ins.width

            idx += n_points

        return xyz, colors, widths, n_groups

    def set_width(self, pid: int | str, width: int | np.ndarray) -> None:
        """
        Set the width of an insertion.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to update.
        width: int or np.ndarray
            The new width of the insertion. Can either be a single width for the entire insertion
            or a width per point.
        """
        if pid in self.insertions:
            if isinstance(width, int | float):
                self.insertions[pid].width = np.array([width])
            else:
                width = np.array(width)
                assert width.shape[0] == self.insertions[pid].xyz.shape[0], \
                    ("Width array must have the same length as the number of points in the "
                     "insertion.")
                self.insertions[pid].width = width

    def set_color(self, pid: int | str, color: list | tuple | np.ndarray) -> None:
        """
        Set the color of an insertion.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to update.
        color:
            The new color of the insertion as an RGBA array. Can either be a single color for
            the entire insertion or a color per point.
        """
        if isinstance(color, list | tuple):
            color = np.array(color, dtype=np.uint8)

        if color.ndim == 1:
            assert color.shape[0] in (3, 4), "Color array must be given as RGB or RGBA."
            self.insertions[pid].color = color
        else:
            assert (color.shape[0] == self.insertions[pid].xyz.shape[0]
                    and color.shape[1] in (3, 4)), \
                ("Color array must have shape (N, 3) or (N, 4) where N is the number of points"
                 " in the insertion.")
            self.insertions[pid].color = color


class InsertionController:
    """
    Controller for managing 3D insertions.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the insertion coordinates.
    scale: float
        The scale factor to apply to the insertion coordinates.

    Attributes
    ----------
    model: InsertionModel
        The model for managing insertion data.
    view: InsertionView
        The view for displaying insertions.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray,
            scale: float = 200
    ):
        self.model = InsertionModel()
        self.view = InsertionView(app, panel, offset, scale)

    def add_insertions(self, xyzs, pids, widths, colors) -> None:
        """
        Add multiple insertions to the model and update the view.

        Parameters
        ----------
        xyzs: list of np.ndarray
            A list of coordinates for each insertion.
        pids: list of int or str
            A list of IDs for each insertion.
        widths: list of int or np.ndarray
            A list of widths for each insertion. Each width can either be a single width for the
            entire insertion or a width per point.
        colors: list of list, tuple, or np.ndarray
            A list of colors for each insertion. Each color can either be a single color for the
            entire insertion or a color per point.
        """
        for xyz, pid, width, color in zip(xyzs, pids, widths, colors, strict=False):
            self.model.add_insertion(xyz, pid, width, color)
        self.view.update_path(*self.model.load_insertions())

    def add_insertion(self, xyz, pid, width, color):
        """
        Add an insertion to the model and update the view.

        Parameters
        ----------
        xyz: np.ndarray
            The coordinates of the insertion. Needs to at least have two coordinates for tip
            and base
        pid: int or str
            The ID of the insertion.
        width: int or np.ndarray
        color: list, tuple, or np.ndarray
            The color of the insertion as an RGBA array. Can either be a single color for the
            entire insertion or a color per point.
        """
        self.model.add_insertion(xyz, pid, width, color)
        self.view.update_path(*self.model.load_insertions())

    def show_insertions(self, pids : list[int | str] | None = None) -> None:
        """
        Show a list of insertions.

        If no IDs are specified, shows all insertions that have been added to the model.

        Parameters
        ----------
        ids: list, optional
            A list IDs of insertions to show. If None, shows all insertions that have been added
            to the model. Default is None.
        """
        pids = pids or self.model.insertions.keys()

        for pid in pids:
            self.model.show_insertion(pid)
        self.view.update_path(*self.model.load_insertions())

    def show_insertion(self, pid: int | str) -> None:
        """
        Show an insertion.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to show.
        """
        self.model.show_insertion(pid)
        self.view.update_path(*self.model.load_insertions())

    def hide_insertions(self, pids: list[int | str] | None = None) -> None:
        """
        Hide a list of insertion.

        If no IDs are specified, hides all insertions that have been added to the model.

        Parameters
        ----------
        pids: list, optional
            A list of IDs of insertions to hide. If None, hides all insertions that have been
            added to the model. Default is None.
        """
        pids = pids or self.model.insertions.keys()
        for pid in pids:
            self.model.hide_insertion(pid)
        self.view.update_path(*self.model.load_insertions())

    def hide_insertion(self, pid: int | str) -> None:
        """
        Hide an insertion.

        Parameters
        ----------
        pid: int or str
            The ID of the insertion to hide.
        """
        self.model.hide_insertion(pid)
        self.view.update_path(*self.model.load_insertions())

    def set_width(self, width: int | np.ndarray, pid: int | str | None = None) -> None:
        """
        Set the width of an insertion.

        If no ID is specified, sets the width for all insertions that have been added to
        the model.

        If the width is given as an array it can only be set for a single insertion at a
        time, i.e the ID must be specified.

        Parameters
        ----------
        width: int or np.ndarray
            The new width of the insertion. Can either be a single width for the entire insertion
             or a width per point.
        pid: int or str, optional
            The ID of the insertion to update. If None, sets the width for all insertions
        """
        # TODO should we allow this?
        if not isinstance(width, int | float) and pid is None:
            raise ValueError("Width given as an array can only be set for a single insertion "
                             "at a time. Please specify the insertion ID.")

        if pid is None:
            for ins_id in self.model.insertions:
                self.model.set_width(ins_id, width)
            self.view.update_path(*self.model.load_insertions())
            return

        self.model.set_width(pid, width)
        self.view.update_path(*self.model.load_insertions())

    def set_color(self, color: list | tuple | np.ndarray, pid: int | str | None = None) -> None:
        """
        Set the color of an insertion.

        If no ID is specified, sets the color for all insertions that have been added to the
        model.

        If the color is given as an array it can only be set for a single insertion at a time,
        i.e the ID must be specified.

        Parameters
        ----------
        color: list, tuple, or np.ndarray
            The new color of the insertion as an RGBA array. Can either be a single color for
            the entire insertion or a color per point.
        pid: int or str, optional
            The ID of the insertion to update. If None, sets the color for all insertions
        """
        color = np.array(color)
        if color.ndim != 1 and pid is None:
            raise ValueError("Color given as an array can only be set for a single insertion "
                             "at a time. Please specify the insertion ID.")

        if pid is None:
            for ins_id in self.model.insertions:
                self.model.set_color(ins_id, color)
            self.view.update_path(*self.model.load_insertions())
            return

        self.model.set_color(pid, color)
        self.view.update_path(*self.model.load_insertions())

class InsertionView:
    """
    View for displaying 3D insertions.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the insertion coordinates.
    scale: float
        The scale factor to apply to the insertion coordinates.

    Attributes
    ----------
    path: datoviz._visual.Path
        The datoviz path visual for displaying insertions.
    visible: bool
        Whether the insertions are currently visible.
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
        # Add a dummy path to initialize
        self.path = self.app.path()
        self.path.set_position(np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32), groups=1)
        self.path.set_data(color=np.array([[0, 0, 0, 0], [0, 0, 0, 0]], dtype=np.uint8),
                           linewidth=np.array([1, 1]),
                           cap='round', join='round')
        self.panel.add(self.path)
        self.path.hide()
        self.visible = False

    def norm_pos(self, pos: np.ndarray) -> np.ndarray:
        """
        Normalize the insertion positions by applying the offset and scale.

        Parameters
        ----------
        pos: np.ndarray
            The coordinates of the insertions.

        Returns
        -------
        np.ndarray
            The normalized coordinates of the insertions.
        """
        return (pos - self.offset) * self.scale

    def update_path(
            self,
            position: np.ndarray,
            color: np.ndarray,
            width: np.ndarray,
            n_groups: int
    ) -> None:
        """
        Update the path visual with new insertion data.

        Parameters
        ----------
        position: np.ndarray
            The coordinates of the path points.
        color: np.ndarray
            The colors of the path points given as RGBA values.
        width: np.ndarray
            The widths of the path points.
        n_groups: int
            The number of individual path groups.
        """
        self.path.set_position(self.norm_pos(position), groups=n_groups)
        self.path.set_data(color=color, linewidth=width, cap='round', join='round')
        self.path.hide()
        self.path.show()
        self.visible = True
