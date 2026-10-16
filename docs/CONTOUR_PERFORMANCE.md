# Exact contour performance investigation

October 17, 2026. Exact geometry preparation and repeated presentation work were
the main optimization targets. Native polygon processing has useful opportunities,
but neither hidden strokes nor a large native scene struct explains the complete
startup delay or resident memory footprint. No native build, native baseline
upgrade, contour approximation or atlas downsampling was used for this investigation.

## Reproduction and measurement boundaries

The Linux runs used native Datoviz revision
`f77b5d05f914149858d56c374e7cb69ee23a72b3`, with the recorded library SHA-256
`6d8a59ace2bf44d014da92e67cb7457b38767ed8ab5286fc7ee6e3a040ea4d40`.
The configured checkout had moved independently; the ignored
`build/endpoint-depth/run_pinned.py` helper selected the isolated pinned Python
source and checked the unchanged native binary. It inherited the already configured
runtime without rebuilding or approving another environment.

The host was an Intel Core i9-14900K with an NVIDIA GeForce RTX 5090,
driver 595.99.02, Python 3.11.15 and NumPy 2.3.5.
Private Xvfb subprocesses used 1800 × 1300 windows, scale 1.5, the same D070 mesh,
camera and anatomy settings, and explicit local data. Registered inputs were the
exact `allen-ccfv3-10um-bilateral-exact-599b5e0bbab1` projections and local intensity
blocks. The 50 µm comparison used its existing verified volume pack. The empty
native case and mesh-only case isolate runtime and 3D presentation costs; they do
not have the linked workspace's complete GUI/render layout.

Measurements distinguish:

- **Preparation and frame durations:** host wall time around Python/native calls.
  These identify CPU-side work and waiting, not GPU execution time or guaranteed
  interaction latency. Fresh-process first frames and subsequent frames are separate.
- **RSS:** current resident host pages from `/proc/self/smaps_rollup`.
- **PSS:** resident host pages apportioned across processes sharing them.
- **Peak RSS:** process high-water mark; it cannot describe current retained memory.
- **GPU process memory:** a separate NVIDIA driver inventory pass sampled this
  process by PID from `nvidia-smi -q -x`. These MiB values include driver-resident
  allocations and are separate from host RSS/PSS; they are not a per-resource
  Vulkan allocation trace. Host memory alone cannot establish GPU costs.

The sequential matrix uses a fresh process for each case; system and driver caches
may already be warm. One workstation and a small number of runs establish useful
attribution, not portable benchmark thresholds. Native source inspection and binary
debug-type inspection supplement the timings.

Ignored reproduction scripts and receipts are under `build/contour-workspace/`:
`profile_native.py`, `profile_matrix.py`, `native-attribution.json`,
`native-findings.json`, and `native-matrix-*.json`. Run scripts with the pinned
helper under a private X server; for example:

```sh
xvfb-run -a -s '-screen 0 2000x1600x24' .venv/bin/python \
  build/endpoint-depth/run_pinned.py build/contour-workspace/profile_matrix.py contours4
```

## Native timing and memory attribution

This exploratory matrix predates the complete package optimization. The registered
raster/contour comparison holds source resolution and window dimensions constant;
50 µm is a distinct data-resolution comparison, not a replacement for exact inputs.

| Presentation | Warm RSS, MiB | Warm PSS, MiB | Constructor, ms | First frame, ms |
| --- | ---: | ---: | ---: | ---: |
| Empty native window | 253 | 172 | See runtime breakdown below | 54 |
| Same 3D mesh, no linked slices | 550 | 468 | 250 | 256 |
| Linked 50 µm raster | 674 | 592 | 358 | 275 |
| Linked registered raster | 899 | 817 | 1,360 | 349 |
| Linked registered contours, 1× | 894 | 812 | 2,441 | 357 |
| Linked registered contours, 4× | 894 | 812 | 2,422 | 400 |

Warm registered-workspace frames took approximately 25–35 ms. The 1×/4× runs
differed by less than 1 MiB of host RSS/PSS. This supplies no measured host-memory
reason to reduce MSAA. The separate GPU process inventory below measures an
18 MiB difference; host RSS alone did not reveal it.

Three real contour staging calls, including Python descriptors and native setters,
took 25–54 ms each. Native region-add validation accounted for 10–18 ms per axis,
and `dvz_panel_add_composite` realization for 11–20 ms. Their combined staging cost
was approximately 114 ms, much smaller than the full 2.4-second constructor.
GPU uploads and first rendering occur later and must not be charged entirely to
these geometry setters.

