# Atlas 2-D slice benchmark

Status: local diagnostic evidence, 2026-09-16.

The isolated slice benchmark separates retained native rendering from slice decoding and CPU
composition. It uses the central DV section of the pinned 50 um Allen pack: two 264 x 228 RGBA
layers (481,536 bytes total), 6,374 mapping-aware Allen boundary segments, and a 900 x 720 native
window on an NVIDIA GeForce RTX 5090. Each result is the median of five randomized fresh processes
with 30 warm-up and 120 measured frames on Datoviz `18b4840ff` in immediate presentation mode.

| Scenario | Median FPS | Run ms | Execute ms | Median RSS |
| --- | ---: | ---: | ---: | ---: |
| Empty 2-D panel | 5,721 | 0.175 | 0.012 | 292 MiB |
| Anatomy image, linear sampling | 4,671 | 0.214 | 0.019 | 292 MiB |
| Anatomy plus annotation | 4,255 | 0.235 | 0.023 | 292 MiB |
| Images plus 6,374 boundaries | 3,849 | 0.260 | 0.030 | 292 MiB |
| Complete slice plus crosshair | 3,544 | 0.282 | 0.035 | 293 MiB |

The complete static slice adds about 0.11 ms per frame over the empty panel. The annotation image,
vector boundaries, and crosshair are individually small, and the complete retained layer stack is
not a linked-navigator bottleneck. Current slice latency is dominated instead by preparing cold
high-resolution registered data and by the embedded-viewport synchronization measured in the 3-D
feature ladder.

This benchmark deliberately excludes CPU decoding, rasterization, and field updates. Those costs
are measured by `examples/benchmark_registered_slices.py`: cold registered composition takes
hundreds of milliseconds, while cached neighboring composition is in the tens of milliseconds.
The two measurements therefore bound different stages and should not be added as if they occurred
on every frame.

Reproduce the native layer ladder with:

```bash
PYTHONPATH=.:../ibl-anatomy/src:../../Viz/datoviz \
DATOVIZ_LIBRARY=../../Viz/datoviz/build/src/libdatoviz.so \
uv run python tools/benchmark_atlas_2d.py \
  ../ibl-anatomy/build/allen-ccf-2017-50um \
  --json build/atlas-2d-50um.json
```

The JSON report remains build-local because timings, memory, driver behavior, and pixels depend on
the host. It records every run, asset dimensions, boundary count, package revisions, and timing
decomposition.
