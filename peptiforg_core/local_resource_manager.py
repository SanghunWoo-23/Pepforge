from __future__ import annotations

"""Local resource registry for Pepforge V5 offline-first execution.

The registry records paths and readiness only. It never downloads models,
installs engines, or treats network availability as scientific readiness.
"""

from pathlib import Path
from typing import Any, Dict
import json
import os

RESOURCE_MANAGER_VERSION = "5.0.0-rc2"
VALID_EXECUTION_MODES = {"offline", "auto", "online_enhanced"}


def normalize_execution_mode(value: str | None) -> str:
    text = str(value or "offline").strip().lower().replace("/", "_").replace(" ", "_")
    while "__" in text:
        text = text.replace("__", "_")
    aliases = {
        "local": "offline", "offline_local": "offline", "offline__local": "offline",
        "online": "online_enhanced", "enhanced": "online_enhanced",
    }
    text = aliases.get(text, text)
    if text not in VALID_EXECUTION_MODES:
        raise ValueError("execution_mode must be offline, auto, or online_enhanced")
    return text


def default_resource_root() -> Path:
    env = str(os.environ.get("PEPFORGE_LOCAL_RESOURCES") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "Pepforge_LocalResources").resolve()


def manifest_path(resource_root: str | Path | None = None) -> Path:
    root = Path(resource_root).expanduser().resolve() if resource_root else default_resource_root()
    return root / "manifests" / "installed_resources.json"


def load_resource_manifest(resource_root: str | Path | None = None) -> Dict[str, Any]:
    path = manifest_path(resource_root)
    if not path.exists():
        return {
            "schema_version": 1,
            "status": "MANIFEST_NOT_FOUND",
            "resource_root": str(path.parents[1]),
            "manifest_path": str(path),
            "resources": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("installed_resources.json must contain a JSON object")
    resources = payload.get("resources") or {}
    if not isinstance(resources, dict):
        raise ValueError("installed_resources.json resources must be an object")
    return {
        **payload,
        "status": "LOADED",
        "resource_root": str(path.parents[1]),
        "manifest_path": str(path),
        "resources": resources,
    }


def _entry_status(name: str, entry: Any, root: Path) -> Dict[str, Any]:
    if isinstance(entry, str):
        entry = {"path": entry}
    if not isinstance(entry, dict):
        return {"name": name, "status": "INVALID_MANIFEST_ENTRY", "available": False, "path": None}
    raw = str(entry.get("path") or "").strip()
    if not raw:
        return {"name": name, "status": "PATH_NOT_CONFIGURED", "available": False, "path": None}
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    exists = path.exists()
    return {
        "name": name,
        "status": "READY" if exists else "PATH_MISSING",
        "available": exists,
        "path": str(path),
        "kind": entry.get("kind"),
        "version": entry.get("version"),
    }


def resource_status(resource_root: str | Path | None = None, *, execution_mode: str = "offline") -> Dict[str, Any]:
    mode = normalize_execution_mode(execution_mode)
    manifest = load_resource_manifest(resource_root)
    root = Path(manifest["resource_root"])
    rows = {name: _entry_status(name, entry, root) for name, entry in (manifest.get("resources") or {}).items()}
    return {
        "resource_manager_version": RESOURCE_MANAGER_VERSION,
        "execution_mode": mode,
        "network_allowed": mode != "offline",
        "local_first": mode in {"offline", "auto"},
        "resource_root": str(root),
        "manifest_status": manifest.get("status"),
        "manifest_path": manifest.get("manifest_path"),
        "resources": rows,
        "claim_guard": "Resource readiness is based on local files/paths and explicit backend checks, not on internet connectivity.",
    }


def configured_path(name: str, resource_root: str | Path | None = None) -> str | None:
    status = resource_status(resource_root)
    row = status["resources"].get(str(name)) or {}
    return row.get("path") if row.get("available") else None


def write_manifest_template(resource_root: str | Path | None = None) -> str:
    path = manifest_path(resource_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        template = {
            "schema_version": 1,
            "resources": {
                "haddock3": {"kind": "executable_or_environment", "path": "engines/haddock3"},
                "openmm": {"kind": "python_environment", "path": "engines/openmm"},
                "esm2_8m": {"kind": "model", "path": "models/esm2_8m"},
                "esmfold": {"kind": "model", "path": "models/esmfold"},
                "pepforge_ranker": {"kind": "model", "path": "models/pepforge_ranker"},
                "alphafold3": {"kind": "external_installation", "path": "databases/alphafold3"},
            },
        }
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


__all__ = [
    "RESOURCE_MANAGER_VERSION", "VALID_EXECUTION_MODES", "normalize_execution_mode",
    "default_resource_root", "manifest_path", "load_resource_manifest", "resource_status",
    "configured_path", "write_manifest_template",
]
