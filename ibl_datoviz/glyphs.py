import logging

import datoviz as dvz
from iblutil.util import Bunch
import numpy as np

logger = logging.getLogger(__name__)


class TextModel:
    """
    Model for managing 3D text labels.

    Attributes
    ----------
    texts: Bunch
        A Bunch object to store text label data, keyed by text id.
    visible_texts: list
        A list of IDs of visible text labels.
    """

    def __init__(self):
        self.texts = Bunch()
        self.visible_texts = list()

    def show_text(self, text_id: int | str) -> None:
        """
        Add a text label to the visible texts list.

        Parameters
        ----------
        text_id: int or str
            The ID of the text label to add.
        """
        if text_id not in self.visible_texts:
            self.visible_texts.append(text_id)

    def hide_text(self, text_id: int | str) -> None:
        """
        Remove a text label from the visible texts list.

        Parameters
        ----------
        text_id: int or str
            The ID of the text label to remove.
        """
        if text_id in self.visible_texts:
            self.visible_texts.remove(text_id)

    def add_text(
            self,
            text_id: int | str,
            text: str,
            position: np.ndarray,
            color: list | tuple | np.ndarray,
            scale: float
    ) -> None:
        """
        Add a text label to the model.

        Parameters
        ----------
        text_id: int or str
            The ID of the text label.
        text: str
            The string to render.
        position: np.ndarray
            The 3D position of the text label.
        color: list, tuple, or np.ndarray
            The color of the text label as an RGB or RGBA array, shared by all of its
            characters.
        scale: float
            The scale factor of the text label.
        """
        color = np.asarray(color, dtype=np.uint8)
        assert color.shape[-1] in (3, 4), "Color array must be given as RGB or RGBA."
        if color.shape[-1] == 3:
            color = np.append(color, 255).astype(np.uint8)

        self.texts[text_id] = Bunch(
            text=text,
            position=np.asarray(position, dtype=np.float32),
            color=color,
            scale=scale
        )
        self.visible_texts.append(text_id)

    def load_text(self) -> tuple[list, np.ndarray, np.ndarray, np.ndarray]:
        """
        Load the visible text labels and prepare data for the view.

        Returns
        -------
        strings: list of str
            The strings of the visible text labels.
        positions: np.ndarray
            The positions of the visible text labels.
        colors: np.ndarray
            The per-character colors of the visible text labels.
        scales: np.ndarray
            The per-string scales of the visible text labels.
        """
        if not self.visible_texts:
            return (
                list(),
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 4), dtype=np.uint8),
                np.empty(0, dtype=np.float32)
            )

        strings = list()
        positions = list()
        colors = list()
        scales = list()
        for text_id in self.visible_texts:
            info = self.texts[text_id]
            strings.append(info.text)
            positions.append(info.position)
            colors.append(np.tile(info.color, (len(info.text), 1)))
            scales.append(info.scale)

        positions = np.ascontiguousarray(np.vstack(positions), dtype=np.float32)
        colors = np.ascontiguousarray(np.vstack(colors), dtype=np.uint8)
        scales = np.ascontiguousarray(np.hstack(scales), dtype=np.float32)

        return strings, positions, colors, scales


