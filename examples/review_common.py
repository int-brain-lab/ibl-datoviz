"""Shared controls and source-grounded slice preparation for the two review apps."""

from __future__ import annotations

import ctypes
import json
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from ibl_anatomy import bundled_surface_catalog, load_surface_catalog, open_volume_pack
from ibl_datoviz import SampledPlane
from ibl_datoviz.context import DEFAULT_CONTEXT_LANDMARKS, AtlasContextSurface
from ibl_datoviz.navigator import SLICE_DISPLAY_AXES, AtlasSliceComposer
from ibl_datoviz.surface_style import RegionStyle

# Named review orientation; visual acceptance is recorded with the review artifacts.
RECORDING_CAMERA = (-1.15, -0.20, 2.50)
INPUT_FIXTURE_WARMUP_FRAMES = 8


def load_major_context(path):
    """Read the shared coarse cut offline, verifying each original source mesh."""
    catalog = bundled_surface_catalog()
    return catalog, load_surface_catalog(path, catalog)


def review_context_surfaces(mesh, catalog, geometries, *, detail='landmarks'):
    """Use the same verified global-region surfaces in both numbered reviews."""
    return [
        AtlasContextSurface.from_geometry(
            geometry,
            mesh,
            color=tuple(bytes.fromhex(member.color_hex.removeprefix('#'))),
            name=member.name,
        )
        for member, geometry in zip(catalog.members, geometries, strict=True)
        if detail == 'all' or member.asset.source_allen_id in DEFAULT_CONTEXT_LANDMARKS
    ]


def add_review_arguments(parser):
    """Add consistent review options without changing native discovery."""
    parser.add_argument('--frames', type=int, default=0, help='zero runs until closed')
    parser.add_argument('--ui-scale', type=float, default=1.0)
    parser.add_argument('--width', type=int, default=2240)
    parser.add_argument('--height', type=int, default=1600)
    parser.add_argument('--offscreen', type=Path, metavar='PNG')
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument('--record-input', type=Path, metavar='PATH')
    inputs.add_argument('--replay-input', type=Path, metavar='PATH')
    parser.add_argument('--replay-mode', choices=('paced', 'controlled'), default='paced')
    parser.add_argument('--replay-report', type=Path, metavar='PATH')


def _input_options(args, viewer=None):
    record = getattr(args, 'record_input', None)
    replay = getattr(args, 'replay_input', None)
    mode = getattr(args, 'replay_mode', 'paced')
    report = getattr(args, 'replay_report', None)
    if record and replay:
        raise ValueError('--record-input and --replay-input are mutually exclusive')
    if (record or replay) and args.offscreen:
        raise ValueError('input recording and replay require an interactive host window')
    if mode != 'paced' and not replay:
        raise ValueError('--replay-mode requires --replay-input')
    if report and not replay:
        raise ValueError('--replay-report requires --replay-input')
    if (record or replay) and (
        viewer is None or not hasattr(viewer, 'cursor') or not hasattr(viewer, 'slices')
    ):
        raise ValueError('input replay is currently supported only by linked review app 2')
    return record, replay, mode, report


def _input_api():
    """Load optional trace modules before opening a native window."""
    try:
        import datoviz  # noqa: PLC0415
        from datoviz import input_replay, input_trace  # noqa: PLC0415
    except ImportError as error:
        raise RuntimeError(
            'input recording/replay requires a Datoviz build providing '
            'the optional datoviz.input_replay API'
        ) from error
    if (
        not all(callable(getattr(input_replay, name, None)) for name in ('Recorder', 'Player'))
        or not all(
            callable(getattr(input_trace, name, None))
            for name in ('write_trace', 'read_trace', 'plain')
        )
        or not callable(getattr(datoviz, 'dvz_app_step', None))
    ):
        raise RuntimeError(
            'configured Datoviz does not provide the complete optional '
            'datoviz.input_replay API; use the matching v0.4 development checkout'
        )
    return input_replay, input_trace


