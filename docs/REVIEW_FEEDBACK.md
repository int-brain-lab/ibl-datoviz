# Manual review feedback

App 1 review began on October 14, 2026, at UI scale 1.5. This log preserves the
reviewer's observations and requested behavior. Implemented corrections remain
subject to manual acceptance. Add subsequent feedback here rather than losing it
in dated implementation handoffs.

## Feedback and status

| Point | Observation or request | Status and acceptance |
| --- | --- | --- |
| Larger controls | Increase UI scale for manual review. | Available through `--ui-scale 1.5`; retain the chosen scale while reviewing. |
| Opaque default brain | The default brain is entirely translucent. | Changed in `e5f0e0f`: app 1 starts at opacity 1.0 rather than 0.16. Restart and confirm the default appearance. Transparency remains an explicit control. |
| Stable selection area | Clicking a tree region grows the selection summary and suddenly pushes the tree downward. | Changed in `e5f0e0f`: fixed-height scrolling summary. Scripted captures confirm a stable heading; manual acceptance remains open. |
| Slow hover in both views | Hovering tree rows and the 3D brain is very slow. Transparency was suggested as a possible cause. | GPU state implemented. After the hemisphere correction, isolated real-mouse sweeps measure about 25 ms tree and 37–38 ms brain frames, with no dense color uploads or static query rebuilds. Manual responsiveness acceptance remains open. |
| Hide scientific data | Hide the scientific-data area for the current review. | Changed in `e5f0e0f`: hidden by default; **Data layers → Show data table** now restores the retained table. |
| Clean hemisphere boundary | Turning off one hemisphere exposes spiky triangles at the interhemispheric boundary. Web v2's reviewed splitting and explode behavior should be reused. | Correction uses the same binary geometry with private presentation copies of crossing triangles and complementary fragment coverage shared by shading and picking. Original ML determines the side after explosion; zero belongs to the right. Validation and manual acceptance are recorded below. |
| GPU highlight state | Highlight should use a small shader-state update, with geometry retained on the GPU, rather than uploading vertex colors or triangles on hover. | Implemented through Datoviz's fixed-size u32 item-state buffer and copied per-vertex slot indices. Sparse flags use existing generic styles; no Allen semantics or full mesh-part API in the engine. |
| Opt-in hover | After completing the benchmark, disable hover by default and retain 3D click selection. Keep hover available and improve its efficiency. | Both review apps disable tree/brain hover feedback and native hover queries by default. Click selection remains enabled. `--hover` restores the improved GPU path; library callers can use `enable_hover=False`. |
| Reserved region browser | Brain-region browsing must occupy a dedicated, always-visible part of the left GUI. Reaching it must not require scrolling the surrounding sidebar; the tree itself needs its own scrollbar. | The reservation in `bc1d9ba` stopped movement but was rejected in the next manual review: controls and empty selection space still crowded the tree into the bottom third. The compact redesign replaces those panes; stability alone does not establish acceptance. |
| Compact, clear sidebar | The reviewer finds the panel confusing, crowded and wasteful, with too little space for the tree. Small icon buttons are welcome because screen space is scarce. | Implemented three compact header rows, a remaining-height tree, and a fixed two-row selection footer. Display settings and full selection details move into explicit in-app windows that leave the tree accessible. Retain UI scale 1.5 and improve hierarchy/contrast rather than shrinking the text. Awaiting new manual review. |
| Expand/collapse icons | Minus and plus can suggest zoom or adding/removing items rather than folding the hierarchy. | Replaced with inward-pointing chevrons for collapse and outward-pointing chevrons for expand. Existing tooltips identify both actions; awaiting manual acceptance. |
| Top-level explode | Explosion is a frequent action and should appear at the top, outside configuration. | Implemented in the always-visible 3D atlas toolbar, outside Display settings. Tree space is preserved; manual acceptance remains open. |
| Clear app 1 controls | Atlas views, scientific scene and appearance controls overlap and leave the reviewer lost. | Implemented Regions, 3D atlas, Display settings, and a separate optional Data layers panel. Controls follow enabled layers; examples and renderer comparisons are secondary. Manual acceptance remains open. |
| Clearly visible selection | Selecting a region makes even the selected region hard to see among transparent anatomy. Consider a faint shell with the selected region remaining solid. | Audit confirms selected authored alpha is preserved, but the previous combined mesh entered WBOIT and overlapping context washed out its color. App 1 now renders only selected signed regions/descendants with authored opacity and a separate verified neutral root envelope. Isolate hides the shell; Show all restores full atlas coverage without clearing selection. Hover stays sparse. FRP/deep thalamus captures and native pixels/picks were checked; manual appearance acceptance remains open. The shell is hidden for explosion or hemisphere filtering. |
| Larger initial window | Start the window twice as large on the current screen. | Both review apps request 2800 × 2000 logical pixels and opt into Datoviz fitting within one monitor's decorated work area. Offscreen sizes remain exact and UI scale remains independent. Isolated fitting/exact-size checks pass; physical screen placement remains for manual review. |
| Toolbar grouping | Multi-select is a different action; collapse and expand are opposites and should sit much closer together. | Implemented a tight collapse/expand pair separated from multi-select. Folding preserves the total region count and button positions. Real mouse checks cover both actions and mode toggling; manual acceptance remains open. |
| Distinct button states | Hover and pressed states appear identical and are confusing. | Datoviz audit finds persistent ACTIVE reuses the pressed background. Datoviz now retains native hover/held/focus backgrounds and adds a persistent on-state underline that survives hover and respects disabled styling. Native GUI tests pass; manual acceptance remains open. |

