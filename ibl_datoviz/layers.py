"""Viewer-owned scientific layers with exact identities and retained presentation."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from uuid import uuid4

import numpy as np

from .component import ComponentVisual, owned, rgba_array
from .insertions import InsertionCollectionVisual, _endpoint_gaps
from .payloads import Paths, Points, Recording
from .points import PointCollection, PointCollectionVisual


@dataclass(frozen=True)
class LayerObservationRef:
    """One observation attached to one particular layer in one viewer."""

    attachment_id: str
    original_id: int | str
    source_key: object = None


@dataclass(frozen=True)
class LayerCapabilities:
    """Geometry controls and native query support, subject to scene coverage."""

    scalar_coloring: bool
    size_px: bool = False
    radius_um: bool = False
    width_px: bool = False
    native_picking: bool = False


@dataclass(frozen=True)
class ScalarEncoding:
    """Complete-population values and their explicit presentation metadata."""

    values: np.ndarray
    name: str
    units: str
    cmap: str
    limits: tuple[float, float]
    missing_color: str


class UnavailableLayerError(LookupError):
    """A recording did not supply the requested population."""


@dataclass(frozen=True)
class _VisibilityUpdate:
    """One retained component visibility write with its prior applied value."""

    component: object
    previous: bool
    visible: bool
    path_id: int | None = None

    def apply(self, visible):
        if self.path_id is None:
            self.component.set_visible(visible)
        else:
            self.component.set_visible(self.path_id, visible)


def _apply_visibility(registry, updates):
    """Restore every attempted native write, including a partially failing setter."""
    attempted = []
    try:
        for update in updates:
            if update.previous == update.visible:
                continue
            attempted.append(update)
            update.apply(update.visible)
    except Exception:
        rollback_error = None
        for update in reversed(attempted):
            try:
                update.apply(update.previous)
            except Exception as error:
                rollback_error = error
        if rollback_error is not None:
            # A viewer owns its scene; standalone internal registries can at
            # least release their owned components when no viewer close exists.
            close = getattr(registry.viewer, 'close', registry.close)
            close()
            raise RuntimeError(
                'layer visibility rollback failed; owner closed'
            ) from rollback_error
        raise


def _color(value):
    if not isinstance(value, str) or len(value) not in (7, 9) or not value.startswith('#'):
        raise ValueError('color must be #RRGGBB or #RRGGBBAA')
    try:
        channels = tuple(int(value[i : i + 2], 16) for i in range(1, len(value), 2))
    except ValueError as error:
        raise ValueError('color must contain hexadecimal channels') from error
    return np.asarray(channels if len(channels) == 4 else (*channels, 255), dtype=np.uint8)


def _positive(value):
    raw = np.asarray(value)
    if raw.shape != () or raw.dtype.kind not in 'iuf':
        raise ValueError('size must be a positive finite number')
    number = float(raw)
    if (
        not np.isfinite(number)
        or number <= 0
        or not np.isfinite(np.float32(number))
        or np.float32(number) <= 0
    ):
        raise ValueError('size must be a positive finite float32 number')
    return number


class _SphereVisual(ComponentVisual):
    def __init__(self, viewer, positions, colors, radius_um):
        super().__init__(viewer.dvz, viewer.scene, viewer.panel, viewer.mesh_data.normalize_points)
        self.data = positions
        self._storage = None
        self._radius_scale = viewer.mesh_data.display_scale
        self._alpha_mode = None
        try:
            if len(positions):
                self.visual = self._required(self.dvz.dvz_sphere(self.scene, 0), 'sphere visual')
                radius = _positive(radius_um * self._radius_scale)
                self._storage = {
                    'position': self._positions(positions),
                    'color': owned(colors, np.uint8),
                    'radius': owned(np.full(len(positions), radius), np.float32),
                }
                self._check(
                    self.dvz.dvz_visual_set_data_many(self.visual, self._storage), 'sphere data'
                )
                alpha = (
                    self.dvz.DVZ_ALPHA_WBOIT
                    if np.any(colors[:, 3] < 255)
                    else (self.dvz.DVZ_ALPHA_OPAQUE)
                )
                self._check(self.dvz.dvz_visual_set_alpha_mode(self.visual, alpha), 'sphere alpha')
                self._alpha_mode = alpha
                self._check(self.dvz.dvz_visual_set_depth_test(self.visual, True), 'sphere depth')
                self._check(
                    self.dvz.dvz_panel_add_visual(self.panel, self.visual, None), 'sphere attach'
                )
        except Exception:
            self.close()
            raise

    def _has_data(self):
        return self.data is not None and len(self.data) > 0

    def update_colors(self, colors):
        """Replace retained colors and derived alpha policy as one native transaction."""
        self._require_open()
        colors = rgba_array(colors, (len(self.data),))
        if not len(self.data):
            return
        alpha = (
            self.dvz.DVZ_ALPHA_WBOIT if np.any(colors[:, 3] < 255) else self.dvz.DVZ_ALPHA_OPAQUE
        )
        previous, old_alpha = self._storage['color'], self._alpha_mode
        alpha_attempted = False
        try:
            self._check(
                self.dvz.dvz_visual_set_data(self.visual, 'color', colors), 'sphere colors'
            )
            if alpha != old_alpha:
                alpha_attempted = True
                self._check(self.dvz.dvz_visual_set_alpha_mode(self.visual, alpha), 'sphere alpha')
        except Exception as error:
            failures = []
            if alpha_attempted:
                try:
                    self._check(
                        self.dvz.dvz_visual_set_alpha_mode(self.visual, old_alpha),
                        'sphere alpha rollback',
                    )
                except Exception as failure:
                    failures.append(failure)
            try:
                self._check(
                    self.dvz.dvz_visual_set_data(self.visual, 'color', previous),
                    'sphere colors rollback',
                )
            except Exception as failure:
                failures.append(failure)
            if failures:
                self.close()
                raise RuntimeError('sphere colors rollback failed; component closed') from error
            raise
        self._storage = {**self._storage, 'color': colors}
        self._alpha_mode = alpha

    def update_radius(self, radius_um):
        """Update physical radius without normalizing or uploading positions again."""
        self._require_open()
        if not len(self.data):
            return
        radius = _positive(radius_um * self._radius_scale)
        radii = owned(np.full(len(self.data), radius), np.float32)
        try:
            self._check(
                self.dvz.dvz_visual_set_data(self.visual, 'radius', radii), 'sphere radius'
            )
        except Exception as error:
            try:
                self._check(
                    self.dvz.dvz_visual_set_data(self.visual, 'radius', self._storage['radius']),
                    'sphere radius rollback',
                )
            except Exception:
                self.close()
                raise RuntimeError('sphere radius rollback failed; component closed') from error
            raise
        self._storage = {**self._storage, 'radius': radii}

    def close(self):
        """Release native resources and all retained attribute storage."""
        super().close()
        self._storage = None


class LayerHandle:
    """An attached immutable payload and its mutable presentation controls."""

    def __init__(self, registry, payload, name, glyph, *, group=None, visible=True):
        self._registry, self._payload = registry, payload
        self._name, self._glyph, self._group = str(name), glyph, group
        self._closed = False
        self._visible = visible
        self._size = 3.0 if glyph == 'path' else 8.0 if glyph == 'point' else 20.0
        self._colors = owned(np.tile(_color('#40dcfa'), (len(payload.ids), 1)), np.uint8)
        self._encoding = None
        self._selected = frozenset()
        self._endpoint_gaps_px = (0.0, 0.0)
        attachment = str(uuid4())
        keys = payload.observation_keys
        self._refs = tuple(
            LayerObservationRef(attachment, key, None if keys is None else keys[i])
            for i, key in enumerate(payload.ids)
        )
        self._positioned_rows = owned(payload.positioned, bool)
        self._native_rows_by_ref = {
            ref: row
            for row, ref in enumerate(
                ref
                for ref, positioned in zip(self._refs, self._positioned_rows, strict=True)
                if positioned
            )
        }
        self._visual = self._build()

    @property
    def payload(self):
        """Immutable scientific payload, including unpositioned observations."""
        return self._payload

    @property
    def name(self):
        """Display label, independent of scientific identity."""
        return self._name

    @property
    def refs(self):
        """All attachment identities in complete payload order."""
        return self._refs

    @property
    def positioned_refs(self):
        """Exact identities corresponding to drawable observations."""
        return tuple(
            ref
            for ref, positioned in zip(self.refs, self.payload.positioned, strict=True)
            if positioned
        )

    @property
    def visible(self):
        """Authored layer visibility, preserved while its recording is hidden."""
        return self._visible

    @property
    def effective_visible(self):
        """Visibility after the containing recording's temporary mask."""
        return self.visible and (self._group is None or self._group.visible)

    @property
    def capabilities(self):
        """Supported controls for the chosen glyph."""
        return LayerCapabilities(
            self._glyph != 'path',
            self._glyph == 'point',
            self._glyph == 'sphere',
            self._glyph == 'path',
            native_picking=self._glyph in ('point', 'sphere'),
        )

    @property
    def scalar_encoding(self):
        """Retained complete-population scalar encoding, or no scalar encoding."""
        return self._encoding

    def _require_open(self):
        if self._closed:
            raise RuntimeError('layer is removed or closed')

    def observation(self, original_id):
        """Resolve an original ID without treating it as a renderer row index."""
        self._require_open()
        if isinstance(original_id, (bool, np.bool_)):
            raise KeyError(original_id)
        try:
            return self.refs[self.payload.ids.index(original_id)]
        except ValueError as error:
            raise KeyError(original_id) from error

    def _build(self, *, colors=None, size=None, selected=None, visible=None, endpoint_gaps=None):
        viewer = self._registry.viewer
        gaps = self._endpoint_gaps_px if endpoint_gaps is None else endpoint_gaps
        colors = self._colors if colors is None else colors
        selected = self._selected if selected is None else selected
        colors = np.array(colors, copy=True)
        for index, ref in enumerate(self.refs):
            if ref in selected:
                colors[index] = (255, 70, 180, 255)
        size = self._size if size is None else size
        visible = self.effective_visible if visible is None else visible
        visual = None
        try:
            if self._glyph == 'path':
                visual = InsertionCollectionVisual(
                    viewer.dvz,
                    viewer.scene,
                    viewer.panel,
                    transform=viewer.mesh_data.normalize_points,
                )
                for index, positioned in enumerate(self.payload.positioned):
                    if positioned:
                        # Internal positive integer renderer keys never replace scientific IDs.
                        visual.set_insertion(
                            index + 1,
                            self.payload.positions_um[index],
                            color=colors[index],
                            width_px=size,
                        )
                        if any(gaps):
                            visual.set_endpoint_gaps_px(index + 1, *gaps)
                        visual.set_visible(index + 1, visible)
            else:
                rows = self.payload.positioned
                positions = self.payload.positions_um[rows]
                if self._glyph == 'point':
                    data = PointCollection.from_arrays(positions, colors[rows], sizes_px=size)
                    visual = PointCollectionVisual(
                        viewer.dvz,
                        viewer.scene,
                        viewer.panel,
                        data,
                        transform=viewer.mesh_data.normalize_points,
                    )
                else:
                    visual = _SphereVisual(viewer, positions, colors[rows], size)
                visual.set_visible(visible)
            picking = getattr(viewer, 'picking', None)
            if picking is not None:
                picking.register(self, visual)
            return visual
        except Exception:
            if visual is not None:
                self._dispose(visual)
            raise

    def _dispose(self, component):
        picking = getattr(self._registry.viewer, 'picking', None)
        if picking is not None:
            picking.unregister(component)
        component.close()

    def _replace(self, **kwargs):
        candidate = self._build(**kwargs)
        previous, self._visual = self._visual, candidate
        self._dispose(previous)

    def _mutate(self):
        self._registry._check()
        self._require_open()

    def _visibility_updates(self, visible):
        if self._glyph == 'path':
            return tuple(
                _VisibilityUpdate(self._visual, item.visible, visible, path_id)
                for path_id, item in self._visual._insertions.items()
            )
        return (_VisibilityUpdate(self._visual, self._visual._visible, visible),)

    def _update_attributes(self, *, colors=None, size=None):
        if self._glyph == 'path':
            self._replace(colors=colors, size=size)
            return
        try:
            if colors is not None:
                displayed = colors[self._positioned_rows]
                for ref in self._selected:
                    row = self._native_rows_by_ref.get(ref)
                    if row is not None:
                        displayed[row] = (255, 70, 180, 255)
                self._visual.update_colors(displayed)
            elif self._glyph == 'point':
                self._visual.update_sizes(size)
            else:
                self._visual.update_radius(size)
        except Exception:
            if self._visual._closed:
                close = getattr(self._registry.viewer, 'close', self._registry.close)
                close()
            raise

    def set_visible(self, visible):
        """Change authored visibility without changing observations or selection."""
        self._mutate()
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('visible must be boolean')
        if bool(visible) == self._visible:
            return
        effective = bool(visible) and (self._group is None or self._group.visible)
        _apply_visibility(self._registry, self._visibility_updates(effective))
        self._visible = bool(visible)

    def set_color(self, color):
        """Replace scalar encoding with one uniform color."""
        self._mutate()
        rgba = _color(color)
        if self._glyph == 'path' and rgba[3] != 255:
            raise ValueError('paths require opaque color')
        colors = owned(np.tile(rgba, (len(self.refs), 1)), np.uint8)
        self._update_attributes(colors=colors)
        self._colors, self._encoding = colors, None

    def color_by(
        self, values, *, name, units, cmap, limits, missing_color='#808080', observation_refs=None
    ):
        """Color complete ordered observations, requiring exact source alignment."""
        self._mutate()
        if not self.capabilities.scalar_coloring:
            raise ValueError('scalar coloring is unsupported for paths')
        if self.payload.observation_keys is not None:
            if (
                observation_refs is None
                or tuple(observation_refs) != self.payload.observation_keys
            ):
                raise ValueError('observation_refs must match complete source observation order')
        elif observation_refs is not None:
            raise ValueError('local annotation scalars use explicit payload order')
        raw_values = np.asarray(values, dtype=np.float64)
        scalar = np.frombuffer(raw_values.tobytes(), dtype=np.float64).reshape(raw_values.shape)
        bounds = np.asarray(limits, dtype=float)
        if scalar.shape != (len(self.refs),) or np.isinf(scalar).any():
            raise ValueError('values must match the complete population and contain no infinities')
        if bounds.shape != (2,) or not np.isfinite(bounds).all() or bounds[1] <= bounds[0]:
            raise ValueError('limits must be finite and increasing')
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(units, str)
            or not units
        ):
            raise ValueError('quantity name and units must be explicit nonempty strings')
        colors = self._registry._scalar_colors(scalar, cmap, bounds, missing_color)
        encoding = ScalarEncoding(scalar, name, units, cmap, tuple(bounds), missing_color)
        self._update_attributes(colors=colors)
        self._colors, self._encoding = colors, encoding

    def _set_size(self, value, capability):
        self._mutate()
        if not getattr(self.capabilities, capability):
            raise ValueError(f'{capability} is unsupported for this glyph')
        size = _positive(value)
        if size == self._size:
            return
        self._update_attributes(size=size)
        self._size = size

    def set_size_px(self, size):
        """Set pixel diameter for point glyphs only."""
        self._set_size(size, 'size_px')

    def set_radius_um(self, radius):
        """Set physical radius for sphere glyphs only."""
        self._set_size(radius, 'radius_um')

    def set_width_px(self, width):
        """Set opaque path width in pixels."""
        self._set_size(width, 'width_px')

    @property
    def endpoint_gaps_px(self):
        """Authored start/end disk radii in logical pixels; no inferred point linkage."""
        return self._endpoint_gaps_px

    def set_endpoint_gaps_px(self, start, end):
        """Set fixed path endpoint disk radii; requires compatible native support.

        For each open path, fragments inside either endpoint disk are excluded.
        Closed paths ignore the radii. Marker size and visibility do not change
        these explicit radii automatically.
        """
        self._mutate()
        if self._glyph != 'path':
            raise ValueError('endpoint gaps are unsupported for this glyph')
        gaps = _endpoint_gaps(start, end)
        if any(gaps) and not hasattr(self._registry.viewer.dvz, 'dvz_path_set_endpoint_gaps'):
            raise RuntimeError('endpoint gaps require a compatible native Datoviz build')
        self._replace(endpoint_gaps=gaps)
        self._endpoint_gaps_px = gaps

    def _close(self):
        if not self._closed:
            self._dispose(self._visual)
            self._closed = True


