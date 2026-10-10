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
