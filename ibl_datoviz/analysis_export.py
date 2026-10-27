"""Detached analysis records over exact retained identities, never renderer indices."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .payloads import Sites


def plain(value):
    """Copy retained metadata into strict JSON values, preserving missing numbers."""
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [plain(item) for item in value]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def frame_record(frame):
    """Copy coordinate declarations without asserting scientific validation."""
    return {
        'reference_space_id': frame.reference_space_id,
        'coordinate_convention': frame.coordinate_convention,
        'provenance': plain(frame.provenance),
    }


def observation_record(layer, index):
    """Detach one original observation with its supplied location and measurement."""
    payload, ref, data = layer.payload, layer.refs[index], layer.scalar_data
    measurement = None
    if data is not None:
        measurement = {
            'name': data.name,
            'units': data.units,
            'value': plain(data.values[index]),
            'status': 'finite' if np.isfinite(data.values[index]) else 'missing',
        }
    return {
        'attachment_id': ref.attachment_id,
        'layer_name': layer.name,
        'original_id': ref.original_id,
        'original_id_type': type(ref.original_id).__name__,
        'source_key': None if ref.source_key is None else asdict(ref.source_key),
        'payload_type': type(payload).__name__,
        'position_um': plain(payload.positions_um[index]),
        'positioned': bool(np.isfinite(payload.positions_um[index]).all()),
        'frame': frame_record(payload.frame),
        'allen_region_id': (
            int(payload.allen_region_ids[index])
            if getattr(payload, 'allen_region_ids', None) is not None else None
        ),
        'measurement': measurement,
        'visible': layer.visible,
        'effective_visible': layer.effective_visible,
        'provenance': plain(payload.provenance),
        'memberships': (
            [asdict(key) for key in payload.memberships[index]]
            if isinstance(payload, Sites) and payload.memberships is not None else None
        ),
    }


def selection_records(viewer):
    """Retain committed selection order, including hidden and unpositioned rows."""
    selected = set(viewer.selection.observations)
    records = {
        ref: observation_record(layer, index)
        for layer in viewer.layers
        for index, ref in enumerate(layer.refs)
        if ref in selected
    }
    return [records[ref] for ref in viewer.selection.observations]


def write_json(path, document):
    """Atomically replace a strict JSON document, creating its parent directory."""
    path = Path(path)
    content = json.dumps(document, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', dir=path.parent, prefix=f'.{path.name}.', delete=False,
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return path
