"""Pure selection precedence and translations; the viewer owns committed state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from .ontology import decode_region_key, encode_region_key

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class SelectionDecision:
    """Identify an event source and the propagation needed at the native boundary."""

    source: Literal['region_table', 'probe_table', 'tree', 'mesh']
    update_tree: bool
    update_tables: bool
    clear_mesh: bool
    sync_probe_table: bool = False
    sync_region_table: bool = False


def selection_decision(
    *,
    region_table_changed=False,
    table_changed=False,
    tree_changed=False,
    mesh_changed=False,
) -> SelectionDecision | None:
    """Choose the first source in the established widget event precedence."""
    if region_table_changed:
        return SelectionDecision('region_table', True, False, True, True)
    if table_changed:
        return SelectionDecision('probe_table', True, False, True, sync_region_table=True)
    if tree_changed:
        return SelectionDecision('tree', False, True, True)
    if mesh_changed:
        return SelectionDecision('mesh', True, True, False)
    return None


def probe_selected_ids(site_ids, mapped_ids, selected_keys) -> tuple[int, ...]:
    """Translate stable site row keys into unique signed mapped region identities."""
    selected = set(selected_keys)
    return tuple(
        dict.fromkeys(
            int(region_id)
            for site_id, region_id in zip(site_ids, mapped_ids, strict=True)
            if int(site_id) in selected and region_id
        )
    )


def selected_row_keys(row_keys, region_ids, logical_ids):
    """Select signed rows in either hemisphere from expanded logical identities."""
    return np.ascontiguousarray(np.asarray(row_keys)[np.isin(np.abs(region_ids), logical_ids)])


def region_ids_from_keys(keys: Sequence[int]) -> tuple[int, ...]:
    """Decode signed region keys without changing order or hemisphere identity."""
    return tuple(decode_region_key(key) for key in keys)


def mesh_ids_from_keys(keys: Sequence[int]) -> tuple[int, ...]:
    """Decode nonzero mesh link identities in stable selection order."""
    return tuple(dict.fromkeys(decode_region_key(key) for key in keys if key))


def tree_selection_keys(region_ids, available_ids):
    """Use the ontology's retained hemisphere convention for logical selections."""
    available = set(available_ids)
    return np.ascontiguousarray(
        [
            encode_region_key(-abs(int(region_id)))
            for region_id in region_ids
            if -abs(int(region_id)) in available
        ],
        dtype=np.uint64,
    )
