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

## Registered atlas slices

`AtlasSliceSource` adapts verified registered projections and scalar intensity blocks. It owns its
byte-accounted decoded cache; callers may clear that cache explicitly. Returned arrays use the
source grid and declared anatomical axes rather than an inferred transpose.

::: ibl_datoviz.atlas_slice_source.AtlasSliceSource
    options:
      members:
        - slice
        - annotation_index_at_world
        - region_for_source_index
        - cache_info
        - clear_cache

## Ontology tree

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

## Probe sites

`ProbeSites` copies caller arrays into immutable storage. Positions are atlas-world micrometres;
values may contain `NaN` for missing observations but never infinities. IDs must be unique positive
integers and Allen region IDs remain signed.

::: ibl_datoviz.probe.ProbeSites
    options:
      members:
        - from_arrays

## Regional values

`AtlasRegionValues` copies immutable signed-Allen scalar rows and optional aggregation weights.
Missing scalar values use `NaN`; cross-mapping reduction remains an explicit caller choice.

::: ibl_datoviz.regions.AtlasRegionValues
    options:
      members:
        - from_arrays
