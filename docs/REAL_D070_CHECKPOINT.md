# Real D070 atlas checkpoint

Status: reproducible local evidence, 2026-09-14.

The native adapter consumes the packaged `ibl-atlas-assets` lock `allen-ccf-2017-d070-20260908`: 486,674 vertices, 966,645 triangles, 1,140 components, and 1,132 signed presentations. Both Python and the web TypeScript decoder match the lock's exact vertex and face presentation fingerprints.

The real pack revealed and fixed a coordinate error hidden by the synthetic fixture. EAM3 positions are already compiled into ML/AP/DV micrometres. The manifest's `source_to_world_um` matrix records the offline source transform and must not be applied again. Display-space normalization remains local to this package.

On the local Linux development host, one diagnostic run measured:

- complete download-independent verification and decode: approximately 0.59–0.66 seconds;
- native display-array preparation: approximately 0.07–0.08 seconds;
- preparation of colors plus vertex and face IDs for each mapping: approximately 7–8 milliseconds;
- Datoviz setup, first offscreen render, and 900 × 720 capture: approximately 0.32 seconds;
- maximum process RSS after rendering: approximately 412–471 MiB, rising to approximately 618–672 MiB after face queries; and
- center-pixel face queries: approximately 120 milliseconds for the first expansion/upload and 11 milliseconds for subsequent unchanged queries, each resolving in one subsequent frame.

These are development diagnostics rather than portable performance thresholds. The mapping path is fast enough for interactive switching after replacing per-element Python lookups with presentation-indexed NumPy tables. Face queries are correct, and Datoviz commit `2274ca3c3` retains their static expanded upload so repeated picks are suitable for throttled hover. The first pick and retained memory footprint remain expensive. A future indexed picking path could remove the expanded position buffer rather than merely caching it.

Reproduce the measurement with:

```bash
PYTHONPATH=.:../ibl-atlas-assets/src python examples/benchmark_atlas.py \
  ../ibl-atlas-assets/build/d070-published \
  --render build/d070-checkpoint.png \
  --json build/d070-checkpoint.json
```

The image and JSON report remain build-local because timings and pixels are host-dependent. The semantic identities are committed in the shared asset-set lock.
