from pathlib import Path
import pytest
from spps_planner.build_profile import IS_PRIVATE, APP_FOLDER
from spps_planner.user_paths import assert_profile_path
from suite_gui import experimental_workflow


def test_default_profile_name_is_distinct():
    assert APP_FOLDER == ("SPPS_Planner_PRIVATE" if IS_PRIVATE else "SPPS_Planner_PUBLIC")


def test_explicit_folder_is_not_blocked_based_on_name(tmp_path):
    other = "SPPS_Planner_PUBLIC" if IS_PRIVATE else "SPPS_Planner_PRIVATE"
    requested = tmp_path / other / "experimental_v5.sqlite"
    assert assert_profile_path(requested) == requested
    gui = type("GUI", (), {})()
    gui.experimental_db_path = requested
    assert experimental_workflow.db_path(gui) == requested


def test_public_package_has_no_private_seed():
    if IS_PRIVATE:
        pytest.skip("Private intentionally bundles experimental seed")
    root = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    assert not any(p.is_file() and p.name != "README.md" for p in root.iterdir())


def test_loading_summary_present():
    path = Path(__file__).resolve().parents[1] / "suite_gui" / "modules" / "experimental_data_panel.py"
    source = path.read_text(encoding="utf-8")
    assert "self.load_summary" in source
    assert "APPLY-ELIGIBLE LOADING CONDITION" in source
    assert "CHEMISTRY DEFAULT ONLY" in source
