"""Owned GPU interaction decoration for an atlas surface's stable presentations."""

from __future__ import annotations

import ctypes

import numpy as np


class SurfaceState:
    """Translate host region sets into sparse presentation-state replacements."""

    def __init__(self, owner):
        self.owner = owner
        self.handle = None
        self.words = np.zeros(len(owner.mesh_data.presentations), dtype=np.uint32)
        self.indices = np.array(owner.mesh_data.presentation_ids, dtype=np.uint32, copy=True)
        self._mapping = None
        self._region_ids = None
        self._style = None
        self._valid = False
        dvz = owner.dvz
        descriptor = dvz.dvz_item_state_buffer_desc()
        descriptor.slot_count = len(self.words)
        descriptor.words = self.words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32))
        try:
            self.handle = dvz.dvz_item_state_buffer(owner.scene, ctypes.byref(descriptor))
            if not self.handle:
                raise RuntimeError('atlas interaction state buffer creation failed')
            owner._check(
                dvz.dvz_visual_set_item_state_buffer(owner.mesh, self.handle, self.indices),
                'atlas interaction state binding',
            )
            self.update((), (), selection_active=False)
        except Exception:
            self.close()
            raise

    def invalidate(self):
        """Force recovery after a setter may have partially changed native state."""
        self._valid = False
        self._style = None

    def _mapped_ids(self):
        owner = self.owner
        if self._mapping != owner.mapping:
            ids = np.zeros(len(self.words), dtype=np.int64)
            for presentation in owner.mesh_data.presentations:
                mapped = presentation['mappings'][owner.mapping]
                if mapped is not None:
                    ids[int(presentation['presentation_id'])] = abs(int(mapped))
            self._region_ids = ids
            self._mapping = owner.mapping
        return self._region_ids

    def update(self, selected, hovered, *, selection_active):
        """Keep authored colors and pick coverage separate from GPU decoration."""
        owner, dvz = self.owner, self.owner.dvz
        ids = self._mapped_ids()
        words = np.zeros_like(self.words)
        if selected:
            words[(ids != 0) & np.isin(ids, selected)] |= np.uint32(dvz.DVZ_ITEM_STATE_SELECTED)
        if hovered:
            words[(ids != 0) & np.isin(ids, hovered)] |= np.uint32(dvz.DVZ_ITEM_STATE_HOVERED)
        slots = (
            np.flatnonzero(words != self.words).astype(np.uint32)
            if self._valid
            else np.arange(len(words), dtype=np.uint32)
        )
        style_key = (bool(selection_active), float(owner.selection_context_opacity))
        try:
            if style_key != self._style:
                selection = dvz.dvz_selection_visual_style()
                selection.selected_visual_flags = 0
                selection.unselected_visual_flags = dvz.DVZ_ITEM_STATE_VISUAL_ALPHA
                selection.selected_alpha = 1.0
                selection.unselected_alpha = owner.selection_context_opacity
                hover = dvz.dvz_item_state_visual_style()
                hover.visual_flags = dvz.DVZ_ITEM_STATE_VISUAL_TINT
                hover.tint = dvz.DvzColor(255, 255, 255, 255)
                hover.tint_mix = 0.28
                owner._check(
                    dvz.dvz_item_state_buffer_style(
                        self.handle, ctypes.byref(selection), ctypes.byref(hover), selection_active
                    ),
                    'selection and hover style update',
                )
                self._style = style_key
            if len(slots):
                owner._check(
                    dvz.dvz_item_state_buffer_update(self.handle, slots, words[slots]),
                    'selection and hover state update',
                )
        except Exception:
            self.invalidate()
            raise
        self.words = words
        self._valid = True

    def close(self):
        """Release the owned bank before its borrowed scene is destroyed."""
        if self.handle is not None:
            self.owner.dvz.dvz_item_state_buffer_destroy(self.handle)
            self.handle = None
