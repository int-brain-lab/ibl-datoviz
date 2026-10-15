# Scientific viewer API proposal

Status: API direction and intended-use scripts approved by the user, October 15,
2026. Staged implementation is authorized. Generic payloads, owned handles,
recording composition, programmatic exact selection, linked observation tables
and Layers controls are now implemented; visual acceptance of these workflows remains open. Later sections
cover intended interfaces, including linked-layout and quantity work not yet
implemented. This is not an announcement of API stability. The earlier
`IBLWorkbench` sketches are superseded.

Use one main `AtlasViewer`, prepared scientific data objects, and handles for
recordings and layers. Python calls and GUI controls operate on the same retained
state. Keep anatomy, scientific observations, selection, cursor and camera
independent. This replaces the earlier provisional `IBLWorkbench` naming; it does
not add a second application controller beside the viewer.

## Approved scripts and executable examples

The [generic annotations](proposed_api/generic_annotations.py) and
[two IBL recordings](proposed_api/ibl_recordings.py) scripts record the reviewed
API and can now be called with prepared assets and frames. Executable module
clients are `examples.scientific_annotations` and `examples.ibl_recordings`;
see [scientific layer usage](api/components.md#viewer-owned-scientific-layers).
The IBL client requires independent source-frame evidence and never infers
registration from coordinate magnitudes or the atlas's frame. Both clients read
explicit local inputs before starting the GUI and perform no downloads.

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
        observation_refs=firing_rate_refs,  # retained by upstream preparation
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
| `AtlasViewer` | Application lifetime, fixed view layout, owned generic layers and recording groups, native presentation |
| `Points`, `Paths` | Prepared generic geometry, stable local IDs, frame and provenance; no required PID/EID |
| `Recording` | Prepared observations and provenance for one insertion within a session |
| Recording handle | Group visibility and access to that recording's available layer handles |
| Layer handle | Visibility, supported styling, scalar encoding and exact observation identities |
| `app.anatomy` | Anatomical context, mapping, hemisphere visibility and explosion |
| `app.selection` | Committed region and observation selection and change notifications |
| `app.tables` | Retained complete-population observation tables linked to exact selection |
| `app.camera` | Current view and the registered startup view used by reset |
| `app.slices` | Linked spatial cursor, slice composition and optional physical planes |

The viewer accepts validated assets from `ibl-anatomy`. Dataset discovery,
downloads, source fidelity checks, analysis and scientific aggregation belong in
data access or preparation. An IBL adapter produces the same payloads that a
script can construct from arrays; the core viewer does not require an AI-agent
runtime or a particular data loader.

## Generic layers first

`app.add_points(Points(...))` and `app.add_paths(Paths(...))` return viewer-owned
handles without requiring a recording or native scene/panel arguments. `Paths`
contains independently identified ordered polylines; each line has its own vertex
array. Its scalar/selection domain is the path ID, not an implicit vertex ID.
`add_recording` composes the same internal layer registry and ownership mechanisms
for supplied channels, clusters, sites and trajectories. Removing a recording
removes its children; removing a generic layer uses `app.remove_layer(handle)`.
A recording child is removed with its group, rather than detached behind the
recording handle. No second application facade is introduced.

Generic payload IDs may be integer or string labels and remain unique within
that payload. IDs are never renderer row indices. A generic payload without a
source identity receives an application-local attachment scope; this is not
advertised as persistent dataset provenance. Source-backed payloads retain
immutable source keys independently of their viewer attachment keys. Core
identities cannot require IBL PID, EID, channel/cluster kinds or integer-only IDs.
The optional IBL adapter translates the current IBL-specific `ObservationRef`
into that generic contract; it does not become the core reference type.

`layer.observation(original_id)` resolves an exact reference for that attachment.
Two layers using the same local ID stay distinct. Source-backed references also
retain the original scientific source identity. Repeated attachment of the same
recording source key is rejected explicitly for the first implementation; names
are display labels and never replacement keys. Explicit replacement is a later
API decision, not an implicit side effect of adding a layer.

## Scientific payloads and identities

```python
from ibl_datoviz import Recording, Channels, Clusters, Trajectory

recording = Recording(
    source=source_key,
    insertion_id=pid,
    session_id=eid,
    name="Subject / session / probe00",
    path=Trajectory(
        positions_um=path_xyz,
        frame=source_frame,
        provenance=path_provenance,
    ),
    channels=Channels(
        ids=channel_ids,
        positions_um=channel_xyz,
        allen_region_ids=channel_region_ids,
        frame=source_frame,
        provenance=channel_provenance,
    ),
    clusters=Clusters(
        ids=cluster_ids,
        positions_um=cluster_xyz,
        allen_region_ids=cluster_region_ids,
        frame=source_frame,
        provenance=cluster_provenance,
    ),
)
```

Each payload owns immutable array storage and snapshots its identity/provenance
metadata. Coordinates have an explicit `frame`: the shared anatomy reference-space
identifier plus a documented coordinate convention, axes, origin and units.
Reuse `ibl-anatomy` reference-space/grid contracts rather than minting another
atlas registry. The initial viewer accepts its atlas-world ML/AP/DV micrometre
convention and rejects unknown or incompatible frames. A caller must supply a
verified conversion upstream for other conventions; matching units or numeric
ranges do not establish compatible origin, orientation or registration.
Renderer normalization happens once at the presentation boundary, with the same
atlas transform for every layer, and never modifies the scientific payload.

Before constructors freeze, review a minimal immutable contract with these fields:

| Contract | Required information |
| --- | --- |
| Source key | Provider/dataset namespace, release version and immutable manifest/content identity |
| Recording key | Source key and original insertion/recording ID; session identity is separate |
| Observation identity | Source/recording scope where present, population and original ID; generic local scopes remain valid |
| Frame | Shared reference-space identity and explicit world-coordinate convention; verified conversion provenance where needed |
| Provenance | Input pins, derivation/position meaning, source validation status and declared uncertainties |

A frame assertion is distinct from a validated source claim. Current BWM 1.1.0
metadata lacks a complete frame declaration: `coordinate_convention="ibl-mlapdv-um"`
is an explicit legacy convention assertion, not proof of atlas registration.
The `prepare_bwm_recording` bridge additionally requires reviewed evidence for the
source coordinate interpretation and atlas reference; it fails without it. An
explicit reviewed legacy declaration can document its inferential assumptions.
Coordinate compatibility does not establish insertion alignment quality, exact
producer execution or scientific source-validation success. It returns the
reviewed core `Recording`, rather than permanently adding a parallel payload model.
Its immutable key/provenance snapshots must not depend on mutable detached source
tables. Reject disagreements between table identity and retained observation refs
rather than silently assigning new keys to existing observations.

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
Cluster positions declare their derivation: the current BWM adapter uses the
assigned channel location, not an inferred neuron soma position. Missing positions
remain rows in the scientific population. Only finite XYZ rows reach spatial
rendering, with an explicit row-to-original-identity map; table/programmatic
selection still addresses unpositioned observations. Controls report total and
positioned counts. A supplied population with no positioned rows retains its
handle and table identity but has no drawable marks. An absent population has no
layer handle. Neither case generates replacement coordinates.

Source/version, frame and provenance constructor types remain review decisions;
their semantics above are prerequisites for stage 1, not deferred adapter details.

## Recording and layer handles

```python
recording.path
recording.channels
recording.clusters
recording.sites

recording.set_visible(False)
app.remove_recording(recording)
```

Only supplied populations have available layer handles; missing-layer access
raises `UnavailableLayerError` (proposed name), rather than returning `None`.
A supplied but entirely unpositioned population is not an unavailable population.
Layer controls use a small shared vocabulary:

```python
layer.set_visible(True)
layer.set_color("#40dcfa")
layer.color_by(
    values,
    observation_refs=value_refs,  # required for externally sourced values
    name="Amplitude",
    units="µV",
    cmap="magma",
    limits=(0, 200),
    missing_color="#808080",
)
```

Uniform color identifies the layer. Scalar coloring identifies a named quantity
with explicit units, limits, colormap and missing-value behavior. Array values
align with the complete payload's stable observation order, including rows without
positions; mismatched lengths and infinities fail validation. Spatial upload
applies the geometry row map to scalars and identities together. Externally prepared
quantities must be explicitly joined by full scientific identity before this call,
including reordered values from the same source. Reject duplicate/foreign keys;
absent expected values become NaN in the complete population order. Length
agreement alone does not establish that join. Source-backed scalar calls require
`observation_refs` retained by the upstream preparation step and matching the
complete target reference sequence; shuffled, missing or foreign equal-length
references fail. These scalar references are immutable payload/source observation
keys, not the viewer-attachment references returned by `layer.observation`.
This initial API does not perform an implicit join. Bare arrays
remain convenient for explicitly ordered local annotations, where the caller
asserts the documented payload order. Missing scalars do not silently remove
observations or change the population. Switching color modes preserves geometry
and identity.

Controls specific to geometry keep their units in their names:

```python
recording.path.set_width_px(3)
recording.channels.set_radius_um(20)  # physical-sphere glyph capability
```

Paths retain their supported opaque stroke style. Point, region and volume
layers expose scalar coloring according to their capabilities; unsupported
operations fail explicitly. A common handle interface does not imply that every
renderer supports every material or quantity operation. Pixel-sized point sprites
use `set_size_px`; physical sphere glyphs use `set_radius_um`. The initial glyph
choice is declared at attachment, and capabilities are exposed before a control
is offered. Neither setter implies the other rendering mode or native picking.
Proposed defaults for review: generic `add_points` uses pixel point glyphs at
8 px; recording channels/sites/clusters use physical sphere glyphs at 20 µm
radius; paths use 3 px opaque strokes. These are display choices, not positional
uncertainties or anatomical cell sizes. A supported glyph does not establish
native scientific picking until its separate acceptance gate passes.

## Anatomy and selection

```python
app.anatomy.set_context("major")
app.anatomy.set_opacity(0.04)
app.anatomy.set_mapping("beryl")
app.anatomy.set_hemispheres(left=True, right=True)
app.anatomy.set_explode(0.3)

app.selection.set_regions(selected_region_ids, mapping="beryl")
app.selection.set_observations([recording.clusters.observation(cluster_id)])
app.selection.clear_observations()
app.selection.clear_regions()
app.selection.clear()  # both selection domains; never cursor/camera/filter state
subscription = app.selection.on_changed(handle_selection)
```

Context choices cover major structures, a reference shell and detailed anatomy.
They refer to validated shared assets, not a relabeling or fabricated merging of
fine meshes. Fine-region explosion preserves the stationary anatomical reference
behavior accepted in the demo.

Selection emphasizes anatomy without silently isolating it, hiding observations
or filtering a scientific population. Region references retain their mapping and
hemisphere meaning; exact observation references retain source and recording
scope. `set_regions(..., mapping=...)` declares the ID namespace and must match
the current displayed mapping; a mismatch fails before mutation. Change mapping
explicitly first rather than silently converting or reinterpreting IDs.
Mapping transitions follow the shared Allen/Beryl/Cosmos selector contract,
including its region-selection reset behavior. Observation selection, region
selection, spatial cursor position and scientific filtering remain different
operations. Initial transitions are explicit:

| Action | Selection result |
| --- | --- |
| Change mapping | Clear regions; retain exact observations |
| Hide a layer/group or change scalar styling | Retain both domains, including hidden observations |
| Remove a layer/recording | Clear only observation attachments owned by it |
| Reset camera or move cursor | Preserve both selection domains |
| Clear regions/observations | Clear only the named domain |
| Select an unpositioned observation | Retain exact identity; no fabricated spatial highlight |

`set_observations` replaces that domain with the supplied attached references;
unknown IDs and removed/foreign handles fail before mutation. Region and
observation selections can coexist. Removing a selected attachment also closes
its native links before issuing the committed selection notification. Selection
is attachment-specific initially: another layer displaying the same source
observation is not implicitly selected. Cross-view linking explicitly resolves
that source key to target attachments; it does not merge their ownership.

Notifications expose scientific identities rather than native visual indices.
GUI and Python edits produce the same authoritative state changes. Subscription
cleanup belongs to the viewer lifetime; callers can also close subscriptions
explicitly. The proposed immutable event contains previous/current region and
observation references, a reason and a monotonically increasing committed revision.
Emit once after retained state and native updates both commit; failure rolls back
without a success event. Callback exceptions cannot undo a completed commit, and
nested writes from callbacks are rejected initially to avoid reentrant partial
updates. Exact event field names/error reporting remain a contract-review item.

Table/programmatic exact selection is the first acceptance gate. Native picking
is a separate capability gate: the pinned engine's scientific identity queries
do not support styled point sprites, and `PointCollectionVisual` has no scientific
identity link map. Use a demonstrated supported glyph/query route with explicit
row/identity translation, or expose picking as unavailable. Do not upgrade the
engine to hide this distinction. Native acceptance must cover overlap, hidden
layers, multiple attachments, missing rows and original ID zero.

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
any workers it creates. Native resource mutation stays on the viewer/GUI thread. It releases layers and callbacks before destroying the scene. Removed
or closed handles fail clearly when reused. Updates validate and prepare their
replacement before replacing retained state, preserving existing transactional
failure behavior.

Refactor the implementation behind `AtlasViewer` into focused controllers and
adapters. Keep reusable component visuals available where useful; the scientist
API should not require native handles or immediate-mode GUI code. The accepted
Layers panel moves from `ScientificSceneReview` into package-level presentation
of the recording/layer state. The demo becomes a small client of that API.

The dependency boundaries are:

| Layer | Owns | Must not depend on |
| --- | --- | --- |
| Shared data access | Catalogs, pinned releases, codecs, source/signal validation and prepared metadata | Viewer, GUI, agent execution |
| Optional IBL adapter | EID/PID/session semantics, source-to-payload conversion and explicit joins | Agent execution, native scenes |
| Core payloads/state | Generic identity, frame checks, layer/selection transitions | IBL reader, codecs, AI runtime |
| Viewer presentation | Datoviz resources, GUI, native links and commit/cleanup mechanics | Dataset discovery, implicit scientific analysis |
| Scientific apps / AI agent | Compose readers, adapters, viewer and explicit analyses | Private renderer internals |

The reusable reader currently resides in `ibl-ai-agent-next` and is imported
through `ibl_ai_agent.access`. Preserve this tested seam for both clients before
physically extracting a standalone data distribution. Do not add a second reader,
codec, catalog or copy of the compressed releases to this repository. Trial/event
and signal loading stays explicit, outside GUI callbacks; validation requirements
are passed through unchanged. Unknown metadata validation and passed signal
validation remain separate facts. Common-clock mapping does not imply measured
synchronization accuracy. Background results must carry source/request identities
and be ignored after removal/close; workers stop before native scene destruction.

An agent can later generate small apps through these same public interfaces and
a dedicated authoring skill. That requires stable examples and review gates first,
not an agent dependency in the viewer or a new plugin framework now.

Datoviz remains responsible for generic rendering, controllers, picking and GUI
primitives. IBL semantics stay in `ibl-datoviz` and shared anatomy/data packages.
Add engine functionality only for a demonstrated generic gap, with its own
validation, before deliberately updating the native package's immutable pin.

## Implementation stages

| Stage | Deliverable | Acceptance gate |
| --- | --- | --- |
| 0 | Review immutable identity/frame/provenance contracts, generic and IBL scripts, selection transitions and capabilities | Approve scripts; inspect two actual insertion metadata results, original IDs, missingness and declared frames before freezing constructors |
| 1 | Owned generic point/path handles; recording composition through the optional adapter; retained layer/selection state and committed events, programmatic exact selection and package-level controls | Reproduce accepted demo; exercise both scripts, independent visibility, scalar alignment, selection transitions, rollback and cleanup; no IBL imports for generic use |
| 2 | Linked observation tables and capability-specific native exact picking | Match original source identities across tables/scene; validate native overlap, hidden/missing rows and multi-recording linking; preserve scientific population |
| 3 | Consolidate linked slices under the viewer; regional and voxel quantities; supplied alignment comparisons | Review cursor/selection semantics, reduction, coverage, missingness and colormaps through dedicated scientific workflows |

The shared metadata prerequisite is now implemented locally: `ibl-ai-agent-next`
commit `3cdb374` exposes pinned BWM recording metadata, and this repository's
`818e286` adds the optional `BwmSource` adapter. The interim `BwmRecording` is an
integration result, not an approved replacement for the core payload contract.
Read-only checks exercised one insertion with 384 channels/459 released units and
another with 96 channels/2 units, preserving source rows and original IDs.
This does not establish verified atlas registration or native picking acceptance.
Signal-validation failures must not trigger an unvalidated direct-file fallback.
The old `IBLWorkbench` experiment remains ignored engineering evidence, not an
additional facade to merge or publish.

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
- Review the two scripts, generic local/source-backed identity scopes and the
  minimal immutable event contract; approve selection transitions above.
- Confirm the BWM-to-core bridge name and the authority supplying its verified frame.
- Place the hover toggle in the public interaction API.
- Specify volume quantities and supplied alignment workflows at their later gate;
  their requirements must not force speculative renderer abstractions into stage 1.

The next user review is the working generic annotation and recording workflows.
Native picking and the unified linked-layout facade retain separate later gates.
The current supported API remains documented in the [API reference](api/index.md).

## Architecture audit of the consolidated proposal

An independent GPT-6.1 Sol subagent at high reasoning reviewed the boundaries,
current reader/adapter code, revised proposal, roadmap and both scripts on
October 15, 2026. Its final reread reported no remaining P1/P2 architecture or
consolidation findings after revisions. The review addressed generic identities,
source versus attachment scope, verified frames, scalar row alignment, selection
transitions, committed events and resource ownership. This is a design audit,
not approval of the proposed API or evidence that its interfaces are implemented.
The user approved the scripts and architecture after this audit; verified
BWM frame evidence and capability-specific native picking retain separate gates.