def _input_runner(viewer, args, input_replay, input_trace, *, title, app_id, preset, run_loop):
    """Run one opt-in trace against a resolved linked scientific fixture."""
    from ibl_datoviz.interaction_benchmark import (  # noqa: PLC0415
        LinkedReadiness,
        ReviewFixture,
        scientific_state,
    )

    record, replay, mode, report_path = _input_options(args, viewer)
    metadata = {
        'app_id': app_id,
        'preset': preset,
        'mapping': viewer.mapping,
        'width': viewer.width,
        'height': viewer.height,
        'ui_scale': viewer.ui_scale,
        'title': title,
        'sidebar_width': getattr(viewer, 'sidebar_width', None),
        'fit_workarea': getattr(viewer, 'fit_workarea', None),
        'layout': 'linked-four-panel',
        'layout_warmup_frames': INPUT_FIXTURE_WARMUP_FRAMES,
        'hover': bool(getattr(viewer, 'enable_hover', False)),
        'fixture_options': dict(getattr(viewer, 'review_fixture_options', {})),
    }
    readiness = LinkedReadiness(viewer)
    try:
        baseline = _settle_linked_readiness(
            viewer, readiness, warmup_frames=INPUT_FIXTURE_WARMUP_FRAMES
        )
        if baseline.status != 'ready':
            raise RuntimeError(
                f'linked review is not ready at input boundary: {baseline.to_dict()}'
            )
        fixture = ReviewFixture.capture(
            viewer,
            fixture_id='ibl-datoviz-linked-review-v1',
            app_id=app_id,
            preset=preset,
            metadata={
                **metadata,
                'sidebar_rect': _sidebar_rect(viewer),
                'panel_rects': _panel_rects(viewer),
            },
        )
        if replay:
            trace = input_trace.read_trace(replay)
            trace_fixture = input_trace.plain(getattr(trace, 'manifest', {})).get('fixture')
            if not isinstance(trace_fixture, Mapping):
                raise ValueError('input trace has no linked review fixture identity')
            fixture.assert_compatible(trace_fixture.get('metadata', {}))
            if trace_fixture.get('app_id') != app_id:
                raise ValueError('input trace belongs to a different review app')
            if trace_fixture.get('preset') != preset:
                raise ValueError('input trace preset does not match this review run')
            if trace_fixture.get('initial_state') != fixture.initial_state:
                raise ValueError(
                    'input trace initial scientific state does not match this review run'
                )

            def finalize(pump):
                final_readiness = _settle_linked_readiness(viewer, readiness, pump=pump)
                return {
                    'ibl_final_scientific_state': scientific_state(viewer),
                    'ibl_final_slice_readiness': final_readiness.to_dict(),
                    'ibl_display_checkpoint': readiness.checkpoint(render_proof=None).to_dict(),
                    'ibl_benchmark_verdict': 'unavailable',
                    'ibl_benchmark_verdict_reason': (
                        'rendered display proof and expected scientific checkpoint '
                        'comparison were not established'
                    ),
                }

            report = dict(
                input_replay.Player(viewer.dvz, viewer.app, viewer.view).run(
                    trace, mode=mode, tick_seconds=1 / 120, finalize=finalize
                )
            )
            if report_path:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report, indent=2) + '\n')
            final_readiness = report.get('finalization', {}).get('ibl_final_slice_readiness', {})
            if final_readiness.get('status') != 'ready':
                raise RuntimeError(f'linked review did not settle after replay: {final_readiness}')
            return

        recorder = input_replay.Recorder(viewer.dvz, viewer.view, fixture=fixture.to_dict())
        recorder.start()
        try:
            run_loop()
        finally:
            trace = recorder.stop()
            input_trace.write_trace(trace, record)
    finally:
        readiness.close()


