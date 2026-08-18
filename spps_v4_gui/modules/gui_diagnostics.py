"""GUI structure diagnostics for SPPS Planner V4.0.0."""
from __future__ import annotations

from pathlib import Path
import ast


def count_function_defs(path: str | Path) -> int:
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        return sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
    except Exception:
        return -1


def legacy_snapshot(root: str | Path) -> dict[str, int | str]:
    root = Path(root)
    legacy = root / "suite_gui" / "legacy" / "spps_tk_gui_legacy.py"
    public = root / "suite_gui" / "spps_tk_gui.py"
    modules = root / "suite_gui" / "modules"
    legacy_lines = len(legacy.read_text(encoding="utf-8").splitlines()) if legacy.exists() else 0
    public_lines = len(public.read_text(encoding="utf-8").splitlines()) if public.exists() else 0
    module_files = sorted(p for p in modules.glob("*.py") if p.name != "__init__.py") if modules.exists() else []
    module_lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in module_files)
    return {
        "legacy_file": str(legacy),
        "legacy_lines": legacy_lines,
        "legacy_function_defs": count_function_defs(legacy),
        "public_entry_lines": public_lines,
        "module_files": len(module_files),
        "module_lines": module_lines,
    }
