# Atlas 3-D feature benchmark

Status: local diagnostic evidence, 2026-09-15.

The benchmark isolates costs around the D070 atlas surface before the multiview navigator is
rebuilt. It uses 486,674 vertices, 966,645 triangles, and 1,140 mesh components at 900 x 720 on an
NVIDIA GeForce RTX 5090. Each result is the median of five fresh processes in randomized order,
with 30 warm-up and 120 measured frames. Datoviz resolved the requested immediate presentation
mode to immediate in every run.

| Scenario | Median FPS | Run ms | Relevant CPU mutation | Median RSS |
| --- | ---: | ---: | ---: | ---: |
| Opaque baseline | 261.6 | 3.82 | 0.00 ms | 363 MiB |
| Continuous arcball update | 249.0 | 4.02 | 0.03 ms | 362 MiB |
| Interaction capability, idle | 240.9 | 4.15 | 0.00 ms | 363 MiB |
| Static explosion | 251.9 | 3.97 | 0.00 ms | 366 MiB |
| Animated explosion | 213.7 | 4.68 | 1.19 ms | 362 MiB |
| Hover-emphasis update every frame | 258.6 | 3.87 | 1.47 ms | 363 MiB |
| Selection update every frame | 257.3 | 3.89 | 1.61 ms | 363 MiB |
| Face query every frame | 91.1 | 10.98 | 0.12 ms | 535 MiB |
| Embedded GUI and ontology, idle | 126.6 | 7.90 | 0.00 ms | 378 MiB |
| Embedded GUI plus interaction, idle | 126.2 | 7.92 | 0.00 ms | 378 MiB |

The optimized raw report is written to `build/atlas-3d-optimized.json` and deliberately remains untracked because
timings depend on the host, driver, window system, and current machine load.

## Findings

Camera updates and idle interaction are effectively free relative to normal run-to-run variation.
Static explosion also has no continuing cost. The current CPU explosion implementation uploads
5,840,088 position bytes when its value changes; changing it every frame costs about 1.2 ms in
Python and reduces median throughput by roughly 13%. This is measurable but not an immediate
performance blocker for a user-controlled slider.

Hover and selection stress tests alternate region state every frame and upload 1,946,696 bytes per
change. Caching the canonical surface colors, absolute mapping IDs, dimmed colors, and writable
output buffer reduced their median Python mutation cost from 8.76-10.97 ms to 1.47-1.61 ms. Their
throughput is now within measurement noise of the opaque baseline. A GPU-resident per-part styling
facility could eventually remove the remaining dense mask, copy, and upload, but it is no longer an
RC3 blocker.

An active face query every frame spends about 9.43 ms in Datoviz's query phase and raises median RSS
by about 172 MiB. Query request construction itself costs only about 0.12 ms. This confirms that
hover queries must be movement-driven, coalesced, and throttled. The retained expanded indexed
picking representation remains a worthwhile later Datoviz optimization. Merely enabling the
interaction capability has little steady-state cost.

The new Datoviz decomposition attributes about 1.59 ms per frame to Dear ImGui construction and the
ontology callback, 5.16 ms to resolving the embedded viewport, and less than 0.01 ms to other prepare
work. Preventing GUI-managed source views from also entering normal app scheduling reduced median
GUI frame time from about 10.9 ms in the diagnostic run to about 7.9 ms, a roughly 28% improvement.
The remaining viewport cost includes the source render and a synchronous device wait; changing that
synchronization policy needs a post-v0.4 design rather than an RC3 shortcut.

High-percentile timing contains occasional 8-17 ms spikes even in baseline runs. The randomized
fresh-process medians are suitable for ranking these large effects, but the report is not a portable
performance threshold. No real pointer events were injected, so Datoviz correctly reports zero
input-latency samples; the query and emphasis scenarios measure update throughput, not end-to-end
human interaction latency.

## GUI and pointer follow-up

A second randomized five-process run on Datoviz `18b4840ff` decomposed the GUI and injected real
pointer-move events through `dvz_view_emit_pointer()`. The same D070 surface, 900 x 720 viewport,
immediate presentation mode, 30 warm-up frames, and 120 measured frames were used.

| Scenario | Run ms | GUI frame ms | GUI viewport ms | Query ms | Median RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Empty GUI window | 0.42 | 0.20 | 0.00 | 0.00 | 338 MiB |
| Empty embedded viewport | 1.04 | 0.31 | 0.38 | 0.00 | 341 MiB |
| Small VISp tree (7 rows) | 0.49 | 0.26 | 0.00 | 0.00 | 338 MiB |
| Complete grey-matter tree (875 rows) | 0.83 | 0.43 | 0.00 | 0.00 | 338 MiB |
| D070 viewport with minimal GUI | 6.41 | 0.83 | 4.88 | 0.00 | 378 MiB |
| Complete atlas GUI | 7.34 | 1.26 | 5.12 | 0.00 | 378 MiB |
| One real pointer move per frame | 11.30 | 0.00 | 0.00 | 9.87 | 535 MiB |

The tree is not the GUI bottleneck. Drawing all 875 retained grey-matter rows adds about 0.23 ms to
the GUI phase relative to the empty window, while the populated embedded surface viewport accounts
for about 4.9 ms in viewport resolution plus its image construction. The complete application adds
less than one millisecond beyond the minimal populated-viewport case. Further ontology-specific
optimization is therefore not justified by this measurement; the synchronous populated-viewport
path remains the meaningful upstream target.

The moving-pointer run produced 120 input samples and 120 queries. Median input-to-submit latency
was 11.44 ms, p95 was 13.69 ms, and p99 was 15.38 ms; 102 frames hit the mesh and 46 changed the
resolved region. A burst control emitted four moves per frame (480 events total) but still executed
only 120 queries. Its median query cost was 10.42 ms and median run time was 11.93 ms. This confirms
that Datoviz already applies latest-position-wins coalescing within a frame by reusing the retained
hover request scope. No Python hover scheduler or arbitrary frequency cap is warranted. The
remaining cost is one movement-driven face query per rendered frame, not an event backlog.

## Reproduction

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
DATOVIZ_LIBRARY=../../Viz/datoviz/build/src/libdatoviz.so \
uv run python tools/benchmark_atlas_3d.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  --regions ../ibl-anatomy/build/d070-published/regions.json \
  --json build/atlas-3d-optimized.json
```

The report embeds package paths, Git revisions, platform information, GPU identity, resolved
presentation mode, individual runs, native Datoviz timing decomposition, mutation durations, query
counts, and aggregate ranges.

## Next measurements

1. Separate query plan construction, command execution, and synchronous readback in a later
   Datoviz profiler revision.
2. Keep the current explosion path unless ordinary slider interaction shows visible latency.
