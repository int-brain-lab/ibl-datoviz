"""Owned regional quantities retain source populations and commit presentation atomically."""

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import numpy as np
import pytest

from ibl_datoviz.payloads import WorldFrame
from ibl_datoviz.regional_quantities import RegionQuantityRegistry, RegionValues
from ibl_datoviz.regions import AtlasRegionValues


@pytest.fixture
def frame():
    return WorldFrame(
        'fixture',
        provenance={
            'verification': {'method': 'fixture frame review', 'evidence': 'fixture identity'},
        },
    )


def values(frame, **changes):
    return RegionValues(
        **{
            'allen_region_ids': [-1, -2, -3, 1, 2, 3, 4, 5],
            'values': [2, 8, np.nan, 4, 12, np.nan, 99, 100],
            'weights': [1, 3, 20, 3, 1, 5, 1, 1],
            'name': 'Prepared rate',
            'units': 'Hz',
            'weight_name': 'neurons',
            'frame': frame,
            'provenance': {'aggregation': {'method': 'explicit fixture'}},
            **changes,
        }
    )


class Catalog:
    def map_allen_ids(self, ids, mapping):
        if mapping == 'allen':
            return list(ids)
        if mapping != 'beryl':
            raise KeyError(mapping)
        lookup = {-1: -10, -2: -10, -3: -10, 1: 10, 2: 10, 3: 20, 4: 0, 5: None}
        return [lookup[int(identity)] for identity in ids]


class Viewer:
    def __init__(self, frame):
        self.frame = frame
        self.catalog = Catalog()
        self.mapping = 'beryl'
        self.region_data = None
        self._region_value_range = None
        self._region_color_scheme = 'sequential'
        self._region_opacity = None
        self.guard_error = self.apply_error = False
        self.calls = []
        self.selection = SimpleNamespace(_check_mutation=self._guard)

    def _guard(self):
        if self.guard_error:
            raise RuntimeError('mutation rejected')

    def _validate_layer_frame(self, frame):
        frame.require_verified()
        if frame != self.frame:
            raise ValueError('frame mismatch')

    def _set_owned_region_data(self, data, **options):
        if self.apply_error:
            raise RuntimeError('native transaction failed and restored')
        self.calls.append((data, options))
        self.region_data = data
        self._region_value_range = options['value_range']
        self._region_color_scheme = options['color_scheme']
        self._region_opacity = options['opacity']


@pytest.fixture
def registry(frame):
    return RegionQuantityRegistry(Viewer(frame))


def test_payload_is_owned_and_immutable(frame):
    raw_values = np.array([1.0, np.nan])
    provenance = {'aggregation': ['source declaration']}
    payload = values(
        frame, allen_region_ids=[-1, 1], values=raw_values, weights=[1, 3], provenance=provenance
    )
    raw_values[0] = 99
    provenance['aggregation'].append('mutated')
    assert payload.values[0] == 1
    assert payload.provenance['aggregation'] == ('source declaration',)
    for array in (payload.allen_region_ids, payload.values, payload.weights):
        with pytest.raises(ValueError):
            array.setflags(write=True)
    with pytest.raises(TypeError):
        payload.provenance['aggregation'] = 'changed'
    with pytest.raises(FrozenInstanceError):
        payload.units = 'changed'


@pytest.mark.parametrize(
    'changes',
    [
        {'weights': None},
        {'weights': [1]},
        {'weights': [-1] * 8},
        {'weights': [0] * 8},
        {'weights': [np.nan] * 8},
        {'units': ''},
        {'weight_name': ' '},
        {'name': ''},
        {'values': [np.inf] * 8},
        {'allen_region_ids': [0] * 8},
        {'allen_region_ids': [True] * 8},
        {'allen_region_ids': [-1] * 8},
        {'allen_region_ids': np.array([2**64 - 1], dtype=np.uint64)},
        {'frame': WorldFrame('unreviewed')},
    ],
)
def test_invalid_prepared_contracts_fail(frame, changes):
    # Explicit weights are mandatory, so None must not trigger legacy unit weights.
    with pytest.raises((ValueError, TypeError)):
        values(frame, **changes)


def test_mapping_coverage_preserves_nan_population_and_source_hemispheres(registry, frame):
    handle = registry.add(values(frame), mapping_reduction='weighted_mean')
    original_ids = handle.payload.allen_region_ids.copy()
    mapped = handle.mapped()
    np.testing.assert_array_equal(mapped.region_ids, [-10, 10, 20])
    np.testing.assert_array_equal(mapped.values, [6.5, 6, np.nan])
    np.testing.assert_array_equal(mapped.declared_weights, [24, 4, 5])
    np.testing.assert_array_equal(mapped.finite_weights, [4, 4, 0])
    np.testing.assert_array_equal(mapped.source_counts, [3, 2, 1])
    np.testing.assert_array_equal(mapped.finite_counts, [2, 2, 0])
    np.testing.assert_array_equal(mapped.unmapped_source_ids, [4, 5])
    registry.viewer.mapping = 'allen'
    assert handle.mapped().mapping == 'allen'
    assert len(handle.mapped().region_ids) == 8
    np.testing.assert_array_equal(handle.payload.allen_region_ids, original_ids)
    with pytest.raises(ValueError):
        mapped.declared_weights.setflags(write=True)


