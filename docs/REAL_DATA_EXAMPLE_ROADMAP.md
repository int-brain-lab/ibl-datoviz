# Real-data interactive example roadmap

Status: two fixed-layout review apps on the `0.2.0.dev0` Datoviz v0.4 branch;
earlier focused-example planning and evidence are retained below.

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
