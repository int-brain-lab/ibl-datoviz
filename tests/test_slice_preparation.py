from dataclasses import replace
from threading import Event, Thread
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_anatomy import open_volume_pack
from ibl_datoviz import LinkedAtlasNavigator
from ibl_datoviz.navigator import AtlasCursor, AtlasSliceComposer
from ibl_datoviz.slice_preparation import (
    PreparedSliceLayers,
    SlicePreparation,
    prepare_slice_layers,
)
from ibl_datoviz.slice_scheduler import SliceRequest, SliceScheduler
from ibl_datoviz.viewer import AtlasViewer
from tests import FIXTURES

VOLUME_FIXTURE = FIXTURES / 'volume-pack-v1' / 'pack'


@pytest.fixture
def source():
    return open_volume_pack(VOLUME_FIXTURE).load_volumes()


def test_prepared_layers_detach_every_array_and_freeze_storage():
    image = np.zeros((2, 3, 4), dtype=np.uint8)
    boundaries = np.arange(12, dtype=np.float32).reshape(6, 2)[::2]
    payload = PreparedSliceLayers(image, image, boundaries, boundaries)
    for name, original, dtype in (
        ('anatomy', image, np.uint8),
        ('annotation', image, np.uint8),
        ('boundary_starts', boundaries, np.float32),
        ('boundary_ends', boundaries, np.float32),
    ):
        values = getattr(payload, name)
        assert values.dtype == dtype
        assert values.flags.c_contiguous
        assert not values.flags.writeable
        assert not np.shares_memory(values, original)
        assert original.flags.writeable
        with pytest.raises(ValueError, match='read-only'):
            values.flat[0] = 99
    image[:] = 1
    boundaries[:] = 99
    assert payload.anatomy.max() == 0
    assert payload.boundary_starts.max() != 99


@pytest.mark.parametrize('mapping', ['allen', 'beryl', 'cosmos'])
@pytest.mark.parametrize('visible', [True, False])
def test_sync_and_worker_preparation_match_without_mutating_cache(source, mapping, visible):
    composer = AtlasSliceComposer(source)
    worker = SlicePreparation(source, 'allen')
    request = SliceRequest(
        'dv', 1, 3, mapping=mapping, annotation_opacity=0.4,
        selected_region_ids=(315,), selection_dim_factor=0.2,
        anatomy_visible=visible, annotation_visible=visible,
    )
    synchronous = prepare_slice_layers(composer, request)
    asynchronous = worker(request)
    for name in ('anatomy', 'annotation', 'boundary_starts', 'boundary_ends'):
        assert np.array_equal(getattr(synchronous, name), getattr(asynchronous, name))
    cached_starts, cached_ends = composer.boundary_segments('dv', 1)
    assert not np.shares_memory(synchronous.boundary_starts, cached_starts)
    assert not np.shares_memory(synchronous.boundary_ends, cached_ends)
    if not visible:
        assert synchronous.anatomy[..., 3].max() == 0
        assert synchronous.annotation[..., 3].max() == 0


def test_owner_request_captures_state_before_worker_runs(source):
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    viewer.cursor = AtlasCursor(2, 2, 1)
    viewer._slice_revisions = {'dv': 3}
    viewer._slice_source_id = 'registered-10um'
    viewer.mapping = 'allen'
    viewer.annotation_opacity = 0.4
    viewer.anatomy_visible = True
    viewer.annotation_visible = True
    viewer._selected_region_ids = [315]
    viewer.selection_dim_factor = 0.2
    request = viewer._slice_request('dv')
    viewer.cursor = AtlasCursor(2, 2, 2)
    viewer.mapping = 'cosmos'
    viewer._selected_region_ids[:] = [997]
    viewer.anatomy_visible = False
    # Worker is independent of the viewer, including its native attributes.
    viewer.dvz = SimpleNamespace()
    assert request.index == 1
    assert request.mapping == 'allen'
    assert request.selected_region_ids == (315,)
    assert request.anatomy_visible
    assert request.source_id == 'registered-10um'
    payload = SlicePreparation(source, 'allen')(request)
    assert payload.anatomy[..., 3].max() > 0


