"""CPU checks for point transparency configuration against the RC4 adapter API."""

import ctypes

import numpy as np
import pytest

from ibl_datoviz.points import PointCollection, PointCollectionVisual


class PointStyle(ctypes.Structure):
    _fields_ = [('aspect', ctypes.c_int), ('stroke_width_px', ctypes.c_float)]


class Native:
    DVZ_ALPHA_OPAQUE = 0
    DVZ_ALPHA_BLENDED = 1
    DVZ_ALPHA_WBOIT = 2
    DVZ_SHAPE_ASPECT_FILLED = 0

    def __init__(self):
        self.calls = []
        self.data = {}

    def dvz_point(self, scene, flags):
        return 'point'

    def dvz_point_style_desc(self):
        return PointStyle()

    def dvz_point_set_style(self, visual, style):
        self.calls.append(('style', visual))
        return 0

    def dvz_visual_set_alpha_mode(self, visual, mode):
        self.calls.append(('alpha', visual, mode))
        return 0

    def dvz_visual_set_depth_test(self, visual, enabled):
        self.calls.append(('depth', visual, enabled))
        return 0

    def dvz_visual_set_data_many(self, visual, data):
        self.data = {key: np.array(value, copy=True) for key, value in data.items()}
        return 0

    def dvz_visual_set_visible(self, visual, visible):
        self.calls.append(('visible', visual, visible))
        return 0

    def dvz_panel_add_visual(self, panel, visual, desc):
        self.calls.append(('attach', visual))
        return 0

    def dvz_visual_destroy(self, visual):
        self.calls.append(('destroy', visual))


def collection(count=2):
    return PointCollection.from_arrays(np.ones((count, 3)), np.full((count, 4), 128, np.uint8))


def test_wboit_configures_rc4_point_and_reports_capabilities():
    native = Native()
    visual = PointCollectionVisual(native, 'scene', 'panel', collection(), alpha_mode='wboit')

    assert ('alpha', 'point', native.DVZ_ALPHA_WBOIT) in native.calls
    assert visual.capabilities.alpha_modes == ('opaque', 'blended', 'wboit')
    assert visual.capabilities.depth_test is True
    assert visual.capabilities.depth_write is False
    assert visual.capabilities.order_independent is True

    visual.replace(collection(4))
    assert len(native.data['position']) == 4
    assert visual.data is not None and len(visual.data) == 4
    visual.close()


@pytest.mark.parametrize('mode', ['opaque', 'blended'])
def test_non_wboit_capabilities_remain_order_dependent(mode):
    visual = PointCollectionVisual(Native(), 'scene', 'panel', collection(), alpha_mode=mode)
    assert visual.capabilities.alpha_modes == ('opaque', 'blended', 'wboit')
    assert visual.capabilities.order_independent is False
    assert visual.capabilities.depth_write is (mode == 'opaque')
    visual.close()


@pytest.mark.parametrize('mode', ['mask', 'depth_peel'])
def test_mask_and_peeling_remain_rejected_before_native_allocation(mode):
    native = Native()
    with pytest.raises(ValueError, match='mask/peeling unavailable'):
        PointCollectionVisual(native, 'scene', 'panel', collection(), alpha_mode=mode)
    assert native.calls == []
