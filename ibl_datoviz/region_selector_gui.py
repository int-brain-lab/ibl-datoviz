"""Controlled native presentation of the shared IBL region-browser model."""

from __future__ import annotations

import math

import numpy as np

from .ontology import ROOT_PARENT, decode_region_key, encode_region_key
from .region_selector import RegionSelector, SelectorRegion, highlight_spans


def selector_from_tree(tree, root, previous=None):
    """Adapt canonical inventory while retaining browser navigation across mappings."""
    indices = tree.subtree_row_indices(root)
    included = set(int(index) for index in indices)
    regions = []
    for index in indices:
        parent = int(tree.parents[index])
        regions.append(
            SelectorRegion(
                str(int(tree.region_ids[index])),
                str(int(tree.region_ids[parent]))
                if parent != ROOT_PARENT and parent in included
                else None,
                int(tree.region_ids[index]),
                tree.acronyms[index],
                tree.names[index],
                bool(tree.mapping_members[index]),
            )
        )
    initial = None
    if previous is not None:
        initial = {
            'query': previous.query,
            'collapsed': previous.collapsed,
            'order': previous.requested_order,
            'multiple': previous.multiple,
            'focus': previous.focus,
        }
    return RegionSelector(regions, initial)


def signed_selection(selector, committed):
    """Preserve hemispheres of surviving host IDs; new browser IDs are canonical left."""
    logical = {
        abs(selector.by_id[key].atlas_id) for key in selector.selected if key in selector.by_id
    }
    result = [region_id for region_id in committed if abs(region_id) in logical]
    retained = {abs(region_id) for region_id in result}
    result.extend(
        -abs(selector.by_id[key].atlas_id)
        for key in selector.selected
        if key in selector.by_id and abs(selector.by_id[key].atlas_id) not in retained
    )
    return tuple(dict.fromkeys(result))


