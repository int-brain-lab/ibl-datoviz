"""Shared synthetic fixture location for CI and contributor review setup."""

import os
from pathlib import Path

FIXTURES = Path(
    os.environ.get(
        'IBL_ANATOMY_FIXTURE_ROOT',
        Path(__file__).resolve().parents[2] / 'ibl-anatomy' / 'tests' / 'fixtures',
    )
)
