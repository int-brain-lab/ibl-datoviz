# Review the two applications

Use the existing prepared real-data assets and configured Datoviz runtime:

```bash
just review 1
just review 2
```

Bare `just review` opens app 1. `just review all` opens app 1, then app 2 when the
first window closes. Add `--ui-scale 1.5` for larger controls. Each application
keeps its visualization structure throughout the review: presets change layer
visibility and settings within existing views. Normal edits preserve the camera;
only the explicit reset button restores the starting camera.

## Region browsing in both apps

Check branch folding and leaf selection separately. Search for a parent acronym, open a retained descendant branch, then clear search and verify that ordinary folding returns. Select multiple leaves with Ctrl/Cmd and the Multiple selection checkbox; use Shift-click for visible siblings. Use the arrow keys and Enter/Space without moving focus back to the search box. A search with no matches should leave an empty browser and remain editable.

When regional values are supplied, switch between anatomical and value order. Search temporarily uses anatomical order and clearing it restores the requested ordering. Verify that surface/table selections preserve the browser's focus and folding, and that mapping changes clear selection. Hiding a selected surface region still preserves committed selection.

## App 1: 3D scientific viewer

The workspace contains one 3D viewport, a control/ontology sidebar and a persistent
scientific-data area. Its presets are **Atlas surface**, **Single BWM probe**,
**Multiple W39 insertions** and **Points + plane**. Orbit with left-drag and zoom
with the wheel. Use the common mapping selector for Allen, Beryl and Cosmos.

**Scientific layers** lets you combine the atlas, recording-site points, analytic
sites, insertion paths and an anatomical plane. **Point encoding** changes uniform
or firing-rate colors, pixel diameter and opacity on the recording-site point
layer. The optional analytic-site layer retains its firing-rate coloring.
**Physical plane** switches transparent blending and depth-writing cutout, with
opacity and cutoff controls. **Independent insertion styles** controls each path's
visibility, color and width. **Atlas appearance and region styles** controls global
opacity, hemispheres and the first selected signed region's visibility/RGBA/opacity.

The BWM inputs are hash-verified real recording sites. Firing-rate colors run from
purple through teal to yellow, clipped at the finite-site 5th/95th percentiles in
Hz. The numeric range remains visible beside the table; original table values are
unchanged. Missing rates have transparent scalar points, and gray analytic-site
and table swatches. Uniform cyan points retain all real recording-site coordinates.
Point opacity is a display multiplier, not a scientific measurement. Table selection
links mapped atlas regions; arbitrary points and sampled planes are not direct
picking targets. The physical plane shows real Allen 50 um grayscale anatomy at
its affine-defined location. Insertion colors identify paths; paths connect actual
channel coordinates without fitted or extrapolated points.

Prepare optional W39 trajectories using the instructions in the
[real-data roadmap](REAL_DATA_EXAMPLE_ROADMAP.md#october-13-runnable-examples).
When those inputs are absent, the multiple-insertion preset is unavailable and the
sidebar explains preparation. Present files with invalid hashes/provenance fail
explicitly. The persistent data area continues to show the pinned BWM recording-site
fixture; it does not claim W39 firing-rate data.

Review these scenarios within the same window:

1. Orbit the atlas, switch mappings, hover/select a region and find it in the tree.
   Edit its color/opacity and hide it. Check that committed selection remains
   understandable; a mapping switch intentionally clears selection.
2. Load the single-probe preset. Toggle uniform/firing-rate point colors, resize
   points and change opacity. Sort/filter the table and select rows. Check units,
   missing-value behavior and the association with the anatomical region.
3. If W39 is prepared, load multiple insertions and style/hide each path independently.
4. Load points + plane. Orbit to judge depth and overlap, compare blending/cutout,
   vary cutoff and isolate individual layers. Check that toggles retain the camera,
   table state and layout. Use reset to return to the starting state.

## App 2: linked atlas navigator

The workspace always contains AP, ML and DV slice views and one 3D view, plus the
sidebar. Presets are **Anatomy**, **Region labels**, **Volume context** and
**Physical slice**. The source is the complete prepared Allen 50 um pack; this app
does not silently use the sampled registered 10 um publication as complete coverage.

Wheel over a slice to scroll it; Ctrl+wheel zooms its existing view. Clicking a
slice moves the two visible cursor coordinates. The sidebar AP/ML/DV sliders move
the shared cursor directly. Cursor motion does not commit region selection;
**Select region** does. AP shows ML/dorsal, ML shows AP/dorsal and DV shows
ML/anterior. Readouts use atlas-world micrometres.

**Slices and 3D layers** controls anatomy, annotations, boundaries and volume
opacity. Zero volume opacity hides the volume while keeping all four panels.
**Physical slice in 3D** adds an anatomy or annotation plane for the chosen axis,
following the current cursor and mapping. It supports blending or cutout. Volume
context and this plane are separate composition routes: enabling the plane hides
the volume, and positive volume opacity hides the plane. Neither action changes
view structure. Slice-label colors retain their canonical mapping colors when you
edit 3D region styles.

Review these scenarios within the same window:

1. Scroll/click each slice and move the sliders. Check orientation, coordinate
   readouts, cursor synchronization and the distinction between cursor and selection.
2. Switch mappings; toggle anatomy/annotations/boundaries and adjust their opacity.
   Hover/select across the tree, slices and 3D view.
3. Compare volume context with zero volume opacity. Confirm that every panel and
   navigation control remains available.
4. Enable a physical slice, switch its axis/content, move the corresponding cursor
   coordinate and compare transparency/cutout. Orbit the 3D view to inspect placement.
   Reset and check the initial layers, cursor and camera.

## Capture and report feedback

```bash
just review all --strict --frames 3
just review 1 --preset mixed --offscreen build/review-1.png
just review 2 --preset physical-slice --offscreen build/review-2.png
```

Offscreen output captures scientific views without the interactive sidebar/table.
`--frames` checks bounded startup and shutdown; it does not establish usability.
For feedback, identify the app, preset, mapping and action, then describe the expected
behavior and what you observed. Focus on scientific meaning, interaction, visual
readability and responsiveness. Rendering checks and screenshots remain separate
from your live scientific/design acceptance.

The older named commands (`surface`, `mapping`, `picking`, `probe`, `firing-rate`,
`slices`, `controls`, `insertions`, `volume-free`) remain available as focused
standalone diagnostics.
