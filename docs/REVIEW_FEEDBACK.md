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
| Slow hover in both views | Hovering tree rows and the 3D brain is very slow. Transparency was suggested as a possible cause. | Open. Removing per-frame catalog deepcopy did not resolve the reported slowdown. Profiling identifies a large picking-cache rebuild cost in 3D; see below. |
| Hide scientific data | Hide the scientific-data area for the current review. | Changed in `e5f0e0f`: hidden by default; **Show scientific data** restores the retained table. |
| Clean hemisphere boundary | Turning off one hemisphere exposes spiky triangles at the interhemispheric boundary. Web v2's reviewed splitting and explode behavior should be reused. | Open. Shared binary geometry already matches; native whole-face hiding differs from web's per-fragment boundary classification. Match the web behavior before accepting hemisphere visibility. |
| Opt-in hover | After completing the benchmark, disable hover by default and retain 3D click selection. Keep hover available and improve its efficiency. | Changed: both review apps disable tree/brain hover feedback and native hover queries by default. Click selection remains enabled. `--hover` restores the feature; library callers can use `enable_hover=False`. Engine efficiency remains open. |
| Reserved region browser | Brain-region browsing must occupy a dedicated, always-visible part of the left GUI. Reaching it must not require scrolling the surrounding sidebar; the tree itself needs its own scrollbar. | Open. Reserve browser space independently of scene controls and selection details. Check at scale 1.5 and the reviewer's window size, including long and multiple selections. |

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

The current web D070 renderer does not cut/cap the binary triangles. It retains
left/right presentation IDs and classifies each fragment by interpolated original
ML, with ML=0 assigned to the right. The native renderer classifies each face once
and removes whole triangles. A face crossing ML=0 can therefore extend across the
hidden hemisphere. The reported spikes are consistent with this behavior gap.
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

The correction should preserve the shared immutable pack. Prefer native
fragment-boundary classification matching the web, or an explicitly derived
render mesh from those same bytes if the engine requires it. Rendering and picking
must agree at the boundary, including after explosion and mapping/style changes.

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

The priority engine fix is to separate geometry/identity cache invalidation from
appearance and alpha changes. RGB-only hover should retain static query geometry;
visibility, alpha/cutoff, geometry, topology, mapping identity and transform changes
must still invalidate the inputs they affect. Repeat the same real-app sweeps after
any correction rather than accepting color-copy microbenchmarks as end-to-end proof.

Default-off verification on the isolated display confirms no native hover queries
and no hover emphasis, while a real 3D click selects signed region -894. Explicit
`enable_hover=True` restores hover on the same location. Native option, tree-click
and CLI forwarding regressions protect the opt-in behavior.

Ignored evidence: `build/hover-profile/` contains native phase timings, Python
profiles, screenshots, diagnostic scripts and receipts. Earlier corrections are
recorded in `build/manual-review-fixes/`.

## Automated review constraint

The reviewer is working on this computer. Automated native GUI checks must use
an isolated display such as Xvfb; browser checks should run headlessly. Visible
manual-review windows are launched by the reviewer. Invisible GPU work can still
compete with the desktop, so keep diagnostic runs bounded.
