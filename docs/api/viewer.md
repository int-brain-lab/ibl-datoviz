# Atlas viewer

Viewer objects own their Datoviz scene, application, GUI, and interaction resources. Use them as
context managers or call `close()` explicitly. Closing is idempotent; rendering or mutation after
close raises `RuntimeError`. Positions are atlas-world micrometres, visual widths are pixels, and
colors are three or four integer channels in `[0, 255]`.

Retained-layer controls keep the existing views: `set_surface_visible()` hides the
whole surface independently of region/hemisphere overrides, `set_surface_opacity()`
updates global opacity transactionally, and `reset_surface_style()` clears regional
overrides and shows both hemispheres without moving the camera. The linked viewer's
`app.slices.set_layers(anatomy=..., annotations=..., boundaries=...)` changes existing
slice panels, and `app.slices.set_volume_opacity(0)` hides the volume without changing layout.
See the [two review apps](../review-apps.md) for concrete compositions.

## Region browser

The Allen/Beryl/Cosmos browser follows the [shared IBL selector contract](https://github.com/int-brain-lab/ibl-anatomy/blob/81bd7d79044e4dc3a528abe50a0296381143f03e/docs/REGION_SELECTOR_CONTRACT.md). Click a branch to fold or unfold it; click a mapping-member leaf to select it. Clicking a selected leaf removes it. Ctrl/Cmd toggles individual leaves, Multiple selection keeps other selections, and Shift-click adds visible selectable siblings between the anchor and target. Arrow keys navigate the tree; Enter or Space activates the focused row.

Search matches names and acronyms, retains ancestor paths and matching subtrees, and temporarily restores anatomical order. Clearing search restores ordinary folding and the requested value order. Value ordering is available when regional data provide finite browser values. Native browser annotations use the canonical left rows and exact signed regional identities; right-only values do not fill missing left values or imply bilateral aggregation. Right-side surface and table values remain available independently. Programmatic selections and selections from surfaces or tables preserve browser focus and folding; selecting a parent through `set_selected_region_ids()` still highlights its mapped descendants.

A mapping change clears committed selection and transient hover while retaining query, ordinary folding and requested order. Tree, region table, probe table and surface updates preserve the documented source precedence and signed hemisphere identities. Selection does not move the linked navigator's cursor. Generic Datoviz tree rendering is controlled by an internal adapter; callers continue using the existing viewer API.

## Selection presentation

`AtlasViewer` defaults to `selection_presentation='legacy'`, preserving bilateral context dimming. Opt into `'focus'` to draw only selected signed regions and their descendants, with an optional neutral reference envelope; `'isolate'` omits the envelope and `'all'` restores the full visible atlas while retaining selection. `set_selection_presentation()` switches these modes without rewriting authored styles. Clear selection restores ordinary atlas coverage. Focus uses the selected hemisphere; selecting a left parent does not select its right homologue. Hidden regions and authored opacity still apply.

Pass a prepared `AtlasEnvelope` through `selection_envelope=` or `set_selection_envelope()`. The shell has no region identity, contributes observation-query depth, and is hidden during explosion, isolation or hemisphere filtering. In focus/isolate mode, hidden context cannot receive surface picks; use the tree or the all-regions mode to select another region. Geometry remains retained: committed selections update draw indices and matching face keys, while hover only updates sparse GPU state. See [reference envelope preparation](../getting-started.md#shared-reference-envelope).

`fit_workarea=True` opts interactive windows into initial fitting within one monitor's usable area. It leaves offscreen dimensions unchanged; the library default is `False`.

## Independent anatomical context

Anatomical context uses `anatomy_presentation='major'`, `anatomical_context=` and `context_opacity=`. Prepare `AtlasContextSurface` records with `ibl_datoviz.context.AtlasContextSurface.from_geometry()` from verified shared surface geometry; these arrays use the atlas's unchanged normalization. `set_anatomical_context()` replaces the owned context transactionally, and `set_context_opacity()` changes only its presentation. `set_anatomy_presentation('detailed')` explicitly returns to the detailed atlas. Use viewer-owned scientific layer handles for observations alongside this independent anatomy context.

Major context is independent of mapping, regional scalar colors and fine selection. It retains authored colors, geometry and opacity while selection updates sparse tint state. Displayed coarse parents are highlighted directly without exposing their fine descendants; explicit fine selections receive a translucent overlay capped at 0.18. Context meshes retain true signed Allen parent identities for supported surface picks, rather than inventing fine reduced-mapping identities. Hidden context has no query coverage. Original-world hemisphere predicates follow the atlas midline policy; context stays at its reference position during fine-region explosion.

## Linked atlas layout

Use `app.slices.set_position()` for explicit-unit cursor navigation,
`app.slices.set_layers()` for composition, `app.slices.show_plane()` for physical
3D planes, and `app.slices.set_volume_opacity()` for an optional volume.

::: ibl_datoviz.viewer.AtlasViewer
    options:
      members:
        - from_packs
        - from_registered_assets
        - from_multiresolution_packs
        - from_anatomy_packs
        - from_slice_source
        - from_registered_slices
        - set_mapping
        - set_region_visible
        - set_region_color
        - set_region_opacity
        - set_hemisphere
        - render_offscreen
        - show
        - close

`AtlasViewer.from_registered_assets()` accepts a verified publication result. It combines an
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

## Lower-level slice data model

Import these explicit composition helpers from `ibl_datoviz.components`; ordinary
linked applications use `app.slices`.

::: ibl_datoviz.navigator.AtlasCursor

::: ibl_datoviz.navigator.AtlasSliceComposer
    options:
      members:
        - set_mapping
        - compose

::: ibl_datoviz.navigator.compose_atlas_slice

## Scientific viewer

::: ibl_datoviz.viewer.AtlasViewer
    options:
      members:
        - from_pack
        - from_assets
        - from_asset_set
        - add_points
        - add_paths
        - add_recording
        - add_region_values
        - layers
        - recordings
        - remove_layer
        - remove_recording
        - set_mapping
        - set_camera_angles
        - set_selection_presentation
        - set_selection_envelope
        - set_region_visible
        - show_region
        - hide_region
        - set_region_color
        - set_region_opacity
        - reset_region_style
        - set_hemisphere_visible
        - set_hemisphere
        - visible_region_ids
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
side metadata. Presentations without an ID in the active mapping are excluded
from rendering and picking, matching the web selector; switching mappings can
restore them when they have an ID.

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

Visibility filters private render triangle indices and their matching face link keys,
preserving atlas identity arrays, normalization and framing. Hidden faces and
faces with zero authored alpha are absent from picking as well as shading; an empty surface suppresses
drawing without unsupported zero-count uploads. Hemisphere controls use the
pack's original-world ML classifier, including its exact on-plane side and
single-presentation fallback. Private copies of crossing source triangles carry
side-specific colors, GPU state slots and signed pick keys, with the same fragment
coverage in shading and queries. Explosion does not change the classifier.
Canonical `mesh_data` arrays, world-point normalization and binary assets remain
unchanged; no vertices are cut, capped or nudged. Native FACE ordinals address the
filtered private draw mesh; signed link keys remain the regional identity.

RGB overrides retain source alpha; RGBA overrides replace authored region alpha,
scaled by global surface opacity. Regional opacity multiplies authored alpha.
Hover and selection preserve authored alpha scaled by global opacity. Selection
dims context independently; this decoration does not remove picking coverage.
Native alpha mode respects effective palette/scalar alpha, not only global opacity. An active
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

## Returned handles and selection events

Construct layer and recording handles through the viewer. Their native resources
remain viewer-owned; removal invalidates the handle. Subscriptions returned by
`app.selection.on_changed()` can be closed independently and end when the viewer
closes. A callback observes committed state, and callback errors do not roll it back.

::: ibl_datoviz.layers.LayerHandle

::: ibl_datoviz.layers.RecordingHandle

::: ibl_datoviz.regional_quantities.RegionalQuantityHandle

::: ibl_datoviz.controllers.SelectionState

::: ibl_datoviz.controllers.SelectionEvent

::: ibl_datoviz.controllers.SelectionSubscription

::: ibl_datoviz.slice_controller.SliceController
