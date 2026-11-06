from __future__ import annotations

from suite_gui import peptide_item_collection as collection


def _items():
    return [
        {"peptide": "A", "selected_plan_rows": [{"No": "1"}]},
        {"peptide": "B", "selected_plan_rows": [{"No": "2"}]},
        {"peptide": "C", "selected_plan_rows": [{"No": "3"}]},
        {"peptide": "D", "selected_plan_rows": [{"No": "4"}]},
    ]


def test_add_and_duplicate_preserve_complete_item_data():
    items, index, added = collection.append_item([], None)
    assert index == 0
    assert added["project"] == "Project-001"
    assert added["sequence"] == ""

    items, duplicate_index, duplicate = collection.duplicate_item(
        _items(), 1
    )
    assert duplicate_index == 4
    assert duplicate["peptide"] == "B_copy"
    assert duplicate["selected_plan_rows"] == [{"No": "2"}]
    assert duplicate["selected_plan_rows"] is not items[1]["selected_plan_rows"]


def test_multi_delete_can_remove_last_remaining_item():
    result = collection.delete_items(_items(), [1, 3])
    assert [item["peptide"] for item in result.items] == ["A", "C"]
    assert result.active_index == 1
    assert result.deleted_indices == (1, 3)

    empty = collection.delete_items([{"peptide": "A"}], [0])
    assert empty.items == []
    assert empty.active_index is None


def test_move_block_preserves_object_identity_selection_and_active_item():
    items = _items()
    active_item = items[2]
    result = collection.move_block(items, [1, 2], 4, active_index=2)

    assert [item["peptide"] for item in result.items] == ["A", "D", "B", "C"]
    assert result.selected_indices == (2, 3)
    assert result.items[result.active_index] is active_item
    assert result.active_index == 3


def test_drop_inside_selected_block_is_a_no_op():
    items = _items()
    result = collection.move_block(items, [1, 2], 2, active_index=1)
    assert result.items == items
    assert result.selected_indices == (1, 2)
    assert result.active_index == 1
