# Atlas 3-D feature benchmark

Status: local diagnostic evidence, 2026-09-15.

The benchmark isolates costs around the D070 atlas surface before the multiview navigator is
rebuilt. It uses 486,674 vertices, 966,645 triangles, and 1,140 mesh components at 900 x 720 on an
NVIDIA GeForce RTX 5090. Each result is the median of five fresh processes in randomized order,
with 30 warm-up and 120 measured frames. Datoviz resolved the requested immediate presentation
mode to immediate in every run.

| Scenario | Median FPS | Run ms | Relevant CPU mutation | Median RSS |
| --- | ---: | ---: | ---: | ---: |
| Opaque baseline | 246.0 | 4.06 | 0.00 ms | 362 MiB |
| Continuous arcball update | 249.0 | 4.02 | 0.03 ms | 362 MiB |
| Interaction capability, idle | 240.9 | 4.15 | 0.00 ms | 363 MiB |
| Static explosion | 251.9 | 3.97 | 0.00 ms | 366 MiB |
| Animated explosion | 213.7 | 4.68 | 1.19 ms | 362 MiB |
| Hover-emphasis update every frame | 113.3 | 8.83 | 8.76 ms | 362 MiB |
| Selection update every frame | 86.8 | 11.52 | 10.97 ms | 362 MiB |
| Face query every frame | 89.8 | 11.14 | 0.12 ms | 534 MiB |
| Embedded GUI and ontology, idle | 96.5 | 10.36 | 0.00 ms | 378 MiB |
| Embedded GUI plus interaction, idle | 98.8 | 10.12 | 0.00 ms | 378 MiB |

The raw report is written to `build/atlas-3d-d070.json` and deliberately remains untracked because
timings depend on the host, driver, window system, and current machine load.

## Findings

Camera updates and idle interaction are effectively free relative to normal run-to-run variation.
Static explosion also has no continuing cost. The current CPU explosion implementation uploads
5,840,088 position bytes when its value changes; changing it every frame costs about 1.2 ms in
Python and reduces median throughput by roughly 13%. This is measurable but not an immediate
performance blocker for a user-controlled slider.

Hover and selection stress tests alternate region state every frame. They rebuild dense colors and
upload 1,946,696 bytes per change. Their 8-11 ms Python cost is the clearest `ibl-datoviz`
bottleneck, although real input should update only when the hovered or selected identity changes.
The next optimization should cache presentation-level masks and colors, then measure whether the
remaining dense color upload is material before requesting a new Datoviz facility.

An active face query every frame spends about 9.9 ms in Datoviz's post phase and raises median RSS
by about 173 MiB. Query request construction itself costs only about 0.12 ms. This confirms that
hover queries must be movement-driven, coalesced, and throttled. The retained expanded indexed
picking representation remains a worthwhile later Datoviz optimization. Merely enabling the
interaction capability has little steady-state cost.

The embedded GUI scenarios spend about 9 ms per frame in Datoviz's prepare phase. This scenario
currently combines the GUI frame, embedded viewport resolution, docking, and the complete retained
ontology tree, so it does not yet identify which layer owns the cost. A follow-up micro-ladder must
compare an empty GUI, an empty embedded viewport, a small tree, and the complete Allen tree before
changing either repository.

High-percentile timing contains occasional 8-17 ms spikes even in baseline runs. The randomized
fresh-process medians are suitable for ranking these large effects, but the report is not a portable
performance threshold. No real pointer events were injected, so Datoviz correctly reports zero
input-latency samples; the query and emphasis scenarios measure update throughput, not end-to-end
human interaction latency.

## Reproduction

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
DATOVIZ_LIBRARY=../../Viz/datoviz/build/src/libdatoviz.so \
uv run python tools/benchmark_atlas_3d.py \
  ../ibl-anatomy/build/d070-published/mesh-pack \
  --regions ../ibl-anatomy/build/d070-published/regions.json \
  --json build/atlas-3d-d070.json
```

The report embeds package paths, Git revisions, platform information, GPU identity, resolved
presentation mode, individual runs, native Datoviz timing decomposition, mutation durations, query
counts, and aggregate ranges.

## Next measurements

1. Split the embedded GUI cost into GUI-only, viewport-only, small-tree, and complete-tree cases.
2. Profile presentation-level color preparation separately from the dense color upload.
3. Measure realistic hover scheduling: pointer movement with at most one outstanding query.
4. Keep the current explosion path unless ordinary slider interaction shows visible latency.
5. Build and benchmark one isolated 2-D slice view before returning to the linked navigator.
