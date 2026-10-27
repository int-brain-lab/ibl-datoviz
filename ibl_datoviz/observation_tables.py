"""Viewer-owned observation tables with exact attachment identity translation."""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from dataclasses import dataclass
from threading import get_ident

import numpy as np

from .gui_data import GuiWidget
from .payloads import Paths


@dataclass(frozen=True)
class ObservationRows:
    """Positive widget keys mapped explicitly to complete immutable references."""

    keys: np.ndarray
    refs: tuple


@dataclass(frozen=True)
class ObservationTable:
    """One retained table borrowing an attached scientific layer."""

    layer: object
    widget: GuiWidget

    @property
    def refs(self):
        """Return all references, including hidden and unpositioned rows."""
        return self.widget.rows.refs

    @property
    def keys(self):
        """Return widget-local keys, which are never scientific IDs."""
        return self.widget.rows.keys

    def selection_keys(self, refs):
        """Translate exact references into the widget's independent row namespace."""
        selected = set(refs)
        return np.asarray(
            [key for key, ref in zip(self.keys, self.refs, strict=True) if ref in selected],
            dtype=np.uint64,
        )

    def selected_refs(self):
        """Reject unknown native keys rather than interpreting them as IDs."""
        if self.widget.handle is None:
            raise RuntimeError('observation table is removed or closed')
        registry = getattr(self.layer, '_registry', None)
        owner = getattr(getattr(registry, 'viewer', None), '_owner_thread', None)
        if owner is not None and get_ident() != owner:
            raise RuntimeError('observation table reads require the viewer owning thread')
        lookup = dict(zip(map(int, self.keys), self.refs, strict=True))
        keys = self.widget.selected_keys()
        if any(int(key) not in lookup for key in keys):
            raise ValueError('observation table returned an unknown row key')
        return tuple(dict.fromkeys(lookup[int(key)] for key in keys))


def _columns(dvz, layer):
    payload = layer.payload
    text_flags = (
        dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
        | dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE
        | dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH
    )
    columns = []
    values = []

    def add(title, data, *, numeric=False):
        columns.append(
            {
                'column_id': len(columns) + 1,
                'type': (
                    dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE if numeric else dvz.DVZ_GUI_TABLE_COLUMN_TEXT
                ),
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE if numeric else text_flags,
                'title': title,
                **({'format': '%.9g'} if numeric else {}),
            }
        )
        values.append((numeric, data))

    add(
        'ID',
        tuple(repr(value) if isinstance(value, str) else str(value) for value in payload.ids),
    )
    add(
        'Type',
        tuple('string' if isinstance(value, str) else 'integer' for value in payload.ids),
    )
    add('XYZ?', tuple('yes' if value else 'no' for value in payload.positioned))
    if isinstance(payload, Paths):
        add(
            'Vertices',
            np.asarray([len(path) for path in payload.positions_um], np.float64),
            numeric=True,
        )
    else:
        scalar, status = _scalar_columns(getattr(layer, 'scalar_encoding', None), len(layer.refs))
        add('Value', scalar, numeric=True)
        add('Value status', status)
        for axis, name in enumerate(('ML (µm)', 'AP (µm)', 'DV (µm)')):
            add(name, np.ascontiguousarray(payload.positions_um[:, axis]), numeric=True)
    for title, data in _source_fields(layer):
        if len(set(data)) > 1:
            add(title, data)
    regions = getattr(payload, 'allen_region_ids', None)
    if regions is not None:
        add('Allen region ID', tuple(str(value) for value in regions))
    return columns, values


def _scalar_columns(encoding, count):
    if encoding is None:
        return np.full(count, np.nan), ('No scalar encoding',) * count
    return encoding.values, tuple(
        'Available' if np.isfinite(value) else 'Missing (NaN)' for value in encoding.values
    )


def _source_fields(layer):
    keys = layer.payload.observation_keys
    if keys is None:
        return ()
    fields = [
        (title, tuple(str(getattr(key, attribute)) for key in keys))
        for title, attribute in (('Recording', 'recording_id'), ('Population', 'population'))
    ]
    fields.extend(
        (title, tuple(str(getattr(key.source, attribute)) for key in keys))
        for title, attribute in (
            ('Provider', 'provider'),
            ('Dataset', 'dataset'),
            ('Version', 'version'),
            ('Content SHA256', 'content_sha256'),
        )
    )
    return tuple(fields)


