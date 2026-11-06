from __future__ import annotations

from pathlib import Path

from suite_gui import ui_system
from tools import verify_windows_release


ROOT = Path(__file__).resolve().parents[1]


def test_responsive_geometry_fits_common_screens_and_centers():
    assert ui_system.responsive_geometry(1920, 1080) == "1600x900+160+90"
    assert ui_system.responsive_geometry(1366, 768) == "1286x680+40+44"
    assert ui_system.responsive_geometry(1024, 680) == "1024x680+0+0"


def test_density_modes_have_complete_real_dimensions():
    assert set(ui_system.DENSITIES) == {"Compact", "Standard", "Comfortable"}
    assert [ui_system.DENSITIES[name]["tree_rowheight"] for name in ui_system.DENSITIES] == [24, 28, 32]
    assert all(values["tab_padding"] and values["button_padding"] for values in ui_system.DENSITIES.values())


def test_shortcuts_route_directly_to_real_controller_methods():
    class Gui:
        def __init__(self):
            self.bound = {}
            self.calls = []

        def bind_all(self, sequence, callback, add=None):
            self.bound[sequence] = callback

        def save_project(self):
            self.calls.append("save")

        def generate_update_plan(self):
            self.calls.append("generate")

    gui = Gui()
    bindings = ui_system.bind_shortcuts(gui)
    assert {"<Control-s>", "<Control-g>", "<Control-Return>", "<Control-e>"} <= set(bindings)
    assert gui.bound["<Control-s>"]() == "break"
    assert gui.bound["<Control-g>"]() == "break"
    assert gui.calls == ["save", "generate"]


def test_windows_release_contract_has_no_stale_v2_or_legacy_imports():
    verify_windows_release.verify_all()
    spec = (ROOT / "SPPS_Planner.spec").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "SPPS_Planner_Setup.iss").read_text(encoding="utf-8")
    assert "legacy_controller" not in spec
    assert "release_composition" not in spec
    assert '#define MyAppVersion "8.0.0"' in installer
    assert "VersionInfoVersion=8.0.0.0" in installer
    launcher = (ROOT / "main_launcher.py").read_text(encoding="utf-8")
    assert "SetProcessDpiAwareness" in launcher
    version = (ROOT / "apps" / "spps_planner_app" / "spps_planner" / "version.py").read_text(encoding="utf-8")
    assert 'VERSION_NUMBER = "8.0.0"' in version
    assert 'DATA_VERSION = "SPPS data v6.0.0"' in version


def test_final_manuals_cover_every_operator_workspace():
    ko = (ROOT / "docs" / "USER_MANUAL_KO.md").read_text(encoding="utf-8")
    en = (ROOT / "docs" / "USER_MANUAL_EN.md").read_text(encoding="utf-8")
    for label in ("Apply Change", "Run / Corrections", "Outcome / ML", "Risk Review", "Data / HPLC", "Column_Map"):
        assert label in ko
    for label in ("Apply Change", "Run / Corrections", "Outcome / ML", "Risk Review", "Data / HPLC", "Column Map"):
        assert label in en
