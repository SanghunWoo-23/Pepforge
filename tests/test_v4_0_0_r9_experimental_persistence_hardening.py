from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from spps_v4_gui import data_system, experimental_data, experimental_workflow
from spps_v4_gui.modules import gui_common
from spps_v4_gui.modules.experimental_data_panel import ExperimentalDataWindow


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_active_run_context_is_real_and_nonblank(monkeypatch):
    """Regression for the Pepforge-only suite_gui/spps_v4_gui namespace mix-up."""
    monkeypatch.setattr(gui_common, "save_active", lambda _gui: None)
    monkeypatch.setattr(gui_common, "active_index", lambda _gui: 0)
    monkeypatch.setattr(data_system, "sync_active_run", lambda item: {"run_id": "RUN-R9", "name": "Run 9"})
    gui = SimpleNamespace(pm_items=[{"work_item_id": "WI-R9"}])

    context = experimental_workflow.active_run_context(gui)

    assert context == {"work_item_id": "WI-R9", "run_id": "RUN-R9", "run_name": "Run 9"}


def test_workflow_records_keep_real_run_and_work_item(tmp_path, monkeypatch):
    db = tmp_path / "experimental.sqlite"
    monkeypatch.setattr(gui_common, "save_active", lambda _gui: None)
    monkeypatch.setattr(gui_common, "active_index", lambda _gui: 0)
    monkeypatch.setattr(data_system, "sync_active_run", lambda item: {"run_id": "RUN-42", "name": "Run 42"})
    gui = SimpleNamespace(
        experimental_db_path=db,
        pm_items=[{"work_item_id": "WI-42"}],
    )

    loading = experimental_workflow.add_loading_record(
        gui,
        {
            "resin_type": "2-CTC",
            "amino_acid_raw": "Fmoc-Ala-OH",
            "aa_eq": 1.0,
            "base": "DIEA",
            "base_eq": 2.0,
            "loading_time_h": 1.0,
            "loading_rate_mmol_g": 0.45,
        },
        status="verified",
    )
    cleavage = experimental_workflow.add_cleavage_record(
        gui,
        {
            "product": "Pep-R9",
            "sequence": "EEMQRR",
            "scale_mmol": 0.1,
            "tfa_ml": 2.85,
            "water_ml": 0.15,
            "cleavage_eq": 30.0,
            "cleavage_time_h": 2.0,
        },
        status="verified",
    )

    assert loading["work_item_id"] == "WI-42"
    assert loading["run_id"] == "RUN-42"
    assert cleavage["work_item_id"] == "WI-42"
    assert cleavage["run_id"] == "RUN-42"


def test_cleavage_snapshot_falls_back_to_persisted_item_rows(monkeypatch):
    monkeypatch.setattr(gui_common, "active_index", lambda _gui: 0)
    gui = SimpleNamespace(
        pm_peptide=_Var("Pep-R9"),
        pm_sequence=_Var("EEMQRR"),
        pm_scale=_Var("0.1"),
        cleavage_time_h=_Var("2"),
        cleavage_eq_override=_Var("30"),
        pm_cleavage_tree=None,
        pm_items=[{
            "selected_cleavage_rows": [
                {"component": "TFA", "volume_mL": 2.85},
                {"component": "DW / water", "volume_mL": 0.15},
                {"component": "TIS", "volume_mL": 0.0},
            ]
        }],
    )
    window = object.__new__(ExperimentalDataWindow)
    window.gui = gui

    snap = ExperimentalDataWindow._current_cleavage_snapshot(window)

    assert snap["tfa_ml"] == pytest.approx(2.85)
    assert snap["water_ml"] == pytest.approx(0.15)
    assert snap["tis_ml"] == pytest.approx(0.0)
    assert snap["cleavage_eq"] == pytest.approx(30.0)


def test_loading_recommendation_filters_shared_query_extras(tmp_path):
    db = tmp_path / "experimental.sqlite"
    gui = SimpleNamespace(experimental_db_path=db, pm_items=[])
    for aa_eq, loading in ((1.0, 0.50), (2.0, 0.90)):
        experimental_workflow.add_loading_record(
            gui,
            {
                "resin_type": "2-CTC",
                "amino_acid_raw": "Fmoc-Ala-OH",
                "aa_eq": aa_eq,
                "base": "DIEA",
                "base_eq": aa_eq * 2,
                "loading_time_h": 1.0,
                "loading_rate_mmol_g": loading,
                "work_item_id": "WI",
                "run_id": "RUN",
            },
            status="verified",
        )

    result = experimental_workflow.recommend_loading(
        gui,
        resin="2-CTC",
        amino_acid="Fmoc-Ala-OH",
        target_loading_mmol_g=0.70,
        aa_eq=1.5,
        base_eq=3.0,
        loading_time_h=1.0,
        include_parsed=False,
        allow_parsed_apply=False,
    )

    assert result["target_recommendation"]["apply_allowed"] is True
    assert result["target_recommendation"]["aa_eq"] == pytest.approx(1.5)