An update-heavy attribution run reached approximately 1,205 MiB RSS while live,
860 MiB after viewer close, and 544 MiB after diagnostic `malloc_trim(0)` with
client/source objects still retained. A separate contour matrix case fell from
894 MiB live to 688 MiB closed and 416 MiB after trimming. Allocator-retained pages
therefore account for a substantial portion of post-close RSS. These observations
neither prove a leak nor establish that every remaining page is necessary.
`malloc_trim` is a diagnostic, not proposed application behavior.

### Native scene size is mostly virtual reservation

The pinned binary's debug information reports `sizeof(DvzScene) = 114,112,976`
bytes, or 108.83 MiB. Its fixed figure array accounts for 53.12 MiB and its fixed
legend array for 42.03 MiB. These are structural reservations, not automatically
resident allocations.

After native bindings loaded, RSS was 57.86 MiB. `dvz_scene()` alone took 0.07 ms
and raised it to 58.74 MiB: **0.88 MiB additional RSS**, with most zero pages still
uncommitted. Creating the app/runtime then raised RSS to 218.38 MiB and PSS by
approximately 90 MiB, taking 195 ms. Dynamic native containers could improve
virtual footprint and fixed capacity limits, but this experiment does not support
presenting them as the main resident-memory optimization.

## Native candidates, ranked

References below are source paths at the pinned Datoviz revision.

1. **Reuse successful triangulation and separate geometry dirtiness from color.**
   `src/scene/domain/polygon_storage.c:216` triangulates a proposed polygon to
   validate it and discards the result. `polygon_composite.c:396` triangulates the
   retained rings again during fill preparation. Reuse could remove much of the
   measured 10–18 ms per-axis validation work without weakening transactional
   rejection. Caching full geometries increases retained memory; prefer an explicit
   lifecycle and budget rather than an unbounded triangulation cache.
2. **Update retained fill colors without rebuilding topology.**
   `polygon_set.c:316` marks the fill role dirty after a color change, and fill
   preparation retriangulates and merges all visible polygons. Stable vertex
   ranges could allow color-only uploads while preserving positions and indices.
   Benefits depend on whether the client actually changes colors or geometry;
   repeated unchanged native updates should first be eliminated in the client.
3. **Skip all-zero or transparent stroke preparation.**
   `polygon_composite.c:487` still builds raw path attributes when every stroke has
   zero width; only final visibility is disabled. An early exit would avoid that
   CPU work and a few MiB of retained raw attributes across the contour buffers.
   It is a small optimization: `scene_emit/uploads.c:158` already skips invisible
   visuals before derived path expansion and GPU upload. Hidden strokes do not
   allocate the visible path's expanded GPU geometry in this route.
4. **Reduce intermediate fill copies.**
   `polygon_composite.c:374` holds per-polygon geometries while producing a merged
   geometry; `src/geom/geometry.c:1421` allocates and copies merged arrays, followed
   by mesh float conversion and retained attribute copies. Direct aggregation
   could reduce transient allocations. It needs allocation-failure, holes,
   ordering and scientific identity coverage before adoption.

These candidates justify a later focused Datoviz change if residual profiles make
them material. They do not justify changing the native baseline for this batch.
Append-only scene slots also remain a resource constraint; the client retains two
polygon buffers per axis instead of allocating a fresh scene object per update.

## GPU memory inventory

A separate pass sampled the renderer process by PID after warm frames. Both
baseline and optimized packages used the same published reader and pinned native
binary, with identical geometry. The baseline contour view reported 208 MiB of
GPU process memory; the optimized contour view also reported 208 MiB at 4× MSAA
and 190 MiB at 1×. The equivalent registered raster view reported 254 MiB. Removed
client textures reduced host RSS by roughly 40 MiB in this constructor workload,
without reducing this driver's reported 4× process GPU allocation total.

All cases stopped appearing in the NVIDIA process inventory after viewer close.
That supports release of this process's GPU context; it does not identify every
individual allocation or prove general leak freedom. Keep the accepted 4× quality:
18 MiB alone does not justify a visual downgrade. Receipts are ignored under
`build/contour-performance/gpu-matrix-*.json`; `profile_gpu.py` records host memory
and driver inventory separately. These inventory passes are not latency trials.

## Confirmed native wheel routing defect

An isolated reproducer, run through the hash-verified f77 helper, emits one native
wheel event without GLFW or XTest. A raw pointer subscriber receives it once.
Union subscribers receive it once with no gesture handler, twice with one handler
and three times with two handlers, always with the same timestamp and payload.
The GUI viewport and its backing window install two handlers on the same router.
The duplications therefore originate in native routing, not extra Python
subscriptions or the test injecting three notches.