## Shared asset and hemisphere audit

The reviewer requires both applications to consume the same binary assets and
preserve the same region, hemisphere and explode semantics. Repository/branch
inspection confirms the current D070 asset convergence is already integrated:

- Pack: `ibl-native-d070-71f78c56e0b35eb2`.
- Manifest SHA256: `2a2b9145b09f67d175a9ce0d7dbcc9e63a2c0444218e06c86902d19378e8dc9d`.
- Geometry SHA256: `b5f5abc7d0bb357520a65dacf33a24251e2bd6f75873d7d5ac650ef2cd271799`.
- 486,674 vertices, 966,645 triangles and 1,140 native components.

`ibl-anatomy`'s D070 lock and web v2's deployment descriptor pin the same
production manifest. App 1 loads that verified materialization. Both apply the
component's authored `explode_displacement_um`; the original world ML coordinate
must continue to determine hemisphere membership after displacement.

The web D070 renderer does not cut/cap the binary triangles. It retains
left/right presentation IDs and classifies each fragment by interpolated original
ML, with ML=0 assigned to the right. The native renderer classifies each face once
and removes whole triangles. A face crossing ML=0 can therefore extend across the
hidden hemisphere. The reported spikes are consistent with this behavior gap;
this describes the native implementation before the correction below.
The older carefully cut/capped D042 geometry is a historical rollback route.

Source references:

- Shared lock: anatomy `src/ibl_anatomy/asset_sets/d070.json`.
- Web: `web/src/rendering/3d/brain-scene-viewport.ts` and
  `web/src/rendering/3d/mesh-presentation-boundary.ts`.
- Native: `ibl_datoviz/atlas.py`, `ibl_datoviz/surface_style.py` and
  `AtlasViewer._upload_surface_faces()` in `ibl_datoviz/viewer.py`.

Fetched branch audit: web `main` (`e3687ab`) already includes the selected-pack
builder (`3d52114`) and website integration (`7439171`). Anatomy `main`
(`295c936`) already includes the shared D070 lock (introduced at `25845bb`).
Native `feature/datoviz-v04` (`e5f0e0f`) contains the asset adapter and signed
hemisphere styles. No unmerged branch implementing native fragment-boundary
parity was found in the available refs. Web's donor
`experiment/brain-mesh-3d-lab` (`ba1e2d1`) is frozen by its repository instructions;
its asset work should be understood from integrated code rather than resumed.

The correction preserves the shared immutable pack. A private `SurfaceGeometry`
adapter keeps the original source triangles, duplicating only crossing/zero-touch
faces into side-specific presentation copies. It copies positions, normals and
authored explosion vectors without cutting, capping or nudging vertices. D070's
private draw mesh has 492,607 vertices and 972,582 triangles: 5,937 additional
triangles, approximately 0.6%. Public `mesh_data` and world-point normalization
continue to use the original canonical arrays and bounds.

Each copy carries a generic signed fragment-clip distance and an explicit
include-zero flag. The engine applies the same predicate in color/transparency
and scientific query passes. Left uses original ML < 0; right uses ML >= 0.
The policy comes from the verified pack, including its axis, threshold and
single-presentation fallback. The classifier is independent of display/explode
positions. Presentation colors, state-buffer slots and signed face keys all use
the same private draw identities.

Initial isolated probes at a nominal central framebuffer coordinate changed side
under rotation. Those probes were not proof of exact-zero ownership: that pixel
need not interpolate exactly to original ML=0. Exact-zero validation instead uses
known zero clip values or coplanar source coordinates. The correction encodes the
required half-open rule explicitly and keeps the complete source-triangle
footprint in both copies, avoiding dependence on shared-edge raster ownership.

The hemisphere batch targets coverage, signed picking and explosion parity.
Its adjacent audit found that web hides presentations whose active mapping is
null while native rendered gray missing-ID context. The review-readiness
follow-up now excludes those faces from both rendering and picking. For D070,
this removes eighteen unmapped Beryl presentations (1,244 private triangles);
Allen and Cosmos remain fully mapped. A native layered regression verifies
that these faces cannot occlude a mapped region behind them, all-unmapped
mappings render only background, and mapping switches restore the surface.
Selection, hover and hemisphere changes cannot reveal unmapped faces. Automated
checks pass; manual acceptance remains open. This closes the recorded null-ID
visibility difference without claiming full rendering parity between stacks.

