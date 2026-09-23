from __future__ import annotations

"""Shared result-folder and package helpers for Pepforge user outputs.

A user-triggered export should create one coherent result bundle rather than
scatter files across a selected directory. Bundle names use the local date plus
an explicit user name, sequence, or tool label. Windows filename restrictions
are handled centrally.
"""

from datetime import datetime
from hashlib import sha1
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile
from typing import Iterable, Mapping, Any

from peptiforg_core.version import PEPFORGE_VERSION

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def sanitize_component(value: str | None, *, fallback: str = "Pepforge", max_length: int = 72) -> str:
    """Return a Windows-safe, readable path component.

    Unicode letters/digits are preserved. Very long labels are shortened with a
    stable hash suffix so peptide sequences remain distinguishable.
    """
    raw = _WHITESPACE.sub("_", str(value or "").strip())
    raw = _INVALID.sub("_", raw)
    raw = re.sub(r"_+", "_", raw).strip(" ._")
    if not raw:
        raw = fallback
    if raw.upper() in _WINDOWS_RESERVED:
        raw = f"_{raw}"
    if len(raw) > max_length:
        digest = sha1(raw.encode("utf-8")).hexdigest()[:8]
        keep = max(8, max_length - 9)
        raw = f"{raw[:keep]}_{digest}"
    return raw


def compact_sequence_label(sequence: str | None, *, max_length: int = 64) -> str:
    text = re.sub(r"\s+", "", str(sequence or ""))
    return sanitize_component(text, fallback="sequence", max_length=max_length)


def bundle_folder_name(
    *,
    name: str | None = None,
    sequence: str | None = None,
    tool: str | None = None,
    date: datetime | None = None,
) -> str:
    day = (date or datetime.now()).strftime("%Y-%m-%d")
    label = str(name or "").strip()
    if not label and str(sequence or "").strip():
        label = compact_sequence_label(sequence)
    if not label:
        label = str(tool or "Pepforge")
    return f"{day}_{sanitize_component(label)}"


def unique_directory(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}_{index:02d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate a unique result folder below: {path.parent}")


def create_result_bundle(
    base_dir: str | Path,
    *,
    name: str | None = None,
    sequence: str | None = None,
    tool: str = "Pepforge",
    unique: bool = True,
) -> Path:
    base = Path(base_dir).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    target = base / bundle_folder_name(name=name, sequence=sequence, tool=tool)
    if unique:
        target = unique_directory(target)
    target.mkdir(parents=True, exist_ok=False if unique else True)
    write_bundle_manifest(target, tool=tool, name=name, sequence=sequence)
    return target


def write_bundle_manifest(
    bundle_dir: str | Path,
    *,
    tool: str,
    name: str | None = None,
    sequence: str | None = None,
    artifacts: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> str:
    bundle = Path(bundle_dir)
    bundle.mkdir(parents=True, exist_ok=True)
    manifest_path = bundle / "RESULT_BUNDLE.json"
    payload: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload.update({
        "schema": "pepforge_result_bundle_v1",
        "pepforge_version": PEPFORGE_VERSION,
        "tool": tool,
        "name": str(name or ""),
        "sequence": str(sequence or ""),
        "bundle_name": bundle.name,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })
    payload.setdefault("created_at", payload["updated_at"])
    if artifacts is not None:
        payload["artifacts"] = {str(k): str(v) for k, v in artifacts.items()}
    if extra:
        payload.setdefault("metadata", {}).update(dict(extra))
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(manifest_path)


def bundle_files(bundle_dir: str | Path, *, exclude: Iterable[str | Path] = ()) -> list[Path]:
    bundle = Path(bundle_dir)
    excluded = {Path(x).resolve() for x in exclude}
    files: list[Path] = []
    for path in bundle.rglob("*"):
        if path.is_file() and path.resolve() not in excluded:
            files.append(path)
    return sorted(files)


def build_bundle_zip(bundle_dir: str | Path, *, filename: str = "result_package.zip") -> str:
    """Create a ZIP *inside* the result bundle without recursively including itself."""
    bundle = Path(bundle_dir)
    bundle.mkdir(parents=True, exist_ok=True)
    zip_path = bundle / sanitize_component(filename, fallback="result_package.zip", max_length=100)
    if zip_path.suffix.lower() != ".zip":
        zip_path = zip_path.with_suffix(".zip")
    fd, temp_name = tempfile.mkstemp(prefix="pepforge_bundle_", suffix=".zip", dir=str(bundle.parent))
    os.close(fd)
    Path(temp_name).unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temp_name, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in bundle_files(bundle, exclude=[zip_path]):
                archive.write(path, path.relative_to(bundle))
        Path(temp_name).replace(zip_path)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return str(zip_path)
