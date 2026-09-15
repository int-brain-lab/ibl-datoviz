# Datoviz v0.4 atlas spike findings

This note records evidence from the first `ibl-datoviz` 0.2 consumer. The current tested revisions are
Datoviz `5c796bbc8`, `ibl-atlas-assets` `f5096c3a9`, the synthetic mesh-pack-v1
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

The exercise exposed and then closed a Datoviz integration issue: camera-less panels returned from
MVP composition before applying their retained arcball. Datoviz `1114b65fa` adds an exact
high-level offscreen regression and applies the arcball without changing the API or ABI. Distinct
Euler angles now produce distinct real D070 captures, so `AtlasViewer` exposes reproducible initial
angles and active-view updates.

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
channel grouping belongs in source adaptation, not rendering. The follow-up regional view supplies
that second use case without introducing metric switching. `AtlasRegionValues` retains signed Allen
identity and explicit aggregation weights; the caller must explicitly choose weighted-mean
reduction when Beryl or Cosmos collapses multiple valid Allen rows. Parent-closure rows absent from
the target mapping are omitted rather than collapsed into the legacy root placeholder. Surface
recoloring uses a presentation lookup and indexed ontology descriptions, avoiding a vertex scan and
an ontology scan per region. The reproducible full-catalog benchmark updates all 2,194 signed Allen
rows over 486,674 vertices in about 6.3 milliseconds per preparation and native upload on the
diagnostic host. One authoritative selection now links regional surface color, individual probe
sites, the ontology tree, a regional summary table, and the site table. This is evidence for a small
typed region-scalar boundary, but not for a shared dashboard abstraction.

The linked navigator now consumes the pinned annotation/template volume contract. It keeps linearly sampled anatomy, nearest-neighbour region color, and mapping-aware vector boundaries as separate layers so each can be controlled and rendered with the appropriate sampling policy.

## Slice-boundary evidence

The first native boundary implementation derives merged vector segments from each oriented annotation slice after Allen-to-presentation remapping. This is important: an Allen boundary disappears when both sides map to the same Beryl or Cosmos identity. The result is cached by mapping, axis, and section, remains crisp under viewport zoom, and is rendered between the slice textures and cursor overlays.

`ephys-atlas-web-v2` already contains a substantially richer production pipeline for slice geometry. Its indexed `.isvg.gz` packs concatenate per-section SVG fragments behind a fixed binary index, retain Allen/Beryl/Cosmos IDs on every path, declare plane/world transforms, and record topology, adjacency, simplification, and boundary-error validation. The assets are reusable, but the web repository and its SVG transport should not become a dependency of this native package.

The clean shared follow-up is to move or adapt that builder and its validated slice-geometry contract into `ibl-atlas-assets`. Consumers should request a projection and section and receive renderer-neutral region rings or boundary polylines plus signed mapping identities and transforms. The web app may encode those records as indexed SVG; `ibl-datoviz` may upload them as retained segments or paths. Until that contract exists, the local voxel-exact boundary derivation provides correct interaction semantics without prematurely freezing the web transport as the shared API.
