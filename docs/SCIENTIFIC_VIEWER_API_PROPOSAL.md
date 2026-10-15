# Scientific viewer API proposal

Status: proposed for API review, October 15, 2026. The recording-context demo has
been accepted visually. The interfaces below describe the intended refactor;
they are not implemented APIs or an announcement of API stability. Recording this
proposal does not start its implementation.

Use one main `AtlasViewer`, prepared scientific data objects, and handles for
recordings and layers. Python calls and GUI controls operate on the same retained
state. Keep anatomy, scientific observations, selection, cursor and camera
independent. This replaces the earlier provisional `IBLWorkbench` naming; it does
not add a second application controller beside the viewer.

## Scientific workflow

A scientist should be able to place one or more recordings in anatomical context,
show their available observations, color a quantity and select anatomy without
learning renderer configuration. The accepted demo supplies the initial visual
defaults: coarse colored anatomy, restrained transparency, independently visible
scientific layers, a region browser, dockable layer controls and consistent camera
interaction.

```python
from ibl_datoviz import AtlasViewer

# A data adapter or explicit preparation step supplies these recordings.
with AtlasViewer(
    atlas=atlas_assets,
    anatomy="major",
    mapping="beryl",
    layout="3d",
) as app:
    first = app.add_recording(
        recording_a,
        name="First recording",
        show=("path", "channels"),
    )
    second = app.add_recording(
        recording_b,
        name="Second recording",
        show=("path", "channels", "clusters"),
    )

    first.path.set_color("#ffd048")
    first.path.set_width_px(3)
    second.channels.color_by(
        firing_rates,
        name="Mean firing rate",
        units="Hz",
        cmap="viridis",
        limits=(0, 20),
    )
    second.clusters.set_visible(False)
    app.show()
```

`show` specifies initial visibility. Other supplied layers remain available through
their handles. Requested unavailable layers fail explicitly; the viewer never
substitutes observations from another recording. A recording's group visibility
temporarily hides its layers and preserves their individual visibility settings
for restoration.

## Public object boundaries

| Object | Responsibility |
| --- | --- |
| `AtlasViewer` | Application lifetime, fixed view layout, recording and quantity layers, native presentation |
| `Recording` | Prepared observations and provenance for one insertion within a session |
| Recording handle | Group visibility and access to that recording's available layer handles |
| Layer handle | Visibility, supported styling, scalar encoding and exact observation identities |
| `app.anatomy` | Anatomical context, mapping, hemisphere visibility and explosion |
| `app.selection` | Committed region and observation selection and change notifications |
| `app.camera` | Current view and the registered startup view used by reset |
| `app.slices` | Linked spatial cursor, slice composition and optional physical planes |

The viewer accepts validated assets from `ibl-anatomy`. Dataset discovery,
downloads, source fidelity checks, analysis and scientific aggregation belong in
data access or preparation. An IBL adapter produces the same payloads that a
script can construct from arrays; the core viewer does not require an AI-agent
runtime or a particular data loader.

## Scientific payloads and identities

```python
from ibl_datoviz import Recording, Channels, Clusters, Trajectory

recording = Recording(
    insertion_id=pid,
    session_id=eid,
    name="Subject / session / probe00",
    path=Trajectory(
        positions_um=path_xyz,
        provenance=path_provenance,
    ),
    channels=Channels(
        ids=channel_ids,
        positions_um=channel_xyz,
        allen_region_ids=channel_region_ids,
        provenance=channel_provenance,
    ),
    clusters=Clusters(
        ids=cluster_ids,
        positions_um=cluster_xyz,
        allen_region_ids=cluster_region_ids,
        provenance=cluster_provenance,
    ),
)
```

Each payload owns immutable array storage. Coordinates are atlas-world ML/AP/DV
micrometres and identify their reference space through validated provenance. The
viewer rejects incompatible frames. Coordinate normalization happens once in the
presentation adapter and does not modify the scientific payload.

Session IDs and insertion IDs remain distinct. Channel and cluster IDs retain
their original source identities, scoped by source/version and recording.
Repeated coordinates are valid observations and do not authorize deduplicating
channels. Registering recordings must not accidentally replace another source's
observations because their local IDs happen to match.

