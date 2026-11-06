"""Repeatable final verification for the SPPS Planner V8.0.0 source release."""
from __future__ import annotations

import argparse
import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "V8.0.0"
REQUIRED_FILES = (
    "main_launcher.py",
    "SPPS_Planner.spec",
    "INSTALL_BUILD_TOOLS_AND_BUILD.bat",
    "assets/SPPS_Planner_Icon.ico",
    "installer/SPPS_Planner_Setup.iss",
)


def verify_static_release() -> None:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError("Missing release files: " + ", ".join(missing))
    legacy_icons = [name for name in ("assets/Pepforge_Icon.ico", "assets/Pepforge_Icon.png") if (ROOT / name).exists()]
    if legacy_icons:
        raise RuntimeError("Legacy Pepforge icon asset(s) returned: " + ", ".join(legacy_icons))
    for name in ("VERSION", "VERSION.txt"):
        actual = (ROOT / name).read_text(encoding="utf-8").strip()
        if actual != EXPECTED_VERSION:
            raise RuntimeError(f"{name} is {actual!r}, expected {EXPECTED_VERSION!r}")
    from suite_gui.release import SPPSGui
    from suite_gui.release_contract import validate_release_controller

    validate_release_controller(SPPSGui)
    if SPPSGui.TITLE != "SPPS Planner V8.0.0":
        raise RuntimeError(f"Unexpected release title: {SPPSGui.TITLE}")
    from tools.verify_windows_release import verify_all as verify_windows
    from tools.verify_v7_integrity import verify_production_purity
    verify_windows()
    verify_production_purity()


def verify_monkey_patch_free() -> None:
    from tools.audit_monkey_patches import (
        audit, audit_active_release, audit_engine_api,
    )

    source = audit(ROOT / "suite_gui")
    active = audit_active_release()
    engine = audit_engine_api()
    if source["binding_count"] != 0 or source["build_wrapper_count"] != 0:
        raise RuntimeError(
            "Runtime GUI rebinding remains: "
            f"{source['binding_count']} bindings, "
            f"{source['build_wrapper_count']} build wrappers"
        )
    if active["legacy_controller_routes"] or active["numbered_module_routes"]:
        raise RuntimeError("A legacy or numbered controller route is active")
    if engine["duplicates"] or engine["missing"]:
        raise RuntimeError(
            "Engine public API is rebound or incomplete: "
            f"duplicates={engine['duplicates']}, missing={engine['missing']}"
        )


def run_verification_passes(passes: int) -> None:
    for number in range(1, passes + 1):
        print(f"[verify] complete pass {number}/{passes}", flush=True)
        verify_static_release()
        verify_monkey_patch_free()
        if not compileall.compile_dir(ROOT / "suite_gui", quiet=1):
            raise RuntimeError("suite_gui compilation failed")
        if not compileall.compile_dir(
            ROOT / "apps" / "spps_planner_app" / "spps_planner",
            quiet=1,
        ):
            raise RuntimeError("spps_planner compilation failed")
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=ROOT,
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--passes", type=int, default=1)
    args = parser.parse_args()
    if args.passes < 1:
        parser.error("--passes must be at least 1")
    sys.path.insert(0, str(ROOT))
    run_verification_passes(args.passes)
    print(f"[verify] SPPS Planner {EXPECTED_VERSION}: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
