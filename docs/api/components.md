# Scientific layers and reusable components

## Viewer-owned scientific layers

Use generic `Points` and `Paths` when the viewer should own their native resources.
Their IDs can be integer or string labels. Repeated positions and rows with missing
coordinates remain scientific observations. Only finite rows are rendered, and
scalar values align with the complete population, including missing positions.

```python
from ibl_datoviz import AtlasViewer, Points, Paths

with AtlasViewer(atlas=verified_assets, mapping="beryl") as app:
    points = app.add_points(
        Points(ids=("a", "b"), positions_um=xyz, frame=app.frame,
               provenance={"kind": "user annotation"}),
        name="Targets", glyph="point",
    )
    points.set_size_px(8)
    points.color_by([0.2, 0.8], name="Confidence", units="1",
                    cmap="viridis", limits=(0, 1))
    paths = app.add_paths(
        Paths(ids=("route",), positions_um=(route_xyz,), frame=app.frame,
              provenance={"kind": "user annotation"}),
        name="Candidate route",
    )
    paths.set_width_px(3)
    app.selection.set_observations([points.observation("b")])
    app.show()
```

`app.frame` can locate annotations authored in that atlas. It must not be copied
onto external source coordinates to claim frame agreement. Source payloads need a
`WorldFrame` with reviewed evidence for the reference, origin, axes and units. A
legacy convention declaration can cite authoritative source code and state its
remaining assumptions. This establishes an explicit coordinate interpretation;
it does not establish individual insertion alignment quality or scientific source
validation. The frame records caller-supplied evidence, not a validation service.

`add_recording(recording, show=("channels", "clusters"))` composes supplied
populations using the same owned registry. `show` sets initial visibility;
unshown populations retain handles. An absent population raises
`UnavailableLayerError`; an entirely unpositioned supplied population retains its
IDs and handle. Recording observations default to physical sphere glyphs with
`set_radius_um(20)`. Point sprites use `set_size_px`, paths use `set_width_px`,
and unsupported operations fail. Inspect `layer.capabilities`; native scientific
picking is currently unavailable for these handles. Exact ID selection is available
through Python and the Layers panel, including hidden/unpositioned observations.

Source-backed scalar calls require `observation_refs=payload.observation_keys`
from the upstream quantity preparation in exactly the full payload order. Reject
shuffled/foreign references rather than using length as evidence of an identity
join. Missing scalar values receive an explicit missing color. Uniform color,
visibility and scalar edits preserve selection. The initial native implementation
rebuilds candidate visuals transactionally; dense animation performance is not
qualified yet.

`app.selection.set_regions(ids, mapping=app.mapping)` selects only regions;
`set_observations(refs)` selects exact attachments. `clear_regions`,
`clear_observations` and `clear` have explicit scopes. Mapping changes clear
regions while retaining observations; removal prunes only owned attachments.
`on_changed(callback)` returns a closable subscription. Events contain immutable
previous/current states, a reason and a committed revision. Callback failures
are recorded in `app.selection.callback_errors` without undoing committed state;
reentrant viewer writes and writes from another thread are rejected. All resources
and subscriptions close before scene destruction, including deferred native
callback shutdown.

The configured interactive launcher is:

```sh
just review annotations --strict --ui-scale 1.5
```

Run the new examples as modules from the repository root in the configured native environment:

```sh
python -m examples.scientific_annotations /path/to/atlas-assets \
    --context-root /path/to/major-surfaces
python -m examples.ibl_recordings /path/to/atlas-assets \
    --release /path/to/bwm-release --pid FIRST_PID --pid SECOND_PID \
    --frame-evidence /path/to/reviewed-source-frame.json
```

Both support `--frames 3`, `--offscreen PNG` and `--report JSON`. They never
fetch datasets. Major anatomy requires the prepared context surfaces; otherwise
they explicitly choose detailed anatomy. The IBL example requires the optional
shared reader and reviewed source coordinate-frame evidence. A frame JSON has the fields
`reference_space_id`, `coordinate_convention` and `provenance`, whose
`verification` mapping records nonempty `method` and `evidence` strings. Supplying
that document does not change metadata or signal source-validation status. If
`provenance.source_manifest_sha256` or `provenance.source_insertion_ids` scopes a
BWM declaration, the bridge rejects recordings outside those reviewed identities.

