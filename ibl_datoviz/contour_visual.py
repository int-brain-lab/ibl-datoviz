"""Two retained polygon buffers for bounded native slice replacement."""

from __future__ import annotations

import ctypes

import numpy as np

from .contour_geometry import ContourComponent, ContourGeometry


class ContourVisual:
    """Stage polygon geometry without consuming a scene slot on every slice.

    The pinned engine has append-only scene slots. Two polygon sets/composites
    are retained until close; component slots grow only to their high-water
    count. CPU ownership and displayed identities stay with the slice owner.
    """

    def __init__(self, dvz, scene, panel, *, max_components=8192, max_vertices=1_000_000):
        self.dvz, self.scene, self.panel = dvz, scene, panel
        self.max_components, self.max_vertices = max_components, max_vertices
        self._buffers = []
        self._active = None
        self._active_visible = False
        self._pending = None
        self._staged = False
        self._closed = False

    @staticmethod
    def _check(status, context):
        if status != 0:
            raise RuntimeError(f'{context}: native status {status}')

    def _visible(self, buffer, visible):
        self._check(self.dvz.dvz_visual_set_visible(buffer['fill'], visible), 'contour visibility')
        self._check(self.dvz.dvz_visual_set_visible(buffer['stroke'], False), 'contour stroke')

    def _create_buffer(self):
        dvz = self.dvz
        polygons = dvz.dvz_polygons(self.scene, 0)
        if not polygons:
            raise RuntimeError('contour polygon allocation failed')
        buffer = {
            'polygons': polygons,
            'composite': None,
            'count': 0,
            'signature': None,
            'geometry': None,
        }
        # Retain partially allocated resources for deterministic cleanup on failure.
        self._buffers.append(buffer)
        composite = dvz.dvz_polygons_composite(polygons, 0)
        if not composite:
            raise RuntimeError('contour composite allocation failed')
        buffer['composite'] = composite
        buffer['fill'] = dvz.dvz_composite_visual(composite, b'fill')
        buffer['stroke'] = dvz.dvz_composite_visual(composite, b'stroke')
        if not buffer['fill'] or not buffer['stroke']:
            raise RuntimeError('contour composite roles unavailable')
        material = dvz.dvz_material_desc()
        material.model = dvz.DVZ_MATERIAL_MODEL_UNLIT
        material.alpha_mode = dvz.DVZ_ALPHA_BLENDED
        self._check(dvz.dvz_visual_set_material(buffer['fill'], material), 'contour material')
        self._check(dvz.dvz_visual_set_depth_test(buffer['fill'], False), 'contour depth')
        self._visible(buffer, False)
        return buffer

    def _descriptor(self, component, matrix, corners):
        dvz = self.dvz
        rings = []
        low, high = corners[0, :2], corners[3, :2]
        for original in (component.outer, *component.holes):
            fraction = np.asarray(original) @ matrix[:2, :2].T + matrix[:2, 2]
            rings.append(np.ascontiguousarray(low + fraction * (high - low), dtype=np.float64))
        descriptor = dvz.dvz_polygon_desc()
        descriptor.outer.xy = ctypes.c_void_p(rings[0].ctypes.data)
        descriptor.outer.count = len(rings[0])
        holes = (dvz.DvzPolygonRing * (len(rings) - 1))()
        for native, ring in zip(holes, rings[1:], strict=True):
            native.xy, native.count = ctypes.c_void_p(ring.ctypes.data), len(ring)
        descriptor.holes, descriptor.hole_count = holes, len(holes)
        return descriptor, (rings, holes)

    def _quarantine(self, buffer):
        # Hiding a generated child alone is insufficient: the next render
        # prepares dirty composites and makes visible source regions reappear.
        buffer['signature'] = buffer['geometry'] = None
        for slot in range(buffer['count']):
            self._check(
                self.dvz.dvz_polygons_set_region_visible(buffer['polygons'], slot, False),
                'contour rejected region hide',
            )
        if buffer['count']:
            attach = self.dvz.dvz_visual_attach_desc()
            attach.coord_space = self.dvz.DVZ_VISUAL_COORD_DATA
            attach.z_layer = 1
            self._check(
                self.dvz.dvz_panel_add_composite(
                    self.panel, buffer['composite'], ctypes.byref(attach)
                ),
                'contour rejected prepare',
            )
        self._visible(buffer, False)

    @staticmethod
    def _signature(geometry, colors, matrix, corners, opacity):
        if not isinstance(geometry, ContourGeometry) or not all(
            type(c) is ContourComponent for c in geometry.components
        ):
            return None
        # Only validated bytes-backed immutable rings may use identity keys.
        # Buffer geometry keeps them alive, preventing object ID recycling.
        rings = tuple(
            (c.atlas_id, c.allen_id, id(c.outer), tuple(map(id, c.holes)))
            for c in geometry.components
        )
        palette = tuple((*colors[c.atlas_id], round(255 * opacity)) for c in geometry.components)
        return rings, tuple(matrix.flat), tuple(np.asarray(corners).flat), palette

    def _cached_buffer(self, signature):
        if signature is None:
            return None
        return next((i for i, b in enumerate(self._buffers) if b['signature'] == signature), None)

    def _fill_component(self, buffer, slot, component, matrix, corners, colors, opacity):
        dvz = self.dvz
        descriptor, storage = self._descriptor(component, matrix, corners)
        if slot < buffer['count']:
            self._check(
                dvz.dvz_polygons_set_region_geometry(
                    buffer['polygons'], slot, ctypes.byref(descriptor)
                ),
                'contour geometry',
            )
        else:
            added = dvz.dvz_polygons_add_region(buffer['polygons'], ctypes.byref(descriptor))
            if added != slot:
                raise RuntimeError('contour component allocation failed')
            buffer['count'] += 1
        del storage  # Native setters have copied the borrowed rings.
        self._check(
            dvz.dvz_polygons_set_region_id(buffer['polygons'], slot, slot + 1),
            'contour private identity',
        )
        self._check(
            dvz.dvz_polygons_set_region_visible(buffer['polygons'], slot, True),
            'contour component visibility',
        )
        color = dvz.DvzColor(*colors[component.atlas_id], round(255 * opacity))
        self._check(
            dvz.dvz_polygons_set_region_fill_color(buffer['polygons'], slot, color),
            'contour color',
        )
        self._check(
            dvz.dvz_polygons_set_region_stroke_width_px(buffer['polygons'], slot, 0),
            'contour fill only',
        )

    def stage(self, geometry, colors, svg_to_fraction, corners, *, opacity=1.0):
        """Prepare the inactive retained buffer, keeping the old display visible."""
        if self._closed:
            raise RuntimeError('contour visual is closed')
        count = len(geometry.components)
        vertices = sum(len(r) for c in geometry.components for r in (c.outer, *c.holes))
        if count > self.max_components or vertices > self.max_vertices:
            raise ValueError('contour section exceeds the retained geometry budget')
        self._staged = False
        self._pending = None
        if not count:
            self._staged = True
            return
        matrix = np.asarray(svg_to_fraction, dtype=float).reshape(3, 3)
        signature = self._signature(geometry, colors, matrix, corners, opacity)
        cached = self._cached_buffer(signature)
        if cached is not None:
            self._pending, self._staged = cached, True
            return
        while len(self._buffers) < 2:
            self._create_buffer()
        index = 1 if self._active == 0 else 0
        buffer, dvz = self._buffers[index], self.dvz
        buffer['signature'] = buffer['geometry'] = None
        try:
            self._visible(buffer, False)
            for slot, component in enumerate(geometry.components):
                self._fill_component(buffer, slot, component, matrix, corners, colors, opacity)
            # Drop surplus ring storage instead of retaining large old sections.
            placeholder = type(
                'Placeholder', (), {'outer': np.array([[0, 0], [1, 0], [0, 1]]), 'holes': ()}
            )()
            for slot in range(count, buffer['count']):
                descriptor, storage = self._descriptor(placeholder, np.eye(3), corners)
                self._check(
                    dvz.dvz_polygons_set_region_geometry(
                        buffer['polygons'], slot, ctypes.byref(descriptor)
                    ),
                    'contour surplus release',
                )
                self._check(
                    dvz.dvz_polygons_set_region_visible(buffer['polygons'], slot, False),
                    'contour surplus visibility',
                )
                del storage
            attach = dvz.dvz_visual_attach_desc()
            attach.coord_space = dvz.DVZ_VISUAL_COORD_DATA
            attach.z_layer = 1
            # This forces checked triangulation, also when already attached.
            self._check(
                dvz.dvz_panel_add_composite(self.panel, buffer['composite'], ctypes.byref(attach)),
                'contour prepare',
            )
            self._visible(buffer, False)
        except Exception as error:
            try:
                self._quarantine(buffer)
            except Exception:
                self.close()
                raise RuntimeError('contour staging rollback failed; visual closed') from error
            raise
        buffer['signature'], buffer['geometry'] = (
            signature,
            geometry if signature is not None else None,
        )
        self._pending, self._staged = index, True

    def activate(self, *, visible=True):
        """Publish prepared native geometry only after the owner accepts its layers."""
        if not self._staged:
            raise RuntimeError('no contour replacement has been staged')
        old, new = self._active, self._pending
        self._staged = False
        try:
            if new is not None:
                self._visible(self._buffers[new], visible)
            if old is not None and old != new:
                self._visible(self._buffers[old], False)
        except Exception as error:
            try:
                if new is not None:
                    self._visible(self._buffers[new], False)
                if old is not None:
                    self._visible(self._buffers[old], self._active_visible)
            except Exception:
                self.close()
                raise RuntimeError('contour activation rollback failed; visual closed') from error
            raise
        self._active, self._active_visible = new, bool(visible)

    def close(self):
        """Release buffers once, before the borrowing scene is destroyed."""
        if self._closed:
            return
        for buffer in self._buffers:
            children = [buffer.get(role) for role in ('fill', 'stroke')]
            self.dvz.dvz_polygons_destroy(buffer['polygons'])
            # f77 composite reset only hides children; explicitly release them.
            for visual in children:
                if visual:
                    self.dvz.dvz_visual_destroy(visual)
        self._buffers.clear()
        self._closed = True
