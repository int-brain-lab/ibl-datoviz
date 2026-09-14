# ibl-datoviz

`ibl-datoviz` 0.2 is a deliberately breaking Datoviz v0.4-based atlas viewer. The first
vertical slice reads the renderer-neutral mesh-pack contract from `ibl-atlas-assets`, uploads
its dense NumPy arrays, retains signed Allen/Beryl/Cosmos presentation identity, and adds a
probe path, arcball navigation, and Datoviz item interaction.

The mesh geometry is uploaded once. Calling `AtlasViewer.set_mapping()` updates only vertex
colors and per-face link keys, so switching ontology mappings does not reload geometry. Datoviz
indexed-mesh item queries identify triangle primitives; the adapter therefore classifies each
face at the declared hemispheric boundary rather than incorrectly treating query IDs as vertex
IDs.

## Development checkout

The committed `uv` sources pin exact Datoviz and atlas-assets revisions. When working on the
three adjacent repositories, use their source trees and the already-built local Datoviz native
library:

```bash
export PYTHONPATH=../../Viz/datoviz:../ibl-atlas-assets/src
/home/cyrille/GIT/Viz/datoviz/.venv/bin/python -m pytest
```

Run the miniature offline viewer and write its smoke image:

```bash
python examples/atlas_spike.py \
  ../ibl-atlas-assets/tests/fixtures/mesh-pack-v1/pack \
  --offscreen build/atlas-spike.png
```

Omit `--offscreen` for the interactive view. Drag to orbit the arcball and click a mesh item to
exercise retained picking/selection. `AtlasViewer.selected_region_ids()` returns the signed IDs
stored by the current mapping's selection.

The miniature fixture is intentionally synthetic and its Beryl mapping is absent. Missing
mapping values therefore use a neutral gray. Real atlas colors should eventually come from a
versioned region catalog supplied as an explicit palette; they do not belong in Datoviz.
