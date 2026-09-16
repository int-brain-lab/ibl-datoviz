# ibl-datoviz

Native Python visualization for International Brain Laboratory atlas data, built on Datoviz
v0.4.

**[Documentation](docs/index.md) · [Getting started](docs/getting-started.md) ·
[Gallery](docs/gallery/index.md) · [API reference](docs/api/index.md)**

![Mapping-aware regional activity in the Allen atlas](docs/images/bwm-region-activity.png)

`ibl-datoviz` combines verified Allen CCF 2017 assets from `ibl-anatomy` with interactive 3-D
surfaces, orthogonal anatomical slices, ontology navigation, probe sites, regional values, and
linked selection.

> [!NOTE]
> Version 0.2 is under active development and intentionally breaks the historical 0.1 API while
> the Datoviz v0.4 integration is validated.

## Features

- Allen, Beryl, and Cosmos presentations backed by a versioned region catalog.
- A native D070 surface viewer with arcball navigation, face picking, region selection, and
  component explosion.
- A four-panel navigator linking three orthogonal slices, a 3-D surface and volume, an AP/ML/DV
  cursor, and the ontology tree.
- Scalar-colored probe sites and regional values with linked, searchable tables.
- Mapping-aware slice boundaries and optional registered 10 um slices over a bounded 50 um 3-D
  volume.
- Native offscreen rendering and reproducible gallery and benchmark commands.

The package owns viewer composition and display behavior. `ibl-anatomy` owns the versioned asset
and decoding contracts; scientific atlas computations and coordinate-to-label annotation remain
outside this package.

## Install a development checkout

The branch pins the Datoviz and `ibl-anatomy` source revisions used during development. From the
repository root:

```bash
uv sync --group dev
```

When developing all three repositories from adjacent checkouts, point Python at their sources:

```bash
export PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz
uv run pytest
```

See [Getting started](docs/getting-started.md) for asset materialization and local native-library
setup.

## Open an atlas

Materialize the immutable D070 asset set with `ibl-anatomy`:

```bash
PYTHONPATH=../ibl-anatomy/src python - <<'PY'
from ibl_anatomy import bundled_asset_set, materialize_asset_set

materialize_asset_set(bundled_asset_set(), "build/atlas-d070")
PY
```

Then open the surface viewer:

```bash
PYTHONPATH=.:../ibl-anatomy/src \
uv run python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen
```

The left dock provides ontology search, mapping controls, official color swatches, and linked
selection. Drag the atlas to orbit it and click a surface region to select it.

The equivalent minimal Python entry point is:

```python
from ibl_datoviz import AtlasViewer

with AtlasViewer.from_asset_set("build/atlas-d070", mapping="beryl") as viewer:
    viewer.show(title="Allen mouse brain atlas")
```

## Open the linked navigator

With the D070 mesh and 50 um annotation/template volume pack materialized:

```bash
PYTHONPATH=.:../ibl-anatomy/src \
uv run python examples/linked_atlas_navigator.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  ../ibl-anatomy/build/allen-ccf-2017-50um \
  --ui-scale 1.5
```

The navigator shares one AP/ML/DV cursor and one region selection across the three slices, 3-D
view, volume, and ontology. Registered 10 um slices are supported without uploading a complete
10 um volume; the detailed command and interaction controls are documented in
[Getting started](docs/getting-started.md#open-the-atlas-browser).

## Real-data examples

The repository includes a compact, provenance-recorded fixture derived from one BWM ephys
insertion. It demonstrates both probe-site and mapping-aware regional views:

```bash
PYTHONPATH=.:../ibl-anatomy/src \
uv run python examples/bwm_probe.py build/atlas-d070 --mapping beryl

PYTHONPATH=.:../ibl-anatomy/src \
uv run python examples/bwm_region_activity.py build/atlas-d070 --mapping beryl
```

These examples keep scientific derivation explicit: renderer payloads contain stable site or
region identities and display values, while ontology labels and mappings come from the verified
catalog. See the [gallery](docs/gallery/index.md) for screenshots, capability labels, and more
commands.

## Development

Run the repository checks with:

```bash
uv run ruff check .
uv run pytest
uv run mkdocs build --strict
```

Performance reports are host-dependent and remain build-local. The current evidence and
reproduction commands are recorded in:

- [Datoviz v0.4 atlas findings](docs/V04_ATLAS_SPIKE_FINDINGS.md)
- [Real D070 checkpoint](docs/REAL_D070_CHECKPOINT.md)
- [3-D feature benchmark](docs/ATLAS_3D_BENCHMARK_FINDINGS.md)
