# Interaction replay benchmark proposal

Status: initial opt-in implementation validated on Linux; manual review pending. Updated: 2026-10-20.

This document defines the IBL-side fixture and benchmark contract for repeatable interaction review. The generic input capture format, event semantics, player clocks, and native measurement hooks belong to Datoviz. Review app 2 exposes opt-in recording and playback when paired with the matching Datoviz development API; the immutable baseline remains unchanged.

The companion native proposal is `spec/scene/proposals/active/INPUT_RECORD_REPLAY.md` in Datoviz, committed at `8b2d955dfa997cee382536ef4233c02967be1c33` on the former `perf/panel-render-reuse` branch, now consolidated into `rc4/integration`. The [published native proposal](https://github.com/datoviz/datoviz/blob/8b2d955dfa997cee382536ef4233c02967be1c33/spec/scene/proposals/active/INPUT_RECORD_REPLAY.md) records the initial design; subsequent source-capture APIs are on the RC4 integration branch. The native proposal is authoritative for the shared design and is not part of the configured Datoviz baseline yet.

## Current commands and limits

With a separately configured Datoviz checkout providing `datoviz.input_trace` and `datoviz.input_replay`, record one interaction session and close its window:

```sh
just review 2 --ui-scale 1.5 --record-input build/input-traces/rotation/manifest.json
just review 2 --ui-scale 1.5 --replay-input build/input-traces/rotation/manifest.json --replay-mode paced --replay-report build/input-traces/paced.json
just review 2 --ui-scale 1.5 --replay-input build/input-traces/rotation/manifest.json --replay-mode controlled --replay-report build/input-traces/controlled.json
```

These flags require the candidate API and deliberately fail on a baseline that lacks it. They do not build Datoviz, change its revision, or update the dependency pin. Recording owns bounded in-memory observations until the loop returns; an overflow or unsupported interaction fails instead of publishing a complete artifact. Idle time through capture stop is retained. Start and finish with buttons and keys released; focus cancellation is explicit.

The initial player requires one GLFW host, the recorded native adapter platform and fixed host geometry. Raw GLFW wheel conventions are not silently transferred between operating systems. Paced playback retains the original offered wall schedule and reports delivery lateness. Controlled playback uses 120 Hz logical input/GUI ticks; its schedule is independent of rendering speed, but it does not freeze arbitrary scene animations or asynchronous workers. Idle paced playback waits on ordinary native deadlines rather than adding a polling tick. Reports distinguish scheduler-iteration duration, which includes waiting, from CPU frame and GPU time. Use the native profilers for the latter; these JSON reports do not manufacture those measurements.

IBL checks the app, preset, asset manifests, initial scientific state, UI configuration and available resolved layout before dispatch. Baseline and final slice readiness are checked outside the measured input phase. Camera snapshots include model rotation, arcball pan/zoom and the 3D panel camera view/projection. Fixed 2D slice panels have no camera controller.

With the native source-capture APIs, normal recording completion stops the input clock first, waits for current slice uploads on the owner thread, explicitly renders the existing scientific source view and takes a blocking RGBA8 capture. A successful source submission must advance its serial exactly once, slice identities and scientific state must remain stable, and a temporarily enabled hidden source is restored afterward. This works after the host window closes while app-owned source resources remain alive. The checkpoint is added under `fixture.terminal_checkpoint` and the trace is rehashed without changing its events or input duration. A sibling `<manifest stem>.terminal.png` is saved for inspection.

Replay captures the terminal source outside the timed input phase and writes a sibling `<report stem>.terminal.png` when `--replay-report` is supplied. `finalization.ibl_terminal_comparison` reports `match`, `mismatch` or `unavailable`. Comparison requires exact scientific state and exact RGBA8 dimensions/content; per-axis scheduling revisions are excluded from cross-run state equality, while scientific request content remains checked. Native submission serials identify evidence within each run and are not equality constraints across runs. A mismatch or failed required checkpoint exits unsuccessfully after preserving the replay report. A legacy trace without terminal evidence may still replay, but reports comparison unavailable. Older traces whose initial camera snapshot lacks the new navigation fields require a fresh recording.

This is a designated scientific source capture, not proof of what the host presented during interaction. Exact pixels are a strict same-renderer comparison policy, with no cross-GPU tolerance implied. Terminal equality alone does not establish identical intermediate input acceptance, asynchronous work, frame cadence or a throughput gain; `ibl_benchmark_verdict` therefore remains unavailable. Controlled replay uses a different pump schedule from live recording and can expose a different terminal camera state even when every host observation was delivered. Such differences remain failures, never automatic reference promotion or relaxed tolerance.

Native `536d78c7d` fixes button and wheel coordinates to follow the last ordered cursor observation. Earlier native builds could query a newer OS cursor position than the live GUI had accepted, changing the replay grab point. Re-record affected traces; literal replay does not repair an incorrect recorded position. A bounded real-mouse rotation now matches its live terminal scientific state and exact source pixels in both paced and controlled modes.

The native trace records mouse, raw fractional wheel, physical/layout key tokens, modifier masks and committed UTF-8 text. The separate Actions adapter currently supports strict discrete one-mouse interchange with proven coordinate equivalence; unsupported keyboard, wheel, host-state, interpolation or precision conversions fail explicitly. Clipboard-dependent actions, external shell operations, file dialogs, drag/drop and IME preedit remain outside this initial profile. Manual Linux interaction acceptance and macOS evidence remain separate from automated headless checks.

## Scope and ownership

The benchmark must cover the full hosted application path: GUI event pump, GUI layout and input routing, scene/controller updates, asynchronous preparation, native rendering, and presentation scheduling. A scene-only or offscreen rotation remains useful for renderer profiling, but it does not measure host input delay or GUI-pump coupling.

Datoviz owns W3C-aligned host observation recording/replay, the separate WebDriver Actions interchange adapter, scheduling clocks, cancellation at the generic player boundary, and opt-in native input-to-submit measurements. IBL owns named fixtures, deterministic scientific state, reset/setup, readiness barriers for its workers, scenario checkpoints, result interpretation, and the scenario catalog.

The IBL adapter maps a fixture and scenario identifier to an existing review app and the generic host replay entry point, before GUI arbitration. Injecting directly into a scene router/controller is a separately labelled profiling workload, not full-host replay. The portable trace must not depend on ImGui-specific event encodings or layout internals. This proposal creates no second renderer and does not alter the locked native baseline.

## Fixture identity and reset

Each run identifies the review app and preset, source assets and their content hashes, anatomy source/resolution, and relevant optional assets. Missing or mismatched assets fail preflight; the harness must not substitute another dataset or silently downgrade a scientific fixture.

The fixture fixes window logical dimensions, framebuffer dimensions, display scale/DPI, UI scale, sidebar visibility and width, panel rectangles, and GUI layout. Record the resolved values in the result so the same logical workload can be reconstructed on another host. A host that cannot provide the declared fixture is unsupported for that comparison.

Reset state includes the initial camera pose and controller mode, cursor, mapping, selected region identities, slice positions, layer visibility, and anatomy opacity. Record exact identities and asset hashes rather than relying on labels or current application defaults. Reset must create a fresh equivalent app state and ensure no prior pointer is held and no worker result remains eligible for display.

Warmup occurs after fixture reset and before the measured segment. Warmup is a declared neutral readiness/render phase, not an unreported copy of the measured interaction; the measured trace starts at its first recorded action. Each repeat resets to the same fixture and uses the same action artifact.

Fixture preflight records and checks these resolved values before any timing sample is accepted:

- Review app, preset, scenario identifier and source trace hash; native and IBL revisions/build hashes are recorded provenance, not equality constraints across optimization comparisons.
- Logical window size, framebuffer size, content scale, UI scale, and display identity.
- Sidebar state and width, each panel rectangle, GUI layout identity, and relevant viewport bounds.
- Camera/controller state, cursor, mapping, selection IDs, slice indices, layer visibility, and opacity.
- Source asset identifiers and hashes, anatomy source and resolution, and optional asset availability.
- Worker and native resource state after reset, including the absence of in-flight prior revisions.

A mismatch in declared fixture compatibility fields makes the run incompatible with the requested comparison. Native/IBL revisions and library hashes are expected to differ when comparing builds. The report retains actual resolved values so the reason is reviewable.

## Run sequence

Each IBL run follows the same host-level sequence:

1. Resolve the named review app, preset, assets, layout, and initial scientific state; reject incompatibilities.
2. Reset the app and verify that prior actions, workers, and displayed revisions cannot affect this run.
3. Perform neutral warmup and wait for declared baseline readiness before opening the measurement window.
4. Start the selected schedule and collect its input, GUI-pump, scene-acceptance, and native timing observations.
5. In controlled mode, pause logical advancement only at declared readiness barriers; in paced mode, observe checkpoints without delaying scheduled input and report completion/settle intervals separately.
6. Complete the recorded terminal input state and verify the final camera and scientific state; an interrupted gesture uses explicit cancellation and is not silently converted into a successful release.
7. Close the app cleanly and write the trace identity, fixture resolution, checkpoints, raw samples, and verdict.

## Workload schedules

One authoritative trace preserves every original observed at the declared host ingress, including GUI-consumed input. Its W3C-aligned observation vocabulary and native fidelity envelope are defined only by the native proposal. WebDriver Actions is a separate import/export format, with explicit representability checks; it is not the canonical recording. Derived gestures and viewport forwarding are diagnostic outputs, never duplicate replay inputs.

The **original schedule** experiment replays the recorded event timing and reports host-input lateness and backlog against that source schedule. It characterizes the observed interaction cadence and is sensitive to the host event pump. It does not guarantee the same accepted scene updates across machines.

The **controlled schedule** experiment uses a declared fixed logical GUI-pump cadence/time and input batch boundaries, independent of achieved render FPS. It measures completed-work costs against the same fixture, with readiness barriers at specified boundaries. Record the pump policy, accepted scene inputs and state checkpoints; divergence makes a strict paired-work comparison invalid. Matching final state alone is insufficient to prove identical accepted input or intermediate work, and asynchronous completed/cancelled work counts remain separately reported.

Record all authoritative host events. If a lower-rate or otherwise decimated trace is useful, derive a separate artifact with a distinct workload identifier and explicit transformation metadata. It is a different workload, never an equivalent replay of the original trace.

Both experiments report the schedule mode, source trace hash, resolved fixture identity, requested cadence, actual GUI-pump intervals, input offered/accepted counts, batch boundaries, and per-phase event attribution. Missing events, unsupported actions, or lossy import must reject the run or label it invalid, not produce a successful timing result.

The trace and run metadata remain separate artifacts: the trace preserves host observations, while fixture metadata describes the IBL state and schedule parameters. The adapter records the source trace hash and derived-workload identifier with every result, so an edited or decimated workload cannot inherit the original trace's identity.

## Asynchronous readiness and checkpoints

The adapter declares readiness checkpoints around operations whose output can arrive asynchronously, such as slice changes, mapping changes, and selection updates. A checkpoint passes only when the expected request identity and revision have been accepted and uploaded on the owning thread, and the presented-source generation or designated capture confirms that identity. A worker completion or upload alone is not evidence of a displayed result. Only controlled mode may wait at these barriers; paced mode observes and reports when they complete without blocking later scheduled input.

The fixture must verify that no stale revision, missing slice, or partial update is displayed at a checkpoint. Use the existing latest-wins semantics; readiness must not force old work to display. A timeout or worker error fails and labels the run. Never replace a wait with a guessed sleep and count it as successful readiness.

The native generation/progress signal or designated rendered checkpoint that proves this association is an implementation prerequisite. The current public API is not assumed to expose that proof already, especially for a nonblocking viewport promoting an older completed image.

Capture checkpoint state for camera/controller pose, cursor and selected region IDs, slice request identities and revisions, and accepted planes. Compare retained state exactly where stable; use declared pixel or numeric tolerances only for values that can vary with backend or floating-point behavior. Record a checkpoint failure separately from timing statistics.

Checkpoints name the expected scientific operation and its expected state, such as an AP slice revision, a committed region ID, or a cleared selection. A checkpoint may inspect captured state and a designated image region; it must not change the state it is measuring.

## Results and interpretation

Keep native CPU timing, GPU timing, and host/presentation observations in separate fields. CPU submit timing and GPU execution may overlap and must not be summed as though they were serial. An input-to-submit measure is not input-to-photon latency; this workload does not claim scanout timing.

For each phase report event counts and phase duration, accepted state/checkpoint identity, GUI-pump cadence, and available input freshness samples. Include p50, p95, p99, and maximum for timing distributions when the sample count supports them; preserve raw samples and mark unavailable metrics explicitly. State whether render validation or profiling instrumentation was active.

Use fresh equivalent fixtures and repeated paired comparisons on the same host, with an ABBA or randomized order to reduce drift. Primary performance runs use Release builds with Vulkan validation disabled; separate correctness runs retain validation. Datoviz semantic validation remains active. CPU and GPU profiles belong to a separate diagnostic cohort because profiler overhead changes the measured workload; pair them with unprofiled runs and report the difference rather than mixing their samples.

The result should distinguish these counts and outcomes:

- Host actions recorded, actions loaded, actions offered to the application, and scene events accepted.
- Frames pumped and rendered in each declared phase, with actual cadence and dropped or coalesced work.
- Readiness requests, accepted uploaded revisions, checkpoint outcomes, and timeout/error classifications.
- Timing sample count and available freshness, CPU, GPU, and presentation-proxy distributions.
- Fixture compatibility, trace integrity, profiler/validation state, and final run validity.

An incomplete sample set, a failed checkpoint, or a trace-integrity failure is not a performance pass. Keep correctness verdicts and performance comparisons separate.

Private Xvfb startup or synthetic headless throughput is useful for smoke checks and code-path coverage. It does not stand in for desktop GUI cadence, display presentation, or physical interaction latency. Report the host, display mode, GPU/backend, application/native revisions, source assets, and resolved layout with each comparison.

## Scenario catalog

Start with a small catalog tied to existing review fixtures: a single 3-D arcball drag; a linked navigator rotation while slices remain visible; a slice scroll followed by readiness; and region selection followed by readiness and deselection. Each scenario defines its initial state, trace, schedule mode, checkpoints, and expected controller/scientific state.

The first catalog should exercise both app 1 and app 2 through the same generic player boundary. It should include a neutral no-input interval for idle cadence and a release/checkpoint phase after every drag. Scenario setup chooses a supported preset explicitly and records its resolved assets; it must not silently switch to a smaller fixture when an optional source is missing.

The current `build/review2-headless/rotation_profile.py` is a renderer/profile harness that synthesizes drag events from its frame callback. It is useful prior art for router injection and source-only profiling, but it is not an authoritative manual trace and does not prove identical host event scheduling. Retain it as a profiling adapter until a generic player and IBL fixture adapter exist.

## Implementation gates

1. Datoviz validates shared host ingress and replay-safe GUI state/frame preparation while preserving live input behavior and suppressing OS polling during replay.
2. Datoviz lands the owned recorder, trace validator/player, cancellation and schedule policies, then exposes lifecycle/progress hooks without importing IBL concepts.
3. IBL adds fixture reset, layout/state preflight, slice readiness checkpoints, result metadata and a small scenario catalog through the generic host player. Controlled scenarios require the declared logical GUI-pump contract.
4. Datoviz adds WebDriver Actions interchange with strict representability/loss reporting; IBL references that adapter rather than implementing a second codec.
5. Paired native and IBL evidence confirms event accounting, state checkpoints, cancellation cleanup, timing overhead and same-host repeatability before any release claim.

## Acceptance evidence

Implementation acceptance requires the shared contract and IBL adapter to demonstrate these invariants:

- Replaying one trace after equivalent fixture resets preserves the declared offered order. Controlled paired-work scenarios require matching accepted input and expected camera/controller state; paced mode reports state divergence explicitly rather than promising frame-independent outcomes.
- Both review apps receive actions through their normal hosted GUI and scene paths, with the target viewport and resolved layout recorded.
- Every source action is accounted for as loaded, offered, rejected, or accepted; no silent trace loss is permitted.
- Controlled runs report their pump cadence and batching, and do not claim equal accepted work when host scheduling changed it.
- Controlled slice/selection barriers identify the accepted revision, matching displayed/captured source generation and expected scientific state before the next phase starts; paced observations never delay offered input.
- Cancellation clears held input without generating clicks or text commands, prevents later actions, removes adapter subscriptions, and allows app workers and native resources to close normally. Missing recorded releases are not silently repaired.
- Invalid fixtures, unsupported actions, missing checkpoints, and timeouts produce explicit invalid-run outcomes with no performance verdict.
- Paired unprofiled runs preserve raw samples and compare like-for-like host, display, asset, layout, and workload identities.
- Profiled diagnostic runs are separately labeled and include a paired unprofiled reference for estimating observer overhead.

This proposal changes no CI performance gates, dependency pins, release baselines, or public APIs. Final semantics and the shared native contract require user review before implementation begins.