An explicit `Sites` payload represents prepared physical sites or declared
channel groups. It keeps group IDs, grouping provenance and source membership
where supplied. It is distinct from `Channels`. The current 192-group fixture
must not become 192 purported original channels. Unknown membership remains
unknown rather than receiving invented source IDs.

A supplied ordered path identifies its coordinate derivation. Connecting channel
locations does not make it an independently reconstructed histology trace.
Cluster locations retain their meaning as estimates from recordings, rather
than exact neuron soma positions. Geometry can be absent: missing coordinates
disable the corresponding spatial layer rather than generating replacements.

The exact provenance record and source/version key types need review before
freezing the payload constructors.

## Recording and layer handles

```python
recording.path
recording.channels
recording.clusters
recording.sites

recording.set_visible(False)
app.remove_recording(recording)
```

Only supplied populations have available layer handles; missing-layer access has
a defined explicit failure. Layer controls use a small shared vocabulary:

```python
layer.set_visible(True)
layer.set_color("#40dcfa")
layer.color_by(
    values,
    name="Amplitude",
    units="µV",
    cmap="magma",
    limits=(0, 200),
    missing_color="#808080",
)
```

Uniform color identifies the layer. Scalar coloring identifies a named quantity
with explicit units, limits, colormap and missing-value behavior. Array values
align with the payload's stable observation order; mismatched lengths and
infinities fail validation. Missing scalars do not silently remove observations
or change the population. Switching color modes preserves geometry and identity.

Controls specific to geometry keep their units in their names:

```python
recording.path.set_width_px(3)
recording.channels.set_radius_um(20)
```

Paths retain their supported opaque stroke style. Point, region and volume
layers expose scalar coloring according to their capabilities; unsupported
operations fail explicitly. A common handle interface does not imply that every
renderer supports every material or quantity operation.

## Anatomy and selection

```python
app.anatomy.set_context("major")
app.anatomy.set_opacity(0.04)
app.anatomy.set_mapping("beryl")
app.anatomy.set_hemispheres(left=True, right=True)
app.anatomy.set_explode(0.3)

app.selection.set_regions([-718], mapping="allen")
app.selection.clear()
subscription = app.selection.on_changed(handle_selection)
```

Context choices cover major structures, a reference shell and detailed anatomy.
They refer to validated shared assets, not a relabeling or fabricated merging of
fine meshes. Fine-region explosion preserves the stationary anatomical reference
behavior accepted in the demo.

Selection emphasizes anatomy without silently isolating it, hiding observations
or filtering a scientific population. Region references retain their mapping and
hemisphere meaning; exact observation references retain source and recording
scope. Mapping transitions follow the shared Allen/Beryl/Cosmos selector contract,
including its selection-reset behavior. Observation selection, region selection,
spatial cursor position and scientific filtering remain different operations.

Notifications expose scientific identities rather than native visual indices.
GUI and Python edits produce the same authoritative state changes. Subscription
cleanup belongs to the viewer lifetime; callers can also close subscriptions
explicitly. The precise observation-selection methods and event payloads belong
to the second implementation stage below.

## Camera interaction

```python
app.camera.set_view("recording")
app.camera.reset()
```

Capture startup orientation, pan and zoom once when the view is created.
Pre-show camera configuration determines that startup view. Later camera edits
change the current pose without silently redefining startup. The reset button,
double-click and Python reset use that same baseline and preserve scientific
layers and selection.

Right/middle dragging remains proportional to pixels at the rotation pivot's
current depth. The virtual trackball follows the panned pivot. Hover feedback
starts disabled and remains available without dense geometry updates. The
placement of its public toggle is a review item: the earlier conversational
`app.camera.set_hover_enabled(False)` sketch mixes interaction with camera pose.

## Linked slices

```python
with AtlasViewer(
    atlas=atlas_assets,
    volumes=atlas_volumes,
    layout="linked",
) as app:
    recording = app.add_recording(
        recording_a,
        show=("path", "channels"),
    )
    app.slices.set_position(ap=120, ml=80, dv=100, units="voxel")
    app.slices.set_layers(
        anatomy=True, annotations=True, boundaries=True,
    )
    app.slices.show_plane("ap", in_3d=True)
    app.show()
```

