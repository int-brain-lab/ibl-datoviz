# Atlas viewer

Viewer objects own their Datoviz scene, application, GUI, and interaction resources. Use them as
context managers or call `close()` explicitly. Closing is idempotent; rendering or mutation after
close raises `RuntimeError`. Positions are atlas-world micrometres, visual widths are pixels, and
colors are three or four integer channels in `[0, 255]`.

Retained-layer controls keep the existing views: `set_surface_visible()` hides the
whole surface independently of region/hemisphere overrides, `set_surface_opacity()`
updates global opacity transactionally, and `reset_surface_style()` clears regional
overrides and shows both hemispheres without moving the camera. The navigator's
`set_slice_layers(anatomy=..., annotations=..., boundaries=...)` changes existing
slice panels, and `set_volume_opacity(0)` hides the volume without changing layout.
See the [two review apps](../review-apps.md) for concrete compositions.

## Linked atlas navigator

::: ibl_datoviz.linked_atlas.LinkedAtlasNavigator
    options:
      members:
        - from_packs
        - from_registered_assets
        - from_multiresolution_packs
        - from_anatomy_packs
        - from_slice_source
        - from_registered_slices
        - set_cursor
        - set_slice_layers
        - set_volume_opacity
        - set_cursor_from_slice_data
        - set_mapping
        - set_probe
        - set_probe_data
        - set_region_data
        - set_region_visible
        - set_region_color
        - set_region_opacity
        - set_hemisphere
        - set_insertion
        - render_offscreen
        - show
        - close

`LinkedAtlasNavigator.from_registered_assets()` accepts a verified publication result. It combines an
independently bounded dense volume and scalar intensity transport with a verified
`MaterializedRegisteredAssets` result from `ibl-anatomy`; Datoviz does not infer resources from
the Ephys Atlas deployment layout. The older `from_anatomy_packs()` and lower-level
`from_multiresolution_packs()` remain available for deliberate local inputs. `ibl-anatomy` owns
integrity, affine, and decoded geometry contracts; `ibl-datoviz` owns raster composition,
latest-wins preparation, and owner-thread GPU updates.

A verified graph need not contain every native-grid section. The bundled 10 um graph contains
sampled sections only; its missing default ML 570 and DV 400 resources prevent unrestricted
navigator startup. Integrity verification does not establish complete section coverage.
`from_anatomy_packs()` supports a complete compatible legacy anatomy-v2 source, and all registered
routes require geometry for every requested section. `AtlasSliceSource.slice()` raises `KeyError`
when a valid grid index has no published resource; it does not interpolate or snap geometry.
See [Getting started](../getting-started.md#open-the-atlas-browser) for sampled previews and the
conditional complete-source route.

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
        - set_region_visible
        - show_region
        - hide_region
        - set_region_color
        - set_region_opacity
        - reset_region_style
        - set_hemisphere_visible
        - set_hemisphere
        - visible_region_ids
        - set_insertion
        - set_insertion_color
        - set_insertion_width
        - set_insertion_visible
        - remove_insertion
        - insertion_ids
        - selected_region_ids
        - set_selected_region_ids
        - clear_selection
        - render_offscreen
        - show
        - close

## Independent surface presentation

Region controls use signed IDs from the current mapping: negative is left,
positive is right. `hemisphere="left"`, `"right"` or `"both"` explicitly expands
an absolute region ID; omitting it targets the supplied signed ID exactly.
Unknown or unmapped IDs fail before native changes. Overrides are stored per
mapping, so switching back restores that mapping's region styles. Global
hemisphere visibility persists across mappings and uses verified presentation
side metadata, including unmapped faces.

```python
viewer.set_region_color(-315, (220, 80, 40))
viewer.set_region_opacity(-315, 0.3)
viewer.hide_region(315)
viewer.show_region(315)
viewer.set_region_visible(315, False, hemisphere="both")
viewer.reset_region_style(315, hemisphere="both")
viewer.set_hemisphere("left")
viewer.set_hemisphere_visible("right", True)
```

Visibility filters canonical triangle indices and their matching face link keys,
preserving atlas identity arrays, normalization and framing. Hidden faces and
faces with zero authored alpha are absent from picking as well as shading; an empty surface suppresses
drawing without unsupported zero-count uploads. Hemisphere controls select the
pack's canonical face partition. They do not reclip geometry, generate cut caps,
or replace the scientific annotation with a mesh.

RGB overrides retain source alpha; RGBA overrides replace authored region alpha,
scaled by global surface opacity. Regional opacity multiplies authored alpha.
Hover/selection cannot raise alpha above authored palette or regional overrides;
the existing global-opacity selection emphasis remains available. Native alpha
mode respects effective palette/scalar alpha, not only global opacity. An active
bounded volume retains its documented source-over composition; the volume-free
route can use mesh WBOIT directly.

Manual appearance overrides affect the 3D surface only. They do not change
scientific values, reductions, linked table colors or slice annotations. Hiding a
selected region preserves committed linked selection; changing mappings retains
the established selection-reset policy. Failed native style/data/mapping updates
restore prior identity, geometry, colors, alpha mode and public/cache state. A
failed rollback closes the viewer rather than leaving a partially updated scene.

See [multiple insertions](insertions.md) and [volume-free navigation](volume-free.md)
for the independent trajectory and slice-source contracts.
