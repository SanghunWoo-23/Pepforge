"""Measure runtime method rebinding across the desktop GUI package."""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path


TARGET_NAMES = {"SPPSGui", "gui_cls"}
ENGINE_PUBLIC_API = {
    "generate_cleavage_cocktail", "recommend_cleavage_preset", "plan_summary",
    "generate_step_materials", "generate_materials",
}


def _target_binding(target) -> str | None:
    if not isinstance(target, ast.Attribute):
        return None
    if isinstance(target.value, ast.Name) and target.value.id in TARGET_NAMES:
        return f"{target.value.id}.{target.attr}"
    return None


def audit(root: Path) -> dict:
    bindings = []
    files = sorted(root.rglob("*.py"))
    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    name = _target_binding(target)
                    if name:
                        bindings.append(
                            {
                                "file": str(path.relative_to(root)),
                                "line": node.lineno,
                                "target": name,
                                "value": ast.unparse(node.value),
                            }
                        )
            elif isinstance(node, ast.AnnAssign):
                name = _target_binding(node.target)
                if name:
                    bindings.append(
                        {
                            "file": str(path.relative_to(root)),
                            "line": node.lineno,
                            "target": name,
                            "value": ast.unparse(node.value),
                        }
                    )
    by_attribute = Counter(item["target"].split(".", 1)[1] for item in bindings)
    by_file = Counter(item["file"] for item in bindings)
    return {
        "root": str(root),
        "python_files": len(files),
        "binding_count": len(bindings),
        "build_wrapper_count": by_attribute.get("_build", 0),
        "bindings_by_attribute": dict(by_attribute.most_common()),
        "bindings_by_file": dict(by_file.most_common()),
        "bindings": bindings,
    }


def audit_active_release() -> dict:
    """Report only routes that are active after release composition."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from suite_gui.release import SPPSGui
    from suite_gui.release_contract import active_route_report

    routes = active_route_report(SPPSGui)
    return {
        "route_count": len(routes),
        "legacy_controller_routes": sorted(
            name
            for name, details in routes.items()
            if details["module"] == "suite_gui.legacy_controller"
        ),
        "numbered_module_routes": sorted(
            name
            for name, details in routes.items()
            if details["module"].startswith("suite_gui.modules.v")
        ),
        "routes": routes,
    }


def audit_engine_api() -> dict:
    """Ensure the calculation API has one source definition per public name."""
    path = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "spps_planner" / "engine.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    definitions = Counter(
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ENGINE_PUBLIC_API
    )
    duplicates = {
        name: count for name, count in definitions.items() if count != 1
    }
    missing = sorted(ENGINE_PUBLIC_API - set(definitions))
    return {
        "definitions": dict(definitions),
        "duplicates": duplicates,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path("suite_gui"),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--active-release",
        action="store_true",
        help="audit final runtime routes instead of historical source bindings",
    )
    args = parser.parse_args()
    report = audit_active_release() if args.active_release else audit(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.active_release:
        print(f"Active routes: {report['route_count']}")
        print(
            "Legacy controller routes: "
            + (", ".join(report["legacy_controller_routes"]) or "none")
        )
    else:
        print(f"Root: {report['root']}")
        print(f"Python files: {report['python_files']}")
        print(f"Runtime class bindings: {report['binding_count']}")
        print(f"_build wrappers: {report['build_wrapper_count']}")
        print("Highest-binding files:")
        for path, count in list(report["bindings_by_file"].items())[:10]:
            print(f"  {count:4d}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
