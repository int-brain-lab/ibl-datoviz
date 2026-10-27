"""Offline scientific figures with embedded raster, legends and source receipts."""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict
from html import escape
from pathlib import Path

import numpy as np

from .analysis_export import frame_record, plain, write_json
from .layers import _color


def _digest(array):
    return hashlib.sha256(np.asarray(array).tobytes()).hexdigest()


def _layer_record(layer):
    data = layer.scalar_data
    payload = layer.payload
    return {
        'attachment_id': layer.refs[0].attachment_id if layer.refs else None,
        'name': layer.name,
        'payload_type': type(payload).__name__,
        'ids': list(payload.ids),
        'source_keys': (
            [asdict(key) for key in payload.observation_keys]
            if payload.observation_keys is not None else None
        ),
        'frame': frame_record(payload.frame),
        'provenance': plain(payload.provenance),
        'positions_sha256': (
            [_digest(line) for line in payload.positions_um]
            if layer.capabilities.width_px else _digest(payload.positions_um)
        ),
        'visible': layer.visible,
        'effective_visible': layer.effective_visible,
        'glyph': layer._glyph,
        'size': layer._size,
        'color_mode': 'scalar' if layer.scalar_encoding is not None else 'uniform',
        'uniform_color': layer._uniform_color,
        'measurement': None if data is None else {
            'name': data.name, 'units': data.units,
            'values_sha256': _digest(data.values),
            'finite': data._counts[0], 'missing': data._counts[1],
            'cmap': data.cmap, 'limits': list(data.limits),
            'missing_color': data.missing_color,
        },
    }


def _legend(layer, y):
    label = escape(layer.name or type(layer.payload).__name__)
    data = layer.scalar_encoding
    if data is None:
        color = _color(layer._uniform_color)
        return (
            f'<rect x="24" y="{y - 14}" width="18" height="18" '
            f'fill="#{bytes(color[:3]).hex()}" fill-opacity="{color[3] / 255}"/>'
            f'<text x="54" y="{y}">{label} · single color</text>'
        )
    values = np.linspace(*data.limits, 48)
    colors = layer._registry._scalar_colors(
        values, data.cmap, np.asarray(data.limits), data.missing_color
    )
    samples = ''.join(
        f'<rect x="{24 + index * 6}" y="{y + 10}" width="6" height="14" '
        f'fill="#{bytes(color[:3]).hex()}" fill-opacity="{color[3] / 255}"/>'
        for index, color in enumerate(colors)
    )
    missing = _color(data.missing_color)
    return (
        f'<text x="24" y="{y}">{label}: {escape(data.name)} ({escape(data.units)})</text>'
        + samples
        + f'<text x="24" y="{y + 44}">{data.limits[0]:.4g}</text>'
        f'<text x="312" y="{y + 44}" text-anchor="end">{data.limits[1]:.4g}</text>'
        f'<rect x="334" y="{y + 10}" width="14" height="14" '
        f'fill="#{bytes(missing[:3]).hex()}" fill-opacity="{missing[3] / 255}"/>'
        f'<text x="358" y="{y + 23}">{data._counts[1]} missing</text>'
    )


def _panel_labels(viewer):
    if not viewer.slices.available:
        return ''
    ml, ap, dv = viewer.slices.position.world_um
    labels = (
        (24, 74, f'Coronal · AP {ap:.4g} µm · ML / dorsal'),
        (viewer.width / 2 + 24, 74, f'Sagittal · ML {ml:.4g} µm · AP / dorsal'),
        (24, viewer.height / 2 + 74, f'Horizontal · DV {dv:.4g} µm · ML / anterior'),
        (viewer.width / 2 + 24, viewer.height / 2 + 74, '3D anatomical context'),
    )
    return ''.join(f'<text x="{x}" y="{y}">{escape(text)}</text>' for x, y, text in labels)


