"""Private retained probe presentation for diagnostic and legacy data clients.

Scientific recording layers use the generic layer registry. This separate helper
keeps the older single-probe rendering path out of the public viewer API while
preserving its table identity, retry and rollback behavior. Its native visuals
remain scene-owned; borrowed handles stay on the viewer for query coverage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import numpy as np

from .presentation import scalar_colors

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from numpy.typing import NDArray

    from .probe import ProbeSites
    from .viewer import AtlasViewer


class ProbeUpload(NamedTuple):
    """Owned read-only upload arrays retained for failed-write recovery."""

    positions: NDArray[np.float32]
    colors: NDArray[np.uint8]
    radii: NDArray[np.float32]
    keys: NDArray[np.uint64]

    def attributes(self):
        """Return the native sphere attributes without copying the snapshot."""
        return {'position': self.positions, 'color': self.colors, 'radius': self.radii}


class ProbePresentation:
    """Own probe payloads and retry candidates independently of viewer assembly."""

    def __init__(self, viewer: AtlasViewer) -> None:
        self.viewer = viewer
        self.data: ProbeSites | None = None
        self.colors: NDArray[np.uint8] | None = None
        self.upload: ProbeUpload | None = None
        self.pending_path = None
        self.pending_sites = None

    def set_path(
        self,
        points_um: Sequence[Sequence[float]],
        *,
        color: Sequence[int] = (255, 205, 72, 255),
        width_px: float = 4.0,
    ) -> None:
        """Add or replace a probe trajectory in atlas world micrometres."""
        viewer = self.viewer
        viewer._require_open()
        viewer._invalidate_picking()
        positions = viewer.mesh_data.normalize_points(points_um)
        if len(positions) < 2:
            raise ValueError('a probe path needs at least two points')
        if not np.isfinite(width_px) or width_px <= 0:
            raise ValueError('probe width must be finite and positive')
        raw_color = np.asarray(color)
        if (
            raw_color.shape not in ((3,), (4,))
            or not np.issubdtype(raw_color.dtype, np.integer)
            or np.any(raw_color < 0)
            or np.any(raw_color > 255)
        ):
            raise ValueError('probe color must contain three or four 8-bit integer channels')
        rgba = tuple(int(channel) for channel in raw_color)
        if len(rgba) == 3:
            rgba += (255,)
        colors = np.tile(np.asarray(rgba, dtype=np.uint8), (len(positions), 1))
        widths = np.full(len(positions), width_px, dtype=np.float32)
        probe = viewer.probe
        if probe is None:
            probe = self.pending_path
            if probe is None:
                probe = viewer.dvz.dvz_path(viewer.scene, 0)
                if not probe:
                    raise RuntimeError('dvz_path() failed')
                self.pending_path = probe
            viewer._check(
                viewer.dvz.dvz_path_set_caps(
                    probe, viewer.dvz.DVZ_SEGMENT_CAP_ROUND, viewer.dvz.DVZ_SEGMENT_CAP_ROUND
                ),
                'probe caps',
            )
            viewer._check(
                viewer.dvz.dvz_path_set_join(probe, viewer.dvz.DVZ_PATH_JOIN_ROUND, 4.0),
                'probe join',
            )
        viewer._check(
            viewer.dvz.dvz_visual_set_data_many(
                probe,
                {'position': positions, 'color': colors, 'stroke_width_px': widths},
            ),
            'probe upload',
        )
        if viewer.probe is None:
            viewer._check(
                viewer.dvz.dvz_panel_add_visual(viewer.panel, probe, None), 'probe attach'
            )
        viewer.probe = probe
        self.pending_path = None

    def set_sites(
        self,
        points_um: Sequence[Sequence[float]],
        *,
        values: Sequence[float] | None = None,
        colors: Sequence[Sequence[int]] | None = None,
        value_range: tuple[float, float] | None = None,
        radius_um: float = 45.0,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> None:
        """Replace sites and clear any typed payload and its linked table on success."""
        viewer = self.viewer
        self.upload_sites(
            points_um,
            values=values,
            colors=colors,
            value_range=value_range,
            radius_um=radius_um,
            color_scheme=color_scheme,
        )
        self.data = None
        self.colors = None
        viewer._replace_probe_table()

    def upload_sites(
        self,
        points_um,
        *,
        values=None,
        colors=None,
        value_range=None,
        radius_um=45.0,
        color_scheme='diverging',
        mapped_ids=None,
    ) -> None:
        """Validate and upload geometry and link identity before committing typed state."""
        viewer = self.viewer
        viewer._require_open()
        positions = viewer.mesh_data.normalize_points(points_um)
        count = len(positions)
        if not np.isfinite(radius_um) or radius_um <= 0:
            raise ValueError('probe site radius must be finite and positive')
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
            if scalar.shape != (count,) or np.isinf(scalar).any():
                raise ValueError('probe values must have shape (n,) and contain no infinities')
            rgba = self.value_colors(scalar, value_range, color_scheme)
        else:
            rgba = np.tile(np.asarray((255, 205, 72, 255), dtype=np.uint8), (count, 1))

        radii = np.full(count, radius_um * viewer.mesh_data.display_scale, dtype=np.float32)
        keys = (
            np.zeros(count, dtype=np.uint64) if mapped_ids is None else mapped_ids.view(np.uint64)
        )
        snapshot = ProbeUpload(
            *(np.array(array, order='C', copy=True) for array in (positions, rgba, radii, keys))
        )
        for array in snapshot:
            array.setflags(write=False)
        self.commit_upload(snapshot)

    def commit_upload(self, snapshot: ProbeUpload) -> None:
        """Commit geometry and identities, restoring the prior snapshot on failure."""
        viewer = self.viewer
        previous = self.upload
        visual = viewer.probe_sites
        if visual is None:
            visual = self.pending_sites
            if visual is None:
                visual = viewer.dvz.dvz_sphere(viewer.scene, 0)
                if not visual:
                    raise RuntimeError('dvz_sphere() failed')
                # Scene owns the candidate even if a setter or attachment fails.
                self.pending_sites = visual
        try:
            viewer._check(
                viewer.dvz.dvz_visual_set_data_many(visual, snapshot.attributes()),
                'probe sites upload',
            )
            viewer._check(
                viewer.dvz.dvz_visual_set_link_keys(visual, viewer.link_channel, snapshot.keys),
                'probe site link keys',
            )
            if viewer.probe_sites is None:
                viewer._check(
                    viewer.dvz.dvz_panel_add_visual(viewer.panel, visual, None),
                    'probe sites attach',
                )
        except Exception as error:
            if previous is not None:
                try:
                    viewer._check(
                        viewer.dvz.dvz_visual_set_data_many(visual, previous.attributes()),
                        'probe sites geometry rollback',
                    )
                    viewer._check(
                        viewer.dvz.dvz_visual_set_link_keys(
                            visual, viewer.link_channel, previous.keys
                        ),
                        'probe sites identity rollback',
                    )
                except Exception:
                    viewer.close()
                    raise RuntimeError('probe sites rollback failed; viewer closed') from error
            raise
        viewer.probe_sites = visual
        self.pending_sites = None
        self.upload = snapshot

    def set_data(
        self,
        data: ProbeSites,
        *,
        value_range: tuple[float, float] | None = None,
        radius_um: float = 45.0,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> None:
        """Display a typed probe payload and link its Allen labels to atlas presentation."""
        viewer = self.viewer
        viewer._require_open()
        viewer._invalidate_picking()
        if viewer.catalog is None:
            raise ValueError('linked probe data requires an atlas region catalog')
        mapped_ids = self.mapped_region_ids(data)
        colors = self.value_colors(data.values, value_range, color_scheme)
        self.upload_sites(
            data.positions_um, colors=colors, radius_um=radius_um, mapped_ids=mapped_ids
        )
        self.data = data
        self.colors = colors
        if viewer.gui is not None:
            viewer._replace_probe_table()

    def mapped_region_ids(self, data: ProbeSites | None = None) -> NDArray[np.int64]:
        """Resolve typed Allen labels in the current atlas presentation mapping."""
        viewer = self.viewer
        payload = self.data if data is None else data
        if payload is None or viewer.catalog is None:
            return np.empty(0, dtype=np.int64)
        try:
            mapped = viewer.catalog.map_allen_ids(payload.allen_region_ids, viewer.mapping)
        except KeyError as error:
            raise ValueError(str(error)) from error
        return np.ascontiguousarray(
            [0 if region_id is None else region_id for region_id in mapped], dtype=np.int64
        )

    @staticmethod
    def value_colors(
        values: NDArray[np.float64],
        value_range: tuple[float, float] | None,
        color_scheme: Literal['diverging', 'sequential'] = 'diverging',
    ) -> NDArray[np.uint8]:
        """Prepare scalar colors using the shared scientific palette contract."""
        return scalar_colors(values, value_range, color_scheme)

    def snapshot_state(self):
        """Retain the probe portion of an enclosing mapping transaction."""
        return self.upload, self.colors

    def restore_state(self, state):
        """Restore retained state before an enclosing transaction restores native data."""
        self.upload, self.colors = state

    def restore_keys(self):
        """Restore typed link identities after a partially failed mapping update."""
        viewer = self.viewer
        if self.data is not None and self.upload is not None:
            viewer._check(
                viewer.dvz.dvz_visual_set_link_keys(
                    viewer.probe_sites, viewer.link_channel, self.upload.keys
                ),
                'surface transaction probe key rollback',
            )

    def update_mapping(self):
        """Apply the viewer's current mapping to typed site identities."""
        viewer = self.viewer
        if self.data is None:
            return
        mapped_ids = self.mapped_region_ids()
        viewer._check(
            viewer.dvz.dvz_visual_set_link_keys(
                viewer.probe_sites, viewer.link_channel, mapped_ids.view(np.uint64)
            ),
            'probe site mapping link keys',
        )
        if self.upload is not None:
            keys = np.array(mapped_ids.view(np.uint64), copy=True)
            keys.setflags(write=False)
            self.upload = self.upload._replace(keys=keys)
