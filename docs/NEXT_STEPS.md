# Audit follow up and implementation handoff

## Active branch

Continue all Datoviz v0.4 work on `feature/datoviz-v04`, keeping `main` unchanged
until an explicit merge request from the user. The former envelope,
video-component, viewer-restoration and v0.4-spike branches have been consolidated;
all their commits are preserved in `feature/datoviz-v04` or its `main` ancestry.
Branch names in the dated entries below identify historical implementation batches.
See `AGENTS.md` for the working-branch policy.

## App 1 accepted; API review next — October 15 2026

The reviewer validates the current recording-context demo, including the latest
interaction corrections. The app-1 visual gate is accepted; the immediate next
step is reviewing the existing public API and the provisional recording/layer
facade. App 2 and further platform evidence retain their own review scope.

The [scientific viewer API proposal](SCIENTIFIC_VIEWER_API_PROPOSAL.md) records the
intended single-viewer facade, scientific payloads, recording/layer handles,
anatomy, selection, camera and linked-slice interfaces, along with staged delivery
and open review decisions. It supersedes the earlier `IBLWorkbench` naming sketch.
The proposal is recorded for review; its refactor has not started.

## Consistent reset and panned rotation — October 15 2026

The viewer registers its startup orientation with `dvz_arcball_initial`, so native
double-click and the Reset view button restore the actual initial orientation,
zero pan and unit zoom. The button no longer reapplies the last programmatically
requested orientation after resetting. Subsequent `set_camera_angles()` changes
the current pose without redefining the view's startup baseline. A native pixel
regression checks exact startup-frame restoration through both reset entry
points, after orientation/pan/zoom changes, while retaining selection/explosion.

The geometric rotation pivot already followed view-plane pan, but pointer motion
was interpreted around the old viewport center. Datoviz `f77b5d05f` centers the
virtual trackball on the projected panned/dollied pivot. Equivalent relative
gestures around the original and moved pivot now yield the same rotation at both
tested zoom levels. The engine arcball suite passes 34/34 with zero skips under
Vulkan validation. The immutable source/lock pin is
`f77b5d05f914149858d56c374e7cb69ee23a72b3`; library SHA256 is
`6d8a59ace2bf44d014da92e67cb7457b38767ed8ab5286fc7ee6e3a040ea4d40`.

Manual review should pan, rotate around the moved brain, zoom and double-click:
the configured startup view should return, matching Reset view. Use the existing
isolated Python 3.11 review command below. These corrections remain local commits.

Package tests pass 661/661 with zero skips under Vulkan validation; strict doctor,
lint and strict docs pass. Actual XTest double-click and toolbar clicks restore
the same initial native camera state in the isolated live review app. Its receipt
is ignored at `build/path-audit/reset-gesture-receipt.json`. Native pixel tests
also prove exact initial-frame restoration, rather than only comparing angles.

## Python minimum raised to 3.11 — October 15 2026

Package metadata now requires Python 3.11 or newer; CI tests 3.11 and 3.13.
The refreshed lock removes Python-3.10-only dependencies and resolution branches
without upgrading the retained package versions. The concurrently updated
Datoviz pin remains unchanged by this support-policy change. Historical Python
3.10 validation entries below describe their original environments.

Validation on Python 3.11.15: 659 tests pass, with one explicit skip for the
unconfigured optional registered 10 µm asset root. Strict doctor, lint, strict
documentation, wheel build, and three-frame startups of both review apps pass.
Isolated installed-wheel CPU checks pass on Python 3.11.15 and 3.13.3; receipts
are under ignored `build/python311-validation/`. Startup checks do not establish
visual acceptance or macOS evidence.

Validation used separate environments to avoid interfering with concurrent work.
The untracked local `.python-version` still selects 3.10; update that local pin
before refreshing the normal development environment, or explicitly select
Python 3.11+ with `uv --python` on commands that accept it. The shared `.venv`
was not modified by this change.

## Shared-data integration checkpoint — October 15 2026

The authorized read-only spike exercised validated BWM and portable HC-3 reads
through `ibl-ai-agent-next` without copying datasets or changing its catalogs.
Source IDs, fidelity and provenance survive; the warning-only BWM read is
correctly refused. The next prerequisite for a live anatomy integration is public
BWM channel/unit metadata access, including coordinates and scoped identities.
Do not substitute the existing fixture's geometry for another registered PID.

The [roadmap](REAL_DATA_EXAMPLE_ROADMAP.md) records the concrete findings and two
provisional API scripts for review before broad viewer/controller changes.
Executable probe and JSON evidence are ignored under `build/agent-data-spike/`.
No agent-repository source, viewer implementation or scientific dataset changed
in this investigation. Keep the other agent's visual corrections separate.

## Zoom-aware panning correction — October 15 2026

The reviewer reports excessive right-drag translation when zoomed in. Datoviz
`53f162f93e53fd21cd5e2deaf0947aa26bc8f724` now converts drag pixels to view-plane
translation using camera projection and current dolly depth at the rotation
center. Previously it applied a fixed view-space translation, which perspective
amplified as the camera approached the brain. Both right and middle drag use the
correction. Scene input supplies the current camera independently of rendering;
temporarily bound controller camera state is restored for shared controllers.
No public API or scientific geometry changed.

The native source/lock pin this engine revision. Built library SHA256 is
`69a77246700f7c475d300f8c9475f5fbf966b799c1d9542247ea41b0755b7ef0`.
Engine arcball checks pass 33/33 with zero skips, including projected pixel motion
through real panel input at three zoom levels, two aspect/FOV settings, and both
perspective and orthographic cameras. Manual pan sensitivity acceptance remains
open. Review with `just review 1 --strict --ui-scale 1.5`, zoom in and right-drag
the brain; zoom out and compare. Evidence is ignored under `build/path-audit/`.

Package validation passes 660/660 with zero skips on Python 3.11 and Vulkan
validation, plus strict doctor, lint/docs and bounded app-1 startup. Concurrent
Python-floor/CI/documentation edits are outside this correction and remain
unstaged. Validation uses the separate ignored `build/path-audit/venv311`
environment, preserving the existing environment. Its direct review command is
`build/path-audit/venv311/bin/python tools/review.py run 1 --strict --ui-scale 1.5`.

## Recording-context corrections ready for review — October 15 2026

The authorized feedback batch is implemented and committed locally. App 1 starts
with Layers on the right, compact active-insertion controls, explicit uniform or
firing-rate site colors, and a 20 µm adjustable glyph radius. Narrow docks wrap
insertion widths onto a clearly associated second row rather than clipping them.
Both apps request 2240 × 1600, retaining the chosen UI scale and work-area fitting.
The named initial/reset camera is now `(-1.15, -0.20, 2.50)` after comparison with
the newer lateral reference. Anatomy planes interpolate grayscale; discrete
annotation planes retain nearest filtering. Exact visual acceptance remains open.

Datoviz `rc4/scientific-3d` contains `b3014e111` (preserve stroke styles across
alpha/material changes) and `0840010b8` (bounded round joins, joint ownership,
duplicate derived-edge handling and original query identities). Native source and
lock now pin `0840010b8a901b5e5f5540b979827e25ea48d5b2`; library SHA256 is
`b3a7525208f71065cac57a78a2908f4105d3eaf1dd33b53bad211ff9a713e36f`.
There is no public API change or anatomy asset update. Scientific arrays and
the W39 fixture hashes remain unchanged. True retracing/self-intersections retain
overlapping-stroke semantics; ordinary adjacent round joins partition coverage.

Validation: 660 package tests pass with zero skips using the real asset roots and
Vulkan validation. Strict doctor, lint, strict docs and source/wheel builds pass.
Engine path 19/19, segment 5/5 and vector 5/5 pass; shader ABI/boundary checks and
expanded WGSL Naga validation pass. The engine path suite also passes separately
under the configured Vulkan validation layer. In the original 800 × 800 W39
diagnostic, all three unmodified paths now match their adjacent-deduplicated
reference captures byte-for-byte, with no pixels beyond the conservative 6-pixel
envelope (previously spikes reached 47–61 pixels).

Isolated live captures at 1800 × 1200 and 1300 × 900, UI scale 1.5, cover initial
and scalar states, selection, W39 and nearest/linear plane comparisons. Real
mouse actions verify all primary visibility controls, site encoding and radius,
and independent W39 insertion visibility/width without moving the region tree.
At very narrow viewport aspect ratios the reference camera may need zooming out
or Layers redocked; exact composition and physical-screen/Mac acceptance remain
manual. Both apps pass bounded startup checks. Evidence is ignored under
`build/path-audit/`. No branches were pushed during this correction batch.

Review from the configured workspace:

```bash
just doctor --strict
just review 1 --strict --ui-scale 1.5
just review 1 --strict --ui-scale 1.5 --preset multiple-insertions
```

