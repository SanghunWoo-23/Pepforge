from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_entrypoint_exports_the_canonical_release():
    from suite_gui import release
    from suite_gui import spps_tk_gui

    assert spps_tk_gui.SPPSGui is release.SPPSGui
    assert spps_tk_gui.main is release.main
    assert spps_tk_gui.launch is release.launch


def test_controller_has_one_direct_launch_guard():
    source = (ROOT / "suite_gui" / "controller.py").read_text(encoding="utf-8")
    assert source.count('if __name__ == "__main__":') <= 1
    assert "release_composition" not in source
    assert "legacy_controller" not in source


def test_final_controller_surface_matches_the_accepted_release():
    from suite_gui.release import SPPSGui

    required_routes = (
        "_build", "destroy", "generate_update_plan", "pm_generate_selected",
        "pm_calculate_all", "apply_change", "pm_apply_change", "export_outputs",
        "pm_on_select", "save_autosave_state", "schedule_autosave",
        "restore_custom_db_tab",
    )
    assert all(callable(getattr(SPPSGui, name, None)) for name in required_routes)
    assert SPPSGui.TITLE == "SPPS Planner V8.0.0"
    assert SPPSGui.RESIN_VALUES == [
        "Rink Amide AM", "Rink Amide MBHA", "Rink Amide ChemMatrix",
        "Rink Amide Tentagel", "2-CTC", "CTC(합성기)", "Wang", "HMPB",
        "Sieber Amide", "PAL resin", "Tentagel", "Manual",
    ]


def test_active_controller_routes_are_declared_directly():
    from suite_gui.release import SPPSGui

    required = {
        "_build", "generate_update_plan", "apply_change", "export_outputs",
        "pm_on_select", "pm_add_peptide", "pm_delete_peptide",
        "save_autosave_state", "schedule_autosave", "save_project",
    }
    assert required <= set(SPPSGui.__dict__)
    assert {
        SPPSGui.__dict__[name].__module__ for name in required
    } == {"suite_gui.controller"}


def test_public_import_does_not_load_numbered_or_legacy_modules():
    script = """
import json, sys
from suite_gui.release import SPPSGui
print(json.dumps(sorted(
    name for name in sys.modules
    if name == 'suite_gui.legacy_controller'
    or name == 'suite_gui.release_composition'
    or name.startswith('suite_gui.modules.v')
    or name.startswith('suite_gui.compat')
)))
"""
    import json
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout.strip()) == []


def test_classic_base_contains_no_runtime_controller_assignments():
    path = ROOT / "suite_gui" / "classic_base.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden = []
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in {"SPPSGui", "gui_cls"}
            ):
                forbidden.append((target.value.id, target.attr, node.lineno))
    assert forbidden == []
