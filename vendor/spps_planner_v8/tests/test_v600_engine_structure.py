from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "apps" / "spps_planner_app" / "spps_planner" / "engine.py"


def _top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_embedded_engine_has_one_canonical_material_pipeline():
    source = ENGINE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = _top_level_functions(tree)

    forbidden_fragments = (
        "_V219_",
        "_V221_",
        "_V222_",
        "ORIG_GENERATE",
        "FINAL REPAIR",
        "patch-stack",
        "hotfix",
    )
    assert not [fragment for fragment in forbidden_fragments if fragment in source]

    dead_superseded_functions = {
        "_recommend_cleavage_preset_initial",
        "_generate_cleavage_cocktail_initial",
        "_plan_summary_initial",
        "_liquid_display_policy",
    }
    assert dead_superseded_functions.isdisjoint(functions)

    for public_name, core_name in (
        ("generate_step_materials", "_generate_step_materials_core"),
        ("generate_materials", "_generate_materials_core"),
    ):
        node = functions[public_name]
        calls = {
            call.func.id
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        }
        assert core_name in calls
        assert not any(name.startswith("_generate_") and "_v2" in name.lower() for name in calls)


def test_embedded_engine_does_not_capture_old_generator_functions_for_rebinding():
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    suspicious = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Name):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and (
                "ORIG" in target.id.upper()
                or "PATCH" in target.id.upper()
                or "OLD_GENERATE" in target.id.upper()
            ):
                suspicious.append((target.id, value.id))
    assert suspicious == []
