"""UI-independent JSON persistence for planner sessions and projects."""
from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
import shutil
import os
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Iterable, Mapping

from suite_gui.material_presentation import AA_REAGENT_NAMES


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
    if not isinstance(data, Mapping):
        raise ValueError(f"Invalid SPPS JSON: top-level object required: {path}")
    return dict(data)


def _write_temp_json(destination: Path, state: Mapping[str, Any]) -> Path:
    """Flush a unique temporary file in the destination directory before publish."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(dict(state), stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def atomic_write_json(path: Path, state: Mapping[str, Any]) -> Path:
    """Publish an entire JSON document without leaving a partial destination."""
    destination = Path(path)
    temporary = _write_temp_json(destination, state)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def file_sha256(path: Path) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def project_file_lock(path: Path, *, timeout: float = 8.0):
    """Cooperative cross-process lock, using Windows or POSIX OS file locking.

    The sidecar lock is intentionally persistent: deleting a lock file while
    another process has it open would allow two independent locks to coexist.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError) as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Project is locked by another process: {target}") from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write_json_with_backup(
    path: Path, state: Mapping[str, Any], *, expected_sha256: str | None = None,
    expected_absent: bool = False,
) -> Path:
    """Atomically save with an OS lock and optional compare-and-swap guard.

    A failed optimistic check leaves both the original and its backup intact.
    All project writes from this application use the same sidecar lock.
    """
    destination = Path(path)
    with project_file_lock(destination):
        if expected_absent and destination.exists():
            raise RuntimeError("Destination appeared after Save As confirmation; choose a different path.")
        if expected_sha256 is not None:
            if not destination.exists() or file_sha256(destination) != expected_sha256:
                raise RuntimeError("Project changed outside SPPS Planner during save; reload or Save As a different file.")
        backup = destination.with_suffix(destination.suffix + ".bak")
        temporary = _write_temp_json(destination, state)
        backup_tmp = None
        try:
            if destination.exists():
                try:
                    read_json_object(destination)
                except (ValueError, OSError, UnicodeError):
                    pass
                else:
                    fd, name = tempfile.mkstemp(prefix=f".{backup.name}.", suffix=".tmp", dir=destination.parent)
                    backup_tmp = Path(name)
                    with os.fdopen(fd, "wb") as target, destination.open("rb") as source:
                        shutil.copyfileobj(source, target)
                        target.flush()
                        os.fsync(target.fileno())
                    os.replace(backup_tmp, backup)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
            if backup_tmp is not None:
                backup_tmp.unlink(missing_ok=True)
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
    "project_file_lock",
    "atomic_write_json_with_backup",
    "file_sha256",
    "normalize_items",
    "project_state",
    "read_json_object",
    "read_json_with_recovery",
]
