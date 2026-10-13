# Insertion trajectories

`InsertionTrajectory` stores one immutable path in atlas-world micrometres.
`InsertionCollectionVisual` manages several independently identified path
visuals in a caller-owned Datoviz scene and panel.

```python
from ibl_datoviz.insertions import InsertionCollectionVisual

insertions = InsertionCollectionVisual(
    dvz,
    viewer.scene,
    viewer.panel,
    transform=viewer.mesh_data.normalize_points,
)
insertions.set_insertion(
    "probe-a", positions_um, color=(255, 205, 72, 255), width_px=4
)
insertions.set_insertion(42, other_positions_um, color=(80, 180, 240), width_px=3)
insertions.set_color("probe-a", (255, 120, 80, 255))
insertions.set_width(42, 5)
insertions.set_visible("probe-a", False)
insertions.remove(42)
insertions.close()  # Before the caller destroys the scene.
```

Identities are non-empty strings or positive integers; booleans are not integer
identities. They are independent of atlas region IDs and insertion order is
available through `ids`. `get_data(identity)` returns the immutable
`InsertionTrajectory` payload. Replacing an existing identity keeps its order
and visibility. The path updates all three native attributes together, including
when the vertex count shrinks or grows.

Each path requires finite positions with shape `(n, 3)` and at least two points.
The collection copies positions into read-only contiguous float32 storage. Color
is a uniform integer RGB or RGBA value in `[0, 255]`; RGB expands to opaque
RGBA. Alpha must be 255 because the supported path route is opaque. Requests for
transparent insertion paths raise `ValueError` rather than silently selecting
an unsupported blend mode. Width is one finite positive pixel value per path.

`set_color()` and `set_width()` update only the selected path and preserve its
geometry and visibility. `set_visible()` affects only the named path. Removing
an absent identity is a no-op; `clear()` removes all paths and leaves the
collection open for later insertions.

The collection borrows the Datoviz object, scene, and panel; it creates and
destroys only its path visuals. It does not create a viewer, scene, camera, GUI,
callbacks, or frame loop. Call its mutations on the scene's permitted mutation
thread, and close it before scene destruction. `close()` is idempotent and later
mutations raise `RuntimeError`. Validation occurs before native mutation. Failed
updates restore the previous upload; if native rollback also fails, that path
is destroyed and removed from the collection.

Insertion paths are independent of `ProbeSites`, probe-site tables, and the
viewer’s legacy single-probe path. The current path rendering support is opaque;
this API does not claim transparency-order independence or a broader native
scientific rendering profile.