@pytest.mark.parametrize(
    'change', [{'index': 2}, {'mapping': 'beryl'}, {'selected_region_ids': (315,)}]
)
def test_worker_rejects_stale_cursor_mapping_or_selection_payload(source, change):
    started, release, notified = Event(), Event(), Event()
    worker = SlicePreparation(source, 'allen')
    old = SliceRequest('dv', 1, 1)
    current = replace(old, revision=2, **change)

    def prepare(request):
        payload = worker(request)
        if request.revision == 1:
            started.set()
            assert release.wait(2)
        return payload

    scheduler = SliceScheduler(prepare, notify=lambda _axis: notified.set(), max_workers=1)
    try:
        scheduler.submit(old)
        assert started.wait(2)
        scheduler.submit(current)
        release.set()
        assert notified.wait(2)
        ready = scheduler.drain_ready()
        assert [item.request for item in ready] == [current]
        expected = worker(current)
        assert np.array_equal(ready[0].payload.annotation, expected.annotation)
    finally:
        release.set()
        scheduler.close()


def test_navigator_close_joins_preparation_before_destroying_scene(monkeypatch):
    started, release, finished, closing, destroyed = (Event() for _ in range(5))

    def prepare(_request):
        started.set()
        assert release.wait(2)
        finished.set()
        return object()

    scheduler = SliceScheduler(prepare, max_workers=1)
    real_close = scheduler.close

    def close_workers():
        closing.set()
        real_close()

    def close_scene(_viewer):
        assert finished.is_set()
        destroyed.set()

    scheduler.close = close_workers
    monkeypatch.setattr(AtlasViewer, 'close', close_scene)
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    viewer._slice_loader = scheduler
    viewer._input_subscription = 0
    scheduler.submit(SliceRequest('dv', 1, 1))
    assert started.wait(2)
    close_thread = Thread(target=viewer.close)
    close_thread.start()
    try:
        assert closing.wait(2)
        assert not destroyed.is_set()
        release.set()
        close_thread.join(2)
        assert not close_thread.is_alive()
        assert destroyed.is_set()
        assert viewer._slice_loader is None
    finally:
        release.set()
        close_thread.join(2)
        real_close()


def test_empty_boundary_upload_hides_without_native_zero_count_updates():
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    events = []
    visual = object()
    viewer.boundary_color = (238, 242, 247)
    viewer.boundary_opacity = 0.82
    viewer.boundaries_visible = True
    viewer.boundary_width_px = 0.7
    viewer.dvz = SimpleNamespace(
        dvz_visual_set_data_many=lambda handle, data: events.append(('data', handle, data)) or 0,
        dvz_visual_set_visible=lambda handle, shown: (
            events.append(('visible', handle, shown)) or 0
        ),
    )
    empty = np.empty((0, 3), dtype=np.float32)
    viewer._upload_boundaries(visual, empty, empty, 'boundaries')
    assert events == [('visible', visual, False)]
    events.clear()
    nonempty = np.zeros((2, 3), dtype=np.float32)
    viewer._upload_boundaries(visual, nonempty, nonempty, 'boundaries')
    assert [event[0] for event in events] == ['data', 'visible']
    assert events[-1] == ('visible', visual, True)
    assert all(len(values) == 2 for values in events[0][2].values())
    events.clear()
    viewer._upload_boundaries(visual, empty, empty, 'boundaries')
    assert events == [('visible', visual, False)]


def test_boundary_visibility_failure_is_checked():
    viewer = LinkedAtlasNavigator.__new__(LinkedAtlasNavigator)
    viewer.dvz = SimpleNamespace(dvz_visual_set_visible=lambda *_args: -1)
    empty = np.empty((0, 3), dtype=np.float32)
    with pytest.raises(RuntimeError, match='boundaries visibility'):
        viewer._upload_boundaries(object(), empty, empty, 'boundaries')
