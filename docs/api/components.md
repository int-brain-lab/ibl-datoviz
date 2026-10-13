# Point collections and sampled planes

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

## Current native rendering limits

The configured native pairing supports the following component behavior. The
`capabilities` record exposes supported alpha modes and effective depth behavior;
it describes this adapter, rather than certifying every native backend.

| Component mode | Depth test | Depth write | Transparent composition |
| --- | --- | --- | --- |
| Points, `opaque`, depth enabled | Yes | Yes | Opaque pass |
| Points, `blended`, depth enabled | Yes | No | Source-over, draw-order dependent |
| Points, depth disabled | No | No | Selected alpha mode |
| Sampled plane, `blended` + `overlay` | No | No | Source-over overlay |

Points reject WBOIT, depth peeling, and alpha mask before creating native resources.
Sampled planes accept only blended overlay rendering. Requesting WBOIT, alpha mask,
or true 3D depth fails explicitly. The image shader has unconditional depth comparison
and disables depth writes even when its vertices are XYZ data coordinates. Texture
alpha controls overlay blending; it does not establish a depth-correct cutout plane.
Intersections with meshes therefore remain an overlay preview, and do not satisfy
the required native scientific 3D plane profile. A future conformant native route
requires separate acceptance; these adapters never silently substitute blended
rendering for a requested unsupported technique.

## Ownership and shutdown

Adapters borrow `dvz`, a live scene, and its panel. They create only their visual
and, for planes, sampled field. They create no app, figure, camera, controller, GUI,
callbacks, worker, or frame loop. Call mutations on the scene's permitted mutation
thread and request frames through the caller's existing loop.

`close()` is idempotent, destroys the component visual and its owned sampled field,
clears retained buffers, and rejects subsequent mutations. Native visual destruction
resets its scene-owned slot, so its existing attachment no longer draws. Explicitly
close all adapters **before** destroying the caller's scene: calling `close()` on
native handles after scene destruction is outside the lifetime contract. Constructor
failure releases resources the adapter has obtained; caller-owned resources remain
available. Caller scene destruction also remains the ultimate native resource owner.
