from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "projects"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (name or "Pepforge_Project").strip())
    return cleaned.strip("._-") or "Pepforge_Project"


def new_project(project_name: str, input_sequence: str = "", base_dir: str | Path | None = None) -> Path:
    base = Path(base_dir) if base_dir else PROJECTS_DIR
    folder = base / f"{safe_name(project_name)}_{now_stamp()}"
    for sub in ["input", "hotspot", "design", "spps", "logs", "exports"]:
        (folder / sub).mkdir(parents=True, exist_ok=True)
    project = default_project(project_name=safe_name(project_name), input_sequence=input_sequence)
    save_project(folder, project)
    if input_sequence:
        (folder / "input" / "input_sequence.txt").write_text(input_sequence, encoding="utf-8")
    return folder


def default_project(project_name: str = "Pepforge_Project", input_sequence: str = "") -> dict[str, Any]:
    return {
        "project_name": project_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "software": "Pepforge",
        "version": "0.2.0-workflow",
        "usage_modes": ["standalone", "workflow"],
        "input_sequence": input_sequence,
        "hotspot_results": [],
        "selected_hotspots": [],
        "design_results": [],
        "selected_candidates": [],
        "spps_settings": {},
        "output_files": {},
        "notes": "Standalone modules remain independent. Workflow mode connects modules through this project.json and CSV files."
    }


def project_file(project_dir: str | Path) -> Path:
    return Path(project_dir) / "project.json"


def load_project(project_dir: str | Path) -> dict[str, Any]:
    path = project_file(project_dir)
    if not path.exists():
        raise FileNotFoundError(f"project.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_project(project_dir: str | Path, project: dict[str, Any]) -> Path:
    path = project_file(project_dir)
    Path(project_dir).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def update_project(project_dir: str | Path, **updates: Any) -> dict[str, Any]:
    project = load_project(project_dir)
    project.update(updates)
    project["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_project(project_dir, project)
    return project


def relpath(project_dir: str | Path, file_path: str | Path) -> str:
    try:
        return str(Path(file_path).resolve().relative_to(Path(project_dir).resolve())).replace("\\", "/")
    except Exception:
        return str(file_path).replace("\\", "/")
