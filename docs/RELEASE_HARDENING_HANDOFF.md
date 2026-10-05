# Release-hardening handoff

Current continuation: [Audit follow up and implementation handoff](NEXT_STEPS.md).
This page records the original five hardening tasks, all completed on `main` before the
October 5, 2026 audit. Their original defects are historical context, not unresolved work.
The historical review baseline passed 82 tests, Ruff, and strict MkDocs; the later audit passed
125 tests with two real-asset skips. See the current handoff for subsequent validation counts,
correctness fixes, staged refactors, and the frozen pre-RC3 source baseline.

## Completed hardening

### 1. Make viewer lifecycle failure-safe

Base and linked viewers establish cleanup-safe state before native allocation. Constructor
cleanup bypasses virtual dispatch, linked slice workers have a finalizer path, repeated close is
harmless, and public native operations reject use after close. Failure injection covers scene,
figure, panel, mesh, and interaction construction, context-manager exceptions, and partial
subclass cleanup. Independently owned GUI/input resources are destroyed before the app and scene.

### 2. Resolve incompatible inherited navigator factories

The surface-only `from_pack()`, `from_assets()`, and `from_asset_set()` factories reject
`LinkedAtlasNavigator` before loading or native allocation. Their documented errors direct callers
to `from_packs()`, `from_multiresolution_packs()`, or `from_anatomy_packs()` with volume inputs.
Factory coverage verifies both concrete viewer classes.

### 3. Enforce validation at probe and position boundaries

World positions, trajectory widths, site radii, color channels, scalar infinities, and explicit
value ranges are validated before native allocation or upload. Positions must be finite, non-empty
`(n, 3)` arrays; trajectories require at least two points; widths and radii must be finite and
positive. RGB/RGBA integer channels must lie in `[0, 255]` before conversion. `NaN` is supported
for missing scalar values, while infinity and inconsistent row counts are rejected. Rejection
coverage verifies that invalid input causes no native allocation or upload.

The October audit found separate payload-copy and replacement-consistency defects; those belong
to the new handoff rather than reopening this historical input-validation task.

### 4. Align package metadata with CI

The checkout is an explicitly unreleased source snapshot. Its committed lock and immutable Git
revisions are authoritative; CI performs normal locked resolution without `--no-deps` on Python
3.10 and 3.13 and reports installed distributions. The provisional metadata ranges
`datoviz>=0.4.0rc2,<0.5` and `ibl-anatomy>=0.1.0,<0.2` are future release bounds, not evidence
of package-index availability or compatibility. A distributable release still requires verification
of the actual Datoviz artifact containing the post-RC2 fixes and a deliberately supported anatomy
distribution. Update the lower bound only after that verification.

### 5. Freeze one public API and document it consistently

Ten workflow-level and advanced composition names form the tested top-level compatibility surface.
The [API overview](api/index.md) documents these names and their ownership, units, validation,
and lifecycle behavior. Transport parsers, link-key codecs, concrete slice records, and
renderer-local cursor helpers remain accessible through implementation modules without a
top-level compatibility promise. API-surface tests enforce the chosen names.

## Current validation commands

Run from the package root with the pinned documentation tools:

```bash
uv sync --group dev --locked
uv run --frozen ruff check .
uv run --frozen pytest -q
uv run --frozen --with-requirements docs/requirements.txt mkdocs build --strict
git diff --check
```

Native checks also require the matching Datoviz library and Vulkan environment, as documented
in [Getting started](getting-started.md#python-and-native-library-pairing). Real-data interaction
review and candidate benchmark reruns remain separate evidence requirements; preserve dated
benchmark results and record the actual source/library identities for new runs.
