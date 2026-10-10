# Audit follow up and implementation handoff

The October 5, 2026 implementation queue has landed: the three reproduced correctness fixes,
documentation/dependency alignment, and R1–R5 extractions are complete. The specifications and
original reproductions below are retained as regression acceptance criteria, not unresolved defects.
Remaining work is live interaction review, complete registered-section coverage, and verification
of eventual distributable RC3/anatomy artifacts. The October 5 package changes targeted the frozen pre-RC3 Datoviz baseline;
no engine source changes were made. The current source pairing is recorded below.

## Published interaction fixes — October 10, 2026

The current immutable Datoviz pin is `62101912dfde633b4510dfbdbccf7d4a7f0b8ba2`, published on upstream main. It includes the gesture suppression and automated window identity fixes described below, plus stationary GUI move suppression and full-name tree tooltips. Anatomy remains at `119457b68fae6967c54d549d9d44e4a4e49c74f8`. Ordinary local review accepts newer configured checkouts with a warning; only an intentional tested-baseline upgrade changes the pin. A documentation-only commit does not require a new pin.

The embedded viewport now forwards MOVE only when the pointer, viewport size, modifiers, or scene revision changes. Leaving or hiding the viewport invalidates the remembered input. It records the revision after forwarding so its own query request cannot perpetuate picking. Native hover application avoids rebuilding item state for an identical result or clearing an already empty hover. Geometry and camera updates still refresh a stationary highlight; active gestures continue suppressing hover without altering committed selection.

A matched Debug comparison uses the previous library (`7773638736c029c0b496bd5afd3fd37bb17bba53f30c0422ce950b4f8bc58337`) and the current build on Linux, Intel RPL-S/Mesa 25.2.8, D070, 900×720. An ImGui NewFramePre hook injects a constant mouse position into the actual GUI forwarding path, without moving the desktop cursor. Each library runs three fresh viewers with 30 warmup and 120 measured frames. The source viewport executes **120 queries per repeat before and zero after**; the highlight stays visible. Geometry and camera refresh assertions pass after each measurement. Median frame interval changes from 15.36 to 9.71 ms, with substantial desktop scheduling variance, so query counts are the stronger evidence. Reports and the repeatable local harness are in ignored `build/stationary-hover.{json,log}` and `build/check-stationary-hover.py`.

The benchmark now reports GPU query backend/download/decode phases, Python surface emphasis updates, native color setter costs and call counts, and the exact loaded library path/SHA256. Setter and emphasis distributions describe actual calls, while native query phase timings are per measured frame; these denominators must not be added together. Benchmark subprocesses remain marked as automated and use the app's uncapped default instead of an invalid zero FPS environment override.

Moving-pointer profiling uses the same D070 asset, Debug library SHA256 `aeb806ed6852a698a6db03a4b4f3113a3ff259dc60013a5fbfa83f6055751568`, three fresh-process repeats, 30 warmup and 120 measured frames. At 900×720, moving hover executes 120 source-view queries and 35 color setter calls per repeat. Query time is 6.15 ms/frame, including 5.89 ms/frame backend, 0.0057 ms/frame download and 0.0017 ms/frame decode. Surface emphasis is 6.54 ms per call; the color setter is only 0.18 ms per call. The isolated emphasis scenario is 1.92 ms per call with a 0.15 ms setter, so the catalog-backed GUI path and NumPy mask/recolor work need investigation alongside GPU query execution. Drag still executes zero queries and has no hover-hit frames. The 1800×1440 repeat is recorded separately; timings depend on resolution and desktop scheduling and are not portable thresholds. Reports/logs are `build/interaction-performance-stationary{,-large}.{json,log}`.

The sidebar default grows from 340 to 400 logical pixels and scales with the existing UI scale. Native tree row tooltips show the complete acronym and wrapped full name, preserving readable labels on narrow trees. The UI still needs the user's live design acceptance; startup and screenshot checks do not establish subjective interaction quality.

Validation against the published source: **264 package tests, zero skips**, with native offscreen rendering and both real asset roots; **61 native scene-interaction tests and 20 GUI-filter tests, zero skips**; all six real-data examples pass three-frame desktop startup at 1.5× scale. Ruff, strict MkDocs, locked installation, and whitespace checks pass. The native build has no compiler warnings. Logs remain in ignored `build/final-{tests,review,docs}.log` and the native build/test logs. macOS rendering and distributable-artifact verification remain separate release gates.

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