def export_figure(viewer, directory, *, title):
    """Write a new PNG/SVG/JSON bundle from an offline viewer, without overwrites."""
    viewer._require_open()
    if viewer.app is not None:
        raise RuntimeError(
            'export a figure before show() or render_offscreen(); use a fresh viewer'
        )
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError(directory)
    if not isinstance(title, str) or not title.strip():
        raise ValueError('figure title must be a nonempty string')
    # Validate all metadata before native capture or filesystem changes.
    layers = [_layer_record(layer) for layer in viewer.layers]
    selection = viewer.selection.to_records()
    json.dumps({'layers': layers, 'selection': selection}, allow_nan=False)
    with tempfile.TemporaryDirectory(prefix='ibl-datoviz-figure-') as temporary:
        staging = Path(temporary)
        viewer.render_offscreen(staging / 'scene.png')
        png = (staging / 'scene.png').read_bytes()
        visible = [layer for layer in viewer.layers if layer.effective_visible]
        width = max(640, viewer.width)
        height = viewer.height + 120 + 80 * len(visible)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" fill="#1d2127"/>'
            '<g fill="#eeeeee" font-family="sans-serif" font-size="16">'
            f'<text x="24" y="30" font-size="22">{escape(title)}</text>'
            f'<image x="0" y="48" width="{viewer.width}" height="{viewer.height}" '
            f'xlink:href="data:image/png;base64,{base64.b64encode(png).decode()}"/>'
            + _panel_labels(viewer)
            + ''.join(_legend(layer, viewer.height + 80 + index * 80)
                      for index, layer in enumerate(visible))
            + f'<text x="24" y="{height - 16}">'
            f'{escape(viewer.mapping)} · ML/AP/DV in µm · '
            'magenta: selected observations · provenance.json</text></g></svg>\n'
        )
        (staging / 'figure.svg').write_text(svg, encoding='utf-8')
        storage = ctypes.create_string_buffer(64 + 15)
        offset = (-ctypes.addressof(storage)) % 16
        model = ((ctypes.c_float * 4) * 4).from_buffer(storage, offset)
        viewer._check(viewer.dvz.dvz_arcball_model(viewer.arcball, model), 'figure camera')
        from . import __version__  # noqa: PLC0415

        receipt = {
            'schema': 'ibl-datoviz-figure-v1',
            'ibl_datoviz_version': __version__,
            'title': title, 'image_size_px': [viewer.width, viewer.height],
            'image_scope': 'scientific scene; no application controls',
            'frame': frame_record(viewer.frame),
            'mapping': viewer.mapping, 'layout': viewer.layout,
            'atlas': {
                'positions_sha256': _digest(viewer.mesh_data.positions_um),
                'indices_sha256': _digest(viewer.mesh_data.indices),
                'anatomy_presentation': viewer.anatomy_presentation,
                'context_opacity': viewer.context_opacity,
                'surface_opacity': viewer.surface_opacity,
                'explode': viewer.explode,
                'selection_presentation': viewer.selection_presentation,
                'hemispheres': dict(viewer._surface_presentation.style.hemispheres),
                'region_overrides': [
                    {'mapping': mapping, 'signed_region_id': region_id, **asdict(style)}
                    for (mapping, region_id), style
                    in viewer._surface_presentation.style.regions.items()
                ],
                'context_surfaces': [
                    {'source_allen_id': surface.source_allen_id,
                     'name': surface.name, 'color': list(surface.color),
                     'positions_sha256': _digest(surface.geometry.mesh.positions_um),
                     'indices_sha256': _digest(surface.geometry.mesh.indices)}
                    for surface in (
                        viewer._anatomical_context.surfaces
                        if viewer._anatomical_context is not None else ()
                    )
                ],
            },
            'camera_model': np.ctypeslib.as_array(model).tolist(),
            'camera_angles': list(viewer.camera_angles),
            'cursor': asdict(viewer.slices.position) if viewer.slices.available else None,
            'slice_presentation': (
                {name: getattr(viewer._linked, name) for name in (
                    'anatomy_visible', 'annotation_visible', 'boundaries_visible',
                    'annotation_opacity', 'boundary_opacity', 'boundary_width_px',
                    'volume_opacity', 'slice_renderer',
                )} if viewer.slices.available else None
            ),
            'selected_regions': [
                {'mapping': mapping, 'signed_region_id': region_id}
                for mapping, region_id in viewer.selection.regions
            ],
            'selected_observations': selection,
            'layers': layers,
            'recordings': [
                {'source': asdict(group.recording.source),
                 'insertion_id': group.recording.insertion_id,
                 'session_id': group.recording.session_id,
                 'provenance': plain(group.recording.provenance)}
                for group in viewer.recordings
            ],
            'files': {
                'scene.png': hashlib.sha256(png).hexdigest(),
                'figure.svg': hashlib.sha256(svg.encode()).hexdigest(),
            },
            'limitations': [
                'Geometry/value hashes identify supplied arrays; source data are not bundled.',
                'A coordinate declaration does not establish alignment or source validation.',
                'SVG embeds raster rendering; scientific geometry is not vectorized.',
                'This receipt is not a restorable workspace or an executable analysis.',
            ],
        }
        write_json(staging / 'provenance.json', receipt)
        directory.mkdir(parents=True, exist_ok=False)
        try:
            for name in ('scene.png', 'figure.svg', 'provenance.json'):
                shutil.copyfile(staging / name, directory / name)
        except Exception:
            shutil.rmtree(directory)
            raise
    return directory
