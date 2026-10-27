# Manual review feedback

## Multi-recording review ready — October 27 2026

The user authorized a multi-recording review after accepting the redesigned
single-recording panel. A new 20-second Linux clip shows two actual BWM
recordings, independent group visibility and four selected clusters retained
across their two linked tables. Source validation and alignment quality remain
unknown under the existing reviewed coordinate declaration. Scientific/native
state checks pass; the clip awaits user acceptance. See
[the handoff](NEXT_STEPS.md#two-recording-visibility-and-selection-review-ready-october-27-2026)
for exact inputs, source identities and artifact hashes.

## Redesigned scalar panel accepted — October 27 2026

The user authorized the audit's implementation. The compact layer inspector,
separate selection summary, collapsed Appearance/Source and methods, retained
measurements across color modes, compact on-demand table and narrow-window
sidebar tabs are implemented. The package compensates the pinned docking
helper's viewport-relative sizing without changing the native baseline. App 1
shares docking and presentation helpers while retaining diagnostic semantics.
See [implementation and validation](NEXT_STEPS.md#simpler-layer-inspector-implemented-october-27-2026).
The user watched and approved the new 20-second Linux clip's panel and ordinary
table/panel actions. Acceptance is scoped to the shown workflow; multiple-recording
presentation, hands-on responsiveness and Mac rendering retain their own evidence
gates. The rejected earlier scalar clip is retained as comparison evidence.

## Scalar right panel rejected and audited — October 27 2026

The reviewer rejects the new scalar example's right panel as confusing and asks
for a deep audit and a much clearer, simpler scientist-facing design. The earlier
accepted atlas-navigation clip remains accepted; the scalar clip is not accepted.
The recommendations below record the audit before implementation and acceptance.

### Evidence and causes

The audit inspected the recorded measured, missing, filtered and uniform-color
states, the package Layers/table adapters, the separate app-1 controls and the
pinned native docking implementation. Four-frame native diagnostic launches on a
private Xvfb display measured the final window rectangles. Values below are the
runtime GUI coordinate units on this Linux display, not Mac/HiDPI evidence.

| Host size / UI scale | Requested Layers width | Actual Layers width | Central viewport size |
| --- | --- | --- | --- |
| 2240 × 1600 / 1.25 | 425 | 330 | 1407 × 1248 |
| 1600 × 1000 / 1.0 | 340 | 255 | 942 × 718 |
| 1440 × 900 / 1.5 | 510 | 297 | 539 × 478 |

The right panel loses width after the Regions split. In the pinned Datoviz
`src/gui/gui.cpp`, `_gui_dock_node_for_slot()` splits the remaining central node,
but `_gui_dock_slot_ratio()` divides the requested width by the full viewport
width. In the first case, approximately `(2240 - 500) * 425 / 2240 = 330` explains
the measured result. Enlarging the right-panel constant would mask the problem
for one geometry. Existing package docking tests assert requested arguments and
call order, so they cannot catch incorrect realized dimensions.

| Priority | Finding | Consequence for a scientist | Recommendation |
| --- | --- | --- | --- |
| Critical | Visibility, style, legend, selection, provenance and help are interleaved with identical visual weight. | The panel gives no clear starting point or task order. | Separate a compact layer list, one active-layer inspector and a small selected-observation summary. |
| Critical | A four-channel numeric Uniform color editor precedes an active firing-rate legend. Its initial swatch is the first row's color, which happens to be gray for the first missing site. | Gray looks like the layer's overall color although values use viridis. Changing this apparent style control clears the active scalar encoding and table values. | Use an explicit Color by choice. Show a simple color swatch only for Single color. Preserve supplied measurements independently of display mode. |
| High | Requested dock widths are not realized; labels are placed after native default-width controls. | Controls squeeze labels and technical paragraphs wrap into a narrow column. | Correct or explicitly compensate for docking semantics, measure actual bounds, place labels above full-width controls and define a small-window fallback. |
| High | The same layer name appears in a separator and checkbox; counts appear as 192/192 after an explanation at the top. | Repetition consumes space, and scientists must decode counts. | One visibility row, a useful name and a plain count such as 192 sites. Show unavailable-coordinate counts only when nonzero. |
| High | Selected values live inside the legend and use up to 12 significant digits. | A selected value resembles another legend annotation; units can wrap to their own line. | A separate Selected site block, about three significant digits by default, value and unit together, and full precision in detailed data. |
| High | An Original ID combo duplicates table/scene selection and exposes the entire population. Its labels stringify integer and string IDs identically. | It scales poorly, implies one selected object even when several are selected and makes mixed ID types ambiguous. | Select observations through scene/table; summarize exact typed identity. Retain ID lookup only as an optional search action. |
| High | Grouped recordings expand every child's complete controls, raw insertion UUID and source status. | A second recording multiplies noise and hides the comparison task. | Compact grouped layer rows and properties for the explicitly inspected layer; keep exact source identity in details and relevant scientific warnings visible. |
| Medium | Picking help, clipping mechanics, colormap name, coordinate description and API side-effect warnings are permanent prose. | Instructions compete with the measurement and actual warnings. | Keep scientific meaning and unavailable-data counts visible; move routine help/method details behind disclosure. Use concise actionable warnings for actual limitations. |
| Medium | Example-only Select measured site / Select missing FR / uniform-color buttons sit above the spatial view. | Another control surface competes with the right panel and teaches a demo-specific workflow. | Remove these from the normal scientist workspace; use ordinary table/scene actions in review recordings. |
| Medium | The table repeats the legend and metadata and starts with Type/XYZ? details. | A fixed-height table shows very few rows. | Open data on demand; favor Site, quantity with units and region. Keep source/type/coordinates available as additional detail and reserve enough height for useful rows. |
| Medium | The app-1 and generic layer panels implement separate control structures and wrapping rules. | Accepted behaviors and layout improvements can diverge between examples. | Share presentation components while preserving app-1's distinct region-linking diagnostic semantics. |

### Proposed default panel

The default should answer three questions: what is visible, what do its colors
mean, and what did I select? Visibility and ordinary data inspection must remain
available without opening advanced settings. The inspector's active layer is UI
focus; changing it must not select observations or anatomy.

```text
Layers
  [x] Recording sites                 192

Color by
  [ Mean firing rate                  v ]
  Firing rate (Hz)
  [ low -------- middle -------- high ]
  2.41                              45.0
  [gray] 38 sites: no firing-rate value
  [View data]

Selected site
  Site 381                         7.62 Hz
  [Clear selection]

> Appearance
> Source and methods
```

The numeric example uses the current real fixture and rounded display limits;
the exact prepared values and percentile range remain unchanged. Include a brief
population description such as "192 co-located channel groups; not neurons" in
the layer's summary/details, so "site" does not imply a neuron. Explain "no good
unit assigned" with the missing-value key. Present no selection as Select a site
in the scene or table. Multiple selections show their count and an Open selected
rows action; they must never collapse scientific state to one object.

Appearance is collapsed initially. It contains Marker size with the correct
pixel diameter or physical radius unit, and other supported visual controls.
Single color reveals a simple swatch; numeric RGBA channels and alpha policy do
not belong in the default view. Source and methods holds the dataset, insertion,
exact IDs/hashes, scalar derivation, coordinate meaning, percentile choice and
clipping counts. Unknown or inadequate source/coordinate validation must remain
a concise visible warning when scientifically relevant, not disappear in details.

For several recordings, show grouped visibility rows at the top and inspect one
layer at a time. Hiding a group preserves its children's authored visibility,
styles and exact selection. Inspecting another layer must not reset camera,
cursor or table state. Missing positions and missing measurements remain separate.

Use aligned read-only color samples as the first native implementation; a smooth
bar can follow if a suitable primitive is available. Avoid adding a new renderer
or graphics resource subsystem just for a decorative gradient. Put labels above
controls, use available-width sizing, separate value/unit presentation from long
prose, and treat font-size-aware wrapping as layout rather than a fixed characters
per line estimate. A wider panel alone will not repair the information hierarchy.

### Supporting state and implementation sequence

1. Preserve scalar measurements independently of the active coloring mode in the
   shared handle/model, rather than retaining them only in this example. Today
   `LayerHandle.set_color()` discards its `ScalarEncoding`; a GUI-only cosmetic
   rename cannot provide a non-destructive color-mode switch. Specify the API
   change explicitly and preserve immutable arrays, full source alignment and
   transactional table/visual recovery.
2. Rebuild the package panel around the compact layer list and inspector. Unify
   repeated presentation helpers with the app-1 composition without changing its
   separate diagnostic selection meaning. Keep glyph controls conditional.
3. Resolve the narrow native dock-ratio defect separately, with an actual-bounds
   regression. Do not rebuild/change the native checkout or dependency pin as part
   of this audit. Account for both sidebars and table minimum sizes; on a small
   window, let users collapse the Regions browser and keep the data table closed
   until requested. Never silently shrink text to fit all panes.
4. Simplify the companion table/header and record normal user actions. No new
   scientific dataset, broad API refactor, persistence feature or performance
   optimization is needed to establish this layout direction.

### Acceptance criteria

- With one recording, visibility, active measurement/units, color key and missing
  count are understandable without scrolling or opening advanced controls.
- No raw RGBA fields, UUID paragraphs, renderer terminology or arbitrary-ID combo
  appears in the default panel. Scientific caveats remain discoverable and actual
  validity warnings remain visible.
- Switching Single color / measurement changes appearance while table values,
  identities and selections stay intact. Clearing/removing measurements is a
  separate explicit operation.
- Measured zero, missing measurement, absent coordinates, hidden layers and no
  selection remain distinct in wording and behavior. Selected highlights never
  masquerade as scalar colors. Multiple selections are summarized accurately.
- Labels, value/unit pairs and controls fit at the three audited host geometries;
  the narrow-window fallback preserves a usable central view. Native checks read
  actual pane/control bounds rather than only asserting requested sizes.
- Two recordings do not expand two complete property forms by default. A table
  can show useful rows without duplicating a page of legend/method explanations.
- A new 15–20-second Linux clip demonstrates ordinary visibility, data inspection,
  missing values and color-mode switching. User acceptance remains required;
  automated checks and this audit do not supply it.

Runtime measurements and the private diagnostic script remain ignored under
`build/short-reviews/layout-*.json` and `build/short-reviews/audit_layout.py`.

## Generic annotations accepted — October 15 2026

The user validates the interactive annotation workflow. The supplied close-up
shows a small depth/overlap issue where the path reaches a pink point marker;
resolve that remaining rendering detail without changing scientific geometry or
making markers visible through nearer anatomy. A native source audit traces the
likely interaction to pixel-point center depth versus path-cap interpolation;
creation order alone cannot resolve it. A native regression and deliberate depth
policy are needed; the pinned engine remains unchanged. Linked tables and native exact
observation picking remain the next stage, with their own acceptance evidence.


App 1 review began on October 14, 2026, at UI scale 1.5. This log preserves the
reviewer's observations and requested behavior. Implemented corrections remain
subject to manual acceptance. Add subsequent feedback here rather than losing it
in dated implementation handoffs.

## Feedback and status

The reviewer accepted the current app-1 recording-context demo after the reset
and panned-rotation corrections on October 15, 2026: "the demo it is good now".
This closes that visual gate and moves the conversation to a quick public API
review. Earlier requests and their validation details remain historical evidence;
this acceptance does not establish app-2 or additional platform acceptance.

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
| Initial anatomical view | Initial camera/trackball should match the supplied oblique dorsal reference, with the olfactory bulbs toward the lower left and cerebellum toward the upper right. | Implemented a named oblique dorsal preset after isolated reference comparisons; manual orientation acceptance remains open. |
| Opacity discontinuity | Changing opacity from 0.9 to 1.0 causes an abrupt visual change. | Major context now keeps one WBOIT technique throughout opacity 0–1 instead of automatically switching to opaque at 1. Detailed anatomy remains a separate presentation. Approximate transparency and endpoint appearance still require manual review. |
| Coarse colored anatomy | All fine Allen regions and individual cortical layers overwhelm the view. Prefer a light shell with a few colored major structures. | Implemented a shared catalog of twelve verified source-native structures, with six displayed orientation landmarks by default to reduce internal clutter. Fine source geometry is not recolored/merged into a false shell. Manual appearance acceptance remains open. |
| Preserve context on selection | The entire regional brain disappears on selection. Highlight the selected region while keeping the rest intact. | Replaced app-1 focus default with independent context and translucent fine overlays. Coarse-parent selections accent existing context without revealing all fine descendants. Native/real-mouse checks preserve other layers; manual acceptance remains open. |
| Show internal scientific layers | Opaque anatomy hides enabled insertion paths and recording sites, making toggles appear ineffective. | Default now shows one supplied amber path and 192 cyan sites inside low-opacity context; scalar colors are an explicit detail choice. Fine overlays cap alpha at 0.18. Inspected hide/restore captures show the data; manual visibility acceptance remains open. |
| Clear dockable layer controls | The floating, non-dockable Data layers window is confusing. Need simple, clearly labeled visibility controls, with useful icons/colors and immediately visible results. | Implemented persistent dockable Layers with three visibility rows, source counts and color swatches. Toggles use the same retained layer state as programmatic visibility. Advanced renderer comparisons remain secondary. Real mouse and small-window checks pass; manual acceptance remains open. |
| Scientific API foundations | Need modular, well-delimited Python constructs for scientific IBL visualization, rather than a demo settings mixture. | Cross-repository architecture audit is complete; first visual prototype implemented. The broader API scripts/refactor await this gate. The reviewer explicitly authorizes compatibility breaks in this early, unused package. |

## Recording-context follow-up — October 15, 2026

This follow-up supersedes the earlier size, camera and docking preferences. The
Regions browser is improving; the 3D presentation and insertion controls still
need review. The audit below was followed by the authorized correction batch;
automated evidence does not replace manual acceptance.

| Point | Observation or request | Proposed correction and acceptance |
| --- | --- | --- |
| Smaller initial window | Reduce the initial window by 20%. | Implemented 2240 × 1600 instead of 2800 × 2000, retaining the chosen UI scale and monitor-work-area fitting. A monitor-clamped window may need its actual starting dimensions considered during physical review. |
| Revised initial camera | Use the new reference image: a more lateral view, olfactory bulbs lower left and recording nearly vertical at the right. | Implemented lateral-oblique `RECORDING_CAMERA = (-1.15, -0.20, 2.50)` after isolated comparisons, shared with Reset view. Scientific coordinates are unchanged. Exact visual agreement awaits manual acceptance. |
| Layers on the right | Start Layers on the right, rather than below the viewport. | Implemented with the existing right-docking API. Labels precede controls, whose widths adapt to the remaining space. User docking and reserved Regions tree space remain available; manual layout acceptance is open. |
| Uniform blue sites | All 192 sites are cyan and appear to form a tube. Is that correct? | Current color intentionally identifies the layer rather than a measured quantity. Radius 85 µm versus roughly 20 µm adjacent spacing produces heavy overlap. Implemented primary Uniform / Mean firing rate controls and an explicit legend. Default glyph radius is 20 µm, adjustable from 3–40 µm: isolated comparisons found 8 µm too small at overview scale. The fixture's 192 co-located channel groups and missing values are preserved; readability awaits manual review. |
| Compact insertion controls | Color and width do not visibly belong to the identifier above them; the controls take too much space. | Implemented one row per active insertion: visibility, short identifier, editable color swatch and width in pixels. Expandable details show full identities and available session metadata/provenance. These are insertion IDs. Inactive example insertions are omitted; controls remain subject to manual review. |
| Spiky insertion paths | W39 paths generate long triangles, possibly from repeated or unusual points. | Fixed in Datoviz `b3014e111` and `0840010b8`: preserve styles through alpha changes, bound round geometry, partition ordinary joints, skip only derived zero-length edges and retain source query identities. All three original W39 arrays now render byte-identically to adjacent-deduplicated diagnostic references; source coordinates remain intact. Orbit/zoom acceptance remains manual. |
| Zoomed-in panning | Right-button dragging pans too far when zoomed in. | Fixed in Datoviz `53f162f93`: pointer translation now uses camera projection and current dolly depth at the rotation center. A 40-pixel drag stays 40 pixels there across tested zoom levels, FOVs and aspect ratios; orthographic cameras and camera-free controllers retain appropriate behavior. Engine arcball checks pass 33/33; manual feel remains to be reviewed. |
| Actual initial view on double-click | Double-click resets to a different orientation from the actual starting view. | The viewer now registers its configured startup pose through `dvz_arcball_initial`. Double-click and Reset view both use that same native baseline, restoring orientation, pan and zoom. Later programmatic rotations do not redefine startup. A native pixel regression verifies both entry points reproduce the startup frame while retaining selection and explosion. |
| Rotation after panning | The rotation center should follow the panned brain. | The geometric pivot already moved with pan, but the virtual-trackball gesture stayed centered on the viewport. Datoviz `f77b5d05f` now centers pointer rotation on the projected pivot, including pan and zoom. Equivalent gestures around the original and moved pivot produce matching rotations; manual feel remains open. |

### Path investigation and implementation proposal

All three pinned W39 arrays contain 384 channel-derived points. Respectively,
195, 192 and 192 consecutive edges have exactly zero length, already in the
original float64 arrays. These repeated coordinates are not introduced by the
float32 adapter. The BWM fixture has 192 distinct locations and no zero-length
edges. The W39 preparation sorts source channels by axial then lateral position;
it does not provide an independently fitted histology trajectory.

An isolated 800 × 800 offscreen diagnostic projected each W39 array into a plane
and requested a 7-pixel round path. Colored pixels extended approximately 47, 61
and 56 pixels from the nearest authored segment. Removing only consecutive exact
duplicates in a temporary diagnostic copy reduced the maximum to below 3 pixels
for all three paths, with no pixels beyond the conservative 6-pixel envelope.
The source archives and production implementation were unchanged. Script,
captures and measurements are ignored artifacts under `build/path-audit/`.

At Datoviz `efbef43b`, `src/scene/shaders/glsl/path.vert` computes miter-based
extrusion for round joins without a round-join length bound. Zero-length edges
retain immediate neighbors and fallback directions. The integer query vertex
shader already bounds non-miter joins, so visible and queried coverage can
disagree. The WGSL path shader also needs corresponding treatment. This is an
engine robustness defect exposed by valid repeated channel locations; scientific
coordinates should not need smoothing to make it render safely.

Implementation testing also found that generic material synchronization overwrote
stroke caps/join parameters when changing alpha mode. The insertion adapter sets
opaque mode before requesting the already-default round styles, whose setters
then return without repairing the shader payload. Stroke-specific material
synchronization must therefore accompany the bounded-geometry correction. Round
capsules also need complementary joint ownership to avoid applying translucent
alpha twice at ordinary adjacent joins; genuine retracing/self-intersections
remain overlapping geometry.

The approved implementation is now complete: the two engine commits above are
pinned by native `b2f2e1d`; native GUI, camera, size, filtering and responsive
corrections are committed separately. Package validation reports 660 passes and
zero skips; engine path 19/19, segment 5/5 and vector 5/5 pass, with an additional
Vulkan-validated path run. Isolated live captures and mouse checks confirm the
layout, visibility/encoding/radius actions and independently styled W39 rows.
Nearest/linear plane comparisons identify the pale stairs as magnified texture
samples and visibly improve grayscale anatomy without modifying source pixels.
Source/wheel, lint, strict doctor/docs and bounded review startups pass. Manual
composition and physical-platform acceptance remain open; commits are local and
unpublished. The sequence below records the approved implementation plan.

Proposed implementation sequence:

1. In Datoviz `rc4/scientific-3d`, add failing pixel-envelope regressions for
   adjacent duplicates, tiny segments, near reversals and perspective. Cover
   widths, endpoint caps, clipping and query coverage. Replace round joins'
   unbounded miter extrusion with bounded segment rectangles and round endpoint
   coverage; use consistent semantics in display, query and WGSL shaders. Verify
   joins remain continuous and overlap does not introduce alpha/color seams.
   A simple miter-length clamp alone is insufficient evidence of correct width.
   No public API break is expected for this correction.
2. In `ibl-datoviz` `feature/datoviz-v04`, retain source arrays and their verified
   hashes; add a real W39 integration regression with rotation/zoom and independent
   styles. Upgrade the immutable engine pin only after the engine correction and
   compatibility checks pass. Coalescing consecutive identical display control
   points is an optional optimization, not the correctness fix or permission to
   remove channel observations.
3. In a separate native-package UI commit, apply the revised size, camera and
   right dock; compact the insertion controls and expose site-color semantics.
   Existing docking and item-width APIs support the layout; the identified
   required engine work is the path correction. Inspect the pale anatomical
   plane artifact separately rather than assuming it has the same cause.
4. Run bounded isolated GPU checks and fresh review captures, then present the
   updated review commands and remaining manual acceptance items. The broad
   scientific layer API refactor remains behind visual acceptance.

## Scientific workflow direction from the October 15 review

The current app-1 visualization and Data layers experience are not accepted. The
reviewer requests a step back to scientific workflows before further UI patches.
The reference camera image is review evidence, not a new canonical gallery asset.

The initial goal is readable, lightly transparent coarse anatomical context with
distinct major-structure colors; simple toggles should immediately reveal or hide
scientific observations. Selecting a region should highlight it in that context
and help inspect its relationship to the scientific layers. Selection must not
silently isolate anatomy, hide data or change the scientific population.

Requested scientific objects include neurons/units, insertion paths, recording
sites, and data from one or multiple sessions. Alignment results may be shown
when real inputs and their coordinate/provenance contracts are available. Unit
localizations must not be presented as exact neuron soma positions without that
evidence. Source session, insertion, channel and cluster identities should remain
distinct and stable.

Longer term, support ephys-atlas-style quantities on channels, clusters, regions
and voxels, with explicit colormaps, region aggregation, data coverage and slices.
Use the existing web application as a source of refined behavior and data
semantics, and `ibl-ai-agent` as evidence of scientific questions and workflows.
Rendering, data preparation and analysis responsibilities must stay clear.

The reviewer explicitly permits aggressive refactoring and compatibility breaks
in this early, unused package to establish a coherent API. Earlier API-freeze
language in roadmaps is not a constraint on this newly requested design work.
The immediate task is an audited vision, API and staged demo plan; implementation
and visual acceptance follow a separate decision.

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
