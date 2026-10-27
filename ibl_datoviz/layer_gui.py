"""Scientist-facing layer inspection over authoritative retained handles."""

import ctypes
import textwrap
import weakref

import numpy as np

from .layers import _color


def _available(viewer, gui):
    size = (ctypes.c_float * 2)()
    viewer.dvz.dvz_gui_content_avail(gui, size)
    return tuple(size)


def _text(viewer, gui, message, *, columns=None):
    width = max(12, int(_available(viewer, gui)[0] / (8 * viewer.ui_scale)))
    if columns is not None:
        width = min(width, columns)
    for line in textwrap.wrap(str(message), width):
        viewer.dvz.dvz_gui_text(gui, line.encode())


def _full_width(viewer, gui):
    viewer.dvz.dvz_gui_set_next_item_width(gui, max(1, _available(viewer, gui)[0] - 1))


def _swatch(viewer, gui, color, key):
    control = (ctypes.c_float * 4)(*(np.asarray(color) / 255))
    viewer.dvz.dvz_gui_color_edit4(
        gui,
        f'##legend_{key}'.encode(),
        control,
        (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5) | (1 << 9),
    )


def _noun(layer, *, plural=False):
    default = 'path' if layer.capabilities.width_px else 'point'
    key = 'observation_label_plural' if plural else 'observation_label'
    return str(layer.payload.provenance.get(key, default + 's' if plural else default))


def draw_scalar_legend(viewer, gui, layer, key, *, compact=False, title=True):
    """Draw read-only scalar samples and missingness, without selection or settings."""
    data = layer.scalar_encoding
    if data is None:
        return
    dvz = viewer.dvz
    if title:
        _text(viewer, gui, f'{data.name} ({data.units})')
    samples = np.linspace(*data.limits, 3)
    colors = layer._registry._scalar_colors(
        samples, data.cmap, np.asarray(data.limits), data.missing_color
    )
    for index, (value, color) in enumerate(zip(samples, colors, strict=True)):
        if index:
            dvz.dvz_gui_same_line(gui, 0, 8 * viewer.ui_scale)
        _swatch(viewer, gui, color, f'{key}_{index}')
        dvz.dvz_gui_same_line(gui, 0, 4 * viewer.ui_scale)
        dvz.dvz_gui_text(gui, f'{value:.3g}'.encode())
    if compact:
        return
    missing = data._counts[1]
    if missing:
        _swatch(viewer, gui, _color(data.missing_color), f'{key}_missing')
        dvz.dvz_gui_same_line(gui, 0, 4 * viewer.ui_scale)
        dvz.dvz_gui_text(gui, f'{missing} missing values'.encode())
        meaning = layer.payload.provenance.get('scalar_missing_meaning')
        if meaning:
            _text(viewer, gui, meaning)
        elif _color(data.missing_color)[3] == 0:
            _text(viewer, gui, 'Missing values are not drawn; their data rows remain available.')


def draw_source_details(viewer, gui, layer):
    """Keep full precision, exact source identity and scientific methods accessible."""
    from .observation_tables import _source_fields  # noqa: PLC0415

    data = layer.scalar_data
    _text(viewer, gui, 'Layer: ' + layer.name)
    if data is not None:
        _text(viewer, gui, f'{data.name} ({data.units})')
        _text(
            viewer,
            gui,
            f'Color limits: {data.limits[0]:.12g} to {data.limits[1]:.12g}; '
            f'{data.cmap}. {data._counts[2]} below, {data._counts[3]} above. '
            'Only colors are clipped; values are unchanged.',
        )
    for key in (
        'scalar_description',
        'scalar_missing_meaning',
        'position_meaning',
        'color_limits_meaning',
    ):
        if layer.payload.provenance.get(key):
            _text(viewer, gui, layer.payload.provenance[key])
    for title, values in _source_fields(layer):
        if values:
            value = values[0] if len(set(values)) == 1 else 'Varies by observation'
            _text(viewer, gui, f'{title}: {value}')
    group = getattr(layer, '_group', None)
    if group is not None:
        _text(viewer, gui, f'Session: {group.recording.session_id}')
        status = group.recording.provenance.get('source_validation_status', 'unspecified')
        _text(viewer, gui, f'Source validation: {status}')
    selected = set(viewer.selection.observations)
    for index, ref in enumerate(layer.refs):
        if ref not in selected:
            continue
        _text(viewer, gui, f'Original ID: {ref.original_id!r} ({type(ref.original_id).__name__})')
        if data is not None:
            _text(viewer, gui, f'Value: {data.values[index]:.17g} {data.units}')
        if not layer.capabilities.width_px:
            xyz = layer.payload.positions_um[index]
            _text(viewer, gui, 'ML/AP/DV (um): ' + ', '.join(f'{v:.12g}' for v in xyz))
        if ref.source_key is not None:
            _text(viewer, gui, f'Source observation: {ref.source_key}')


