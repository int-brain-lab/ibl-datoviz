# API overview

Use one `AtlasViewer` with a fixed `layout="3d"` or `layout="linked"`, prepared
scientific payloads, and viewer-owned layer handles. Python calls and GUI controls
operate on the same retained state. Region selection, observation selection,
cursor position, and camera navigation remain independent.

| Object | Responsibility |
| --- | --- |
| [`AtlasViewer`](viewer.md) | Application lifetime, layout, owned native resources and controllers |
| [`Points`, `Paths`](components.md#viewer-owned-scientific-layers) | Immutable geometry, original IDs, frames and provenance |
| `Recording`, `Channels`, `Clusters`, `Sites`, `Trajectory` | Prepared insertion-scoped scientific populations |
| `WorldFrame`, `SourceKey`, `SourceObservationKey` | Explicit coordinate evidence and immutable scientific identity |
| `LayerHandle`, `RecordingHandle` | Viewer-owned mutable presentation of prepared populations |
| `RegionValues`, `RegionalQuantityHandle`, `MappedRegionValues` | Prepared regional quantities, presentation and mapped coverage |
| `SelectionState`, `SelectionEvent`, `SelectionSubscription` | Committed state, change events and explicit callback lifetime |
| [`AtlasMesh`, `AtlasEnvelope`, `AtlasSliceSource`](data-models.md) | Prepared anatomy and registered slice inputs |

The package's explicit `ibl_datoviz.__all__` defines the supported top-level
names. `app.anatomy`, `app.camera`, `app.selection`, `app.slices`, and `app.tables`
provide the relevant controls; layers and recordings return owned handles.
Use viewers as context managers, or call `close()` explicitly.

## Lower-level components

`ibl_datoviz.components` exposes caller-owned rendering primitives and diagnostic
adapters: `PointCollection`, `PointCollectionVisual`, `SampledPlane`,
`SampledPlaneVisual`, `InsertionTrajectory`, `InsertionCollectionVisual`,
`AtlasTreeModel`, `AtlasCursor`, `AtlasSliceComposer`, and `compose_atlas_slice`.
Visuals borrow an existing scene and panel and must close before scene destruction.
`ProbeSites` and `AtlasRegionValues` remain here as legacy preparation helpers;
new scientific application code uses the richer payloads and owned handles.

## Migration from the previous API

This development refactor deliberately breaks compatibility. Import lower-level
objects from `ibl_datoviz.components` instead of the package root. Replace the
separate `LinkedAtlasNavigator` facade with `AtlasViewer(layout="linked", ...)`
or the linked-source factories documented in [volume-free navigation](volume-free.md).

Replace viewer probe and insertion setters with `add_points`, `add_paths`, or
`add_recording`, then edit the returned handles. Use `RegionValues` and
`add_region_values` for regional scalars. These migrations preserve source IDs,
frames, and declared units; they must not infer scientific provenance or replace
regional selection with observation selection implicitly. Low-level diagnostic
clients may continue composing visuals explicitly through `components`.

The optional `ibl_datoviz.ibl` module supplies `BwmSource` and
`prepare_bwm_recording`. Importing the core API does not require the shared IBL
reader or an AI runtime. `ibl-anatomy` validates and decodes packaged anatomy;
`ibl-datoviz` owns presentation and interaction. Coordinate-to-label computation
belongs in data preparation or an explicit compatible anatomy reader.
