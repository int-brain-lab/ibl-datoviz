# Datoviz v0.4 atlas spike findings

This note records evidence from the first `ibl-datoviz` 0.2 consumer. The tested revisions are
Datoviz `6387745a1`, `ibl-atlas-assets` `958f722f8`, and the synthetic mesh-pack-v1 fixture.

## What works without another Datoviz API

- A mesh pack's contiguous `float32[N, 3]` positions/normals, `uint8[N, 4]` colors, and flattened
  `uint32` indices upload directly through `dvz_visual_set_data_many()` and
  `dvz_visual_set_index_data()`.
- Color changes are independent retained updates. Allen/Beryl/Cosmos presentation can therefore
  change without rebuilding or re-uploading position, normal, or index data.
- Arcball binding, a 3-D path for the probe, an offscreen view, exact RGBA capture, and explicit
  app-before-scene destruction all work through the public Python facade.
- Indexed-mesh item queries return triangle primitive identity. Datoviz's query geometry expands
  each indexed triangle and writes `primitive_index + 1` to all three query vertices. A link-key
  array indexed by face can therefore carry a signed atlas region ID losslessly, encoded as the
  bit-preserving `int64`/`uint64` view.

## Narrow API mismatch discovered

Mesh querying and mesh item-state styling currently disagree about the meaning of an item.
Indexed-mesh queries resolve a triangle index, while `_item_state_visual_item_count()` treats a
non-instanced mesh as one item (and an instanced mesh's items as its instances). Consequently a
face link key gives a correct query/selection identity, but built-in hover or selection styling
cannot reliably highlight the selected anatomical region in one dense multi-region mesh.

This spike does not propose an ABI change yet. Plausible options are an explicit mesh query
identity attribute (per face/group), a face-to-group table, or a distinct face query target whose
result may carry a group/link key. The real atlas pack should be tried before choosing. One visual
per region remains the straightforward fallback when correct region highlighting is required.

## Asset-contract evidence

The consumer needs the declared presentation boundary to classify bilateral component vertices
and faces. `MeshPack.manifest` contains it, but `MeshGeometry` does not expose it. The current v1
fixture declares the provisional boundary as original-world ML zero with on-plane points assigned
right, so this spike implements that exact rule and documents the hard-coded assumption. The next
small `ibl-atlas-assets` change should expose validated presentation-boundary metadata on
`MeshGeometry`; consumer code should then reject unsupported boundary coordinates/statuses.

Presentation IDs should be treated as opaque keys. The adapter uses keyed lookup rather than
assuming IDs are dense or aligned with tuple order. Signed ontology IDs remain presentation
values, not presentation IDs, and are covered by regressions on both vertex colors and face link
keys.

## Next evidence step

Run the same adapter on a representative real mesh pack and verify that every triangle belongs to
one anatomical presentation after boundary classification. Then decide whether the dense mesh
plus group-aware picking route is sufficient or whether the first production viewer should attach
one visual per region/component.
