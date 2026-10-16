"""Package-level controls over authoritative scientific layer handles."""

import ctypes
import textwrap

import numpy as np


def _text(viewer, gui, message):
    available = (ctypes.c_float * 2)()
    viewer.dvz.dvz_gui_content_avail(gui, available)
    width = max(12, int(available[0] / (9 * viewer.ui_scale)))
    for line in textwrap.wrap(str(message), width):
        viewer.dvz.dvz_gui_text(gui, line.encode())


def _layer_controls(viewer, gui, layer, key):
    dvz = viewer.dvz
    visible = ctypes.c_bool(layer.visible)
    count = f'{len(layer.positioned_refs)}/{len(layer.refs)}'
    if dvz.dvz_gui_checkbox(
        gui,
        f'{layer.name or "Layer"} ({count})##visible_{key}'.encode(),
        ctypes.byref(visible),
    ):
        layer.set_visible(visible.value)
    caps = layer.capabilities
    color = layer._colors[0] / 255 if len(layer.refs) else np.array([0.25, 0.85, 0.98, 1])
    control = (ctypes.c_float * 4)(*color)
    if dvz.dvz_gui_color_edit4(gui, f'Color##{key}'.encode(), control, 0):
        rgba = np.rint(np.clip(list(control), 0, 1) * 255).astype(np.uint8)
        if caps.width_px:
            rgba[3] = 255
        layer.set_color('#' + bytes(rgba).hex())
    label, setter = (
        ('Size (px)', layer.set_size_px)
        if caps.size_px
        else ('Radius (um)', layer.set_radius_um)
        if caps.radius_um
        else ('Width (px)', layer.set_width_px)
    )
    size = ctypes.c_float(layer._size)
    if dvz.dvz_gui_slider_float(
        gui,
        f'{label}##{key}'.encode(),
        ctypes.byref(size),
        0.5,
        100.0,
    ):
        setter(size.value)
    encoding = layer.scalar_encoding
    if encoding is not None:
        _text(
            viewer,
            gui,
            f'{encoding.name} [{encoding.units}], {encoding.cmap}; '
            f'{encoding.limits[0]:g} to {encoding.limits[1]:g}',
        )
    meaning = layer.payload.provenance.get('position_meaning')
    if meaning:
        _text(viewer, gui, meaning)
    if dvz.dvz_gui_button(gui, f'Observation table##{key}'.encode()):
        viewer.tables.show(layer)
    if not layer.refs:
        return
    selected = viewer.selection.observations
    local = [ref for ref in selected if ref in layer.refs]
    current = ctypes.c_int(layer.refs.index(local[0]) + 1 if local else 0)
    labels = (ctypes.c_char_p * (len(layer.refs) + 1))(
        b'None',
        *(str(ref.original_id).encode() for ref in layer.refs),
    )
    if dvz.dvz_gui_combo(
        gui,
        f'Original ID##select_{key}'.encode(),
        ctypes.byref(current),
        labels,
        len(labels),
    ):
        other = tuple(ref for ref in selected if ref not in layer.refs)
        chosen = (layer.refs[current.value - 1],) if current.value else ()
        viewer.selection.set_observations(other + chosen)


def _quantity_controls(viewer, gui, quantity):
    dvz = viewer.dvz
    dvz.dvz_gui_separator_text(gui, quantity.name.encode())
    visible = ctypes.c_bool(quantity.visible)
    if dvz.dvz_gui_checkbox(gui, b'Regional quantity', ctypes.byref(visible)):
        quantity.set_visible(visible.value)
    _text(viewer, gui, f'{quantity.payload.name} [{quantity.payload.units}]')
    _text(viewer, gui, 'Mapping reduction: weighted mean; colors apply to detailed anatomy')
    values = quantity.payload.values
    _text(viewer, gui, f'{int(np.isfinite(values).sum())}/{len(values)} source values available')
    if dvz.dvz_gui_button(gui, b'Remove regional quantity'):
        quantity.remove()


def draw_layers_gui(viewer, gui):
    """Draw retained layer visibility, style and exact-ID selection without I/O."""
    registry = getattr(viewer, '_regional_quantities', None)
    quantity = registry.handle if registry is not None else None
    if not viewer.layers and quantity is None:
        return
    dvz = viewer.dvz
    visible = dvz.dvz_gui_begin(gui, b'Layers', None, 0)
    try:
        if not visible:
            return
        _text(viewer, gui, 'Counts: positioned / complete observations')
        _text(viewer, gui, 'Right-click: select an observation. Left-click: select anatomy.')
        picking = getattr(viewer, 'picking', None)
        if picking is not None:
            reason = picking.unavailable_reason
            if reason:
                _text(viewer, gui, 'Scene observation selection unavailable: ' + reason)
        if quantity is not None:
            _quantity_controls(viewer, gui, quantity)
        child_layers = set()
        for index, group in enumerate(viewer.recordings):
            dvz.dvz_gui_separator_text(gui, group.name.encode())
            control = ctypes.c_bool(group.visible)
            if dvz.dvz_gui_checkbox(
                gui, f'Visible##group_{index}'.encode(), ctypes.byref(control)
            ):
                group.set_visible(control.value)
            _text(viewer, gui, f'Insertion {group.recording.insertion_id}')
            status = group.recording.provenance.get('source_validation_status', 'unspecified')
            _text(viewer, gui, f'Metadata source validation: {status}; signals not requested here')
            for offset, layer in enumerate(group.layers):
                child_layers.add(layer)
                _layer_controls(viewer, gui, layer, f'{index}_{offset}')
        for index, layer in enumerate(viewer.layers):
            if layer not in child_layers:
                dvz.dvz_gui_separator_text(gui, (layer.name or 'Annotations').encode())
                _layer_controls(viewer, gui, layer, f'generic_{index}')
    finally:
        dvz.dvz_gui_end(gui)
