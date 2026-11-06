from __future__ import annotations

import ast
from pathlib import Path

from suite_gui import plan_input_factory

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value):
        self._value = value
    def get(self):
        return self._value
    def set(self, value):
        self._value = value


class _Gui:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, _Var(value))


def test_cleavage_helpers_have_one_canonical_definition_each():
    path = ROOT / "apps" / "spps_planner_app" / "spps_planner" / "engine.py"
    module = ast.parse(path.read_text(encoding="utf-8"))
    counts = {name: 0 for name in (
        "_canonical_cleavage_component",
        "cleavage_cocktail_presets",
        "_preset_components",
    )}
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in counts:
            counts[node.name] += 1
    assert counts == {name: 1 for name in counts}


def test_blank_editor_sequence_does_not_fall_back_to_demo_peptide():
    gui = _Gui(pm_sequence="", pm_scale="0.2", pm_copies="1", pm_loading="0.8", pm_chemistry="DIC/HOBt", coupling_eq="5")
    plan = plan_input_factory.build_editor_plan_input(gui, "Rink Amide AM", True)
    assert plan.sequence == ""


def test_release_blank_item_has_no_invented_project_or_peptide_identity():
    from suite_gui.modules.release_ui import _blank_item
    item = _blank_item()
    assert item["project"] == ""
    assert item["peptide"] == ""
    assert item["sequence"] == ""
