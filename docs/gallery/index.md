# Gallery

These examples are executable checkpoints, not static mock-ups. Capability labels distinguish
what works in the current native renderer from future browser exports.

<div class="gallery-grid" markdown>

<div class="gallery-card" markdown>

## BWM probe sites

![Real BWM probe sites](../images/bwm-probe.png)

<span class="capability capability--native">Native · available</span>
<span class="capability capability--webgpu">WebGPU · candidate</span>

One real insertion with a translucent WBOIT anatomy shell, probe trajectory, 192 channel groups,
missing-value styling, and a linked searchable table.

```bash
python examples/bwm_probe.py build/atlas-d070 --mapping beryl
```

</div>

<div class="gallery-card" markdown>

## Regional BWM activity

![Mapping-aware regional activity](../images/bwm-region-activity.png)

<span class="capability capability--native">Native · available</span>
<span class="capability capability--webgpu">WebGPU · candidate</span>

The same record aggregated by signed Allen region, then explicitly reduced for Beryl or Cosmos.
Selection links valued surfaces, sites, ontology rows, and both retained tables.

```bash
python examples/bwm_region_activity.py build/atlas-d070 --mapping beryl
```

</div>

<div class="gallery-card" markdown>

## Allen atlas explorer

<span class="capability capability--native">Native · available</span>
<span class="capability capability--webgpu">WebGPU · candidate</span>

Verified D070 geometry, official ontology colors, Allen/Beryl/Cosmos switching, arcball camera,
face picking, and an optional synthetic probe used to test linked selection.

```bash
python examples/allen_mouse_brain.py build/atlas-d070 --demo-probe
```

</div>

<div class="gallery-card" markdown>

## Offline contract smoke test

<span class="capability capability--native">Native · available</span>
<span class="capability capability--webgpu">WebGPU · candidate</span>
<span class="capability capability--data">Synthetic fixture</span>

A small network-free mesh and region catalog for fast rendering and lifecycle checks. It carries
no scientific claim.

```bash
python examples/atlas_spike.py \
  ../ibl-atlas-assets/tests/fixtures/mesh-pack-v1/pack \
  --regions ../ibl-atlas-assets/tests/fixtures/atlas-regions-v1/regions.json
```

</div>

</div>

## Diagnostic benchmark

`examples/benchmark_atlas.py` verifies the real asset graph, measures decoding and mapping
preparation, optionally renders a frame, and records face-query timings. Its generated PNG and JSON
remain build-local because timing and pixels depend on the host.

## Capability matrix

| Entry | Native | Offscreen | WebGPU |
| --- | --- | --- | --- |
| Offline contract smoke test | Available | Available | Candidate semantic fixture |
| Allen atlas explorer | Available | Available | Candidate; not exported |
| BWM probe sites | Available | Available | Candidate; not exported |
| Regional BWM activity | Available | Available | Candidate; not exported |
| D070 diagnostic benchmark | Available | Available | Not applicable |

## WebGPU status

No example is currently claimed as a WebGPU export. The two BWM scenes are good first candidates
because their data contracts and expected interactions are now concrete. A browser implementation
must state how it replaces native WBOIT before its output is presented as equivalent. The offline
smoke fixture should be the first automated cross-renderer semantic test.

See [Development](../development.md#regenerate-the-gallery) for the single-command gallery pipeline.
