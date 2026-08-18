"""UI-independent JSON persistence for planner sessions and projects."""
from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

from spps_v4_gui.material_presentation import AA_REAGENT_NAMES


_PROTECTED_NAME_FIELDS = {
    "Unit name", "unit", "material", "reagent", "protected_reagent",
}


def _migrate_protected_names(item: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy one-letter AA display cells without altering chemistry."""
    for output_key in (
        "selected_plan_rows", "selected_material_rows", "selected_total_rows",
        "selected_checklist_rows",
    ):
        rows = item.get(output_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in _PROTECTED_NAME_FIELDS:
                value = str(row.get(field, "") or "").strip()
                if value in AA_REAGENT_NAMES:
                    row[field] = AA_REAGENT_NAMES[value]
    return item


def normalize_items(items: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Deep-copy valid rows and migrate legacy operator-facing AA labels."""
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        normalized.append(_migrate_protected_names(deepcopy(dict(item))))
    return normalized


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object; a non-object root represents an empty state."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, Mapping) else {}


def atomic_write_json(path: Path, state: Mapping[str, Any]) -> Path:
    """Write readable UTF-8 JSON and atomically replace the destination."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(state), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def file_sha256(path: Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json_with_backup(path: Path, state: Mapping[str, Any]) -> Path:
    """Atomically write JSON while retaining the last complete file as .bak."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    backup = destination.with_suffix(destination.suffix + ".bak")
    temporary.write_text(
        json.dumps(dict(state), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    if destination.exists():
        try:
            read_json_object(destination)
        except Exception:
            pass
        else:
            backup_tmp = backup.with_suffix(backup.suffix + ".tmp")
            shutil.copy2(destination, backup_tmp)
            backup_tmp.replace(backup)
    temporary.replace(destination)
    return destination


def read_json_with_recovery(path: Path) -> tuple[dict[str, Any], Path, bool]:
    """Read the primary JSON or its last-known-good .bak after corruption."""
    source = Path(path)
    try:
        return read_json_object(source), source, False
    except Exception as primary_error:
        backup = source.with_suffix(source.suffix + ".bak")
        if not backup.exists():
            raise primary_error
        return read_json_object(backup), backup, True


def project_state(
    *,
    app_version: str,
    saved_at: str,
    selected_pm_index: int,
    pm_items: Iterable[Any] | None,
    defaults: Mapping[str, Any] | None = None,
    batch_rows: Iterable[Any] | None = None,
    active_index: int | None = None,
    base: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the legacy-compatible state envelope used by save actions."""
    state = dict(base or {})
    state.update(
        {
            "app_version": app_version,
            "saved_at": saved_at,
            "selected_pm_index": int(selected_pm_index),
            # In-memory items have already passed migration on load. A shallow
            # row copy is sufficient for immediate JSON serialization and
            # avoids deep-copying every result table on each autosave.
            "pm_items": [
                dict(item) for item in (pm_items or [])
                if isinstance(item, Mapping)
            ],
            "defaults": dict(defaults or {}),
        }
    )
    if batch_rows is not None:
        state["batch_rows"] = [
            dict(row) for row in (batch_rows or [])
            if isinstance(row, Mapping)
        ]
    if active_index is not None:
        state["active_index"] = int(active_index)
    return state


__all__ = [
    "atomic_write_json",
    "atomic_write_json_with_backup",
    "file_sha256",
    "normalize_items",
    "project_state",
    "read_json_object",
    "read_json_with_recovery",
]
