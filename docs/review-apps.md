# Review applications and scientific annotations

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

## Scientific annotations

Review the new viewer-owned point/path API interactively:

```bash
just review annotations --strict --ui-scale 1.5
```

This opens the prepared D070 anatomy with illustrative targets and a route, using
the accepted six-structure context and package-level Layers controls. These are
user annotations, not measured recording data. It uses the configured native
runtime and existing anatomy assets; slice volumes and the shared IBL reader are
not required. Missing major surfaces fail explicitly; run setup if not prepared.

Use the Layers panel to hide/show targets and the route, edit colors and point
size/path width, and select `target-a` or `target-b` by original ID. Selection is
pink. Check that hiding a selected layer preserves selection and that mapping
changes clear region selection while retaining the selected annotation. Orbit,
pan, zoom and reset; layer state should persist. Native mouse picking of these
annotations is a later gate; the region browser and anatomical picking still work.
Changing a scalar-colored layer's uniform color clears its scalar encoding.

For bounded startup or a geometry-only capture:

```bash
just review annotations --strict --frames 3 --ui-scale 1.5
just review annotations --strict --offscreen "build/annotations review.png"
```

`just review all` continues to cover apps 1 and 2. Close the annotation window to
return to the shell. Record interactive findings in the feedback log.

## Region browsing in both apps

Hover feedback starts disabled in both the tree and the 3D brain. Click a leaf
or a brain region to select it. To explicitly enable hover while investigating
performance, launch with `just review 1 --ui-scale 1.5 --hover` (or app `2`).
The library constructor also accepts `enable_hover=False` without disabling
click selection; its existing default remains enabled for compatibility.

The sidebar is a compact region browser: mapping and visible hemispheres, search,
and a small action toolbar sit above the tree. The hierarchy fills the remaining
height with its own scrollbar; a fixed two-row selection summary sits below it.
The settings icon opens **Display settings** over the visualization and the info
icon opens **Selection details**. Both are ordinary in-app windows: the uncovered
tree stays usable while they are open. Opening settings or selecting many regions
must not move the search box or resize the tree. Icon buttons provide tooltips.

App 1 keeps independent coarse anatomical context visible throughout selection. A 3D click selects the displayed major anatomical structure and its actual side; use the tree for finer regions. Fine selection adds a translucent regional overlay without hiding context or filtering scientific observations. Selecting a displayed coarse parent accents its existing surface without revealing every fine descendant mesh. Clearing selection removes the emphasis only. App 2 and ordinary library callers retain their existing presentation unless explicitly configured otherwise.

Hover remains sparse GPU decoration in both apps; it does not upload dense colors or rebuild geometry. The browser owns scientific selection details, so the engine's raw visual/item/key metadata card is disabled.

Check branch folding and leaf selection separately. Search for a parent acronym, open a retained descendant branch, then clear search and verify that ordinary folding returns. Select multiple leaves with Ctrl/Cmd and the multiple-selection icon; use Shift-click for visible siblings. Use the arrow keys and Enter/Space without moving focus back to the search box. A search with no matches should leave an empty browser and remain editable.

When regional values are supplied, switch between anatomical and value order. Search temporarily uses anatomical order and clearing it restores the requested ordering. Verify that surface/table selections preserve the browser's focus and folding, and that mapping changes clear selection. Hiding a selected surface region still preserves committed selection.

## App 1: Where did we record?

This is the first visual review gate, before the broader scientist-facing API refactor. Launch the prepared workspace from the repository:

```bash
just doctor --strict
just review 1 --strict --ui-scale 1.5
```

The window requests 2240 × 1600 logical pixels and fits one monitor's decorated work area. The named lateral-oblique orientation puts olfactory areas toward the lower left and cerebellar cortex toward the upper right. **Reset view** restores orientation, pan and zoom without resetting scientific layers or selection. **Explode selection** separates a selected fine region using its authored displacement; the coarse context remains a stationary anatomical reference.