class LayerPanel:
    """Own inspection focus only; all scientific mutations use the shared handles."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._active = None
        self.error = ''

    def active_layer(self):
        """Prune removed attachments without retaining their resources."""
        layers = self.viewer.layers
        active = self._active() if self._active is not None else None
        if active not in layers:
            active = layers[0] if layers else None
            self.inspect(active)
        return active

    def inspect(self, layer):
        """Inspecting a layer never selects observations, anatomy or a new camera."""
        if layer is not None and layer not in self.viewer.layers:
            raise ValueError('cannot inspect a foreign or removed layer')
        self._active = None if layer is None else weakref.ref(layer)

    def _action(self, method, *args):
        try:
            method(*args)
        except (ValueError, RuntimeError) as error:
            if getattr(self.viewer, '_closed', False):
                raise
            self.error = str(error)
        else:
            self.error = ''

    def _group_name(self, group):
        if group.name and group.name != group.recording.insertion_id:
            return group.name
        return f'Recording {self.viewer.recordings.index(group) + 1}'

    def _layer_name(self, layer):
        return (
            f'{self._group_name(layer._group)} / {layer.name}'
            if layer._group is not None
            else layer.name
        )

    def _short_label(self, gui, label, *, fraction=1.0):
        width = _available(self.viewer, gui)[0] * fraction
        count = max(8, int(width / (8 * self.viewer.ui_scale)))
        return label if len(label) <= count else label[: count - 1] + '…'

    def _rows(self, gui):
        viewer, dvz = self.viewer, self.viewer.dvz
        grouped = set()
        for index, group in enumerate(viewer.recordings):
            visible = ctypes.c_bool(group.visible)
            if dvz.dvz_gui_checkbox(
                gui,
                f'{self._short_label(gui, self._group_name(group))}##group_{index}'.encode(),
                ctypes.byref(visible),
            ):
                self._action(group.set_visible, visible.value)
            for layer in group.layers:
                grouped.add(layer)
                self._row(gui, layer)
        for layer in viewer.layers:
            if layer not in grouped:
                self._row(gui, layer)

    def _row(self, gui, layer):
        visible = ctypes.c_bool(layer.visible)
        key = id(layer)
        label = (
            self._short_label(gui, layer.name or 'Layer', fraction=0.75) + f' · {len(layer.refs)}'
        )
        if self.viewer.dvz.dvz_gui_checkbox(
            gui, f'{label}##visible_{key}'.encode(), ctypes.byref(visible)
        ):
            self._action(layer.set_visible, visible.value)

    def _color(self, gui, layer):
        viewer, dvz, data = self.viewer, self.viewer.dvz, layer.scalar_data
        if data is not None:
            dvz.dvz_gui_text(gui, b'Color by')
            mode = ctypes.c_int(0 if layer.scalar_encoding is not None else 1)
            items = (ctypes.c_char_p * 2)(f'{data.name} ({data.units})'.encode(), b'Single color')
            _full_width(viewer, gui)
            if dvz.dvz_gui_combo(gui, b'##color_mode', ctypes.byref(mode), items, 2):
                self._action(layer.set_color_mode, ('scalar', 'uniform')[mode.value])
        if layer.scalar_encoding is not None:
            draw_scalar_legend(viewer, gui, layer, 'inspector', title=False)
        else:
            control = (ctypes.c_float * 4)(*(_color(layer._uniform_color) / 255))
            dvz.dvz_gui_text(gui, b'Color')
            dvz.dvz_gui_same_line(gui, 0, 8 * viewer.ui_scale)
            if dvz.dvz_gui_color_edit4(gui, b'##single_color', control, (1 << 5) | (1 << 7)):
                rgba = np.rint(np.clip(list(control), 0, 1) * 255).astype(np.uint8)
                if layer.capabilities.width_px:
                    rgba[3] = 255
                self._action(layer.set_color, '#' + bytes(rgba).hex())
            if data is not None:
                _text(viewer, gui, 'Measurement values remain in the data table.')

    def _selected(self, gui, layer):
        viewer, dvz = self.viewer, self.viewer.dvz
        selected = set(viewer.selection.observations)
        local = [(i, ref) for i, ref in enumerate(layer.refs) if ref in selected]
        dvz.dvz_gui_separator_text(gui, f'Selected {_noun(layer)}'.encode())
        if not local:
            _text(viewer, gui, 'Select in the scene or data table.')
        elif len(local) == 1:
            index, ref = local[0]
            identity = f'{_noun(layer).capitalize()} {ref.original_id!r}'
            dvz.dvz_gui_text(gui, self._short_label(gui, identity, fraction=0.48).encode())
            data = layer.scalar_data
            if data is not None:
                value = data.values[index]
                text = f'{value:.3g} {data.units}' if np.isfinite(value) else 'No measurement'
                dvz.dvz_gui_same_line(gui, _available(viewer, gui)[0] * 0.5, 0)
                dvz.dvz_gui_text(gui, text.encode())
            if not layer.payload.positioned[index]:
                _text(viewer, gui, 'Location unavailable')
        else:
            _text(viewer, gui, f'{len(local)} {_noun(layer, plural=True)} selected')
            if dvz.dvz_gui_button(gui, b'View selected rows'):
                self._action(viewer.tables.show_selected, layer)
        if local and dvz.dvz_gui_button(gui, b'Clear selection##observations'):
            own = set(layer.refs)
            self._action(
                viewer.selection.set_observations,
                tuple(ref for ref in viewer.selection.observations if ref not in own),
            )
        others = len(selected) - len(local)
        if others:
            _text(viewer, gui, f'{others} selected in other layers')

    def _appearance(self, gui, layer):
        viewer, dvz = self.viewer, self.viewer.dvz
        if not dvz.dvz_gui_collapsing_header(gui, b'Appearance', 0):
            return
        caps = layer.capabilities
        label, setter = (
            ('Marker diameter (px)', layer.set_size_px)
            if caps.size_px
            else ('Marker radius (um)', layer.set_radius_um)
            if caps.radius_um
            else ('Path width (px)', layer.set_width_px)
        )
        dvz.dvz_gui_text(gui, label.encode())
        _full_width(viewer, gui)
        size = ctypes.c_float(layer._size)
        if dvz.dvz_gui_slider_float_format(
            gui, b'##marker_size', ctypes.byref(size), 0.5, 100, b'%.1f'
        ):
            self._action(setter, size.value)

    def _warnings(self, gui, layer):
        viewer = self.viewer
        absent = len(layer.refs) - len(layer.positioned_refs)
        if absent:
            _text(viewer, gui, f'{absent} locations unavailable; rows retained in data.')
        if not layer.effective_visible:
            _text(viewer, gui, 'Hidden in the scene; data and selection are retained.')
        group = layer._group
        if group is not None:
            status = group.recording.provenance.get('source_validation_status', 'unspecified')
            if status != 'passed':
                _text(viewer, gui, f'Source validation: {status}')
        picking = getattr(viewer, 'picking', None)
        if picking is not None and picking.unavailable_reason:
            _text(viewer, gui, 'Scene picking unavailable; use the data table.')

    def draw(self, gui):
        """Draw compact visibility rows and properties for one explicitly inspected layer."""
        viewer, dvz = self.viewer, self.viewer.dvz
        layer = self.active_layer()
        if not viewer.layers:
            return
        if len(viewer.layers) > 3:
            height = min(160 * viewer.ui_scale, _available(viewer, gui)[1] * 0.25)
            visible = dvz.dvz_gui_begin_child(gui, b'layer_list', 0, height, 0)
            try:
                if visible:
                    self._rows(gui)
            finally:
                dvz.dvz_gui_end_child(gui)
        else:
            self._rows(gui)
        if len(viewer.layers) > 1:
            dvz.dvz_gui_text(gui, b'Inspect layer')
            _full_width(viewer, gui)
            current = ctypes.c_int(viewer.layers.index(layer))
            labels = (ctypes.c_char_p * len(viewer.layers))(
                *(
                    self._short_label(gui, self._layer_name(candidate)).encode()
                    for candidate in viewer.layers
                )
            )
            if dvz.dvz_gui_combo(
                gui, b'##inspect_layer', ctypes.byref(current), labels, len(labels)
            ):
                self.inspect(viewer.layers[current.value])
                layer = self.active_layer()
        dvz.dvz_gui_separator_text(gui, b'Display')
        self._color(gui, layer)
        self._warnings(gui, layer)
        if dvz.dvz_gui_button(gui, b'View data'):
            self._action(viewer.tables.show, layer)
        self._selected(gui, layer)
        self._appearance(gui, layer)
        if dvz.dvz_gui_collapsing_header(gui, b'Source and methods', 0):
            draw_source_details(viewer, gui, layer)
        if self.error:
            _text(viewer, gui, 'Change failed: ' + self.error)


def _quantity_controls(viewer, gui, quantity):
    dvz = viewer.dvz
    visible = ctypes.c_bool(quantity.visible)
    if dvz.dvz_gui_checkbox(gui, quantity.name.encode(), ctypes.byref(visible)):
        quantity.set_visible(visible.value)
    _text(viewer, gui, f'{quantity.payload.name} ({quantity.payload.units})')
    if dvz.dvz_gui_collapsing_header(gui, b'Regional quantity details', 0):
        _text(viewer, gui, 'Mapping reduction: weighted mean; detailed anatomy colors.')
        values = quantity.payload.values
        _text(
            viewer, gui, f'{int(np.isfinite(values).sum())}/{len(values)} source values available'
        )
        if dvz.dvz_gui_button(gui, b'Remove regional quantity'):
            quantity.remove()


def draw_layers_gui(viewer, gui):
    """Keep default controls focused on visibility, measurement and selected data."""
    registry = getattr(viewer, '_regional_quantities', None)
    quantity = registry.handle if registry is not None else None
    if not viewer.layers and quantity is None:
        return
    visible = viewer.dvz.dvz_gui_begin(gui, b'Layers', None, 0)
    try:
        if visible:
            if quantity is not None:
                _quantity_controls(viewer, gui, quantity)
            if not hasattr(viewer._window, 'layer_panel'):
                viewer._window.layer_panel = LayerPanel(viewer)
            viewer._window.layer_panel.draw(gui)
    finally:
        viewer.dvz.dvz_gui_end(gui)
