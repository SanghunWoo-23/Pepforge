from __future__ import annotations

import ast
from pathlib import Path

from tools.audit_monkey_patches import audit, audit_active_release


def test_active_release_and_static_base_have_no_runtime_rebinding():
    root = Path(__file__).resolve().parents[1] / "suite_gui"
    report = audit(root)
    active = audit_active_release()

    assert report["python_files"] > 10
    assert report["binding_count"] == 0
    assert report["build_wrapper_count"] == 0
    assert report["bindings"] == []
    assert "legacy_controller.py" not in report["bindings_by_file"]
    assert active["legacy_controller_routes"] == []
    assert active["numbered_module_routes"] == []

    installers = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        installers.extend(
            (str(path.relative_to(root)), node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "install"
        )
    assert installers == []


def test_classic_base_has_no_duplicate_method_definitions():
    root = Path(__file__).resolve().parents[1]
    path = root / "suite_gui" / "classic_base.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    duplicates = {}
    from collections import Counter
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        counts = Counter(
            child.name for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        repeated = {name: count for name, count in counts.items() if count > 1}
        if repeated:
            duplicates[node.name] = repeated
    assert duplicates == {}
