# Release-hardening handoff

This note records the API-review work that should be completed before an `ibl-datoviz` release.
It is intentionally separate from the Datoviz v0.4 performance work: the current performance
evidence is sufficient for the release candidate, while the items below are correctness and
packaging blockers in this Python package.

The review baseline passed 82 tests, Ruff, and a strict MkDocs build. Those checks do not cover the
failure paths and API ambiguities described here.

## Recommended commit sequence

Keep the changes reviewable as five implementation commits followed by any final release-note
update. Do not combine these items with Datoviz query, mesh, or presentation optimizations.

### 1. Make viewer lifecycle failure-safe

Status: implemented on the feature branch. Base and linked viewers now establish cleanup-safe
state before native allocation, constructor cleanup bypasses virtual dispatch, slice workers have a
linked-view finalizer path, repeated close is harmless, and public native operations reject use
after close. Failure injection covers scene, figure, panel, mesh, and interaction construction;
context-manager exceptions and partial-subclass cleanup are also covered.

`AtlasViewer.__init__()` creates the native scene before all fallible Python setup is inside its
cleanup boundary. For example, mapping-control construction occurs after `dvz_scene()` but before
the constructor's `try` block. An invalid mapping or another setup failure in that interval can
leak the scene. Subclass initialization adds a second partial-construction path.

Initialize every cleanup-relevant attribute, including `_closed` and native handles, before the
first native allocation. Put all work following that allocation under one exception boundary and
ensure cleanup is safe for every partially initialized state. Be careful about virtual dispatch:
base construction currently calls `self.close()`, which resolves to
`LinkedAtlasNavigator.close()` for navigator instances.

After `close()`, public methods and factories must never call Datoviz through destroyed handles.
Choose one consistent contract: mutating/rendering methods should raise a clear `RuntimeError`
mentioning that the viewer is closed, while repeated `close()` remains harmless. Apply the guard
to inherited navigator methods as well as base viewer methods. Preserve destruction order: detach
or destroy independently owned GUI/input resources, destroy the app, then destroy the scene.

Acceptance coverage should inject failures at each native construction stage and assert that every
successfully created owning handle is destroyed exactly once. Add tests for base and navigator
constructor failure, idempotent close, context-manager exception exit, finalizer safety on partial
objects, and representative calls after close (`show`, `render_offscreen`, mapping, selection,
probe, region, cursor, and slice operations).

### 2. Resolve incompatible inherited navigator factories

`LinkedAtlasNavigator` inherits `AtlasViewer.from_pack()`, `from_assets()`, and
`from_asset_set()`. Those class methods instantiate `cls` with only a mesh (and sometimes a
catalog), but `LinkedAtlasNavigator.__init__()` also requires `volumes`. Calls such as
`LinkedAtlasNavigator.from_pack(...)` therefore advertise a factory that cannot construct the
subclass.

Prefer explicitly prohibiting those three inherited entry points on `LinkedAtlasNavigator` with a
clear error that directs callers to `from_packs()`, `from_multiresolution_packs()`, or
`from_anatomy_packs()`. An override that accepts the extra volume inputs is also valid, but only if
it provides a materially useful API without duplicating the existing navigator factories. Ensure
the generated API reference does not present unusable inherited constructors.

Acceptance coverage should call every factory through both concrete classes and verify either a
valid instance or the intentional, documented error. Type annotations and docstrings must match
the runtime behavior.

### 3. Enforce validation at probe and position boundaries

Validation is split between `AtlasMesh.normalize_points()`, `AtlasViewer.set_probe()`,
`AtlasViewer.set_probe_sites()`, and `ProbeSites.from_arrays()`. The paths are inconsistent. In
particular, raw viewer methods can pass non-finite positions to native uploads; `set_probe()` does
not validate finite positive width or color channels before converting to `uint8`, so invalid
channels can wrap; and `set_probe_sites()` does not reject a non-finite radius. Direct scalar input
should follow the same no-infinity policy as `ProbeSites` while continuing to support `NaN` as a
missing value.

Centralize or share validation where practical. Require positions with non-empty shape `(n, 3)`
and finite coordinates; require finite positive widths and radii; require RGB or RGBA colors with
integer channels in `[0, 255]` before any dtype conversion; and reject infinite scalar values,
malformed value ranges, and inconsistent row counts. Preserve the existing requirement that a
trajectory contains at least two points. Do not silently clip, wrap, or reshape invalid input.

Add parameterized tests for `NaN`, both infinities, malformed ranks and lengths, fractional and
out-of-range color channels, Boolean/color edge cases if accepted by NumPy's integer checks, and
non-finite or non-positive sizes. Assert that rejected calls perform no native allocation or
upload.

### 4. Align package metadata with CI

The declared project dependencies are release ranges (`datoviz>=0.4.0rc2,<0.5` and
`ibl-anatomy>=0.1.0,<0.2`), while CI manually installs exact Git revisions and then installs this
package with `--no-deps`. Consequently CI does not prove that the package can be installed and
tested from its published metadata. The project declares Python `>=3.10`, but CI exercises only
3.10.

First decide the release contract: either published dependency versions exist and become the
authoritative metadata, or this remains a source-snapshot package whose direct references and
limitations are explicit. Then make the lock/source configuration, `pyproject.toml`, CI, README,
and getting-started commands agree. CI must include at least one normal resolved installation of
the package, without using `--no-deps` to hide metadata conflicts. Test the lowest supported Python
version and one current supported version, or narrow `requires-python` to the versions actually
supported. Keep native-runtime/GPU skips narrowly scoped; dependency or import failures must fail
the job.

Acceptance is a clean-environment install using only the documented command, followed by the unit
suite, Ruff, and strict documentation build. Verify the installed distributions and versions in
CI so an adjacent checkout cannot accidentally satisfy the test.

### 5. Freeze one public API and document it consistently

The API overview says the public surface is intentionally small, but `ibl_datoviz.__all__` also
exports lower-level slice source types, cursor/composer helpers, encoding helpers, and
`parse_svg_path`. Some appear in detailed API pages, some only in `__all__`, and the README focuses
on a still smaller viewer API. This makes compatibility promises unclear.

Classify every current top-level export as supported public API or internal implementation detail.
Retain only deliberate public names in `__all__`; move implementation helpers behind module-level
imports rather than top-level exports when they are not intended to be stable. For every retained
name, include it in the API overview or an explicitly labeled advanced API section and document
ownership, units, accepted missing values, exceptions, and lifecycle behavior. Examples should
import through the supported path. Avoid renaming solely for tidiness; compatibility decisions
should be explicit and recorded in the release notes.

Add an API-surface test that asserts the chosen top-level names, plus documentation link/build
checks. Review at minimum `AtlasViewer`, `LinkedAtlasNavigator`, `AtlasMesh`, `ProbeSites`,
`AtlasRegionValues`, `AtlasTreeModel`, `AtlasSliceSource`, `AtlasSourceSlice`, `AtlasCursor`,
`AtlasSliceComposer`, the slice/cursor helpers, region-key helpers, and `parse_svg_path`.

## Final validation

After the five blockers are resolved, run from a clean environment:

```bash
uv sync --group dev
uv run ruff check .
uv run pytest -q
uv run mkdocs build --strict
git diff --check
```

Also run the native smoke tests when the Datoviz shared library and a GPU context are available.
Then rerun the existing 2-D and 3-D consumer benchmarks against the finalized Datoviz RC candidate;
compare them with the recorded findings, but do not make architectural performance work a release
condition for this hardening sequence.
