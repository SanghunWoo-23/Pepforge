"""Static and optional binary checks for the Windows V8.0.0 Final release."""
from __future__ import annotations

import argparse
import ast
import importlib.util
from pathlib import Path
import re
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "apps" / "spps_planner_app"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from suite_gui import catalogs
from suite_gui.session_state import DEFAULT_STATE_FIELDS
from spps_planner.database import (
    bundled_compounds_path,
    compound_lookup,
    load_compounds,
    validate_compounds_dataframe,
)

VERSION = "V8.0.0"
NUMBER = "8.0.0"
FORBIDDEN_IMPORTS = {
    "suite_gui.legacy_controller", "suite_gui.release_composition",
    "suite_gui.modules.classic_workflow", "suite_gui.modules.workbench_workflow",
}


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_identity() -> None:
    _require(_read("VERSION").strip() == VERSION, "VERSION identity mismatch")
    _require(_read("VERSION.txt").strip() == VERSION, "VERSION.txt identity mismatch")
    version_source = _read("apps/spps_planner_app/spps_planner/version.py")
    _require(f'VERSION_NUMBER = "{NUMBER}"' in version_source, "Internal VERSION_NUMBER mismatch")
    _require('DATA_VERSION = "SPPS data v6.0.0"' in version_source, "Data version mismatch")
    installer = _read("installer/SPPS_Planner_Setup.iss")
    _require(f'#define MyAppVersion "{NUMBER}"' in installer, "Installer AppVersion mismatch")
    _require(f"VersionInfoVersion={NUMBER}.0" in installer, "Installer file metadata mismatch")
    _require('#define MyAppPublisher "Sanghun Woo"' in installer, "Installer publisher mismatch")
    version_info = _read("installer/version_info.txt")
    _require("filevers=(8, 0, 0, 0)" in version_info, "EXE file version mismatch")
    _require("prodvers=(8, 0, 0, 0)" in version_info, "EXE product version mismatch")
    _require("StringStruct(u'CompanyName', u'Sanghun Woo')" in version_info, "EXE company metadata mismatch")
    stale = []
    version_names = {"APP_VERSION", "VERSION", "VERSION_NUMBER", "VERSION_LABEL", "TITLE"}
    for path in sorted((ROOT / "suite_gui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if any(isinstance(target, ast.Name) and target.id in version_names for target in targets):
                text = value.value
                if re.search(r"V?[2-5]\.\d+\.\d+", text):
                    stale.append(f"{path.relative_to(ROOT)}:{node.lineno}={text}")
    _require(not stale, "Stale runtime version constants remain: " + "; ".join(stale))


def _hidden_imports() -> list[str]:
    tree = ast.parse(_read("SPPS_Planner.spec"), filename="SPPS_Planner.spec")
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "hiddenimports" for target in node.targets):
            return [str(value.value) for value in node.value.elts if isinstance(value, ast.Constant)]
    raise RuntimeError("SPPS_Planner.spec has no literal hiddenimports list")


def verify_spec() -> None:
    imports = _hidden_imports()
    stale = sorted(set(imports) & FORBIDDEN_IMPORTS)
    _require(not stale, "Removed legacy hidden imports remain: " + ", ".join(stale))
    required = {
        "suite_gui.controller", "suite_gui.work_item_window", "suite_gui.data_workflow",
        "suite_gui.ml_workflow", "suite_gui.risk_workflow", "spps_planner.engine",
    }
    _require(required <= set(imports), "Required runtime hidden imports are missing")
    for name in imports:
        _require(importlib.util.find_spec(name) is not None, f"Hidden import cannot resolve: {name}")
    spec = _read("SPPS_Planner.spec")
    _require('version=str(project / "installer" / "version_info.txt")' in spec, "EXE version resource is not connected")


def verify_build_scripts() -> None:
    """The only BAT must retain tooling, build, self-test and installer checks."""
    scripts = {path.name for path in ROOT.glob("*.bat")}
    _require(scripts == {"INSTALL_BUILD_TOOLS_AND_BUILD.bat"},
             f"Expected exactly one Windows build BAT, got: {sorted(scripts)}")
    script = _read("INSTALL_BUILD_TOOLS_AND_BUILD.bat")
    required = (
        "--no-pause", "Python.Python.3.12", "JRSoftware.InnoSetup",
        "-r requirements.txt -r requirements-dev.txt", "-m compileall",
        "tools\\verify_windows_release.py", "runtime_selftest",
        "-m PyInstaller", "--check-exe", "--self-test",
        "tools\\verify_packaged_runtime.py", "ISCC",
        "installer\\SPPS_Planner_Setup.iss", "--check-installer",
        "SPPS_Planner_Setup_V8.0.0.exe",
    )
    missing = [token for token in required if token not in script]
    _require(not missing, f"Missing mandatory build stage(s): {missing}")
    _require("call BUILD_" not in script,
             "Single BAT must not call a deleted build script")


def verify_icons() -> None:
    png_path = ROOT / "assets" / "SPPS_Planner_Icon.png"
    ico_path = ROOT / "assets" / "SPPS_Planner_Icon.ico"
    _require(png_path.is_file(), "SPPS Planner PNG icon is missing")
    _require(ico_path.is_file(), "SPPS Planner Windows icon is missing")
    with Image.open(png_path) as png:
        _require(png.mode == "RGBA", "SPPS Planner PNG icon must preserve transparency")
        _require(png.size == (500, 500), "SPPS Planner PNG icon has unexpected dimensions")
        _require(png.getpixel((0, 0))[3] == 0, "SPPS Planner PNG background is not transparent")
    with Image.open(ico_path) as ico:
        sizes = set(ico.info.get("sizes", ()))
    required_sizes = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
    _require(required_sizes <= sizes, "SPPS Planner ICO is missing Windows icon sizes")


def verify_operator_fmoc_catalog() -> None:
    names = [
        *catalogs.FMOC_AA_VALUES,
        *catalogs.FMOC_D_AA_VALUES,
        *catalogs.FMOC_NON_NATURAL_AA_VALUES,
        *catalogs.FMOC_LINKER_VALUES,
    ]
    _require(names and len(names) == len(set(names)), "Fmoc operator catalog is empty or duplicated")
    _require(all(name.startswith("Fmoc-") for name in names), "Fmoc operator catalog contains a shorthand name")
    forbidden_choices = {"A", "Ala", "R", "Arg", "D-R", "D-Arg", "dR", "PEG4", "Ahx"}
    _require(not forbidden_choices.intersection(catalogs.UNIT_VALUES), "Legacy one-/three-letter material choices remain visible")
    _require("Fmoc-D-Gly-OH" not in names, "Achiral glycine must not be presented as a D-isomer")

    compounds = load_compounds(bundled_compounds_path())
    issues = validate_compounds_dataframe(compounds)
    if not issues.empty:
        errors = issues[issues["level"].eq("ERROR")]
        _require(errors.empty, "Bundled compounds.csv has schema errors")
    lookup = compound_lookup(compounds)
    forbidden_markers = ("placeholder", "default/proxy", "vendor-specific", "verify exact")
    for name in names:
        row = lookup.get(name)
        _require(row is not None, f"Operator catalog reagent is absent from compounds.csv: {name}")
        _require(str(row.get("Reagent/protected form", "")) == name, f"Catalog name is not exact in compounds.csv: {name}")
        try:
            mw = float(row.get("Reagent MW (g/mol)", 0) or 0)
        except Exception:
            mw = 0.0
        _require(mw > 0, f"Operator catalog reagent has no calculable MW: {name}")
        joined = " ".join(str(value).lower() for value in row.values())
        _require(not any(marker in joined for marker in forbidden_markers), f"Operator catalog reagent contains placeholder language: {name}")


def verify_no_runtime_monkey_patching() -> None:
    violations = []
    roots = (ROOT / "suite_gui", ROOT / "apps" / "spps_planner_app" / "spps_planner")
    for source_root in roots:
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "MethodType":
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:MethodType")
                    if node.func.id == "setattr" and node.args and isinstance(node.args[0], ast.Name):
                        target = node.args[0].id
                        if target[:1].isupper():
                            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:class setattr")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "__get__":
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:descriptor rebinding")
    _require(not violations, "Runtime monkey patching detected: " + "; ".join(violations))


def verify_single_volume_basis_ui() -> None:
    classic = _read("suite_gui/classic_base.py")
    release_ui = _read("suite_gui/modules/release_ui.py")
    _require("self.ml_per_mmol =" not in classic, "Removed global volume variable was recreated")
    _require("textvariable=self.ml_per_mmol" not in classic, "Removed global volume widget remains")
    _require("'mL per mmol'" not in classic and '"mL per mmol"' not in classic, "Duplicate mL per mmol label remains")
    _require("Amide/Rink" in release_ui and "2-CTC/Trityl" in release_ui, "Canonical resin-specific volume controls are missing")
    _require("ml_per_mmol" not in DEFAULT_STATE_FIELDS, "Removed global volume field is still persisted")


def _verify_pe(path: Path, label: str) -> None:
    _require(path.is_file(), f"{label} was not found: {path}")
    _require(path.stat().st_size > 1024, f"{label} is unexpectedly small")
    _require(path.read_bytes()[:2] == b"MZ", f"{label} is not a Windows PE executable")


def verify_all(*, check_exe: bool = False, check_installer: bool = False) -> None:
    verify_identity()
    verify_spec()
    verify_build_scripts()
    verify_icons()
    verify_operator_fmoc_catalog()
    verify_no_runtime_monkey_patching()
    verify_single_volume_basis_ui()
    if check_exe:
        _verify_pe(ROOT / "dist" / "SPPS_Planner" / "SPPS_Planner.exe", "Portable EXE")
    if check_installer:
        _verify_pe(ROOT / "installer" / "output" / "SPPS_Planner_Setup_V8.0.0.exe", "Installer")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-exe", action="store_true")
    parser.add_argument("--check-installer", action="store_true")
    args = parser.parse_args()
    verify_all(check_exe=args.check_exe, check_installer=args.check_installer)
    print("[OK] SPPS Planner V8.0.0 source Windows release contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
