# Getting started

## Install a development checkout

The project is an unreleased source snapshot. Its committed `uv.lock` and `[tool.uv.sources]`
entries pin the exact Datoviz and `ibl-anatomy` Git revisions currently under test; the dependency
ranges in package metadata are provisional bounds for a later distributable release. From the
repository root:

```bash
uv sync --group dev --locked
```

When developing the three adjacent repositories together, point Python at the local sources and
use the Datoviz environment that owns the built native library:

```bash
export PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz
../../Viz/datoviz/.venv/bin/python -m pytest
```

## Materialize the real atlas

The D070 asset-set lock identifies immutable remote bytes. Materialization verifies the complete
mesh graph and region catalog before making them available to a viewer:

```bash
PYTHONPATH=../ibl-anatomy/src python - <<'PY'
from ibl_anatomy import bundled_asset_set, materialize_asset_set

materialize_asset_set(bundled_asset_set(), "build/atlas-d070")
PY
```

The registered 10 um projection graph has its own bundled lock. Materialize it through
`ibl-anatomy` so every transitive resource is checked before Datoviz sees it:

```bash
PYTHONPATH=../ibl-anatomy/src python - <<'PY'
from ibl_anatomy import bundled_registered_asset_set, materialize_registered_asset_set

materialize_registered_asset_set(
    bundled_registered_asset_set(), "build/atlas-registered-10um"
)
PY
```

The lock names an immutable Ephys Atlas deployment, but that deployment layout is not the
consumer API. Python consumers use the verified result/root through `ibl-anatomy`. Direct fetches
from a different browser origin currently require an approved CORS policy or same-origin proxy.

## Open the atlas browser

Start with the isolated 3-D surface baseline. It contains one opaque mesh, one perspective camera,
and one arcball in a direct native window—no ImGui, ontology, hover query, volume, or slices:

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
uv run python examples/atlas_spike.py \
  ../ibl-anatomy/build/d070-published/mesh-pack
```

Then test the ontology and linked-selection layer independently by adding the catalog:

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
uv run python examples/atlas_spike.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  --regions ../ibl-anatomy/build/d070-published/regions.json
```

This second rung also exposes an **Explode regions** slider. It follows the shared mesh contract:
at amount `t`, every component is translated by `t * (component centroid - whole-brain centroid)`.
Pass `--explode 0.5` to start at a nonzero value. The baseline without `--regions` remains unchanged.

The full asset-set entry point follows:

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen
```

The left dock contains the parent-closed ontology tree, mapping selector, filters, official color
swatches, and linked selection. Drag the main view to orbit and click a surface region to select it.

For the four-panel navigator, materialize the separate 50 um volume pack and provide both immutable
pack roots:

```bash
python examples/linked_atlas_navigator.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  ../ibl-anatomy/build/allen-ccf-2017-50um \
  --ui-scale 1.5
```

The atlas dock and visualization area resize as sibling panels. Hover a slice to preview its mapped
region, and click to move the shared AP/ML/DV cursor without changing selection. Use the prominent
Select cursor region button to commit that location, or select directly from the ontology tree or
3-D surface. Left-drag over the 3-D quadrant to orbit it. Over a slice, the wheel accumulates
fractional input and steps two sections per standard notch; Shift+wheel steps ten. The bracket/Page
Up/Page Down keys provide single-section steps. Ctrl+wheel zooms a slice, and double-click resets
its zoom. Separate controls toggle the anatomy, annotation, and mapping-aware vector boundary
layers and adjust annotation, boundary, or volume opacity. The template is linearly sampled, while
the discrete labels retain nearest-neighbour sampling and transparent atlas margins reveal the
neutral panel background.

The same committed mapped identity drives the official slice colors, 3-D cursor, surface highlight,
ontology tree, and any attached probe or regional tables. The scalar anatomical template is
volume-rendered in the 3-D panel on native Datoviz; volume rendering is not currently claimed for
the WebGPU export.

The slice grid and dense 3-D volume are independent. When a 10 um intensity block pack and the
exact registered anatomy pack have been materialized, keep the 50 um pack as the bounded dense
volume and opt into 10 um slices explicitly:

```bash
python examples/linked_atlas_navigator.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  ../ibl-anatomy/build/allen-ccf-2017-50um \
  --slice-resolution registered \
  --slice-intensity-pack ../ibl-anatomy/build/allen-ccf-2017-10um-intensity \
  --registered-asset-root build/atlas-registered-10um
```

In this mode the authoritative cursor lives in the 10 um grid and is transformed through ML/AP/DV
world micrometres to the D070 surface and 50 um volume. Anatomy blocks and exact signed Allen
geometry are decoded lazily, cached within explicit bounds, and prepared through a latest-wins
worker queue; only completed current slices mutate Datoviz state on the view owner thread. No
complete 10 um volume is uploaded to the GPU.

For a non-interactive smoke render, add an output path:

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/bwm_probe.py \
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
