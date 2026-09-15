# IBL Datoviz

`ibl-datoviz` is a native Python viewer for International Brain Laboratory atlas data, built on
Datoviz v0.4. It connects verified Allen CCF 2017 surface assets to interactive 3-D rendering,
ontology navigation, probe sites, regional values, and linked selection.

<div class="capability-row">
  <span class="capability capability--native">Native · available</span>
  <span class="capability capability--webgpu">WebGPU · planned</span>
  <span class="capability capability--data">Allen · Beryl · Cosmos</span>
</div>

![Mapping-aware BWM regional activity](images/bwm-region-activity.png)

## Current scope

- Verified renderer-neutral geometry and ontology data come from `ibl-atlas-assets`.
- Dense meshes, WBOIT transparency, picking, arcball navigation, and retained GUI widgets use
  Datoviz v0.4.
- `ibl-datoviz` owns native viewer composition and display behavior. It does not become a second
  scientific atlas authority.
- `iblatlas` remains responsible for scientific ontology, mapping, coordinates, labels, and atlas
  computations.

[Get started](getting-started.md){ .md-button .md-button--primary }
[Browse the gallery](gallery/index.md){ .md-button }

!!! note "Development status"

    The 0.2 line intentionally breaks with the historical 0.1-era API while the Datoviz v0.4
    integration is validated. The public surface is still expected to evolve before release.
