"""Volume context hooks preserve atomic public controller behavior."""

from types import SimpleNamespace

import pytest

from ibl_datoviz.slice_controller import SliceController


def owner_with_volume(hook, setter=None):
    """Create a controller owner with observable volume policy and no native scene."""
    component = SimpleNamespace(volume_opacity=0.24)
    if setter is None:

        def setter(opacity):
            component.volume_opacity = opacity

    component.set_volume_opacity = setter
    owner = SimpleNamespace(
        _linked=component,
        _closed=False,
        _require_open=lambda: None,
        _on_volume_opacity_committed=hook,
    )
    owner.close = lambda: setattr(owner, '_closed', True)
    return owner


def test_volume_context_hook_observes_committed_opacity():
    observed = []
    owner = owner_with_volume(
        lambda opacity: observed.append((opacity, owner._linked.volume_opacity))
    )
    SliceController(owner).set_volume_opacity(0.0)
    assert observed == [(0.0, 0.0)]


def test_failed_volume_context_hook_restores_prior_opacity():
    def reject(_opacity):
        raise RuntimeError('plane hide failed')

    owner = owner_with_volume(reject)
    with pytest.raises(RuntimeError, match='plane hide failed'):
        SliceController(owner).set_volume_opacity(0.7)
    assert owner._linked.volume_opacity == 0.24
    assert not owner._closed


def test_failed_volume_context_rollback_closes_viewer():
    def reject(_opacity):
        raise RuntimeError('plane hide failed')

    def upload(opacity):
        if opacity == 0.24:
            raise RuntimeError('rollback upload failed')
        owner._linked.volume_opacity = opacity

    owner = owner_with_volume(reject, upload)
    with pytest.raises(RuntimeError, match='volume context rollback failed; viewer closed'):
        SliceController(owner).set_volume_opacity(0.7)
    assert owner._closed
