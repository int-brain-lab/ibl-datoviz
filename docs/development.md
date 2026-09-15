# Development and documentation

## Checks

```bash
ruff check .
pytest
```

The adjacent-source command in [Getting started](getting-started.md) is useful while Datoviz and
`ibl-anatomy` are changing together.

## Build the documentation

Install the exact documentation tool versions without changing the project lock, then build in
strict mode:

```bash
uv pip install --requirements docs/requirements.txt
mkdocs build --strict
```

Generated HTML is written to ignored `site/`.

## Regenerate the gallery

The manifest at `docs/gallery/manifest.json` is the source of truth for example commands,
capability labels, and canonical documentation images. Generate every screenshot and benchmark
report into the ignored build tree:

```bash
python tools/build_gallery.py \
  --asset-root ../ibl-anatomy/build/d070-published
```

Use `--example bwm-probe` to run one entry or `--dry-run` to inspect commands. After reviewing the
pixels, update only the entries that declare a canonical image:

```bash
python tools/build_gallery.py \
  --asset-root ../ibl-anatomy/build/d070-published \
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
python tools/benchmark_region_updates.py \
  ../ibl-anatomy/build/d070-published \
  --mapping allen --iterations 20 --json build/region-update-benchmark.json
```

The report is build-local because timings depend on the machine. The region and vertex counts make
the measured workload explicit.