The default scene contains six verified source-native context structures: Isocortex, Olfactory areas, Midbrain, Pons, Medulla and Cerebellar cortex. They form an incomplete orientation cut, not a complete brain partition or a closed shell. Their source colors identify anatomy. The shared `ibl-anatomy` catalog contains twelve structures; the default omits six internal structures to reduce visual clutter. Setup materializes the hash-pinned source meshes in `build/allen-major-context`. Missing/corrupt assets fail explicitly rather than falling back to the dense brain.

A real BWM recording starts visible: 192 prepared recording sites in cyan and one amber path joining their actual coordinates. The default glyph radius is 20 µm rather than 85 µm to reduce overlap between neighboring sites. Uniform cyan identifies the site layer, rather than a measured quantity. The path is not an independent histology trace. Layer counts describe the supplied observations. **Layers** is persistently docked on the right of the viewport and can be resized, moved or docked elsewhere; the Regions browser retains its own full-height reservation. Its three checkboxes control Brain context, Insertion paths and Recording sites. No toggle changes the camera or context opacity.

**Recording sites → Color** switches uniform geometry to mean firing rate. Values are means of good units assigned to co-located channel groups in the default verified fixture; these are not individual neuron soma locations. The range uses finite-site 5th/95th percentiles in Hz, with purple low and yellow high. Missing scalar values are gray and original table values remain unchanged. **Recording details → Site table** opens the optional linked recording table. Recording captions and derivation text come from the supplied fixture's provenance, not a hardcoded subject identity.

The settings gear opens **Display settings**, including Context opacity. Context uses one approximate transparency technique throughout 0–1, avoiding the old automatic transparent-to-opaque pipeline jump at 1. This does not make overlapping transparent surfaces physically exact. At high opacity, internal data can still be obscured; the recording task starts at 0.04. Fine overlays cap opacity at 0.18 so they do not become opaque obstacles. The optional explicit detailed-anatomy presentation retains its separate rendering behavior.

Review in this order:

1. Judge the initial camera against the reference. The recording should be findable immediately, and major anatomical context should be understandable without individual cortical layers.
2. Turn Recording sites off: the amber path should remain. Turn Insertion paths off too: both data layers disappear. Restore each independently; camera, region selection and styles must stay fixed.
3. Turn Brain context off/on. Sites and paths remain visible; restoring context restores its previous appearance.
4. Search and select the FRP leaf, then the VPL leaf (in the thalamus). Context and data must remain. Clear selection, then click a large visible cortex surface: select the shown parent/side without exposing all cortical layers. Try Allen/Beryl/Cosmos and left/right visibility.
5. Under Recording sites, switch Color to Mean firing rate (Hz) and inspect the range/missing-value legend. Adjust Radius (um) while zooming in: these are display glyphs, not physical site sizes. Open Recording details → Site table and check linked selection. Restore uniform color to compare geometry readability.
6. Resize or dock Layers elsewhere. At UI scale 1.5, the three primary toggles must remain readable and accessible; the tree should not jump when selection changes. Orbit/zoom and verify Reset view; inspect Explode selection with a fine region selected.
7. In Display settings, compare low opacity, 0.9 and 1.0. Check the endpoint transition and judge the transparency approximation separately from anatomical clutter.

Each active insertion has its own compact row: visibility, identifier, editable color swatch and width in pixels. Insertion details shows full insertion IDs and supplied session metadata. Narrow docks place the width on a second line within the same insertion group. These controls do not change other insertions.

Advanced diagnostics retain the older presets, comparison point renderer, physical plane and optional W39 paths. Anatomy planes interpolate continuous grayscale; region labels retain nearest-neighbor filtering. Choose Multiple W39 insertions to inspect three independently styled paths, orbit and zoom, and verify that repeated channel locations produce continuous strokes without spikes. These W39 IDs identify insertions, and their derivative does not supply session metadata. They are outside this first visual gate. Missing optional W39 data disables that example without borrowing BWM firing rates. Later gates will review multiple-recording API scripts and linked slices; no alignment computation or new cluster/voxel feature workflow is claimed here.

For a deliberate twelve-structure comparison, run the example directly with `--context-detail all` in the configured Datoviz environment. Ordinary review should start with the six landmarks above. Offscreen output captures scientific views without interactive controls.

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

Record observations and their acceptance status in the
[manual review feedback log](REVIEW_FEEDBACK.md).

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