class TextController:
    """
    Controller for managing 3D text labels.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the text positions.
    scale: float, optional
        The scale factor to apply to the text positions. Default is 200.

    Attributes
    ----------
    model: TextModel
        The model for managing text label data.
    view: TextView
        The view for displaying text labels.
    """

    def __init__(
            self,
            app: dvz._app.App,
            panel: dvz._panel.Panel,
            offset: np.ndarray,
            scale: float = 200
    ):
        self.model = TextModel()
        self.view = TextView(app, panel, offset, scale)

    def add_text(
            self,
            text: str,
            position: np.ndarray,
            color: list | tuple | np.ndarray,
            size: float,
            text_id: int | str | None = None
    ) -> None:
        """
        Add a text label to the model and update the view.

        Parameters
        ----------
        text: str
            The string to render.
        position: np.ndarray
            The 3D position of the text label.
        color: list, tuple, or np.ndarray
            The color of the text label as an RGB or RGBA array.
        size: float
            The scale factor of the text label.
        text_id: int or str, optional
            The ID of the text label, used to show/hide it later. If None, the text string
            itself is used as the ID. Default is None.
        """
        text_id = text if text_id is None else text_id
        self.model.add_text(text_id, text, position, color, size)
        self.view.update_text(*self.model.load_text())

    def add_texts(
            self,
            texts: list[str],
            positions: list | np.ndarray,
            colors: list,
            sizes: list | np.ndarray,
            text_ids: list | None = None
    ) -> None:
        """
        Add multiple text labels to the model and update the view.

        Parameters
        ----------
        texts: list of str
            The strings to render.
        positions: list of np.ndarray
            The 3D position of each text label.
        colors: list of list, tuple, or np.ndarray
            The color of each text label as an RGB or RGBA array.
        sizes: list of float
            The scale factor of each text label.
        text_ids: list of int or str, optional
            The IDs of each text label, used to show/hide them later. If None, the text
            strings themselves are used as IDs. Default is None.
        """
        text_ids = texts if text_ids is None else text_ids
        for text_id, text, position, color, size in zip(
                text_ids, texts, positions, colors, sizes, strict=False):
            self.model.add_text(text_id, text, position, color, size)
        self.view.update_text(*self.model.load_text())

    def show_texts(self, text_ids: list | None = None) -> None:
        """
        Show a list of text labels.

        If no IDs are specified, shows all text labels that have been added to the model.

        Parameters
        ----------
        text_ids: list, optional
            A list of IDs of text labels to show. If None, shows all text labels that have
            been added to the model. Default is None.
        """
        text_ids = text_ids or self.model.texts.keys()
        for text_id in text_ids:
            self.model.show_text(text_id)
        self.view.update_text(*self.model.load_text())

    def show_text(self, text_id: int | str) -> None:
        """
        Show a text label.

        Parameters
        ----------
        text_id: int or str
            The ID of the text label to show.
        """
        self.model.show_text(text_id)
        self.view.update_text(*self.model.load_text())

    def hide_texts(self, text_ids: list | None = None) -> None:
        """
        Hide a list of text labels.

        If no IDs are specified, hides all text labels that have been added to the model.

        Parameters
        ----------
        text_ids: list, optional
            A list of IDs of text labels to hide. If None, hides all text labels that have
            been added to the model. Default is None.
        """
        text_ids = text_ids or self.model.texts.keys()
        for text_id in text_ids:
            self.model.hide_text(text_id)
        self.view.update_text(*self.model.load_text())

    def hide_text(self, text_id: int | str) -> None:
        """
        Hide a text label.

        Parameters
        ----------
        text_id: int or str
            The ID of the text label to hide.
        """
        self.model.hide_text(text_id)
        self.view.update_text(*self.model.load_text())


class TextView:
    """
    View for displaying 3D text labels.

    Parameters
    ----------
    app: datoviz._app.App
        The datoviz application instance.
    panel: datoviz._panel.Panel
        The datoviz panel instance.
    offset: np.ndarray
        The offset to apply to the text positions.
    scale: float
        The scale factor to apply to the text positions.

    Attributes
    ----------
    text: datoviz.visuals.Glyph
        The datoviz glyph visual for displaying text labels.
    visible: bool
        Whether the text labels are currently visible.
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
        # Add a dummy glyph to initialize
        self.text = self.app.glyph(font_size=15)
        self.text.set_strings(
            ['l'],
            string_pos=np.array([[0, 0, 0]], dtype=np.float32),
            scales=np.array([1], dtype=np.float32),
            color=(0, 0, 0, 0)
        )
        self.panel.add(self.text)
        self.text.hide()
        self.visible = False

    def norm_pos(self, pos: np.ndarray) -> np.ndarray:
        """
        Normalize the text positions by applying the offset and scale.

        Parameters
        ----------
        pos: np.ndarray
            The coordinates of the text labels.

        Returns
        -------
        np.ndarray
            The normalized coordinates of the text labels.
        """
        return (pos - self.offset) * self.scale

    def update_text(
            self,
            strings: list,
            positions: np.ndarray,
            colors: np.ndarray,
            scales: np.ndarray
    ) -> None:
        """
        Update the text labels in the view.

        Parameters
        ----------
        strings: list of str
            The strings of the visible text labels.
        positions: np.ndarray
            The positions of the visible text labels.
        colors: np.ndarray
            The per-character colors of the visible text labels.
        scales: np.ndarray
            The per-string scales of the visible text labels.
        """
        if not strings:
            # datoviz's Glyph.set_strings requires a non-empty list, so just hide the
            # visual entirely when there is nothing left to show.
            self.text.hide()
            self.visible = False
            return

        self.text.set_strings(strings, string_pos=self.norm_pos(positions), scales=scales)
        self.text.set_color(colors)
        self.text.hide()
        self.text.show()
        self.visible = True
