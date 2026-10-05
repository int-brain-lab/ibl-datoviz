import numpy as np
import pytest

from ibl_datoviz.ontology import encode_region_key
from ibl_datoviz.selection import (
    mesh_ids_from_keys,
    probe_selected_ids,
    region_ids_from_keys,
    selected_row_keys,
    selection_decision,
    tree_selection_keys,
)


@pytest.mark.parametrize(
    ('events', 'source', 'propagation'),
    [
        (
            {
                'region_table_changed': True,
                'table_changed': True,
                'tree_changed': True,
                'mesh_changed': True,
            },
            'region_table',
            (True, False, True, True),
        ),
        (
            {'table_changed': True, 'tree_changed': True, 'mesh_changed': True},
            'probe_table',
            (True, False, True, False),
        ),
        ({'tree_changed': True, 'mesh_changed': True}, 'tree', (False, True, True, False)),
        ({'mesh_changed': True}, 'mesh', (True, True, False, False)),
    ],
)
def test_precedence_and_propagation(events, source, propagation):
    decision = selection_decision(**events)
    assert decision.source == source
    assert (
        decision.update_tree,
        decision.update_tables,
        decision.clear_mesh,
        decision.sync_probe_table,
    ) == propagation


def test_no_event_keeps_committed_selection():
    assert selection_decision() is None


def test_probe_identity_translation_and_mapping_switch():
    sites = np.array([11, 22, 33, 44], dtype=np.uint64)
    mapped = np.array([-8, 8, -8, 0], dtype=np.int64)
    assert probe_selected_ids(sites, mapped, [11, 33, 44]) == (-8,)
    assert probe_selected_ids(sites, mapped, []) == ()
    assert probe_selected_ids(sites, np.zeros(4, dtype=np.int64), [11, 22]) == ()
    np.testing.assert_array_equal(selected_row_keys(sites, mapped, [8]), [11, 22, 33])
    np.testing.assert_array_equal(selected_row_keys(sites, mapped, []), [])
    keys = np.array([encode_region_key(-8), encode_region_key(8)], dtype=np.uint64)
    assert region_ids_from_keys(keys) == (-8, 8)


def test_tree_keys_preserve_ontology_hemisphere_convention():
    keys = tree_selection_keys([8, -315, 997], [-8, -315])
    assert region_ids_from_keys(keys) == (-8, -315)
    assert mesh_ids_from_keys([0, *keys, keys[0]]) == (-8, -315)
