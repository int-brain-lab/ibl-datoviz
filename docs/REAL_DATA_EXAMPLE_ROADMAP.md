# Real-data interactive example roadmap

Status: the reviewer accepted the current app-1 recording-context demo after the reset and panned-rotation corrections. The next gate is public API review. App 2 and further platforms have separate acceptance scope.

The current API design and implementation stages are in the
[scientific viewer API proposal](SCIENTIFIC_VIEWER_API_PROPOSAL.md). It uses
`AtlasViewer` as the single entry point and supersedes the historical
`IBLWorkbench` sketches. The shared-data findings below inform that proposal;
the source metadata prerequisite has since been implemented locally.

## First visual prototype available — October 15 2026

The first visual gate is accepted: six shared source-native
context landmarks, the reference-oriented camera, one visible real recording,
context-preserving selection and persistent dockable Layers. This supersedes the
rejected focus/isolation default. See [the review commands and checklist](review-apps.md#app-1-where-did-we-record)
and [the implementation evidence](NEXT_STEPS.md#first-recording-context-visual-gate-october-15-2026).
The next gate reviews API naming and multiple-recording layer handles. Alignment
comparisons and new scalar/voxel workflows remain later phases.

## Shared data and IBL controller feasibility — October 15 2026

The user authorized a bounded cross-repository integration investigation alongside
the ongoing viewer work. This does not establish visual acceptance of the current
apps or approval of the provisional API names below.

Keep the dependency direction: reusable data access and IBL source adapters feed
both the agent and an IBL application controller; the controller prepares layers
for `ibl-datoviz`, which retains native presentation/resource ownership. The agent
can author applications through those same public interfaces. Existing compressed
releases remain shared inputs; no second data copy, codec or catalog is needed.

The initial read-only probe exercised existing local catalogs through
`ibl_ai_agent.access`. One source-validated BWM 1.1.0 insertion returned 133,083
spikes with original cluster IDs 21 and 36 under an explicit passed-validation,
100 µs timing requirement. Its stimulus-event read succeeded through a recorded
common-clock mapping, whose synchronization precision remains unquantified. A
warning-only registration was correctly rejected. A source-validated HC-3 package
returned 89,148 events with original codes 0–8 and a declared 25 µs timing bound;
source codes retain their original meaning and are not an implicitly selected
neural population. These are engineering checks, not new scientific analyses.

The initial metadata-access gap has since been addressed locally in
`ibl-ai-agent-next` (`3cdb374`) and the optional `BwmSource` adapter here
(`818e286`). The shared reader now exposes pinned channel/unit metadata and
cluster-to-channel associations. Two insertion reads retained 384 channels/459
units and 96 channels/2 units respectively, without deduplication or cross-PID
geometry substitution. The legacy coordinate convention is an explicit caller
assertion; a complete verified reference-frame contract remains a prerequisite
for the proposed core-payload bridge. Signal failures still prohibit direct-file
fallbacks. These checks do not establish native picking or scientific visual
acceptance.

Evidence and the executable probe live under ignored `build/agent-data-spike/`.
Observed local BWM and HC-3 spike opens took approximately 0.1 s and 0.01 s;
cache state was uncontrolled and the BWM insertion has only two units. These
measurements do not establish full-recording interactive performance.

### Consolidated API review

The earlier `IBLWorkbench` scripts and `layers=` construction sketch are
superseded. Review the [single-viewer proposal](SCIENTIFIC_VIEWER_API_PROPOSAL.md)
and its two proposed scripts: [generic points/paths](proposed_api/generic_annotations.py)
and [two IBL recordings](proposed_api/ibl_recordings.py). `show=` specifies initial
visibility, and supplied populations retain handles even when hidden or entirely
unpositioned. Generic layers and IBL composition share one retained state and
ownership model.

The experimental workbench remains ignored under `build/ibl-integration/prototype/`
as engineering evidence, not a competing API or a supported example. Physical
extraction of the reusable data library and an agent app-authoring skill follow
reviewed contracts and a demonstrated independently tested two-client boundary.

## Proposed scientific workflow reset — October 15 2026

Historical design record: this reset proposal was approved through the first visual
gate. Its asset inventory and implementation checkpoints describe that earlier
stage; the consolidated API proposal and current handoff above govern new work.
Later phases await their own review and visual acceptance. The original audit made no implementation changes. It draws on the native source, Datoviz's RC4 capabilities and release lanes, the web application's data/presentation semantics, and scientific workflows documented in `ibl-ai-agent`.

The first goal is a scientist understanding where a recording lies in anatomy within seconds. The current renderer/settings demonstration is not that experience. Preserve the validated low-level identity, ownership, sparse interaction and failure-recovery work; reconsider the composition and public API. The reviewer explicitly permits breaking this early, unused package's API. Earlier instructions to preserve every export do not constrain this proposal.

### Recommended default experience

- Use a named lateral-oblique camera matching the latest review reference, with olfactory bulbs toward the lower left and cerebellum toward the upper right. Determine actual camera parameters through visual comparison, not guessed Euler angles.
- Start the recording demo with one real BWM recording's sites and supplied path already visible, inside lightly transparent, muted, colored major anatomical structures. An explicit anatomy-only preset can be opaque.
- Keep the Regions browser dominant. Provide a compact persistent, dockable Layers panel with clearly named rows, visibility state, color swatch and useful count. Ordinary visibility should not require opening a floating settings window. Keep style details secondary and the viewport unobstructed.
- Highlight selection without removing or restyling the rest of the context. Accent an already displayed context structure at its authored opacity; reveal a fine selected region as a separate restrained translucent overlay. Do not make selected anatomy an opaque obstacle to its recording sites.
- Keep camera, context opacity, layer styles and selection stable when toggling data. Restore the same appearance when a layer returns. Selection, cursor movement, visibility, scientific filtering and aggregation remain distinct actions.
- Retain hover as an efficient explicit opt-in. It must not rebuild dense geometry or upload dense colors.

### Separate the scientific and visual meanings

| Concern | Contract |
| --- | --- |
| Anatomical mapping | Resolve Allen identities into the chosen labels and selection membership. |
| Context granularity | Choose which actual surfaces are drawn; remapping colors does not simplify geometry. |
| Scientific aggregation | Declare the source population, reduction, missingness, weights and hemisphere policy. |
| Selection | Emphasize regions or exact observations without silently changing population, context or values. |
| Alignment | Display supplied alignment results and provenance; do not infer alignment inside the renderer. |

Channel observations, cluster observations and voxel samples are different populations. Session and insertion identity scope local channel/cluster IDs. Cluster locations are estimates from recordings, not demonstrated exact neuron soma positions. Mapping or bilateral folding must not silently introduce a new scientific reduction or mean of means. The viewer consumes prepared scientific outputs; discovery, loading and analysis remain outside it.

### Anatomy and transparency prerequisites

The D070 asset has 486,674 vertices, 966,645 triangles and 1,140 components. Allen/Beryl/Cosmos presentations reuse this fine geometry. A coarser color mapping therefore does not create the requested clean context shell.

The verified source-native root-997 envelope is available now, but is neutral whole-brain context, not individually colored major structures. Its documented six open boundaries also prevent describing it as a closed anatomical volume. Inventory actual major-region source surfaces and choose a catalog-declared ontology cut without redundant ancestor/descendant surfaces. Intended categories such as cortex, hippocampus, basal ganglia, thalamus, brainstem and cerebellum describe the desired readability, not an already verified asset inventory.

If needed, extend `ibl-anatomy`'s currently root-only surface descriptor into a narrow hash-verified coarse-surface catalog, with Allen identity, reference space, source provenance and hemisphere policy. Shared assets stay there for native and web consumption. Do not concatenate fine meshes or recolor internal layers and call the result a cleaned external shell. An honest neutral envelope can support an early camera/composition study, but does not complete the colored-context acceptance gate.

The opacity discontinuity comes from switching approximate WBOIT mixing below opacity one to opaque frontmost-depth rendering at one. Reducing irrelevant contributors helps clutter; it does not prove correct transparent composition. Sweep representative coarse and dense scenes, diagnose generic engine defects separately, and keep remaining approximation explicit. Depth peeling is not a drop-in replacement for the current indexed-state/fragment-coverage profiles. The scientific API should expose anatomy presentation intent; renderer comparisons belong in diagnostics.

### Consolidated Python boundary

The provisional `from_assets`, `add_insertions`, `add_sites` and `set_coloring`
sketch has been superseded by the [scientific viewer API proposal](SCIENTIFIC_VIEWER_API_PROPOSAL.md).
Review its [generic annotations](proposed_api/generic_annotations.py) and
[two-recording](proposed_api/ibl_recordings.py) scripts instead. They use one
`AtlasViewer`, generic owned handles, optional IBL composition and authoritative
selection state. They are proposed interfaces, not current runnable examples.
Explicit payload replacement remains a later API decision; existing native
transactional update/rollback and resource ownership contracts remain required.

### Two task demos first

1. **Where did we record?** One verified BWM recording's sites and supplied path inside coarse context. Demonstrate independent visibility, uniform versus firing-rate coloring, context-preserving region selection and a small optional site table. Optional verified W39 paths extend the same workflow to multiple insertions; they do not inherit BWM firing-rate measurements. Paths joining channel locations are not automatically independent histology or alignment truth.
2. **Which anatomy surrounds this recording?** Reuse the complete prepared 50 µm source for linked AP/ML/DV plus 3D, with the same recording geometry. Inspect coordinates, move the cursor and explicitly select anatomy. Preserve cursor/selection separation and the volume-free route.
3. **Later: how does a measured feature vary?** Use an actual compatible channel, cluster, regional or voxel release. Show feature, units, population, transform, reduction, missingness and color range. Add this after the first two demos and payload contracts are accepted.

Alignment comparison becomes a targeted extension when real planned/traced/aligned inputs exist. Raster/PSTH dashboards, alignment computation, unrestricted dataset discovery and advanced volume composition are not prerequisites for these first demos.

### Implementation checkpoints, if adopted

| Checkpoint / focused commits | Repository / branch | Gate and agent allocation |
| --- | --- | --- |
| Record rejected review and this proposal | `ibl-datoviz` / `feature/datoviz-v04` | Lead; documentation only. |
| Inventory major-region geometry | Read-only anatomy/web/native | Low-cost agent at medium effort; list available sources and gaps. |
| Add verified coarse-surface catalog if needed | `ibl-anatomy` / `main` | Narrow descriptor/catalog and integrity tests; medium implementer, high independent contract audit. Preserve source geometry and publication boundaries. |
| Camera/context prototype, then recording/selection controls | `ibl-datoviz` / `feature/datoviz-v04` | Medium native implementer, high audit. Reuse internals. **Manual visual acceptance before broad API refactoring.** |
| Review one- and multiple-recording API scripts | Same native branch | High API lead; medium scientific-user review. Decide breaks explicitly. |
| Extract semantic payloads and owned multi-layer handles | Same native branch | Focused data/lifetime commit, then viewer integration commit; medium implementation, high lifetime/identity/rollback audit. |
| Make dockable controls consume layer state | Same native branch | Separate GUI commit; medium implementation. Remove duplicated demo state and default focus/isolation behavior. |
| Replace the two review compositions and document API changes | Same native branch | Separate demo/docs commits; medium integration, high end-to-end audit. Keep diagnostic examples outside primary review. |
| Add real scalar/cluster/voxel workflows later | Native plus relevant preparation/shared-contract repositories | Decide after prior acceptance; medium domain work and high scientific audit. |
| Reproduce/fix a generic engine defect only if demonstrated | Datoviz / `rc4/scientific-3d` | Separate minimal engine commit, generated bindings/docs when needed, medium graphics implementation and high audit. |

Web and AI-agent repositories are read-only design references in this plan. A future web consumer update for the shared coarse catalog would be scoped separately. Continue native work on its existing feature branch; retain the engine RC4 lane and anatomy's permitted main lane. Prepare local commits only; publication remains a separate decision.

### Acceptance and release boundaries

First visually accept the named orientation, readable colored coarse context, visible recording geometry, understandable layer toggles and context-preserving superficial/deep selection. Then review multiple insertions, signed sides and descendants, exact object identities, missing values and units, opacity sweeps including 0/low/0.9/1, linked slice orientation, small windows/HiDPI, transactional replacement/empty/restore and clean shutdown. Automated startup and inspected captures do not replace scientific manual review or actual platform evidence.

Datoviz already has docking; the current app helper explicitly applies NoDocking. Fixing this does not require a new engine docking system. The RC4 engine also already supplies the principal non-volume composition, retained-state and query primitives. An arbitrary native point adapter does not automatically provide all the scientific picking/linking semantics needed by a new layer API.

Keep RC3 scoped to existing correctness/capability work. RC4 owns required scientific composition and package acceptance; RC5 is contingency for unresolved acceptance gaps; final v0.4 closes exact-candidate validation without new semantics. Full mesh parts and asynchronous queries remain early-v0.5 work. Advanced OIT/volume composition and broad WebGPU parity remain separately scoped.

## Current review workflow — October 14 2026

`just review 1` opens the 3D scientific workspace with a persistent control/ontology
sidebar and data area. `just review 2` opens the linked AP/ML/DV plus 3D workspace.
Presets change layer visibility/settings in the existing views; normal edits preserve
camera and cursor, while explicit reset restores the starting state. Bare `just review`
opens app 1, and `just review all` runs 1 then 2. Older named examples remain individual
diagnostics. This replaces the original six-launch default sequence.

The [review guide](review-apps.md) defines the two in-app review checklists, scientific
encodings, optional W39 preparation and native rendering limits. Reviewer preference
is now fewer applications with more interactions and stable visualization structure.
The earlier one-capability-per-example inventory remains useful for isolated regression
diagnostics; live acceptance should use the two integrated workspaces and their layer
toggles to isolate features.

## October 14 region-browser convergence

Both fixed-layout apps now use the shared IBL region-selector behavior derived from the refined web browser. Follow the [region-browsing checklist](review-apps.md#region-browsing-in-both-apps), especially parent versus leaf activation, search/folding restoration, modifier ranges, keyboard focus and external selection. The anatomy contract and offline conformance bundle protect shared behavior; native rendering and platform review remain separate. See the [handoff](NEXT_STEPS.md#shared-ibl-region-selector-october-14-2026) for pinned revisions, failure recovery and validation evidence. Browser value annotations use exact canonical-left signed identities and never substitute right-side values.

## Product decision

`ibl-datoviz` has validated a substantial native rendering stack, but it is not yet mature enough
to present a showcase image as a product-level hero. Keep the README and documentation landing
page text-first until the interaction model, visual encodings, public API, and packaging contract
have been reviewed through live examples.

The review apps are the next product-discovery tool. Use real, pinned IBL data and
fixed views with layer controls and presets so the reviewer can isolate interactions
or visual encodings without relaunching. A dense scene must still allow its individual
parts to be hidden or inspected independently.

The regional BWM surface example remains a development checkpoint, not a whole-brain scientific
figure. Do not promote it as a hero. Revisit it only after its scientific question, sampled versus
unsampled styling, legend, and title are explicit.

## Current maturity

The strongest implemented path is the native linked atlas workflow:

- verified D070 surface geometry and Allen/Beryl/Cosmos presentations;
- arcball navigation, WBOIT transparency, face picking, hover, selection, and region explosion;
- ontology navigation and linked probe/regional tables;
- AP/ML/DV anatomy and annotation slices with a shared world-space cursor;
- mapping-aware slice boundaries and a bounded 50 um anatomical volume;
- optional registered 10 um slices with lazy decoding, caching, and latest-wins preparation; and
- native interactive windows, deterministic offscreen capture, gallery generation, and diagnostic
  benchmarks.

This is still a development branch rather than a stable library. Lifecycle safety, navigator factory behavior, input validation, the public API freeze, and source-snapshot dependency/CI alignment are implemented. Follow [the audit handoff](NEXT_STEPS.md) for current correctness fixes, refactoring, documentation repairs, and release validation; the [earlier release handoff](RELEASE_HARDENING_HANDOFF.md) records the original review. The small WebGPU fixture proof is historical; the gallery now records that its old build route is absent from frozen Datoviz main; parity for the Python viewer, GUI, picking, WBOIT, and volume rendering is not established.

## Work order

Progress: viewer lifecycle failure safety, navigator factory behavior, input validation, the public API, and reproducible source-snapshot CI are implemented. The first six focused example programs and reproducible gallery commands are in place; live review remains the next product gate before any image or interaction is promoted.

The October 13 restoration batch adds three independently runnable real-data examples:
`atlas_region_hemisphere_controls.py` for signed region styling and hemisphere state,
`bwm_multiple_insertions.py` for independently styled paths, and
`atlas_volume_free_navigator.py` for slice navigation without native 3D volume allocation. They
use the verified D070 asset set and 50 um source prepared by `just setup`. The multi-path example
reproduces its ignored derivative in `build/w39-insertions/` from an explicitly supplied,
hash-pinned W39 `channels.pqt`; the builder records source and decoded-array hashes.

1. Validate the landed correctness fixes and staged refactors against the current pinned Datoviz baseline; see [the audit handoff](NEXT_STEPS.md) for evidence and remaining release gates.
2. Review both fixed-layout real-data apps interactively using their scenario checklists.
3. Iterate on controls, feedback, visual encodings, and scientific descriptions.
4. Add the linked and higher-resolution examples once their component interactions are accepted.
5. Preserve the tested public Python API while reviewing the workflows.
6. Complete published dependency compatibility, reproducible onboarding, current documentation, and release notes; source-snapshot CI alignment is already implemented.
7. Treat browser/WebGPU expansion as a later product decision, not as a prerequisite for native
   feedback.

Do not undertake speculative renderer optimization during this sequence unless a focused example
demonstrates a user-visible problem. Existing 2-D and 3-D benchmarks already identify face-query
memory, embedded-viewport synchronization, and cold registered-slice preparation as the meaningful
costs.

## Capability ladder

Each program should have one primary capability even when it needs a minimal atlas surface or
slice as context.

| Proposed example | Primary capability | Real data |
| --- | --- | --- |
| `real_atlas_surface.py` | Orbit one D070 atlas surface | Pinned D070 mesh pack |
| `atlas_mapping_switch.py` | Switch Allen/Beryl/Cosmos presentation | D070 mesh and region catalog |
| `atlas_region_picking.py` | Hover and select a surface region | D070 face identities |
| `atlas_ontology_link.py` | Link surface selection with the ontology tree | D070 catalog and mesh |
| `bwm_probe_geometry.py` | Display one probe trajectory and channel positions | Pinned BWM insertion |
| `bwm_probe_firing_rate.py` | Color sites by firing rate and show missing values | Pinned BWM insertion |
| `atlas_slice_scroll.py` | Scroll one anatomical slice plane | Pinned Allen volume pack |
| `atlas_slice_boundaries.py` | Show mapping-aware region boundaries | Allen annotations and catalog |
| `atlas_triplanar_cursor.py` | Synchronize one cursor across AP/ML/DV slices | Pinned Allen volume pack |
| `atlas_registered_slice.py` | Lazily display a registered 10 um slice | Exact registered anatomy packs |
| `atlas_volume.py` | Render the bounded anatomical volume | Pinned 50 um template volume |
| `linked_atlas_navigator.py` | Integrate already-reviewed capabilities | All compatible pinned assets |

The first implementation batch should stop after six examples:

1. real atlas surface;
2. mapping switch;
3. region picking;
4. BWM probe geometry;
5. BWM firing-rate sites; and
6. single-plane slice scrolling.

This batch establishes the basic rendering and interaction vocabulary without asking reviewers to
debug the complete navigator at once.

## Example contract

Every promoted example must satisfy the following contract:

- use real, immutable IBL data with recorded provenance, source version, and hashes;
- have one obvious interaction and one stated primary capability;
- run interactively by default in a native window;
- support deterministic `--offscreen` capture for smoke tests and reviewed gallery output;
- expose only controls needed for the primary capability;
- explain every color, geometry, opacity, aggregation, and missing-data encoding;
- avoid hidden scientific derivation or aggregation;
- use stable identities from the asset/catalog contracts rather than display labels as keys;
- declare native, offscreen, and WebGPU capability honestly in the gallery manifest; and
- include focused automated coverage for its data preparation and viewer calls.

Examples should be independently runnable. Do not require a user to start from the full navigator
to inspect a basic feature. Shared implementation belongs in `ibl_datoviz`; examples should remain
small compositions rather than alternate application frameworks.

## Data and provenance policy

Interactive examples should not depend on a live network service. Extract the smallest useful
fixture from an immutable release, record the source dataset and selection rule, hash both source
artifacts and the committed derivative, and make any lossy reduction explicit. Large atlas assets
remain materialized through `ibl-anatomy` locks rather than copied into this repository.

The existing BWM fixture is appropriate for geometry and one scalar-site example. Additional
scientific capabilities should be driven by additional real use cases rather than by adding
synthetic metrics to that fixture. Coordinate-to-annotation lookup and scientific atlas
computation remain outside `ibl-datoviz`; this package consumes resolved identities and owns their
visual presentation and interaction.

## October 5 follow-up evidence

The three reproduced correctness bugs, source dependency/onboarding alignment, and R1–R5
extractions have landed in focused commits. The final full suite passes 239 tests without skips with matching native runtime and both verified
real roots. Synthetic native offscreen checks, bounded table GUI startup/cleanup, and standard
sequential 2-D/3-D benchmarks pass at implementation revision `4c7788a`. These checks
still do not supply live feedback for the first six examples, sorting/filtering, HiDPI, or docking.
Keep those review gates open and retain the text-first presentation.

The bundled registered graph `ibl-atlas-projections-05b9f3f85db9` contains sampled sections:
AP 165/1320, ML 142/1140, and DV 100/800, at offsets 4, 6, and 1 modulo 8 respectively.
The center ML index 570 is absent. A complete 10 um navigator therefore needs a compatible
complete registered pack; the current sampled deployment cannot establish arbitrary cursor
navigation. Define absent-section behavior or supply complete assets before promoting that route.
No interpolation or alternative scientific geometry was introduced during these refactors.

## October 10 interactive feedback

The first live feedback identified hover emphasis during camera dragging, small Linux high-DPI
text, scattered sidebar controls, and poor perceived performance. The package now clears/suspends
hover during gestures, groups the sidebar by task, uses a larger base font, and exposes
`just review picking --ui-scale 1.5`. Native scripted gesture checks and inspected UI captures
support this first correction; reviewer acceptance remains open. The subsequent local Datoviz
fix stops native hover queries during dragging while preserving selection. Manual review windows
now use the main monitor, with tests and bounded review/benchmark runs routed separately by i3.
See [the handoff](NEXT_STEPS.md) for measurements, workload limits, and remaining stationary-pointer
and moving-hover work. This feedback does
not establish acceptance of the remaining first-batch examples.

## Feedback loop

For each example, ask the reviewer to evaluate only:

1. whether the stated capability is scientifically and visually understandable;
2. whether the primary interaction behaves as expected;
3. whether missing, selected, hovered, and contextual data are distinguishable;
4. whether the default camera, scale, contrast, and control placement are useful; and
5. what concrete behavior should change before the example is composed into a larger workflow.

Keep screenshots subordinate to the live review. A gallery image is a regression artifact and a
discovery aid, not evidence that an interaction is mature.

## October 13 runnable examples

After `just setup /path/to/datoviz` has materialized `build/atlas-d070` and
`build/allen-ccf-2017-50um`, prepare the BWM trajectories from the exact W39 channel release.
The parquet belongs to `ephys_atlas_channels/2026_W39-ibl-review-20261007-v1`; its release root
manifest SHA256 is `6adc9fa963196d6db829125c5ac869c49bec7622ec7397e8503965f79476a2b8`, and the
`channels.pqt` SHA256 is `17dd0a9be89a7eea683d05a6c34170726bde47e66d509aba5217932dbffff52e`.
For acquisition details and ONE-authenticated download instructions, see the paper repository's
[`sources/media/README.md`, Scientific inputs section](https://github.com/int-brain-lab/paper-ephys-atlas/blob/feature/datoviz-media/sources/media/README.md#scientific-inputs)
and `sources/media/prepare.py --download-source`; those instructions acquire the immutable W39
objects and do not change this repository. The builder requires pandas plus pyarrow and reads the
local file only:

```sh
CHANNELS_PQT=/path/to/channels.pqt
uv run --frozen --with pandas --with pyarrow python tools/build_w39_insertions.py \
  --channels "$CHANNELS_PQT" --output build/w39-insertions
just review controls
just review insertions
just review volume-free
just review insertions --frames 3
just review insertions --offscreen build/w39-insertions.png
```

`build_w39_insertions.py` selects the first three lexically sorted PIDs, keeps finite channel
geometry where `labels != 3`, sorts by axial then lateral position, and converts source XYZ
metres to atlas-world micrometres. It adds no fitted or extrapolated path points. The example
defaults to distinct path colors and widths; repeat `--insertion-width PID=PX` or add
`--hide-insertion PID` to inspect independent controls. Region controls default to the left
hemisphere with one region opacity preset; the `controls` review opens an unbounded native window.
`--frames N` bounds startup and `--offscreen PNG` captures an initial state. The volume-free
navigator reads slices from the real Allen 50 um pack with `render_volume=False`, so it creates no
native volume visual or 3D sampled field.

## Promotion gates

Do not restore a hero image until all of the following are true:

- both fixed-layout review apps have been reviewed interactively;
- visual encodings include legends or direct explanation where needed;
- no-data and contextual anatomy semantics are unambiguous;
- lifecycle and validation blockers are closed;
- the supported API and installation path are documented and tested from a clean environment; and
- the selected hero represents a real user workflow rather than an implementation checkpoint.

The final linked navigator should be treated as the integration test of accepted components, not
as the design surface on which every component is invented simultaneously.
