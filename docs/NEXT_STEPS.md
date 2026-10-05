# Audit follow up and implementation handoff

The October 5, 2026 implementation queue has landed: the three reproduced correctness fixes,
documentation/dependency alignment, and R1–R5 extractions are complete. The specifications and
original reproductions below are retained as regression acceptance criteria, not unresolved defects.
Remaining work is live interaction review, complete registered-section coverage, and verification
of eventual distributable RC3/anatomy artifacts. All package changes target frozen Datoviz main;
no engine source changes were made.

## Baseline and completed work

The original audited package revision was `e8bf9f5` on `main`, version `0.2.0.dev0`. Focused follow-up commits are recorded below; the January v0.1 checkout and its removed object API are obsolete. The Datoviz baseline is `066a7451195b38c5e95dcf7af7383b89ec5ec903`, and this package now pins that same revision. The anatomy revision is `119457b68fae6967c54d549d9d44e4a4e49c74f8`.

Already implemented: verified D070 assets, Allen/Beryl/Cosmos presentation, linked ontology and probe/regional tables, orthogonal slices, bounded native volume rendering, registered 10 um slices, latest-wins preparation, lifecycle failure safety, navigator factory restrictions, probe validation, ten supported top-level exports, and locked source-snapshot CI on Python 3.10 and 3.13. Do not reimplement the original five hardening items; [the earlier handoff](RELEASE_HARDENING_HANDOFF.md) records their history.

The original audit passed a normal locked development install, Ruff, strict MkDocs, wheel/sdist builds, and 125 tests against the Datoviz baseline above. Two tests skipped because the real D070 and registered 10 um roots were unavailable. All three synthetic native offscreen tests passed after activating the Datoviz Vulkan environment. The synthetic gallery render and three-frame GUI startup/cleanup checks for both viewer classes passed too. These checks do not establish full real-data interaction quality, cross-platform rendering, or current D070 performance; historical benchmarks retain their original commit and host scope.

## Implementation progress

- Dependency/onboarding alignment landed in `c381fc2`: locked clean install, strict MkDocs, source pairing, materialization recipes, and historical browser labels validated. Complete real-data materialization still needs asset/GPU review.
- R5 complete: input adapter owns subscription/callback lifetime; pure wheel, keyboard, zoom, and resize/content-scale decisions preserve interactions. 63 focused input/slice/navigator tests and both three-frame native GUI runs pass. Manual HiDPI/docking review remains outstanding.
- R4 complete: immutable requests feed renderer-independent per-axis preparation; named prepared buffers are copied and read-only. Sync and async refresh share preparation/upload. 49 focused tests and two linked native offscreen smokes pass; stale cursor/mapping/selection results and joined shutdown covered.
- R3 complete: explicit pure selection decisions preserve region-table/probe-table/tree/mesh precedence and propagation; ID/key helpers retain signed hemispheres and stable site keys. 112 selection/GUI/viewer/navigator tests pass. Hover remains independent.
- R2 complete: GUI helpers own typed retained rows and native handles, clean partial failures, and destroy each handle once. Viewer retains authoritative selection, callbacks, and borrowed control buffers. 105 focused tests pass, including 16 GUI ownership/failure regressions. Live sorting/filtering review remains outstanding.
- R1 complete: pure scalar interpolation and weighted mapping reduction live in `presentation.py`; viewer retains named tuple-compatible adapters and label formatting. 112 focused tests pass, including 23 direct presentation regressions.

- Payload ownership fixed in `91db67e`: all retained numeric buffers are independent C-order copies; 22 focused tests pass.
- Native failure recovery added in `eaad3ed`: one owned upload snapshot restores both geometry and identity after setter failure; failed restoration closes the viewer explicitly. Null construction and failed setup/attachment retry safely with at most one pending scene-owned candidate. 126 targeted tests pass, including 13 added recovery/retry cases.
- Probe replacement fixed in `7cf5988`: successful raw replacement clears typed payload, colors, per-site link keys, and linked table; typed uploads commit identity after validation. Path constructor, caps, and joins now report native failures. 67 atlas/replacement tests and four native offscreen smokes pass, including typed/raw/mapping/typed transitions.
- Native checks use Datoviz source main `066a745` and the local built library with its Vulkan SDK environment. Real assets and live interaction review remain separate evidence.

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

Run from the repository root:

```bash
uv sync --group dev --locked
uv run --frozen ruff check .
uv run --frozen pytest -q
uv run --frozen --with-requirements docs/requirements.txt mkdocs build --strict
git diff --check
```

Tests use synthetic fixtures from the pinned adjacent anatomy checkout; CI shows the exact setup. For the local source baseline, add the adjacent Datoviz checkout to `PYTHONPATH`, select its matching built library, and activate its platform Vulkan environment. On macOS, use `direnv exec ../../Viz/datoviz` around the validation command. Confirm imported module paths and revisions so installed distribution metadata cannot conceal a different source checkout. Report native/GPU and real-asset skips explicitly.

Use `uv run --frozen python tools/build_gallery.py --example atlas-spike --fixture-root <anatomy-fixtures> --output-root build/audit-gallery` for a synthetic gallery check, run `tests/test_smoke.py` with the configured native environment, and check three-frame startup/cleanup of both GUI classes. The two real-asset tests require `IBL_ATLAS_ASSET_SET_ROOT` and `IBL_REGISTERED_ASSET_SET_ROOT`. Benchmark and gallery tools write to the ignored build tree; review pixels before replacing tracked canonical images.

The follow-up is complete when the reproduced failures are covered and fixed, onboarding runs cleanly, dependency evidence matches the pre-RC3/RC3 baseline actually tested, the staged refactors preserve public behavior and native ownership, and outstanding live review or unavailable platform/asset evidence is explicitly recorded. Update this checklist and the roadmap as work lands.
