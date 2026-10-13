"""Independent mapped-region presentation and canonical hemisphere visibility."""

from dataclasses import dataclass, replace
from numbers import Integral

import numpy as np


@dataclass(frozen=True)
class RegionStyle:
    """An authored region override, separate from hover and selection emphasis."""

    visible: bool = True
    color: tuple[int, ...] | None = None
    opacity: float = 1.0


class SurfaceStyle:
    """Keep signed overrides scoped to mappings and anatomical sides independent."""

    def __init__(self, mesh):
        self.mesh = mesh
        self.regions = {}
        self.hemispheres = {'left': True, 'right': True}
        sides = np.asarray([p['side'] for p in mesh.presentations])
        self.vertex_sides = sides[mesh.presentation_ids]
        self.face_sides = sides[mesh.face_presentation_ids]

    def copy(self):
        """Copy authored state while sharing immutable mesh identity arrays."""
        result = object.__new__(type(self))
        result.mesh = self.mesh
        result.regions = self.regions.copy()
        result.hemispheres = self.hemispheres.copy()
        result.vertex_sides, result.face_sides = self.vertex_sides, self.face_sides
        return result

    def _ids(self, mapping, region_id, hemisphere):
        if isinstance(region_id, bool) or not isinstance(region_id, Integral) or region_id == 0:
            raise ValueError('region ID must be a nonzero signed integer in the current mapping')
        if hemisphere not in (None, 'left', 'right', 'both'):
            raise ValueError('hemisphere must be left, right, both or None')
        value = int(region_id)
        requested = (
            (value,)
            if hemisphere is None
            else {
                'left': (-abs(value),),
                'right': (abs(value),),
                'both': (-abs(value), abs(value)),
            }[hemisphere]
        )
        available = set(self.mesh.face_mapping_ids(mapping).tolist())
        result = tuple(value for value in requested if value in available)
        if not result:
            raise ValueError('region has no mesh faces in the requested mapping/hemisphere')
        return result

    def set_region(self, mapping, region_id, *, hemisphere=None, **changes):
        """Update a signed region or explicitly expand to anatomical hemispheres."""
        if 'color' in changes and changes['color'] is not None:
            color = np.asarray(changes['color'])
            if (
                color.shape not in ((3,), (4,))
                or not np.issubdtype(color.dtype, np.integer)
                or np.any(color < 0)
                or np.any(color > 255)
            ):
                raise ValueError(
                    'region color must contain three or four integer channels in [0, 255]'
                )
            changes['color'] = tuple(int(value) for value in color)
        if 'opacity' in changes and (
            not np.isfinite(changes['opacity']) or not 0 <= changes['opacity'] <= 1
        ):
            raise ValueError('region opacity must be finite and between zero and one')
        if 'visible' in changes and not isinstance(changes['visible'], (bool, np.bool_)):
            raise ValueError('region visibility must be boolean')
        for value in self._ids(mapping, region_id, hemisphere):
            key = (mapping, value)
            self.regions[key] = replace(self.regions.get(key, RegionStyle()), **changes)

    def reset_region(self, mapping, region_id, *, hemisphere=None):
        """Remove an authored override for the selected mapped identities."""
        for value in self._ids(mapping, region_id, hemisphere):
            self.regions.pop((mapping, value), None)

    def set_hemisphere_visible(self, hemisphere, visible):
        """Control hemisphere faces using verified presentation side metadata."""
        if hemisphere not in ('left', 'right', 'both'):
            raise ValueError('hemisphere must be left, right or both')
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('hemisphere visibility must be boolean')
        for side in ('left', 'right') if hemisphere == 'both' else (hemisphere,):
            self.hemispheres[side] = bool(visible)

    def visible_faces(self, mapping):
        """Return canonical face membership; zero opacity suppresses picking too."""
        mask = np.ones(len(self.mesh.face_presentation_ids), dtype=bool)
        for side, visible in self.hemispheres.items():
            if not visible:
                mask[self.face_sides == side] = False
        ids = self.mesh.face_mapping_ids(mapping)
        for (style_mapping, region_id), style in self.regions.items():
            if style_mapping == mapping and (
                not style.visible
                or style.opacity == 0
                or (style.color is not None and len(style.color) == 4 and style.color[3] == 0)
            ):
                mask[ids == region_id] = False
        return mask

    def apply(self, mapping, colors, *, alpha_scale=1.0):
        """Apply authored colors/opacities to canonical colors before emphasis."""
        colors = np.array(colors, copy=True, order='C')
        if not any(style_mapping == mapping for style_mapping, _ in self.regions):
            return colors
        ids = self.mesh.mapping_ids(mapping)
        for (style_mapping, region_id), style in self.regions.items():
            if style_mapping != mapping:
                continue
            selected = ids == region_id
            if style.color is not None:
                colors[selected, : len(style.color)] = style.color
                if len(style.color) == 4:
                    colors[selected, 3] = round(style.color[3] * alpha_scale)
            colors[selected, 3] = np.rint(colors[selected, 3].astype(float) * style.opacity)
        return colors

    def alpha_cap(self, mapping, canonical_alpha):
        """Keep authored palette/style transparency through interactive emphasis."""
        colors = np.zeros((len(canonical_alpha), 4), np.uint8)
        colors[:, 3] = canonical_alpha
        return self.apply(mapping, colors)[:, 3].copy()