The shared reader owns integrity/validation and codecs; `BwmSource` retains all
source metadata and `prepare_bwm_recording` snapshots it into core payloads. BWM
cluster positions currently mean assigned channel locations, not neuron somata.
Signal access remains an explicit upstream `source.spikes(..., requirements=...)`
call; the example performs metadata reads only, before starting the GUI.

## Borrowed-scene point collections and sampled planes

`PointCollection` and `SampledPlane` are independent CPU payloads. Their constructors
copy inputs into immutable contiguous arrays without changing the caller's write
flags. Positions and corners remain in atlas-world micrometres. These components
do not change `ProbeSites`, its stable site IDs, signed Allen labels, linked tables,
or existing non-empty payload requirement.

```python
from ibl_datoviz import PointCollection, PointCollectionVisual

points = PointCollection.from_arrays(positions_um, rgba, sizes_px=3.0)
display = PointCollectionVisual(
    dvz, scene, panel, points,
    transform=atlas_mesh.normalize_points,
    alpha_mode="blended",
    depth_test=True,
)
display.update_colors(new_rgba)
display.update_sizes(4.0)
display.set_visible(False)
display.replace(replacement_points)
display.close()  # Before caller scene destruction.
```

Colors are integer RGB or RGBA channels in `[0, 255]`; RGB expands to fully opaque
RGBA. Positions have finite shape `(n, 3)` and pixel diameters are finite and
positive, supplied as a scalar or `(n,)` array. Empty `(0, 3)` positions and matching
empty colors are valid. `replace()` uploads all attributes together when point
counts change, including smaller and larger replacements. An empty replacement
hides the visual without calling unsupported native zero-count setters. Restoring
data replaces the full upload before restoring visibility. Authored visibility is
independent of empty suppression.

`update_colors()` uploads only color data and `update_sizes()` uploads only pixel
diameters. These operations preserve existing owned immutable geometry internally;
they do not repeat the display transform or upload positions. Native upload failure
leaves the public payload unchanged.

`PointCollection.from_scalars(positions_um, values, palette=lut256,
value_range=(low, high), sizes_px=3.0)` requires an explicit 256-entry integer RGB
palette and increasing finite range. It normalizes in float64, interpolates between
adjacent LUT entries, and rounds each channel using `floor(x + 0.5)`, matching the
paper website's mapping of float32 artifacts promoted to JavaScript numbers.
Out-of-range finite values clip; NaNs use the low RGB with alpha zero; infinities
are rejected. Range, scientific units, legends, and scalar reduction remain caller
policy. The payload retains the resulting colors rather than original scalars.

```python
from ibl_datoviz import SampledPlane, SampledPlaneVisual

plane = SampledPlane.from_arrays(corners_um, rgba_image, sampling="nearest")
display = SampledPlaneVisual(
    dvz, scene, panel, plane,
    transform=atlas_mesh.normalize_points,
    depth_policy="overlay",
)
display.update_pixels(new_rgba_image)
display.update_corners(new_corners_um)
display.replace(None)  # Empty plane: suppress drawing.
display.replace(plane)
display.close()
```

Use an explicit physical plane when its position should participate in the 3D
scene's depth and transparency:

```python
display = SampledPlaneVisual(
    dvz, scene, panel, plane,
    transform=atlas_mesh.normalize_points,
    depth_policy="physical",
    alpha_mode="wboit",
)
```

Plane corners are a finite rectangle of shape `(4, 3)`, ordered top-left,
bottom-left, top-right, bottom-right. RGBA pixels have non-empty shape
`(height, width, 4)`; row zero appears at the top edge. `sampling` is `nearest`
or `linear`. Geometry validation uses a relative tolerance of `1e-5` for rectangle
closure and orthogonality. The transform receives world coordinates once per
geometry replacement and must return finite coordinates with the same shape.
With `transform=None`, coordinates are passed through explicitly; callers displaying
a centered physical slice can construct its rectangle in their chosen 2D coordinates.

