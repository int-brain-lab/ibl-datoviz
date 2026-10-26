"""Prepared source-native major anatomy and its independent retained visuals."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

from .atlas import AtlasMesh, _MeshPresentationBoundary
from .envelope import AtlasEnvelope
from .surface_geometry import SurfaceGeometry
from .surface_state import SurfaceState

# The source-native cut accepted for the recording-context default.
DEFAULT_CONTEXT_LANDMARKS = frozenset((315, 698, 313, 771, 354, 528))


@dataclass(frozen=True)
class AtlasContextSurface:
    """Owned coarse geometry with its source Allen identity and authored color.

    Context remains in its original anatomical position during fine-region
    explosion. Hemisphere coverage uses original world ML, including triangles
    crossing the midline; the source geometry is never clipped or capped.
    """

    geometry: SurfaceGeometry
    color: tuple[int, int, int]
    name: str
    source_allen_id: int

    @classmethod
    def from_geometry(cls, surface, atlas, *, color, name=''):
        """Normalize verified ``ibl_anatomy.SurfaceGeometry`` using the atlas frame."""
        if surface.asset.variant != 'source-native':
            raise ValueError('major context requires source-native geometry')
        envelope = AtlasEnvelope.from_geometry(surface, atlas)
        channels = np.asarray(color)
        if (
            channels.shape != (3,)
            or not np.issubdtype(channels.dtype, np.integer)
            or np.any(channels < 0)
            or np.any(channels > 255)
        ):
            raise ValueError('context color must contain three integer channels in [0, 255]')
        region_id = int(surface.asset.source_allen_id)
        if region_id <= 0:
            raise ValueError('context surface requires a positive source Allen identity')
        # Shared reference surfaces declare ML/AP/DV world coordinates. Signed
        # presentation conventions match the dense atlas: negative is left.
        boundary = atlas._presentation_boundary
        zero_side = boundary.on_plane_side if boundary is not None else 'right'
        count = len(envelope.positions)
        mesh = AtlasMesh(
            positions_um=envelope.positions_um,
            positions=envelope.positions,
            normals=envelope.normals,
            indices=envelope.indices,
            explode_offsets=np.zeros((count, 3), np.float32),
            component_ids=np.zeros(count, np.uint16),
            presentation_ids=np.zeros(count, np.int32),
            face_presentation_ids=np.zeros(len(envelope.indices) // 3, np.int32),
            presentations=tuple(
                {'presentation_id': i, 'side': side, 'mappings': {'allen': signed}}
                for i, side, signed in ((0, 'left', -region_id), (1, 'right', region_id))
            ),
            reference_space=envelope.reference_space,
            display_scale=atlas.display_scale,
            _presentation_boundary=_MeshPresentationBoundary(
                'original-world-ml', 0, 0.0, zero_side, ((0, 0, 1),)
            ),
        )
        geometry = SurfaceGeometry.from_mesh(mesh)
        for value in vars(geometry.mesh).values():
            if isinstance(value, np.ndarray):
                value.setflags(write=False)
        geometry.fragment_clip.setflags(write=False)
        return cls(geometry, tuple(int(c) for c in channels), name or str(region_id), region_id)


class AnatomicalContext:
    """Scene-owned coarse visuals; no geometry or dense color uploads on selection."""

    def __init__(self, owner, surfaces):
        self.owner = owner
        self.surfaces = tuple(surfaces)
        self.entries = []
        self._presentation = None
        try:
            for surface in self.surfaces:
                visual = owner.dvz.dvz_mesh(owner.scene, 0)
                if not visual:
                    raise RuntimeError('anatomical context creation failed')
                entry = SimpleNamespace(visual=visual, surface=surface, state=None)
                self.entries.append(entry)
                mesh = surface.geometry.mesh
                self._check(owner.dvz.dvz_visual_set_visible(visual, False), 'context hide')
                self._check(
                    owner.dvz.dvz_visual_set_data_many(
                        visual,
                        {
                            'position': mesh.positions,
                            'normal': mesh.normals,
                            'color': self._colors(surface),
                        },
                    ),
                    'context geometry',
                )
                self._check(
                    owner.dvz.dvz_visual_set_index_data(visual, mesh.indices), 'context indices'
                )
                self._check(
                    owner.dvz.dvz_mesh_set_fragment_clip(visual, surface.geometry.fragment_clip),
                    'context hemisphere coverage',
                )
                self._check(
                    owner.dvz.dvz_visual_set_alpha_mode(
                        visual,
                        owner.dvz.DVZ_ALPHA_WBOIT,
                    ),
                    'context transparency',
                )
                self._check(
                    owner.dvz.dvz_panel_add_visual(owner.panel, visual, None), 'context attach'
                )
                entry.state = SurfaceState(
                    SimpleNamespace(
                        dvz=owner.dvz,
                        scene=owner.scene,
                        mesh=visual,
                        _surface_mesh=mesh,
                        mapping='allen',
                        selection_presentation='all',
                        selection_context_opacity=1.0,
                        context_tint=True,
                        _check=owner._check,
                    )
                )
        except Exception:
            self.close()
            raise

    def _check(self, result, message):
        try:
            self.owner._check(result, message)
        except Exception:
            self._presentation = None
            raise

    def _colors(self, surface):
        return np.tile(
            np.array((*surface.color, round(self.owner.context_opacity * 255)), np.uint8),
            (len(surface.geometry.mesh.positions), 1),
        )

    def update(self, *, force=False):
        """Update hemisphere coverage only when presentation changes; tint sparsely."""
        owner = self.owner
        hemispheres = owner._surface_presentation.style.hemispheres
        presentation = (
            owner.mapping,
            owner._surface_presentation.visible,
            owner.anatomy_presentation,
            owner.context_opacity,
            tuple(hemispheres.values()),
        )
        if force or presentation != self._presentation:
            for entry in self.entries:
                mesh, visual = entry.surface.geometry.mesh, entry.visual
                sides = np.array([p['side'] for p in mesh.presentations])
                mask = np.array([hemispheres[s] for s in sides[mesh.face_presentation_ids]])
                if np.any(mask):
                    self._check(
                        owner.dvz.dvz_visual_set_index_data(
                            visual, mesh.indices.reshape(-1, 3)[mask].reshape(-1).copy()
                        ),
                        'context hemisphere indices',
                    )
                    keys = mesh.face_mapping_ids('allen')[mask].view(np.uint64).copy()
                    self._check(
                        owner.dvz.dvz_visual_set_target_link_keys(
                            visual, owner.dvz.DVZ_SCENE_TARGET_FACE, owner.link_channel, keys
                        ),
                        'context source parent keys',
                    )
                known = (
                    owner.mapping == 'allen'
                    if owner.tree_model is None
                    else entry.surface.source_allen_id
                    in {abs(int(v)) for v in owner.tree_model.region_ids}
                )
                self._check(
                    owner.dvz.dvz_visual_set_query_capabilities(
                        visual,
                        getattr(owner.dvz, 'DVZ_QUERY_CAPABILITY_ITEM', 0)
                        | (
                            owner.dvz.DVZ_QUERY_CAPABILITY_FACE
                            if owner.enable_interaction and known
                            else 0
                        ),
                    ),
                    'context parent picking',
                )
                if force or self._presentation is None or presentation[3] != self._presentation[3]:
                    self._check(
                        owner.dvz.dvz_visual_set_data(
                            visual, 'color', self._colors(entry.surface)
                        ),
                        'context opacity',
                    )
                    self._check(
                        owner.dvz.dvz_visual_set_alpha_mode(
                            visual,
                            owner.dvz.DVZ_ALPHA_WBOIT,
                        ),
                        'context transparency',
                    )
                self._check(
                    owner.dvz.dvz_visual_set_visible(
                        visual,
                        owner._surface_presentation.visible
                        and owner.anatomy_presentation == 'major'
                        and owner.context_opacity > 0
                        and bool(np.any(mask)),
                    ),
                    'context visibility',
                )
            self._presentation = presentation
        # Catalog trees retain true Allen parents in every mapping. These are
        # parent identities; context geometry and colors are never remapped.
        selected = owner._signed_focus_ids()
        hovered = owner._signed_focus_ids(owner._hovered_region_ids)
        for entry in self.entries:
            entry.state.update(selected, hovered, selection_active=bool(selected))

    def close(self):
        """Destroy state banks before visuals and before the borrowed scene."""
        for entry in self.entries:
            if entry.state is not None:
                entry.state.close()
            self.owner.dvz.dvz_visual_destroy(entry.visual)
        self.entries.clear()
