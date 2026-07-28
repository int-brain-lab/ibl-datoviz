import logging

import datoviz as dvz
from iblutil.util import Bunch
import numpy as np

logger = logging.getLogger(__name__)


class TextModel:
    """
    Model for managing 3D text labels.
    """
    def __init__(self):
        self.texts = list()

    def add_text(self, text: str, position: np.ndarray, color: np.ndarray, scale: float) -> None:
        info = Bunch(
            text=text,
            position=position,
            color=color,
            scale=scale
        )
        self.texts.append(info)

    def load_text(self):

        strings = list()
        positions = list()
        colors = list()
        scales = list()
        for text in self.texts:
            strings.append(text.text)
            positions.append(text.position)
            colors.append([text.color] * len(text.text))
            scales.append(text.scale)

        positions = np.ascontiguousarray(np.vstack(positions), dtype=np.float32)
        colors = np.ascontiguousarray(np.vstack(colors), dtype=np.uint8)
        scales = np.ascontiguousarray(np.hstack(scales), dtype=np.float32)


        return strings, positions, colors, scales


class TextController:
    """
    Controller for managing 3D text labels.
    """
    def __init__(self, app: dvz._app.App, panel: dvz._panel.Panel, offset: np.ndarray, scale: float = 200):
        self.view = TextView(app, panel, offset, scale)
        self.model = TextModel()

    def add_text(self, text: str, position: np.ndarray, color: np.ndarray, size: int | float) -> None:
        self.model.add_text(text, position, color, size)
        self.view.add_text(*self.model.load_text())


class TextView:
    """
    View for displaying 3D text labels.
    """
    def __init__(self, app: dvz._app.App, panel: dvz._panel.Panel, offset: np.ndarray, scale: float):
        self.app = app
        self.panel = panel
        self.offset = offset
        self.scale = scale
        self.text = self.app.glyph(font_size=15)
        self.text.set_strings(['l'], string_pos=np.array([[0, 0, 0]], dtype=np.float32),
                              scales=np.array([1], dtype=np.float32))
        self.panel.add(self.text)

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

    def add_text(self, strings, positions, colors, scales):
        self.text.set_strings(strings, string_pos=self.norm_pos(positions), scales=scales)
        self.text.set_color(colors)
        self.text.hide()
        self.text.show()