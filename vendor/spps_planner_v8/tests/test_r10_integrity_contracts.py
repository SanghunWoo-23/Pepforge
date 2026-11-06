from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from suite_gui import persistence_workflow
from suite_gui.modules import plan_workflow


def test_collect_state_aborts_when_active_plan_capture_fails(monkeypatch):
    gui = SimpleNamespace(pm_items=[])
    def boom(*_args, **_kwargs):
        raise RuntimeError("capture failed")
    monkeypatch.setattr(plan_workflow, "_save_active", boom)
    with pytest.raises(RuntimeError, match="capture the active Planner state"):
        persistence_workflow.collect_state(gui)


def test_failed_project_publication_does_not_advance_revision_or_history(tmp_path: Path, monkeypatch):
    gui = SimpleNamespace(
        _project_revision=7, _project_change_history=[{"revision":7}],
        _loaded_project_path=None, _loaded_project_fingerprint="", last_outdir=None,
    )
    monkeypatch.setattr(persistence_workflow, "collect_state", lambda _gui: {"project_revision":7,"project_change_history":[{"revision":7}]})
    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(persistence_workflow.state_persistence, "atomic_write_json_with_backup", fail_write)
    with pytest.raises(OSError, match="disk full"):
        persistence_workflow._save_project_path(gui, tmp_path / "project.json", False)
    assert gui._project_revision == 7
    assert gui._project_change_history == [{"revision":7}]


def test_proxy_or_approx_reagents_require_manual_identity_confirmation():
    root = Path(__file__).resolve().parents[1]
    path = root / "apps" / "spps_planner_app" / "data" / "compounds.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = {row["Token"]: row for row in csv.DictReader(handle)}
    guarded = {"Dpr","Hyl","Chg","Bip","Phe4Me","TyrMe","MeGly","Sec"}
    assert guarded <= set(rows)
    for token in guarded:
        row = rows[token]
        assert row["Chemistry profile"] == "MANUAL_REQUIRED"
        assert "operator-confirmed" in row["DB note"]