Check initial size/orientation, Layers placement and compact grouping first, then
uniform versus firing-rate colors and site radius. Orbit/zoom the three W39 paths
and adjust one row's visibility, color and width independently. Follow the
[updated checklist](review-apps.md#app-1-where-did-we-record). Stop at this visual
gate before the broader scientific layer API refactor.

## Recording-context review findings — October 15 2026

The next manual pass requests a 20% smaller initial window, the newer lateral
camera reference, Layers docked on the right, explicit site-color meaning and
compact controls grouped by insertion. The W39 path spikes were reproduced in
an isolated offscreen diagnostic: repeated source coordinates expose unbounded
round-join extrusion in Datoviz, with different rendering/query bounds. The
diagnosis, measurements and proposed engine-first correction are recorded in
[the feedback log](REVIEW_FEEDBACK.md#recording-context-follow-up-october-15-2026).
No production fix or engine pin upgrade has been made during this investigation.
The previous startup/test results do not establish acceptance of these paths.

## First recording-context visual gate — October 15 2026

The approved implementation now reaches the first visual review gate; the broader
scientist-facing layer API refactor remains pending manual feedback. App 1 is
Where did we record?: six original major-structure orientation landmarks at
context opacity 0.04, one amber supplied path and 192 cyan recording sites.
The named camera is `RECORDING_CAMERA = (-0.12, 0.18, 2.50)`, selected through
isolated comparisons against the supplied oblique dorsal reference. Exact visual
acceptance belongs to the reviewer.

The shared anatomy catalog has twelve verified source-native meshes. The default
uses Isocortex 315, Olfactory areas 698, Midbrain 313, Pons 771, Medulla 354 and
Cerebellar cortex 528; six internal context structures remain available through
`--context-detail all` when running the example directly. The inventory rejected
Cerebellum 512's zero normals instead of silently repairing them. Source bytes,
counts, parent lineage, labels and colors are verified; this is incomplete display
context, not a complete closed anatomical partition. `just setup` prepares the
catalog under `build/allen-major-context`; missing/corrupt assets fail explicitly.

Context geometry/colors/opacity remain independent of mapping and selection.
Coarse clicks retain true signed source-parent identities and accent the displayed
surface without exposing all fine descendants. Explicit fine selections add a
translucent overlay capped at 0.18. Other context and scientific layers stay
visible. Hemisphere coverage uses original ML and the atlas's zero-ownership
policy. Context stays at its anatomical reference position during fine explosion.
Major context uses fixed WBOIT throughout opacity 0–1, removing the old implicit
pipeline jump at the endpoint; approximate overlapping transparency remains a
visual-review concern. Library detailed anatomy remains a separate presentation.

Layers starts docked below the viewport with context/path/site visibility and
counts; it can be moved or docked elsewhere. The tree retains full height.
Recording details enables scalar firing-rate colors with units/range and actual
fixture provenance. The supplied path joins channel coordinates; it is not an
independent histology trace. Visibility preserves styles, camera and selection;
Reset view restores orientation/pan/zoom without resetting scientific state.
Datoviz adds only `DVZ_SELECTION_FLAGS_NO_CARD` so applications owning scientific
details can suppress raw visual/item/key cards while retaining native selection.

Pins: anatomy `6498a830e9b078ff4fc4cb06e39436d0fc68aa48`; Datoviz
`efbef43b8fd120519da48088a39deb86df3b1bbe` on `rc4/scientific-3d`.
Native library SHA256:
`368d26834fd99bcc2845b3b7d6b061095256534dd53653d1b258fc5d36a2a4b6`.
Anatomy remains on its permitted `main`; native remains on `feature/datoviz-v04`.
The user authorizes publication of these relevant branches at this review gate.

Validation: 653 native-package tests pass with zero skips and both real asset
roots, strict doctor, lint, strict docs, source/wheel builds and bounded startups
of both review apps at scale 1.5. Anatomy has 153 passing tests with source-backed
inventory checks, package/resource checks and an independent hash/lineage audit.
The narrow engine change passes build, selection/interaction tests, binding/ABI,
API-reference and strict documentation checks. Native context regression proves
parent identities under mapping changes, hemisphere/zero-alpha query coverage,
restoration and fine-overlay alpha. CPU regressions cover ownership, sparse
hover, zero-plane predicates, context replacement and rollback.

Isolated live captures cover 1600 × 1200 and 1100 × 720 at scale 1.5, superficial,
deep and coarse-parent selection, layer visibility and scalar coloring. Real
mouse checks cover all three checkboxes, a cortex pick returning -315, a fine FRP
tree click, explosion and Reset view. These are Linux evidence, not manual or Mac
acceptance. Ignored evidence is under `build/recording-prototype/`.

Run `just doctor --strict`, then `just review 1 --strict --ui-scale 1.5`.
Follow the exact [app-1 checklist](review-apps.md#app-1-where-did-we-record).
Review the visual composition before proceeding to API scripts and the broader
refactor. App 2 is a regression check at this gate, not a new demo redesign.

## Scientific-user review reset — October 15 2026

The latest manual review rejects app 1's focus/isolation default, dense anatomy,
opaque occlusion of data and floating Data layers controls. Earlier automated
validation below establishes mechanics, not product acceptance. New camera,
coarse-context, data-layer and long-term API feedback is recorded in
[the feedback log](REVIEW_FEEDBACK.md). The high-reasoning cross-repository audit
and staged proposal are in [the revised roadmap](REAL_DATA_EXAMPLE_ROADMAP.md#proposed-scientific-workflow-reset-october-15-2026).
No application/engine changes were made during this audit. Review a small visual
prototype before undertaking the proposed broad API refactor; the user explicitly
permits compatibility breaks in this early, unused package.

## App 1 clarity and selection focus — October 15 2026

The primary workflow is now Regions beside a 3D atlas, with permanently visible
Explode, camera-only Reset view, selection display choice and Data layers.
Display settings and optional data controls no longer share the demo/settings
mixture. Data controls follow enabled layers; examples and alternative point
rendering are secondary. Collapse/expand form a tight pair separated from
multi-select. The displayed region total is stable under folding, keeping those
buttons stationary. Both review apps request 2800 × 2000 logical pixels with
opt-in fitting to one monitor's decorated usable area, independently of UI scale.
Offscreen sizes retain their exact requested dimensions.

App 1 defaults to signed selection focus: selected regions and their descendants
retain authored colors/alpha, drawn separately from a faint neutral Allen root
envelope. The root asset is hash-verified, cached by setup under `build/allen-root`,
and loaded offline. Isolate removes the shell; Show all restores whole-brain
picking without clearing selection. Clear selection restores the normal opaque
atlas. The shell is nonpickable and hidden for explosion or hemisphere filtering;
missing shell assets are reported rather than replaced with generated geometry.
Library callers and app 2 retain legacy bilateral dimming by default. Hover stays
disabled initially and uses sparse GPU flags when enabled. Committed focus changes
replace indices/face keys without reuploading retained vertices or dense colors.

Datoviz is pinned locally to `0ae953d3f9e07695d99722eaf9cbcc6a46dbbffa`
on `rc4/scientific-3d`; native library SHA256 is
`3379eee2ad5d4e3d537d9018db33624a116e8c9a1797e7054899e57aec451688`.
The engine adds a persistent selected icon indicator, retaining native hover,
held, keyboard focus and disabled states, plus an explicit default-off work-area
fitting flag. No mesh-part API or anatomy-specific engine behavior was needed.

Validation passes 631 tests with zero skips and both real asset roots, strict
doctor, lint, strict docs, wheel/source builds, and bounded scale-1.5 startups of
both apps. The new native regression compares focused pixels with an opaque
single-hemisphere reference and checks signed FACE picking through a nonpickable
shell. Failure injection covers selection/style/mapping/mode, explosion and shell
replacement rollback; an independent high-reasoning audit reviewed these paths.
Engine build, GUI 25/25, window filter 32/32, binding/ABI/API references and strict
engine documentation checks pass. Isolated fitting checks distinguish fitted
interactive windows from exact-size windows and offscreen views.

Live isolated captures cover app 1 at 1600 × 1200 and 1100 × 720, scale 1.5,
including FRP, deep thalamus, bilateral selection, isolate/all and optional panels;
app 2 has a small-window regression capture. Real mouse checks cover tree click,
multiple-selection mode, collapse/expand, Data layers, explosion and Reset view.
Tree bounds remain stable. Evidence stays ignored under `build/atlas-ux-review/`.
These are Linux checks; physical multi-monitor/macOS behavior and appearance
acceptance remain manual review gates.

All commits are local only; neither main branch nor anatomy/web source or binary
assets changed. The unpublished engine revision is seeded into the local Git
cache for locked review; fresh remote installs await publication. Restart with
`just review 1 --ui-scale 1.5`. Further implementation should wait for manual
feedback; see the updated [feedback log](REVIEW_FEEDBACK.md).

## Expand/collapse icon refinement — October 15 2026

The reviewer found minus/plus ambiguous. Collapse now uses inward-pointing
chevrons and expand uses outward-pointing chevrons, retaining the existing
buttons, tooltips and tree actions. The local Datoviz pin is
`45c82fa4ca60855dc525e80a6e7fe4cc5dbb2cbb`; library SHA256 is
`0da025f107efac630adb86a2e06b8f08e638de04967f219f2278506a6d9cb7b1`.
The engine build and 25 GUI tests pass with zero failures/skips. A live isolated
scale-1.5 capture was inspected under `build/chevron-review/`. This is a glyph-only
refinement of the validated compact layout below; all commits remain local and
manual acceptance remains open.

## Compact region browser: local review snapshot — October 15 2026

The latest sidebar review rejected the earlier reserved-pane layout: it stopped
movement but left the hierarchy in the bottom third of the panel. The replacement
has three compact header rows, a remaining-height tree with its own scrollbar,
and a fixed two-row selection footer. Mapping and visible hemispheres remain
text choices; small vector buttons provide settings, search clearing, multiple
selection, expansion/collapse, sorting when values exist, and selection actions.
Full names and ancestry are available in **Selection details**. **Scene** and
scientific-data controls use ordinary non-docking windows inside the same host;
they do not consume hierarchy height or block the uncovered browser.

Linked slice completion is processed before controls are drawn, including when
settings or the sidebar are closed. Selection transactions, rollback, signed
identities, keyboard/range navigation and deferred fatal GUI cleanup retain their
contracts. Auxiliary windows initially use the actual sidebar edge and live
host size; a host/sidebar resize reapplies bounds, while unchanged layouts retain
user window placement. Hover stays off and scientific data hidden initially.

The local Datoviz pin is `78855559edd5ebfc7eace5228935754f37228b7e` on
`rc4/scientific-3d`. The rebuilt Linux library SHA256 is
`d61b45334531afc6ad491621804a3772d7af09643dc1e249f91826c87c6356b9`.
The additive engine changes supply logical sizing/placement, hinted search,
vector icon buttons, explicit keyboard navigation and opt-in exact tree spacing
and readable secondary labels. Existing tree defaults remain unchanged. Native
icon tests cover coordinate scale 1/2 and user scale 1/1.5, keyboard activation,
disabled activation suppression and transient hover/focus help. The actual GUI
suite passes 25 tests. Bindings, generated API references, documentation status
and strict hermetic engine documentation checks pass.

Consumer validation passes 605 tests with zero skips and both real asset roots,
strict doctor, lint, strict docs and both scale-1.5 bounded app startups. Wheel
and source builds pass; installed-wheel checks pass on Python 3.10 and 3.13 and
include the new private browser module without loading native bindings on import.
Isolated Xvfb/XTest checks pass both apps at 1600 × 1200 and 1100 × 720, scale
1.5, plus app 1 at 1600 × 1200, scale 1.0. They exercise empty/one/twelve
selections, no-result search and clearing, wheel scrolling, real tree clicks with
Details open, closing auxiliary windows, keyboard focus movement, and Scene
clicks that leave brain selection, arcball angles and linked cursor unchanged.
Tree height is 929 pixels at 1200 and 449 at 720, scale 1.5; app 1 has 1,016
pixels at scale 1.0/1200. Selected captures were inspected. Evidence is ignored
under `build/compact-sidebar/`; it is scripted Linux evidence, not human or Mac
acceptance.

All changes in this batch are local commits only. Both `main` branches, anatomy,
web source, binary assets and the engine data gitlink remain unchanged. The local
Git cache contains the unpublished engine revision for locked local review;
fresh remote resolution awaits publication. Restart with
`just review 1 --ui-scale 1.5` (or app `2`) for the next manual review. No further
feature work is planned before that review.

## Review readiness: unmapped surface visibility — October 15 2026

Unmapped presentations are now omitted from native surface rendering and FACE
queries in the active mapping, matching web v2's null-ID handling. This uses the
existing transactional face/index/key filter; mapping switches restore mapped
faces and preserve hemisphere controls and authored styles. Raw canonical mesh
arrays and colors remain available unchanged. No engine, anatomy, web source,
binary asset or dependency pin changed in this follow-up.

For D070, this omits eighteen Beryl presentations (1,244 private draw triangles);
Allen and Cosmos have no unmapped presentations. The previous CI run at
`b0e1268` passed. Local validation passes 594 tests with zero skips and both real
asset roots, strict doctor, lint and docs. A layered native regression checks
that an unmapped foreground neither draws nor occludes a mapped region behind
it, an all-unmapped mapping draws only background, and switching back restores
the source surface. CPU regressions exercise partial/all-unmapped startup,
selection/hover, explosion and hemisphere/mapping transitions. Real D070 checks
cover all eighteen mapping/hemisphere/explode states, signed picks and combined
versus isolated-side silhouette equality. Ignored captures and logs are under
`build/unmapped-review/`; the Beryl capture was inspected. Both review apps also
pass bounded startup at UI scale 1.5 on an isolated display. Manual review is the
next gate; hover stays off by default and scientific layers stay hidden initially.

## Hemisphere coverage and reserved browsing — October 15 2026

Datoviz is pinned to `bf9794f7ba658c7c6256bab054948661d26db403` on `rc4/scientific-3d`. The rebuilt
Linux library SHA256 is `122cca62420db6c0bc85094c8f403e28b1f8f0153d519848d17974b34244d92f`; the anatomy pin remains
`81bd7d79044e4dc3a528abe50a0296381143f03e`. No anatomy/web source, binary assets,
engine data gitlink or canonical gallery media changed in this batch.

Hemisphere rendering and picking now use the verified pack's original-world ML
classifier, including its exact on-plane side, threshold and single-presentation
fallback. A private `SurfaceGeometry` adapter duplicates complete crossing source
triangles into side-specific copies with matching colors, state slots and signed
FACE keys. A generic copied Datoviz fragment-clip input applies complementary
half-space predicates in ordinary lit/unlit opaque, blended and WBOIT meshes and
their queries. There is no atlas-specific engine API, vertex adjustment, triangle
cut/cap, mesh-part API or new query target. Public canonical `mesh_data`, world
normalization and source provenance remain unchanged. Private D070 geometry grows
by 5,937 triangles, approximately 0.6%, and is prepared once in about 0.20 seconds
on this host. Hover/selection retain sparse state updates.

The sidebar now reserves browser space independently of scene controls and
selection details. Each pane scrolls independently; the outer sidebar does not.
Real XTest mouse, wheel and keyboard checks cover both apps at 1600 × 1200 and
app 1 at 1100 × 720, scale 1.5. Search remains reachable and its vertical anchor
does not move after scrolling controls or selecting twelve regions. The tree has
its own scrollbar. New window-height allocation replaces the old fixed tree
height; failed frame updates retain widget rollback and balanced GUI scopes.
The final audit also found a fatal rollback cleanup hazard: callback-triggered
closure now stops the app and defers native destruction until the GUI scopes
and native run loop have returned. `show()` then reports the saved fatal error.

Validation passes 591 consumer tests with zero skips and both real asset roots;
new native regressions cover true-zero coplanar ownership, crossing samples under
camera rotation, hemisphere hiding and all three mappings through explosion and
interaction decoration. Real D070 checks cover eighteen mapping/hemisphere/explode
states, signed picks, and equality between the combined silhouette and the union
of the isolated sides. Captures were inspected. Engine proofs cover twenty-four
shader-emission profiles, twelve native clip coverage profiles, native FACE/ITEM
queries, multi-figure ownership/retry, clip replacement/clear and a deterministic
live WebGPU transition. The final engine scene count is 793/793 with zero failures/skips.

Repeated real-app XTest profiling measures 24.8–25.0 ms tree-hover frames and
36.7–38.1 ms brain-hover frames, compared with the earlier 23–24/30–31 ms indexed
state-only measurements and the original 151/91–101 ms diagnosis. The added
fragment-query work has a measured cost. After warmup, all forty brain queries
complete with zero static uploads/bytes; each forty-frame tree/brain phase
requests 1,600/2,000 flag-payload bytes and uploads no dense vertex colors. These
are bounded NVIDIA/Xvfb diagnostics, not portable frame-rate guarantees. Hover
remains disabled by default in both review apps; click selection remains active.

The real-data repeat caught a temporary clipping-cache regression before push:
a twelve-word cache tuple was copied into an eleven-word executor array. One
shared capacity and a compile-time check now prevent that mismatch; native tests
assert actual warm upload counters through state/style changes and authored clip
replacement/clear. The failed profile is retained separately under ignored
`build/hemisphere-review/cache-regression-before/`. Other evidence stays in
`build/hemisphere-review/` and engine `build/fragment-clip-*` outputs.

The previous CI failure was a separate eager native-binding import in the
benchmark helper module. The import is now deferred to benchmark execution, so
CPU-only helper tests can collect without a native library. Benchmark reports
distinguish canonical asset counts from private render counts and use the actual
render position payload size for explosion updates. Clean wheel/source builds
and isolated installed-wheel checks pass on Python 3.10.17 and 3.13.3 with the
exact locked revision. Strict doctor, full tests, lint, documentation and bounded
three-frame startup checks pass for both apps at scale 1.5. Manual review and
physical platform acceptance remain open. A separate native/web difference for
unmapped Beryl presentations is recorded in [the feedback log](REVIEW_FEEDBACK.md);
this batch does not claim complete rendering-visibility parity.

## GPU interaction state — October 14 2026

The immutable Datoviz baseline is now `a9d943aae9292d40e79ed30c2f8f227259f5053c`
on `rc4/scientific-3d`; the anatomy pin remains
`81bd7d79044e4dc3a528abe50a0296381143f03e`. The rebuilt Linux library SHA256 is
`c6e061e44842e8b1be4c04387a0edd9e4766cf744089f88efbad70e4ec4f28ec`.
Historical dependency metadata still identifies unreleased source snapshots.

Both atlas viewers now bind one scene-owned Datoviz item-state buffer to stable
presentation indices. Hover and selection replace sparse u32 flags and use existing
generic tint/context-alpha styles in the shader. The private `SurfaceState` adapter
maps Allen/Beryl/Cosmos identities at presentation granularity; static indices and
authored vertex colors are retained. The buffer closes before its scene, and
transaction rollback forces restoration after partially failing native setters.
Scalar data, mapping identities and explicit region styles retain their existing
authored upload paths and query semantics.

Selection and hover preserve authored/global alpha. Selected regions no longer
become artificially opaque. Context dimming is decoration and does not remove
scientific pick coverage, including at zero context opacity; authored zero-alpha
regions remain unpickable. Hover tint remains white at mix 0.28, with only the
small shader-versus-uint8 rounding difference from the previous CPU path. Review
apps retain hover-off defaults and click selection; `--hover` enables the new path.

On the RTX 5090, three bounded XTest sweeps of real D070/Beryl at 1600 × 1200,
UI scale 1.5 and opacity 1.0 measure 22.8–24.1 ms tree-hover frames and 30.4–31.1 ms
brain-hover frames, versus prior 151 ms and 91–101 ms. Tree/brain phases request
1,600/2,000 state-payload bytes over 40 frames, with no dense color uploads and no
static query rebuilds after warmup. Native emitted-upload tests separately verify
two distant four-byte writes. The synthetic API benchmark requests eight bytes
per leaf hover/selection update and no dense colors. Actual mouse captures were
inspected and brain click selection succeeds after each sweep. Timings depend on
this GPU, virtual display and other host activity.

Validation: 553 tests pass with zero skips, both verified real roots and Vulkan
validation enabled. Lint, changed-file formatting, strict MkDocs and whitespace
checks pass. The independent engine audit covers ownership, copied atomic updates,
shared figure consumers, upload-failure retry, query revision invariance, twelve
shader emission profiles, six native rendering profiles and a deterministic live
WebGPU state transition. The rebuilt canonical engine scene suite passes 789/789
with zero failures/skips. An initial broader run exposed one stale legacy test
object with missing header dependencies; rebuilding that object resolves all eight
failures without source or expectation changes. Evidence remains ignored in
`build/indexed-state/`.

Clean wheel and source-archive builds pass. Isolated installed-wheel CPU checks
pass on Python 3.10.17 and 3.13.3 with the exact locked dependency revisions;
`surface_state.py` is included and importing it does not load native bindings.
These packaging checks do not certify a distributable Datoviz release artifact.

This is the bounded RC4 indexed-state capability proposed for v0.4. It does not
introduce mesh parts, per-part transforms, draw ranges or a category color palette.
Those larger APIs and asynchronous picking remain post-v0.4 candidates. Physical
platform/user acceptance and distributable dependency certification remain release
gates. Hemisphere-boundary parity and the reserved region-browser layout remain
the next manual-feedback implementation batches; see [the feedback log](REVIEW_FEEDBACK.md).

## App 1 manual-review corrections — October 14 2026

Ongoing user observations, unresolved hover performance, hemisphere-boundary
parity and reserved browser layout are tracked in [the review log](REVIEW_FEEDBACK.md).
Both review apps now default to click selection without tree/brain hover emphasis
or native hover queries. `--hover` explicitly restores the feature. Library callers
can set `enable_hover=False`; their existing default remains unchanged. Native
profiling reproduces 91–101 ms brain-hover and 151 ms leaf-hover frames, dominated
by query geometry invalidation after recoloring. The GPU-state batch above replaces
this interactive recoloring path; these figures describe the original diagnosis.

App 1 now starts with an opaque atlas (surface opacity 1.0 instead of the inherited
probe-context 0.16). The scientific-data window starts hidden; **Show scientific
data** restores the retained table without changing its data or lifetime. Selection
details occupy a fixed-height scrolling area, so leaf selection and longer names
cannot move the browser below them. The shared fix applies to both viewers.

Each frame now copies only mutable selector state, sharing frozen catalog records
and read-only hierarchy indices. Empty-query visibility skips the search-context
scan. Transactional candidate isolation and failure recovery remain intact. On
875 real Allen rows, the local copy microbenchmark fell from 6.261 ms for deepcopy
to about 0.001 ms for the state copy. Bounded hover recoloring measured medians of
0.852 ms opaque and 0.671 ms at opacity 0.16; these CPU timings do not establish GPU
or live interaction performance.

Validation: 548 tests pass, zero skips, on the strict matching native runtime with
Vulkan validation enabled. Lint and whitespace checks pass. Xvfb captures at scale
1.5 confirm hidden data, opaque unselected surface, and an unchanged browser heading
position before/after selection. Evidence stays in ignored
`build/manual-review-fixes/`. No windows were opened on the physical desktop.
Restart app 1 to load the corrections; live responsiveness review remains open.

## Shared IBL region selector — October 14 2026

The native Allen/Beryl/Cosmos browser now follows the refined web selector behavior. `ibl-anatomy` owns the reusable [v1 contract](https://github.com/int-brain-lab/ibl-anatomy/blob/81bd7d79044e4dc3a528abe50a0296381143f03e/docs/REGION_SELECTOR_CONTRACT.md), schema and reviewed synthetic scenarios. Both consumers carry identical, hash-checked offline bundles with immutable source locks: 12 scenarios and 51 transitions. Update the contract first, review expected outcomes independently, synchronize both mirrors through its explicit-source sync/check command, then update both implementations and run their conformance and platform tests. Do not regenerate expectations from a port to make it pass.

Datoviz is pinned to `9aa5fd98e9d31b8e9439e328d62f519b0412575e` on `rc4/scientific-3d`; anatomy is pinned to `81bd7d79044e4dc3a528abe50a0296381143f03e` on `feature/region-selector-contract`. The engine adds opt-in controlled tree projection, bounded input intents, clipped focus and copied row annotations/highlights/tooltips. Generic automatic trees and tables retain their prior behavior. The rebuilt Linux library SHA256 is `7c4e8e6f139465a0e3c4bc6cfb2549f69711b8d0c44c72ae0270799e05307343`. Dependency versions still describe unreleased source snapshots; this is not distributable release certification. CI's synthetic fixture revision matches the anatomy pin.

Python browser state and the native adapter are separate from the existing ontology/catalog translation and host selection. Branch activation folds rather than selects; selectable leaves follow web toggle/multiple/visible-sibling range rules. Search retains matching subtrees and required ancestry, temporarily uses anatomy order and restores ordinary folding/requested ranking when cleared. Keyboard navigation, hover, search highlights, counts and regional value presentation retain the widget inventory. Browser values use exact signed canonical-left identities; right-only data never fill missing left entries or imply bilateral aggregation. Surface/table values keep their authored signed identities. Public viewer methods and selection-source precedence remain intact; programmatic selection preserves focus/folding and linked cursor movement remains independent.

Frame failure restores widget, surface and table feedback. Linked recovery also replaces rejected slice requests with newer revisions containing the prior selection and restores all hover overlays. Failed recovery closes the viewer and workers. Tests cover dropped/failed input batches, partial uploads, mapping rollback, signed survivors, key/focus event ordering, empty search and copied UTF-8 annotation storage.

Validation: **547 tests pass, zero skips** with both verified real roots and strict matching source/library pins, Vulkan validation enabled and no validation errors in the suite log. Lint, changed-file formatting, strict MkDocs and whitespace checks pass. Both review apps pass bounded three-frame startup. Actual XTest mouse/keyboard input in both retained desktop apps at scales 1.0 and 1.5 checks search/clear, multiple mode, collapse, branch activation, arrow navigation, Enter selection and selected-leaf toggle; scale 1.5 also exercises sidebar scrolling. Handles remain stable through ordinary controls. Programmatic checks cover all three mappings. GUI captures were inspected. These are bounded Linux checks, not live user or physical macOS/Windows acceptance.

Clean wheel CPU installation checks pass on Python 3.10.17 and 3.13.3; the installed anatomy bundle also drives all 51 Python transitions without sibling source checkouts. Engine GUI tests pass 22/22, facade checks 11/11, binding/ABI checks and docs pass, and the focused widget Valgrind run reports no errors or leaks. The web full gate passes, including 258 browser tests and four documentation screenshot checks; its exact unpublished candidate passes production-origin checks. Existing optional anatomy real-source and web D070-fixture skips remain explicitly separate from the zero-skip native suite.

Ignored evidence is `build/region-selector/receipt.json`, desktop captures/script/log, `build/region-selector-tests.log`, `build/region-selector-startup.log`, `build/region-selector-docs.log` and `build/region-selector/install/`. Engine receipts are in its ignored `build/controlled-tree-validation/`. No scientific assets, engine data submodule or canonical documentation media were changed. Remaining gates are live design/scientific review, physical platform evidence and distributable dependency certification.

## Two fixed-layout review apps — October 14 2026

The default review workflow now has two applications. `just review 1` opens one
3D scientific viewport with a control/ontology sidebar and persistent data area;
`just review 2` opens the AP/ML/DV plus 3D navigator. Bare `just review` opens 1,
and `just review all` opens 1 then 2. Older named examples remain individual
diagnostics. Presets and layer controls retain existing scenes, figures, views,
panels and camera state; explicit reset restores the initial camera and settings.
See the [review guide](review-apps.md) for the two scenario checklists.

App 1 combines verified D070, the pinned 192-site BWM fixture, a real Allen 50 um
physical plane and optionally prepared W39 paths. It exposes mapping, picking,
ontology, global/signed region/hemisphere styles, point color/size/opacity, path
styles, layer visibility and WBOIT/mask plane controls. Typed probe data/table
remain retained even when analytic spheres are hidden and arbitrary points render
the sites. Presets preserve the table handle and state; mapping changes retain
the established selection-reset policy. Missing W39 data disable the multiple-path
preset with preparation instructions; corrupt present assets fail explicitly.
The table remains the identified BWM fixture and does not claim W39 firing rates.
The visible FR scale states the finite 5th/95th percentile range in Hz; scalar
missing points have alpha zero, while analytic/table missing values are gray.
Detailed encodings are expandable so table rows remain readable at 1.5 UI scale.

App 2 keeps all four views, cursor/slice controls and ontology navigation. Anatomy,
label, volume-context and physical-slice presets change existing layers. A physical
anatomy/annotation plane tracks the chosen axis, cursor and mapping using the source
affine and the existing cached slice composer. Volume context and that plane are
mutually exclusive composition routes without layout changes. Volume resources
are allocated once and zero opacity hides them; this review is not the separate
zero-volume-allocation factory contract. The complete 50 um source is used, with
no substitution of sampled registered sections.

Additive retained-viewer setters expose whole-surface visibility/opacity/style
reset and linked slice-layer/volume-opacity changes. Surface visibility composes
with authored hemisphere/region filtering, including across mapping changes.
Native failures restore public/native state or close on failed rollback. The review
apps close their borrowed-scene point/plane components before the caller's scene;
the linked navigator preserves worker shutdown. Scene presets, volume/plane mutual
exclusion and finalizer cleanup have regression coverage.

Validation: **510 tests pass, zero skips** on Linux/Python 3.10.17 with both real
asset roots and the strict configured RC4 source/library pairing. Two additional
native app tests switch presets/layers in retained views and restore baseline
pixels exactly. Bounded real-data desktop checks at scales 1.0 and 1.5 exercise
every preset, independent paths, styles, point updates, mask replacement, mapping
changes, cursor/plane synchronization and reset. Native handle identity checks and
inspected GUI captures confirm the fixed workspaces and persistent app-1 table
through presets. Both numeric apps pass three-frame startup and offscreen capture;
the new preset and spaced output-path forwarding are checked. Vulkan validation
is enabled and logs contain no validation errors. This remains scripted behavior
evidence, not live scientific/design acceptance.

Lint, changed-file formatting, strict MkDocs, justfile parsing/discovery/argument
forwarding and whitespace checks pass. Built-wheel isolated CPU installation checks
pass on Python 3.10.17 and 3.13.3. Evidence and receipts are ignored
`build/review-apps/`: `tests.log`, `native-tests.log`, `desktop.log`,
`desktop-receipt.json`, `final-startup.log`, `final-captures.log`, and
`install/receipt{310,313}.json`. Datoviz pin/native library, anatomy pin and canonical
media are unchanged from the RC4 migration below; no upstream engine changes or
build were needed. Main stays unchanged. CI for the pushed revision, live user
review, native Python 3.13, physical macOS/Windows and distributable certification
remain separate gates.

## RC4 source migration — October 14 2026

The package now pins Datoviz to `c761eb2404f0ae0d39ec25a7ef96472b11d9ad6e`
on `rc4/scientific-3d`. That upstream commit refreshes the generated alpha-cutoff
bindings; `just ctypes` and `just ctypes-check` pass, including 17 adaptation tests
and 207 ABI records. The source revision and lock agree, with no other dependency
changes. Anatomy remains at `0bd6a63c7c46d4ef0fdd710934e059135b342d7b`.
Datoviz still carries `0.4.0rc2` distribution metadata; this is an immutable RC4
development baseline, not a released RC4 artifact. Both repositories keep their
`main` branches unchanged.

`PointCollectionVisual` now accepts explicit `alpha_mode="wboit"` and reports
order-independent composition. `SampledPlaneVisual` adds opt-in
`depth_policy="physical"` with opaque, blended, WBOIT and mask modes. Physical
planes use unlit textured meshes, owned normals/indices and sampled fields;
mask `alpha_cutoff` defaults to 0.5 with inclusive equality and zero-alpha
discard. The existing blended image-overlay default and linked 2D slice routes
are preserved. Construction, replacement, texture resizing and close retain
transactional cleanup and the borrowed-scene lifetime contract. In-place upload
failure now restores prior pixels even if a failing native upload partially
mutated them. See [component contracts](api/components.md).

Validation on Linux/Python 3.10.17: **461 tests pass, zero skips**, including
explicitly configured D070 and registered real assets, native offscreen component
checks and a maintained signed face-query regression covering hide/opacity,
empty/restore and mapping changes. Native mixed point/plane/mesh captures prove
reversed-order agreement within two channel levels, opaque depth occlusion,
texture holes, cutoff equality/endpoints, effective zero alpha, retained updates
and caller-scene survival. Vulkan validation-layer activation is confirmed by
loader diagnostics; focused and full-suite logs contain no validation errors.
All nine existing real-data examples complete three-frame desktop startup with
validation enabled. Lint, changed-file formatting, strict MkDocs and whitespace
checks pass.

Clean wheel installation checks with locked dependencies pass on Python 3.10.17
and 3.13.3 using isolated imports, owned CPU payloads and offline packaged anatomy
locks. Receipts are ignored `build/rc4-upgrade-install/receipt{310,313}.json`.
Native evidence uses the existing engine library SHA256
`10d3aae8821300b0c09f5be656ae95022d8a2d9c850c810934f7491bdb983d02`;
no engine rebuild, anatomy mutation or canonical-media publication was performed.
The local review configuration now selects the matching RC4 source/library and
`just doctor --strict` passes.

A diagnostic mixed scene combines verified D070 surfaces, all pinned BWM
recording-site coordinates as uniformly colored WBOIT points, endpoint sphere/path
context and an affine-positioned AP slice from the real Allen 50 um pack. Reversed
point/plane attachment order agrees within two channel levels; closing the components
restores the baseline exactly. A physical masked anatomical plane also renders
and restores correctly. Captures were inspected. Inputs, explicit display
encodings, grid/corner coordinates and hashes are recorded in ignored
`build/rc4-investigation/mixed-real-receipt.json`; these diagnostics are scripted
rendering evidence, not scientific or live interaction acceptance.

Other evidence is ignored `build/rc4-investigation/`: `upgrade-tests.log`,
`scientific-native-validation.log`, `query-regression.log`, `upgrade-startup.log`,
`upgrade-docs.log`, `upgrade-lint.log` and `mixed-real.log`.

The first pushed revision passed both CI matrices' unit, wheel-installation and
documentation checks, then exposed stale anatomy imports in the gallery helper:
it implicitly prepended an adjacent fixture checkout's `src` directory. The helper
now uses locked installed anatomy unless the caller explicitly supplies a source
override, with a subprocess regression against a poisoned sibling checkout.
CI's fixture checkout also matches the locked anatomy revision. The local native
synthetic gallery smoke passes (`gallery-smoke.log`); hosted CI retains its explicit
native-runtime-unavailable skip policy.

Next gates are live review of the new mixed scientific workflow, native Python
3.13 and physical macOS/Windows evidence, CI for the pushed package revision, and
eventual distributable dependency certification. Complete registered-section
coverage remains an anatomy gate. Sampled/MASK mesh queries, styled/depth-cued
point queries and transparent sphere/path composition remain explicit engine
exclusions; arbitrary point/site identities do not automatically become atlas
region identities. Optional volume workflows remain supported with their prior
composition limitations.

## RC4 compatibility investigation — October 14 2026

Recommendation: start the package migration on `feature/datoviz-v04` against
Datoviz's integrated `rc4/scientific-3d` branch. RC3 publication is not a
development prerequisite. Existing package behavior is compatible with the
candidate; exposing its new scientific rendering capabilities is a separate
implementation batch.

The investigated package revision is `dd862d59044842e8b7efe3e745d88aedc2b12ba9`.
The engine candidate is `3de114eabbf2205fb0ce9623c9443f25d27d0c34`, with existing
native library SHA256
`10d3aae8821300b0c09f5be656ae95022d8a2d9c850c810934f7491bdb983d02`.
The investigation paired that worktree's facade with its library without changing
the saved review configuration, dependency pins, engine source or build.

On Linux/Python 3.10.17, **404 tests pass, zero skips**, including native component
rendering and explicitly configured D070 and registered real assets. An independent
run using the engine's committed Python package, extracted into ignored build
storage, also passes **404 tests, zero skips** with the same library. All nine
existing real-data examples complete three-frame native desktop startup. Controls,
multiple insertions and volume-free navigation also produce inspected offscreen
captures. These establish current-workflow compatibility, not acceptance of newly
enabled point/plane techniques or scientific/live design approval.

The existing stationary-pointer harness passes three repetitions: zero redundant
queries over 120 unchanged frames, with one fresh query after geometry and camera
changes. A focused extension at a fixed pointer verifies signed Allen key `-434`,
hide/restore, zero-opacity/restore, both-hemispheres-empty/restore, and Beryl key
`-879` followed by Allen restoration. Committed selection survives visibility
and opacity changes; mapping changes retain the documented selection-reset policy.
The existing injected gesture harness passes hover suppression/recovery and
selection preservation, with UI startup at scales 1.0 and 1.5. These are bounded
scripted native checks. No matched performance improvement, explicitly enabled
Vulkan validation-layer run, Python 3.13 native run, macOS/Windows rendering,
browser parity or distributable-artifact certification is claimed.

Evidence, scripts, source/library hashes and receipt are ignored
`build/rc4-investigation/`; test logs are `tests.log` and
`committed-bindings-tests.log`, example evidence is `review.log`, and native
interaction evidence is `stationary-hover.log`, `retained-query.log` and
`gestures.log`. The saved checkout remains at `858bdf261`; `just doctor --strict`
still rejects its mismatch with pin `62101912d`, as expected. Investigation runs
used explicit candidate runtime selection rather than bypassing the strict check.

Original implementation sequence (see the completed migration and remaining gates above):

1. Finalize and commit the upstream generated bindings before choosing the new
   immutable baseline. The RC4 worktree's sole tracked modification adds
   `dvz_visual_alpha_cutoff` and `dvz_visual_set_alpha_cutoff`; the native library
   exports them but the investigated commit's Python bindings omit them. Existing
   workflows do not need these additions; masked-plane support does.
2. Advance the Datoviz pin and lock to the resulting immutable commit, configure
   its matching source/library, and run strict doctor, full tests and bounded
   review startup. Validate clean installation and CI's pinned fixture path.
3. Add point WBOIT in `ibl_datoviz/points.py`, with accurate capabilities and
   native mixed mesh/point/sphere/path order, zero-alpha and retained-update checks.
   Keep current defaults, array ownership and component shutdown contracts.
4. Add an explicit physical-depth path in `ibl_datoviz/sampled_plane.py` while
   preserving the existing blended-overlay default. Physical planes require a
   textured mesh, normals, indices, the `texture` field slot and field sampling;
   changing image flags cannot deliver this behavior. Add WBOIT and MASK/cutoff
   with transactional field/geometry replacement, failure cleanup, depth holes,
   cutoff equality, effective-alpha and reversed-order native checks.
5. Promote focused native query coverage into maintained regression tests and
   review the mixed scientific scene over real data. Distinguish site item IDs
   from region IDs; sampled/MASK mesh queries and style/depth-cued point queries
   remain engine exclusions. Preserve the optional volume and 2D slice routes.

Release artifacts, physical platform proof, complete registered-section coverage
and live interaction/scientific acceptance remain separate gates.

## Reproducible review follow-up — October 13 2026

Implemented on `feature/datoviz-v04`: runnable real-data region/hemisphere,
multiple-insertion and volume-free examples. `just review controls`,
`just review insertions` and `just review volume-free` use the configured native
environment; `--offscreen PNG` captures one named example. `review all` retains
the original six-example sequence. The roadmap documents explicit preparation
of three W39 channel paths from the hash-pinned source parquet. Source and
decoded-array hashes are verified, and existing outputs cannot be overwritten.
Scientific coordinates are converted directly from metres to micrometres;
no fitted or extrapolated trajectory is introduced.

Validation: **404 tests pass, zero skips**, with D070, registered real assets
and native rendering. Lint, changed-file formatting, strict MkDocs and whitespace
checks pass. All three new examples complete three-frame native desktop startup
and offscreen rendering; representative captures were inspected. The original
six examples also complete bounded startup. Logs and images are ignored
`build/review-followup-*`. This establishes reproducible startup and scripted
rendering, not mouse/GUI design acceptance or macOS rendering.

`tools/check_installed.py` checks a built wheel with isolated Python imports,
owned CPU payloads and offline packaged anatomy locks. Clean Python 3.10.17 and
3.13.3 environments pass using the locked dependency revisions, without loading
native bindings. Editable/source imports are rejected. CI now runs this check
on both Python versions; the workflow itself has not yet run on GitHub. Local
receipts are `build/install-review/receipt{,310}.json`; commands are documented
in `docs/getting-started.md`.

Native evidence uses the existing Datoviz source
`858bdf261fe4b8a41b4102a89684e60071e3df66` and library SHA256
`1275a85fdf34149fc2a42afea837ca5c8709c9ff21c769b15b2e3bc8190e26c5`.
No engine source/build, dependency pin or lock changed. Paper CPU acceptance
reporting landed on `feature/datoviz-media`; shared mixed-scene transparency and
plane depth remain engine gates. Video presentation and scientific review remain
deferred; the anatomy coverage audit is a later batch.

## Viewer restoration — October 13 2026

Branch `feature/viewer-restoration` builds on `feature/video-components`. The
authorized batch restores independent region/hemisphere controls, multiple
insertion trajectories and volume-free navigation. Video presentation and final
scientific review are explicitly postponed; paper/media inputs and video files
were not changed by this batch.

Signed-region visibility, RGB(A), opacity and reset controls are available on
AtlasViewer and the linked navigator. Overrides are scoped to the active mapping;
global hemisphere visibility uses canonical side metadata and persists across
mapping changes. Visibility compacts triangle indices and their corresponding
64-bit signed face keys together. Empty/zero-authored-alpha regions do not render
or remain native picking targets; committed linked selection survives hiding.
Palette and scalar alpha now select the native transparency mode correctly, and
selection/hover cannot override authored alpha. Geometry, normalization and
scientific values stay unchanged. Hemisphere filtering uses canonical faces,
without new clipping or cut caps.

Native style, scalar-data and mapping updates are transactional across geometry,
keys, colors, alpha mode, caches and selection. Injected failures restore prior
state; a failed rollback closes the viewer. The earlier explicit-palette mapping
path also now refreshes its ontology model for the target mapping. These updates
preserve the existing mapping selection-reset policy and ProbeSites semantics.

`InsertionTrajectory` and `InsertionCollectionVisual` own validated world-space
paths and provide independent stable string/integer IDs, color, width, visibility,
replacement and removal. AtlasViewer wraps these operations; the original single
`set_probe()` remains independent. Paths explicitly use opaque alpha and depth
testing, with round caps/joins. Transparent paths and trajectory picking/linking
are outside this batch. Components close before their borrowed scene is destroyed.

`LinkedAtlasNavigator(render_volume=False)` omits native volume visuals and 3D
sampled fields. `from_slice_source()` can use a compatible explicit source;
`from_registered_slices()` takes verified registered assets, intensity transport
and an explicit catalog, with no dense volume pack required. Existing volume
factories retain their defaults. Missing registered sections still fail explicitly,
and slice/cursor/selection layers and worker shutdown keep their prior contracts.
Volume-free surfaces use the base alpha policy; positive-opacity bounded volumes
retain their existing source-over limitation.

Validation: **400 tests pass, zero skips**, including explicitly configured D070
and registered real assets, native surface visibility/restore, multiple-path
rendering and no-volume allocation guards. Package lint, changed-file formatting,
strict MkDocs and whitespace checks pass. All six real-data examples complete
three-frame desktop startup. Native checks use Datoviz
`858bdf261fe4b8a41b4102a89684e60071e3df66`, library SHA256
`1275a85fdf34149fc2a42afea837ca5c8709c9ff21c769b15b2e3bc8190e26c5`.
No engine source/build, dependency pin, anatomy asset or shared environment changed.

An ignored real-data review at `build/restoration-review/` uses D070, the existing
complete 50 um slice source and three identified W39 channel-coordinate paths.
Source hashes, selection rule and coordinate conversion are recorded locally.
Native captures exercise left/right/both visibility, selected-region hiding,
regional opacity, independent insertion styles/removal, Allen/Beryl/Cosmos and
empty/restored surface state. Canonical indices remain byte-identical; no native
volume visual/field exists. Representative captures were inspected. This is
scripted native behavior evidence, not exhaustive mouse/GUI design acceptance.
Logs are `build/restoration-final-{tests,lint,docs}.log`,
`build/restoration-example-startup.log` and `build/restoration-real-review.log`.

See [viewer controls](api/viewer.md), [insertions](api/insertions.md) and
[volume-free navigation](api/volume-free.md). Shared point/plane/mesh WBOIT and
depth-correct sampled planes remain upstream work; these restored workflows do
not claim that profile or release/cross-platform certification.

## Paper video components — October 13 2026

Branch `feature/video-components` builds on the reference-envelope branch.
`PointCollection` restores arbitrary scalar/RGBA channel collections independently
of `ProbeSites`. `SampledPlane` owns rectangular world geometry and RGBA textures.
Both payloads own immutable arrays; their visual adapters borrow a caller's
scene/panel and apply its display transform exactly once. They own no app,
camera, GUI or frame loop. Existing public names and ProbeSites semantics remain.

Points support color/size-only updates, full replacement, logical empty payloads
and independent visibility. Planes support pixel/corner updates, texture resizing,
empty/restore, explicit sampling and rollback. Constructor/upload failure releases
candidate resources; close is idempotent and precedes caller scene destruction.
The adapters reject unsupported WBOIT/mask/peeling or true plane-depth requests.
Current plane rendering is explicitly an overlay preview, even with XYZ placement.
See [component contracts](api/components.md).

Validation: **327 tests pass, zero skips**, including explicitly selected real
registered assets and two new native component tests, on Linux with Datoviz source
`858bdf261fe4b8a41b4102a89684e60071e3df66` and library SHA256
`1275a85fdf34149fc2a42afea837ca5c8709c9ff21c769b15b2e3bc8190e26c5`.
The focused component set has 53 passing tests, including native pixel/range
checks for replacement, empty restore, visibility, recoloring, texture resize and
caller-scene survival after close. Package lint, changed-file formatting, strict
MkDocs and whitespace checks pass. Existing formatting differences in unrelated
files were left untouched. Logs are ignored `build/video-components-{tests,lint,docs}.log`.

The engine was updated independently during this work; no engine source/build,
dependency pin or lock was changed here. These checks validate a development
source/library pairing, not released artifact or platform certification. The paper
apps now consume these components and have deterministic capture/export tooling.
Shared mesh/point/plane WBOIT and correct 3D plane depth/cutout remain engine gates.
Independent region/hemisphere controls and multiple insertion controllers remain
broader restoration work; they are not needed by the current two video storyboards.

## Shared Allen reference envelope — October 13 2026

Branch `feature/allen-reference-envelope` adds `AtlasEnvelope`, a companion
display adapter for the shared root-997 asset in `ibl-anatomy`. Its default
offline source is the original smooth Allen reference surface. The adapter
owns its arrays, rejects mismatched reference spaces, and uses the regional
`AtlasMesh` transform without reapplying the source affine or changing D070
positions, indices, presentation identities or framing. Explicit prepared
`annotation-boundary` arrays are supported for diagnostics; no silent fallback
or runtime smoothing occurs.

The paper media apps use this adapter with a prepared Allen envelope. The
companion source has 49,324 vertices, 98,638 triangles and six open edges, so it
remains a display surface rather than a replacement for annotation queries.
Datoviz's source/library and dependency pin are unchanged. The anatomy source
pin is intentionally advanced to the envelope implementation for reproducible
installed use; shared D070 assets remain byte-identical.

The locked anatomy revision is `0bd6a63c7c46d4ef0fdd710934e059135b342d7b`.
Locked resolution and installation pass with no other dependency changes.
The previous fixture cache was preserved and a new cache fetched at that
revision. Standard `just doctor` passes with the existing local Datoviz-revision
warning; `just test` passes 273 tests with one expected registered-asset skip
when its optional environment variable is unset. The explicitly configured
registered root is included in the zero-skip native run below.

Validation: 274 tests pass with zero skips using the configured native facade
and library, D070 and registered real-asset roots. Four adapter regression tests
cover array ownership, shared normalization, reference-space rejection, and
invalid normals/indices. Ruff lint/formatting, strict MkDocs and whitespace
checks pass. Both real paper apps produce reviewed native captures. macOS and
release artifact certification remain separate.

The October 5, 2026 implementation queue has landed: the three reproduced correctness fixes,
documentation/dependency alignment, and R1–R5 extractions are complete. The specifications and
original reproductions below are retained as regression acceptance criteria, not unresolved defects.
Remaining work is live interaction review, complete registered-section coverage, and verification
of eventual distributable RC3/anatomy artifacts. The October 5 package changes targeted the frozen pre-RC3 Datoviz baseline;
no engine source changes were made. The current source pairing is recorded below.

## GPU-independent Python 3.13 validation — October 11, 2026

While NVIDIA driver/library compatibility awaits reboot, a separate ignored environment
(`build/pre-reboot-py313`) validates the locked source snapshot on Python 3.13.3 with
NumPy 2.3.5. **263 CPU tests pass**, with two real-asset tests skipped because their
asset-root environment variables were deliberately unset. The five native offscreen tests
in `tests/test_smoke.py` were explicitly excluded; this run supplies no GPU or rendering
evidence. Synthetic fixtures use the configured pinned anatomy fixture cache. Ruff,
strict MkDocs, and whitespace checks pass. Logs are `build/pre-reboot-py313-{sync,tests,docs}.log`.
The Python 3.13 CPU compatibility check is now covered locally; Python 3.13 native rendering,
macOS, live design acceptance, and distributable dependency verification remain open.
No Datoviz build, source, dependency pin, or primary development environment was changed.

## Recoloring performance and pre-reboot review — October 11, 2026

Python surface emphasis now reuses a bounded descendant index on each retained ontology model. Vertex membership is tested against unique absolute mapping IDs and expanded through an owned inverse array, rather than sorting the full vertex-ID array for each update. Integer row indices avoid repeated boolean-index scans during color reads and writes. Derived arrays still invalidate on mapping/canonical-color changes, and replacement tree models get independent descendant indexes. The first use pays a one-time index preparation cost; steady-state measurements warm this up. The inverse adds approximately 3.9 MB for D070 on a 64-bit host. Public API, signed selection identity, color arithmetic and native ownership contracts are preserved.

A CPU attribution harness over 120 D070 updates with a mix of parent and leaf hover IDs shows ontology expansion falling from 229 to 2 ms total and membership testing from 429 to 8 ms total. Total profiled time falls from 1203 to 401 ms after also changing the color indexing. These numbers include profiler overhead and a fake native setter that copies arrays, so they describe attribution rather than native frame latency. Harness/stats are ignored `build/profile-recolor.py`, `build/recolor-{before,after,indexed}.{log,prof}`. A direct comparison with the previous viewer produces **byte-identical RGBA arrays in 36 real-data cases**, covering Allen/Beryl/Cosmos, parent/leaf hover, signed/multiple selection, clearing and opaque/transparent surfaces (`build/recolor-color-equivalence.json`). Regression tests cover membership, cache invalidation, owned storage and nonmember ontology parents.

The matched native comparison runs the previous package commit `e8e833d` from an isolated checkout and the optimized package with the same D070 asset and native library SHA256 `8fca97bb5d8fec4a3cc57ba6fb587ad5fdd8be4c6416972517809a959dd3d412`. Both use Intel RPL-S/Mesa 25.2.8, 900×720, three fresh-process repeats, 30 warmup and 120 measured frames. Moving-hover emphasis falls from **6.61 to 1.39 ms per call**; isolated emphasis falls from 1.94 to 0.69 ms per call. Median moving-hover frame interval changes from 15.66 to 14.27 ms, with desktop scheduling variance. Query time remains approximately 5.3 ms/frame, with 120 source-view queries and 36 hover changes per repeat. Drag still executes zero queries. Reports/logs are `build/recolor-gui-{before,after}.{json,log}`. At 1800×1440, optimized emphasis is 1.73 ms per moving-hover call, query time 5.34 ms/frame and frame interval 17.05 ms; that resolution has no new matched before run (`build/recolor-gui-after-large.{json,log}`).

`uv run --frozen tools/review.py benchmark -- ...` now uses the saved source/native pairing and D070 assets without changing the shell environment. Benchmark reports preserve NVIDIA diagnostic failures, Vulkan inventory and driver-selection environment alongside library/source identity. Optional `--profile-emphasis` records measured Python function costs, including tree expansion, masks and color upload, and stays off for timing comparisons. Its live hover/idle check passes (`build/recolor-profile-native.{json,log}`). The current NVIDIA diagnostic still reports a driver/library mismatch; no NVIDIA performance result is claimed. Follow [the GPU comparison instructions](development.md#compare-hover-performance-across-gpus) after reboot: verify driver health and the intended Vulkan device before repeating the same unprofiled workloads.

The desktop review repeats hover suppression/recovery with selection preserved, and verifies actual i3 output placement for manual versus automated windows. Filtered-tree captures at 1.0× and 1.5× show the motor-region search and readable selection summary; switching to Beryl completes safely. Captures and checks are ignored `build/recolor-filter-{1.0,1.5}.png`, `build/native-drag-review.json` and `build/i3-placement-{manual,automated}.json`. Full-name tooltips handle clipped rows. User design acceptance remains a live-review gate. All six examples pass three-frame startup at 1.5× scale. **270 package tests pass with zero skips**, including both real asset roots and native offscreen tests; Ruff, strict MkDocs and whitespace checks pass (`build/recolor-{tests,startup,docs}.log`). No Datoviz build, source or pin changes were made for this package optimization.

## Published interaction fixes — October 10, 2026

The current immutable Datoviz pin is `62101912dfde633b4510dfbdbccf7d4a7f0b8ba2`, published on upstream main. It includes the gesture suppression and automated window identity fixes described below, plus stationary GUI move suppression and full-name tree tooltips. Anatomy remains at `119457b68fae6967c54d549d9d44e4a4e49c74f8`. Ordinary local review accepts newer configured checkouts with a warning; only an intentional tested-baseline upgrade changes the pin. A documentation-only commit does not require a new pin.

The embedded viewport now forwards MOVE only when the pointer, viewport size, modifiers, or scene revision changes. Leaving or hiding the viewport invalidates the remembered input. It records the revision after forwarding so its own query request cannot perpetuate picking. Native hover application avoids rebuilding item state for an identical result or clearing an already empty hover. Geometry and camera updates still refresh a stationary highlight; active gestures continue suppressing hover without altering committed selection.

A matched Debug comparison uses the previous library (`7773638736c029c0b496bd5afd3fd37bb17bba53f30c0422ce950b4f8bc58337`) and the current build on Linux, Intel RPL-S/Mesa 25.2.8, D070, 900×720. An ImGui NewFramePre hook injects a constant mouse position into the actual GUI forwarding path, without moving the desktop cursor. Each library runs three fresh viewers with 30 warmup and 120 measured frames. The source viewport executes **120 queries per repeat before and zero after**; the highlight stays visible. Geometry and camera refresh assertions pass after each measurement. Median frame interval changes from 15.36 to 9.71 ms, with substantial desktop scheduling variance, so query counts are the stronger evidence. Reports and the repeatable local harness are in ignored `build/stationary-hover.{json,log}` and `build/check-stationary-hover.py`.

The benchmark now reports GPU query backend/download/decode phases, Python surface emphasis updates, native color setter costs and call counts, and the exact loaded library path/SHA256. Setter and emphasis distributions describe actual calls, while native query phase timings are per measured frame; these denominators must not be added together. Benchmark subprocesses remain marked as automated and use the app's uncapped default instead of an invalid zero FPS environment override.

Moving-pointer profiling uses the same D070 asset, Debug library SHA256 `aeb806ed6852a698a6db03a4b4f3113a3ff259dc60013a5fbfa83f6055751568`, three fresh-process repeats, 30 warmup and 120 measured frames. At 900×720, moving hover executes 120 source-view queries and 35 color setter calls per repeat. Query time is 6.15 ms/frame, including 5.89 ms/frame backend, 0.0057 ms/frame download and 0.0017 ms/frame decode. Surface emphasis is 6.54 ms per call; the color setter is only 0.18 ms per call. The isolated emphasis scenario is 1.92 ms per call with a 0.15 ms setter, so the catalog-backed GUI path and NumPy mask/recolor work need investigation alongside GPU query execution. Drag still executes zero queries and has no hover-hit frames. The 1800×1440 repeat is recorded separately; timings depend on resolution and desktop scheduling and are not portable thresholds. Reports/logs are `build/interaction-performance-stationary{,-large}.{json,log}`.

The sidebar default grows from 340 to 400 logical pixels and scales with the existing UI scale. Native tree row tooltips show the complete acronym and wrapped full name, preserving readable labels on narrow trees. The UI still needs the user's live design acceptance; startup and screenshot checks do not establish subjective interaction quality.

Validation against the published source: **264 package tests, zero skips**, with native offscreen rendering and both real asset roots; **61 native scene-interaction tests and 20 GUI-filter tests, zero skips**; all six real-data examples pass three-frame desktop startup at 1.5× scale. Ruff, strict MkDocs, locked installation, and whitespace checks pass. The native build has no compiler warnings. Logs remain in ignored `build/final-{tests,review,docs}.log` and the native build/test logs. macOS rendering and distributable-artifact verification remain separate release gates.

The first push exposed a native-library dependency during collection of the new viewport unit tests on both CI Python versions. Their fake input constants and ctypes app configuration are now self-contained. A local CI-style run without the native library passes **257 tests with seven expected native/real-asset skips**; the viewport tests themselves run and pass. The configured native suite remains the rendering evidence.

## Initial baseline upgrade — October 10, 2026

At the user's request, the Datoviz pin and lock now select current main
`ab8a8fb4a9c2b1396598a4f7b84653f77321ce9c`, replacing the October 5 pre-RC3
baseline. Anatomy remains pinned to `119457b68fae6967c54d549d9d44e4a4e49c74f8`.
The upstream delta contains a dockspace background fix and conda packaging changes;
no package API or engine source changes were needed for this upgrade.

Locked resolution and development installation, `just doctor`, Ruff, strict MkDocs,
and diff checks pass. The full suite passes **247 tests with zero skips**, including
native offscreen tests and both real asset roots, on Linux/Python 3.10.17. All six
real-data examples pass `just review all --frames 3` on the desktop display, with
no native warning/error messages. The separate Xvfb startup run exits successfully
but reports missing DRI3/presentation support and is not rendering evidence.
Logs are retained locally in `build/current-datoviz-review{,-display}.log`.

The existing native library was used without rebuilding or switching Datoviz;
its SHA256 is `791c649ac26253d609e2b5bc11f7adb4a49d8a3fe867c0397e624a47593c32ac`.
Datoviz distribution metadata remains `0.4.0rc2`. Live interaction review, macOS,
Python 3.13, and distributable artifact verification remain outstanding. The
October 5 validation and benchmarks below retain their original baseline scope.

## Local checkout workflow — October 10, 2026

Local setup, doctor, tests, and review now use the configured Datoviz checkout,
report its revision and the locked install's pin, and warn rather than fail when
they differ. Markdown-only upstream commits no longer require package pin updates.
`just doctor --strict`, `just test --strict [pytest arguments]`, and
`just review all --strict` retain exact-revision enforcement for baseline validation.
The loaded Python facade and native-library checks, pinned anatomy fixture checks,
and locked installs/CI are preserved. This checks runtime paths, not the native
library's build revision; maintain the engine build separately when needed.

Validation: **255 tests pass with zero skips** using both real asset roots and the
native runtime. Regression tests cover local mismatch warnings, strict rejection
before launch for all three commands, matching strict revisions, wrong loaded
paths, and pytest expression forwarding through the recipe separator. `just --dump`,
recipe discovery/formatting, strict doctor/test forwarding, Ruff, strict MkDocs,
and diff checks pass. All six examples pass three-frame desktop startup/cleanup
with `just review all --strict --frames 3`; the log is
`build/local-review-strict.log`. Live interaction and macOS review remain open.

## First live review corrections — October 10, 2026

The reviewer reported lingering hover emphasis during trackball dragging, a cluttered sidebar,
small Linux high-DPI text, and poor perceived performance. A retained viewport input subscription
now clears native/Python hover at gesture start and suppresses it through release until fresh
pointer motion. Committed selection is preserved. The subscription is removed before the viewport
router is destroyed, including partial setup failure. This suppresses the visible highlight;
it does not disable native hover queries.

The sidebar now groups mapping, optional appearance, selection, and region browsing. Region
search labels sit above their fields; hierarchy expansion actions live together in a collapsed
section. Selection acronym/name appear separately and long names wrap. A 18 px base UI font and
`just review picking --ui-scale 1.5` improve readability; all six examples accept that scale,
and the initial sidebar width scales with it. Captures at 1.0 and 1.5 were inspected in
`build/atlas-ui-{1.0,1.5}.png`; canonical documentation images were not replaced. This is the
first UI correction, awaiting the reviewer's interaction/design feedback.

Full native/real-asset tests pass: **262 tests with zero skips and no warnings**.
All six examples pass three-frame desktop startup at 1.5 scale. A scripted native picking
sequence verifies initial hover, no hover during drag, preserved selection, and hover recovery
on fresh motion; `build/native-drag-review.json` records the result. Regression tests cover
stale hover after release, pressed motion, and callback teardown/failure. macOS/high-DPI device
behavior and manual interaction acceptance remain open.

### Current performance investigation

Fresh-process measurements use D070, three repeats, 30 warmup frames and 120 measured frames,
continuous scheduling, uncapped FPS and immediate presentation. Measurements ran against the
working tree based on `d2b2470` and Datoviz `ab8a8fb4a9c2b1396598a4f7b84653f77321ce9c`, using
the existing native library recorded above. They are current-host evidence, not portable
thresholds or an asserted speedup over the October 5 host. Vulkan enumeration lists Intel
Graphics (RPL-S), Mesa 25.2.8, and llvmpipe; the benchmark's NVIDIA-only GPU description is null.
The enumeration log is `build/interaction-vulkan-summary.log`.

| Workload | 900×720 median frame interval | 1800×1440 median frame interval |
| --- | --- | --- |
| Plain surface | 4.29 ms | 8.50 ms |
| Docked GUI idle | 6.80 ms | 12.00 ms |
| Docked pointer hover | 16.54 ms | 20.74 ms |
| Docked pointer drag | 13.60 ms | 15.16 ms |

The existing isolated face-query benchmark costs about 7.4 ms/query before these UI changes;
Python hover-emphasis updates cost about 2.2 ms when changed. New `gui_pointer_hover` and
`gui_pointer_drag` scenarios exercise the embedded surface plus normal GUI and highlight code
with synthetic inside-viewport motion. Events enter the viewport router directly; they do not
measure the OS/ImGui forwarding path or human input latency. The benchmark now preserves all
view timing records, so source-view query work cannot disappear behind the host view's zero
query count. Its source fields report per-source-frame averages; they must not be added to
host frame intervals as independent costs.

Both docked scenarios execute 120 native queries over 120 measured source frames. Dragging
reports zero highlighted hover regions, but source queries still cost about 5–6 ms/frame.
Raw `MOVE` events reach the native item-interaction controller alongside gesture events, and
its `MOVE` branch does not guard against a held camera gesture. Most measured query time is
in the native backend, not query download/decode. The immediate next engine investigation is
to suppress hover-query scheduling during gestures, then rerun the same workload. Separately
profile embedded-viewport rendering and Python region-color uploads while crossing regions.
Also measure stationary-pointer behavior: the GUI forwarding path currently emits `MOVE`
on every rendered frame while hovered, even without actual mouse motion.
No speculative renderer or picking implementation change was made here.

Reports/logs: `build/interaction-performance-{before,after,large}.{json,log}`. The before report
has only the original isolated scenarios; the new combined scenarios have no before counterpart.
The following command reproduces the combined ladder after configuring the helper environment
(as described for direct commands in getting started):

```bash
uv run --frozen python tools/benchmark_atlas_3d.py build/atlas-d070/mesh-pack --regions build/atlas-d070/regions.json --scenarios baseline gui_idle gui_pointer_hover gui_pointer_drag --repeats 3 --warmup 30 --frames 120 --width 1800 --height 1440 --json build/interaction-performance-repeat.json
```

## Native gesture scheduling and automation placement — earlier October 10 checkpoint

The explicitly authorized Datoviz follow-up is committed locally in `6a133d710` (X11 window
instance override and native test-runner marking) and `64cc670ed` (gesture-aware hover queries).
The configured checkout and rebuilt library now include those changes. The immutable dependency
pin stays at published `ab8a8fb4a9c2b1396598a4f7b84653f77321ce9c`; these engine commits have not
been pushed or recorded as a new locked baseline. Local workflow warns about that difference.
Native public headers, Python API, query rendering, and resource ownership were not changed.

Native item interaction now tracks held buttons and gestures, cancels its pending hover requests
on press/drag, clears transient hover, and rejects old hover results through release until fresh
motion. Selection requests/state are preserved. Release and drag-stop events reach the interaction
even outside the panel, preventing a stuck suppression state. The new regression exercises the
same router/gesture-handler combination that emits both gesture events and raw motion.

`DVZ_WINDOW_INSTANCE` overrides the X11 instance while retaining class `datoviz`. Package tests,
bounded review runs and benchmark subprocesses use `datoviz-automated`; interactive review uses
`datoviz`. The local i3 configuration was backed up, validated and reloaded with separate rules:
manual windows on the main left monitor, automated windows on the right portrait monitor. Both
placements were asserted with real windows and i3 tree inspection; records are
`build/i3-placement-{manual,automated}.json`. The setting applies only to child processes.
The optional configuration note belongs in the development guide, not introductory setup.

The same three-repeat, 30-warmup/120-measured-frame ladder was rerun at both resolutions.
A matched Debug control relinks the old interaction/controller objects from `ab8a8fb4a` with
the same remaining native objects; no tracked sources were reverted. Its loaded library path
was asserted after applying the Datoviz environment. The control build script and object/library
provenance are retained in the engine's ignored `build/ibl-hover-control.py` and
`build/ibl-hover-control/provenance.json`. Report checkout metadata is not the substituted
control objects' revision. Candidate reports were collected from the tested working tree before
the native commits, using the rebuilt library recorded below.

| Workload | Control 900×720 | Fixed 900×720 | Control 1800×1440 | Fixed 1800×1440 |
| --- | --- | --- | --- | --- |
| Plain surface | 4.30 ms | 4.28 ms | 8.68 ms | 8.70 ms |
| Docked GUI idle | 8.98 ms | 7.75 ms | 12.53 ms | 12.12 ms |
| Docked pointer hover | 15.95 ms | 17.02 ms | 18.71 ms | 19.21 ms |
| Docked pointer drag | 12.69 ms | 6.46 ms | 14.80 ms | 10.93 ms |

These are host frame-interval medians, not human input latency or portable thresholds. Every
drag repeat drops from 120 native hover queries to zero over 120 measured source frames;
moving hover still executes 120 queries. The original source-view synthetic-input limitations
still apply. The gesture fix addresses the reproduced drag overhead; variation in idle/hover
timings is not evidence of improvements there. Stationary ImGui forwarding, normal hover query
cost, viewport rendering and changed-region color uploads remain separate performance work.
Reports/logs are `build/interaction-performance-{engine,engine-large,control,control-large}.json`,
`build/interaction-performance-engine.log` and `build/interaction-performance-control.log`.

Validation: **264 package tests pass with zero skips**, including both real asset roots; all six
examples pass three-frame desktop startup at 1.5 scale. **60 native scene-interaction tests pass
with zero skips**, including hover cancellation, preserved selection, stale result rejection and
outside-release recovery. The native scripted atlas gesture check passes again. Incremental
Datoviz build succeeds; its pre-existing redundant `_scene_item_state_sync` declaration warning
remains. Native library SHA256 is
`7773638736c029c0b496bd5afd3fd37bb17bba53f30c0422ce950b4f8bc58337` (Debug build).
Unrelated upstream working-tree changes were left uncommitted; its widget portability edit was
included by the normal build. macOS and manual interaction/design acceptance remain open.

## Baseline and completed work

The original audited package revision was `e8bf9f5` on `main`, version `0.2.0.dev0`. Focused follow-up commits are recorded below; the January v0.1 checkout and its removed object API are obsolete. The Datoviz baseline is `066a7451195b38c5e95dcf7af7383b89ec5ec903`, and was the package pin for that audit. The anatomy revision is `119457b68fae6967c54d549d9d44e4a4e49c74f8`.

Already implemented: verified D070 assets, Allen/Beryl/Cosmos presentation, linked ontology and probe/regional tables, orthogonal slices, bounded native volume rendering, registered 10 um slices, latest-wins preparation, lifecycle failure safety, navigator factory restrictions, probe validation, ten supported top-level exports, and locked source-snapshot CI on Python 3.10 and 3.13. Do not reimplement the original five hardening items; [the earlier handoff](RELEASE_HARDENING_HANDOFF.md) records their history.

The original audit passed a normal locked development install, Ruff, strict MkDocs, wheel/sdist builds, and 125 tests against the Datoviz baseline above. Two tests skipped because the real D070 and registered 10 um roots were unavailable. All three synthetic native offscreen tests passed after activating the Datoviz Vulkan environment. The synthetic gallery render and three-frame GUI startup/cleanup checks for both viewer classes passed too. These checks do not establish full real-data interaction quality, cross-platform rendering, or current D070 performance; historical benchmarks retain their original commit and host scope.

## Implementation progress

- Dependency/onboarding alignment landed in `c381fc2`: locked clean install, strict MkDocs, source pairing, materialization recipes, and historical browser labels validated. Complete real-data materialization still needs asset/GPU review.
- R5 complete (`bbe940a`): input adapter owns subscription/callback lifetime; pure wheel, keyboard, zoom, and resize/content-scale decisions preserve interactions. 63 focused input/slice/navigator tests and both three-frame native GUI runs pass. Manual HiDPI/docking review remains outstanding.
- R4 complete (`e6390f3`): immutable requests feed renderer-independent per-axis preparation; named prepared buffers are copied and read-only. Sync and async refresh share preparation/upload. 49 focused tests and two linked native offscreen smokes pass; stale cursor/mapping/selection results and joined shutdown covered.
- R3 complete (`c838e44`): explicit pure selection decisions preserve region-table/probe-table/tree/mesh precedence and propagation; ID/key helpers retain signed hemispheres and stable site keys. 112 selection/GUI/viewer/navigator tests pass. Hover remains independent.
- R2 complete (`48dd405`): GUI helpers own typed retained rows and native handles, clean partial failures, and destroy each handle once. Viewer retains authoritative selection, callbacks, and borrowed control buffers. 105 focused tests pass, including 16 GUI ownership/failure regressions. Live sorting/filtering review remains outstanding.
- R1 complete (`0ba5dae`): pure scalar interpolation and weighted mapping reduction live in `presentation.py`; viewer retains named tuple-compatible adapters and label formatting. 112 focused tests pass, including 23 direct presentation regressions.

- Payload ownership fixed in `91db67e`: all retained numeric buffers are independent C-order copies; 22 focused tests pass.
- Native failure recovery added in `eaad3ed`: one owned upload snapshot restores both geometry and identity after setter failure; failed restoration closes the viewer explicitly. Null construction and failed setup/attachment retry safely with at most one pending scene-owned candidate. 126 targeted tests pass, including 13 added recovery/retry cases.
- Probe replacement fixed in `7cf5988`: successful raw replacement clears typed payload, colors, per-site link keys, and linked table; typed uploads commit identity after validation. Path constructor, caps, and joins now report native failures. 67 atlas/replacement tests and four native offscreen smokes pass, including typed/raw/mapping/typed transitions.
- Native checks use Datoviz source main `066a745` and the local built library with its Vulkan SDK environment. Real assets and live interaction review remain separate evidence.

## Contributor workflow follow-up

`tools/review.py` now owns the package-side setup/test/review workflow; Datoviz remains a separately
built prerequisite. One setup command persists the local pairing, fetches pinned anatomy fixtures,
materializes D070, and builds the 50 um pack from fresh hash-checked downloads. Tests resolve cached
fixtures explicitly instead of relying on an adjacent anatomy checkout. `run` opens the first six
real-data examples sequentially or one named example; `--frames 3` supports bounded startup.

The complete first-time setup and a cached repeat were exercised on Linux. All six freshly
materialized real-data examples passed three-frame native startup through this helper. Its test
command passed 246 tests with one optional registered-root skip; Mac library discovery and failed
pairing/download paths have direct tests, but actual Mac execution remains the next live review.
This follow-up also scopes a lifecycle-test mock to its own viewer so unrelated garbage-collected
viewers cannot contaminate destruction-order assertions.

The repository now provides portable `just` recipes for setup, tests, review, runtime diagnosis,
Ruff, and strict documentation builds. They delegate platform handling to the existing Python
helper and pass arguments through quoted shell positional parameters. Recipe parsing, formatting,
discovery, and forwarding of spaced/quoted paths and multiword pytest expressions pass. Cached
`just setup`, `just test` (246 passed, one optional registered-root skip), and all six three-frame
native examples through `just review all --frames 3` pass on Linux. Actual macOS execution remains
pending; no Datoviz source or public API changes were required.

The README audit removed duplicate setup/materialization guidance, made `just` the contributor
entry point, and clarified that direct Python/gallery/benchmark commands still require manual
runtime pairing because helper environments apply only to child processes. Getting started and
development now share the same recipes and cache paths. Root `AGENTS.md` documents their use,
validation expectations, native ownership, frozen engine scope, and GitHub identity policy.

## Final validation — October 5, 2026

The final implementation revision tested was `4c7788a`; subsequent handoff edits are documentation
only. Additional native review landed `6834a03` (probe selection propagates to the regional table
without reselecting source site rows) and `4c7788a` (empty slice boundaries hide their visual;
nonempty updates restore it). The latter respects the frozen engine's nonzero attribute-count
contract across creation, synchronous refresh, and asynchronous upload.

- Full suite with matching native runtime and both verified real roots: **239 passed, zero skips**.
- Normal locked resolved installation, Ruff, strict MkDocs, wheel/sdist build, and diff checks pass.
- Both viewer classes pass automatic three-frame GUI checks with typed and regional tables,
  raw/typed probe replacement, mapping changes, and repeated cleanup.
- The regenerated synthetic 900×720 gallery image was inspected; tracked canonical images were
  not replaced.
- D070 was verified from `../ibl-anatomy/build/d070-published`; the registered graph was freshly
  materialized into `build/handoff-registered-10um` (59 files, 5,700,497 bytes). Complete fresh
  downloads/builds of the 50 um and 10 um NRRD transports were not rerun; their documented builder
  entry points and the installed readers against existing packs were checked.

Exact local pairing: Python 3.10.17, NumPy 2.2.6, Datoviz source main `066a7451195b38c5e95dcf7af7383b89ec5ec903`
with distribution metadata `0.4.0rc2`, and anatomy source `119457b68fae6967c54d549d9d44e4a4e49c74f8`
with metadata `0.1.0`. The imported Datoviz facade is `~/GIT/Viz/datoviz/datoviz/__init__.py`;
anatomy comes from the locked environment. The library is
`~/GIT/Viz/datoviz/build/src/libdatoviz.so`, SHA256
`2b11f53ba0c891be99a3223747ec1837319580e5112ae11964e6d48c3e8549b1`.
The clean frozen checkout's Debug/Ninja target reports no pending build work. The native environment
uses Vulkan SDK 1.4.328.1 on Linux, NVIDIA GeForce RTX 5090, driver 595.84. Other platforms and the
Python 3.13 CI configuration were not exercised locally during this follow-up.

### Performance evidence

Standard 2-D (25 runs) and 3-D (85 runs) ladders completed sequentially at clean revision `4c7788a`,
with all scenarios, five repeats, 30 warmup frames, 120 measured frames, and 900×720 windows.
The regional update workload ran 100 iterations over 2,194 source regions and 486,674 vertices.
These are host-specific measurements, not portable thresholds or evidence of a renderer speedup.
Historical benchmark results and their original revision/host scope remain intact.

| Workload | Measured time |
| --- | --- |
| Complete 2-D slice, median frame | 8.30 ms |
| 3-D baseline, median frame | 9.32 ms |
| 3-D GUI idle, median frame | 10.34 ms |
| 3-D face query / pointer hover, median frame | 15.44 / 15.48 ms |
| 3-D selection / explosion, median frame | 11.09 / 11.82 ms |
| Regional weighted updates, mean | 8.886 ms |
| Registered AP 660, cold / warm composition | 303 / 16.8 ms |
| Registered ML 566, cold / warm composition | 255 / 19.0 ms |
| Registered DV 401, cold / warm composition | 470 / 28.3 ms |

The registered measurements are a **distinct sampled-graph workload**, not a rerun of the legacy
complete anatomy-v2 benchmark. The bundled graph has AP 165/1320, ML 142/1140, and DV 100/800
sections, with offsets 4, 6, and 1 modulo 8. Default ML 570 and DV 400 are absent. The onboarding
route now previews available sections and makes a complete navigator conditional on a compatible
complete pack. No interpolation, snapping, or substitute scientific annotation was introduced.

Commands and complete logs/results are retained locally in `build/handoff-validation-evidence.json`,
`build/handoff-final-{pytest,gui,gallery}.log`, and
`build/handoff-final-benchmark-{2d,3d,regions,registered-graph}.json`.
The standard benchmark commands are reproducible with the native environment above:

```bash
xvfb-run -a uv run --frozen python tools/benchmark_atlas_2d.py ../ibl-anatomy/build/allen-ccf-2017-50um --repeats 5 --warmup 30 --frames 120 --width 900 --height 720 --json build/handoff-final-benchmark-2d.json
xvfb-run -a uv run --frozen python tools/benchmark_atlas_3d.py ../ibl-anatomy/build/d070-published/mesh-pack --regions ../ibl-anatomy/build/d070-published/regions.json --repeats 5 --warmup 30 --frames 120 --width 900 --height 720 --json build/handoff-final-benchmark-3d.json
uv run --frozen python tools/benchmark_region_updates.py ../ibl-anatomy/build/d070-published --mapping allen --iterations 100 --json build/handoff-final-benchmark-regions.json
```

### Remaining gates

Live review of the first six real-data examples, scientific encoding, sorting/filtering, HiDPI,
and docking is still outstanding. Automatic GUI lifecycle checks and screenshots do not replace
that review. Complete registered-section availability or an explicitly designed absent-section
policy is also outstanding. Verify actual RC3/anatomy distribution artifacts before making release
metadata authoritative; the locked source snapshot does not establish index-package compatibility.

## Correctness fixes (completed regression specifications)

### 1 Preserve successful slice results when another axis fails

Completed: drains now consume one failure at a time while preserving successful
results and other failures. The navigator schedules another owner-thread frame
after a failure, so coalesced notifications cannot strand another axis. The 15
focused queue/scheduler/consumer tests pass, including simultaneous outcomes,
stale failures, and resumed work; Ruff passes for the changed code.

Location: `LatestWinsExecutor.drain_ready()` in `ibl_datoviz/latest_wins.py`, consumed by `ibl_datoviz/slice_scheduler.py` and `LinkedAtlasNavigator._drain_prepared_slices()`.

Reproduction: submit independent keys with two workers, let one preparation return a valid payload and the other raise, and wait for both completion notifications before draining. The first drain raises the worker exception after clearing every ready payload; the next drain returns an empty list. A successfully prepared slice is permanently lost. Multiple simultaneous errors are also cleared even though only the first is reported.

Preserve successful outcomes while reporting failures, or adopt explicit per-key outcomes. Keep the solution compatible with Python 3.10 and preserve generation-based stale-result rejection, bounded pending/ready storage, owner-thread uploads, and wake-up notifications. If results remain queued after an error, ensure the navigator drains them again without requiring a new cursor change.

Acceptance: add deterministic event-based coverage for mixed success/failure, multiple failures, stale failures superseded by newer requests, and continued work after failure. Exercise the scheduler and navigator consumer so one failed axis cannot silently prevent another current axis from uploading. Retain the existing stale-request and shutdown tests.

### 2 Give data payloads independent array storage

Completed in `91db67e`; independent ownership coverage passes for every retained array.

Locations: `ProbeSites.from_arrays()` in `ibl_datoviz/probe.py` and `AtlasRegionValues.from_arrays()` in `ibl_datoviz/regions.py`.

Both constructors promise copied storage, but `np.ascontiguousarray()` can return a caller's existing correctly typed contiguous array. Marking it read-only changes the caller's write flags. The caller can then re-enable writes and mutate the retained payload. This was reproduced for probe positions and regional values.

Make explicit C-contiguous copies for every retained numeric array before setting read-only flags. Preserve dtype, identity validation, missing-value behavior, and the supported constructors. Avoid introducing a new public data API merely to repair ownership.

Acceptance: correctly typed contiguous inputs keep their original write flags; inputs and payloads share no memory; changing an input after construction does not change the payload. Cover strided inputs, all retained arrays, expected dtypes, and read-only output flags in `tests/test_probe.py` and `tests/test_regions.py`.

### 3 Keep raw and typed probe replacement consistent

Completed in `7cf5988`, with additional transactional native-failure recovery following final ownership review.

Locations: `AtlasViewer.set_probe_sites()`, `set_probe_data()`, `_mapped_probe_region_ids()`, `_replace_probe_table()`, and `set_mapping()` in `ibl_datoviz/viewer.py`.

Reproduction: attach two typed probe sites with `set_probe_data()`, replace them with one raw site using `set_probe_sites()`, then change mapping. The rendered geometry has one site, but `probe_data` still contains the old two rows and mapping changes rebind their identities. An existing probe table and cached colors also describe the previous payload.

Define replacement semantics explicitly. Recommended behavior: a successful raw replacement clears typed data, cached typed colors, link keys, and its linked table; a typed replacement establishes all of them together. Separate a private validated upload operation from the two public entry points so the typed path does not accidentally clear its own new state. Validate new inputs before clearing valid old state. Check native constructor and setter failures along these paths, including the currently unchecked path constructor/cap/join setup.

Acceptance: test typed-to-raw and raw-to-typed transitions with equal and different row counts, subsequent mapping changes, existing GUI tables, selection synchronization, and rejected input preserving the previous state. Extend a native smoke or add a bounded native example exercising typed sites, raw replacement, mapping change, and typed replacement. The existing offscreen probe smoke tests only the trajectory line and cannot verify this sites transition.

## Documentation and dependency alignment (completed source snapshot)

1. Update the Datoviz source pin and lock to the intended pre-RC3 baseline, then validate the normal resolved install and the local source/native pairing. Keep the immutable anatomy pin unless a required anatomy change is independently justified. When RC3 is published, verify the actual package artifact and update the supported lower bound accordingly; wheel metadata currently permits RC2 even though the source snapshot uses post-RC2 fixes. A distributable release also needs a deliberately supported anatomy distribution. Do not infer package-index availability from source metadata.
2. Make [Getting started](getting-started.md) one executable fresh-checkout sequence: use `uv run` consistently, use one documented D070 root, include the exact 50 um volume and 10 um intensity materialization commands or an explicit linked upstream recipe, and explain the local Python/native-library pairing. The audited instructions created `build/atlas-d070` but later assumed an unrelated adjacent `d070-published` root; the corrected sequence uses the former consistently. Avoid relying on globally installed dependencies or undisclosed existing assets.
3. Correct the README and historical handoff MkDocs command to use the pinned documentation requirements. Reconcile old present-tense defects, completed API/CI work, and historical test counts. Keep dated benchmark results and exact revisions, but remove claims that old revisions are the current tested baseline.
4. Reconcile [the gallery](gallery/index.md) and its manifest: `lab_ibl_atlas_webgpu_spike` and `wasm-ibl-atlas-spike` are absent from the audited Datoviz main. Label the old proof historical and correct the advertised current reproduction route/capability. Browser feature expansion is a separate later decision, not a prerequisite for these native fixes.

Acceptance: the install and documentation commands work from a clean environment; strict MkDocs passes; all advertised paths and capabilities match their recorded baseline; no completed hardening task is presented as an unresolved defect.

## Refactoring tasks (R1–R5 completed)

`viewer.py` and `linked_atlas.py` are each approximately 1,500 lines. Refactor after the relevant correctness regressions pass, preserving the ten names tested by `tests/test_public_api.py`, factory behavior, coordinate units, signed region identities, cached update paths, and native ownership. Keep each extraction independently reviewable and avoid a renderer rewrite or a generic framework.

### R1 Extract pure scalar and regional presentation

Move scalar color validation/interpolation from `_probe_value_colors()` and mapping collision reduction from `_region_value_view()` into a renderer-independent internal module, such as `presentation.py`. Return named internal presentation records instead of repeatedly unpacking a five-element tuple. Pass catalog, mapping, payload, range, scheme, and opacity explicitly. Keep tree label formatting, orchestration, and native uploads in the viewer initially, and retain its existing method adapters while migrating callers.

Acceptance: direct pure-function coverage for constant values, all-NaN data, explicit ranges, invalid infinities/ranges, weighted mapping collisions, hemisphere identity, void/unmapped omission, and opacity. Preserve the finite-only mean denominator and total displayed weights, missing-value gray, constant-value midpoint, and clipping. Existing probe/regional tests must preserve labels, numerical reductions, colors, and update behavior. This task should require no Datoviz handles and add no top-level export or new scientific aggregation policy.

### R2 Separate retained GUI data from viewer orchestration

Extract row preparation and widget creation/upload/destruction from `_replace_region_tree()`, `_replace_probe_table()`, `_replace_region_table()`, and their selection adapters into internal GUI helpers. Make ownership explicit: viewer cleanup coordinates destruction, while each helper owns its native handle and row model. Datoviz copies row keys, parents, numeric columns, and text at these setters; retain callback and control buffers only where the native API actually borrows them. Keep authoritative selection state and scene mutations in one orchestrator rather than creating a second selection model.

Acceptance: mapping/data replacement still preserves or resets selection according to current tests; native handles are destroyed exactly once; callback/control-buffer lifetimes match their contracts; constructor failure, close, and partial-subclass cleanup stay safe. Preserve site IDs as probe row keys, signed region-key encoding, world DV coordinates, tree parent remapping, and filters. Run synthetic GUI startup/cleanup for both classes and existing tree/table linking tests; review sorting/filtering and linked selection interactively. Do this after the probe replacement fix and R1 so GUI helpers consume consistent presentation records.

### R3 Make selection synchronization explicit

Extract the selection-source decisions in `_sync_selection_highlight()` and ID/key translations in the mesh/tree/probe-table/region-table selection adapters into a small internal controller or pure decision layer. Represent the authoritative source and required propagation explicitly. Keep `_apply_selected_region_ids()` as the viewer's native-update boundary and preserve current event precedence: region table, then probe table, then tree, then changed mesh. Hover remains transient and independent of committed selection.

Acceptance: cover simultaneous widget events, parent-region expansion, hemisphere signs, stable site IDs versus mapped region IDs, clearing, and mapping switches. The native linked GUI must still synchronize surface, tree, both tables, and cursor selection without feedback loops. Follow R2; do not move all rendering, GUI drawing, and picking into a new oversized controller.

### R4 Separate slice preparation from native slice layers

In `linked_atlas.py`, replace the positional worker payload from `_prepare_slice()` with an explicit internal prepared-layer record. Reuse preparation/upload logic for synchronous `_refresh_slices()` and asynchronous `_prepare_slice()` / `_upload_slice_payload()`. Group `_slice_layers()`, boundary preparation, and immutable request inputs separately from native layer creation and mutation. A small internal object for each axis can hold native layer handles and display state; the existing scheduler remains the preparation mechanism. Freeze or explicitly transfer array ownership after preparation; a frozen dataclass alone does not freeze its NumPy buffers.

Acceptance: worker code never calls Datoviz or reads mutable viewer state that should have been captured in its request; uploads only occur on the owner thread; changing mapping, selection, or cursor rejects stale payloads; one axis failure preserves other axes; shutdown joins workers before destroying scene resources. Preserve bounded caches, lightweight hover-overlay updates independent of base slice recomposition, and the independent 10 um slice / 50 um volume contract. Follow the queue fix and compare native linked offscreen output with the current smoke expectations.

### R5 Extract slice input handling without changing interactions

Move the large nested callbacks inside `LinkedAtlasNavigator._create_view()` into an internal input adapter with explicit subscription ownership. Isolate pure wheel accumulation, key-step calculation, zoom clamping, and coordinate-conversion inputs from native event routing. Keep native callback references alive until unsubscription; keep `_create_view()` and `close()` responsible for wiring and lifetime.

Acceptance: cover fractional wheel input, modifier combinations, keyboard hover gating, zoom limits/reset, pointer entry/exit, resize/content-scale conversion, slice clicks, and subscription failure/cleanup. Preserve documented selection versus cursor behavior and keyboard/wheel semantics. Review the actual linked navigator interactively after extraction, including HiDPI and docking coordinates. Schedule this after R4 rather than editing the same module concurrently.

## Real data review and performance follow up

The first focused example batch is implemented but still awaits live review: `real_atlas_surface.py`, `atlas_mapping_switch.py`, `atlas_region_picking.py`, `bwm_probe_geometry.py`, `bwm_probe_firing_rate.py`, and `atlas_slice_scroll.py`. Follow [the roadmap](REAL_DATA_EXAMPLE_ROADMAP.md), record concrete interaction/scientific-encoding feedback, and keep screenshots subordinate to that review. Ensure units, legends, no-data styling, and sampled-versus-context anatomy are understandable before promoting images.

Rerun the existing 2-D, 3-D, registered-slice, and regional-update benchmarks against the chosen Datoviz candidate when the corresponding assets and GPU are available. Record exact source/package/native-library identity and comparable workloads. Preserve historical results; do not invent portable FPS thresholds. Face-query memory, embedded-viewport synchronization, and cold registered-slice composition are later measured optimization targets, not reasons to expand RC3 engine scope. Datoviz already coalesces pointer moves within a frame; do not add an arbitrary Python hover scheduler without new evidence.

## Execution and validation

Recommended commits: queue/error handling; payload ownership; probe replacement; dependency and onboarding alignment; each refactor separately; real-data review corrections. Use subagents for independent queue, payload, and documentation work. Keep the probe/GUI/presentation work under one coordinator and serialize changes to `viewer.py` and `linked_atlas.py` to avoid conflicting edits and divergent ownership decisions. Review each delegated result and integrate its tests before proceeding.

Run from the repository root after building Datoviz separately:

```bash
just setup /path/to/datoviz  # once; setup-tests skips review assets
just doctor
just lint
just test
just docs
git diff --check
```

Local tests use pinned synthetic fixtures in `build/review/anatomy`; CI retains its adjacent
checkout. The helper selects the remembered Datoviz facade and matching native library, using its
configured `direnv` environment when available. `just doctor` verifies imported module and library
paths. Report native/GPU and real-asset skips explicitly. Agent instructions and the contributor
workflow document the same commands on macOS and Linux.

Use `uv run --frozen python tools/build_gallery.py --example atlas-spike --fixture-root <anatomy-fixtures> --output-root build/audit-gallery` for a synthetic gallery check, run `tests/test_smoke.py` with the configured native environment, and check three-frame startup/cleanup of both GUI classes. The two real-asset tests require `IBL_ATLAS_ASSET_SET_ROOT` and `IBL_REGISTERED_ASSET_SET_ROOT`. Benchmark and gallery tools write to the ignored build tree; review pixels before replacing tracked canonical images.

The follow-up is complete when the reproduced failures are covered and fixed, onboarding runs cleanly, dependency evidence matches the pre-RC3/RC3 baseline actually tested, the staged refactors preserve public behavior and native ownership, and outstanding live review or unavailable platform/asset evidence is explicitly recorded. Update this checklist and the roadmap as work lands.
