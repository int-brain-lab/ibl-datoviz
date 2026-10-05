"""Retained GUI rows and their explicitly owned native widget handles.

Datoviz copies row/column data at the setters. These records support selection
translation; native callbacks and borrowed GUI control buffers stay with viewers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .ontology import ROOT_PARENT, encode_region_key

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True)
class TableRows:
    """Stable native row keys and their signed mapped region identities."""

    keys: NDArray[np.uint64]
    region_ids: NDArray[np.int64]


@dataclass(frozen=True)
class TreeRows:
    """Visible tree row keys and remapped hierarchy parents."""

    keys: NDArray[np.uint64]
    region_ids: NDArray[np.int64]
    parents: NDArray[np.uint32]


class GuiWidget:
    """Own one table or tree handle, destroying it at most once."""

    def __init__(self, dvz, kind, rows):
        self.dvz = dvz
        self.kind = kind
        self.rows = rows
        self.handle = None

    @staticmethod
    def check(result, action):
        """Reject failed native setters."""
        if result != 0:
            raise RuntimeError(f'Datoviz {action} failed')

    def close(self):
        """Release the independent widget handle exactly once."""
        if self.handle is not None:
            handle, self.handle = self.handle, None
            getattr(self.dvz, f'dvz_gui_{self.kind}_destroy')(handle)

    def selected_keys(self):
        """Read native selection without keeping a second selection model."""
        return getattr(self.dvz, f'dvz_gui_{self.kind}_get_selection')(self.handle)

    def set_selection(self, keys, action):
        """Upload authoritative selection keys and reveal a single tree row."""
        self.check(
            getattr(self.dvz, f'dvz_gui_{self.kind}_set_selection')(self.handle, keys), action
        )
        if self.kind == 'tree' and len(keys) == 1:
            self.check(
                self.dvz.dvz_gui_tree_reveal(self.handle, int(keys[0])),
                'atlas ontology selection reveal',
            )


def create_probe_table(dvz, data, mapped_ids, region_labels, colors):
    """Prepare rows and upload a new independently owned widget."""
    owner = GuiWidget(dvz, 'table', TableRows(data.site_ids, mapped_ids))
    try:
        columns = [
            {
                'column_id': 1,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Site',
            },
            {
                'column_id': 2,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': 'DV (µm)',
                'format': '%.0f',
            },
            {
                'column_id': 3,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.value_name,
                'format': '%.3f',
            },
            {
                'column_id': 4,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Region',
            },
            {'column_id': 5, 'type': dvz.DVZ_GUI_TABLE_COLUMN_COLOR, 'title': ''},
        ]
        owner.handle = dvz.dvz_gui_table(
            b'ibl_probe_sites',
            columns,
            dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER | dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not owner.handle:
            owner.handle = None
            raise RuntimeError('dvz_gui_table() failed')
        setters = (
            (
                dvz.dvz_gui_table_set_rows,
                (owner.handle, data.site_ids, dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE),
                'probe table rows',
            ),
            (
                dvz.dvz_gui_table_set_column_text,
                (owner.handle, 1, data.labels),
                'probe table labels',
            ),
            (
                dvz.dvz_gui_table_set_column_double,
                (owner.handle, 2, data.positions_um[:, 2].astype(np.float64)),
                'probe table depth',
            ),
            (
                dvz.dvz_gui_table_set_column_double,
                (owner.handle, 3, data.values),
                'probe table values',
            ),
            (
                dvz.dvz_gui_table_set_column_text,
                (owner.handle, 4, region_labels),
                'probe table regions',
            ),
            (
                dvz.dvz_gui_table_set_column_color,
                (owner.handle, 5, colors),
                'probe table colors',
            ),
        )
        for setter, args, action in setters:
            owner.check(setter(*args), action)
    except BaseException:
        owner.close()
        raise
    return owner


def create_region_table(dvz, data, region_ids, values, weights, labels, colors):
    """Prepare rows and upload a new independently owned widget."""
    keys = np.ascontiguousarray(region_ids.view(np.uint64))
    owner = GuiWidget(dvz, 'table', TableRows(keys, region_ids))
    try:
        columns = [
            {
                'column_id': 1,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_TEXT,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SEARCHABLE
                | dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_STRETCH,
                'title': 'Region',
            },
            {
                'column_id': 2,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.value_name,
                'format': '%.3f',
            },
            {
                'column_id': 3,
                'type': dvz.DVZ_GUI_TABLE_COLUMN_DOUBLE,
                'flags': dvz.DVZ_GUI_TABLE_COLUMN_FLAGS_SORTABLE,
                'title': data.weight_name,
                'format': '%.0f',
            },
            {'column_id': 4, 'type': dvz.DVZ_GUI_TABLE_COLUMN_COLOR, 'title': ''},
        ]
        owner.handle = dvz.dvz_gui_table(
            b'ibl_region_values',
            columns,
            dvz.DVZ_GUI_DATA_WIDGET_FLAGS_FILTER | dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not owner.handle:
            owner.handle = None
            raise RuntimeError('dvz_gui_table() failed')
        setters = (
            (
                dvz.dvz_gui_table_set_rows,
                (owner.handle, keys, dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE),
                'region table rows',
            ),
            (
                dvz.dvz_gui_table_set_column_text,
                (owner.handle, 1, labels),
                'region table labels',
            ),
            (
                dvz.dvz_gui_table_set_column_double,
                (owner.handle, 2, values),
                'region table values',
            ),
            (
                dvz.dvz_gui_table_set_column_double,
                (owner.handle, 3, weights),
                'region table weights',
            ),
            (
                dvz.dvz_gui_table_set_column_color,
                (owner.handle, 4, colors),
                'region table colors',
            ),
        )
        for setter, args, action in setters:
            owner.check(setter(*args), action)
    except BaseException:
        owner.close()
        raise
    return owner


def create_region_tree(dvz, model, root_acronym, filter_text):
    """Prepare rows and upload a new independently owned widget."""
    row_indices = model.subtree_row_indices(root_acronym)
    old_to_new = {int(old): new for new, old in enumerate(row_indices)}
    parents = np.ascontiguousarray(
        [
            ROOT_PARENT
            if int(model.parents[old]) == ROOT_PARENT or int(model.parents[old]) not in old_to_new
            else old_to_new[int(model.parents[old])]
            for old in row_indices
        ],
        dtype=np.uint32,
    )
    labels = tuple(model.acronyms[index] for index in row_indices)
    names = tuple(model.names[index] for index in row_indices)
    owner = GuiWidget(
        dvz, 'tree', TreeRows(model.keys[row_indices], model.region_ids[row_indices], parents)
    )
    try:
        owner.handle = dvz.dvz_gui_tree(
            b'ibl_atlas_ontology',
            dvz.DVZ_GUI_DATA_WIDGET_FLAGS_MULTI_SELECT,
        )
        if not owner.handle:
            owner.handle = None
            raise RuntimeError('dvz_gui_tree() failed')
        owner.check(
            dvz.dvz_gui_tree_set_rows(
                owner.handle,
                model.keys[row_indices],
                parents,
                labels,
                names,
                dvz.DVZ_GUI_DATA_SET_FLAGS_RESET_STATE,
            ),
            'atlas ontology rows',
        )
        owner.check(
            dvz.dvz_gui_tree_set_swatches(owner.handle, model.colors[row_indices]),
            'atlas ontology colors',
        )
        if filter_text:
            owner.check(
                dvz.dvz_gui_tree_set_filter(owner.handle, filter_text),
                'atlas ontology filter restore',
            )
        styles = []
        for region_id, member in zip(
            model.region_ids[row_indices], model.mapping_members[row_indices], strict=True
        ):
            if member:
                continue
            style = dvz.dvz_gui_data_style()
            style.flags = dvz.DVZ_GUI_DATA_STYLE_FLAGS_FOREGROUND
            style.row_key = encode_region_key(int(region_id))
            style.foreground = dvz.DvzColor(118, 126, 137, 255)
            styles.append(style)
        if styles:
            owner.check(
                dvz.dvz_gui_tree_set_styles(owner.handle, styles),
                'atlas ontology hierarchy styles',
            )
        owner.check(
            dvz.dvz_gui_tree_expand_to_depth(owner.handle, 3),
            'atlas ontology expansion',
        )
    except BaseException:
        owner.close()
        raise
    return owner
