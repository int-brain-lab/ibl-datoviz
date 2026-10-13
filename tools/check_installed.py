#!/usr/bin/env python3
"""Check installed wheel APIs and bundled anatomy locks without loading native code.

Run with the isolated environment's ``python -I tools/check_installed.py``.
The small arrays are packaging smoke inputs, not scientific atlas fixtures.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from importlib.metadata import distribution
from pathlib import Path

import numpy as np


def check_installation():
    """Reject editable/source imports and exercise the installed CPU contracts."""
    if not sys.flags.isolated:
        raise RuntimeError('run this check with python -I to exclude source-path overrides')
    packages = {}
    prefix = Path(sys.prefix).resolve()
    for name, module_name in (
        ('ibl-datoviz', 'ibl_datoviz'),
        ('ibl-anatomy', 'ibl_anatomy'),
        ('datoviz', 'datoviz'),
    ):
        installed = distribution(name)
        origin = json.loads(installed.read_text('direct_url.json') or '{}')
        if origin.get('dir_info', {}).get('editable'):
            raise RuntimeError(f'{name} is editable; install the built wheel instead')
        module = import_module(module_name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(prefix):
            raise RuntimeError(f'{name} was imported outside the isolated environment: {path}')
        packages[name] = {'version': installed.version, 'module': str(path), 'origin': origin}

    ibl_anatomy = import_module('ibl_anatomy')
    ibl_datoviz = import_module('ibl_datoviz')

    for name in ibl_datoviz.__all__:
        if not hasattr(ibl_datoviz, name):
            raise RuntimeError(f'missing public API: {name}')

    positions = np.array([[0, 0, 0], [1, 2, 3]], dtype=np.float32)
    points = ibl_datoviz.PointCollection.from_arrays(
        positions, [[255, 0, 0, 255], [0, 255, 0, 128]]
    )
    trajectory = ibl_datoviz.InsertionTrajectory.from_arrays(positions)
    plane = ibl_datoviz.SampledPlane.from_arrays(
        [[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 0]],
        np.full((2, 2, 4), 255, dtype=np.uint8),
    )
    positions[:] = -100
    for payload in (points.positions_um, trajectory.positions_um, plane.corners_um, plane.rgba):
        if payload.flags.writeable or not payload.flags.c_contiguous:
            raise RuntimeError('installed payload does not retain immutable contiguous storage')
    if points.positions_um[0, 0] != 0 or trajectory.positions_um[0, 0] != 0:
        raise RuntimeError('installed payload retained caller-owned coordinates')

    surface = ibl_anatomy.bundled_surface_asset()
    atlas = ibl_anatomy.bundled_asset_set()
    registered = ibl_anatomy.bundled_registered_asset_set()
    if surface.reference_space_id != atlas.reference_space_id:
        raise RuntimeError('bundled surface and atlas reference spaces differ')
    if 'datoviz._ctypes' in sys.modules:
        raise RuntimeError('CPU installation check unexpectedly loaded native bindings')
    return {
        'status': 'passed-cpu-installation',
        'python': sys.version,
        'packages': packages,
        'public_api': ibl_datoviz.__all__,
        'bundled_assets': {
            'surface': surface.asset_id,
            'surface_source_sha256': surface.source.sha256,
            'atlas': atlas.asset_set_id,
            'registered': registered.asset_set_id,
        },
        'native_rendering': 'not-run',
    }


if __name__ == '__main__':
    print(json.dumps(check_installation(), indent=2, sort_keys=True))
