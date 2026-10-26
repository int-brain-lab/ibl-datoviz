"""Exact ordered geometry against the pre-compaction full-grid contour algorithm."""

import numpy as np
import pytest

from ibl_datoviz.navigator import label_contours


def full_grid_reference(labels):
    """Frozen original algorithm; crossing order is part of the regression oracle."""
    height, width = labels.shape
    padded = np.pad(labels, 1)
    tl, tr = padded[:-1, :-1], padded[:-1, 1:]
    bl, br = padded[1:, :-1], padded[1:, 1:]
    edges = np.stack((tl != tr, tr != br, bl != br, tl != bl), axis=-1)
    counts = edges.sum(axis=-1)
    offsets = np.array(((0, -0.5), (0.5, 0), (0, 0.5), (-0.5, 0)))
    starts, ends = [], []
    for first in range(4):
        for second in range(first + 1, 4):
            rows, columns = np.nonzero((counts == 2) & edges[..., first] & edges[..., second])
            centers = np.column_stack((columns, rows))
            starts.append(centers + offsets[first])
            ends.append(centers + offsets[second])
        rows, columns = np.nonzero((counts > 2) & edges[..., first])
        centers = np.column_stack((columns, rows))
        starts.append(centers + offsets[first])
        ends.append(centers)
    scale = np.array((width, height))
    return tuple(
        np.ascontiguousarray(np.concatenate(parts) / scale, dtype=np.float32)
        for parts in (starts, ends)
    )


def assert_exact(labels):
    before = labels.copy()
    expected = full_grid_reference(labels)
    actual = label_contours(labels)
    for reference, candidate in zip(expected, actual, strict=True):
        assert candidate.dtype == np.float32 and candidate.flags.c_contiguous
        assert reference.shape == candidate.shape
        assert reference.tobytes() == candidate.tobytes()
    np.testing.assert_array_equal(labels, before)


@pytest.mark.parametrize('dtype', [np.int8, np.uint16, np.int32, np.int64, np.uint64])
@pytest.mark.parametrize('shape', [(0, 0), (0, 4), (4, 0), (1, 1), (1, 9), (9, 1), (17, 23)])
def test_background_padding_singleton_and_noncontiguous_inputs(dtype, shape):
    labels = np.zeros(shape, dtype=dtype)
    assert_exact(labels)
    labels[...] = 7
    assert_exact(labels)
    assert_exact(labels.T)
    assert_exact(labels[::-1, ::-1])


def test_sparse_signed_regions_and_multiple_junctions():
    labels = np.zeros((100, 120), dtype=np.int64)
    labels[20:50, 30:70] = -315
    labels[40:65, 50:80] = 315
    labels[30:40, 40:50] = -(2**50)
    labels[35:45, 45:55] = 2**50
    assert_exact(labels)
    assert_exact(labels[::2, ::-2])


@pytest.mark.parametrize('seed', range(12))
def test_dense_fallback_preserves_checkerboards_and_arbitrary_junctions(seed):
    rng = np.random.default_rng(seed)
    for size in (2, 5, 25):
        labels = rng.integers(-5, 6, size=(size, size + 3), dtype=np.int64)
        assert_exact(labels)
        assert_exact(labels.T)
    checkerboard = np.indices((24, 30)).sum(axis=0) % 2
    assert_exact(checkerboard)
