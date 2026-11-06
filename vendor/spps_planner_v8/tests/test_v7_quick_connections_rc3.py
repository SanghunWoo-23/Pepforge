from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from suite_gui import quick_synthesis


class Var:
    def __init__(self, value=""):
        self.value = str(value)
    def get(self):
        return self.value
    def set(self, value):
        self.value = str(value)


def test_sync_active_project_does_not_touch_saved_rows_without_active_selection():
    old = {"sequence": "OLD", "scale": "0.2", "copies": "1", "resin": "Rink Amide AM", "loading": "0.8", "chemistry": "DIC/HOBt"}
    gui = SimpleNamespace(
        pm_items=[dict(old)], pm_sequence=Var("NEW"), pm_scale=Var("0.1"), pm_copies=Var("1"),
        pm_resin=Var("Rink Amide AM"), pm_loading=Var("0.8"), pm_chemistry=Var("HBTU/NMM"),
        pm_project=Var(""), pm_peptide=Var(""), pm_lot=Var(""),
    )
    gui.pm_current_index = lambda: None
    added = []
    def add(item):
        added.append(dict(item))
        gui.pm_items.append(dict(item))
    gui.pm_add_peptide = add
    gui.pm_live_sync_selected = lambda: None
    gui.schedule_autosave = lambda: None

    assert quick_synthesis.sync_active_project(gui, create=True)
    assert gui.pm_items[0]["sequence"] == "OLD"
    assert added and added[0]["sequence"] == "NEW"


def test_packaged_runtime_verifier_reads_version_file(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "report.json"
    version = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    report.write_text(json.dumps({"app_version": version, "build_revision": "test", "checks": {"version": True}, "ok": True}), encoding="utf-8")
    run = subprocess.run([sys.executable, str(root / "tools" / "verify_packaged_runtime.py"), str(report)], cwd=root, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr + run.stdout
