# Atlas viewer

Viewer objects own their Datoviz scene, application, GUI, and interaction resources. Use them as
context managers or call `close()` explicitly. Closing is idempotent; rendering or mutation after
close raises `RuntimeError`. Positions are atlas-world micrometres, visual widths are pixels, and
colors are three or four integer channels in `[0, 255]`.

## Linked atlas navigator

::: ibl_datoviz.linked_atlas.LinkedAtlasNavigator
    options:
      members:
        - from_packs
        - from_registered_assets
        - from_multiresolution_packs
        - from_anatomy_packs
        - set_cursor
        - set_cursor_from_slice_data
        - set_mapping
        - set_probe
        - set_probe_data
        - set_region_data
        - render_offscreen
        - show
        - close

`LinkedAtlasNavigator.from_registered_assets()` is the shared publication path. It combines an
independently bounded dense volume and scalar intensity transport with a verified
`MaterializedRegisteredAssets` result from `ibl-anatomy`; Datoviz does not infer resources from
the Ephys Atlas deployment layout. The older `from_anatomy_packs()` and lower-level
`from_multiresolution_packs()` remain available for deliberate local inputs. `ibl-anatomy` owns
integrity, affine, and decoded geometry contracts; `ibl-datoviz` owns raster composition,
latest-wins preparation, and owner-thread GPU updates.

The three slice panels use increasing atlas world coordinates from left to right and bottom to top:
AP slices show ML/dorsal, ML slices show AP/dorsal, and DV slices show ML/anterior. Clicking a
slice changes the two visible cursor coordinates while retaining the orthogonal slice coordinate.
Annotation slices are precolored on the CPU so the complete Allen/Beryl/Cosmos catalog is not
limited by the current 64-entry GPU categorical palette.

## Navigator data model

::: ibl_datoviz.navigator.AtlasCursor

::: ibl_datoviz.navigator.AtlasSliceComposer
    options:
      members:
        - set_mapping
        - compose

::: ibl_datoviz.navigator.compose_atlas_slice

## Surface viewer

::: ibl_datoviz.viewer.AtlasViewer
    options:
      members:
        - from_pack
        - from_assets
        - from_asset_set
        - set_mapping
        - set_camera_angles
        - set_probe
        - set_probe_sites
        - set_probe_data
        - set_region_data
        - selected_region_ids
        - set_selected_region_ids
        - clear_selection
        - render_offscreen
        - show
        - close
