"""IBL region-browser behavior, independent of native widgets and scene state.

The versioned anatomy conformance bundle specifies these transitions. Native
row keys and signed selection translation belong to the GUI adapter.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Literal

Order = Literal['anatomy', 'value-asc', 'value-desc']
_TRIM = (
    '\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680'
    '\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
)


def trim_query(query: str) -> str:
    """Use ECMAScript trim, including BOM and excluding next-line U+0085."""
    return query.strip(_TRIM)


def highlight_spans(text: str, query: str) -> tuple[tuple[int, int], ...]:
    """Return original codepoint ranges even when lowercasing expands text."""
    term = trim_query(query).lower()
    if not term:
        return ()
    lowered = text.lower()
    owners = [index for index, character in enumerate(text) for _ in character.lower()]
    spans: list[tuple[int, int]] = []
    position = lowered.find(term)
    while position >= 0:
        start, end = owners[position], owners[position + len(term) - 1] + 1
        if spans and start < spans[-1][1]:
            spans[-1] = (spans[-1][0], max(end, spans[-1][1]))
        else:
            spans.append((start, end))
        position = lowered.find(term, position + len(term))
    return tuple(spans)


@dataclass(frozen=True)
class SelectorRegion:
    """One semantic catalog row with its original signed identity."""

    id: str
    parent_id: str | None
    atlas_id: int
    acronym: str
    name: str
    mapping_member: bool = True

    @classmethod
    def from_dict(cls, row):
        """Read a contract row without changing identity."""
        return cls(
            row['id'],
            row.get('parentId'),
            row['atlasId'],
            row['acronym'],
            row['name'],
            row.get('mappingMember', True),
        )


@dataclass(frozen=True)
class SelectorRow:
    """Projected display row; semantic parents stay on its region."""

    region: SelectorRegion
    depth: int
    branch: bool


class RegionSelector:
    """Browser-local navigation plus selection proposals supplied to its host.

    Callers can copy this model, apply a frame's input, then accept or reject the
    proposed selection. Committed physical selection remains viewer-owned.
    """

    def __init__(self, regions, initial=None):
        initial = initial or {}
        self.query = trim_query(initial.get('query', ''))
        self.collapsed = set(initial.get('collapsed', ()))
        self.search_collapsed: set[str] = set()
        self.selected = list(dict.fromkeys(initial.get('selected', ())))
        self.requested_order: Order = initial.get('order', 'anatomy')
        self.multiple = initial.get('multiple', False)
        self.focus = initial.get('focus')
        self.anchor = initial.get('anchor') or (self.selected[-1] if self.selected else None)
        self.hover = initial.get('hover')
        self.values = dict(initial.get('values', {}))
        self.regions = tuple(regions)
        self._build_hierarchy()
        # Each stage retains just its latest immutable inputs/output. Shallow
        # frame copies share those entries; a miss replaces only the candidate's
        # entry, so rejected frames cannot invalidate committed presentation.
        self._context_cache = None
        self._projection_cache = None
        self._visible_cache = None
        self._reset_search_folding()
        self._repair_focus()

    def copy(self):
        """Fork mutable interaction state while sharing the read-only catalog."""
        candidate = copy.copy(self)
        candidate.collapsed = self.collapsed.copy()
        candidate.search_collapsed = self.search_collapsed.copy()
        candidate.selected = self.selected.copy()
        candidate.values = self.values.copy()
        return candidate

    def _build_hierarchy(self):
        self.by_id = {region.id: region for region in self.regions}
        if len(self.by_id) != len(self.regions):
            raise ValueError('region hierarchy contains duplicate IDs')
        children: dict[str | None, list[SelectorRegion]] = {}
        for region in self.regions:
            if region.parent_id is not None and region.parent_id not in self.by_id:
                raise ValueError(f'region {region.id} has missing parent {region.parent_id}')
            children.setdefault(region.parent_id, []).append(region)
        rows = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(region, depth):
            if region.id in visiting:
                raise ValueError(f'region hierarchy contains a cycle at {region.id}')
            if region.id in visited:
                return
            visiting.add(region.id)
            descendants = children.get(region.id, ())
            rows.append(SelectorRow(region, depth, bool(descendants)))
            for child in descendants:
                visit(child, depth + 1)
            visiting.remove(region.id)
            visited.add(region.id)

        for region in children.get(None, ()):
            visit(region, 0)
        for region in self.regions:
            if region.id not in visited:
                visit(region, 0)
        grey = next(
            (
                i
                for i, row in enumerate(rows)
                if row.region.acronym == 'grey' and abs(row.region.atlas_id) == 8
            ),
            None,
        )
        if grey is not None:
            depth = rows[grey].depth
            end = grey + 1
            while end < len(rows) and rows[end].depth > depth:
                end += 1
            projected = []
            for row in rows[grey + 1 : end]:
                relative = row.depth - depth - 1
                region = row.region
                if relative == 0:
                    region = SelectorRegion(
                        region.id,
                        None,
                        region.atlas_id,
                        region.acronym,
                        region.name,
                        region.mapping_member,
                    )
                projected.append(SelectorRow(region, relative, row.branch))
            rows = projected
        self.hierarchy = tuple(rows)
        self.row_by_id = {row.region.id: row for row in rows}
        self.atlas_id_to_region_id = {abs(region.atlas_id): region.id for region in self.regions}
        self._ranked_leaves = tuple(
            row for row in self.hierarchy if not row.branch and row.region.mapping_member
        )
        position = {region.id: i for i, region in enumerate(self.regions)}
        self._leaf_positions = tuple(position[row.region.id] for row in self._ranked_leaves)

    @property
    def order(self):
        """Return effective display order while preserving the requested order."""
        return 'anatomy' if self.query else self.requested_order

    def _context(self):
        term = self.query.lower()
        if self._context_cache is not None and self._context_cache[0] == term:
            return self._context_cache[1]
        matches = {
            region.id
            for region in self.regions
            if term in region.acronym.lower() or term in region.name.lower()
        }
        retained = set(matches)
        required = set()
        for region in self.regions:
            parent = region.parent_id
            visited = {region.id}
            while parent is not None and parent not in visited:
                visited.add(parent)
                if region.id in matches:
                    retained.add(parent)
                    required.add(parent)
                if parent in matches:
                    retained.add(region.id)
                parent = self.by_id[parent].parent_id
        context = frozenset(matches), frozenset(retained), frozenset(required)
        self._context_cache = term, context
        return context

    @property
    def active_collapsed(self):
        """Return query-specific or ordinary folding state."""
        return self.search_collapsed if self.query else self.collapsed

    def _reset_search_folding(self):
        self.search_collapsed.clear()
        if self.query:
            matches, _, required = self._context()
            self.search_collapsed.update(
                row.region.id
                for row in self.hierarchy
                if row.branch and row.region.id not in matches and row.region.id not in required
            )

    def projected_rows(self):
        """Project anatomy or ranked leaves with stable semantic identities."""
        order = self.order
        if order == 'anatomy':
            return self.hierarchy
        # Snapshot public mutable inputs rather than relying on mutation flags.
        # Missing/nonfinite values have identical ranking semantics, including
        # newly allocated NaNs which otherwise compare unequal on every frame.
        values = tuple(
            value if value is not None and math.isfinite(value) else None
            for row in self._ranked_leaves
            for value in (self.values.get(row.region.id),)
        )
        key = order, values
        if self._projection_cache is not None and self._projection_cache[0] == key:
            return self._projection_cache[1]

        def ranking(index):
            value = values[index]
            scalar = value if value is not None else 0
            if order == 'value-desc':
                scalar = -scalar
            return (value is None, scalar, self._leaf_positions[index])

        rows = tuple(
            SelectorRow(self._ranked_leaves[index].region, 0, False)
            for index in sorted(range(len(self._ranked_leaves)), key=ranking)
        )
        self._projection_cache = key, rows
        return rows

    def visible_rows(self):
        """Return projected rows remaining after query and ancestor folding."""
        rows = self.projected_rows()
        anatomy = self.order == 'anatomy'
        collapsed = frozenset(self.active_collapsed) if anatomy else frozenset()
        term = self.query.lower()
        cached = self._visible_cache
        if cached is not None and cached[0] is rows and cached[1:3] == (term, collapsed):
            return cached[3]
        retained = self._context()[1] if self.query else ()
        visible = []
        for row in rows:
            if self.query and row.region.id not in retained:
                continue
            parent = row.region.parent_id
            folded = False
            while anatomy and parent is not None:
                if parent in collapsed:
                    folded = True
                    break
                parent_row = self.row_by_id.get(parent)
                parent = parent_row.region.parent_id if parent_row else None
            if not folded:
                visible.append(row)
        result = tuple(visible)
        self._visible_cache = rows, term, collapsed, result
        return result

    def _repair_focus(self):
        visible = [row.region.id for row in self.visible_rows()]
        if self.focus not in visible:
            self.focus = visible[0] if visible else self.focus
        if self.hover not in visible:
            self.hover = None

    def set_query(self, query):
        """Change search and reset only its temporary folding state."""
        query = trim_query(query)
        if query != self.query:
            self.query = query
            self._reset_search_folding()
        self._repair_focus()

    def set_selected(self, selected, *, preserve_anchor=False):
        """Synchronize ordered host selection without changing navigation focus."""
        selected = list(dict.fromkeys(selected))
        if selected != self.selected and not preserve_anchor:
            added = [key for key in selected if key not in self.selected]
            self.anchor = added[-1] if added else (selected[-1] if selected else None)
        self.selected = selected
        if self.anchor not in selected:
            self.anchor = selected[-1] if selected else None

    def toggle_branch(self, region_id):
        """Toggle disclosure unless search requires the branch to stay open."""
        row = next((row for row in self.projected_rows() if row.region.id == region_id), None)
        if row is None or not row.branch:
            return
        if self.query and region_id in self._context()[2]:
            return
        if region_id in self.active_collapsed:
            self.active_collapsed.remove(region_id)
        else:
            self.active_collapsed.add(region_id)
        self._repair_focus()

    def set_all_expanded(self, expanded):
        """Apply bulk disclosure to the effective presentation."""
        required = self._context()[2] if self.query else set()
        for row in self.projected_rows():
            if row.branch:
                if expanded or row.region.id in required:
                    self.active_collapsed.discard(row.region.id)
                else:
                    self.active_collapsed.add(row.region.id)
        self._repair_focus()

    def activate(self, region_id, *, ctrl=False, meta=False, shift=False, keyboard=False):  # noqa: PLR0911
        """Apply row activation and return a host selection effect."""
        row = next((row for row in self.projected_rows() if row.region.id == region_id), None)
        if row is None:
            return None
        if row.branch:
            self.toggle_branch(region_id)
            return None
        if not row.region.mapping_member:
            return None
        if shift and not keyboard:
            anchor = self.by_id.get(self.anchor)
            parent = self.by_id[region_id].parent_id
            if anchor is None or parent is None or anchor.parent_id != parent:
                return None
            siblings = [
                item.region.id
                for item in self.visible_rows()
                if not item.branch
                and item.region.mapping_member
                and self.by_id[item.region.id].parent_id == parent
            ]
            if self.anchor not in siblings or region_id not in siblings:
                return None
            left, right = sorted((siblings.index(self.anchor), siblings.index(region_id)))
            keys = siblings[left : right + 1]
            self.set_selected([*self.selected, *keys], preserve_anchor=True)
            return {'kind': 'range', 'ids': keys, 'target': region_id}
        self.anchor = region_id
        if ctrl or meta or self.multiple or region_id in self.selected:
            keys = (
                [key for key in self.selected if key != region_id]
                if region_id in self.selected
                else [*self.selected, region_id]
            )
        else:
            keys = [region_id]
        self.set_selected(keys, preserve_anchor=True)
        return {'kind': 'select', 'id': region_id, 'additive': ctrl or meta}

    def navigate(self, key, *, ctrl=False, meta=False):  # noqa: PLR0912
        """Handle browser navigation or ordinary keyboard activation."""
        rows = self.visible_rows()
        if not rows:
            return None
        keys = [row.region.id for row in rows]
        if self.focus not in keys:
            return None
        index = keys.index(self.focus)
        row = rows[index]
        if key in ('Enter', ' '):
            return self.activate(self.focus, ctrl=ctrl, meta=meta, keyboard=True)
        if key == 'ArrowRight' and self.order == 'anatomy':
            if row.branch and self.focus in self.active_collapsed:
                self.toggle_branch(self.focus)
            else:
                child = next(
                    (item.region.id for item in rows if item.region.parent_id == self.focus), None
                )
                if child:
                    self.focus = child
        elif key == 'ArrowLeft' and self.order == 'anatomy':
            if row.branch and self.focus not in self.active_collapsed:
                self.toggle_branch(self.focus)
            elif row.region.parent_id in keys:
                self.focus = row.region.parent_id
        elif key == 'ArrowDown':
            self.focus = keys[min(len(keys) - 1, index + 1)]
        elif key == 'ArrowUp':
            self.focus = keys[max(0, index - 1)]
        elif key == 'Home':
            self.focus = keys[0]
        elif key == 'End':
            self.focus = keys[-1]
        return None

    def snapshot(self):
        """Return the language-neutral conformance observation."""
        matches, retained, _ = self._context()
        branches = {row.region.id for row in self.projected_rows() if row.branch}
        return {
            'matches': [region.id for region in self.regions if region.id in matches],
            'retained': [region.id for region in self.regions if region.id in retained],
            'visible': [row.region.id for row in self.visible_rows()],
            'expanded': [
                region.id
                for region in self.regions
                if region.id in branches and region.id not in self.active_collapsed
            ],
            'selected': self.selected.copy(),
            'focus': self.focus,
            'anchor': self.anchor,
            'order': self.order,
            'requestedOrder': self.requested_order,
            'hover': self.hover,
        }

    def apply(self, action):  # noqa: PLR0912
        """Apply one versioned conformance action."""
        op = action['op']
        if op == 'query':
            self.set_query(action['value'])
        elif op == 'selection':
            self.set_selected(action['selected'])
        elif op == 'values':
            self.values = dict(action['values'])
            self._repair_focus()
        elif op == 'multiple':
            self.multiple = action['enabled']
        elif op == 'order':
            self.requested_order = action['value']
            self._repair_focus()
        elif op in ('collapse', 'expand'):
            collapsed = action['id'] in self.active_collapsed
            if collapsed != (op == 'collapse'):
                self.toggle_branch(action['id'])
        elif op in ('collapseAll', 'expandAll'):
            self.set_all_expanded(op == 'expandAll')
        elif op == 'activate':
            return self.activate(
                action['id'],
                ctrl=action.get('ctrl', False),
                meta=action.get('meta', False),
                shift=action.get('shift', False),
                keyboard=action.get('keyboard', False),
            )
        elif op == 'key':
            return self.navigate(
                action['key'], ctrl=action.get('ctrl', False), meta=action.get('meta', False)
            )
        elif op == 'hover':
            row = self.row_by_id.get(action.get('id'))
            visible = {row.region.id for row in self.visible_rows()}
            self.hover = (
                row.region.id
                if row and row.region.mapping_member and row.region.id in visible
                else None
            )
        elif op == 'focus':
            self.focus = action.get('id')
        else:
            raise ValueError(f'unknown region-selector action: {op}')
        return None
