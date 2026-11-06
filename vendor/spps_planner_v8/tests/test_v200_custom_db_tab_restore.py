from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v200_custom_db_restore_is_narrow_and_version_fixed():
    module = (ROOT / "suite_gui" / "custom_db_workflow.py").read_text(encoding="utf-8")
    controller = (ROOT / "suite_gui" / "controller.py").read_text(encoding="utf-8")
    assert "def restore_tab" in module
    assert "def add_or_update" in module
    assert "custom_db_workflow.restore_tab(self)" in controller
    assert "legacy_controller" not in controller


def test_direct_custom_material_classes_and_connections_exist():
    classic = (ROOT / "suite_gui" / "custom_db_workflow.py").read_text(encoding="utf-8")
    for category in ["AA/Chemical", "Coupling reagent", "Catalyst/additive", "Base", "Solvent", "Cleavage cocktail", "Resin", "Other"]:
        assert category in classic
    for function_name in [
        "add_or_update",
        "delete_selected",
        "lookup",
        "custom_options",
        "refresh_setup_comboboxes",
    ]:
        assert f"def {function_name}" in classic
