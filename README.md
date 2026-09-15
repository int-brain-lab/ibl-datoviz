# ibl-datoviz

**[Documentation](docs/index.md) · [Gallery](docs/gallery/index.md) ·
[API reference](docs/api/index.md)**

`ibl-datoviz` 0.2 is a deliberately breaking Datoviz v0.4-based atlas viewer. The first
vertical slice reads the renderer-neutral mesh-pack contract from `ibl-anatomy`, uploads
its dense NumPy arrays, retains signed Allen/Beryl/Cosmos presentation identity, and adds
scalar-colored probe sites, a probe path, arcball navigation, and Datoviz item interaction.

The mesh geometry is uploaded once. Calling `AtlasViewer.set_mapping()` updates only vertex
colors and per-face link keys, so switching ontology mappings does not reload geometry. Datoviz
indexed-mesh item queries identify triangle primitives; the adapter therefore classifies each
face at the declared hemispheric boundary rather than incorrectly treating query IDs as vertex
IDs.

Build the local documentation site with `mkdocs build --strict`. Gallery commands and capability
labels are kept in `docs/gallery/manifest.json`; `python tools/build_gallery.py --dry-run` shows the
reproducible native screenshot pipeline without modifying tracked images.

## Development checkout

The committed `uv` sources pin exact Datoviz and atlas-assets revisions. When working on the
three adjacent repositories, use their source trees and the already-built local Datoviz native
library:

```bash
export PYTHONPATH=../../Viz/datoviz:../ibl-anatomy/src
/home/cyrille/GIT/Viz/datoviz/.venv/bin/python -m pytest
```

Run the miniature offline viewer and write its smoke image:

```bash
python examples/atlas_spike.py \
  ../ibl-anatomy/tests/fixtures/mesh-pack-v1/pack \
  --regions ../ibl-anatomy/tests/fixtures/atlas-regions-v1/regions.json \
  --offscreen build/atlas-spike.png
```

Omit `--offscreen` for the interactive view. With `--regions`, the viewer uses official ontology
colors and adds a native retained region browser with Allen/Beryl/Cosmos switching, search,
color swatches, collapse/expand controls, signed-ID selection, and a region explosion slider.
Explosion uses the mesh pack's canonical component-centroid displacement vectors, matching the
ephys-atlas-web-v2 definition. Drag to orbit the arcball and click a mesh face to exercise picking.
`AtlasViewer.selected_region_ids()` returns signed IDs selected through either surface or tree.

Use the real D070 mesh without `--regions` as the first performance and interaction baseline. This
path creates one direct native view containing only an opaque mesh, perspective camera, and
arcball; it does not initialize ImGui, ontology widgets, picking, volumes, or slices:

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
uv run python examples/atlas_spike.py \
  ../ibl-anatomy/build/d070-published/mesh-pack
```

Only after that baseline is healthy, add the region catalog to test the separate embedded-GUI,
hover, linked-selection, and explosion rung:

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
uv run python examples/atlas_spike.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  --regions ../ibl-anatomy/build/d070-published/regions.json
```

Use `--explode 0.5` to set an initial value. The slider currently updates only the mesh position
buffer; the benchmark ladder will measure this path before a Datoviz GPU-deformation API is
considered.

The miniature fixture is intentionally synthetic and its Beryl mapping is absent. Missing
mapping values therefore use a neutral gray. Real atlas colors should eventually come from a
versioned region catalog supplied as an explicit palette; they do not belong in Datoviz.

## Real D070 checkpoint

Materialize the pinned real surface once through `ibl-anatomy`, then run the same verified graph through the native adapter:

```bash
PYTHONPATH=../ibl-anatomy/src python - <<'PY'
from ibl_anatomy import bundled_asset_set, materialize_asset_set
materialize_asset_set(bundled_asset_set(), "build/atlas-d070")
PY

PYTHONPATH=.:../ibl-anatomy/src python examples/benchmark_atlas.py \
  build/atlas-d070 --render build/atlas-d070.png --json build/atlas-d070.json
```

The EAM3 arrays are already compiled into declared ML/AP/DV micrometre coordinates. `source_to_world_um` is source provenance and must not be applied again. The shared reader owns that invariant and the vertex/face presentation classification; this package owns display normalization, palette upload, Datoviz interaction, and viewer lifecycle.

See [the real D070 checkpoint](docs/REAL_D070_CHECKPOINT.md) for reproducible preparation, rendering, memory, and face-query measurements.

