# Audit follow up and implementation handoff

## Active branch

Continue all Datoviz v0.4 work on `feature/datoviz-v04`, keeping `main` unchanged
until an explicit merge request from the user. The former envelope,
video-component, viewer-restoration and v0.4-spike branches have been consolidated;
all their commits are preserved in `feature/datoviz-v04` or its `main` ancestry.
Branch names in the dated entries below identify historical implementation batches.
See `AGENTS.md` for the working-branch policy.

## Terminal scientific replay checkpoints — October 20 2026

Recording completion now binds a settled scientific source capture into the trace fixture without extending the input clock. Replay compares full camera navigation, scientific slice/selection/layer state and exact RGBA8 pixels; scheduling revisions and native submission serials remain run-local evidence. PNGs and diagnostic reports are written under the caller's artifact paths. A required checkpoint failure remains an unsuccessful replay; matching terminal results still do not constitute an equal-work or performance verdict. See [current commands and limits](INTERACTION_REPLAY_BENCHMARK.md#current-commands-and-limits).

Native `abf2d8c17` fixes clean CI by generating the local ctypes artifact before checking freshness. `eab619f94` adds the borrowed viewport source getter and successful view-submission serial, with focused synchronization-validation coverage including source capture after actual host close. Generated bindings remain local artifacts; the configured baseline and dependency pin remain unchanged.

A private-display XTest recording first exposed a real fidelity bug: the recorded button callback position was 3×2 pixels ahead of the source-router press accepted by the live GUI. Source-router observers showed identical final drag endpoints but different press positions, explaining a roughly 0.57-degree terminal rotation mismatch. This was not caused by intermediate move coalescing. Native `536d78c7d` fixes button and wheel ingress to use the last ordered cursor observation; initial cursor snapshots remain unchanged. Its installed-GLFW-callback regression reproduces the defect before the fix and passes afterward.

After that correction, a fresh 33-event real-mouse recording and two controlled plus one paced replay all finish with exactly matching scientific state and RGBA8 pixels, with successful exits and every event delivered. Before/after traces, source-pointer observations, reports and inspected source PNGs remain ignored under `build/input-checkpoint-*` and `build/input-pointer-diagnostic/`. Terminal reproduction is established for this bounded Linux gesture; intermediate-work equivalence, a representative user recording, throughput gains and physical-platform acceptance remain separate gates.

A second private-display mixed recording exercises 3D rotation, AP slice wheel steps, left-click cursor positioning and right-click region selection, then closes shortly after the final click. Both paced and controlled runs deliver all 36 observations and match terminal scientific state and RGBA8 pixels exactly. The cursor changes from `[132, 114, 80]` to `[136, 24, 62]`, selection changes from empty to signed region `-1035`, and slice revisions advance on all three axes. Final upload readiness and designated source captures are ready; artifacts are ignored under `build/input-checkpoint-mixed/`.

Final readiness also includes pending region-browser auto-slice lookup work before any resulting slice revisions exist. The helper exposes owner-thread pending/error state; cancellation and stale completion cannot falsely keep a checkpoint pending or ready. Fixtures capture/reset the auto-slice policy, and lookup failures invalidate terminal proof. Focused tests cover navigation→slice-upload sequencing, timeout/cancellation, retained worker errors, stale completion and policy reset.

Native `337da6a0a` also repairs an existing CI regression test's stale idle baseline. A deliberately injected focus-loss event reproduces the failure; fresh counters at the established idle boundary now prove that worker wake and a request for one viewport leave the other idle. The fix preserves the initial no-render assertions and passes repeated llvmpipe/NVIDIA synchronization validation.

Validation passes all 1,326 native tests with zero failures/skips under private-display Vulkan synchronization validation, all 1,177 candidate-paired IBL tests with one existing optional skip, and 64 focused fixture/capture/navigation/wiring tests. Ruff, strict MkDocs and whitespace checks pass. The unchanged pinned-baseline suite also passes 1,176 tests with two existing optional skips. Hosted CI remains a separate check.

## Continuous rendering review options — October 20 2026

`just review 2 --benchmark` requests continuous frames and immediate presentation with no inherited FPS cap. Optional `--fps-overlay` enables the native overlay independently. Overrides are applied after the checkout's platform environment; both options require a host window and work with numbered apps, `all` and named examples. No baseline pin, build type or validation policy changes. See [usage and measurement limits](review-apps.md#continuous-rendering-for-benchmarking).

Validation: 68 focused review/recording-wiring tests pass, including real subprocess checks of platform-environment precedence. Strict configured-baseline app-2 startup passes five frames on a private Xvfb display with both flags at UI scale 1.5. Ruff, strict MkDocs and just recipe parsing/discovery/argument forwarding pass. This bounded launch does not establish interactive quality or a throughput result.

## Native RC4 branch consolidation — October 20 2026

Native ongoing development is now consolidated on `rc4/integration`, renamed from `perf/panel-render-reuse`. Native `main` remains reserved for RC3 finalization. Redundant native implementation branches were backed up and retired locally; their checkout folders remain as detached snapshots. The configured scientific checkout remains at the exact pinned revision `73d0f0bcdd595d2f76e2cdffcc2dd89c25a56858`, now detached; neither this repository's branch policy nor its dependency pin changes. Both repositories have verified recovery bundles and saved branch refs under their common Git directories. No remote branches were changed.

Consolidation validation passes: native 1,324/1,324 tests with Vulkan synchronization validation and no validation diagnostics; candidate-paired IBL 1,145 tests with one existing optional-asset skip. Strict baseline doctor, Ruff and strict MkDocs also pass. These are Linux development checks; the baseline pin remains unchanged.

## Initial opt-in interaction recording and replay — October 20 2026