Same-sized textures update in place. Changing dimensions creates a new sampled
field, binds it to the existing visual, and destroys the old field after success.
Corner-only updates retain the field and pixels. An empty plane retains native
storage while hidden; `update_pixels()` and `update_corners()` require a non-empty
payload, restored with `replace()` first. Failed replacements restore the previous
geometry, pixels, field binding, sampling, and visibility. A failed rollback closes
the component and raises an error without destroying the caller's scene.

## Native rendering modes

The configured native pairing supports the following component behavior. The
`capabilities` record exposes supported alpha modes and effective depth behavior;
it describes this adapter, rather than certifying every native backend.

| Component mode | Depth test | Depth write | Transparent composition |
| --- | --- | --- | --- |
| Points, `opaque`, depth enabled | Yes | Yes | Opaque pass |
| Points, `blended`, depth enabled | Yes | No | Source-over, draw-order dependent |
| Points, `wboit`, depth enabled | Yes | No | Shared weighted order-independent transparency |
| Points, depth disabled | No | No | Selected alpha mode |
| Sampled plane, `blended` + `overlay` | No | No | Source-over overlay |
| Sampled plane, `opaque` + `physical` | Yes | Yes | Opaque textured mesh |
| Sampled plane, `blended` + `physical` | Yes | No | Source-over, draw-order dependent |
| Sampled plane, `wboit` + `physical` | Yes | No | Shared weighted order-independent transparency |
| Sampled plane, `mask` + `physical` | Yes | Yes | Alpha cutout with physical texture holes |

Points accept `opaque`, `blended` and `wboit`; alpha mask and depth peeling are
rejected before creating native resources. Select `wboit` explicitly on every
transparent point, physical plane and mesh that should share that composition.
Opaque recording-site spheres and insertion paths continue to provide depth
context. Transparent sphere/path rendering is outside these component contracts.

Sampled planes retain `depth_policy="overlay"`, `alpha_mode="blended"` as their
defaults. This image route ignores 3D depth, even for XYZ corners. It rejects
other alpha modes. The opt-in `physical` route uses an unlit textured mesh with
normals, indices and a sampled texture. Its transformed corners must remain
non-degenerate and planar. Existing 2D slice overlays keep their image behavior.

For `depth_policy="physical", alpha_mode="mask"`, `alpha_cutoff` defaults to
`0.5` and must be finite and in `[0, 1]`. Fragments below the effective-alpha
cutoff are discarded; equality survives. Effective zero alpha is always
discarded, including at cutoff zero, so texture holes write neither color nor
depth. Effective alpha includes texture, vertex and material alpha; the adapter
initializes white vertex colors and an unlit material with opacity one. Nearest
sampling preserves discrete cutout boundaries, while linear sampling interpolates
texture alpha. A mask is a binary coverage policy, not translucent blending.

`capabilities.order_independent` is true for WBOIT configurations, and
`capabilities.sampled_plane_3d` is true for physical planes. These modes target
the immutable RC4 development source in the locked environment; released wheel
metadata alone does not establish support. Native sampled/MASK mesh queries and
styled/depth-cued point queries remain engine exclusions. The adapters do not
automatically enable picking or map arbitrary point IDs to atlas regions.

## Ownership and shutdown

Adapters borrow `dvz`, a live scene, and its panel. They create only their visual
and, for planes, sampled field plus a physical-plane index buffer when needed.
They create no app, figure, camera, controller, GUI,
callbacks, worker, or frame loop. Call mutations on the scene's permitted mutation
thread and request frames through the caller's existing loop.

`close()` is idempotent, destroys the component visual, owned sampled field and index buffer,
clears retained buffers, and rejects subsequent mutations. Native visual destruction
resets its scene-owned slot, so its existing attachment no longer draws. Explicitly
close all adapters **before** destroying the caller's scene: calling `close()` on
native handles after scene destruction is outside the lifetime contract. Constructor
failure releases resources the adapter has obtained; caller-owned resources remain
available. Caller scene destruction also remains the ultimate native resource owner.
