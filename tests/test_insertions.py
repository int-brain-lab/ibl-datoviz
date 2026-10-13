"""Owned multiple insertion visuals with a stateful native test double."""

import numpy as np
import pytest

from ibl_datoviz.insertions import InsertionCollectionVisual, InsertionTrajectory


class FakeDatoviz:
    DVZ_ALPHA_OPAQUE = 0
    DVZ_SEGMENT_CAP_ROUND = 1
    DVZ_PATH_JOIN_ROUND = 2

    def __init__(self):
        self.visuals = {}
        self.calls = []
        self.next_handle = 1
        self.fail_next = None

    def _status(self, operation):
        self.calls.append((operation,))
        if self.fail_next == operation:
            self.fail_next = None
            return -1
        return 0

    def dvz_path(self, scene, flags):
        self.calls.append(('path', scene, flags))
        if self.fail_next == 'path':
            self.fail_next = None
            return None
        handle = self.next_handle
        self.next_handle += 1
        self.visuals[handle] = {'visible': True}
        return handle

    def dvz_path_set_caps(self, visual, first, last):
        return self._status('caps')

    def dvz_visual_set_alpha_mode(self, visual, mode):
        self.visuals[visual]['alpha_mode'] = mode
        return self._status('alpha')

    def dvz_visual_set_depth_test(self, visual, enabled):
        self.visuals[visual]['depth_test'] = enabled
        return self._status('depth')

    def dvz_path_set_join(self, visual, join, miter):
        return self._status('join')

    def dvz_visual_set_data_many(self, visual, attributes):
        # Simulate an upload that mutates before it reports failure.
        self.visuals[visual].update(
            {name: np.array(array, copy=True) for name, array in attributes.items()}
        )
        return self._status('upload')

    def dvz_visual_set_data(self, visual, name, value):
        self.visuals[visual][name] = np.array(value, copy=True)
        return self._status(f'data:{name}')

    def dvz_visual_set_visible(self, visual, visible):
        status = self._status('visible')
        if status == 0:
            self.visuals[visual]['visible'] = bool(visible)
        return status

    def dvz_panel_add_visual(self, panel, visual, desc):
        self.calls.append(('attach', panel, visual))
        return self._status('attach')

    def dvz_visual_destroy(self, visual):
        self.calls.append(('destroy', visual))
        del self.visuals[visual]


def path(count=3, start=0):
    return np.column_stack(
        (np.arange(start, start + count), np.arange(count), np.arange(count) * -1)
    ).astype(np.float32)


def test_trajectory_owns_immutable_arrays_and_rejects_transparent_or_invalid_data():
    positions = path()[::1]
    trajectory = InsertionTrajectory.from_arrays(positions, color=(1, 2, 3), width_px=2)
    positions[:] = -20
    assert trajectory.positions_um.flags.owndata
    assert trajectory.positions_um.flags.c_contiguous
    assert not trajectory.positions_um.flags.writeable
    assert trajectory.color.tolist() == [1, 2, 3, 255]
    assert not trajectory.color.flags.writeable
    assert trajectory.width_px == 2
    for points in ([], [[0, 0, 0]], [[0, 0, np.nan], [1, 1, 1]]):
        with pytest.raises(ValueError, match='positions'):
            InsertionTrajectory.from_arrays(points)
    with pytest.raises(ValueError, match='alpha|opaque|transparency'):
        InsertionTrajectory.from_arrays(path(), color=(1, 2, 3, 128))
    for width in (0, -1, np.inf, np.nan, True):
        with pytest.raises(ValueError, match='width'):
            InsertionTrajectory.from_arrays(path(), width_px=width)


@pytest.mark.parametrize('identity', ['', 0, -1, True, False, 1.0, None])
def test_invalid_insertion_identity_is_rejected(identity):
    visual = InsertionCollectionVisual(FakeDatoviz(), 'scene', 'panel')
    with pytest.raises(ValueError, match='identity'):
        visual.set_insertion(identity, path())
    visual.close()


def test_multiple_paths_update_counts_preserve_visibility_and_are_independent():
    native = FakeDatoviz()

    def transform(points):
        return points * 2 + 1

    collection = InsertionCollectionVisual(
        native, 'borrowed-scene', 'borrowed-panel', transform=transform
    )
    collection.set_insertion('first', path(4), color=(10, 20, 30), width_px=3)
    first_handle = collection._insertions['first'].visual
    collection.set_insertion(23, path(2, 10), color=(40, 50, 60, 255), width_px=5)
    second_handle = collection._insertions[23].visual
    assert collection.ids == ('first', 23)
    assert first_handle != second_handle
    np.testing.assert_array_equal(native.visuals[first_handle]['position'], transform(path(4)))

    collection.set_visible('first', False)
    for count in (2, 7):
        collection.set_insertion('first', path(count, count), width_px=count + 1)
        assert collection._insertions['first'].visual == first_handle
        assert native.visuals[first_handle]['visible'] is False
        assert len(native.visuals[first_handle]['position']) == count
        assert len(native.visuals[first_handle]['color']) == count
        assert len(native.visuals[first_handle]['stroke_width_px']) == count
        assert np.all(native.visuals[first_handle]['stroke_width_px'] == count + 1)
    assert collection.get_data('first').width_px == 8
    assert collection.get_data(23).width_px == 5
    assert collection.ids == ('first', 23)
    collection.close()


