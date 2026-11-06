from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from suite_gui import experimental_data, experimental_workflow
from spps_planner.build_profile import BUILD_FLAVOR


class Gui(SimpleNamespace):
    def _log(self, *_args):
        return None


def _reset_caches():
    experimental_data._INITIALIZED_DB_PATHS.clear()
    experimental_workflow._SEEDED_DB_PATHS.clear()


def test_operator_write_is_readable_after_process_cache_reset(tmp_path: Path):
    db = tmp_path / "operator.sqlite"
    gui = Gui(experimental_db_path=db, pm_items=[{"peptide":"P","sequence":"AC","scale":"0.1","resin":"2-CTC","loading":"0.3"}], _v2097_active_index=0)
    _reset_caches()
    before_l = len(experimental_workflow.loading_records(gui))
    before_c = len(experimental_workflow.cleavage_records(gui))
    loading = experimental_workflow.add_loading_record(gui, {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Cys(Trt)-OH", "aa_eq":0.5,
        "base_eq":2.0, "loading_time_h":4.0, "loading_rate_mmol_g":0.31,
    })
    cleavage = experimental_workflow.add_cleavage_record(gui, {
        "product":"P", "sequence":"AC", "scale_mmol":0.1, "cleavage_eq":100.0, "cleavage_time_h":3.0,
    })
    assert loading["record_id"] and cleavage["record_id"]
    _reset_caches()  # simulate a fresh application process
    gui2 = Gui(experimental_db_path=db)
    loading_rows = experimental_workflow.loading_records(gui2)
    cleavage_rows = experimental_workflow.cleavage_records(gui2)
    assert len(loading_rows) == before_l + 1
    assert len(cleavage_rows) == before_c + 1
    assert any(r["record_id"] == loading["record_id"] for r in loading_rows)
    assert any(r["record_id"] == cleavage["record_id"] for r in cleavage_rows)


def test_explicit_database_does_not_absorb_unrelated_canonical_history(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "canonical" / "experimental_v5.sqlite"
    explicit = tmp_path / "explicit.sqlite"
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset_caches()
    experimental_data.initialize(canonical)
    experimental_data.add_record("loading", {"resin_type":"2-CTC","amino_acid_raw":"Fmoc-Ala-OH","loading_rate_mmol_g":0.2}, canonical)
    _reset_caches()
    experimental_data.initialize(explicit)
    assert experimental_data.list_records("loading", explicit) == []


def test_legacy_data_subdir_is_recovered_into_canonical_store(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "profile" / "experimental_v5.sqlite"
    legacy = canonical.parent / "data" / canonical.name
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset_caches()
    experimental_data.initialize(legacy)
    old = experimental_data.add_record("loading", {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Gly-OH", "aa_eq":0.5,
        "base_eq":2.0, "loading_time_h":4.0, "loading_rate_mmol_g":0.27,
    }, legacy)
    _reset_caches()
    experimental_data.initialize(canonical)
    rows = experimental_data.list_records("loading", canonical)
    assert any(r["record_id"] == old["record_id"] for r in rows)
    # Recovery copies/merges; the historical source is never deleted.
    assert legacy.is_file()


def test_existing_empty_canonical_merges_changed_legacy_store(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "profile" / "experimental_v5.sqlite"
    legacy = canonical.parent / "data" / canonical.name
    monkeypatch.setattr(experimental_data, "default_db_path", lambda: canonical)
    _reset_caches()
    experimental_data.initialize(canonical)
    _reset_caches()
    experimental_data.initialize(legacy)
    row = experimental_data.add_record("cleavage", {
        "product":"Legacy","sequence":"AC","scale_mmol":0.1,"cleavage_eq":100,"cleavage_time_h":3,
    }, legacy)
    _reset_caches()
    experimental_data.initialize(canonical)
    rows = experimental_data.list_records("cleavage", canonical)
    assert any(r["record_id"] == row["record_id"] for r in rows)


@pytest.mark.skipif(BUILD_FLAVOR != "PRIVATE", reason="Private bundled seed contract")
def test_private_seed_is_not_cached_as_complete_after_import_failure(tmp_path: Path, monkeypatch):
    db = tmp_path / "private.sqlite"
    gui = Gui(experimental_db_path=db)
    _reset_caches()
    real_import = experimental_data.import_path
    state = {"failed": False}
    def flaky(path, db_path=None, **kwargs):
        if Path(path).name == "loading_history_seed.csv" and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("simulated seed failure")
        return real_import(path, db_path, **kwargs)
    monkeypatch.setattr(experimental_data, "import_path", flaky)
    experimental_workflow.initialize(gui)
    key = str(db.resolve())
    assert key not in experimental_workflow._SEEDED_DB_PATHS
    assert "simulated seed failure" in str(getattr(gui, "experimental_db_error", ""))
    experimental_workflow.initialize(gui)
    assert key in experimental_workflow._SEEDED_DB_PATHS
    assert getattr(gui, "experimental_db_error", "") == ""
    assert len(experimental_workflow.loading_records(gui)) >= 61
    assert len(experimental_workflow.cleavage_records(gui)) >= 52


@pytest.mark.skipif(BUILD_FLAVOR != "PRIVATE", reason="Private bundled seed contract")
def test_private_data_store_diagnostic_reports_seed_counts(tmp_path: Path):
    db = tmp_path / "private.sqlite"
    gui = Gui(experimental_db_path=db)
    _reset_caches()
    status = experimental_workflow.data_store_status(gui)
    assert status["build_flavor"] == "PRIVATE"
    assert Path(status["path"]) == db
    assert status["seed_complete"] is True
    assert status["counts"]["loading"] >= 61
    assert status["counts"]["cleavage"] >= 52
    assert status["counts"]["sequence"] == 212
    assert status["counts"]["cleavage_usage"] == 199