def _settle_linked_readiness(viewer, readiness, *, pump=None, warmup_frames=0):
    """Draw requested owner-thread warmup frames, then settle current slice uploads."""
    if pump is None:
        app_step = getattr(viewer.dvz, 'dvz_app_step', None)
        if not callable(app_step):
            raise RuntimeError('input replay requires Datoviz dvz_app_step support')

        def pump():
            outcome = app_step(viewer.app, 0.01)
            if outcome < 0:
                raise RuntimeError(f'Datoviz owner-thread app step failed: {outcome}')

    for _ in range(warmup_frames):
        request_frame = getattr(viewer.dvz, 'dvz_view_request_frame', None)
        if not callable(request_frame):
            raise RuntimeError('input replay requires Datoviz dvz_view_request_frame support')
        if request_frame(viewer.view) != 0:
            raise RuntimeError('could not request linked review fixture warmup frame')
        pump()
    baseline = readiness.check()
    if baseline.status == 'pending':
        return readiness.wait(timeout=10.0, pump=pump)
    return baseline


def _sidebar_rect(viewer):
    """Capture the resolved GUI sidebar rect after the owner-thread warmup."""
    rect = getattr(getattr(viewer, '_sidebar', None), 'sidebar_rect', None)
    if rect is None:
        raise RuntimeError('linked review GUI did not resolve its sidebar layout')
    return [float(value) for value in rect]


def _panel_rects(viewer):
    """Copy actual panel bounds, preferring the ABI-simple inner/plot getters."""
    dvz = viewer.dvz
    inner_getter = getattr(dvz, 'dvz_panel_inner_rect_px', None)
    plot_getter = getattr(dvz, 'dvz_panel_plot_rect_px', None)
    rect_type = getattr(dvz, 'DvzRect', None)
    if callable(inner_getter) and callable(plot_getter) and rect_type is not None:
        panels = {**viewer.slice_panels, '3d': viewer.panel}
        result = {}
        for name, panel in panels.items():
            rects = {}
            for kind, getter in (('inner', inner_getter), ('plot', plot_getter)):
                rect = rect_type()
                if not getter(panel, ctypes.byref(rect)):
                    raise RuntimeError(f'could not read the {name} panel {kind} rectangle')
                rects[kind] = [
                    float(rect.x),
                    float(rect.y),
                    float(rect.width),
                    float(rect.height),
                ]
            result[name] = rects
        return result

    # Retain compatibility with builds that expose only snapshot frame info.
    resolve = getattr(dvz, 'dvz_panel_resolve_frame', None)
    get_info = getattr(dvz, 'dvz_panel_frame_info', None)
    unref = getattr(dvz, 'dvz_panel_frame_unref', None)
    info_type = getattr(dvz, 'DvzPanelFrameInfo', None)
    if not all(callable(value) for value in (resolve, get_info, unref)) or info_type is None:
        return None
    panels = {**viewer.slice_panels, '3d': viewer.panel}
    result = {}
    for name, panel in panels.items():
        snapshot = resolve(panel)
        if not snapshot:
            raise RuntimeError(f'could not resolve the {name} panel layout')
        try:
            info = info_type()
            info.struct_size = ctypes.sizeof(info)
            if not get_info(snapshot, ctypes.byref(info)):
                raise RuntimeError(f'could not read the {name} panel layout')
            rect = info.panel_rect_px
            result[name] = [
                float(rect.x),
                float(rect.y),
                float(rect.width),
                float(rect.height),
            ]
        finally:
            unref(snapshot)
    return result


def finish_review(viewer, args, title, *, app_id='2', preset='overlay'):
    """Use the caller-owned viewer's existing capture or interactive frame loop."""
    if args.frames < 0:
        raise ValueError('frames must be nonnegative')
    record, replay, _mode, _report = _input_options(args, viewer)
    if args.offscreen:
        rgba = viewer.render_offscreen(args.offscreen)
        print(f'wrote {args.offscreen} ({rgba.shape[1]}x{rgba.shape[0]})')
    elif not (record or replay):
        viewer.show(title=title, frame_count=args.frames)
    else:
        input_replay, input_trace = _input_api()
        viewer.show(
            title=title,
            frame_count=args.frames,
            runner=lambda current, run_loop: _input_runner(
                current,
                args,
                input_replay,
                input_trace,
                title=title,
                app_id=app_id,
                preset=preset,
                run_loop=run_loop,
            ),
        )