Commit `e223d51` adds the review-2 fixture/readiness adapter, optional owner-thread loop runner and record/replay CLI. Native commit `227eaff0b` adds original host ingress and replay-safe GUI input; `571da9416` fixes policy-driven callback retention and unsubscription. The companion player, bounded trace storage and strict Actions interchange provide paced/controlled playback. See [the commands and current limits](INTERACTION_REPLAY_BENCHMARK.md#current-commands-and-limits). This work remains on the existing development branches, with no baseline or dependency-pin change.

The configured-baseline suite passes 1,144 tests with two existing optional skips; the candidate-paired suite passes 1,145 with one optional skip. Ruff and strict MkDocs pass. Native validation includes 97 pure codec/player tests, binding freshness/ABI checks, 175 app-related checks with synchronization validation, focused input/window/controller checks, GUI replay isolation and four clean Valgrind ingress regressions. A high-effort Sol 6.1 audit reviewed the architecture and fidelity fixes.

Private-display Linux checks record 33 actual GLFW mouse observations via XTest and deliver all 33 in paced and controlled modes. Both modes rotate the camera; repeated controlled runs finish with exactly equal scientific state and current slice readiness. Fixture preflight now waits for eight rendered warmup frames, captures resolved sidebar/panel geometry, hashes verified source identities, and fails on retained GUI errors. Native capture preserves idle duration and platform identity. Reports preserve final scientific state and accepted slice identities; rendered display proof and the full scientific benchmark verdict remain explicitly unavailable. No comparable performance gain is claimed until both builds use the same recorded workload and policy.

Implementation remains local on Datoviz `rc4/integration` and IBL `feature/datoviz-v04`. Generic capture/player capability does not promote the baseline or establish macOS acceptance. The next interactive review can record one manual app-2 session; replay it for matched CPU/GPU profiling, then add explicit scientific checkpoints and rendered proof before accepting equal-work throughput results.

## Interaction replay benchmark proposal — October 20 2026

Added the proposed IBL fixture, reset, asynchronous readiness, checkpoint, result and scenario-catalog contract in [Interaction replay benchmark](INTERACTION_REPLAY_BENCHMARK.md). The shared W3C-aligned observation format and player contract remain in the companion local Datoviz proposal; WebDriver Actions is separate interchange. This is a spec-only draft, not an implemented benchmark or release gate, and the detailed shared semantics require review before implementation.

## Interaction CPU profiling and focused optimizations — October 20 2026

The canonical atlas display transform is prepared once per mesh from the complete source coordinates. Source and display coordinates retain immutable owned byte storage; replacing geometry prepares a new center, while private render compaction cannot change the canonical normalization. Cursor and crosshair updates acknowledge only successful native writes and skip unchanged geometry. Selection-sensitive slice payloads still receive new revisions; failed partial writes force geometry restoration on rollback.

Surface visibility now resolves authored color, alpha, hemisphere, mapping and selection at presentation cardinality, then expands the final boolean mask to faces. This removes full vertex RGBA expansion and alpha reduction from selection without a cross-frame cache or new invalidation machinery. Palette fallbacks are generated only when the palette lacks the requested signed or absolute region identity. A high-effort Sol 6.1 audit reviewed the representation, coordinate ownership and applied-state rollback without finding blockers.

In matched private-display real-data replays with validation disabled, median slice-scroll action processing fell from 14.58 to 2.42 ms and region-selection processing from 45.77 to 19.49 ms. These measure controller actions rather than desktop FPS or input-to-photon latency. Scientific-view captures are pixel-identical before/after for initial state, selected region, moved slice and cleared selection. The full configured-baseline suite passes 1,112 tests with two existing optional skips; the paired native candidate passes 1,113 with one existing optional skip. Focused palette tests and the rendered equivalence check also pass after the final fallback-only change. Ruff and strict documentation checks pass.

Native work remains on `perf/panel-render-reuse`. Commit `056a5c38e` indexes command-stream labels while preserving label order, replacement and allocation-failure fallback. It passes 178 DRP2/related scene checks with synchronization validation and focused Valgrind checks. Label insertion scales substantially better in synthetic large-table measurements, but four alternating scientific-view replay processes do not establish a robust whole-frame gain. A separate real-data rotation with synchronization and submit-time validation reports no errors. The broader runtime ID indexes and semantic-state reuse are deferred: a synthetic clone probe copies 1.79 MB in approximately 67 microseconds at 1,024 objects, but the application's live object count and attributable copy cost remain unmeasured. Transactional semantic validation remains enabled.

Release builds and Vulkan validation disabled are performance-review conditions; correctness checks continue with validation enabled. Native baseline configuration and the immutable package pin remain unchanged. Commits are local; publication, remote CI and the new desktop interaction capture remain separate evidence. Raw CPU/GPU traces, replay profiles and comparison receipts are retained in ignored `build/live-profile-20261020/` and `build/review2-performance/` outputs.

## Native panel profiling follow-up — October 19 2026

Local Datoviz work is on `perf/panel-render-reuse`, based on published scientific candidate `5690da0b2`, with commits `f2603c9d9` (reuse contract), `604816ce3` (opt-in panel diagnostics), `0860b3370` (duplicate composition validation removal), and `8bd71b5ba` (validation-correct test fixtures). Two high-effort Sol 6.1 audits and cheaper source explorations informed the design and safety review. The configured checkout and immutable pin remain unchanged; native publication, remote CI and application baseline promotion remain separate steps.

An exact-input composition-cache prototype passed four CPU regressions but did not establish a representative gain: eight alternating fresh processes, three 240-frame trials each, measured median source-frame time 3.61 ms disabled versus 3.70 ms enabled. It was removed from the native working tree and preserved as an ignored experiment. Composition resolution was only approximately 57 microseconds of approximately 383 microseconds of panel planning in a separate diagnostic run. Removing a duplicate adjacent contract validation reduces a synthetic resolver microbenchmark from 8.94 to 7.84 microseconds; this is a phase-only improvement, not a whole-frame speedup claim.

An isolated prototype routing the three slices through existing intermediate presentation found a fractional panel-grid mismatch: 87,842 changed pixels, maximum channel difference 194. A partial coordinate fix reduces this to 175 pixels with maximum difference 2, but the independent audit found wider sampled-pass and absolute-fragment-coordinate requirements. It remains an ignored prototype. GPU panel-image caching is not implemented or enabled. The native proposal defines the required allocation/viewport mapping, isolation, typed products, submission acknowledgement, frame-slot ownership and conservative fallback before that work can land.

The final Linux native suite passes 1,315 tests with no skips and no reported errors under active Vulkan synchronization and submit-time validation. Initial full-suite validation exposed two pre-existing test-fixture mistakes; both were repaired without changing production synchronization. The paired candidate IBL suite passes 1,106 tests with two existing optional skips, as does the configured baseline suite. A separate 24-frame real-data rotation with active synchronization validation reports no errors. Private-display profiling and validation do not establish physical desktop latency, macOS interaction acceptance or multiple-GPU coverage. Reports, raw profiles and experiment patches remain ignored under `build/review2-headless/`, including `FOLLOWUP.md`.

## Zero-opacity linked volume visibility — October 19 2026

The linked navigator now hides its retained volume draw at zero opacity and restores visibility at positive opacity, including initialization and transactional rollback after a partially failing setter. Data and visual handles remain retained. The zero-opacity D070/full 50 um capture is pixel-identical to the previous visible-but-transparent volume capture. A private-display 240-frame replay records a 1.67 ms median source GPU render span, compared with 1.82–1.84 ms in the prior full sweep; these separate runs establish removed volume work, not a matched end-to-end speedup or desktop latency improvement. Raw profiles and captures remain ignored under `build/review2-headless/`.

Focused controller/native rendering tests pass (24 tests), and the full configured-baseline suite passes (1,106 tests, two existing skips: the optional image-plane-pan API absent from the baseline and optional registered-asset coverage). Ruff and formatting checks pass. The configured native baseline and immutable pin remain unchanged. Native panel planning/render reuse is being investigated separately; it is not enabled by this change.

## Opt-in native nonblocking viewport candidate — October 18 2026

Datoviz scientific candidate `2644ca68e` implements `DVZ_GUI_VIEWPORT_FLAGS_NONBLOCKING`; strict same-frame presentation remains the default. Three lazy canvas-owned targets retain a completed image while newer source work runs. Source and host timeline ownership, display pins, resize generations and immutable per-slot descriptors protect reuse and retirement. Scheduling now follows source/input demand and pending completions; visible idle viewports stop redrawing. Borrowed GPU uploads, completed-command resource retirement, stable logical slot scopes, post-submit queries, and failed-submit re-emission preserve correctness under overlap. A high-effort Sol 6.1 audit signed off after a negative-control rendered-pixel regression confirmed the failed-submit retry fix.

The final candidate passes all 1,314 native tests with synchronization and submit-time validation enabled, with no skips, plus specification/source guards, binding freshness/ABI checks, presentation, Quickstart, shaderc and strict documentation checks. The native Python/tooling lane passes 494 tests with one skip. Against the explicitly paired candidate facade and library, the complete IBL suite passes 1,105 tests with one optional registered-asset test skipped. A final real-data 120-frame nonblocking rotation explicitly enables the validation layer and synchronization/submit-time checking and finishes without reported validation errors. This is Linux exercised-path evidence; manual macOS acceptance and native exact-head remote CI remain separate gates.

Matched review-2 desktop measurements keep D070/full 50 um slices, six context surfaces, host 2240×1600, source 1534×1385 and UI scale 1.5. Fresh-process strict/nonblocking/nonblocking/strict order with three 240-frame trials per process gives six samples per mode on the same Debug library and CPython 3.11. Validation is disabled only for performance runs. Median host time decreases from 4.583 to 1.557 ms (66.0% lower), while completed source throughput increases from 218 to 321 images/s; nonblocking promotion throughput is approximately 317 images/s. Approximately 120–121 new source images serve 240 host iterations. These are measured application/source rates, not monitor refresh or input-to-photon latency.

Separate memory trials remain stable at 232 MiB GPU process memory in strict mode and 300 MiB nonblocking; RSS stays approximately 710–711 MiB. Vulkan/NVTX traces show 480 strict timeline waits totaling 527.889 ms over 240 host iterations, versus none in nonblocking mode. There is no queue-idle call in either rotation range and only one final device-idle drain per app run. The first overlapping run lazily initializes another slot; the second has no Vulkan resource creation, allocation or destruction calls. GPU and CPU work overlap and must not be added as independent costs.

Receipts stay ignored under `build/review2-rotation/`; measured native library SHA256 is `b6a6bb2742fd60ab12c91853cea5695c4f5754896dd29d0784808489418aa46e`. The immutable pin and configured baseline are unchanged. Nonblocking remains an opt-in candidate policy: displayed images can precede current scene state, so strict mode remains appropriate for same-frame scientific picking/capture agreement. Manual review and native publication approval remain pending. Unchanged slice-panel rendering reuse is a separate potential follow-up.

## Source-only CI native-test prerequisites — October 18 2026

The published `8e5adcb` CI run exposed unguarded native integration fixtures: the locked Datoviz source package imports successfully but has no shared library on the CPU-only runner. Native-dependent fixtures and individual tests now request an explicit native prerequisite; pure tests in the same modules continue to run. Missing-library errors skip only when no `DATOVIZ_LIBRARY` is configured. Explicit-library failures and unrelated runtime errors still fail, covered by three focused policy regressions. No dependency pin or native setup/build policy changes.

The source-only full suite passes 1,015 tests with 91 reported skips. Ruff, strict MkDocs, the isolated wheel build/install check and whitespace checks pass. Gallery smoke takes CI's existing expected missing-native warning/skip route. These skips do not establish native correctness; candidate native tests remain a separate validation lane. Published commit `2eca4d34b8f6b15ff1a4ffb1da46ad2d0de47b9d` passes remote CI on Python 3.11 and 3.13 ([run](https://github.com/int-brain-lab/ibl-datoviz/actions/runs/39115059750)).

## Scientific candidate synchronization integration — October 18 2026

Native `fix/arcball-viewport-orbit` integrates the validated main synchronization fixes through merge `84f65c0ff`; `eb0b6794a` adds a combined indexed-state/LUT failure-and-retry regression. The merge preserves the candidate's navigation, fragment coverage and indexed-state APIs. An independent high-effort Sol 6.1 integration audit found no blocker. The configured baseline and immutable dependency pin remain unchanged; this is candidate evidence, not baseline promotion or manual interaction acceptance.

The merged candidate builds and passes binding freshness/ABI checks, 113 runtime-vklite checks with synchronization and submit-time validation explicitly enabled, 644 scene CPU checks, and targeted indexed-state (5), fragment-clip (4), WBOIT (17) and scalar-transfer (1) checks. The subsequently added combined retry regression passes separately: failed LUT allocation preserves pending bank consumption and volume realization; retry emits both updates; the next unchanged emission emits neither. The full IBL suite against the explicitly paired candidate facade/library passes 1,102 tests, with one optional registered 10 um asset test skipped because its asset root is absent.

A fresh Vulkan/NVTX capture on the merged Debug candidate records 240 actual public-router rotation frames at the same 2240×1600 host, 1614×1385 source, UI scale 1.5, D070/full 50 um slices and six context surfaces. Validation is disabled only for these performance experiments. The instrumented trace averages 4.460 ms/frame. It contains 480 timeline waits: 240 short waits total 0.149 ms and 240 source-completion waits total 488.995 ms (2.037 ms/frame). GPU workload interval union is 1.938 ms/frame; GPU time overlaps host waiting and must not be added to it. There are no queue-idle calls or transient buffer/command-buffer allocations during the range. One device-idle call takes 0.136 ms across the entire range, so broad device waits are no longer a per-frame bottleneck. This is bounded exercised-path evidence, not universal synchronization correctness or input-to-photon latency.

Separate diagnostic visibility ablations, retaining the same panels and input trajectory, use two 240-frame runs each: ordinary rotation 4.113/4.327 ms, hidden slices 3.555/3.536 ms, hidden context meshes 2.291/2.241 ms, hidden volume 3.729/3.902 ms. These sequential diagnostic runs are not additive cost decompositions or matched ABBA benchmarks. They point to translucent context rendering and strict source completion as the next useful native targets. A separate 180-frame cProfile run records 101 ms total Python callback work (0.56 ms/frame, including replay overhead), with GUI sidebar work 55 ms and tree drawing 15 ms; retained selector derivation is no longer dominant.

The next architecture investigation should compare panel-level render reuse for unchanged slices against the existing nonblocking GUI generation-promotion/fairness design. Preserve strict same-frame mode and scientific picking/input semantics; do not hide context meshes or change transparency as an unreviewed optimization. Queue-role metadata repair is separate: allocated queues currently lose capability/is-set metadata and repeated same-family requests can reuse indices. Repair and test metadata without moving consumers to optional queues; all current production consumers explicitly use MAIN, so that repair alone does not accelerate rotation.

Receipts remain ignored under `build/review2-rotation/` (integrated Vulkan SQLite/report, summary JSON, cProfile and per-variant reports). The measured candidate library SHA256 is `19d52000bdc68c4721c28668f476c00faec94c7141b707e24965224e3ea5a04b`. Native integration/test receipts remain under the candidate's ignored build tree. Linux evidence does not establish macOS interaction acceptance. Publication remains pending the native repository's explicit approval requirement.

## Retained region selector derivations — October 17 2026

The browser model retains one immutable result per search-context, ranked-projection
and visible-row derivation. Frame candidates share warm entries; a candidate miss
replaces only its own entry, preserving the committed model for rollback. Semantic
keys detect direct mutable value/folding changes, ignore unrelated selection and
focus changes, and preserve effective anatomy order during search. Catalog selection
indexes and stable ranking positions are built once. Cache storage is bounded per
model rather than accumulating query history. The pinned conformance bundle and
new mutation/copy/ranking regressions pass (20 model tests).

The GUI retains projection, expansion, annotation identity and selection
preparation separately from successfully uploaded native state. Both pre-draw and
post-input upload boundaries remain; partial native failures still invalidate
applied-state knowledge and restore the previous presentation. Annotation keys
preserve signed zero and normalize missing/nonfinite values. Regional data is
refreshed at existing set/clear/mapping transactions instead of every sidebar
frame. New regressions cover unchanged-frame preparation reuse, data replacement,
mapping, clearing, annotation failure, rollback and retry. A high-effort Sol 6.1
read-only audit found no correctness blockers.

Validation passes against the unchanged strict baseline `73d0f0bc`: 1,101 tests
passed, with two skips (the optional image-plane-pan API absent from that baseline,
and the registered 10 um asset test without its explicit asset root). Strict doctor,
Ruff, strict MkDocs and three-frame startup/cleanup of both numbered apps pass.
Manual interaction acceptance remains deferred.

A fresh paired actual-X11 public-router replay used the same native Debug library
(SHA256 `6c61683b83630d5888b619464b7e474b71b3b2253fc889cd00af21a66dbbfd0d`),
Python 3.11, 2240×1600, UI scale 1.5, D070/full 50 um slices and six context
surfaces, 3×240 frames per case. The pre-change package snapshot averaged 9.565 ms
per frame (9.840/9.478/9.376); retained preparation averaged 8.367 ms
(8.618/8.603/7.881), a 12.5% frame-time reduction in this bounded run. Every run
verified a changed arcball model. These are workload-specific host-frame costs,
not portable FPS or input-to-photon claims. Separate 180-frame cProfile runs
recorded 364 upload calls in both cases: cumulative upload Python time fell from
930 ms to 4.1 ms, while visible-row derivation fell from 765 ms to 1.1 ms and
frame-time regional-value preparation disappeared. Profiler timings include
instrumentation overhead and are not the wall-time benchmark. Raw reports,
profiles, the isolated pre-change package and comparison receipt are ignored
under `build/review2-rotation/` and `build/selector-cache-baseline/`.

A separate read-only native exploration confirmed that volume transfer-LUT
emission currently lacks an unchanged-input gate, and identified broad waits in
the strict GUI viewport resolver and command submission helper. Follow-up belongs
in Datoviz: retain LUT realization per consumer/resource generation and replace
broad waits with precise completion dependencies while preserving staging and
sampled-image lifetimes. Do not merely gate on opacity or remove waits. No native
code, source revision, build or dependency pin changed in this optimization.

## Direct slice region selection — October 17 2026

Linked 2-D slices now distinguish left-click (move crosshair without changing region selection) from right-click (select the signed region under the pointer without moving the crosshair or resetting zoom). Void clears region selection; points outside the displayed image do nothing. Selection uses the active mapping and existing selection controller, preserving tree/table synchronization and leaving auto-slice navigation unrequested. With pending lazy raster or exact-contour updates, it uses the displayed section, and rejects a displayed section from an obsolete mapping. Left-double-click resets slice zoom; right-double-click does not. Existing 3-D rotate/pan input is unchanged. The review toolbar and interaction documentation explain the controls.

The focused slice-input, review and contour/native suites pass 50 tests. An actual review-2 XTest right-click selects region -599 while retaining cursor (132, 114, 80) and slice zoom. Ruff and strict docs pass. Manual interaction acceptance remains pending.

## Review 2 presentation and performance follow-up — October 17 2026

Review 2 now starts with grayscale anatomy plus mapped labels at 45% opacity. An always-visible Slices selector switches anatomy, anatomy plus labels, labels, and anatomy plus boundaries without replacing panels or changing cursor/region selection. Existing layer and opacity controls remain available; custom layer combinations are reflected in the selector. The toolbar explicitly distinguishes slice clicks (crosshair position) from brain/tree clicks (region selection). The existing Select button under Cursor and selection selects the region at the crosshair. Existing click semantics and double-click slice-zoom reset are preserved. `--preset anatomy` retains grayscale startup; reset restores the new overlay default.

A bounded attribution run used the actual LinkedAtlasReview, D070 meshes, complete 50 um raster slices, six major context surfaces, Allen mapping, UI scale 1.5, native candidate `63b51011e`, NVIDIA RTX 5090/595.99.02 and Python 3.13. At 2240×1600 on the actual X11 desktop, 24 updates per scenario averaged 25–29 ms per slice step and 70 ms per selection, versus 55–62 ms and 99 ms under Xvfb. Forced idle redraw averaged 2.9 ms on the desktop versus 29 ms under Xvfb; these are bounded harness frame costs, not end-user FPS or input-to-photon latency. Native phase timings show virtual-display presentation dominates that discrepancy; do not use its wall times as desktop rendering performance. Color-overlay and grayscale workloads were measured separately. Loading verified inputs took about 1.8 s with warm filesystem caches, construction 0.7 s, and window creation 0.2 s, before first-frame work.

The main client hotspot is `AtlasMesh.normalize_points()`, which rescans all mesh vertices for min/max whenever the cursor marker moves. A profiling-only cached-center experiment reduces actual-desktop slice steps to 13–18 ms and selections to 61 ms; standalone action cost drops from about 15 to 2–5 ms. Production code is unchanged: retaining the mesh affine needs an explicit storage/geometry-lifetime contract. Selection also rebuilds per-vertex colors and reduces authored alpha back to presentation IDs in `_visible_surface_faces()` (about 20 ms per profiled call). Cache or compute the authored visibility at presentation granularity with correct mapping/palette/style/value invalidation, then apply selection masks. Keep rollback, signed region IDs and GPU query alignment covered. The ordinary 50 um volume path currently prepares synchronously; its preparation costs about 2–5 ms per axis, while Python-side upload calls cost about 0.3 ms per payload. First remove the larger redundant work before adding scheduling complexity.

Real XTest drags were verified to change the model/projection: at 1400×1000 under Xvfb, rotation/pan averaged about 20 ms per motion and slice wheel about 36 ms. Enabling optional brain hover raised motion frames from 20 to 43 ms. Native query timing attributes about 13.4 ms to construction, 1.5 ms to emission and 4.1 ms to backend work, with roughly 16 MB of static uploads per frame. The executor retains only one visual's static query geometry; querying the six major surfaces repeatedly replaces that cache. This is a concrete general Datoviz target requiring retained resources for multiple visuals, bounded memory and destruction/version invalidation, rather than a client hover throttle. Hiding the zero-opacity volume did not materially improve frame times in the matched Xvfb experiment.

Host RSS on the desktop was about 727 MiB after warmup and 868 MiB after selection, then stable over the bounded subsequent scenarios; closing reduced it to 559 MiB while inputs/client references remained alive. These are process resident measurements, not GPU allocation or leak-freedom evidence. The long-run retention and GPU allocation breakdown remain follow-ups. Raw receipts, cProfile dumps, native phase logs and screenshots are ignored under `build/review2-performance/`; one scalar arcball-setter scenario did not redraw the source view and is excluded from navigation conclusions. Use the verified XTest drags instead. The cached-center runs are diagnostic experiments, not delivered optimizations.

The focused review/slice-input suite passes 33 tests, including native retained-panel updates and all four representation choices. Both numbered apps start and Ruff/strict docs pass. Manual review of the new toolbar, colors and click explanations remains pending.

## Repeated pan/zoom distortion correction — October 17 2026

Repeated screen pan plus viewport-centered physical dolly accumulated lateral camera displacement. Rotation matrices remained rigid, but the resulting oblique perspective could severely distort the atlas. This was a navigation-policy design error in the earlier candidate; the previous bounded gesture tests did not expose the accumulated effect.

The atlas viewer now selects optional native `PROJECTION_ZOOM` alongside `SCREEN_PAN` and `ADAPTIVE_ORBIT`. Pan/zoom changes only image framing and magnification, keeping camera position and depth projection fixed. Wheel zoom remains centered on the viewport and pan tracks pointer pixels at every magnification. Zoom during an active pan rebases its gesture origin, including controller links. Adaptive rotation uses actual image magnification: anatomical pivot when zoomed out, transitioning to the viewport inspection pivot when zoomed in. This intentionally replaces dolly parallax with image magnification for atlas navigation; native physical dolly remains available separately. Older configured baselines retain their supported behavior and the immutable pin is unchanged.

Regression coverage includes 480 mixed pan/zoom operations, multiple depths, closed-loop/reset history, adaptive pivots after repeated gestures, active-pan wheel and linked zoom continuity, mode/link validation and GPU face-query alignment after magnification and pan. Linux validation passes all 1,300 native tests and 59 focused arcball cases, binding/ABI checks, 1,088 downstream tests with one existing missing registered-asset skip, both numbered app startups, Ruff and strict docs. The user accepted the corrected navigation during Linux review. Manual macOS acceptance of this correction remains pending.

## Adaptive rotation pivot experiment — October 17 2026

The atlas viewer opts into the candidate native `ADAPTIVE_ORBIT` policy when available alongside `SCREEN_PAN`. At initial framing and when zoomed out, rotation retains the current anatomical origin. A cubic transition in normalized camera dolly reaches the viewport-center pivot at roughly three times the initial perspective magnification. Native `orbit_zoom_start` and `orbit_zoom_end` configure these endpoints (defaults 1 and 3); they are magnifications rather than the stored exponential dolly factor. The anatomical center includes accumulated placement after earlier close-up rotations, avoiding reuse of an old local pivot when zooming out.

Choosing a pivot does not move the image; the pivot is frozen throughout each rotation drag. The existing pointer sphere/quaternion mapping, exact pixel pan and viewport-centered wheel zoom are preserved. The viewport target uses a stable positive inspection plane rather than transparent-shell depth picking, including after dolly passes the original center. Tiny framing changes taper smoothly to exact unpanned behavior. Orthographic rotation stays anatomical. The native policy remains opt-in; the atlas viewer enables it for the current experiment.

Native candidate `70ecc2e2c` passes all 1,296 native tests with zero failures/skips, plus generated binding and ABI checks. A high Sol 6.1 audit found no remaining blockers after the continuity and link fixes. The downstream suite passes 1,088 tests with one existing registered-asset skip, both numbered apps start, and Ruff passes. On macOS with Apple M1 Pro, all 55 focused arcball tests pass with zero skips, regenerated bindings and 210-record ABI validation pass, both numbered review apps start, and all five retained-view/surface-query checks pass. These checks establish native startup and rendering integration; manual interaction acceptance remains pending. Reviewers should compare whole-brain rotation while zoomed out with local viewport-centered rotation after panning and zooming in, checking for jumps at drag start, continuity across zoom levels and stable behavior after zooming out again. Publication and immutable-pin promotion remain pending.

## Viewport-centered wheel zoom after pan — October 17 2026

The image-plane pan candidate now directs wheel dolly along the ray through the center of the currently framed viewport. Previously, the projection offset moved the old optical center away from the viewport center, while wheel movement still followed that old axis. The new retained lateral dolly displacement keeps points on the viewport-center ray centered through zoom, without changing the physical rotation pivot, pan-neutral rotation controls or exact pixel panning. Direct programmatic zoom remains a scalar setter; orthographic wheel behavior and the existing wheel sensitivity/distance law are unchanged. Reset clears the new displacement. ZOOM links share it only between two screen-pan controllers; mixed-mode links continue to share only the scalar.

Native candidate commit `6f4606276` passes all 1,289 native tests with zero failures/skips. The downstream suite passes 1,088 tests with one existing registered-asset skip; both numbered apps start, and strict docs pass. Regression coverage includes three depths, repeated pan/zoom, off-axis and tilted perspective cameras, orthographic behavior, wheel reversibility, reset and link isolation. Actual review-1 XTest pan plus wheel-in/out checks pass at dolly 0/1/2/2.8. A high Sol 6.1 audit found no remaining blockers. Manual acceptance remains pending. The configured checkout and immutable pin stay unchanged. Use `uv run --frozen python build/review_candidate.py 1 --ui-scale 1.5` to review, after closing previous windows.

## Image-plane pan candidate — October 17 2026

Manual feedback identified inadequate pan sensitivity at high zoom. Independent pixel tracking reproduced it: a 60-pixel drag moved the prominent atlas features about 18 pixels at dolly 2 and 8 pixels at dolly 2.5. The nearest translucent context surface was a valid GPU depth anchor but a poor perceptual reference for deeper visible anatomy. The earlier state-derived depth checks below established depth selection, not pixel tracking of the visible structures.

Native candidate commit `857f66f89` adds opt-in `DVZ_ARCBALL_FLAGS_SCREEN_PAN`: a normalized projection offset moves every visible layer by the same number of pixels, without changing the physical camera, original rotation pivot, unpanned rotation mapping or depth values. It bypasses navigation-depth queries, continues working when the original pivot passes behind the camera, rejects combination with viewport-orbit mode, and rejects PAN links between different pan modes. Ordinary camera/surface-depth panning remains the native default. The atlas viewer selects image-plane pan when that optional native flag is available; the immutable supported baseline keeps its existing behavior.

Actual review-1 XTest captures now track a 60-pixel drag by exactly 60 pixels at dolly 0, 1, 2, 2.5, 2.8 and 3.1. GPU face queries follow the rendered offset and reset restores alignment. All 1,285 native tests pass with zero skips; candidate bindings and ABI checks pass. The downstream suite passes 1,087 tests with one existing registered-asset skip, and the added query regression passes. Both numbered apps start; Ruff and strict docs pass. Manual acceptance remains pending. No publication or pin/configuration change is part of this candidate.

Review with `uv run --frozen python build/review_candidate.py 1 --ui-scale 1.5`, after closing earlier windows. `just review` continues to use the configured baseline.

## Wheel sensitivity and surface-anchored pan — October 17 2026

Datoviz commit `a359c8f4b` adds `DvzArcballDesc.zoom_speed`, a per-controller wheel sensitivity multiplier: default 2 doubles the previous response, 1 restores it, and zero selects the default. Programmatic zoom is unchanged. The descriptor and regenerated bindings must be paired: the former library-only override with the supported facade no longer suffices. The ignored local candidate runner pairs the candidate facade/library while reusing the approved platform environment, leaving configured setup and the immutable pin unchanged.

Linked slices now advance four sections per standard wheel notch and twenty with Shift, retaining fractional remainder, keyboard precision, slider precision and Ctrl+wheel slice magnification. Validation passes: 1,276 native tests with zero skips; generated bindings, policy and ABI checks; 1,087 downstream tests with one unmaterialized registered-asset-set skip; both candidate review apps start. Ruff passes. Interactive acceptance and publication remain pending.

Datoviz commit `2c09a5ba6` fixes visible-mesh grab panning by querying GPU surface depth at the stored press position when dragging starts. The corresponding plane stays fixed during the gesture, so the grabbed surface follows mouse pixels across zoom, including visible geometry beyond the original pivot plane. Deferred cumulative input, private query scopes, epochs and weak-identity/binding/camera/layout/geometry checks guard completion; source-panel teardown and HiDPI/subpanel coordinates have regressions. Context meshes can supply navigation depth without becoming scientifically selectable. Background misses retain the pivot-plane fallback, with no movement if no positive plane exists; non-mesh depth is not yet supported.

Final pan validation passes: 1,282/1,282 native tests with zero failures/skips; real GPU depth and pan cases, shader ABI and query-boundary/source guards, both new WGSL shaders through Naga, and three private queue/lifetime cases through Valgrind with zero errors/leaks. The downstream suite passes 1,087 tests with one unmaterialized registered-asset skip; both numbered apps start. Actual review-1 XTest grabs with hover enabled at dolly 0/1/2 use foreground depth approximately 2.899/1.592/0.477 rather than pivot depth 3/2/1. High Sol 6.1 architecture review and independent controller review found no remaining blockers. These checks do not replace manual Linux review; macOS interaction evidence remains unavailable.

The local ignored review helper pairs the candidate Python facade and library; from this worktree run `uv run --frozen python build/review_candidate.py all --ui-scale 1.5`. Close previous windows first. This deliberately reports the unpinned candidate revision and leaves `build/review/config.json`, `pyproject.toml` and `uv.lock` unchanged. Publication and pin promotion remain pending interactive acceptance.

For distance-relative zoom, a multiplicative camera-distance law is the recommended separate follow-up: `d_new = d_old * exp(-gain * wheel_delta)` gives coarser travel far away and finer travel nearby. Current wheel zoom still becomes additive eye-space travel through `log(zoom)`; this batch changes sensitivity, not that distance law. Orthographic zoom needs projection-scale handling rather than camera dolly.

## Pan-neutral fixed-pivot interaction candidate — October 17 2026

The viewport-centered physical orbit below was reviewed and rejected as the default. The next local native candidate, `4f9caf8b5` on `fix/arcball-viewport-orbit`, keeps the original physical rotation pivot and sphere/quaternion mapping, while computing the pointer sphere center with view-plane pan omitted. Original zero-pan behavior is preserved for stable camera/zoom during each gesture, including off-axis cameras, both projection types, zoom and edge drags. Panning no longer carries the control sphere offscreen. The former physical-orbit mode remains available through `DvzArcballDesc.controller_flags = DVZ_ARCBALL_FLAGS_VIEWPORT_ORBIT`, disabled by default.

Focused native tests pass 40/40 and the full native suite passes 1,276/1,276 with zero failures or skips; regenerated Python bindings, 17 binding tests, policy checks and ABI validation pass. A high Sol 6.1 read-only audit found no blockers. Both modes retain their regression coverage. Both numbered review apps pass bounded startup with the candidate library. The same explicit candidate-library review command selects this new default after closing and restarting any previous review window. Interactive acceptance, publication and pin promotion remain pending; the configured checkout and supported immutable pin are unchanged.

## Linked review anatomy and orbit follow-up — October 17 2026

Review app 2 now uses the same six verified global-region context surfaces,
colors, opacity and recording camera as app 1. Both entry points share the
context loader and surface-selection helper. The linked slice panels and dense
region identities remain available for slice navigation and explicit selection.
The linked CLI also accepts `--context-root`; absent context assets fail clearly.
Focused review/context tests pass (103 CPU and three native tests), Ruff passes,
and an inspected offscreen linked capture confirms the coarse context.

The viewport-centered arcball candidate is committed at `8ed7e84a8` on the local Datoviz branch `fix/arcball-viewport-orbit`, based on the supported scientific revision. Pointer rotation rebases the inspection target to the center ray at its retained depth without a pose jump, keeps the virtual sphere viewport-centered, and preserves the public pure-orientation model matrix. Private navigation translation supplies the corresponding orbit. Camera bases are frozen during a drag; rotation-only links keep gizmos centered, and full/PAN-only links preserve live pose and cumulative target gestures.

The large-pan regression fails on the original engine and passes on the candidate. Focused coverage passes 39/39 with zero skips, including perspective/orthographic cameras, tilted camera poses, repeated pan/zoom/orbit, press/commit/reset continuity, camera-context restoration and live full/partial links. A high Sol 6.1 independent audit identified the partial-link transition cases; regression coverage was strengthened to prove propagation and continued-drag behavior. Both numbered review apps pass bounded three-frame startup with the candidate library and the supported Python facade.

The configured checkout and immutable dependency pin remain unchanged. Interactive rotation quality still requires Linux review. Use an explicit `DATOVIZ_LIBRARY` override pointing to the candidate build when reviewing; the startup report must identify that library. Publication, integration and pin promotion remain pending the user's review. The final native suite passes 1,275/1,275 with zero failures and zero skips; the independent audit reports no remaining blockers. Strict MkDocs and whitespace checks also pass.

## Published native fixes and supported baseline — October 17 2026

The user approved publication and baseline promotion. This supersedes the local,
unmerged and pin-unchanged status in the historical checkpoints below.

- Datoviz main now contains the RC3 input and buffer-growth fixes at
  `bdaee98dff2b46bbdf936236bfbb63eb1a11fb40`. Its post-push submodule-reachability
  workflow passed for that exact commit.
- Published scientific-3D integration
  `73d0f0bcdd595d2f76e2cdffcc2dd89c25a56858` merges the approved main changes into
  `rc4/scientific-3d`, preserving its APIs and both sets of tests through three
  test-only merge conflicts. Its native full suite passes 1,270/1,270 with zero
  skips; regenerated bindings and ABI validation pass, including 210 records.
- `pyproject.toml` and `uv.lock` now pin that exact published scientific revision.
  The configured native checkout was rebuilt at the same revision, and ordinary
  `just doctor --strict` passes. The locked source package installs successfully
  from its public Git revision; the anatomy pin remains unchanged.
- Full IBL validation passes on both Python 3.11 and 3.13: 1,087 tests, with one
  explicitly unmaterialized registered-asset-set skip per run. Strict numbered
  review startup, explicit exact-contour workspace startup, Ruff, strict MkDocs,
  and whitespace checks pass. An actual XTest run on the promoted library cycles
  Allen/Beryl/Cosmos three times without runtime execution errors; hover, AP
  660→658→626 wheel/burst steps, accepted contours and six fixed buffers pass.

Run `just review all --strict --ui-scale 1.5` from a desktop terminal for the
pending interactive Linux review; close app 1 to advance to app 2. For exact
contour review, use the explicit asset invocation in `docs/review-apps.md`, adding
`--strict` before its forwarded arguments and omitting the bounded frame limit.
Automated startup does not establish interaction quality. Physical macOS/Windows
rendering and input remain unverified; no release artifact is approved by this
baseline promotion. Continue implementation on `feature/datoviz-v04`.

## Mapping buffer-growth error fixed locally — October 17 2026

This supersedes the unresolved mapping error in the input-only checkpoint below.
Datoviz commit `cb4859066`, on `fix/input-router-gesture-ownership`, fixes growth
of buffers defined by a prior successful stream but never used by a draw. The
atlas exposed this through retained UV buffers on untextured meshes. Duplicate
unused definitions within one batch, external-buffer ownership, pending work,
readbacks and dependent-binding restrictions remain protected. Native and
WebGPU implementations share the revised contract; public API layouts are
unchanged.

- Native full suite: 1,231/1,231 passed, zero skips. All six new CPU lifecycle
  regressions pass Valgrind without leaks/errors. The actual native mesh
  regression and WebGPU regression failed before the fix and pass afterward.
- Specification checks and WebGPU Node smoke pass, including checked GPU-error
  scopes and packet-set failures. Independent high Sol 6.1 review found no
  remaining P1/P2; Node smoke does not establish actual browser GPU rendering.
- The isolated supported f77 source plus both fixes passes 1,087 IBL tests on
  Python 3.11, with the optional registered-asset-set skip. Actual XTest mapping
  cycles through Allen/Beryl/Cosmos three times without any runtime execution
  errors; hover, AP 660→658→626 wheel/burst steps, accepted contours and six
  fixed polygon buffers all pass.

Both fixes remain local and unmerged. The supported binary hash, review
configuration and package pin remain unchanged; manual platform review and
exact baseline promotion remain separate gates. No client workaround was added.

## Native input correction validated locally — October 17 2026

The RC3 fix is committed in Datoviz as `3690cc8f8` on
`fix/input-router-gesture-ownership`, based on native main `858bdf261`.
One router-owned interpreter replaces independent gesture recognizers; windows
retain one activation and GUI viewports borrow it. Raw and union subscribers
receive one original event regardless of zero, one or two activation handles.
No Python deduplication or sensitivity change was introduced.

- Native main candidate: 1,224/1,224 tests pass with zero skips; all 23 input
  tests pass Valgrind with zero errors or retained bytes. Regenerated bindings,
  ABI checks and 15 Python raw/facade/GUI checks pass. Independent high Sol 6.1
  architecture review found no remaining P1/P2 after runtime-driven corrections.
- Native main lacks APIs used by the scientific workspace. The same eight-file
  core patch applies cleanly to an isolated exact f77 baseline; its independent
  build, regenerated bindings and focused input/window/controller/GUI tests pass.
  The IBL suite on that candidate passes 1,087 tests on Python 3.11, with the
  existing optional registered-asset-set skip.
- Actual XTest input at UI scale 1.5 verifies hover and Allen/Beryl/Cosmos mapping,
  one wheel notch AP 660→658, and a 16-notch burst ending at AP 626 with the
  matching contour request accepted. The trace has one slice step and one
  preparation, 511.63 ms settle time, six stable polygon buffers, and eight
  cached entries totaling 7,272,224 bytes. This is a single trace, not a
  comparative performance benchmark. Evidence remains in ignored build outputs.
- The previously recorded pre-wheel mapping `CreateBuffer InvalidState` error
  still appears. It is a separate unresolved resource-lifecycle issue; the
  input correction does not establish warning-free rendering.

The original supported binary hash, native checkout, review configuration and
package pin remain unchanged. The native fix is local: merge/publication and a
validated package baseline upgrade need separate review. Manual Linux review
remains deferred, and physical macOS/Windows input is unverified.

## Published reader and contour performance — October 17 2026

This checkpoint supersedes the unpublished-reader and performance limitations in
older entries below. The user authorized publication, deep timing/memory work,
subagent exploration and postponing manual review.

- Published reconciled anatomy `2e190e0`, then optimized reader
  `95ae2426965769d2592f239abb251bc621f1cedb`, on anatomy/main. The package lock and
  CI fixture checkout now use that immutable revision. Contour review uses the
  installed locked reader by default; `--anatomy-source` remains an optional
  child-process development override. A fresh empty-cache frozen environment
  fetched the public anatomy and Datoviz commits without source overrides; a
  freshly built installed wheel passed the isolated CPU installation check.
- Reader decoding across all 3,260 sections is byte-identical in geometry,
  identities, component order and holes, with aggregate CPU time 1,172→328 s
  (3.57×). Anatomy passes 197 tests, zero skips. The independent high Sol 6.1
  audits found no remaining P1/P2 issues in reader arithmetic or package caches,
  exact interval vectorization and teardown.
- Native CPU triangulation passes every section: 1,373,858 components, 62,968
  holes and 109,809,314 triangles, with valid coordinates/index bounds and exact
  per-component outer-minus-holes area. Four workers took 117.46 s, peak worker
  RSS 82.31 MiB. This establishes triangulation/area, not whole-corpus pixels or
  overlap-free spatial coverage.
- `9514665` adds bounded immutable geometry caches and selection interval reuse;
  `739e495` reuses source geometry for rasterization and retained native fills,
  removes unused contour-panel textures and skips ineffective dimming masks.
  `b09fc82` vectorizes exact integer edge sweeps; `83d885e` releases preparation
  caches after workers join. Public constructors retain owned-storage validation.
  `adafdd0` stops superseded work between decode, geometry and raster phases,
  and releases executor callbacks after worker shutdown. The actual-wheel trace
  accepted its final payload at 683 ms instead of 956 ms, preserving all input
  steps and fixed polygon buffers.
  Source/mapping/axis/index keys, byte budgets, native failure quarantine,
  accepted-section identity and shared source lifetimes are preserved.
- Three fresh-process controlled medians: construction 3,759→1,890 ms, cold AP
  change 1,209→606 ms, cached return 263→87 ms, parent selection 1,038→169 ms,
  Beryl 537→358 ms, Cosmos 600→372 ms. Median host RSS 1,124→1,061 MiB and peak
  1,350→1,249 MiB; allocator variation and workload scope are recorded in the
  [performance report](CONTOUR_PERFORMANCE.md). Pixel comparisons for selection
  and Beryl are exact. Active-hover wheel/burst checks are separate workloads.
- A separate PID-based NVIDIA inventory reports 208 MiB for warm 4× contours,
  unchanged by this batch; 1× contours use 190 MiB and registered raster 254 MiB.
  Retain the accepted 4× quality. Native candidates are duplicate triangulation,
  topology rebuilds on color changes, zero-width stroke preparation and transient
  fill copies. The native scene's 109 MiB struct is mostly virtual reservation;
  scene allocation adds less than 1 MiB RSS. No engine build or baseline upgrade
  was made.
- Confirmed a native P2 in hash-verified f77: each gesture handler re-emits the
  unchanged wheel event to union subscribers. With the window and GUI viewport
  handlers, one raw wheel event is delivered three times, advancing six slices.
  `tools/diagnose_wheel_routing.py` reproduces it without a GPU context or XTest.
  Correct native pass-through forwarding and handler ownership before considering
  a validated baseline upgrade; no sensitivity/deduplication workaround was added.
  The pre-wheel mapping trace also logs `CreateBuffer InvalidState`; captures and
  request checks pass, but this warning remains a separate unresolved engine gate.

Final package validation on **both Python 3.11 and 3.13: 1,087 passed, one
optional registered-asset-root skip per run**, using the hash-verified original
f77 binary and isolated f77 Python facade. Fresh installed-wheel CPU checks also
pass on both Python versions.
Ruff, strict MkDocs, source/wheel builds and whitespace checks pass. The configured
external Datoviz checkout is still at `54c9ce1`, while the supported baseline is
`f77b5d0`; ordinary `just doctor --strict` correctly rejects that known drift.
Checks used `build/endpoint-depth/run_pinned.py` without changing the external
checkout, native library, setup configuration or supported native pin.

Manual Linux review remains deferred; macOS rendering evidence remains a release
gate. Exact contours stay opt-in and the dense 50 µm defaults remain available.
Cold slices are faster but still not fluid scrolling. A lazy physical-plane
raster path and unchanged-image reuse are the next client candidates; they need
explicit preparation/accepted-section contract tests. Physical extraction of the
shared data reader remains a separate packaging decision. Its audit identifies
NumPy's missing base dependency and a moderate extraction with compatibility
re-exports; no production-agent change or second reader implementation was made.

## Autonomous contour, shared-reader and agent integration — October 17 2026

The user accepted the current contour appearance and authorized implementation
without waiting for further manual review. Work landed on the existing branches;
no engine build, native pin, production-agent change, merge into Datoviz main or
publication was performed.

- Resolved the Mac `ibl-anatomy/main` merge conflict by retaining both public
  contour and surface exports, committed as `2e190e0`. Fetched that merge from
  `ssh mba` into local anatomy/main. Both trees are clean; the two source commits
  remain unpublished. Anatomy passes **186 tests, zero skips**, including actual
  three-orientation contours, source surfaces and ontology. All 57 public exports
  resolve. Keep the installed anatomy pin until the reconciled commit is available
  upstream; use only an explicit child-process source override meanwhile.
- `093dbe0` provides immutable exact contour components, signed mapped IDs,
  geometry containment with holes/islands and source-order boundary ties, interval
  cancellation for mapped borders and selected parent unions. Independent actual
  section checks cover all nine orientation/mapping combinations: zero mapped or
  selected-union boundary discrepancies, and 1,728 exact picks matching label
  oracles across the sampled 837 source paths.
- `f9f82ac` integrates optional `slice_renderer="contours"` into the existing linked
  AtlasViewer. Preparation uses its existing per-axis workers and latest-wins
  requests; the owner retains accepted panel identities and immutable geometry.
  Cursor/hover/selection use accepted geometry, including correct full-cell-edge
  coordinates. Old mappings temporarily suppress interactions rather than
  interpreting old geometry as new identities. Unknown pending geometry cannot
  clear selection as if it were known background.
- Two retained polygon buffers per axis avoid f77's append-only polygon,
  composite and visual slot limits. Staging includes checked triangulation before
  activation. Rejected dirty composites are quarantined at their source regions,
  so frame preparation cannot resurrect them; rollback preserves authored hidden
  visibility. Failure to restore closes the component. Native stress covers 160
  replacements, empty restoration, holes and injected failures. The numerical
  source cache is bounded by entry count and 32 MiB.
- `2d05102`, `6aecd45` allow the same scientific client to read either a named
  shared-reader workspace or an explicit BWM release, and launch contour mode
  against explicit compatible registered/intensity packs. The optional regional
  payload requires an explicit weighted-mean mapping reduction; it is not a
  scientific choice inferred from available columns. The development reader is
  scoped through `tools/review.py contours --workspace --anatomy-source ...`.
- Incubation `ibl-ai-agent-next/main` now contains the
  `datoviz-app-composition` skill, executable multi-PID/linked viewer template,
  generic annotation/regional payload recipes and frame/reduction guards. It
  composes public APIs without copying releases, adding another codec or reading
  signals. Physical reader extraction remains a separate packaging decision.

The real metadata-only two-PID release check used BWM ephys 1.1.0: insertion
`a21bade7…` supplied 384 channels and 459 clusters, and `bf746764…` supplied 96
channels and 2 clusters. Source validation remains **unknown**, while reviewed
coordinate evidence was scoped to the exact release manifest and both PIDs.
Tables retained exact selection through hide/show and Allen→Beryl changes;
removing the first recording removed its table while retaining the second
selection. A separate named-workspace linked template startup used its one
registered PID and an AP physical plane. No signal reads or transfers occurred.
Evidence is ignored under `build/agent-data-spike/`.

Full package validation passes **1,059 tests with one optional registered 10 µm
asset-root skip** on the supported anatomy pin. The explicit reconciled reader
source also passed the full suite (1,057 tests before two final client declaration
guards were added); the new guards pass focused tests. Both runs used the
hash-verified immutable f77 native baseline through
`build/endpoint-depth/run_pinned.py`. Ruff, strict MkDocs and whitespace checks pass. The high Sol 6.1
architecture audit has no remaining contour P1/P2 findings; its separate regional
aggregation finding is addressed by requiring the explicit reduction declaration.

The incubation agent's complete unit suite passes **374 tests, 13 local-data
tests intentionally deselected**; its five focused app-template tests include
source/frame and explicit mapping-reduction gates. Source and wheel builds pass,
and the new wheel passes the existing isolated Python 3.13 CPU installation
check with all three contour modules included and no native bindings imported.
Receipts are ignored under `build/contour-workspace/`.

Actual private-Xvfb contour GUI checks at scale 1.5 cover Allen/Beryl/Cosmos,
signed parent selection, exact hover, wheel and burst navigation; the latest
request wins and all six native buffer handles remain fixed. The sampled run
retained 9 decoded contour entries (7,950,912 bytes), used about 1.37 GiB peak
process RSS, settled mapping/selection changes in roughly 0.48–0.88 seconds and a
cold wheel change in roughly 2.29 seconds. These measurements do not establish
full-corpus triangulation correctness or fluid scrolling. Screenshots/receipts
are ignored under `build/contour-workspace/`. The public client also passed an
actual three-frame startup against complete registered assets and context.

Manual review is deliberately deferred. Exact contours remain opt-in; ordinary
50 µm defaults and dense auto-slice remain available. Lazy contour sources report
auto-slice unavailable rather than borrowing anchors from a different grid.
Optional physical 3D planes retain categorical pixels from the same exact grid.
Remaining work includes publishing/adopting the reconciled anatomy dependency,
whole-corpus triangulation/performance checks, additional platform evidence and
any separately authorized standalone data-library packaging.

## Shared contour reader and native prototype — October 17 2026

The authorized first two stages now have an additive numerical reader in
`ibl-anatomy/main` (commit `857564f`) and the isolated `examples/registered_contours.py` experiment
on this branch. The reader preserves signed mapping IDs and classifies arbitrary
serialized ring order into owned immutable components, holes and nested islands.
It supports the exact rectilinear half-grid SVG profile, not arbitrary SVG curves
or a smoothing derivative. Existing asset bytes and registered reader APIs remain
unchanged. Reader validation and audit details are recorded in the anatomy
repository's handoff.

The native prototype renders coronal 660, sagittal 566 and horizontal 393 directly
through retained polygon sets, unlit catalog fills and joined outlines, with
requested 4x MSAA. It uses private positive native component keys with a signed
identity side table. Three GPU tests cover holes/islands, source-buffer detachment,
actual native descriptor-buffer copying and display-only Y inversion. Geometry
and source copies have independent lifetimes; app teardown precedes scene teardown.

Original even-odd SVG versus classified-component rasterization has **zero changed
source pixel centres across all 837 source paths** in these three sections. The
captured components total 649/434/1086, with 22/15/36 holes. Decoding initially took
about 0.42–0.79 seconds per uncached section in the final captures. The final
three-panel captures took about 148–196 ms for the first render, including
deferred triangulation/warm-up; their last two warm frames were about 4–9.5 ms.
Whole-process peak RSS was about 488–497 MiB, including native/driver allocations.
These are
prototype measurements, not scrolling performance guarantees. Final receipts also
record loaded native binary and reader source hashes, requested MSAA, stroke and
output dimensions, and whole-process peak RSS.

Actual macOS captures at normal scale and central 3x magnification were inspected
under `build/contour-prototype/exact{,-zoom3}.png`. Receipts, original-path parity,
bounded GUI startup and test logs are in that ignored directory. The package full
suite passes **979 tests with one optional registered 10 µm asset-root skip**;
lint, strict docs and whitespace pass. Normal configured native source still has
the documented 54c9ce1/f77 drift; no engine build, revision, binary or pin changed.
The independent high GPT-6.1 Sol audit reports no remaining blocking findings for
this first two-stage scope; its final shared-reader check passed 33 tests with
all three real sections and no skips. Anatomy's full suite passed 159 tests.

Use the [prototype command](review-apps.md#exact-shared-contour-prototype) with
explicit anatomy source and asset paths. The source override is scoped to that
child process. The local anatomy main ancestry does not contain the installed
6498a830 surface-catalog baseline, so this experiment does not establish that its
new commit can replace the package pin. Reconcile that ancestry and validate the
full supported anatomy API before a future dependency adoption.

Workspace defaults, native selection/picking/navigation and web runtime assets
are unchanged. The next gate is human review of the three-orientation experiment,
followed by shared mapped/selection boundary semantics, worker/cache integration,
geometry-authoritative picking and bounded scrolling/lifetime tests. Complete
corpus geometry/triangulation validation and producer extraction/publication remain
later gates. Do not promise mathematically smooth curves: these are exact 10 µm
voxel-edge contours with finer source geometry and native antialiasing.

## Slice palette, selection and contour review — October 16 2026

Linked annotations now default to opaque catalog colors instead of the previous
58% grayscale blend. Native readback verifies chromatic catalog RGB values within
one byte, with no extra sRGB encoding detected. Annotation opacity remains
adjustable for grayscale context. Slice selection preserves every base pixel and
uses a dark-edged white vector outline, expanding selected parent descendants.
The legacy standalone composer's explicit dimming arguments remain available;
the linked slice request uses a dim factor of one independently of 3D styling.

Cached shared categorical contours connect half-cell crossings instead of
tracing each voxel stair step. Multi-region/checkerboard junctions meet at the
cell center. Small one-voxel regions remain represented. This is presentation
geometry within half a voxel, not higher-resolution anatomy or label
interpolation. The exact source labels and picking/lookup contracts remain
unchanged. Selected contours are owned immutable worker results, accepted under
the existing request/revision gates and remapped on zoom alongside the images.
Deselecting hides old geometry without submitting empty native attributes.

Actual macOS real-data captures were inspected at
`build/review/slice-presentation.png` and `build/review/presentation/selected.png`,
including an Allen parent selection. Bounded workspace startup passes. The full
suite passes **974 tests with one optional registered 10 µm asset-root skip**;
lint, strict docs and whitespace pass. The configured native checkout still
reports its existing revision mismatch, and no native build or pin was changed.
Manual visual acceptance and complete higher-resolution assets remain separate
gates.

## Slice cursor review refinement — October 16 2026

Removed the small mouse-following disc from the 2D slice panels, preserving
region hover and tooltips. The 3D cursor now combines its lit sphere with three
thin, subdued cyan cylinders aligned with the atlas axes (900 µm length,
28 µm radius). All parts share one scene-owned opaque mesh and normal depth
testing; temporary native geometries are destroyed after copying/merging,
including on failure. Actual macOS bounded workspace startup and lint pass
with the existing configured source revision warning.

## Lit spatial slice cursor — October 16 2026

The linked workspace's 3D slice cursor now uses one cyan Phong-lit sphere mesh
with a fixed 120 µm atlas-space radius, replacing the depth-disabled segment
crosshair and pixel dot. Normal depth testing and opaque rendering provide
occlusion and perspective cues. Native temporary geometry is destroyed after
the mesh copies it; the scene retains visual ownership. Cursor updates reuse
the same visual and preserve slice/selection behavior.

All **22 focused linked-workspace, auto-slice and native review-app tests** pass
without skips on the configured macOS runtime. The real-data offscreen capture
`build/review/cursor-lit-sphere.png` was inspected. Lint and whitespace pass;
the existing native source revision mismatch remains. Visual interaction
acceptance remains with the reviewer.

## Compact linked slice toolbar — October 16 2026

The three projection sliders now share one row with equal space. Auto-slice
progress/errors appear beside the checkbox, so transient status no longer adds
a row and shifts the viewport. The 12 auto-slice tests, lint, whitespace check
and actual macOS `just review workspace --frames 3` pass on the configured
runtime with its existing source revision warning. Interaction acceptance remains
with the reviewer.

## Review context setup recovery — October 16 2026

After pulling newer code on macOS, atlas and volume assets were present but the
ignored major-context directory was absent. Review now checks every expected
context OBJ before launching app 1, annotations, workspace or all, and reports
the setup command instead of failing inside the example. Incomplete directories
must be moved aside before setup; downloads remain confined to setup. App 2 does
not require major context.

The older local anatomy fixture cache was preserved under
`build/review/anatomy-before-6498a830-20261016`; rerunning setup prepared the locked
cache, reference envelope and major surfaces. The actual macOS
`just review workspace --frames 3` passes. All **38 launcher tests** pass without
skips; lint, strict docs and whitespace checks pass. This is bounded startup
evidence, not interaction acceptance. `just doctor --strict` still rejects the
previously recorded configured Datoviz source drift (54c9ce1 versus f77b5d0);
no native build, checkout revision or package pin was changed.

## Workspace docking and region navigation — October 16 2026

Implemented the user's workspace review requests on `feature/datoviz-v04`:

- Default Observations docking occupies only the center column below the atlas;
  Regions and Layers dock first on the sides. Windows remain movable and the
  table retains its native boolean close/reopen contract.
- The linked toolbar omits Explode and exposes Coronal (AP), Sagittal (ML) and
  Horizontal (DV) voxel sliders beside a default-on auto-slice checkbox.
- Auto-slice follows explicit Regions-list activation (including keyboard and
  shift-range endpoints), preserving observation and region selection domains.
  It computes the occupied voxel nearest the signed mapped region centroid from
  the exact loaded dense annotation grid, with deterministic AP/ML/DV ties.
  Lazy projection sources and regions without occupied voxels keep the cursor
  fixed with an explicit status. No web companion grid is reused.
- Bounded CPU lookup runs through the existing latest-wins executor pattern.
  Manual navigation, direct scene gestures, programmatic region selection,
  deselection, mapping changes and disabling the option discard pending intent.
  Enabling affects future selections only. Shutdown joins the worker; native
  post callbacks retain and report upload failures through normal app shutdown.
  Table selections keep their established precedence over simultaneous list input.

Validation: **960 passed, 1 skipped** (optional registered 10 µm asset), Ruff and
strict MkDocs passed. Tests used the existing isolated f77 source checkout paired
with the hash-verified supported baseline binary through
`build/endpoint-depth/run_pinned.py`; no native revision, pin or configuration
changed. Real private-Xvfb mouse checks at UI scale 1.5 verified docking bounds,
projection slider movement, checkbox off/on, and Regions → worker → native post
navigation: selecting Beryl MOp (-985) reached occupied anchor (86, 71, 47) while
retaining observation 0; selecting MOs with auto-slice off preserved that cursor.
Screenshots and receipts are ignored under `build/region-navigation/`. Human
Linux/macOS review remains pending; use `just review workspace --ui-scale 1.5`.

## Integrated scientific workspace checkpoint — October 16 2026

The user authorized sustained implementation through a reviewable linked
workspace, without waiting for Linux visual review. The following is implemented
on `feature/datoviz-v04`; `main`, the supported native pin and production agent
remain unchanged. All commits are local and no publication was requested.

- `cf9f2ca`: exact native identities for filled points and spheres, private positive
  keys, attachment/source translation, stale-click guards and transactional
  highlight/table updates. Current filled point disks are supported on f77; invoking
  the point style setter with FILLED does not activate its unsupported outlined
  profile. GPU coverage checks establish the actual capability rather than
  assuming every point-style setter disables queries. Paths remain unsupported
  for composed queries. Unsupported visible path/plane/volume/legacy-probe coverage
  reports unavailable instead of silently allowing a pick through it.
- `2f930db`: immutable `RegionValues` and one owned regional quantity on the
  detailed anatomy mesh, explicit weighted-mean reduction, units, declared versus
  finite weights/counts, source missingness and unmapped/signed IDs. Hide/remove
  restores prior scalar presentation under the current mapping. Multiple active
  mesh-color owners and concurrent legacy scalar writes are rejected.
- `1896205`: physical paired grayscale/annotation slice planes from accepted
  immutable requests, correct affine signs/half-voxel edges, independent sampling,
  stale-result guards, atomic pair replacement and owned resource cleanup.
- `42adc69`, `553df02`: `AtlasViewer(layout="linked")` dispatches to the existing
  navigator implementation with one scene/registry/controller/scheduler. Thin
  `app.slices` provides explicit voxel/world units, accepted cursor events,
  presentation and physical-plane controls. Full cursor validation and rollback
  preserve observation/region domains; callbacks cannot mutate reentrantly.
  Worker/input/plane cleanup, partial construction and native-post error shutdown
  retain their ownership boundaries. Right-click selects observations;
  left-click selects anatomy. Supported anatomy contributes frontmost query depth
  without acquiring unintended region FACE eligibility.
- `ec0fdde`: optional BWM bridge consumes shared recording metadata, snapshots
  provenance, checks complete source/PID/session identity and accepts only exact
  reviewed producer frame declarations. Explicit reviewed legacy frames remain
  supported when source declarations are absent; they cannot hide failed,
  conflicting or unreviewed source declarations. Existing signal gates remain.
- `99ba9fe`: `examples.scientific_workspace` and `just review workspace` compose
  the public API with supplied local assets, optional BWM recordings and explicit
  prepared regional JSON. The default annotations and the rendering-check scalar
  fixture are labelled synthetic, not measurements. Data loading precedes GUI
  startup; no signals, discovery, downloads, statistical derivations or data copies
  were introduced.

Shared data commits on `ibl-ai-agent-next/main` are `1195770` (frozen generic
recording/frame/evidence contracts, publicly exposed through access) and
`dc69ed1` (explicit producer/PID-scoped BWM spatial declarations). The generic
contracts do not assume mouse, Allen anatomy or IBL. Frame evidence, byte
integrity, scientific source validation and insertion alignment are distinct.
Legacy releases with no declaration retain an empty coordinate-declaration list
and unknown source validation; channel coordinate columns remain intact. Full shared-reader suite: **369 passed, 13 existing skips**; focused
contract/reader checks, Ruff and mypy pass. Those 13 skips are intentional
`local_data` opt-in exclusions (enable with `pytest -m local_data` or
`IBL_AI_AGENT_LOCAL_DATA=1`), not missing dependencies or confirmed missing assets.
Exact reasons are in `build/ibl-integration/reader-skip-reasons.log`. Production
`ibl-ai-agent` is untouched.

Final package validation on both the exact f77 source/original binary and the
separate endpoint candidate: **915 passed, one optional registered 10 µm asset-root
skip each**. Lint, strict docs and whitespace pass. The normally configured
engine checkout still has its previously recorded source revision drift; the
strict baseline run uses the isolated immutable source pair. Ordinary
`just review workspace --frames 3 --ui-scale 1.5` passes with that configured
runtime's explicit mismatch warning; no build/configuration/pin change was made.
Logs are ignored at `build/workspace-final-pytest.log`,
`build/workspace-endpoint-candidate-pytest.log` and
`build/scientific-workspace/launcher-startup.log`.

Actual XTest gestures at scale 1.5 select original integer `0` and string `"0"`
as distinct attachments with matching native table selection, preserve region
selection on right-click, select signed Allen `-315` on normal left-click while
preserving observations, and commit nothing on right-button drag. A visible path
reports unsupported coverage without changing selection. Receipt/captures are
under `build/scientific-workspace/scene-mouse-*` and `linked-scene-*.png`.
Real D070/50 µm queries pass with major context and the detailed fragment-clipped
surface; hiding anatomy permits both illustrative targets to resolve exactly.
Evidence is `real-query-receipt.json`, `real-query.log` and `real-query-initial.png`
in that directory. Nonzero-alpha anatomy can block an observation even when
translucent; this frontmost policy is documented explicitly.

The shared reader and bridge retain the two real reviewed populations (384
channels/459 clusters and 96 channels/2 clusters with original IDs 21/36) through
offscreen rendering and bounded GUI startup. Source validation/alignment remain
unknown; byte integrity passes and signals are not requested. Existing reviewed
frame evidence SHA256 and release/PID scope are unchanged. Evidence is ignored at
`build/ibl-integration/shared-metadata-{recordings.png,recordings.json,startup.json}`.
The combined linked BWM/illustrative regional field/physical AP-plane capture and
receipt are `build/scientific-workspace/bwm-regions-plane.{png,json}` and were
visually inspected. Plane query unavailability is reported in the receipt.

The high GPT-6.1 Sol architecture audit reports no remaining P1/P2 findings after
fixing anatomical FACE eligibility, stale-query invalidation and partial-init
cleanup. Linux interaction/scientific presentation acceptance remains the next
user gate. The existing endpoint candidate has not been adopted. Actual browser
and macOS rendering are unvalidated; voxel quantities, supplied alignment
comparisons, physical extraction of the shared reader and an AI app-authoring
skill remain later work after these interfaces are reviewed.

## Native endpoint-gap candidate implemented — October 15 2026

The user authorized implementing, building, auditing and rendering an isolated
native correction before changing the supported baseline. Datoviz commit
`b5401cfd142981d0e0de9d59a32220f40bb98c29` on `fix/path-endpoint-gap` adds
`dvz_path_set_endpoint_gaps(visual, start_px, end_px)`. The candidate is based on
f77 and lives in a separate worktree; the normal engine checkout, review config,
immutable package pin and baseline binary remain unchanged. No changes were
published. Generated Python bindings are refreshed locally and pass their native
freshness/ABI gates, but remain unstaged according to the native repository policy.

The opt-in radii are fixed logical pixels, default zero. Each open subpath's
original start/end disk excludes fragments from every segment, including later
segments re-entering a disk. Closed paths ignore gaps; endpoints outside the
camera depth range contribute no disk. Coordinates and normal depth tests remain
unchanged. The same mask covers color, picking/query and surface-depth output;
WGSL shaders share the appearance policy. Native rendering lowers radii to
physical pixels; scientific queries use logical target pixels and user scale.
The exterior boundary has an antialias feather. This is explicit styling, with
no automatic dependency on point size or visibility.

Package commit `a5fc60b` adds retained `layer.set_endpoint_gaps_px(start, end)` and
the annotation example's `--endpoint-gaps-px START END`. Nonzero gaps fail clearly
on the supported f77 baseline before layer replacement. Defaults preserve the
current appearance. Style survives width/color/visibility/selection rebuilds,
and direct component updates restore native and retained state after failure.

Validation: native path 19/19, vector 5/5 and DPI 12/12 tests pass, with zero skips.
Tests cover multiple subpaths, gaps crossing the first segment, short overlapping
disks, zero reset, offset panels, device/user scale and near/far original
endpoints. Binding generation/checks, shader ABI and scene boundaries pass.
Naga validates both expanded WGSL stages; path/vector WebGPU packet layouts pass.
Actual browser rendering and macOS interaction remain unvalidated. The final
package suite passes **781 tests with one optional registered 10 µm asset-root
skip on both the original baseline and native candidate**. Lint and strict docs
pass. Exact suite logs are ignored under
`build/endpoint-depth/package-{baseline,candidate}-pytest.log`.

The rendered matrix passes **288 cases**: both gaps, start only and end only,
96 each. Cases span both slopes, attachment orders, three camera rotations,
point alpha modes, endpoint re-entry in either direction and overlapping short
paths. There are zero path pixels in marker interiors, zero path/marker pixels
through the nearer opaque mesh, full mesh coverage of every marker reference
pixel, and surviving external path geometry. Short paths covered by overlapping
disks disappear. The 24 zero-gap controls retain the original overlap in all
12 nearer-slope cases (85–86 white interior pixels), confirming unchanged defaults.
All reports identify the final native commit and library SHA256
`e3c060fa8392f8f531b78e13b97e4d1a4c427a7667503e1ba773267fc4849d85`.
Reports and captures are ignored under `build/endpoint-gap-{candidate,start-only,end-only,zero}/`.
The actual annotation example with 4 px radii around 8 px markers was captured
and visually inspected in `build/endpoint-depth/annotations-candidate.png`.

The final GPT-6.1 Sol high audit reports no remaining P1/P2 findings. Its review
caught and resolved shared vector input-layout compatibility and device-scale
query sizing before the final native commit. Interactive candidate review is now
the next gate; native integration into the maintained engine branch and supported
baseline adoption follow acceptance and compatibility validation. Ordinary
`just review annotations` still uses the existing configured runtime/defaults.
The ignored local launcher `build/endpoint-depth/review_candidate.py` checks the
reviewed source, binary and local binding identities before opening the candidate,
and does not modify normal setup or approve another envrc.

## Linked observation tables and native endpoint reproduction — October 15 2026

The user authorized the next two tracks after accepting generic annotations.
`app.tables.show(layer)` and the layer's Observation table button now open retained
native tables linked through `app.selection`. Complete source populations remain
available, including missing/hidden observations and zero/string IDs. A single
active-table selector keeps multiple opened populations accessible. Source context
and validation status remain visible; full pins/session details are expandable.
IDs sort explicitly as text. Row tokens never become scientific IDs.

Table selection, layer highlights and successful notifications commit together.
Native input that changes selection before host validation is rolled back on
failure. Removal and shutdown release table handles before source/scene cleanup.
Closed-table and foreign-thread reads fail before native access. An integration
test also exposed and fixed empty point populations calling atlas normalization
without any geometry. The GPT-6.1 Sol high audit, including a final reread of the lifetime guards,
found no remaining P1/P2 findings.

Validation: the final full suite passes 763 tests with one optional registered
10 µm asset-root skip. Lint and strict docs pass. Two actual BWM
recordings run through the existing shared reader and reviewed frame evidence;
the GUI capture `build/ibl-integration/observation-tables-gui.png` was inspected,
showing original cluster IDs 21/36 and source validation unknown. Actual XTest
mouse input selects original cluster 36; Python then selects 21, with native table
and scientific selection synchronized in both directions. The receipt is
`build/ibl-integration/observation-table-mouse-receipt.json`. No signal reads,
source-data edits or package extraction were needed. Table interaction remains a
new user review gate.

The normally configured engine checkout was independently advanced to
`54c9ce13a5661c917ac3d38d5a8e99cf71340216` (compiler warning changes). The existing
library SHA256 remains exactly the recorded f77 baseline:
`6d8a59ace2bf44d014da92e67cb7457b38767ed8ab5286fc7ee6e3a040ea4d40`.
Validation used an isolated, detached f77 source worktree under
`build/endpoint-depth/native-baseline`, that existing binary, strict source/library
checks and the already approved original runtime environment. No original engine
checkout was switched, no new envrc approved, no build/configuration changed and
no pin upgraded. Normal configured `--strict` commands currently reject that
external source revision; ordinary review reports the mismatch and uses the
existing configured runtime. Resolve that source choice explicitly before calling
normal configured strict checks accepted.

The endpoint diagnostic is now reproducible via
`uv run --frozen tools/diagnose_endpoint_depth.py` on a matching configured source;
portable `--datoviz`/`--library` options select an explicit pair. Its worker also
checks the imported source pin. At the pinned baseline, 24 synthetic cases cover
both slope signs, both attachment orders, three camera rotations and both point
alpha policies. The 12 nearer-slope cases show 85–86 white path pixels inside 640
pink marker-interior pixels; farther slopes show none. Every nearer opaque mesh
occludes all 640 pixels correctly. These measured results reproduce the issue;
they are not encoded as desired rendering assertions. Seven pure geometry tests
check the depth model and why cap correction alone cannot produce full marker
priority. Evidence, seven inspected representative images out of 72 captures,
report and an unapplied candidate patch are ignored under `build/endpoint-depth/`.

A screen-extruded cap compresses the depth interpolation, but even an exact
centerline correction leaves nearer path-body pixels in front of a flat marker.
A complete fix needs an explicit connected-endpoint gap/marker-priority policy,
with near-occluder regressions, in the native engine. The partial shader patch is
not a production fix and was not compiled/applied. Native implementation and any
baseline upgrade need their own explicit decision and compatibility validation;
no depth test was disabled or scientific coordinate moved to mask the issue.

## Generic annotation workflow accepted — October 15 2026

The user interactively reviewed `just review annotations` and accepts the
workflow. One small rendering issue remains: the path stroke intersects the
pixel-point marker at their shared endpoint. Track this as a narrow overlap/depth
correction; preserve scientific positions and normal 3D occlusion. A high-reasoning
GPT-6.1 Sol source audit found a native depth-policy limitation: pixel-point disks
retain their center depth while screen-extruded path caps interpolate segment
depth. Draw order alone cannot fix fragments that fail depth comparison, and the
pinned public API has no ordinary per-visual depth-bias control. No package-only
fix or engine/pin change has been made. Next prepare an isolated native endpoint
regression (both slopes, attachment orders and camera angles, with a nearer opaque
occluder) before choosing a native correction. This acceptance
is for generic annotation interaction, not the separate BWM geometry/alignment or
native exact-picking gates.

The next implementation stage is linked observation tables using the existing
attachment/source identities, followed by exact native picking for a demonstrated
supported glyph/query route. Tables must retain missing/hidden observations and
original IDs, with bidirectional selection through the existing controller. Styled
pixel points remain outside the pinned engine's scientific query profile until
explicit support and native acceptance exist.

## Reviewed BWM coordinate declaration and two-recording run — October 15 2026

The follow-up GPT-6.1 Sol high-reasoning audit separates coordinate interpretation
from insertion alignment quality. The earlier gate treated an unavailable full
producer execution chain as a blocker to any reviewed legacy frame declaration;
that was too strong for exploratory metadata visualization. The reviewed converter
preserves `channels.mlapdv.npy` XYZ columns, the historical official IBL writer
supplies AllenAtlas coordinates in µm, and the historical atlas contract agrees
with the shared anatomy bregma origin and axis orientation. This is a documented
legacy interpretation, not proof of exact upstream writer/configuration or
scientific source-validation success.

Primary pins: [IBL channel writer](https://github.com/int-brain-lab/ibllib/blob/db4ad4f2cc2e15b7c4a59f95fc9996e41ba7e51c/ibllib/qc/alignment_qc.py#L342-L358)
and [IBL atlas contract](https://github.com/int-brain-lab/iblatlas/blob/b874deaacf01c91ad54d8115b5e02ba5475ad88c/iblatlas/atlas.py).
The complete reviewed evidence is ignored at
`build/ibl-integration/reviewed-bwm-frame.json`, SHA256
`cc745213a47587b8ad89674ad243cc1c14eea22d9f528d8583cd7f0b4ab881ba`.
It declares manifest
`43978e003c20e4bb526486ef26f9ab286d9379a73a4d412f48293e20e527613b`
and exactly two PIDs: `a21bade7-5be7-4a17-a9b9-ddee453e6260` and
`bf746764-78e0-4b9c-bdf6-65b6ff45745d`. Original channel-file hashes, exact
producer execution/configuration, source validation and insertion alignment
quality remain unavailable/unknown and are retained in the evidence.

The BWM bridge now enforces optional `source_manifest_sha256` and
`source_insertion_ids` provenance scopes before conversion. Stale or foreign
recordings are rejected; no source/signal validation gate is relaxed. A future
shared-data release should carry an authoritative coordinate declaration and
producer pins itself rather than duplicating readers or mutating this pinned
release. No production data, catalog, dataset or agent source changed here.

Both real recordings now run through the shared reader, generic payload bridge
and AtlasViewer: 384 channels / 459 clusters and 96 channels / 2 clusters, all
positioned. Native offscreen capture and a strict three-frame GUI run at scale
1.5 pass; original cluster 21 in the second PID is selected in the GUI. Images
were inspected. Receipts are `build/ibl-integration/reviewed-bwm-recordings.json`
and `reviewed-bwm-startup.json`; captures are beside them. These are Linux
engineering checks, not user acceptance of alignment, interaction or scientific
validity. No signal reads were performed.

Validation: 46 payload/bridge/adapter tests pass, including release/PID scope
regressions; lint and strict docs pass. The high audit's final reread found no
remaining P1/P2 findings. Generic interactive review is ready independently via
`just review annotations --strict --ui-scale 1.5`.

## Interactive annotation launcher — October 15 2026

Run `just review annotations --strict --ui-scale 1.5` for the generic point/path
workflow with the configured native pairing, prepared D070 anatomy, the accepted
six-structure context and package-level Layers controls. It requires no slice
volumes or IBL reader. Missing context assets fail explicitly. The existing
`review all` still opens apps 1 and 2; annotations is an explicit additional target.
Quoted `--offscreen` paths and bounded `--frames` use the same forwarding/runtime
rules. See [the annotation review checklist](review-apps.md#scientific-annotations).

Validation: 28 launcher tests pass; recipe parsing/discovery, strict three-frame
native startup and strict lint/docs pass. Interactive quality still needs the
user's review. The subsequent BWM source-frame findings are recorded above.

## Scientific layers and shared BWM bridge implemented — October 15 2026

The user approved the consolidated architecture and both intended-use scripts,
then authorized implementation and focused local commits. `AtlasViewer` now owns
generic `Points`/`Paths` and recording groups, with package-level Layers controls.
Core payloads snapshot immutable arrays, source keys, frame declarations and
provenance. Recording children acquire source-scoped observation keys; viewer
attachments remain distinct. Scalar values align with the complete population,
including rows without coordinates. Source-backed quantities require ordered
observation references. Physical sphere and pixel-point controls have explicit
capabilities; native scientific picking is not claimed.

Selection shares authoritative state between Python and GUI controls. Mapping
changes clear regions while preserving observations; visibility preserves both,
and removal prunes only owned attachments. Notifications follow full native and
retained commits. Failed native updates restore old state, rollback failure closes
the viewer, callback failures cannot undo committed state, and reentrant/foreign
thread writes fail. Linked mapping/selection transitions and native input teardown
were corrected to obey the same outer transaction and lifetime boundaries.

An independent GPT-6.1 Sol subagent at high reasoning audited implementation and
examples. Its final reread found no remaining P1/P2 architecture findings after
fixes. Validation: **729 passed, one skip** for the unconfigured optional registered
10 µm asset root; strict doctor, Ruff, strict docs and wheel build pass. An isolated
installed-wheel check imports generic APIs and the optional adapter without an AI
reader installed. Both original review apps pass bounded strict startups. The new
generic annotation example runs over D070; its real GUI capture at scale 1.5 was
inspected. These are Linux engineering checks, not user visual acceptance or Mac
evidence. Receipts and captures are ignored under `build/ibl-integration/`.

Runnable clients: `python -m examples.scientific_annotations` and
`python -m examples.ibl_recordings`; both accept explicit existing assets,
`--frames`, `--offscreen` and `--report`. The BWM client requires independent frame
evidence, uses `BwmSource`/`prepare_bwm_recording`, reads metadata before GUI startup,
and performs no signal reads. Two actual BWM metadata reads preserve 384 channels /
459 units and 96 channels / 2 units; missing frame evidence is correctly rejected.
The local legacy release documents neither its complete reference-frame chain nor
an original-channel/converter pin. Official IBL code supports the legacy ML/AP/DV
µm convention, but this is insufficient to claim verified per-release registration.
Do not fabricate frame evidence to open the actual-data GUI. Obtain/review that
source declaration before its scientific visual review; metadata source validation
and insertion alignment quality remain unknown.

Next user gate: inspect the generic annotation GUI and review the real-recording
workflow once its source frame evidence is supplied. Unified linked-layout facade,
linked observation tables, native exact picking, regional/voxel workflows and an
agent app-authoring skill retain later stages. No data package extraction, dataset
copy, production-agent modification, native rebuild or pin update was needed.

## App 1 and API direction accepted; staged implementation — October 15 2026

The reviewer validates the current recording-context demo, including the latest
interaction corrections. The app-1 visual gate and subsequent scientific API
direction are accepted. Implementation and the next workflow gate are recorded
above. App 2 and further platform evidence retain their own review scope.

The [scientific viewer API proposal](SCIENTIFIC_VIEWER_API_PROPOSAL.md) records the
intended single-viewer facade, scientific payloads, recording/layer handles,
anatomy, selection, camera and linked-slice interfaces, along with staged delivery
and open review decisions. It supersedes the earlier `IBLWorkbench` naming sketch.
The consolidated proposal now includes generic owned points/paths, optional IBL
recording composition, dependency boundaries, prerequisite identity/frame contracts
and explicit selection transitions. Its two linked scripts are proposed API
examples, not runnable supported examples. The user approved the architecture and scripts and authorized staged implementation
with focused local commits. The initial payload/layer and optional IBL composition
implementation is recorded above; visual acceptance remains a later gate. An independent
GPT-6.1 Sol audit at high reasoning found no remaining P1/P2 architecture or
consolidation issues after revision. Syntax and Ruff checks pass for both scripts;
the strict documentation build passes. These checks do not exercise proposed APIs.

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

The initial read-only spike exercised validated BWM and portable HC-3 reads
through `ibl-ai-agent-next` without copying datasets or changing its catalogs.
Source IDs, fidelity and provenance survive; warning-only signal access is refused.

The subsequent local commits `ibl-ai-agent-next:3cdb374` and
`ibl-datoviz:818e286` implement pinned BWM metadata access and the optional
`BwmSource` adapter. The reader owns integrity/source checks; the adapter retains
all rows and original source identities, uses explicit legacy coordinate
conventions and leaves signal validation gates unchanged. No production
`ibl-ai-agent` code or scientific dataset changed. A complete verified atlas frame
is still needed for the proposed bridge into the reviewed core payloads.

Validation: package suite 675 passed, one skip for the unconfigured optional
registered 10 µm asset root; sibling data package 343 passed, 13 opt-in local-data
skips. The ignored workbench experiment has 10 passing CPU/native ownership and
selection checks. Its facade is intentionally outside the package. This evidence
supports the data seam and resource contracts, not acceptance of a new GUI or
native scientific picking. Probe/prototype evidence remains under ignored
`build/agent-data-spike/` and `build/ibl-integration/`.

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
