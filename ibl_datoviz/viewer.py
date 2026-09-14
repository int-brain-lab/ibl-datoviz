"""Datoviz v0.4 atlas viewer with explicit native object ownership."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import TYPE_CHECKING

import datoviz as dvz
import numpy as np

from .atlas import AtlasMesh

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
        width: int = 900,
        height: int = 720,
        datoviz: ModuleType | None = None,
    ) -> None:
        self.dvz = dvz if datoviz is None else datoviz
        self.mesh_data = mesh
        self.mapping = mapping
        self.palette = palette
        self.width = width
        self.height = height
        self.scene = self.dvz.dvz_scene()
        if not self.scene:
            raise RuntimeError('dvz_scene() failed')
        self.app = None
        self.view = None
        self.arcball = None
        self.interaction = None
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
                        'color': mesh.colors(mapping, palette),
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
                    self.mesh, self.dvz.DVZ_QUERY_CAPABILITY_ITEM
                ),
                'mesh picking capability',
            )
            self.link_channel = self.dvz.dvz_link_channel(self.scene, b'atlas-region')
            self._check(
                self.dvz.dvz_visual_set_link_keys(
                    self.mesh, self.link_channel, mesh.link_keys(mapping)
                ),
                'mesh region link keys',
            )
            self._check(self.dvz.dvz_panel_add_visual(self.panel, self.mesh, None), 'mesh attach')
            self.interaction = self.dvz.dvz_item_interaction(self.panel, None)
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
        self._check(
            self.dvz.dvz_visual_set_data(
                self.mesh, 'color', self.mesh_data.colors(mapping, effective_palette)
            ),
            'mapping color update',
        )
        self._check(
            self.dvz.dvz_visual_set_link_keys(
                self.mesh, self.link_channel, self.mesh_data.link_keys(mapping)
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
        """Return signed mapped region IDs currently retained by mesh selection."""
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
        return tuple(signed)

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
