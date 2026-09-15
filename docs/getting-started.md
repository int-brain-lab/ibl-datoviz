# Getting started

## Install a development checkout

The project currently pins release-candidate dependencies. From the repository root:

```bash
uv sync --group dev
```

When developing the three adjacent repositories together, point Python at the local sources and
use the Datoviz environment that owns the built native library:

```bash
export PYTHONPATH=.:../ibl-atlas-assets/src:../../Viz/datoviz
../../Viz/datoviz/.venv/bin/python -m pytest
```

## Materialize the real atlas

The D070 asset-set lock identifies immutable remote bytes. Materialization verifies the complete
mesh graph and region catalog before making them available to a viewer:

```bash
PYTHONPATH=../ibl-atlas-assets/src python - <<'PY'
from ibl_atlas_assets import bundled_asset_set, materialize_asset_set

materialize_asset_set(bundled_asset_set(), "build/atlas-d070")
PY
```

## Open the atlas browser

```bash
PYTHONPATH=.:../ibl-atlas-assets/src python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen
```

The left dock contains the parent-closed ontology tree, mapping selector, filters, official color
swatches, and linked selection. Drag the main view to orbit and click a surface region to select it.

For a non-interactive smoke render, add an output path:

```bash
PYTHONPATH=.:../ibl-atlas-assets/src python examples/bwm_probe.py \
  build/atlas-d070 --mapping beryl --offscreen build/bwm-probe.png
```

## Minimal Python use

```python
from ibl_datoviz import AtlasViewer

with AtlasViewer.from_asset_set("build/atlas-d070", mapping="beryl") as viewer:
    viewer.show(title="Allen mouse brain atlas")
```

See the [API overview](api/index.md) for ownership rules and the [gallery](gallery/index.md) for
complete examples.
