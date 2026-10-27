# Use the viewer in an analysis

Start with prepared coordinates and measurements, inspect them in anatomy, and
return exact selected observations to Python. The viewer consumes scientific
outputs; it does not discover datasets, estimate alignment or compute firing rates.

## Bring your own arrays or DataFrame columns

Use the configured Python/native pairing described in [Getting started](getting-started.md).
`atlas_assets` below is an existing verified materialized asset set. Positions
must be in the viewer's declared ML/AP/DV micrometre coordinate frame. Convert
and establish that frame upstream; do not relabel unknown coordinates.

```python
from ibl_datoviz import AtlasViewer, Points

with AtlasViewer(atlas=atlas_assets) as app:
    layer = app.add_points(
        Points(ids, positions_um, app.frame, {"position_meaning": position_description}),
        name="My analysis",
    )
    layer.color_by(values, name="Firing rate", units="Hz",
                   cmap="viridis", limits=(0, 30))
    app.tables.show(layer)
    app.show()
    selected = app.selection.to_records()
```

For a DataFrame, `ids = df.index.tolist()`,
`positions_um = df[["ml_um", "ap_um", "dv_um"]].to_numpy()` and
`values = df["firing_rate_hz"].to_numpy()` are sufficient, provided they retain
the same complete row order. Pandas is optional. Integer and string IDs remain
distinct; IDs must be unique within a payload. NaN coordinates and values retain
their rows, with unavailable locations and measurements represented explicitly.

Generic points have attachment-local identities. For reusable source identities,
supply `SourceObservationKey` records, or attach an explicitly prepared `Recording`
with channels/clusters/sites using `app.add_recording()`. Source-keyed scalar
arrays require the complete matching `observation_refs` sequence. See
[data models](api/data-models.md) and [the recording example](review-apps.md#multiple-recordings-and-linked-selection).

## Return selections to an analysis

`app.selection.to_records()` returns detached dictionaries in committed selection
order. Every row includes the typed original ID, attachment ID, optional full
source key, declared frame, supplied position and Allen region annotation,
retained measurement/value/units, visibility and provenance. Site memberships
are preserved when supplied. A missing measurement is distinct from no supplied
measurement; JSON uses `null` for nonfinite numbers.

Hidden rows and rows without positions remain selected and exportable. Export
does not apply table search, sorting or a selected-rows display mask as scientific
filtering. Paths export their full supplied vertices, not an invented centroid.
Attached copies of the same source remain distinct attachments.

```python
def changed(event):
    rows = app.selection.to_records()
    # Join by the full source_key, not an unscoped local cluster ID.
    update_my_analysis(rows)
    app.selection.export_json("results/selection.json")

subscription = app.selection.on_changed(changed)
app.show()
subscription.close()
```

Register before `show()`, on the viewer's owning thread. Callbacks run after a
successful selection commit. Reading/exporting is supported inside callbacks;
reentrant viewer mutations are rejected. Callback failures do not undo scientific
selection; inspect `app.selection.callback_errors`. Keep expensive analysis outside
the GUI callback. Viewer close releases subscriptions. Export inside the callback
if your runner closes the viewer before returning from `show()`.

`export_json()` atomically replaces the file and includes separately namespaced
region selections, the revision and observation records. It is an analysis
artifact, not a saved workspace or a selection-import format.

## Locate an observation in anatomy

Construct a linked viewer with an explicit compatible slice source or volume pack,
then call `app.slices.locate(layer.observation(original_id))`. The inspector also
offers **Show in slices** for one positioned point/channel/cluster/site. This moves
the cursor to the nearest grid location without changing observation selection,
region selection, layer visibility or camera orientation. The supplied observation
coordinate remains unchanged. Missing positions, paths, foreign/removed references
and out-of-grid coordinates fail explicitly. Declared source location meaning and
alignment uncertainty continue to apply; a cluster location is not automatically
an independently measured soma position.

## Export a figure with its source record

Prepare a fresh viewer and configure its layers, measurements, selections and
camera before calling:

```python
app.export_figure("results/figure-01", title="My supplied measurement")
```

The directory must be new. It contains:

- `scene.png`: the scientific viewport without application controls;
- `figure.svg`: the embedded PNG, title and active observation-layer legends;
- `provenance.json`: source identities, frame evidence, original IDs, geometry/value
  hashes, measurement scales/missingness, selection, mapping, camera model, cursor,
  anatomy presentation and hashes of the two image files.

Set `width` and `height` at viewer construction for the raster resolution. Call
before `show()` or `render_offscreen()`; this first version does not export a live
docked viewport or reproduce an interactively moved camera in a new viewer. SVG
embeds raster geometry. The source data and executable analysis are not bundled,
and the receipt is not an alignment validation or restorable workspace.
Legends cover viewer-owned observation layers; regional/volume encodings need
their own figure explanation.

For comparisons, pass the same scientifically chosen `limits` to each compatible
layer's `color_by()`. This shares presentation limits without normalizing,
filtering or aggregating the underlying values. State any upstream reduction
and missingness policy in the payload provenance.

## A complete offline BWM example

The example uses the existing hash-checked 192-row fixture. Each row is a prepared
co-located channel group, and its measurement is the mean firing rate of assigned
good units under the fixture's recorded derivation. These are not original cluster
IDs or a newly computed analysis. Source validation and alignment quality remain
unknown. No signals, network services, optional reader or pandas are required.

After native pairing and asset preparation, run from the repository:

```bash
python -m examples.analysis_roundtrip build/atlas-d070 \
  --context-root build/allen-major-context \
  --volume-root build/allen-ccf-2017-50um \
  --ui-scale 1.25 --output build/my-selection
```

Select rows in the data table, use **Show in slices** on a single selection, and
Ctrl/Cmd-click to extend it. Each committed selection updates
`build/my-selection/selection.json` with exact identities and supplied values.
The terminal prints the selected original site IDs.

For a bounded offline figure of explicitly chosen rows:

```bash
python -m examples.analysis_roundtrip build/atlas-d070 \
  --context-root build/allen-major-context \
  --volume-root build/allen-ccf-2017-50um \
  --select-site 383 --select-site 381 --locate-site 381 \
  --output build/my-figure-selection --figure-dir build/my-new-figure
```

Site 383 has no supplied firing-rate value; site 381 has a finite value. Both
remain in the export. The offline command uses its explicitly authored camera;
it does not restore a prior GUI session. Ordinary three-frame startup is available
with `--frames 3`, but does not establish interaction quality or macOS rendering.