class RecordingHandle:
    """One recording's supplied layers, with independent authored visibility."""

    def __init__(self, registry, recording, name):
        self._registry, self._recording = registry, recording
        self._name = str(name or recording.name)
        self._visible, self._closed = True, False
        self._layers = {}

    @property
    def recording(self):
        """Prepared immutable recording."""
        return self._recording

    @property
    def name(self):
        """Human-readable recording label."""
        return self._name

    @property
    def layers(self):
        """Supplied layers in attachment order."""
        return tuple(self._layers.values())

    @property
    def visible(self):
        """Group mask, independent of child visibility."""
        return self._visible

    def __getattr__(self, name):
        """Resolve supplied recording children with explicit missing-population errors."""
        if name in ('channels', 'clusters', 'sites', 'path'):
            if self._closed:
                raise RuntimeError('recording is removed or closed')
            if name not in self._layers:
                raise UnavailableLayerError(f'recording has no {name} population')
            return self._layers[name]
        raise AttributeError(name)

    def set_visible(self, visible):
        """Temporarily mask all children while preserving their authored visibility."""
        self._registry._check()
        if self._closed:
            raise RuntimeError('recording is removed or closed')
        if not isinstance(visible, (bool, np.bool_)):
            raise ValueError('visible must be boolean')
        if bool(visible) == self._visible:
            return
        updates = tuple(
            update
            for layer in self.layers
            for update in layer._visibility_updates(bool(visible) and layer.visible)
        )
        _apply_visibility(self._registry, updates)
        self._visible = bool(visible)


