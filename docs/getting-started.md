# Getting started

## Shared reference envelope

Regional displays use the original D070 Allen geometry. A whole-brain context
shell uses the companion source-native Allen root asset from `ibl-anatomy`,
without additional smoothing. Prepare it explicitly, then read it offline:

```python
from ibl_anatomy import materialize_surface_asset
from ibl_datoviz import AtlasEnvelope, AtlasMesh

materialize_surface_asset("build/allen-root")  # new destination; source hash checked
atlas = AtlasMesh.from_pack("build/atlas-d070/mesh-pack")
envelope = AtlasEnvelope.from_source("build/allen-root", atlas)
```

Upload `envelope.positions`, `envelope.normals` and `envelope.indices` to a
separate mesh visual. The envelope shares the regional mesh's exact display
transform; it does not supply regional picking identities or change the atlas's
framing. Its source coordinates are already converted to world µm before display
normalization. Different reference spaces fail explicitly. The companion source
has six open boundary edges and is for display, not voxel-label or closed-solid
computations. `from_world_arrays()` also accepts explicitly prepared
`annotation-boundary` geometry for diagnostic tools. No default fallback or
runtime geometry smoothing is performed.

## Contributor workflow

Ongoing v0.4 implementation stays on `feature/datoviz-v04`; see `AGENTS.md`.

Python 3.11 or newer is required. CI covers Python 3.11 and 3.13.

