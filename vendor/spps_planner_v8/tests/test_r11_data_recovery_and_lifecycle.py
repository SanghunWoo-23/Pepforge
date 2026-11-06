from __future__ import annotations

from pathlib import Path
import sqlite3
import tkinter as tk

import pytest

from suite_gui import experimental_data


def _reset() -> None:
    experimental_data._INITIALIZED_DB_PATHS.clear()


def test_premerge_backup_preserves_canonical_before_legacy_import(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "profile" / "experimental_v5.sqlite"
    legacy = canonical.parent / "data" / canonical.name
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset()
    experimental_data.initialize(canonical)
    kept = experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Ala-OH", "loading_rate_mmol_g":0.20,
    }, canonical)
    _reset()
    experimental_data.initialize(legacy)
    incoming = experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Gly-OH", "loading_rate_mmol_g":0.27,
    }, legacy)
    _reset()
    experimental_data.initialize(canonical)
    status = experimental_data.legacy_recovery_status(canonical)
    backup = Path(status["last_backup"])
    assert backup.is_file()
    current = experimental_data.list_records("loading", canonical)
    assert {r["record_id"] for r in current} >= {kept["record_id"], incoming["record_id"]}
    backup_rows = experimental_data.list_records("loading", backup)
    backup_ids = {r["record_id"] for r in backup_rows}
    assert kept["record_id"] in backup_ids
    assert incoming["record_id"] not in backup_ids


def test_corrupt_legacy_store_is_not_merged_and_is_reported(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "profile" / "experimental_v5.sqlite"
    legacy = canonical.parent / "data" / canonical.name
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset()
    experimental_data.initialize(canonical)
    kept = experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Ala-OH", "loading_rate_mmol_g":0.20,
    }, canonical)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(b"this is not a sqlite database")
    _reset()
    experimental_data.initialize(canonical)
    rows = experimental_data.list_records("loading", canonical)
    assert [r["record_id"] for r in rows].count(kept["record_id"]) == 1
    status = experimental_data.legacy_recovery_status(canonical)
    assert str(legacy) in status["last_error"]
    assert "integrity=" in status["last_error"]


def test_manual_database_backup_round_trip(tmp_path: Path):
    db = tmp_path / "experimental_v5.sqlite"
    _reset()
    experimental_data.initialize(db)
    row = experimental_data.add_record("cleavage", {
        "product":"Backup","sequence":"AC","scale_mmol":0.1,"cleavage_eq":100,"cleavage_time_h":3,
    }, db)
    backup = experimental_data.backup_database(db, reason="manual_test")
    assert backup.is_file()
    assert "manual_test" in backup.name
    _reset()
    rows = experimental_data.list_records("cleavage", backup)
    assert any(r["record_id"] == row["record_id"] for r in rows)


def test_experimental_window_destroy_cancels_its_pending_jobs(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    from suite_gui.modules import experimental_data_panel
    monkeypatch.setattr(experimental_data_panel.ExperimentalDataWindow, "_build", lambda self: None)
    monkeypatch.setattr(experimental_data_panel.ui_system, "fit_window", lambda *a, **k: None)
    window = experimental_data_panel.ExperimentalDataWindow(root)
    token = window._schedule(60000, lambda: None)
    assert token is not None
    assert token in set(map(str, root.tk.call("after", "info")))
    window.destroy()
    assert token not in set(map(str, root.tk.call("after", "info")))
    root.destroy()


def test_coupling_review_rolls_back_when_evidence_db_write_fails(monkeypatch):
    from suite_gui import experimental_workflow, ml_dataset
    from suite_gui.modules import gui_common
    original = {"peptide":"P", "sequence":"AC", "work_item_id":"WI1", "marker":"before"}
    gui = type("G", (), {})()
    gui.pm_items = [dict(original)]
    monkeypatch.setattr(gui_common, "save_active", lambda _gui: None)
    monkeypatch.setattr(gui_common, "active_index", lambda _gui: 0)
    def mutate(item, **_kwargs):
        item["marker"] = "reviewed"
        item["new_review_field"] = 1
        return {"version": 1}
    monkeypatch.setattr(ml_dataset, "review_item", mutate)
    monkeypatch.setattr(experimental_workflow, "active_run_context", lambda _gui: {"run_id":"RUN1"})
    monkeypatch.setattr(experimental_workflow, "_ready_db", lambda _gui: Path("unused.sqlite"))
    monkeypatch.setattr(experimental_data, "add_outcome", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    with pytest.raises(RuntimeError, match="Work Item review was restored"):
        experimental_workflow.record_coupling_review(gui, actual_purity_percent=90)
    assert gui.pm_items[0] == original


def test_data_store_status_uses_sql_counts_not_full_history_materialization(tmp_path: Path, monkeypatch):
    from suite_gui import experimental_workflow
    db = tmp_path / "experimental_v5.sqlite"
    experimental_data.initialize(db)
    experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Ala-OH", "loading_rate_mmol_g":0.20,
    }, db)
    gui = type("G", (), {"experimental_db_path": db})()
    monkeypatch.setattr(experimental_data, "list_records", lambda *a, **k: (_ for _ in ()).throw(AssertionError("full history scan")))
    status = experimental_workflow.data_store_status(gui)
    assert status["counts"]["loading"] >= 1


def test_explicit_v5_database_does_not_auto_clone_adjacent_v4(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "canonical" / "experimental_v5.sqlite"
    explicit = tmp_path / "explicit" / "experimental_v5.sqlite"
    legacy_v4 = explicit.with_name("experimental_v4.sqlite")
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset()
    experimental_data.initialize(legacy_v4)
    old = experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Val-OH", "loading_rate_mmol_g":0.22,
    }, legacy_v4)
    _reset()
    experimental_data.initialize(explicit)
    rows = experimental_data.list_records("loading", explicit)
    assert all(r["record_id"] != old["record_id"] for r in rows)
