"""Gallery subprocesses must use locked anatomy despite adjacent fixture checkouts."""

import subprocess
import sys
from pathlib import Path

from tools.build_gallery import _environment


def test_gallery_uses_installed_anatomy_with_a_stale_adjacent_checkout(tmp_path, monkeypatch):
    repository = tmp_path / 'repo'
    repository.mkdir()
    stale = tmp_path / 'ibl-anatomy' / 'src' / 'ibl_anatomy'
    stale.mkdir(parents=True)
    (stale / '__init__.py').write_text("raise RuntimeError('stale anatomy checkout imported')\n")
    monkeypatch.delenv('PYTHONPATH', raising=False)
    result = subprocess.check_output(
        [
            sys.executable,
            '-c',
            'import ibl_anatomy; from ibl_anatomy import load_surface_asset; '
            'print(ibl_anatomy.__file__)',
        ],
        cwd=repository,
        env=_environment(repository),
        text=True,
    )
    assert not Path(result.strip()).resolve().is_relative_to(stale)
