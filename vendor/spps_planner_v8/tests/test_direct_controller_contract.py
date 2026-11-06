from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_direct_controller_contains_no_runtime_class_rebinding():
    path = ROOT / "suite_gui" / "controller.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in {"SPPSGui", "gui_cls"}
                ):
                    forbidden.append((node.lineno, ast.unparse(target)))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
        ):
            forbidden.append((node.lineno, "setattr"))
    assert forbidden == []


def test_direct_controller_is_the_public_runtime_identity():
    from suite_gui.controller import SPPSGui as DirectController
    from suite_gui.release import SPPSGui as ReleaseController
    from suite_gui.spps_tk_gui import SPPSGui as PublicController

    assert ReleaseController is DirectController
    assert PublicController is DirectController
    assert DirectController.TITLE == "SPPS Planner V8.0.0"


def test_direct_build_uses_explicit_ui_pipeline_not_super_wrapper():
    path = ROOT / "suite_gui" / "controller.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SPPSGui"
    )
    build = next(
        node for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "_build"
    )
    source = ast.unparse(build)
    assert "build_ui(self)" in source
    assert "super()._build" not in source