def _create_table(dvz, layer):
    keys = np.frombuffer(
        np.arange(1, len(layer.refs) + 1, dtype=np.uint64).tobytes(), dtype=np.uint64
    )
    widget = GuiWidget(dvz, 'table', ObservationRows(keys, layer.refs))
    try:
        columns, values = _columns(dvz, layer)
        attachment = layer.refs[0].attachment_id if layer.refs else str(id(layer))
        widget.handle = dvz.dvz_gui_table(
            f'ibl_observations_{attachment}'.encode(),
            columns,
            dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER | dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not widget.handle:
            widget.handle = None
            raise RuntimeError('dvz_gui_table() failed')
        widget.check(
            dvz.dvz_gui_table_set_rows(
                widget.handle,
                keys,
                dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
            ),
            'observation table rows',
        )
        for index, (numeric, data) in enumerate(values, 1):
            setter = (
                dvz.dvz_gui_table_set_column_double
                if numeric
                else dvz.dvz_gui_table_set_column_text
            )
            widget.check(setter(widget.handle, index, data), 'observation table column')
    except BaseException:
        widget.close()
        raise
    return ObservationTable(layer, widget)


class ObservationTables:
    """Own lazy native tables; the selection controller remains authoritative."""

    def __init__(self, viewer):
        self.viewer = viewer
        self._tables = []
        self._opened = ctypes.c_bool(False)
        self._active = 0

    @property
    def tables(self):
        """Return retained table owners in creation order."""
        return tuple(self._tables)

    @property
    def visible(self):
        """Return whether the owned observation window is currently requested."""
        return bool(self._tables and self._opened.value)

    def show(self, layer):
        """Open one attached layer's full population without loading signal data."""
        self.viewer.selection._check_mutation()
        if not any(candidate is layer for candidate in self.viewer.layers):
            raise ValueError('table layer is foreign, removed or unknown')
        for table in self._tables:
            if table.layer is layer:
                self._opened.value = True
                self._active = self._tables.index(table)
                return table
        table = _create_table(self.viewer.dvz, layer)
        try:
            table.widget.set_selection(
                table.selection_keys(self.viewer.selection.observations),
                'observation table initial selection',
            )
        except BaseException:
            table.widget.close()
            raise
        self._tables.append(table)
        self._opened.value = True
        self._active = len(self._tables) - 1
        return table

    def _set_selection(self, refs):
        """Upload atomically, restoring authoritative state after partial failure."""
        self.viewer.selection._check_mutation()
        refs = tuple(refs)
        registry = getattr(self.viewer, '_layer_registry', None)
        if registry is not None and any(not registry.contains(ref) for ref in refs):
            raise ValueError('observation reference is foreign, removed or unknown')
        previous = self.viewer.selection.observations
        try:
            for table in self._tables:
                table.widget.set_selection(
                    table.selection_keys(refs), 'observation table selection'
                )
        except BaseException:
            self._restore(previous)
            raise

    @contextmanager
    def _updating_encoding(self, layer, encoding):
        """Keep retained columns and native colors atomic, including partial writes."""
        table = next((table for table in self._tables if table.layer is layer), None)
        if table is None or encoding is layer.scalar_encoding:
            yield
            return

        def upload(current):
            values, status = _scalar_columns(current, len(table.refs))
            dvz, widget = self.viewer.dvz, table.widget
            widget.check(
                dvz.dvz_gui_table_set_column_double(widget.handle, 4, values),
                'observation scalar values',
            )
            widget.check(
                dvz.dvz_gui_table_set_column_text(widget.handle, 5, status),
                'observation scalar status',
            )

        try:
            upload(encoding)
            yield
        except BaseException:
            if table.widget.handle is not None:
                try:
                    upload(layer.scalar_encoding)
                except BaseException as error:
                    self.viewer.close()
                    raise RuntimeError(
                        'observation scalar rollback failed; viewer closed'
                    ) from error
            raise

    def _restore(self, refs):
        try:
            for table in self._tables:
                table.widget.set_selection(
                    table.selection_keys(refs), 'observation table selection rollback'
                )
        except BaseException as error:
            self.viewer.close()
            raise RuntimeError('observation table rollback failed; viewer closed') from error

    def _remove(self, refs):
        """Close tables whose attachments are removed before publishing selection."""
        removed = set(refs)
        for table in tuple(self._tables):
            if any(ref in removed for ref in table.refs) or table.layer._closed:
                self._tables.remove(table)
                table.widget.close()

    def draw(self, gui):
        """Draw nonmodal tables and route native row selection through the controller."""
        if not self.visible:
            return
        visible = self.viewer.dvz.dvz_gui_begin(
            gui,
            b'Observations',
            ctypes.byref(self._opened),
            0,
        )
        try:
            if visible:
                self._active = min(self._active, len(self._tables) - 1)
                active = ctypes.c_int(self._active)
                labels = []
                for i, table in enumerate(self._tables):
                    group = getattr(table.layer, '_group', None)
                    scope = f' ({group.recording.insertion_id[:8]})' if group is not None else ''
                    labels.append(f'{i + 1}: {table.layer.name}{scope}'.encode())
                items = (ctypes.c_char_p * len(labels))(*labels)
                if self.viewer.dvz.dvz_gui_combo(
                    gui,
                    b'Layer##observations',
                    ctypes.byref(active),
                    items,
                    len(labels),
                ):
                    self._active = active.value
                table = self._tables[self._active]
                self._draw_header(gui, table)
                self._draw_table(gui, table)
        finally:
            self.viewer.dvz.dvz_gui_end(gui)

    def _draw_header(self, gui, table):
        from .layer_gui import _text, draw_scalar_legend  # noqa: PLC0415

        text = self.viewer.dvz.dvz_gui_text
        meaning = table.layer.payload.provenance.get('position_meaning')
        text(gui, b'Original IDs (text sort); XYZ? = coordinates available')
        if getattr(table.layer, 'scalar_encoding', None) is not None:
            draw_scalar_legend(self.viewer, gui, table.layer, 'observations', compact=True)
        elif not isinstance(table.layer.payload, Paths):
            text(gui, b'No active scalar encoding; Value = NaN (not a measured zero).')
        fields = [
            (title, data[0])
            for title, data in _source_fields(table.layer)
            if data and len(set(data)) == 1
        ]
        group = getattr(table.layer, '_group', None)
        if group is not None:
            text(gui, f'Recording: {group.recording.insertion_id}'.encode())
            status = group.recording.provenance.get('source_validation_status', 'unspecified')
            text(gui, f'Metadata source validation: {status}'.encode())
        description = table.layer.payload.provenance.get('scalar_description')
        missing = table.layer.payload.provenance.get('scalar_missing_meaning')
        if (fields or meaning or description or missing or group is not None) and (
            self.viewer.dvz.dvz_gui_collapsing_header(gui, b'Source and provenance', 0)
        ):
            # Provenance is available on demand without crowding the observation rows.
            if meaning:
                _text(self.viewer, gui, meaning)
            if description:
                _text(self.viewer, gui, f'Quantity: {description}')
            if missing:
                _text(self.viewer, gui, missing)
            for title, value in fields:
                _text(self.viewer, gui, f'{title}: {value}')
            if group is not None:
                _text(self.viewer, gui, f'Session: {group.recording.session_id}')

    def _draw_table(self, gui, table):
        previous = self.viewer.selection.observations
        try:
            result, events, dropped = self.viewer.dvz.dvz_gui_table_draw(gui, table.widget.handle)
            GuiWidget.check(result, 'observation table draw')
            if dropped:
                raise RuntimeError('observation table input batch dropped')
            if any(
                event.type == self.viewer.dvz.DVZ_GUI_DATA_EVENT_SELECTION_CHANGED
                for event in events
            ):
                selected = table.selected_refs()
                own_refs = set(table.refs)
                other = tuple(ref for ref in previous if ref not in own_refs)
                self.viewer.selection.set_observations((*other, *selected))
        except BaseException:
            # Native input mutates its selection before scientific state is committed.
            self._restore(previous)
            raise

    def _close(self):
        """Destroy native widgets before their borrowing scene is destroyed."""
        tables, self._tables = self._tables, []
        for table in reversed(tables):
            table.widget.close()