class LayerRegistry:
    """Own all layer attachments and release them before the viewer's scene."""

    def __init__(self, viewer, *, before_mutation=None, on_remove=None, validate_frame=None):
        self.viewer = viewer
        self._before_mutation, self._on_remove = before_mutation, on_remove
        self._validate_frame = validate_frame
        self._layers, self._recordings = [], []
        self._closed = False

    @property
    def layers(self):
        """All live layers, including recording children."""
        return tuple(self._layers)

    @property
    def recordings(self):
        """Live recording handles in attachment order."""
        return tuple(self._recordings)

    def _check(self):
        if self._closed:
            raise RuntimeError('layer registry is closed')
        if self._before_mutation is not None:
            self._before_mutation()

    def _validate_payload(self, payload):
        if self._validate_frame is not None:
            self._validate_frame(payload.frame)

    def add_points(self, payload, *, name='', glyph='point'):
        """Attach arbitrary points without requiring a recording or data reader."""
        self._check()
        if not isinstance(payload, Points):
            raise TypeError('payload must be Points')
        if glyph not in ('point', 'sphere'):
            raise ValueError('glyph must be point or sphere')
        self._validate_payload(payload)
        layer = LayerHandle(self, payload, name, glyph)
        self._layers.append(layer)
        return layer

    def add_paths(self, payload, *, name=''):
        """Attach independently identified ordered polylines."""
        self._check()
        if not isinstance(payload, Paths):
            raise TypeError('payload must be Paths')
        self._validate_payload(payload)
        layer = LayerHandle(self, payload, name, 'path')
        self._layers.append(layer)
        return layer

    def add_recording(self, recording, *, name='', show=('path', 'channels')):
        """Compose supplied payloads atomically; reject repeated scientific keys."""
        self._check()
        if not isinstance(recording, Recording):
            raise TypeError('recording must be Recording')
        if any(handle.recording.key == recording.key for handle in self.recordings):
            raise ValueError('recording source key is already attached')
        populations = ('path', 'channels', 'clusters', 'sites')
        show = tuple(show)
        if len(set(show)) != len(show) or any(item not in populations for item in show):
            raise ValueError('show must contain unique supported population names')
        for population in show:
            if getattr(recording, population) is None:
                raise UnavailableLayerError(f'recording has no {population} population')
        group = RecordingHandle(self, recording, name)
        try:
            for population in populations:
                payload = getattr(recording, population)
                if payload is None:
                    continue
                self._validate_payload(payload)
                layer = LayerHandle(
                    self,
                    payload,
                    population,
                    'path' if population == 'path' else 'sphere',
                    group=group,
                    visible=population in show,
                )
                group._layers[population] = layer
        except Exception:
            for layer in reversed(group.layers):
                layer._close()
            group._closed = True
            raise
        self._recordings.append(group)
        self._layers.extend(group.layers)
        return group

    def contains(self, ref):
        """Whether an exact attachment identity is currently live in this registry."""
        return isinstance(ref, LayerObservationRef) and any(
            ref in layer.refs for layer in self.layers
        )

    def update_selection(self, refs):
        """Commit highlights transactionally without invoking public mutation guards."""
        selected = frozenset(refs)
        if any(not self.contains(ref) for ref in selected):
            raise ValueError('selection contains a foreign or removed observation')
        candidates = []
        try:
            for layer in self.layers:
                local = frozenset(selected.intersection(layer.refs))
                if local != layer._selected:
                    candidates.append((layer, local, layer._build(selected=local)))
        except Exception:
            for layer, _, candidate in candidates:
                layer._dispose(candidate)
            raise
        for layer, local, candidate in candidates:
            old, layer._visual = layer._visual, candidate
            layer._selected = local
            layer._dispose(old)

    def remove_layer(self, layer):
        """Remove a generic layer and prune only its observation attachments."""
        self._check()
        if layer not in self._layers or layer._group is not None:
            raise ValueError('layer must be a live generic attachment owned by this viewer')
        layer._close()
        self._layers.remove(layer)
        if self._on_remove is not None:
            self._on_remove(layer.refs)

    def remove_recording(self, recording):
        """Release all child visuals before pruning their committed selection."""
        self._check()
        if recording not in self._recordings:
            raise ValueError('recording is not attached to this viewer')
        refs = tuple(ref for layer in recording.layers for ref in layer.refs)
        for layer in reversed(recording.layers):
            layer._close()
            self._layers.remove(layer)
        recording._closed = True
        self._recordings.remove(recording)
        if self._on_remove is not None:
            self._on_remove(refs)

    def _scalar_colors(self, values, cmap, bounds, missing_color):
        missing = _color(missing_color)
        dvz = self.viewer.dvz
        if not isinstance(cmap, str):
            raise ValueError('cmap must name a supported built-in colormap')
        selector = getattr(dvz, f'DVZ_BUILTIN_COLORMAP_{cmap.upper()}', None)
        if selector is None:
            raise ValueError(f'unsupported built-in colormap: {cmap!r}')
        finite = np.isfinite(values)
        normalized = np.clip(
            (np.where(finite, values, bounds[0]) - bounds[0]) / (bounds[1] - bounds[0]), 0, 1
        )
        indices = np.floor(normalized * 255 + 0.5).astype(int)
        palette = np.empty((256, 4), dtype=np.uint8)
        for index in np.unique(indices):
            color = dvz.DvzColor()
            if not dvz.dvz_colormap_builtin_sample(
                selector, float(index) / 255, ctypes.byref(color)
            ):
                raise RuntimeError('native built-in colormap sample failed')
            palette[index] = (color.r, color.g, color.b, color.a)
        colors = palette[indices]
        colors[~finite] = missing
        return owned(colors, np.uint8)

    def close(self):
        """Release every owned visual without destroying the borrowed scene."""
        if self._closed:
            return
        errors = []
        for layer in reversed(self.layers):
            try:
                layer._close()
            except Exception as error:
                errors.append(error)
        for recording in self.recordings:
            recording._closed = True
        self._layers.clear()
        self._recordings.clear()
        self._closed = True
        if errors:
            raise RuntimeError('failed to release layer resources') from errors[0]