def test_color_width_visibility_remove_and_clear_are_per_insertion():
    native = FakeDatoviz()
    collection = InsertionCollectionVisual(native, 'scene', 'panel')
    collection.set_insertion('a', path())
    collection.set_insertion('b', path())
    a, b = collection._insertions['a'].visual, collection._insertions['b'].visual
    collection.set_color('a', (7, 8, 9))
    collection.set_width('a', 7.5)
    collection.set_visible('a', False)
    assert collection.get_data('a').color.tolist() == [7, 8, 9, 255]
    assert collection.get_data('a').width_px == 7.5
    assert native.visuals[a]['visible'] is False
    assert np.all(native.visuals[a]['color'] == [7, 8, 9, 255])
    assert np.all(native.visuals[a]['stroke_width_px'] == 7.5)
    assert native.visuals[b]['visible'] is True
    assert np.all(native.visuals[b]['color'] == [255, 205, 72, 255])
    assert collection.remove('a') is True
    assert collection.remove('a') is False
    assert collection.ids == ('b',)
    collection.clear()
    collection.clear()
    assert collection.ids == ()
    assert native.visuals == {}
    assert all(call[0] != 'destroy_scene' for call in native.calls)
    collection.close()


def test_failed_replacement_rolls_back_native_and_python_state():
    native = FakeDatoviz()
    collection = InsertionCollectionVisual(native, 'scene', 'panel')
    collection.set_insertion('track', path(3), color=(1, 2, 3), width_px=2)
    item = collection._insertions['track']
    handle, previous = item.visual, collection.get_data('track')
    before = {
        name: np.array(value, copy=True) if isinstance(value, np.ndarray) else value
        for name, value in native.visuals[handle].items()
    }
    native.fail_next = 'upload'
    with pytest.raises(RuntimeError, match='insertion upload'):
        collection.set_insertion('track', path(5, 10), color=(4, 5, 6), width_px=8)
    assert collection.get_data('track') is previous
    assert collection._insertions['track'].visual == handle
    for name, value in before.items():
        np.testing.assert_array_equal(native.visuals[handle][name], value)

    native.fail_next = 'data:color'
    with pytest.raises(RuntimeError, match='insertion color'):
        collection.set_color('track', (90, 80, 70))
    assert collection.get_data('track') is previous
    np.testing.assert_array_equal(native.visuals[handle]['color'], before['color'])
    collection.close()


@pytest.mark.parametrize(
    'failure', ['alpha', 'depth', 'caps', 'join', 'upload', 'visible', 'attach']
)
def test_new_path_setup_failure_destroys_only_candidate(failure):
    native = FakeDatoviz()
    collection = InsertionCollectionVisual(native, 'scene', 'panel')
    collection.set_insertion('existing', path())
    existing = collection._insertions['existing'].visual
    native.fail_next = failure
    with pytest.raises(RuntimeError):
        collection.set_insertion('candidate', path(2))
    assert collection.ids == ('existing',)
    assert set(native.visuals) == {existing}
    collection.close()


def test_null_path_constructor_and_close_are_retryable_and_idempotent():
    native = FakeDatoviz()
    collection = InsertionCollectionVisual(native, 'scene', 'panel')
    native.fail_next = 'path'
    with pytest.raises(RuntimeError, match='dvz_path'):
        collection.set_insertion('track', path())
    assert collection.ids == ()
    collection.set_insertion('track', path())
    visual = collection._insertions['track'].visual
    collection.close()
    collection.close()
    assert collection.ids == ()
    assert visual not in native.visuals
    with pytest.raises(RuntimeError, match='closed'):
        collection.set_insertion('again', path())


@pytest.mark.parametrize('method', ['set_color', 'set_width'])
def test_explicit_none_style_is_rejected_without_mutation(method):
    native = FakeDatoviz()
    collection = InsertionCollectionVisual(native, 'scene', 'panel')
    collection.set_insertion('track', path())
    previous = collection.get_data('track')
    calls = len(native.calls)
    with pytest.raises(ValueError):
        getattr(collection, method)('track', None)
    assert collection.get_data('track') is previous
    assert len(native.calls) == calls
    collection.close()
