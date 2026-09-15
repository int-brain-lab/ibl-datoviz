"""Renderer-facing views of the shared Allen region catalog."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Mapping

    from numpy.typing import NDArray

    from ibl_anatomy import AtlasRegionCatalog

ROOT_PARENT = np.iinfo(np.uint32).max


def encode_region_key(region_id: int) -> int:
    """Encode a signed atlas ID as the bit-identical Datoviz uint64 key."""
    return int(np.asarray(region_id, dtype=np.int64).view(np.uint64))


def decode_region_key(key: int) -> int:
    """Decode a Datoviz uint64 key to its signed atlas ID."""
    return int(np.asarray(key, dtype=np.uint64).view(np.int64))


def _rgba(color_hex: str) -> tuple[int, int, int, int]:
    return tuple(bytes.fromhex(color_hex[1:])) + (255,)


@dataclass(frozen=True)
class AtlasTreeModel:
    """Packed, parent-closed rows for one retained Datoviz ontology tree."""

    mapping: str
    region_ids: NDArray[np.int64]
    keys: NDArray[np.uint64]
    parents: NDArray[np.uint32]
    acronyms: tuple[str, ...]
    names: tuple[str, ...]
    colors: NDArray[np.uint8]
    mapping_members: NDArray[np.bool_]
    descriptions: Mapping[int, str]

    @classmethod
    def from_catalog(cls, catalog: AtlasRegionCatalog, mapping: str) -> AtlasTreeModel:
        """Build the canonical left tree, excluding the non-anatomical void row."""
        rows = tuple(row for row in catalog.left(mapping) if row.atlas_id != 0)
        if not rows:
            raise ValueError(f'atlas mapping has no anatomical rows: {mapping}')
        row_index = {row.atlas_id: index for index, row in enumerate(rows)}
        parents = []
        for row in rows:
            if row.parent_id is None:
                parents.append(ROOT_PARENT)
            elif row.parent_id not in row_index:
                raise ValueError(f'atlas tree is not parent-closed at region {row.atlas_id}')
            else:
                parents.append(row_index[row.parent_id])
        region_ids = np.ascontiguousarray([row.atlas_id for row in rows], dtype=np.int64)
        acronyms = tuple(row.acronym for row in rows)
        names = tuple(row.name.removesuffix(' (left)') for row in rows)
        descriptions = {
            abs(int(region_id)): f'{acronym} — {name}'
            for region_id, acronym, name in zip(region_ids, acronyms, names, strict=True)
        }
        return cls(
            mapping=mapping,
            region_ids=region_ids,
            keys=np.ascontiguousarray(region_ids.view(np.uint64)),
            parents=np.ascontiguousarray(parents, dtype=np.uint32),
            acronyms=acronyms,
            names=names,
            colors=np.ascontiguousarray([_rgba(row.color_hex) for row in rows], dtype=np.uint8),
            mapping_members=np.ascontiguousarray(
                [row.mapping_member for row in rows], dtype=np.bool_
            ),
            descriptions=MappingProxyType(descriptions),
        )

    @property
    def palette(self) -> dict[int, tuple[int, int, int, int]]:
        """Return canonical colors keyed by both signed and logical region identity."""
        result = {}
        for region_id, color in zip(self.region_ids, self.colors, strict=True):
            rgba = tuple(int(channel) for channel in color)
            result[int(region_id)] = rgba
            result.setdefault(abs(int(region_id)), rgba)
        return result

    @property
    def selectable_region_ids(self) -> frozenset[int]:
        """Return signed IDs which are actual members of this mapping."""
        return frozenset(
            int(region_id)
            for region_id, member in zip(self.region_ids, self.mapping_members, strict=True)
            if member
        )

    def subtree_row_indices(self, root_acronym: str) -> NDArray[np.uint32]:
        """Return packed row indices for one acronym-rooted ontology subtree."""
        roots = [index for index, acronym in enumerate(self.acronyms) if acronym == root_acronym]
        if len(roots) != 1:
            raise ValueError(f'expected one {root_acronym!r} ontology row, found {len(roots)}')
        root = roots[0]
        included = []
        for index in range(len(self.region_ids)):
            ancestor = index
            while ancestor not in (ROOT_PARENT, root):
                ancestor = int(self.parents[ancestor])
            if ancestor == root:
                included.append(index)
        return np.ascontiguousarray(included, dtype=np.uint32)

    def expanded_logical_ids(self, region_ids: tuple[int, ...]) -> tuple[int, ...]:
        """Expand selected ontology rows to selectable descendants, ignoring hemisphere."""
        selected = {abs(int(region_id)) for region_id in region_ids if region_id}
        if not selected:
            return ()
        included = set(selected)
        for index, region_id in enumerate(self.region_ids):
            if not self.mapping_members[index]:
                continue
            parent_index = index
            while parent_index != ROOT_PARENT:
                ancestor = abs(int(self.region_ids[parent_index]))
                if ancestor in selected:
                    included.add(abs(int(region_id)))
                    break
                parent_index = int(self.parents[parent_index])
        return tuple(sorted(included))

    def describe(self, region_id: int) -> str:
        """Return a compact acronym and name for a signed or logical region ID."""
        return self.descriptions.get(abs(int(region_id)), str(region_id))
