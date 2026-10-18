"""Explicit prerequisites for tests that exercise native Datoviz objects."""

import os

import datoviz
import pytest


def _load_native_datoviz():
    """Return the native module, skipping only an unconfigured source-only installation."""
    try:
        _ = datoviz.dvz_scene
    except RuntimeError as error:
        if not os.environ.get('DATOVIZ_LIBRARY') and 'Unable to load libdatoviz' in str(error):
            pytest.skip('Datoviz native library is not installed')
        raise
    return datoviz


@pytest.fixture
def native_datoviz():
    """Skip source-only installs, but fail when an explicitly configured runtime cannot load."""
    return _load_native_datoviz()