def load_review_slice(source, axis, index=None, mapping='allen', *, layer='anatomy', opacity=1.0):
    """Prepare one physical rectangle using the same orientation as the linked slices.

    Corners follow pixel edges through the source affine; no fitted geometry,
    reorientation of scientific coordinates or resampling is introduced.
    """
    composer = source if isinstance(source, AtlasSliceComposer) else None
    if composer is not None:
        source = composer.volumes
    if isinstance(source, (str, Path)):
        source = open_volume_pack(source).load_volumes()
    if axis not in SLICE_DISPLAY_AXES or layer not in ('anatomy', 'annotation'):
        raise ValueError('slice axis/layer must be AP/ML/DV and anatomy/annotation')
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('plane opacity must be finite and in [0, 1]')
    grid = source.grid
    fixed = grid.array_axes.index(axis)
    if index is None:
        index = grid.shape[fixed] // 2
    if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
        raise ValueError('slice index must be an integer')
    if not 0 <= index < grid.shape[fixed]:
        raise ValueError('slice index is outside the source grid')
    if composer is None:
        composer = AtlasSliceComposer(source, mapping)
    elif composer.mapping != mapping:
        composer.set_mapping(mapping)
    anatomy, annotation = composer.compose_layers(axis, int(index), annotation_opacity=1.0)
    pixels = np.array(anatomy if layer == 'anatomy' else annotation, copy=True)
    pixels[..., 3] = np.rint(pixels[..., 3].astype(float) * opacity).astype(np.uint8)
    matrix = np.asarray(grid.index_to_world_um_matrix, dtype=float).reshape(4, 4)
    x_axis, y_axis = SLICE_DISPLAY_AXES[axis]

    def bounds(name):
        array_axis = grid.array_axes.index(name)
        world_axis = grid.world_axes.index(name)
        linear = matrix[:3, array_axis]
        if np.count_nonzero(np.abs(linear) > 1e-8) != 1 or linear[world_axis] == 0:
            raise ValueError('physical slices require the axis-aligned source grid')
        ends = (-0.5, grid.shape[array_axis] - 0.5)
        return ends if linear[world_axis] > 0 else ends[::-1]

    x0, x1 = bounds(x_axis)
    y0, y1 = bounds(y_axis)
    corners = np.zeros((4, 3), dtype=float)
    corners[:, fixed] = index
    corners[:, grid.array_axes.index(x_axis)] = (x0, x0, x1, x1)
    corners[:, grid.array_axes.index(y_axis)] = (y0, y1, y0, y1)
    return SampledPlane.from_arrays(
        grid.index_to_world(corners),
        pixels,
        sampling='linear' if layer == 'anatomy' else 'nearest',
    )


