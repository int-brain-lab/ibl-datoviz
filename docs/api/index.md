# API overview

The public API is intentionally small and split at data ownership boundaries.

The [scientific viewer API proposal](../SCIENTIFIC_VIEWER_API_PROPOSAL.md) describes
the approved direction following acceptance of the recording-context demo.
Generic payloads, owned layer/recording handles, exact programmatic selection and
package-level Layers controls are now implemented. Exact native picking for filled points/spheres and the
unified linked-layout facade are implemented and retain interactive acceptance gates.

| Object | Responsibility |
| --- | --- |
| [`Points`, `Paths`](components.md#viewer-owned-scientific-layers) | Generic immutable geometry, original IDs, frames and provenance |
| `Recording`, `Channels`, `Clusters`, `Sites`, `Trajectory` | Prepared insertion-scoped scientific populations |
| `WorldFrame`, `SourceKey`, `SourceObservationKey` | Explicit coordinate evidence and immutable scientific identity |
| [`AtlasViewer`](viewer.md) | Datoviz scene, native resources, mapping, overlays, GUI, and selection |
| [`AtlasMesh`](data-models.md#ibl_datoviz.atlas.AtlasMesh) | Display-ready mesh arrays and presentation identity |
| [`AtlasTreeModel`](data-models.md#ibl_datoviz.ontology.AtlasTreeModel) | Packed retained-tree rows derived from the shared catalog |
| [`ProbeSites`](data-models.md#ibl_datoviz.probe.ProbeSites) | Immutable positions, site identities, values, and signed Allen IDs |
| [`AtlasRegionValues`](data-models.md#ibl_datoviz.regions.AtlasRegionValues) | Immutable regional scalar values and explicit aggregation weights |

## Supported top-level API

The compatibility surface is the package's explicit `ibl_datoviz.__all__`: `AtlasViewer`,
`LinkedAtlasNavigator`, `AtlasMesh`, `ProbeSites`, `AtlasRegionValues`, `RegionValues`, `AtlasTreeModel`,
`AtlasSliceSource`, `AtlasCursor`, `AtlasSliceComposer`, and `compose_atlas_slice`. Examples import
these names from `ibl_datoviz`. The scientific API also exports `Points`, `Paths`,
`Channels`, `Clusters`, `Sites`, `Trajectory`, `Recording`, `WorldFrame`, `SourceKey`,
`SourceObservationKey`, `LayerObservationRef`, `LayerCapabilities` and
`UnavailableLayerError`. The optional `ibl_datoviz.ibl` module documents `BwmSource`
and `prepare_bwm_recording`; importing generic viewer APIs does not require the
shared IBL reader or an AI runtime.

Other module members are implementation details. In particular, SVG parsing, signed-link-key
encoding, cursor-fraction helpers, and the concrete source-slice record may change without a
top-level compatibility promise.

`ibl-anatomy` validates and decodes packaged anatomy. `ibl-datoviz` converts those arrays into
native presentation and interaction. Scientific coordinate-to-label operations remain in
`iblatlas` or in an explicitly provenance-bearing data preparation step.

All viewer instances own native resources and should be used as context managers.