Datoviz is a separate prerequisite: clone and build your chosen local checkout and establish its
working Vulkan/MoltenVK environment. This package does not build or change that native checkout.
Install `just` and `uv` on your machine. On macOS, `brew install just uv` installs both; on
Linux, use their official [just installation instructions](https://github.com/casey/just#installation)
and [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
The same recipes work on macOS and Linux. Once Datoviz works, run from a fresh `ibl-datoviz` checkout:

```bash
just setup /path/to/datoviz
just test
just review
```

`just setup` installs the locked development dependencies, records your Datoviz path in ignored
`build/review/config.json`, discovers its native build (`libdatoviz.dylib` on macOS, `libdatoviz.so`
on Linux), and checks the actual imported Python module
and loaded library against the configured checkout. If the checkout has `.envrc` and `direnv` is installed,
it uses `direnv exec` automatically; allow/configure that environment while setting up Datoviz.
Otherwise it inherits your already working runtime environment. For these recipes, no package-side
`PYTHONPATH`, `DATOVIZ_LIBRARY`, adjacent anatomy checkout, or Fractal connection is required.

Setup also fetches the pinned anatomy builders and synthetic fixtures into `build/review/anatomy`,
materializes verified D070 assets in `build/atlas-d070`, prepares the hash-verified companion Allen root envelope in `build/allen-root` and twelve major-structure context meshes in `build/allen-major-context`,
and downloads the two hash-pinned Allen
50 um NRRDs to build `build/allen-ccf-2017-50um`. The builder's `pynrrd` dependency is installed in an
isolated `uv --with` environment; your project lock is unchanged. The initial setup needs network
access and takes longer than subsequent runs. Repeating it verifies and reuses cached assets.
It does not download the optional 10 um data.

For a lightweight unit/native test setup, skip real-data downloads:

```bash
just setup-tests /path/to/datoviz
just test
```

The test command selects the cached synthetic fixtures and native environment. If D070 was prepared,
it also enables that real-asset test. The optional registered-asset test remains skipped unless
`IBL_REGISTERED_ASSET_SET_ROOT` is set. GPU/runtime skips are reported by pytest; they are not proof
of native validation.

The review command opens app 1, Where did we record?, with coarse anatomical context, a visible real recording and persistent dockable layer controls. App 2 keeps three anatomical slices and a 3D view. Presets and layer
toggles update existing views; they do not rebuild or rearrange the visualization.
See the [review guide](review-apps.md) for the two short review checklists.

```bash
just review 1
just review 2
just review all --frames 3
just review 1 --ui-scale 1.5
just review 1 --preset mixed --offscreen build/mixed.png
just doctor
just test -q tests/test_probe_replacement.py
```

Older focused examples remain available individually, including `just review picking`,
`just review controls`, `just review insertions` and `just review volume-free`. The insertion example
requires explicitly prepared W39 trajectories; see the
[real-data example roadmap](REAL_DATA_EXAMPLE_ROADMAP.md). Use
`just review volume-free --offscreen build/volume-free.png` to capture one
example with the configured native environment. `review all` opens app 1 then app 2;
close the first window to advance. Missing optional W39 trajectories disable app 1's
multiple-insertion preset without replacing them with synthetic data.

Local setup, doctor, tests, and review use your configured Datoviz checkout. Each command reports
its revision and the installed pin; a difference produces a warning and continues. A Markdown-only
Datoviz commit therefore needs no package pin update. Keep the native build compatible with the
checkout's Python bindings when changing engine code; the helper checks loaded paths, not the
native library's build revision.

To validate the pinned baseline, require an exact revision match:

```bash
just doctor --strict
just test --strict tests/test_review.py -q
just review all --strict --frames 3
```

Put `--strict` before pytest arguments for `just test`. The helper equivalents are
`tools/review.py doctor --strict`, `tools/review.py test --strict -- <pytest arguments>`,
and `tools/review.py run all --strict`. Installs and CI continue to use the locked source pin;
update it only when deliberately recording a tested baseline.

The atlas sidebar uses a 18 px base UI font and separates mapping, appearance, selection,
and region browsing. `--ui-scale` multiplies text, controls, and the initial sidebar width;
Datoviz also applies its reported device scale. Hover emphasis clears during camera gestures
and resumes on fresh pointer motion after release; committed selection stays intact.

Run `just` to list commands, `just lint` for Ruff, and `just docs` for a strict documentation build.
Quote a checkout path containing spaces, for example `just setup "$HOME/GIT/Datoviz checkout"`.
Run `just setup` with the checkout path again after dependency pins change; a cache from a different
anatomy revision must be moved aside as the setup error instructs. Setup preserves existing cached
assets and does not rebuild Datoviz.
After `git pull`, rerun setup if review reports missing context data: downloaded
meshes under `build/` are ignored by Git. If a context directory is incomplete,
move it aside first so setup can prepare a complete verified catalog.

The recipes wrap `tools/review.py`. If `just` is unavailable, the equivalent commands are:

```bash
uv sync --group dev --locked
uv run --frozen tools/review.py setup --datoviz /path/to/datoviz
uv run --frozen tools/review.py test
uv run --frozen tools/review.py run
```

Each example runs in its own process. A failure stops the sequence with its error rather than
continuing through broken examples. Strict-mode Datoviz revision mismatches, anatomy revision mismatches, missing libraries, corrupt
cached bytes, and blocked Datoviz environments fail explicitly. The helper does not approve `.envrc`,
switch engine branches, or publish generated images.

The individual installation/materialization commands below remain useful for custom data roots and
troubleshooting; most contributors can use the workflow above.

## Installed-wheel CPU check

Check the wheel independently of the editable checkout, using the exact locked
dependency revisions in a separate environment:

```bash
uv build --wheel --out-dir build/install-check/dist
uv export --locked --no-dev --no-emit-project --format requirements-txt \
  --output-file build/install-check/requirements.txt > /dev/null
uv venv --python 3.13 build/install-check/venv
uv pip install --python build/install-check/venv/bin/python \
  -r build/install-check/requirements.txt build/install-check/dist/*.whl
build/install-check/venv/bin/python -I tools/check_installed.py \
  > build/install-check/receipt.json
```

Use a fresh output/environment directory for each installation check. Repeat on
Python 3.11 to check the minimum supported version. The check rejects editable
imports and imports outside the isolated environment, exercises the new owned
CPU payloads and reads the packaged
atlas, registered-section and envelope locks offline. Its receipt records package
origins and versions. No native bindings, GPU rendering or downloads of numeric
atlas assets are exercised; native compatibility remains a separate check.

## Install a development checkout

The project is an unreleased source snapshot. Its committed `uv.lock` and `[tool.uv.sources]`
entries pin the exact Datoviz and `ibl-anatomy` Git revisions currently under test; the dependency
ranges in package metadata are provisional bounds for a later distributable release. From the
repository root:

```bash
uv sync --group dev --locked
```

The current pinned Datoviz source baseline is
`9aa5fd98e9d31b8e9439e328d62f519b0412575e` from `rc4/scientific-3d`; anatomy is pinned to
`81bd7d79044e4dc3a528abe50a0296381143f03e`. The source snapshot includes RC4 scientific
transparency, alpha-cutoff bindings and controlled native region browsing even though its distribution version is still `0.4.0rc2`. The provisional
wheel dependency bounds do not establish that index packages support this application.
Before releasing, verify the selected distributable Datoviz artifact and a deliberately supported anatomy distribution.

## Python and native library pairing

The contributor recipes above configure their child processes; they do not export variables into
your shell. For direct commands, inspect the resolved environment with no source override:

```bash
uv run --frozen python -c "import datoviz, ibl_anatomy; print(datoviz.__file__); print(ibl_anatomy.__file__)"
```

Use `just test` for managed fixtures and native tests. Direct pytest needs
`IBL_ANATOMY_FIXTURE_ROOT=build/review/anatomy/tests/fixtures` after setup, or CI's pinned adjacent
anatomy checkout.

Interactive and offscreen rendering also need the matching Datoviz native library and a Vulkan
runtime. For a local source build, check out the baseline in `~/GIT/Viz/datoviz` and follow its
[build instructions](https://github.com/datoviz/datoviz/tree/9aa5fd98e9d31b8e9439e328d62f519b0412575e#readme).
Run from this package root, overriding only the Datoviz Python module and selecting the library
built from that same revision (use `libdatoviz.dylib` on macOS):

```bash
git -C ~/GIT/Viz/datoviz rev-parse HEAD
export PYTHONPATH="$HOME/GIT/Viz/datoviz${PYTHONPATH:+:$PYTHONPATH}"
export DATOVIZ_LIBRARY="$HOME/GIT/Viz/datoviz/build/src/libdatoviz.so"
uv run --frozen python -c "import datoviz; import datoviz._ctypes as native; print(datoviz.__file__); print(native.dvz._name)"
```

Activate the platform Vulkan environment from the Datoviz directory before rendering. With
`direnv` configured for that checkout, prefix rendering commands with
`direnv exec ~/GIT/Viz/datoviz` (also on macOS). Avoid mixing a source Python facade with a library
built at another revision; installed distribution versions alone cannot identify this pairing.

## Materialize the real atlas

The D070 asset-set lock identifies immutable remote bytes. Materialization verifies the complete
mesh graph and region catalog before making them available to a viewer:

```bash
uv run --frozen python - <<'PY'
from ibl_anatomy import bundled_asset_set, materialize_asset_set

materialize_asset_set(bundled_asset_set(), "build/atlas-d070")
PY
```

The registered 10 um projection graph has its own bundled lock. It publishes sampled exact
geometry for preview and validation, rather than every section of the 10 um grid. Materialize it
through `ibl-anatomy` to verify every transitive resource:

```bash
uv run --frozen python - <<'PY'
from ibl_anatomy import bundled_registered_asset_set, materialize_registered_asset_set

materialize_registered_asset_set(
    bundled_registered_asset_set(), "build/atlas-registered-10um"
)
PY
```

The lock names an immutable Ephys Atlas deployment, but that deployment layout is not the
consumer API. Python consumers use the verified result/root through `ibl-anatomy`. Direct fetches
from a different browser origin currently require an approved CORS policy or same-origin proxy.

## Build the volume and intensity packs

The pinned anatomy package supplies the readers; the source checkout supplies the builders.
Create a local tools checkout at its immutable revision, without overriding the installed package:

```bash
git clone https://github.com/int-brain-lab/ibl-anatomy.git build/anatomy-tools
git -C build/anatomy-tools checkout --detach 119457b68fae6967c54d549d9d44e4a4e49c74f8
mkdir -p build/allen-sources
curl --fail --location https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/average_template/average_template_50.nrrd -o build/allen-sources/average_template_50.nrrd
curl --fail --location https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/annotation/ccf_2017/annotation_50.nrrd -o build/allen-sources/annotation_50.nrrd
uv run --frozen --with pynrrd==1.1.3 python build/anatomy-tools/tools/build_allen_volume_pack.py \
  build/allen-sources/average_template_50.nrrd \
  build/allen-sources/annotation_50.nrrd build/atlas-d070/regions.json \
  build/allen-ccf-2017-50um
```

The builder verifies the pinned source hashes and rejects an existing output directory. The
optional 10 um intensity transport requires a 343 MB source download, temporary decoded storage
of about 2.4 GB, and about 1.3 GB of output. Build it explicitly:

```bash
curl --fail --location https://download.alleninstitute.org/informatics-archive/current-release/mouse_ccf/average_template/average_template_10.nrrd -o build/allen-sources/average_template_10.nrrd
PYTHONPATH="$PWD/build/anatomy-tools${PYTHONPATH:+:$PYTHONPATH}" \
uv run --frozen python -m tools.build_intensity_blocks \
  build/allen-sources/average_template_10.nrrd build/allen-ccf-2017-10um-intensity \
  --dataset-id allen-ccf-2017-10um-intensity \
  --reference-space-id allen-ccf-2017 --grid-id allen-ccf-2017-10um \
  --index-to-world-um 0 10 0 -5739 -10 0 0 5400 0 0 -10 332 0 0 0 1 \
  --source-id allen-average-template-10um \
  --source-sha256 055b79034ea3ac47cf8776ecdb0c61d2b338d38ee5fd87d0962753efe600a775 \
  --display-low 0 --display-high 252 --sections-per-block 8 --compression-level 6
```

See the pinned upstream [50 um volume recipe](https://github.com/int-brain-lab/ibl-anatomy/blob/119457b68fae6967c54d549d9d44e4a4e49c74f8/docs/SPIKE_002_ATLAS_VOLUME_PACK.md)
and [10 um intensity provenance](https://github.com/int-brain-lab/ibl-anatomy/blob/119457b68fae6967c54d549d9d44e4a4e49c74f8/docs/SPIKE_003_INTENSITY_BLOCK_TRANSPORT.md).

## Open the atlas browser

Start with the isolated 3-D surface baseline. It contains one opaque mesh, one perspective camera,
and one arcball in a direct native window—no ImGui, ontology, hover query, volume, or slices:

```bash
uv run --frozen python examples/atlas_spike.py \
  build/atlas-d070/mesh-pack
```

Then test the ontology and linked-selection layer independently by adding the catalog:

```bash
uv run --frozen python examples/atlas_spike.py \
  build/atlas-d070/mesh-pack \
  --regions build/atlas-d070/regions.json
```

This second rung also exposes an **Explode regions** slider. It follows the shared mesh contract:
at amount `t`, every component is translated by `t * (component centroid - whole-brain centroid)`.
Pass `--explode 0.5` to start at a nonzero value. The baseline without `--regions` remains unchanged.

The full asset-set entry point follows:

```bash
uv run --frozen python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen
```

The left dock contains the parent-closed ontology tree, mapping selector, filters, official color
swatches, and linked selection. Drag the main view to orbit and click a surface region to select it.

For the four-panel navigator, materialize the separate 50 um volume pack and provide both immutable
pack roots:

```bash
uv run --frozen python examples/linked_atlas_navigator.py \
  build/atlas-d070/mesh-pack \
  build/allen-ccf-2017-50um \
  --ui-scale 1.5
```

The atlas dock and visualization area resize as sibling panels. Hover a slice to preview its mapped
region, and click to move the shared AP/ML/DV cursor without changing selection. Use the prominent
Select cursor region button to commit that location, or select directly from the ontology tree or
3-D surface. Left-drag over the 3-D quadrant to orbit it. Over a slice, the wheel accumulates
fractional input and steps four sections per standard notch; Shift+wheel steps twenty. The bracket/Page
Up/Page Down keys provide single-section steps. Ctrl+wheel zooms a slice, and double-click resets
its zoom. Separate controls toggle the anatomy, annotation, and mapping-aware vector boundary
layers and adjust annotation, boundary, or volume opacity. The template is linearly sampled, while
the discrete labels retain nearest-neighbour sampling and transparent atlas margins reveal the
neutral panel background.

The same committed mapped identity drives the official slice colors, 3-D cursor, surface highlight,
ontology tree, and any attached probe or regional tables. The scalar anatomical template is
volume-rendered in the 3-D panel on native Datoviz; volume rendering is not currently claimed for
the WebGPU export.

The slice grid and dense 3-D volume are independent. A complete compatible 10 um registered
anatomy source supports high-resolution slices over the bounded 50 um volume without uploading a
complete 10 um volume to the GPU.

The bundled published graph is **sampled geometry only**: 165 of 1320 AP sections (indices
4, 12, ...), 142 of 1140 ML sections (6, 14, ...), and 100 of 800 DV sections (1, 9, ...).
It cannot start the current unrestricted navigator: the default cursor requests ML 570 and DV 400,
which have no registered resource and raise `KeyError`. Do not pass the bundled root through
`--registered-asset-root` as a full-navigator onboarding command. The source does not interpolate,
snap to another section, or silently substitute 50 um annotation for missing registered geometry.

With the intensity transport built above, preview an actually published section without a native
scene:

```bash
uv run --frozen python - <<'PY'
from ibl_anatomy import (
    bundled_registered_asset_set, open_intensity_block_pack, open_volume_pack,
    verify_materialized_registered_asset_set,
)
from ibl_datoviz import AtlasSliceComposer, AtlasSliceSource

assets = verify_materialized_registered_asset_set(
    bundled_registered_asset_set(), "build/atlas-registered-10um"
)
intensity = open_intensity_block_pack("build/allen-ccf-2017-10um-intensity")
catalog = open_volume_pack("build/allen-ccf-2017-50um").load_volumes().regions
source = AtlasSliceSource(
    intensity,
    {projection.world_slice_axis: projection for projection in assets.projections.values()},
    catalog,
)
composer = AtlasSliceComposer(source, "allen")
for axis, index in (("ap", 660), ("ml", 566), ("dv", 401)):
    anatomy, annotation = composer.compose_layers(axis, index)
    print(axis, index, anatomy.shape, annotation.shape)
PY
```

For deliberate local inputs, `--anatomy-pack` accepts a **complete** compatible legacy anatomy-v2
pack. Its reference space, grid, affine, signed identities, and intensity alignment must match,
and every requested slice needs geometry. Such a real complete pack is not supplied by the bundled
publication lock; the following is conditional on obtaining one:

```bash
uv run --frozen python examples/linked_atlas_navigator.py \
  build/atlas-d070/mesh-pack \
  build/allen-ccf-2017-50um \
  --slice-resolution registered \
  --slice-intensity-pack build/allen-ccf-2017-10um-intensity \
  --anatomy-pack path/to/complete-anatomy-v2.json
```

This path is covered by synthetic native smoke tests; complete real-data interaction still awaits
review. The authoritative cursor lives in the high-resolution grid and transforms through ML/AP/DV
world micrometres to the surface and dense volume. Prepared current slices mutate Datoviz only on
the view owner thread.

For a non-interactive smoke render, add an output path:

```bash
uv run --frozen python examples/bwm_probe.py \
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