class RegionSelectorGui:
    """Own browser state, not physical scene selection or the widget lifetime."""

    def __init__(self, widget, model, *, value_name='Value'):
        self.widget = widget
        self.model = model
        self.value_name = value_name
        self._uploaded = {}
        self.upload(model)

    def candidate(self):
        """Copy mutable state before collecting a frame's intents."""
        return self.model.copy()

    @staticmethod
    def sync_selection(model, region_ids, *, preserve_anchor=False):
        """Project signed host identities onto canonical browser IDs."""
        available = {abs(region.atlas_id): region.id for region in model.regions}
        model.set_selected(
            [available[abs(region_id)] for region_id in region_ids if abs(region_id) in available],
            preserve_anchor=preserve_anchor,
        )

    def _setter(self, part, signature, call):
        if self._uploaded.get(part) == signature:
            return
        try:
            self.widget.check(call(), f'region selector {part}')
        except Exception:
            # A failed setter may have partially mutated its native destination.
            self._uploaded.clear()
            raise
        self._uploaded[part] = signature

    def upload(self, model):
        """Upload changed copied data without stealing focus from GUI controls."""
        dvz, handle = self.widget.dvz, self.widget.handle
        rows = model.visible_rows()
        projection = tuple(
            (
                row.region.atlas_id,
                row.depth,
                row.branch,
                row.region.mapping_member and not row.branch,
            )
            for row in rows
        )
        self._setter(
            'projection',
            projection,
            lambda: dvz.dvz_gui_tree_set_projection(
                handle,
                np.array([encode_region_key(row[0]) for row in projection], dtype=np.uint64),
                np.array([row[1] for row in projection], dtype=np.uint32),
                np.array([row[2] for row in projection], dtype=np.bool_),
                np.array([row[3] for row in projection], dtype=np.bool_),
            ),
        )
        expanded = tuple(
            encode_region_key(row.region.atlas_id)
            for row in rows
            if row.branch and row.region.id not in model.active_collapsed
        )
        self._setter(
            'expansion',
            expanded,
            lambda: dvz.dvz_gui_tree_set_expanded(handle, np.array(expanded, dtype=np.uint64)),
        )
        # Normalize NaN because tuple equality must not force redundant native uploads.
        values = tuple(
            sorted(
                (key, value if value is not None and math.isfinite(value) else None)
                for key, value in model.values.items()
            )
        )
        signature = (tuple(row.region.id for row in rows), model.query, values, self.value_name)
        self._setter('annotations', signature, lambda: self._annotations(model, rows))
        selected = tuple(
            encode_region_key(model.by_id[key].atlas_id)
            for key in model.selected
            if key in model.by_id
        )
        self._setter(
            'selection',
            selected,
            lambda: dvz.dvz_gui_tree_set_selection(handle, np.array(selected, dtype=np.uint64)),
        )
        visible = {row.region.id for row in rows}
        if getattr(model, '_focus_requested', False) and model.focus in visible:
            self.widget.check(
                dvz.dvz_gui_tree_set_focus(
                    handle, encode_region_key(model.by_id[model.focus].atlas_id)
                ),
                'region selector focus',
            )
            model._focus_requested = False

    def _annotations(self, model, rows):
        dvz = self.widget.dvz
        annotations = []
        for row in rows:
            region = row.region
            annotation = dvz.dvz_gui_tree_annotation()
            annotation.row_key = encode_region_key(region.atlas_id)
            value = model.values.get(region.id)
            finite = value is not None and math.isfinite(value)
            annotation.value_text = (
                (f'{value:.3f}' if finite else '—').encode() if model.values else b''
            )
            annotation.flags = (
                0 if finite or not model.values else dvz.DVZ_GUI_TREE_ANNOTATION_FLAGS_MISSING
            )
            lineage, parent = [], region.parent_id
            while parent is not None:
                ancestor = model.by_id[parent]
                lineage.append(ancestor.acronym)
                parent = ancestor.parent_id
            tooltip = f'{region.acronym} — {region.name}\nAllen ID: {abs(region.atlas_id)}'
            if lineage:
                tooltip += '\n' + ' / '.join([*reversed(lineage), region.acronym])
            if model.values:
                tooltip += f'\n{self.value_name}: ' + (f'{value:.3f}' if finite else 'missing')
            annotation.tooltip = tooltip.encode()
            for field, text in (('label', region.acronym), ('secondary', region.name)):
                spans = highlight_spans(text, model.query)
                packed = (dvz.DvzGuiTreeTextSpan * len(spans))(
                    *(
                        dvz.DvzGuiTreeTextSpan(
                            len(text[:start].encode()), len(text[start:end].encode())
                        )
                        for start, end in spans
                    )
                )
                setattr(annotation, f'{field}_span_count', len(spans))
                setattr(annotation, f'{field}_spans', packed)
            annotations.append(annotation)
        return dvz.dvz_gui_tree_set_annotations(self.widget.handle, annotations)

    def commit(self, candidate):
        """Restore the old native presentation if any copied setter fails."""
        try:
            self.upload(candidate)
        except Exception:
            self.upload(self.model)
            raise
        self.model = candidate

    def controls(self, gui, candidate, filter_buffer, sidebar):
        """Collect two compact rows without changing committed selector state."""
        dvz = self.widget.dvz
        scale = sidebar.viewer.ui_scale
        icon_size, gap = 22.0 * scale, 6.0 * scale
        width, _ = sidebar.available(gui)
        dvz.dvz_gui_set_next_item_width(gui, max(1.0, width - icon_size - gap))
        if dvz.dvz_gui_input_text_with_hint(
            gui,
            b'##ibl_atlas_filter',
            b'Search name or acronym',
            filter_buffer,
            len(filter_buffer),
        ):
            candidate.set_query(filter_buffer.value.decode())
        dvz.dvz_gui_same_line(gui, 0.0, gap)
        if sidebar.icon(
            gui, b'##ibl_clear_search', 'CLEAR', 'Clear search', disabled=not candidate.query
        ):
            filter_buffer.value = b''
            candidate.set_query('')
        count = (
            len(candidate._context()[0] & {row.region.id for row in candidate.hierarchy})
            if candidate.query
            else len(candidate.hierarchy)
        )
        dvz.dvz_gui_text(gui, f'{count} regions'.encode())
        # Keep the inverse tree actions visually paired. Persistent multiselect
        # is a separate mode, with a larger gap before its button.
        dvz.dvz_gui_same_line(gui, 0.0, gap)
        if sidebar.icon(gui, b'##ibl_collapse_all', 'COLLAPSE', 'Collapse all'):
            candidate.set_all_expanded(False)
        dvz.dvz_gui_same_line(gui, 0.0, 2.0 * scale)
        if sidebar.icon(gui, b'##ibl_expand_all', 'EXPAND', 'Expand all'):
            candidate.set_all_expanded(True)
        dvz.dvz_gui_same_line(gui, 0.0, 16.0 * scale)
        if sidebar.icon(
            gui,
            b'##ibl_multiple',
            'MULTISELECT',
            'Multiple selection (Ctrl/Cmd also adds)',
            active=candidate.multiple,
        ):
            candidate.multiple = not candidate.multiple
        label = {
            'anatomy': 'Anatomy order',
            'value-asc': 'Value ascending',
            'value-desc': 'Value descending',
        }[candidate.requested_order]
        finite_values = any(
            value is not None and math.isfinite(value) for value in candidate.values.values()
        )
        tooltip = 'Anatomy order (search)' if candidate.query else label
        if candidate.values:
            tooltip += f' / {self.value_name} (left hemisphere)'
        if not finite_values:
            return
        dvz.dvz_gui_same_line(gui, 0.0, gap)
        if sidebar.icon(gui, b'##ibl_order', 'SORT', tooltip, disabled=bool(candidate.query)):
            orders = ('anatomy', 'value-desc', 'value-asc')
            candidate.apply(
                {'op': 'order', 'value': orders[(orders.index(candidate.requested_order) + 1) % 3]}
            )

    def intents(self, candidate, events):
        """Translate generic widget input into browser-local semantics."""
        dvz = self.widget.dvz
        key_names = {
            getattr(dvz, f'DVZ_KEY_{native}'): browser
            for native, browser in (
                ('UP', 'ArrowUp'),
                ('DOWN', 'ArrowDown'),
                ('LEFT', 'ArrowLeft'),
                ('RIGHT', 'ArrowRight'),
                ('HOME', 'Home'),
                ('END', 'End'),
                ('ENTER', 'Enter'),
                ('SPACE', ' '),
            )
        }
        # Native focus observations describe the row focused before this draw
        # applies host navigation; settle them before processing key intents.
        events = sorted(
            events, key=lambda event: event.type != dvz.DVZ_GUI_DATA_EVENT_FOCUS_CHANGED
        )
        selection_intent = None
        for event in events:
            effect = None
            region_id = str(decode_region_key(event.row_key)) if event.row_key else None
            flags = int(event.flags)
            modifiers = {
                'ctrl': bool(flags & 2),
                'meta': bool(flags & 8),
                'shift': bool(flags & 1),
            }
            if event.type == dvz.DVZ_GUI_DATA_EVENT_ROW_CLICKED:
                effect = candidate.activate(region_id, **modifiers)
            elif event.type == dvz.DVZ_GUI_DATA_EVENT_DISCLOSURE_CLICKED:
                candidate.toggle_branch(region_id)
            elif event.type == dvz.DVZ_GUI_DATA_EVENT_KEY_PRESSED and event.detail in key_names:
                candidate._focus_requested = True
                effect = candidate.navigate(
                    key_names[event.detail], ctrl=modifiers['ctrl'], meta=modifiers['meta']
                )
                candidate.apply({'op': 'hover', 'id': candidate.focus})
            elif event.type == dvz.DVZ_GUI_DATA_EVENT_FOCUS_CHANGED:
                if event.detail:
                    candidate.apply({'op': 'focus', 'id': region_id})
                    candidate.apply({'op': 'hover', 'id': region_id})
                elif candidate.hover == region_id:
                    candidate.apply({'op': 'hover', 'id': None})
            elif event.type == dvz.DVZ_GUI_DATA_EVENT_HOVER_CHANGED:
                if event.detail:
                    candidate.apply({'op': 'hover', 'id': region_id})
                elif candidate.hover == region_id:
                    candidate.apply({'op': 'hover', 'id': None})
            if effect is not None:
                selection_intent = effect
        return selection_intent
