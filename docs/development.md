# Development and documentation

Start with [the audit follow up and implementation handoff](NEXT_STEPS.md) for the current correctness fixes, staged refactoring tasks, and validation requirements. The [real-data interactive example roadmap](REAL_DATA_EXAMPLE_ROADMAP.md) records the capability ladder and live review process. The [earlier release-hardening handoff](RELEASE_HARDENING_HANDOFF.md) records the original review and completed hardening work.

## Checks

```bash
just setup-tests /path/to/datoviz  # once, after building Datoviz separately
just lint
just test
```

The [contributor workflow](getting-started.md#contributor-workflow) manages fixtures and the local
Datoviz pairing without an adjacent anatomy checkout. Use `just setup /path/to/datoviz` to prepare
real review data, then `just review` for interactive review. `just doctor` checks the remembered pairing;
`just test tests/test_probe_replacement.py -q` forwards pytest arguments unchanged. Local commands
report and warn about Datoviz revision differences while using the configured checkout. For pinned
baseline validation use `just doctor --strict`, `just test --strict`, and `just review all --strict`. Ordinary pytest also accepts
`IBL_ANATOMY_FIXTURE_ROOT`; CI retains its pinned adjacent fixture checkout.

## Optional i3 window placement

While the reviewer is using this computer, run automated GUI checks on an isolated
display, for example `xvfb-run -a just test --strict` on Linux. Run browser checks
headlessly. Window placement rules alone do not prevent windows appearing on the
working desktop. Keep GPU diagnostics bounded because they still share the GPU.

On X11/i3, a Datoviz build supporting `DVZ_WINDOW_INSTANCE` lets window rules distinguish
manual launches from automation. Interactive `just review` uses instance `datoviz`;
`just test`, bounded `just review --frames N` runs, and benchmarks use `datoviz-automated`.
Both have class `datoviz`. Match the class and instance together in separate i3 `for_window`
rules to send them to your preferred outputs. The helper sets this only for its child process,
so test runs do not change subsequent manual launches. Older native builds ignore the override.

## Build the documentation

Install the exact documentation tool versions without changing the project lock, then build in
strict mode:

```bash
just docs
```

Generated HTML is written to ignored `site/`. Run `just` to list all recipes.
Agent contributors should also read the repository-root `AGENTS.md` before editing.

## Direct gallery and benchmark tools

The `just` test/review recipes configure only their child processes. Before running the direct
commands below, activate the [manual Python/native pairing](getting-started.md#python-and-native-library-pairing)
and Datoviz runtime environment in your shell. Full `just setup` prepares the assets these commands
use; `setup-tests` prepares only fixtures.

## Regenerate the gallery

The manifest at `docs/gallery/manifest.json` is the source of truth for example commands,
capability labels, and canonical documentation images. Generate every screenshot and benchmark
report into the ignored build tree:

```bash
uv run --frozen python tools/build_gallery.py \
  --asset-root build/atlas-d070
```

Use `--example bwm-probe` to run one entry or `--dry-run` to inspect commands. After reviewing the
pixels, update only the entries that declare a canonical image:

```bash
uv run --frozen python tools/build_gallery.py \
  --asset-root build/atlas-d070 \
  --volume-root build/allen-ccf-2017-50um \
  --fixture-root build/review/anatomy/tests/fixtures \
  --example bwm-probe --publish
```

`--publish` is deliberately explicit. Ordinary runs never modify tracked documentation assets.
GPU screenshots and benchmark timings are host-dependent; scientific identity remains fixed by
the atlas asset-set lock and the BWM fixture provenance.

## Check retained regional updates

The linked mesh/tree/table path is designed to update regional values without rebuilding the atlas
catalog or scanning every region for every mesh update. Exercise it against a materialized asset
set with:

```bash
uv run --frozen python tools/benchmark_region_updates.py \
  build/atlas-d070 \
  --mapping allen --iterations 20 --json build/region-update-benchmark.json
```

The report is build-local because timings depend on the machine. The region and vertex counts make
the measured workload explicit.

## Compare hover performance across GPUs

After `just setup`, use the remembered Datoviz checkout and runtime without exporting paths into your shell:

```bash
xvfb-run -a uv run --frozen tools/review.py benchmark -- \
  --scenarios gui_idle gui_pointer_hover gui_pointer_drag hover_emphasis_update \
  --repeats 3 --warmup 30 --frames 120 \
  --width 900 --height 720 --json build/hover-900.json
```

Repeat with `--width 1800 --height 1440` and a distinct report name. Preserve the same asset, source commits, native library SHA256, frame count and warmup when comparing drivers or GPUs. The Xvfb command isolates automated windows from the working desktop.

The report records NVIDIA driver diagnostics, the Vulkan device inventory, Vulkan driver-selection environment, native query phases, and Python emphasis/color-setter distributions. Inventory describes available devices, not the device selected by a running Datoviz view. On a Linux host with multiple drivers, choose the intended ICD explicitly for a controlled comparison using `VK_DRIVER_FILES=/path/to/driver_icd.json` (or `VK_ICD_FILENAMES` with older loaders), and verify `vulkaninfo --summary` lists only the intended GPU before running. Confirm `nvidia-smi` succeeds before collecting NVIDIA results. Driver mismatch output is retained in the report instead of being silently treated as missing hardware.

The report also records sparse interaction-state setter calls, changed-word counts and requested payload bytes (four bytes per word). These are API payload measurements; native emitted-upload checks establish GPU transfer size. After warmup, hover and selection should upload no dense vertex colors and cause no static query-geometry refreshes.

For deeper Python attribution, add `--profile-emphasis` to a separate diagnostic run. It records function call counts, self time and cumulative time for measured emphasis updates, including ontology expansion and presentation-state updates. Profiling adds overhead: compare ordinary timings with profiling disabled, and do not sum nested cumulative times. Tree relationships and presentation-to-region mappings are cached; report cold startup separately from warmed steady-state timings.

## Viewer ownership and internal components

`AtlasViewer` is the public application owner for both `layout="3d"` and
`layout="linked"`. Layout selection does not change its concrete class. Prepared
scientific payloads enter through `add_points`, `add_paths`, `add_recording`, and
`add_region_values`; returned handles and public controllers are the application API.
Caller-owned rendering primitives live in `ibl_datoviz.components`.

The viewer coordinates mapping/selection transactions and owns the scene lifetime.
Its internal components have distinct responsibilities:

| Component | Owned state and work |
| --- | --- |
| `LinkedSlices` | Slice sources/composers, cursor, accepted requests, visuals, workers, and input subscription |
| `SurfacePresentation` | Authored styles, applied surface masks/cache, and typed transaction snapshots/recovery |
| `ProbePresentation` | Diagnostic probe payloads, colors, pending candidates, and upload recovery |
| `ViewerLayout` | Host/view/GUI assembly and docking; native handles remain owned by the viewer |

Mapping and selection updates coordinate anatomy and slices before publishing events.
Rejected work advances slice revisions during recovery, so old worker completions
cannot become current. Rollback restores native data as well as host state; a failed
rollback closes the viewer. Snapshot color payloads retain immutable owned storage.

Native GUI/input callbacks may request shutdown but must not release their resources
until dispatch scopes unwind. Close guards run before diagnostic visuals are released;
slice workers join and input subscriptions detach before app/scene destruction.
External source caches remain caller-owned. Public mutations require the owner thread
and cannot run reentrantly from selection or cursor notifications.

Application-specific cursor/volume hooks run after the scientific update succeeds.
Restoration paths use internal setters deliberately when repeating a committed hook
would recurse. Review fixture resets use public controllers, so application policies
also apply during replay. Change these boundaries with failure-injection and lifetime
checks, not only successful startup tests.
