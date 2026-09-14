# Datoviz v0.4 atlas spike findings

This note records evidence from the first `ibl-datoviz` 0.2 consumer. The tested revisions are
Datoviz `2274ca3c3`, `ibl-atlas-assets` `25845bb`, the synthetic mesh-pack-v1
fixture, and the materialized real D070 asset-set lock.

## What works without another Datoviz API

- A mesh pack's contiguous `float32[N, 3]` positions/normals, `uint8[N, 4]` colors, and flattened
  `uint32` indices upload directly through `dvz_visual_set_data_many()` and
  `dvz_visual_set_index_data()`.
- Color changes are independent retained updates. Allen/Beryl/Cosmos presentation can therefore
  change without rebuilding or re-uploading position, normal, or index data.
- Arcball binding, a 3-D path for the probe, an offscreen view, exact RGBA capture, and explicit
  app-before-scene destruction all work through the public Python facade.
- Indexed-mesh face queries return triangle primitive identity. A target-specific link-key array
  indexed by face carries a signed atlas region ID losslessly, encoded as the bit-preserving
  `int64`/`uint64` view. Mesh item queries retain their distinct whole-mesh/instance semantics.

## Narrow API gap resolved

The original spike incorrectly attached face keys to Datoviz's item target. That target correctly
means a whole mesh or instance, so the apparent face picking was false. The consumer evidence led
to an explicit `DVZ_SCENE_TARGET_FACE` path and `dvz_visual_set_target_link_keys()`, leaving item
semantics unchanged and allowing item and face key maps to coexist.

Linked identity is scoped by a scene-local channel plus its 64-bit key, rather than by key alone.
That permits the same ontology ID to be reused safely by unrelated linked views and keeps zero as a
valid application key. Rebinding or destroying a channel also recomputes retained item state, so
linked highlights cannot remain stale.

Face picking now has exact triangle and application link identity. Built-in item-state styling is
still intentionally whole-mesh/instance based: highlighting an anatomical region requires owned
vertex recoloring or separate component visuals. Atlas-scale hover should be throttled even though
unchanged picks now reuse retained query geometry.

## Asset-contract evidence

The consumer needs the declared presentation boundary to classify bilateral component vertices
and faces. The first spike exposed that `MeshPack.manifest` contained the rule while `MeshGeometry`
did not. `ibl-atlas-assets` now validates and exposes the boundary and provides batched
`presentation_ids_for_component()` resolution. This consumer uses that shared rule for both vertex
presentation and per-face query identity; it no longer hard-codes ML zero or the on-plane side.

Presentation IDs should be treated as opaque keys. The adapter uses keyed lookup rather than
assuming IDs are dense or aligned with tuple order. Signed ontology IDs remain presentation
values, not presentation IDs, and are covered by regressions on both vertex colors and face link
keys.

## Next evidence step

The real D070 checkpoint is complete. Every one of its 486,674 vertices and 966,645 triangles
resolves to the same signed-presentation fingerprints in the Python and TypeScript consumers. It
also exposed a coordinate bug hidden by the synthetic identity transform: decoded EAM3 positions
are already compiled into declared world coordinates, so the source-provenance transform must not
be applied again.

Dense upload and mapping-only updates remain appropriate: native preparation is below 0.1 seconds
and mapping color/identity arrays take about 7–9 milliseconds on the diagnostic host. Datoviz now
retains the expanded picking upload until the mesh position, index, instance-transform, or topology
revisions change. On the real D070 mesh the initial query takes roughly 120 milliseconds, while
unchanged subsequent queries take roughly 11 milliseconds instead of 85–101 milliseconds. The
expanded picking representation still raises peak memory materially; avoiding that footprint would
require an indexed picking shader/data path rather than this deliberately smaller cache fix.