def test_second_attachment_rejected_even_when_first_hidden(registry, frame):
    handle = registry.add(values(frame), mapping_reduction='weighted_mean')
    handle.set_visible(False)
    with pytest.raises(ValueError, match='already attached'):
        registry.add(values(frame), mapping_reduction='weighted_mean')
    handle.remove()
    replacement = registry.add(values(frame), mapping_reduction='weighted_mean')
    assert replacement is registry.handle


def test_hide_remove_restore_previous_scalar_settings_in_current_mapping(registry, frame):
    previous = AtlasRegionValues.from_arrays([-1], [42])
    viewer = registry.viewer
    viewer.region_data, viewer._region_value_range = previous, (0, 50)
    viewer._region_color_scheme, viewer._region_opacity = 'diverging', 0.4
    handle = registry.add(values(frame), name='rates', mapping_reduction='weighted_mean')
    assert handle.visible and handle.name == 'rates'
    handle.color_by('value', cmap='diverging', limits=(0, 15))
    assert handle.cmap == 'diverging' and handle.limits == (0.0, 15.0)
    viewer.mapping = 'allen'
    handle.set_visible(False)
    assert viewer.region_data is previous
    assert viewer._region_value_range == (0, 50)
    assert viewer._region_opacity == 0.4
    assert viewer.mapping == 'allen'
    count = len(viewer.calls)
    handle.color_by('value', cmap='sequential', limits=[0, 100])
    assert len(viewer.calls) == count
    handle.set_visible(True)
    assert viewer.region_data.values is handle.payload.values
    assert viewer._region_color_scheme == 'sequential'
    handle.remove()
    assert registry.handle is None and not handle.visible
    assert viewer.region_data is previous
    with pytest.raises(RuntimeError, match='removed'):
        handle.set_visible(True)


@pytest.mark.parametrize('operation', ['add', 'color', 'hide', 'remove', 'show'])
def test_failed_upload_never_commits_handle_state(registry, frame, operation):
    if operation != 'add':
        handle = registry.add(values(frame), mapping_reduction='weighted_mean')
        if operation == 'show':
            handle.set_visible(False)
    registry.viewer.apply_error = True
    with pytest.raises(RuntimeError, match='transaction'):
        if operation == 'add':
            registry.add(values(frame), mapping_reduction='weighted_mean')
        elif operation == 'color':
            handle.color_by('value', cmap='diverging', limits=(0, 20))
        elif operation == 'hide':
            handle.set_visible(False)
        elif operation == 'remove':
            handle.remove()
        else:
            handle.set_visible(True)
    if operation == 'add':
        assert registry.handle is None
    else:
        assert registry.handle is handle
        assert handle.visible == (operation != 'show')
        assert handle.cmap == 'sequential' and handle.limits is None
        assert not handle._closed


@pytest.mark.parametrize(
    'field,cmap,limits',
    [
        ('other', 'sequential', None),
        ('value', 'viridis', None),
        ('value', 'sequential', (1, 1)),
        ('value', 'diverging', (1, np.inf)),
    ],
)
def test_unavailable_encodings_rejected_before_native_calls(registry, frame, field, cmap, limits):
    handle = registry.add(values(frame), mapping_reduction='weighted_mean')
    before = len(registry.viewer.calls)
    with pytest.raises(ValueError):
        handle.color_by(field, cmap=cmap, limits=limits)
    assert len(registry.viewer.calls) == before


def test_owner_guards_and_shutdown(registry, frame):
    handle = registry.add(values(frame), mapping_reduction='weighted_mean')
    registry.viewer.guard_error = True
    with pytest.raises(RuntimeError, match='mutation rejected'):
        handle.set_visible(False)
    registry.viewer.guard_error = False
    before = len(registry.viewer.calls)
    registry._close()
    assert len(registry.viewer.calls) == before
    assert registry.handle is None and not handle.visible
    with pytest.raises(RuntimeError, match='closed'):
        handle.mapped()
    with pytest.raises(RuntimeError, match='closed'):
        registry.add(values(frame), mapping_reduction='weighted_mean')


def test_explicit_mapping_reduction_and_frame_match_required(registry, frame):
    with pytest.raises(TypeError):
        registry.add(values(frame))
    with pytest.raises(ValueError, match='weighted_mean'):
        registry.add(values(frame), mapping_reduction='mean')
    other = WorldFrame('other', provenance=frame.provenance)
    with pytest.raises(ValueError, match='frame mismatch'):
        registry.add(values(other), mapping_reduction='weighted_mean')
    assert registry.handle is None


def test_nonfinite_aggregate_coverage_fails_before_attachment(registry, frame):
    payload = values(
        frame, allen_region_ids=[-1, -2], values=[np.nan, np.nan], weights=[1e308, 1e308]
    )
    with pytest.raises(ValueError, match='coverage weights overflow'):
        registry.add(payload, mapping_reduction='weighted_mean')
    assert registry.handle is None
    assert registry.viewer.calls == []
