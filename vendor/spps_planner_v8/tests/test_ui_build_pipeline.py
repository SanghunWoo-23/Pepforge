from __future__ import annotations

import ast
from pathlib import Path

from suite_gui import ui_build


ROOT = Path(__file__).resolve().parents[1]


def test_ui_build_pipeline_order_is_explicit(monkeypatch):
    events = []
    names = (
        "build_base_interface",
        "apply_plan_workspace",
        "apply_operator_workspace",
        "apply_final_release_ui",
        "apply_custom_database_ui",
        "bind_direct_workspace_actions",
        "apply_theme",
        "fit_window",
        "bind_shortcuts",
        "install_menu",
    )
    for name in names[:6]:
        monkeypatch.setattr(
            ui_build, name,
            lambda _gui, route=name: events.append(route),
        )
    for name in names[6:9]:
        monkeypatch.setattr(
            ui_build.ui_system, name,
            lambda _gui, *args, route=name, **kwargs: events.append(route),
        )
    monkeypatch.setattr(
        ui_build, "install_menu",
        lambda _gui: events.append("install_menu"),
    )
    ui_build.build_ui(object())
    assert events == list(names)


def test_ui_build_source_has_no_runtime_controller_binding():
    path = ROOT / "suite_gui" / "ui_build.py"
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
