# Data models

## Atlas mesh

`AtlasMesh` owns contiguous display-ready arrays derived from verified `ibl-anatomy` geometry.
World positions and point inputs use micrometres; normalized positions are renderer coordinates.
Malformed shapes, non-finite coordinates, unknown mappings, and invalid colors raise `ValueError`
or `KeyError` before native upload.

::: ibl_datoviz.atlas.AtlasMesh
    options:
      members:
        - from_pack
        - from_geometry
        - mapping_names
        - mapping_ids
        - face_mapping_ids
        - colors
        - link_keys
        - normalize_points

## Reference brain envelope

`AtlasEnvelope` owns a separate whole-brain display surface. It uses the same
normalization as `AtlasMesh`, preserving scientific world coordinates and regional
identities. Its default source is the verified source-native Allen envelope;
annotation-boundary arrays require an explicit variant.

::: ibl_datoviz.envelope.AtlasEnvelope
    options:
      members:
        - from_source
        - from_geometry
        - from_world_arrays

## Registered atlas slices

`AtlasSliceSource` adapts verified registered projections and scalar intensity blocks. It owns its
byte-accounted decoded cache; callers may clear that cache explicitly. Returned arrays use the
source grid and declared anatomical axes rather than an inferred transpose. Valid grid indices
without registered geometry raise `KeyError`. The bundled real publication includes sampled
sections, not complete 10 um coverage; callers must request available sections for previews or
supply a complete compatible source for unrestricted navigation.

::: ibl_datoviz.atlas_slice_source.AtlasSliceSource
    options:
      members:
        - slice
        - annotation_index_at_world
        - region_for_source_index
        - cache_info
        - clear_cache

## Lower-level ontology tree

Import `AtlasTreeModel` from `ibl_datoviz.components` for explicit GUI composition.
Ordinary applications use the viewer-owned region browser.


`AtlasTreeModel` is an advanced presentation model derived from a verified region catalog. Signed
atlas IDs remain identities; labels are never used as keys.

::: ibl_datoviz.ontology.AtlasTreeModel
    options:
      members:
        - from_catalog
        - palette
        - selectable_region_ids
        - expanded_logical_ids
        - describe

## Legacy probe preparation

`ProbeSites` is available from `ibl_datoviz.components` for diagnostic clients.
New applications use `Channels`, `Clusters`, or `Sites` and viewer-owned handles.


`ProbeSites` copies caller arrays into immutable storage. Positions are atlas-world micrometres;
values may contain `NaN` for missing observations but never infinities. IDs must be unique positive
integers and Allen region IDs remain signed.

::: ibl_datoviz.probe.ProbeSites
    options:
      members:
        - from_arrays

## Regional values

Use `RegionValues` and `app.add_region_values()` for scientific regional data with
units, explicit weights, frame evidence and provenance. The lower-level
`AtlasRegionValues` record is available from `ibl_datoviz.components`.

::: ibl_datoviz.regional_quantities.RegionValues

::: ibl_datoviz.regional_quantities.MappedRegionValues


`AtlasRegionValues` copies immutable signed-Allen scalar rows and optional aggregation weights.
Missing scalar values use `NaN`; cross-mapping reduction remains an explicit caller choice.

::: ibl_datoviz.regions.AtlasRegionValues
    options:
      members:
        - from_arrays
