# Volume-free linked navigation

`AtlasViewer` can display a surface, three orthogonal slice panels,
boundaries, cursor overlays, and owned scientific layers
without constructing a native volume visual or uploading a 3D sampled field.
Existing factories retain `render_volume=True` by default.

```python
from ibl_datoviz import AtlasMesh, AtlasViewer

mesh = AtlasMesh.from_pack(mesh_pack)
with AtlasViewer.from_slice_source(mesh, slice_source) as navigator:
    navigator.show()
```

`slice_source` is an explicit compatible source such as `AtlasSliceSource` or
verified `AtlasVolumes`. It supplies the grid, region catalog, template and
annotation sections, and annotation lookup. The navigator checks scientific
reference-space compatibility and verifies every mesh mapping's nonzero signed
region IDs against the source catalog before creating native resources. It uses
that catalog for mesh colors, ontology, mapping, and selection. The factory takes
an existing `AtlasMesh` and always selects `render_volume=False`.

To reuse a dense pack as a CPU slice source while skipping GPU volume rendering:

```python
with AtlasViewer.from_packs(
    mesh_pack, volume_pack, render_volume=False
) as navigator:
    navigator.show()
```

This factory still opens the supplied dense pack. To avoid needing a dense volume
pack entirely, use verified registered projections, their matching intensity
transport, and an explicitly verified region catalog:

```python
from ibl_anatomy import open_region_catalog

catalog = open_region_catalog(catalog_path, sha256=catalog_sha256)
with AtlasViewer.from_registered_slices(
    mesh_pack, intensity_pack, verified_registered_assets, catalog=catalog
) as navigator:
    navigator.show()
```

`verified_registered_assets` must be an `ibl_anatomy.MaterializedRegisteredAssets`
result. The current anatomy result contains projection readers and has no region
catalog property, so `catalog` is required independently. The factory requires
exactly one AP, ML, and DV registered projection and never calls `open_volume_pack`.
`AtlasSliceSource` continues validating the intensity/projection reference space,
grid identity, plane shapes, slice counts, and affine correspondence.

The direct constructor also accepts
`AtlasViewer(mesh, layout="linked", slice_source=source, render_volume=False)`.
Omitting both sources or requesting `render_volume=True` without volumes raises
an error. Volume-free mode creates no native volume visual or 3D sampled field;
internal render handles are not part of the public viewer API. No volume-opacity GUI slider is shown, and
the resolution label explicitly says the 3D volume is disabled. The surface alpha
mode uses the ordinary `AtlasViewer` policy, including palette alpha and selection.

Cursor navigation preserves committed selection unless an explicit selection
gesture is requested. Mapping changes, slice orientation, nearest annotation
sampling, linear anatomy sampling, boundaries, hover, zoom, and worker ownership
keep their existing behavior. `close()` joins slice workers before releasing
native resources, including after construction failure.

Registered data must contain the sections requested by navigation. Removing the
volume does not supply missing sections: absent-section reader errors remain
explicit, without lower-resolution substitution or invented annotation. The
bundled registered graph has sampled coverage and does not establish unrestricted
navigation. Native slice images remain 2D overlays; this route makes no claim of
3D sampled-plane depth or unified volume/surface transparency.

The existing volume-enabled route remains available. A present volume with
positive opacity keeps its current source-over surface composition limitation.
Setting its opacity to zero delegates surface alpha selection to `AtlasViewer`;
it retains the allocated volume resources. Use `render_volume=False` to avoid
those allocations entirely.
