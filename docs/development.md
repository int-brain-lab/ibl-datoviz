# Development and documentation

## Checks

```bash
ruff check .
pytest
```

The adjacent-source command in [Getting started](getting-started.md) is useful while Datoviz and
`ibl-atlas-assets` are changing together.

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
  --asset-root ../ibl-atlas-assets/build/d070-published
```

Use `--example bwm-probe` to run one entry or `--dry-run` to inspect commands. After reviewing the
pixels, update only the entries that declare a canonical image:

```bash
python tools/build_gallery.py \
  --asset-root ../ibl-atlas-assets/build/d070-published \
  --example bwm-probe --publish
```

`--publish` is deliberately explicit. Ordinary runs never modify tracked documentation assets.
GPU screenshots and benchmark timings are host-dependent; scientific identity remains fixed by
the atlas asset-set lock and the BWM fixture provenance.
