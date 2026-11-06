from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def test_v8_standalone_entry_present():
    assert (ROOT / "vendor/spps_planner_v8/main_launcher.py").is_file()
    assert (ROOT / "vendor/spps_planner_v8/VERSION.txt").read_text().strip() == "V8.0.0"

def test_pepforge_version_unchanged():
    from peptiforg_core.version import PEPFORGE_VERSION
    assert str(PEPFORGE_VERSION).lstrip("Vv") == "6.0.0"

def test_v8_launcher_dispatch_is_valid_python():
    text = (ROOT / "main_launcher.py").read_text(encoding="utf-8")
    ast.parse(text)
    assert 'v8_root = _resource_path("vendor", "spps_planner_v8")' in text
    assert 'companion = exe_dir / "SPPS_Planner" / "SPPS_Planner.exe"' in text
    assert 'SPPS Planner V8 executable is missing' in text