The resulting application trace steps AP 660→658→656→654 for one injected notch.
The worker begins 658 immediately, spends about 431 ms on it, discards its stale
result, then spends about 458 ms on 654. Only 654 uploads, in 39 ms; hover costs
9 ms total. This explains much of the difference from a direct final-cursor
request. The interactive helper's settle timer starts after its first frame run,
so it is not complete input-to-result latency. The trace accepted the final
payload at 956 ms and ended at 1,062 ms.

The portable reproducer is [`tools/diagnose_wheel_routing.py`](https://github.com/int-brain-lab/ibl-datoviz/blob/feature/datoviz-v04/tools/diagnose_wheel_routing.py).
It needs the configured native environment and creates no GPU context. Run it
with the installed pinned facade/library; for example, from an already configured
Datoviz environment: `uv run --frozen tools/diagnose_wheel_routing.py`.
It reports expected single delivery alongside observed counts.

Additional evidence is ignored under `build/contour-performance/`: `repro_wheel_union.py`,
`wheel-trace.json`, `wheel-trace.log` and `wheel-trace-analysis.txt`. At f77, `src/input/input_router.c:593–594` emits raw union delivery, while
`src/input/pointer.c:370–379` forwards the same wheel through each gesture
handler. `src/window/window_host.c:802` and `src/gui/gui.cpp:3307` install handlers
on the shared router. The native fix should prevent pass-through wheel
re-emission and resolve handler ownership while preserving derived click/drag
events; client timestamp deduplication
would conceal a routing defect and needs separate input semantics validation.
This batch does not change wheel sensitivity or apply a native upgrade.

The same interactive checks log a native `CreateBuffer InvalidState` warning
during pre-wheel mapping setup. Captures and accepted-request checks pass, but
that warning remains unresolved and is a separate engine investigation; it must
not be presented as a clean native render log.

## Shared reader: exactness and CPU improvement

`ibl-anatomy` commit `95ae2426965769d2592f239abb251bc621f1cedb` optimizes exact
numerical contour decoding. Its `contours.py` SHA-256 is
`96d74348597901768e8d0d0ec5544064b07f9eda436191e7128fb41ee320b61a`.
The baseline is `2e190e05b9516df99bbba61284036306681476d9`, reader SHA-256
`eb0608942caff122341c4dcf83109143efc17bd5da61c97bf9dcd82d3dba593d`.

Median decode durations for coronal 660 / sagittal 566 / horizontal 393 changed
from 503 / 367 / 698 ms to 137 / 99 / 196 ms. The complete 3,260-section corpus
comparison preserved identities, component/hole order and every ring byte, with
zero rejections. Summed per-section decode durations changed from 1,172 to
328 seconds, approximately 3.57× faster. Four comparison workers completed in
383 seconds, with peak worker RSS 71.7 MiB. A separate 10,000-case seeded grammar
comparison matched acceptance/rejection and all 842 accepted geometries.

This comparison validates the decoder; separate native triangulation evidence
is recorded below. It does not establish every-section rendering.
Reader timings, tracemalloc allocation peaks and host RSS are distinct measures;
the three-section reader RSS stayed approximately 63 MiB. Shared-reader receipts
are in its ignored `build/contour-performance/` directory. Source assets, topology
and coordinate precision were unchanged.

## Whole-corpus native triangulation

A separate four-process pass used the same immutable f77 binary and optimized
reader across every section. All **3,260 sections, 1,373,858 components and 62,968
holes** passed. It checked finite half-grid native positions, triangle index
bounds and exact summed triangle area against each outer ring minus its holes.
The run generated 112,562,588 native vertices and 109,809,314 triangles, with no
failed sections or components. Each temporary CPU geometry was destroyed before
advancing to the next component.

Wall time was 117.46 seconds; peak worker RSS was 82.31 MiB, and the largest
component contained 2,074 native vertices. Evidence is ignored under
`build/contour-triangulation/{summary,sections,pilot}.json` and `corpus.log`.
This validates native triangulation and exact area. It does not prove pixel
coverage, spatial non-overlap, whole-corpus picking or interactive performance.

## Package geometry reuse

Commit `9514665` retains validated immutable mapped rings, complete borders and
per-region normalized integer intervals. Selection updates XOR the relevant
interval endpoints without revalidating rings or walking every original edge.
Flags use small immutable component records sharing the original owned buffers.
Public constructors continue to validate and detach caller storage.

`SlicePreparation` owns a separate LRU per axis, scoped to its retained immutable
source plus request source ID, mapping, axis and index. Each axis retains at most
four entries and 16 MiB of accounted storage. Accounting includes ring arrays,
SVG borders, region intervals, normalized borders and fixed Python metadata
allowances. Selection variants are not retained in another cache. Outstanding
accepted/worker payloads may keep evicted immutable storage alive independently;
the limit describes cache retention, not total process memory. Viewer shutdown
joins workers before dropping its preparation caches. A native weak-reference
check confirms immediate release while an externally retained source remains
usable. Source caches belong to the source and are not cleared by viewer close.

The three-section clean-reader receipt measured selection geometry alone at
4.38 / 5.85 / 5.76 ms, 16 ms combined. Full preparation still included image work:
144 ms combined for parent selection and 72 ms for returning to three cached
sections. These isolated figures describe that run, not an end-to-end speedup
claim. Both ring and normalized-border identity reuse were checked. Cache
eviction, source/mapping/axis separation, immutable ownership, holes, signed
parents, partial overlaps and random categorical-boundary oracles passed; the
focused pinned-native suite passed 56 tests.

Receipts are `build/contour-workspace/geometry-cache-profile.json` and
`geometry-cache-environment.json`; the latter records the clean reader commit
and identical source hashes before and after measurement.

## Exact vectorized cold preparation

Commit `b09fc82` replaces per-edge Python dictionaries with bounded int64 edge
arrays and lexicographically sorted endpoint events. Per-region and selected
unions use XOR parity; the complete border uses positive coverage. The existing
half-grid coordinate bounds, segment ordering and public owned-ring validation
remain unchanged.

Five alternating paired samples over the actual three orientations gave summed
preparation medians of 478→169 ms for Allen, 269→87 ms for Beryl and 248→107 ms for
Cosmos. All 3,039 geometry comparisons against `739e495` matched ring and hole
bytes, mapped/source IDs, selection flags and every boundary row. The independent
audit matched a further 24,000 interval sweeps and 700 geometry/hole cases,
including ±2**52 doubled-coordinate bounds. The focused pinned suite passed 61
tests. Evidence is `build/contour-workspace/geometry-vectorized-comparison.json`.

## Cooperative cancellation of obsolete preparation

Commit `adafdd0` adds an optional cancellation-aware preparation callback to the
existing slice scheduler. Existing one-argument callbacks remain supported. The
worker checks a scheduler-owned predicate before and after its axis lock, after
numerical decoding, after mapped geometry and after raster composition. A newer
request stops later expensive stages; the executor discards its obsolete outcome.
No partial payload is published and completed immutable source cache entries
remain usable. Workers retain an independent preparer, not native viewer handles.

Shutdown marks requests obsolete before joining, releases locks before waiting,
and then releases preparation/notification callbacks. Tests cover cancellation
at phase boundaries, genuine current failures, concurrent shutdown and immediate
owner/cache release without garbage collection. The independent high audit found
no P1/P2 in this implementation.

One instrumented post-change wheel run preserved 660→654, the final burst index
558, exact hover and six retained polygon buffers. Stale AP658 stopped after
179 ms of source work, skipping geometry/raster preparation; previously it ran
431 ms. Final AP654 preparation remained about 456 ms. The final payload was
accepted at 683 ms instead of 956 ms. Input-to-end trace time was 821 instead of
1,062 ms; reported settle was 678 instead of 910 ms. These are paired diagnostic
runs, not three-process medians, and the native duplicate wheel delivery remains.

Evidence is `build/contour-performance/wheel-trace-cancelled.{json,log}` and
`wheel-trace-cancelled.analysis.txt`. A fresh direct-API sanity run after this
change measured cold AP 569 ms, cached return 86 ms, selection 164 ms and mappings
354/372 ms, consistent with the geometry batch below.

## Controlled end-to-end comparison

The baseline package was extracted from the wheel built before this batch;
its reader was the published `2e190e0`. The optimized package includes bounded
geometry reuse, native buffer reuse, removal of unused panel textures, exact
vectorized interval preparation and reader `95ae242`. All runs use the same
Python, NumPy, native binary, window, inputs and cursor sequence. Each receipt
records imported module paths, reader hash and all package Python file hashes;
package files are checked for changes through the run.

Three fresh processes per version, before the separate cancellation change,
produced these median owner-side durations. The later cancellation sanity run and
input trace are recorded above.
A section/selection/mapping operation includes draining asynchronous preparation
until all accepted sections match the request revision, plus frames used by that
polling loop. It is not an isolated function microbenchmark.

| Operation | Baseline, ms | Optimized, ms | Observed optimized range, ms |
| --- | ---: | ---: | ---: |
| Construct workspace, before view/first frames | 3,759 | 1,890 | 1,886–1,896 |
| Cold AP 660→654 | 1,209 | 606 | 603–651 |
| Return to cached AP 660 | 263 | 87 | 87–88 |
| Select signed parent −8 | 1,038 | 169 | 167–174 |
| Change Allen→Beryl | 537 | 358 | 353–358 |
| Change Beryl→Cosmos | 600 | 372 | 372–423 |
| Zoom accepted AP geometry | 280 | 83 | See receipts |

The warm 30-frame batch fell from a median 981 to 565 ms; this is a bounded
explicit rendering loop, not a guarantee of mouse responsiveness. Median idle
host RSS fell from 1,124 to 1,061 MiB, while peak RSS fell from 1,350 to 1,249 MiB.
Baseline idle RSS varied from 1,076–1,126 MiB and peak RSS from 1,310–1,384 MiB;
allocator behavior makes these memory gains less stable than the latency gains.
After closing, dropping the viewer, clearing source caches and diagnostic trim,
with input/source objects still retained, RSS was similar: 335 versus 334 MiB. No general leak claim follows from this.

The retained baseline trials are `controlled-baseline`, `controlled-baseline-3`
and `controlled-baseline-4`; optimized trials are `controlled-final-4` through
`controlled-final-6`. `controlled-summary.json` records medians/ranges. An earlier
baseline trial overlapped a separate GPU inventory and is excluded from these
aggregates. All files are ignored under `build/contour-performance/`.

A separate factorial check isolates contributions. Reader optimization alone
reduced a cold AP change to 750 ms; the optimized package with the old reader
took 1,139 ms; both together took roughly 606 ms. Mapping and selection gains
come mainly from package changes, while decoder work remains important for cold
sections. Those isolation variants are individual runs, not three-run medians.

Baseline and optimized selected-parent and Beryl screenshots matched every pixel
at 1800×1300. The live XTest check additionally verifies exact native hover,
Allen/Beryl/Cosmos parent selection, actual wheel input, a 16-event burst with
latest-request acceptance, and six fixed polygon buffers. Its active-hover,
different-cursor workflow is separate from the controlled API timings. Receipts
are `interaction-final.log` and `receipt.json`; manual review is still deferred.


## Remaining optimization opportunities

The next candidates need their own measured change and contract tests:

- **Separate contour-panel preparation from physical-plane raster preparation.**
  Cold annotation rasterization still costs roughly 180 ms for the sampled AP
  section. Its exact validity mask also controls anatomical-image alpha, so
  simply dropping it would change void/hole/tissue rendering. A cheaper exact
  validity-mask path plus deferred annotation RGBA for optional physical 3D
  planes could help, but must preserve mask pixels, accepted-section identity,
  asynchronous ownership and physical-plane behavior.
- **Avoid unchanged image work on mapping/selection updates.** Grayscale anatomy
  is unchanged for a fixed source and section. A bounded immutable image cache,
  or explicit per-layer preparation dependencies, could avoid recoloring and
  uploading it repeatedly. Budget the retained images against actual savings.
- **Cache verified compressed source blocks.** Registered block loading and
  validation take tens of milliseconds in the cold section path. Any shared
  block cache must preserve file-integrity/freshness behavior and a byte budget.
- **Consider reproducible numerical derivatives.** A digest-addressed local
  numerical cache could avoid reparsing registered paths. This needs a shared
  reader/cache format and provenance policy, rather than another visualization
  codec or a second authoritative atlas dataset.

The implemented changes retain exact source geometry, existing default raster
behavior, the accepted 4× appearance, and the supported native binary. Manual
Linux interaction review and macOS evidence remain separate release gates.

## Final validation and release gates

The complete package suite passes on Python 3.11 and 3.13: **1,087 passed, one
optional registered-asset-root skip per run**. Both use the supported f77 facade
and hash-verified native binary. Source and wheel builds pass. Fresh installed-wheel
CPU checks pass on both versions; the latter import public CPU APIs without
loading native bindings. Ruff, strict MkDocs and whitespace checks pass.

The configured external source checkout remains at `54c9ce1`, while the supported
native baseline is f77. `just doctor --strict` correctly rejects that known drift.
The pinned helper supplies validation without changing the external checkout,
native library, configuration or supported pin. A later review setup must resolve
that pairing explicitly; manual Linux review, macOS evidence, the confirmed native
wheel-routing defect and the logged native buffer warning remain separate gates.
