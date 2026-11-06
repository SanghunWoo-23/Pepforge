from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from suite_gui import custom_db_workflow, export_workflow, ml_workflow
from suite_gui.controller import SPPSGui


ROOT = Path(__file__).resolve().parents[1]


class _Gui:
    def __init__(self, path: Path):
        self.actual_runs_path = path
        self.custom_materials = {}
        self.pm_items = [{
            "project": "P-001",
            "peptide": "Pep-A",
            "sequence": "G-H-K",
            "scale": "0.2",
            "resin": "Rink Amide AM",
            "loading": "0.8",
            "lot": "LOT-7",
            "chemistry": "DIC/HOBt",
        }]
        self._v229_active_index = 0


def test_custom_database_validates_and_immediately_supplies_lookup_and_options():
    gui = _Gui(Path("unused.csv"))
    record = custom_db_workflow.store_record(
        gui,
        name="Fmoc-AEEA-OH",
        material_class="AA/Chemical",
        mw="325.36",
        density="",
        note="custom linker",
    )
    custom_db_workflow.store_record(
        gui,
        name="My-DMF",
        material_class="Solvent",
        mw="80.0",
        density="0.95",
    )

    assert record["name"] == "Fmoc-AEEA-OH"
    assert custom_db_workflow.lookup(gui, " fmoc aeea oh ") == ("325.36", "")
    assert custom_db_workflow.options_for_column(
        gui, "Unit name", ["Fmoc-Gly-OH"],
    ) == ["Fmoc-Gly-OH", "Fmoc-AEEA-OH"]
    assert custom_db_workflow.options_for_column(
        gui, "Coupling solvent", ["DMF"],
    ) == ["DMF", "My-DMF"]
    with pytest.raises(ValueError, match="MW must be numeric"):
        custom_db_workflow.store_record(
            gui, name="Bad", material_class="Other", mw="not-a-number",
        )


def test_actual_run_log_captures_observed_results_and_doubling_atomically(tmp_path):
    path = tmp_path / "actual_runs.csv"
    gui = _Gui(path)

    row = ml_workflow.append_actual_run(
        gui,
        actual_yield_percent=71.4,
        actual_purity_percent=93.2,
        failure_flag=False,
        doubling_adjustment="7:2",
        issue_note="position 7 doubled",
    )
    saved = pd.read_csv(path)

    assert row["sequence"] == "G-H-K"
    assert len(saved) == 1
    assert saved.loc[0, "actual_yield_percent"] == pytest.approx(71.4)
    assert saved.loc[0, "actual_purity_percent"] == pytest.approx(93.2)
    assert saved.loc[0, "doubling_adjustment"] == "7:2"
    assert saved.loc[0, "issue_note"] == "position 7 doubled"
    assert not path.with_name(path.name + ".tmp").exists()


def test_ml_training_uses_real_csv_and_model_service(monkeypatch, tmp_path):
    path = tmp_path / "actual_runs.csv"
    pd.DataFrame({
        "sequence_length": [3, 4, 5, 6, 7],
        "actual_yield_percent": [80, 77, 74, 70, 68],
    }).to_csv(path, index=False)
    gui = _Gui(path)
    captured = {}

    import spps_planner.ml

    def fake_train(csv_path, target, model_path, task="regression"):
        captured.update({
            "csv_path": Path(csv_path),
            "target": target,
            "model_path": Path(model_path),
            "task": task,
        })
        return {"rows": 5, "target": target, "task": task, "mae": 1.0}

    monkeypatch.setattr(spps_planner.ml, "train_supervised", fake_train)
    metrics = ml_workflow.train(gui, "actual_yield_percent", "regression")

    assert metrics["rows"] == 5
    assert captured["csv_path"] == path
    assert captured["target"] == "actual_yield_percent"
    assert captured["task"] == "regression"
    assert metrics["model_path"].endswith(
        "actual_yield_percent_regression.joblib",
    )


def test_ml_training_refuses_placeholder_model_without_enough_observations(tmp_path):
    path = tmp_path / "actual_runs.csv"
    pd.DataFrame({
        "actual_purity_percent": [91, 92, 93, 94],
    }).to_csv(path, index=False)
    with pytest.raises(ValueError, match="at least 5 actual run rows"):
        ml_workflow.train(
            _Gui(path), "actual_purity_percent", "regression",
        )


def test_export_direct_route_syncs_editor_then_exports_visible_state(monkeypatch):
    events = []

    class Gui:
        def _sync_modifier_to_aa(self):
            events.append("sync")

    monkeypatch.setattr(
        export_workflow.plan_workflow,
        "export_outputs",
        lambda gui, namespace: events.append(("export", gui, namespace)) or "ok",
    )
    gui = Gui()
    assert export_workflow.export(gui) == "ok"
    assert events[0] == "sync"
    assert events[1][0] == "export"


def test_stage_six_controller_routes_are_direct_and_do_not_use_super():
    tree = ast.parse(
        (ROOT / "suite_gui" / "controller.py").read_text(encoding="utf-8"),
    )
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SPPSGui"
    )
    routes = {
        "export_outputs",
        "export_selected_outputs",
        "restore_custom_db_tab",
        "add_custom_material",
        "delete_custom_material",
        "load_custom_material_selection",
        "record_synthesis_result",
        "review_ml_observation",
        "active_ml_review",
        "ml_review_history",
        "build_ml_dataset",
        "ml_dataset_status",
        "refresh_ml_data",
        "train_ml_model",
        "predict_ml_for_active_item",
        "detect_ml_anomalies",
    }
    methods = {
        node.name: ast.unparse(node)
        for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name in routes
    }
    assert set(methods) == routes
    assert all("super()" not in source for source in methods.values())


def test_stage_six_controller_aliases_reach_direct_services(monkeypatch):
    gui = object.__new__(SPPSGui)
    calls = []
    monkeypatch.setattr(
        custom_db_workflow,
        "add_or_update",
        lambda actual: calls.append(("custom", actual)),
    )
    monkeypatch.setattr(
        ml_workflow,
        "append_actual_run",
        lambda actual, **values: calls.append(("ml", actual, values)),
    )
    monkeypatch.setattr(
        export_workflow,
        "export",
        lambda actual, *args, **kwargs: calls.append(("export", actual)),
    )

    gui.add_custom_material()
    gui.record_synthesis_result(actual_yield_percent=80)
    gui.export_outputs()
    assert [call[0] for call in calls] == ["custom", "ml", "export"]
