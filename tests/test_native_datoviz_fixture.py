"""Check that the native prerequisite skips only ordinary source-only installs."""

import pytest

from tests import conftest


def _stub_native_symbol_access(monkeypatch, error):
    def fail(name):
        if name == 'dvz_scene':
            raise error
        raise AttributeError(name)

    module = vars(conftest.datoviz)
    monkeypatch.delitem(module, 'dvz_scene', raising=False)
    monkeypatch.setitem(module, '__getattr__', fail)


def test_native_fixture_skips_missing_library_when_no_path_is_configured(monkeypatch):
    monkeypatch.delenv('DATOVIZ_LIBRARY', raising=False)

    error = RuntimeError('Unable to load libdatoviz (no candidate found)')
    _stub_native_symbol_access(monkeypatch, error)
    with pytest.raises(pytest.skip.Exception, match='Datoviz native library is not installed'):
        conftest._load_native_datoviz()


def test_native_fixture_does_not_skip_an_explicit_library_failure(monkeypatch):
    monkeypatch.setenv('DATOVIZ_LIBRARY', '/nonexistent/libdatoviz.so')

    error = RuntimeError('Unable to load libdatoviz (explicit path unavailable)')
    _stub_native_symbol_access(monkeypatch, error)
    with pytest.raises(RuntimeError, match='explicit path unavailable'):
        conftest._load_native_datoviz()


def test_native_fixture_does_not_skip_other_native_runtime_errors(monkeypatch):
    monkeypatch.delenv('DATOVIZ_LIBRARY', raising=False)

    error = RuntimeError('GPU context creation failed')
    _stub_native_symbol_access(monkeypatch, error)
    with pytest.raises(RuntimeError, match='GPU context creation failed'):
        conftest._load_native_datoviz()
