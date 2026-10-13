from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vendored_spps_r2_has_project_batch_runtime():
    vendor = ROOT / "vendor" / "spps_planner_v7_r2"
    assert (vendor / "VERSION").read_text(encoding="utf-8").strip() == "V7.0.0"
    controller = (vendor / "suite_gui" / "controller.py").read_text(encoding="utf-8")
    assert 'TITLE = "SPPS Planner V7.0.0 Final"' in controller
    base = (vendor / "suite_gui" / "classic_base.py").read_text(encoding="utf-8")
    assert "self.geometry('1920x1080')" in base
    assert "self.minsize(1550, 900)" in base


def test_vendored_spps_uses_normal_wheel_scroll_contract():
    vendor = ROOT / "vendor" / "spps_planner_v7_r2"
    dialog = (vendor / "suite_gui" / "modules" / "add_peptide_dialog.py").read_text(encoding="utf-8")
    assert 'bind_class(scroll_tag, "<MouseWheel>", _wheel)' in dialog
    assert 'tags.insert(1, scroll_tag)' in dialog
    assert 'canvas.itemconfigure(canvas_window, width=max(1, int(event.width)))' in dialog


def test_spps_vendor_bridge_is_separate_process_target():
    launcher = (ROOT / "main_launcher.py").read_text(encoding="utf-8")
    assert 'subprocess.Popen(' in launcher
    assert '[sys.executable, str(vendor_entry)]' in launcher
    assert 'cwd=str(vendor_root)' in launcher
    bridge = (ROOT / "vendor" / "spps_planner_v7_r2" / "pepforge_entry.py").read_text(encoding="utf-8")
    assert 'from suite_gui.release import SPPSGui' in bridge
    assert 'PEPFORGE_WORKFLOW_SPPS_SEQUENCE' in bridge
