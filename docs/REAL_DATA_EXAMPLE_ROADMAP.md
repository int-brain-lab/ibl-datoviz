# Real-data interactive example roadmap

Status: implementation plan for the `0.2.0.dev0` Datoviz v0.4 branch.

## Product decision

`ibl-datoviz` has validated a substantial native rendering stack, but it is not yet mature enough
to present a showcase image as a product-level hero. Keep the README and documentation landing
page text-first until the interaction model, visual encodings, public API, and packaging contract
have been reviewed through live examples.

Examples are the next product-discovery tool. Build small interactive programs over real, pinned
IBL data, with each example demonstrating one capability. They should let a reviewer isolate one
interaction or visual encoding and give direct actionable feedback. Do not use a visually dense
integration example to stand in for evidence about its individual parts.

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

This is still a development branch rather than a stable library. The release blockers in
[Release-hardening handoff](RELEASE_HARDENING_HANDOFF.md) remain authoritative: lifecycle safety,
navigator factory behavior, input validation, dependency/CI alignment, and public API definition.
WebGPU currently proves only a small fixture-based portability path; it does not provide parity for
the Python viewer, GUI, picking, WBOIT, or volume rendering.

## Work order

Progress: viewer lifecycle failure safety is implemented. Input validation is the next hardening
task before starting the first example batch.

1. Fix lifecycle failure safety and input validation before expanding interactive usage.
2. Build and review the first batch of focused real-data examples.
3. Iterate on controls, feedback, visual encodings, and scientific descriptions.
4. Add the linked and higher-resolution examples once their component interactions are accepted.
5. Freeze the supported public Python API from the workflows that proved useful.
6. Align package metadata, clean-environment CI, documentation, and release notes.
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

## Feedback loop

For each example, ask the reviewer to evaluate only:

1. whether the stated capability is scientifically and visually understandable;
2. whether the primary interaction behaves as expected;
3. whether missing, selected, hovered, and contextual data are distinguishable;
4. whether the default camera, scale, contrast, and control placement are useful; and
5. what concrete behavior should change before the example is composed into a larger workflow.

Keep screenshots subordinate to the live review. A gallery image is a regression artifact and a
discovery aid, not evidence that an interaction is mature.

## Promotion gates

Do not restore a hero image until all of the following are true:

- at least the first example batch has been reviewed interactively;
- visual encodings include legends or direct explanation where needed;
- no-data and contextual anatomy semantics are unambiguous;
- lifecycle and validation blockers are closed;
- the supported API and installation path are documented and tested from a clean environment; and
- the selected hero represents a real user workflow rather than an implementation checkpoint.

The final linked navigator should be treated as the integration test of accepted components, not
as the design surface on which every component is invented simultaneously.
