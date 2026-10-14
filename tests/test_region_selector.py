"""Reviewed shared behavior and independent native model edge cases."""

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from ibl_datoviz.region_selector import (
    RegionSelector,
    SelectorRegion,
    highlight_spans,
    trim_query,
)

BUNDLE = Path(__file__).parent / 'fixtures' / 'region-selector'


def test_shared_region_selector_conformance():
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    # Exact bundle bytes, including expected results, are pinned independently
    # of this implementation. A port must never regenerate its own oracle.
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() == digest
    lock = json.loads((BUNDLE.parent / 'region-selector-lock.json').read_text())
    assert lock['commit'] == '81bd7d79044e4dc3a528abe50a0296381143f03e'
    for name, digest in lock['sha256'].items():
        assert hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() == digest
    traces = json.loads((BUNDLE / 'traces.json').read_text())
    jsonschema.validate(traces, json.loads((BUNDLE / 'schema.json').read_text()))
    for scenario in traces['scenarios']:
        selector = RegionSelector(
            [SelectorRegion.from_dict(row) for row in scenario['regions']], scenario['initial']
        )
        for index, (action, expected) in enumerate(
            zip(scenario['actions'], scenario['expected'], strict=True)
        ):
            selector.apply(action)
            assert selector.snapshot() == expected, (scenario['id'], index, action)


@pytest.mark.parametrize(
    ('text', 'query', 'expected'),
    [
        ('İnsula', 'i\u0307n', ((0, 2),)),
        ('😀İnsula', 'i\u0307', ((1, 2),)),
        ('ΟΣ', 'ος', ((0, 2),)),
        ('Straße', 'ss', ()),
        ('VISp VISp', 'visp', ((0, 4), (5, 9))),
        ('aa', 'a', ((0, 1), (1, 2))),
        ('insula', ' \ufeff ', ()),
    ],
)
def test_unicode_highlights_keep_original_codepoints(text, query, expected):
    assert highlight_spans(text, query) == expected


def test_ecmascript_query_trim_has_explicit_whitespace():
    assert trim_query('\ufeff\u00a0VISp\u2028') == 'VISp'
    assert trim_query('\u0085VISp\u0085') == '\u0085VISp\u0085'


@pytest.mark.parametrize(
    'regions',
    [
        [SelectorRegion('a', None, 1, 'A', 'A'), SelectorRegion('a', None, 2, 'B', 'B')],
        [SelectorRegion('a', 'missing', 1, 'A', 'A')],
        [SelectorRegion('a', 'b', 1, 'A', 'A'), SelectorRegion('b', 'a', 2, 'B', 'B')],
    ],
)
def test_invalid_hierarchy_rejected_before_projection(regions):
    with pytest.raises(ValueError):
        RegionSelector(regions)


def test_branch_member_activation_only_folds_and_host_selection_does_not_reveal():
    regions = [
        SelectorRegion('p', None, -10, 'P', 'Parent'),
        SelectorRegion('leaf', 'p', -11, 'L', 'Leaf'),
    ]
    selector = RegionSelector(regions)
    selector.activate('p')
    assert selector.selected == []
    selector.set_selected(['leaf'])
    assert selector.snapshot()['visible'] == ['p']
    assert selector.focus == 'p'


def test_omitted_grey_wrapper_does_not_erase_semantic_range_parents():
    selector = RegionSelector(
        [
            SelectorRegion('grey', None, -8, 'grey', 'Grey'),
            SelectorRegion('a', 'grey', -10, 'A', 'First'),
            SelectorRegion('b', 'grey', -11, 'B', 'Second'),
        ]
    )
    assert [row.depth for row in selector.visible_rows()] == [0, 0]
    selector.activate('a')
    selector.activate('b', shift=True)
    assert selector.selected == ['a', 'b']
    selector.apply({'op': 'order', 'value': 'value-desc'})
    selector.set_selected(['a'])
    selector.activate('b', shift=True)
    assert selector.selected == ['a', 'b']


def test_frame_copy_isolates_mutable_state_and_shares_frozen_catalog():
    model = RegionSelector(
        [SelectorRegion('a', None, -1, 'A', 'Parent'), SelectorRegion('b', 'a', -2, 'B', 'Leaf')],
        {'selected': ['b'], 'values': {'b': 1.0}},
    )
    before = model.snapshot()
    candidate = model.copy()
    candidate.collapsed.add('a')
    candidate.search_collapsed.add('a')
    candidate.selected.clear()
    candidate.values['b'] = 2.0
    candidate.focus = 'a'
    assert model.snapshot() == before
    assert model.values == {'b': 1.0}
    assert model.search_collapsed == set()
    assert candidate.regions is model.regions
    assert candidate.hierarchy is model.hierarchy
