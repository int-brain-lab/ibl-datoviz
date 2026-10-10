# ibl-datoviz

Native Python visualization for International Brain Laboratory atlas data, built on Datoviz
v0.4.

**[Documentation](docs/index.md) · [Getting started](docs/getting-started.md) ·
[Gallery](docs/gallery/index.md) · [API reference](docs/api/index.md)**

`ibl-datoviz` combines verified Allen CCF 2017 assets from `ibl-anatomy` with interactive 3-D
surfaces, orthogonal anatomical slices, ontology navigation, probe sites, regional values, and
linked selection. The package owns viewer composition and display behavior. `ibl-anatomy` owns the
versioned asset and decoding contracts; scientific atlas computations and coordinate-to-label
annotation remain outside this package.

> [!NOTE]
> Version 0.2 is under active development and intentionally breaks the historical 0.1 API while
> the Datoviz v0.4 integration is validated.

## Try it locally

The contributor workflow is supported on macOS and Linux. Install [`uv`](https://docs.astral.sh/uv/)
and [`just`](https://just.systems/), then clone and build Datoviz separately using the source
checkout you want to review. Datoviz also needs a working Vulkan runtime (MoltenVK on macOS).
This project does not build or switch the Datoviz checkout for you.

From the root of this repository, prepare the local pairing and review data once:

```bash
just setup "$HOME/GIT/Viz/datoviz"
```

`just setup` reports the local and pinned Datoviz revisions and checks loaded Python/native paths, then
fetches the pinned test fixtures and prepares the verified D070 surface and 50 um slice assets.
The initial setup needs network access; later runs reuse the verified cache. For tests without the larger
real-data downloads, use `just setup-tests "$HOME/GIT/Viz/datoviz"` instead.

Then run tests or open the interactive examples:

```bash
just test
just review picking
just review
```

Local commands warn and continue if the Datoviz revision differs from the pin. Use `just doctor --strict`,
`just test --strict`, or `just review all --strict` to require the tested baseline.

`just review` opens six examples in sequence; close a window to continue. Choose `surface`,
`mapping`, `picking`, `probe`, `firing-rate`, or `slices` to open one. `just doctor` checks which
Datoviz Python module and native library the workflow will load. See the [contributor guide](docs/getting-started.md)
for setup details, troubleshooting, and direct `uv` commands. Agents should read
[AGENTS.md](AGENTS.md) before changing the repository.

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

## Python use and additional examples

`just setup` prepares the data for the examples below. The recipes configure the native environment
for their child processes; they do not change your shell. Before running Python or examples directly,
follow the [manual Python/native pairing](docs/getting-started.md#python-and-native-library-pairing)
steps. A minimal surface viewer is:

```python
from ibl_datoviz import AtlasViewer

with AtlasViewer.from_asset_set("build/atlas-d070", mapping="beryl") as viewer:
    viewer.show(title="Allen mouse brain atlas")
```

## Open the linked navigator

After full setup and manual runtime pairing, open the complete 50 um navigator:

```bash
uv run --frozen python examples/linked_atlas_navigator.py \
  build/atlas-d070/mesh-pack \
  build/allen-ccf-2017-50um \
  --ui-scale 1.5
```

The navigator shares one AP/ML/DV cursor and one region selection across three slices, the 3-D
view, volume, and ontology. Complete compatible registered sources support 10 um slices without
uploading a complete 10 um volume. The bundled verified publication contains sampled geometry only
and cannot start unrestricted registered navigation. See [Getting started](docs/getting-started.md#open-the-atlas-browser)
for the supported preview and complete-source routes.

## Real-data examples

The repository includes a compact, provenance-recorded fixture derived from one BWM ephys
insertion. After manual runtime pairing, these examples demonstrate probe-site and mapping-aware
regional views:

```bash
uv run --frozen python examples/bwm_probe.py build/atlas-d070 --mapping beryl
uv run --frozen python examples/bwm_region_activity.py build/atlas-d070 --mapping beryl
```

Renderer payloads contain stable site or region identities and display values, while ontology
labels and mappings come from the verified catalog. See the [gallery](docs/gallery/index.md) for
screenshots, capability labels, and more examples. Run `just lint` for Ruff and `just docs` for a
strict documentation build. Performance reports and reproduction commands are listed in the
[benchmark findings](docs/ATLAS_3D_BENCHMARK_FINDINGS.md) and [slice benchmark](docs/ATLAS_2D_BENCHMARK_FINDINGS.md).
