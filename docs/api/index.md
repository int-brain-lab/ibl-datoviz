# API overview

The public API is intentionally small and split at data ownership boundaries.

| Object | Responsibility |
| --- | --- |
| [`AtlasViewer`](viewer.md) | Datoviz scene, native resources, mapping, overlays, GUI, and selection |
| [`AtlasMesh`](data-models.md#ibl_datoviz.atlas.AtlasMesh) | Display-ready mesh arrays and presentation identity |
| [`AtlasTreeModel`](data-models.md#ibl_datoviz.ontology.AtlasTreeModel) | Packed retained-tree rows derived from the shared catalog |
| [`ProbeSites`](data-models.md#ibl_datoviz.probe.ProbeSites) | Immutable positions, site identities, values, and signed Allen IDs |
| [`AtlasRegionValues`](data-models.md#ibl_datoviz.regions.AtlasRegionValues) | Immutable regional scalar values and explicit aggregation weights |

`ibl-atlas-assets` validates and decodes packaged anatomy. `ibl-datoviz` converts those arrays into
native presentation and interaction. Scientific coordinate-to-label operations remain in
`iblatlas` or in an explicitly provenance-bearing data preparation step.

All viewer instances own native resources and should be used as context managers.