Use the same recording handles and selection model in 3D-only and linked layouts.
Choose the panel layout at construction; changing presets or visibility does not
recreate the application or its panels. A 3D-only application need not load volume
assets. Linked navigation uses their verified affine and coverage, with explicit
coordinate units. Cursor movement does not commit region selection. Continuous
grayscale can interpolate; categorical labels retain nearest sampling.

## Regional and voxel quantities

```python
regions = app.add_region_values(
    region_values,
    name="Regional firing rate",
    mapping_reduction="weighted_mean",
)
regions.color_by("value", cmap="viridis", limits=(0, 20))
```

The regional payload supplies source Allen identities, values, units, missingness
and explicit aggregation weights. The selector `"value"` refers to that declared
payload field. Mapping reduction must preserve the intended population; a mean
of region means is not silently substituted for a population-weighted mean.
Scientific aggregation remains separate from display mapping and selection.

Voxel quantities will use a corresponding volume-layer boundary with an explicit
grid, affine, reference space, quantity metadata and missingness. Its constructor
and transfer-function API are not specified yet. Supplied alignment comparisons
also remain a later workflow: the viewer displays results and provenance rather
than calculating alignment.

## Ownership and architecture

The viewer owns native scenes, layer resources, GUI handles, subscriptions and
workers. It releases layers and callbacks before destroying the scene. Removed
or closed handles fail clearly when reused. Updates validate and prepare their
replacement before replacing retained state, preserving existing transactional
failure behavior.

Refactor the implementation behind `AtlasViewer` into focused controllers and
adapters. Keep reusable component visuals available where useful; the scientist
API should not require native handles or immediate-mode GUI code. The accepted
Layers panel moves from `ScientificSceneReview` into package-level presentation
of the recording/layer state. The demo becomes a small client of that API.

Datoviz remains responsible for generic rendering, controllers, picking and GUI
primitives. IBL semantics stay in `ibl-datoviz` and shared anatomy/data packages.
Add engine functionality only for a demonstrated generic gap, with its own
validation, before deliberately updating the native package's immutable pin.

## Implementation stages

| Stage | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1 | Viewer facade, payloads and recording/layer handles; paths, sites/channels, scalar coloring, anatomy, camera and retained Layers GUI | Reproduce the accepted demo through a short public script; compare GUI and Python edits and independent recording visibility; test identities, ownership, rollback and reset |
| 2 | Source metadata adapter, multiple-recording examples, exact channel/cluster selection, linked tables and events | Use matching source-scoped metadata; validate coordinates and associations; link exact observations without changing population or borrowing another insertion's geometry |
| 3 | Consolidate linked slices under the viewer; regional and voxel quantities; supplied alignment comparisons | Review cursor/selection semantics, reduction, coverage, missingness and colormaps through dedicated scientific workflows |

Stage 1 establishes handles that can own several recordings; stage 2 exercises
them with live source-backed workflows. Source metadata access is a prerequisite
for that integration: the inspected data interface does not yet expose all
required channel coordinates and cluster associations. Signal-validation failures
must not trigger an unvalidated direct-file fallback.

Keep native implementation and focused commits on `feature/datoviz-v04`. Generic
engine changes, if needed, remain on `rc4/scientific-3d`. Shared anatomy assets
retain their own catalog and binary provenance. Choose the data-adapter repository
and branch explicitly before editing it; the viewer must not embed a duplicate
data reader. Publish only under the applicable repository authorization rules.

This early package can break compatibility. Replace the old monolithic setter
surface deliberately and update examples/tests/docs with the new API instead of
adding an indefinite compatibility layer. In particular, migrate
`set_probe_data`, per-insertion setters and the separate navigator facade into
the relevant data objects and handles. Preserve the existing native ownership and
scientific identity contracts through that migration.

## Review items before freezing the API

- Confirm the insertion-scoped meaning and source/version identity of `Recording`.
- Finalize provenance/reference-space types, explicit site-group membership and
  the behavior of unavailable layer access.
- Confirm handle names, `show` defaults, uniform/scalar color transitions and
  physical versus screen-space glyph controls.
- Place the hover toggle in the public interaction API and define observation
  selection events without conflating them with regions or the spatial cursor.
- Specify volume quantities and supplied alignment workflows at their later gate;
  their requirements must not force speculative renderer abstractions into stage 1.

The next action is reviewing these interfaces and contracts before implementation.
The current supported API remains documented in the [API reference](api/index.md).