Ignored evidence is in `build/hemisphere-audit/`, `build/hemisphere-review/` and
`build/unmapped-review/`.

## Hover profiling

Profiling uses a separate Xvfb display and the NVIDIA ICD on the RTX 5090. It does
not open windows on the working desktop. Real app 1 uses Beryl, opacity 1.0,
1600 by 1200 pixels and UI scale 1.5. Measurements are short diagnostic runs;
other GPU activity and virtual-display presentation affect absolute timings.

A full-app 3D sweep averages roughly 91–101 ms per frame. The source view's picking
work accounts for approximately 69–72 ms per frame. One measured run spends about
46 ms building query geometry, 10 ms emitting it and 13 ms in backend execution.
Python GUI work is about 4 ms per frame; hover recoloring is roughly 1 ms.

Color updates invalidate the mesh query's combined static cache, because its key
includes the color attribute version. Rebuilding a face query expands the mesh to
2,899,935 query vertices. In one 40-frame run, 24 static refreshes upload a total
of 1,391,968,800 bytes, about 58 MB per refresh. The cache rebuild includes geometry
and identities even when hover changes only RGB colors.

Diagnostic suppression of color uploads reduces the 3D sweep to about 36 ms per
frame while preserving observed hover transitions. Disconnecting picking reduces
it to about 29 ms. These are diagnostic interventions, not proposed shipping
behavior: hover feedback and picking must remain functional.

A selectable FRP tree-leaf sweep alternating hover and exit averages 151 ms per
frame, with 46 hover transitions across warmup and measurement. Suppressing color
uploads reduces it to 23 ms with the same alternating transitions. The initial
context-branch sweeps produced no hover transitions and are not used as evidence
for selectable-row performance. Both actual hover paths reproduce the problem.

The implemented path binds copied presentation-slot indices once and retains a
fixed-size GPU buffer of u32 hover/selection flags. Existing tint and context-alpha
styles apply before lighting in opaque, source-over blended and WBOIT meshes.
Parent selection updates descendant presentation flags, proportional to presentation
count rather than vertex count. This is independent of legacy instance-rate mesh
item state. It introduces no ontology, category color palette or mesh-part API.

Interaction decoration does not invalidate scientific queries. Authored colors,
opacity, geometry, topology, mapping identity, visibility and transforms retain
their ordinary query invalidation. Bounded alpha-mode changes used for decoration
retain query caches. Hover and selection preserve authored/global alpha rather
than raising hovered/selected opacity as the previous CPU recoloring did. Fully
dimmed context remains selectable; authored zero-alpha regions remain unpickable.

The October 14 indexed-state-only baseline used three repeated real-mouse sweeps
on the same D070/Beryl workload, measuring 22.8–24.1 ms
tree-hover frames and 30.4–31.1 ms brain-hover frames. Idle frames are 17.4–17.7 ms.
Each 40-frame tree phase requests 1,600 state-payload bytes; each brain phase
requests 2,000 bytes. Both paths retain visible transitions and upload no dense
colors. Native phase logs report zero static query uploads and zero query upload
bytes after warmup, with all 40 brain queries completing. A real brain click also
selects a region after each sweep. These bounded Linux timings are diagnostic
evidence, not portable performance guarantees or manual acceptance.

The hemisphere-corrected October 15 repeat measures 24.8–25.0 ms tree-hover frames
and 36.7–38.1 ms brain-hover frames. The extra fragment-query work has a measurable
cost. All forty brain queries complete with zero static uploads/bytes after
warmup; sparse state payloads and zero dense color uploads match the earlier
baseline. A temporary cache-layout mismatch was caught by this repeat before
publication, fixed with a shared capacity/compile-time guard, and covered by
native tests that assert actual warm upload counters.

The updated IBL suite passes 590 tests with zero skips and Vulkan validation enabled.
Independent engine proofs cover sparse emitted writes, shared consumers, ownership,
failure recovery, unchanged query revisions, six native render profiles and a
deterministic browser WGSL transition. Full mesh parts and asynchronous picking
remain separate future work.

Default-off verification on the isolated display confirms no native hover queries
and no hover emphasis, while a real 3D click selects signed region -894. Explicit
`enable_hover=True` restores hover on the same location. Native option, tree-click
and CLI forwarding regressions protect the opt-in behavior.

Ignored evidence: `build/indexed-state/` contains post-change timings, real-mouse
profiles/captures and full-suite logs. `build/hover-profile/` contains native phase timings, Python
profiles, screenshots, diagnostic scripts and receipts. Earlier corrections are
recorded in `build/manual-review-fixes/`.

## Automated review constraint

The reviewer is working on this computer. Automated native GUI checks must use
an isolated display such as Xvfb; browser checks should run headlessly. Visible
manual-review windows are launched by the reviewer. Invisible GPU work can still
compete with the desktop, so keep diagnostic runs bounded.