def test_two_process_loading_and_cleavage_persistence_and_reuse(tmp_path):
    """Write in process A; reopen/reuse the same SQLite evidence in process B."""
    root = Path(__file__).resolve().parents[1]
    db = tmp_path / "experimental.sqlite"
    env = os.environ.copy()
    app_path = str(root / "apps" / "spps_planner_app")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root), app_path, env.get("PYTHONPATH", "")]))

    writer = r'''
from pathlib import Path
from types import SimpleNamespace
import sys
from spps_v4_gui import experimental_workflow

db = Path(sys.argv[1])
g = SimpleNamespace(experimental_db_path=db, pm_items=[])
for aa, loading in ((1.0, 0.50), (2.0, 0.90)):
    experimental_workflow.add_loading_record(g, {
        "resin_type":"2-CTC", "amino_acid_raw":"Fmoc-Ala-OH",
        "aa_eq":aa, "base":"DIEA", "base_eq":aa*2,
        "loading_time_h":1.0, "loading_rate_mmol_g":loading,
        "work_item_id":"WI-PERSIST", "run_id":"RUN-PERSIST",
    }, status="verified")
experimental_workflow.add_cleavage_record(g, {
    "product":"Pep-Persist", "sequence":"EEMQRR", "scale_mmol":0.1,
    "tfa_ml":2.85, "water_ml":0.15, "cleavage_eq":30.0,
    "cleavage_time_h":2.0, "work_item_id":"WI-PERSIST", "run_id":"RUN-PERSIST",
}, status="verified")
'''
    reader = r'''
from pathlib import Path
from types import SimpleNamespace
import json, sys
from spps_v4_gui import experimental_workflow

db = Path(sys.argv[1])
g = SimpleNamespace(experimental_db_path=db, pm_items=[])
loading = experimental_workflow.loading_records(g, statuses=["verified"])
cleavage = experimental_workflow.cleavage_records(g, statuses=["verified"])
ladv = experimental_workflow.advise_loading(
    g, resin="2-CTC", amino_acid="Fmoc-Ala-OH", aa_eq=1.5,
    base_eq=3.0, loading_time_h=1.0, target_loading_mmol_g=0.70,
    include_parsed=False,
)
cadv = experimental_workflow.advise_cleavage(
    g, product="Pep-Persist", sequence="EEMQRR", resin="2-CTC",
    scale_mmol=0.1, include_parsed=False,
)
print(json.dumps({
    "loading_count":len(loading), "cleavage_count":len(cleavage),
    "loading_apply":bool((ladv.get("target_recommendation") or {}).get("apply_allowed")),
    "cleavage_source":str((cadv.get("recommended_condition") or {}).get("condition_source") or ""),
}))
'''

    subprocess.run([sys.executable, "-c", writer, str(db)], cwd=root, env=env, check=True, timeout=30)
    completed = subprocess.run(
        [sys.executable, "-c", reader, str(db)], cwd=root, env=env,
        check=True, timeout=30, capture_output=True, text=True,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    assert payload == {
        "loading_count": 2,
        "cleavage_count": 1,
        "loading_apply": True,
        "cleavage_source": "exact_lab_record",
    }


def test_integrity_critical_paths_use_initialized_database():
    source = Path(experimental_workflow.__file__).read_text(encoding="utf-8")
    assert "def _ready_db" in source
    for expected in (
        'list_records("loading", _ready_db(gui)',
        'list_records("cleavage", _ready_db(gui)',
        'add_record("loading", _attach_run_context(gui, values), _ready_db(gui)',
        'add_record("cleavage", _attach_run_context(gui, values), _ready_db(gui)',
        'loading_recommendation.advise(db_path=_ready_db(gui)',
        'cleavage_recommendation.advise(db_path=_ready_db(gui)',
    ):
        assert expected in source
