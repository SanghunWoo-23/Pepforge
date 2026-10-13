"""Pure collection operations for Project Manager peptide items."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


def blank_item(number: int) -> dict[str, Any]:
    return {
        "work_item_id": uuid4().hex,
        "project": f"Project-{number:03d}",
        "peptide": f"Peptide-{number:03d}",
        "sequence": "",
        "copies": "1",
        "scale": "0.2",
        "resin": "Rink Amide AM",
        "loading": "0.8",
        "lot": "",
        "chemistry": "DIC/HOBt",
        "status": "Ready",
        "loading_time_h": "",
        "cleavage_time_h": "",
        "cleavage_preset": "",
    }


def append_item(items, item=None):
    result = list(items or [])
    created = dict(item or blank_item(len(result) + 1))
    if not str(created.get("work_item_id", "")).strip():
        created["work_item_id"] = uuid4().hex
    result.append(created)
    return result, len(result) - 1, created


def duplicate_item(items, index):
    result = list(items or [])
    if index is None or not (0 <= int(index) < len(result)):
        return result, None, None
    created = json.loads(json.dumps(result[int(index)], default=str))
    created["peptide"] = f"{created.get('peptide', 'Peptide')}_copy"
    created["work_item_id"] = uuid4().hex
    created.pop("synthesis_execution", None)
    created.pop("ml_review", None)
    created.pop("risk_review", None)
    created.pop("runs", None)
    created.pop("active_run_id", None)
    result.append(created)
    return result, len(result) - 1, created


@dataclass(frozen=True)
class DeleteResult:
    items: list
    active_index: int | None
    deleted_indices: tuple[int, ...]


def delete_items(items, selected) -> DeleteResult:
    original = list(items or [])
    valid = tuple(sorted({
        int(index)
        for index in selected or []
        if 0 <= int(index) < len(original)
    }))
    if not valid:
        return DeleteResult(original, None, ())
    deleted = set(valid)
    remaining = [
        item for index, item in enumerate(original) if index not in deleted
    ]
    active = min(valid[0], len(remaining) - 1) if remaining else None
    return DeleteResult(remaining, active, valid)


@dataclass(frozen=True)
class MoveResult:
    items: list
    selected_indices: tuple[int, ...]
    active_index: int | None


def move_block(items, selected, target, active_index=None) -> MoveResult:
    original = list(items or [])
    valid = sorted({
        int(index)
        for index in selected or []
        if 0 <= int(index) < len(original)
    })
    if not original or not valid:
        return MoveResult(original, tuple(valid), active_index)
    target = int(target)
    if target in valid and min(valid) <= target <= max(valid):
        return MoveResult(original, tuple(valid), active_index)
    active_item = (
        original[int(active_index)]
        if active_index is not None
        and 0 <= int(active_index) < len(original)
        else None
    )
    selected_set = set(valid)
    block = [original[index] for index in valid]
    rest = [
        item
        for index, item in enumerate(original)
        if index not in selected_set
    ]
    before_target = sum(1 for index in valid if index < target)
    insert_at = max(0, min(len(rest), target - before_target))
    moved = rest[:insert_at] + block + rest[insert_at:]
    new_selected = tuple(range(insert_at, insert_at + len(block)))
    if active_item is not None:
        try:
            active = next(
                index
                for index, item in enumerate(moved)
                if item is active_item
            )
        except StopIteration:
            active = new_selected[0]
    else:
        active = active_index
    return MoveResult(moved, new_selected, active)


__all__ = [
    "DeleteResult",
    "MoveResult",
    "append_item",
    "blank_item",
    "delete_items",
    "duplicate_item",
    "move_block",
]
