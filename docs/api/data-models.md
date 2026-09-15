# Data models

## Atlas mesh

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

## Ontology tree

::: ibl_datoviz.ontology.AtlasTreeModel
    options:
      members:
        - from_catalog
        - palette
        - selectable_region_ids
        - expanded_logical_ids
        - describe

::: ibl_datoviz.ontology.encode_region_key

::: ibl_datoviz.ontology.decode_region_key

## Probe sites

::: ibl_datoviz.probe.ProbeSites
    options:
      members:
        - from_arrays

## Regional values

::: ibl_datoviz.regions.AtlasRegionValues
    options:
      members:
        - from_arrays
