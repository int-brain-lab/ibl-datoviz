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
- Arcball binding, a 3-D path and scalar-colored sphere sites for a probe, an offscreen view,
  exact RGBA capture, and explicit app-before-scene destruction all work through the public
  Python facade.
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

The viewer now keeps one authoritative region selection instead of merging independently retained
tree and surface selections. A tree event replaces surface selection; a changed surface selection
replaces and reveals the corresponding canonical left-tree row. This prevents mirrored selections
from feeding back into the next frame and accumulating stale regions. Parent ontology selection is
expanded to mapping-member descendants before the color mask is built, while the public selection
continues to report exactly the signed IDs chosen by the user.

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

## Probe-overlay evidence

The first quantitative overlay uses one retained sphere visual for all sites and one batched
`dvz_visual_set_data_many()` upload for positions, RGBA colors, and radii. Coordinates go through
the same atlas-world-to-display transform as the surface and probe path. A small diverging color
mapping handles finite ranges, clipping, constant data, and missing values in Python while the
renderer receives only display-ready arrays. Supplying application colors bypasses that mapping.

An opaque whole-brain surface hides internal sites. Lowering only the atlas vertex alpha and using
ordinary source-over blending is also insufficient for this dense, self-overlapping surface. The
viewer therefore applies `DVZ_ALPHA_WBOIT` automatically when `surface_opacity < 1`, and every
mapping or selection recolor preserves the configured alpha multiplier. This is a concrete use of
Datoviz v0.4's improved 3-D transparency, not a decorative feature toggle.

The current browser subset does not promise this WBOIT path. A WebGPU export should expose that
capability difference and choose a deliberate fallback (region isolation, clipping, or an opaque
surface plus exterior sites) instead of presenting source-over output as equivalent.

The linked probe follow-up deliberately keeps the payload smaller than an ephys application model:
stable site IDs, atlas-world coordinates, one scalar, signed Allen IDs, and labels. The viewer maps
those Allen IDs through the verified catalog for the active presentation, installs all sphere item
link keys in one call, and populates a retained searchable/sortable table through column-wise batch
setters. Table selection becomes the authoritative region selection for that event; tree or surface
selection selects every matching site. Stable site keys remain distinct from atlas keys, avoiding
the common mistake of treating multiple sites in one region as one row.

This experiment also sharpens package boundaries. Coordinate-to-annotation-volume lookup remains
an `iblatlas` responsibility. An application may persist its resulting signed Allen IDs in a probe
payload; `ibl-datoviz` handles rendering and interaction, while `ibl-atlas-assets` supplies the
versioned catalog used for presentation remapping. No new `iblatlas` API is justified by this slice.

## Real BWM insertion evidence

The first real consumer record comes from local `bwm_ephys` 1.1.0 insertion
`a21bade7-5be7-4a17-a9b9-ddee453e6260`. Its 384 channel rows form 192 exact co-located atlas sites;
459 units pass the dataset's recorded `label >= 1.0` good-unit rule, and 154 sites have at least one
assigned unit. The display value is the mean firing rate of good units per co-located channel group.
The committed fixture records hashes for the channels, insertions, and units Parquet inputs as well
as its own CSV hash.

This case required only two small generalizations: a human-readable scalar name and an explicit
sequential color scheme. A robust finite 5th–95th percentile display range prevents a few high-rate
sites from flattening the rest; it does not alter raw table values. The fixture retains good-unit
count as evidence, but the renderer payload does not absorb it speculatively. Multiple simultaneous
metrics and feature switching should be designed from another real use case.

The exercise also exposed a Datoviz integration issue: setting substantially different Euler angles
through `dvz_arcball_set()` after `dvz_view_arcball()` produced byte-identical initial offscreen
captures. Interactive pointer updates and programmatic initial-state propagation need a focused
Datoviz regression before `ibl-datoviz` exposes a camera-preset API.

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

The real-record slice shows one scalar is enough for a single-feature probe view and that co-located
channel grouping belongs in source adaptation, not rendering. The next work should fix and regress
the initial arcball-state issue in Datoviz, then test a second real ephys feature before designing
multi-feature switching. Volume rendering should wait until a pinned annotation/template volume
contract exists.
