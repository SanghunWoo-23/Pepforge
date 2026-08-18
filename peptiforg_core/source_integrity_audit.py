from __future__ import annotations

"""Static release audit for runtime patching and incomplete implementations."""

import ast
import re
from pathlib import Path
from typing import Any


FORBIDDEN_PATTERNS = {
    "runtime_class_method_assignment": re.compile(r"\b(?:SPPSGui|gui_cls)\.[A-Za-z_]\w*\s*="),
    "override_suppression": re.compile(r"type:\s*ignore\[override\]"),
    "patch_function": re.compile(r"\bdef\s+_patch_"),
    "placeholder_marker": re.compile(r"\b(?:placeholder|dummy)\b", re.I),
}

BANNED_RELEASE_FILES = {
    "spps_v4_gui/legacy_controller.py",
    "spps_v4_gui/release_composition.py",
    "spps_v4_gui/classic_2094_tk_gui.py",
}


def audit_source_tree(root_dir: str | Path) -> dict[str, Any]:
    root = Path(root_dir)
    findings: list[dict[str, Any]] = []
    for relative in sorted(BANNED_RELEASE_FILES):
        if (root / relative).exists():
            findings.append({"file": relative, "line": 0, "rule": "banned_release_file"})
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("tests/") or relative in {
            "scripts/consolidate_duplicate_definitions.py",
            "peptiforg_core/source_integrity_audit.py",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append({"file": relative, "line": exc.lineno or 0, "rule": "syntax_error"})
            continue
        definitions: dict[str, list[int]] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.setdefault(node.name, []).append(node.lineno)
        for name, lines in definitions.items():
            if len(lines) > 1:
                findings.append({"file": relative, "line": lines[1], "rule": "duplicate_top_level_definition", "name": name})
        for rule, pattern in FORBIDDEN_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append({"file": relative, "line": text.count("\n", 0, match.start()) + 1, "rule": rule})
    return {
        "status": "passed" if not findings else "failed",
        "finding_count": len(findings),
        "findings": findings,
        "claim_boundary": "Static code-integrity audit; native Windows and optional scientific dependency execution remain separate runtime checks.",
    }


__all__ = ["audit_source_tree"]
