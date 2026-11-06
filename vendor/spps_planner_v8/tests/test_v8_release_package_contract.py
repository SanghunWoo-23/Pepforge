"""Source-package hygiene and V8 release identity guardrails."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v8_release_version_and_citation():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V8.0.0"
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "V8.0.0"
    assert 'version: "8.0.0"' in (ROOT / "CITATION.cff").read_text(encoding="utf-8")


def test_minimal_windows_build_entrypoints():
    scripts = {p.name for p in ROOT.glob("*.bat")}
    assert scripts == {"INSTALL_BUILD_TOOLS_AND_BUILD.bat"}
    content = (ROOT / "INSTALL_BUILD_TOOLS_AND_BUILD.bat").read_text(encoding="utf-8")
    for token in ("winget install", "--no-pause", "PyInstaller", "--self-test",
                  "verify_packaged_runtime.py", "ISCC", "--check-installer",
                  "SPPS_Planner_Setup_V8.0.0.exe"):
        assert token in content
    assert "BUILD_EXE_ONLY.bat" not in content
    assert "BUILD_INSTALLER.bat" not in content


def test_release_docs_and_no_archived_notes():
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "README_KO.md").is_file()
    assert (ROOT / "RELEASE_NOTES_V8.0.0.txt").is_file()
    assert not (ROOT / "PACKAGE_README.md").exists()
    assert not (ROOT / "docs/release_history").exists()


def test_v8_export_output_filenames():
    source = (ROOT / "suite_gui/modules/plan_workflow.py").read_text(encoding="utf-8")
    assert "project_manager_selected_outputs_v8.0.0.xlsx" in source
    assert "project_manager_state_v8.0.0.json" in source
    assert "project_manager_selected_outputs_v7.0.0.xlsx" not in source