class ReviewControls:
    """Share anatomical style controls without changing the app's view structure."""

    def __init__(self, viewer):
        """Remember an explicit reset target and own only Python GUI input buffers."""
        self.viewer = viewer
        self.initial_mapping = viewer.mapping
        self.initial_camera = viewer.camera_angles
        self.initial_opacity = viewer.surface_opacity
        self.initial_context_opacity = getattr(viewer, 'context_opacity', None)
        self.error = None
        self._region_key = None
        self._available_regions = {}
        self._region_opacity = ctypes.c_float(1)
        self._region_visible = ctypes.c_bool(True)
        self._region_color = (ctypes.c_float * 4)(1, 1, 1, 1)

    def reset(self):
        """Explicitly reset appearance and camera; ordinary layer edits never do so."""
        viewer = self.viewer
        viewer.set_mapping(self.initial_mapping)
        viewer.clear_selection()
        viewer.reset_surface_style()
        viewer.set_surface_visible(True)
        viewer.set_surface_opacity(self.initial_opacity)
        if self.initial_context_opacity is not None:
            viewer.set_context_opacity(self.initial_context_opacity)
        viewer.set_explode(0)
        viewer.set_camera_angles(self.initial_camera)
        self._region_key = None
        self.error = None

    def _attempt(self, callback, *args):
        try:
            callback(*args)
            self.error = None
        except (ValueError, RuntimeError) as error:
            self.error = str(error)
            self._region_key = None

    def draw(self, gui):
        """Draw stable control IDs and read state back from the authoritative model."""
        dvz = self.viewer.dvz
        if getattr(self.viewer, 'anatomy_presentation', None) == 'major':
            opacity = ctypes.c_float(self.viewer.context_opacity)
            if dvz.dvz_gui_slider_float(gui, b'Context opacity', ctypes.byref(opacity), 0, 1):
                self._attempt(self.viewer.set_context_opacity, opacity.value)
            if self.error:
                dvz.dvz_gui_text(gui, f'Change failed: {self.error}'.encode())
            return
        if dvz.dvz_gui_collapsing_header(gui, b'3D atlas', 1 << 5):
            visible = ctypes.c_bool(self.viewer._surface_visible)
            if dvz.dvz_gui_checkbox(gui, b'Atlas visible', ctypes.byref(visible)):
                self._attempt(self.viewer.set_surface_visible, visible.value)
            self._draw_styles(gui)
        if self.error:
            dvz.dvz_gui_text(gui, f'Change failed: {self.error}'.encode())

    def _draw_styles(self, gui):
        viewer, dvz = self.viewer, self.viewer.dvz
        if hasattr(viewer, 'slice_panels'):
            dvz.dvz_gui_text(gui, b'Slice labels keep mapping colors.')
        opacity = ctypes.c_float(viewer.surface_opacity)
        if dvz.dvz_gui_slider_float(gui, b'Surface opacity', ctypes.byref(opacity), 0, 1):
            self._attempt(viewer.set_surface_opacity, opacity.value)
        regions = viewer.selected_region_ids()
        if not regions:
            dvz.dvz_gui_text(gui, b'Select a surface or tree region to edit its style.')
            return
        region = regions[0]
        if viewer.mapping not in self._available_regions:
            self._available_regions[viewer.mapping] = set(
                np.unique(viewer.mesh_data.face_mapping_ids(viewer.mapping)).tolist()
            )
        if region not in self._available_regions[viewer.mapping]:
            dvz.dvz_gui_text(gui, b'The selected region has no displayed mesh faces.')
            return
        key = (viewer.mapping, region)
        if key != self._region_key:
            style = viewer._surface_style.regions.get(key, RegionStyle())
            color = style.color
            if color is None:
                color = (viewer.palette or {}).get(region, (120, 160, 220, 255))
            rgba = tuple(color) if len(color) == 4 else (*color, 255)
            self._region_color[:] = np.asarray(rgba, dtype=float) / 255
            self._region_opacity.value = style.opacity
            self._region_visible.value = style.visible
            self._region_key = key
        label = viewer.tree_model.describe(region) if viewer.tree_model else str(abs(region))
        acronym = label.partition(' — ')[0]
        side = 'Left' if region < 0 else 'Right'
        dvz.dvz_gui_text(gui, f'{acronym} ({side})'.encode())
        if len(regions) > 1:
            dvz.dvz_gui_text(gui, f'Editing the first of {len(regions)} selected regions'.encode())
        if dvz.dvz_gui_checkbox(gui, b'Region visible', ctypes.byref(self._region_visible)):
            self._attempt(viewer.set_region_visible, region, bool(self._region_visible.value))
        if dvz.dvz_gui_slider_float(
            gui, b'Region opacity', ctypes.byref(self._region_opacity), 0, 1
        ):
            self._attempt(viewer.set_region_opacity, region, float(self._region_opacity.value))
        if dvz.dvz_gui_color_edit4(gui, b'Region RGBA', self._region_color, 0):
            color = np.rint(np.clip(self._region_color, 0, 1) * 255).astype(np.uint8)
            self._attempt(viewer.set_region_color, region, color)
        if dvz.dvz_gui_button(gui, b'Reset this region style'):
            self._attempt(viewer.reset_region_style, region)
            self._region_key = None