Launch the linked real-atlas explorer directly from that verified asset graph:

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen
```

Add a fixed probe trajectory and 48 synthetic scalar-colored sites whose Allen labels were
precomputed with `iblatlas.AllenAtlas(25)`:

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/allen_mouse_brain.py \
  build/atlas-d070 --mapping allen --demo-probe
```

With `--probe`, the example lowers anatomy opacity to 0.18 and renders the dense atlas mesh with
Datoviz v0.4 weighted blended order-independent transparency (WBOIT). Override that choice with
`--surface-opacity`. The viewer API keeps opacity as a multiplier on canonical region alpha, so
mapping changes and selection highlighting preserve the translucent anatomy shell. WBOIT is a
native capability in this checkpoint; a future WebGPU version needs an explicit supported
fallback rather than silently changing the rendering model.

`ProbeSites` is the small renderer-neutral application payload exercised by this demo: immutable
site IDs, ML/AP/DV positions, scalar values, and signed Allen IDs. The viewer derives the current
Allen/Beryl/Cosmos presentation through the verified catalog, installs item link keys in one batch,
and builds a searchable/sortable retained table. Selecting table rows selects their atlas regions;
tree or surface selection selects matching sites. Custom coordinates remain available through
`--probe ENTRY_ML ENTRY_AP ENTRY_DV TIP_ML TIP_AP TIP_DV`, without pretending they have been
anatomically annotated.

## Real BWM ephys checkpoint

The repository includes one compact derived fixture from the local `bwm_ephys` 1.1.0 dataset. It
contains insertion `a21bade7-5be7-4a17-a9b9-ddee453e6260` (PL030, Hausser lab): 384 channels
collapsed to 192 exact atlas locations, seven signed Allen regions, and the mean firing rate of the
459 good units assigned to those sites. Source hashes and the full derivation are stored in the
adjacent provenance JSON.

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/bwm_probe.py \
  build/atlas-d070 --mapping beryl
```

![Real BWM probe sites in the D070 atlas](docs/images/bwm-probe.png)

The demo uses a sequential color scheme and clips its display range to the finite 5th–95th
percentiles. This is a robust visualization choice, not a statistical analysis or a change to the
recorded values. Missing values remain explicit and gray. The GUI table exposes the raw mean firing
rate and links its stable channel-group rows to surface and ontology selection.

The second view aggregates those same measurements by signed Allen region and carries the declared
site counts forward as weights when Allen rows collapse into Beryl or Cosmos. It exercises one
selection across scalar-colored surfaces, probe sites, the ontology tree, and both retained tables:

```bash
PYTHONPATH=.:../ibl-anatomy/src python examples/bwm_region_activity.py \
  build/atlas-d070 --mapping beryl
```

![Mapping-aware BWM regional activity](docs/images/bwm-region-activity.png)

`AtlasRegionValues` deliberately contains only signed Allen IDs, one scalar, weights, and column
names; ontology labels remain catalog-owned. The caller must explicitly request
`mapping_reduction="weighted_mean"`, because that reduction is scientifically valid for this
site-mean/count example but not for arbitrary statistics. Rows absent from a reduced mapping are
omitted rather than misrepresented as root. Rendering belongs here; scientific derivation remains
explicit in the example, while asset decoding and ontology metadata remain in `ibl-anatomy`.
The example also gives valued regions higher opacity than the surrounding anatomical context; both
opacities remain explicit viewer settings.

`AtlasViewer(camera_angles=(x, y, z))` selects a reproducible initial arcball view, and
`set_camera_angles()` updates an active view. These calls require Datoviz commit `1114b65fa` or
later; earlier v0.4 snapshots retained the angles but skipped them on camera-less panels.

To reproduce the committed fixture from the local BWM dataset, run the optional Pandas-based build
tool; Pandas is deliberately not an `ibl-datoviz` runtime dependency:

```bash
python tools/build_bwm_probe_fixture.py \
  ../ibl-ai-agent/reports/datasets/bwm_ephys/1.1.0 examples/data
```

The tree is a parent-closed ontology view. Rows used only to preserve hierarchy in reduced Beryl
or Cosmos mappings are visibly muted but remain expandable. Selecting a parent highlights all mapped descendants;
multiple selection, search, mapping changes, surface picking, clearing, and tree reveal all share
one authoritative selection state. Geometry remains unchanged while colors and face identities
follow the selected mapping.
