"""Controller workflows for rule and real-model risk review."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pandas as pd

from spps_v4_gui import data_system, ml_dataset, ml_workflow, risk_assessment, state_persistence
from spps_v4_gui.modules import plan_workflow


CLASSIFIER_TARGETS = ("failure_flag", "doubling_required")


def _item(gui: Any) -> dict[str, Any]:
    return ml_workflow._active_item_ref(gui)


def _model_signal(gui: Any, target: str, item: dict[str, Any]) -> dict[str, Any]:
    task = ml_dataset.TARGET_TASKS[target]
    path = ml_workflow._models_dir(gui) / f"{target}_{task}.joblib"
    metadata_path = path.with_suffix(".metadata.json")
    if not path.is_file() or not metadata_path.is_file():
        return {"target": target, "available": False, "status": "No trained reviewed-data model."}
    try:
        metadata = state_persistence.read_json_object(metadata_path)
        if int(metadata.get("rows", 0) or 0) < ml_workflow.MIN_TRAIN_ROWS:
            raise ValueError("Model metadata has insufficient reviewed rows.")
        from spps_planner.ml import predict_supervised_details
        row = ml_dataset.observation(item)
        detail = predict_supervised_details(path, pd.DataFrame([row]))[0]
        return {
            "target": target, "available": True, "status": "Observed-data model available",
            "prediction": detail["prediction"], "confidence": detail["confidence"],
            "positive_probability": detail["positive_probability"],
            "model_path": str(path), "trained_at": metadata.get("trained_at", ""),
            "dataset_version": metadata.get("dataset_version"),
            "dataset_fingerprint": metadata.get("dataset_fingerprint", ""),
            "training_rows": metadata.get("rows", 0),
        }
    except Exception as exc:
        return {"target": target, "available": False, "status": f"Model unavailable: {exc}"}


def evaluate(gui: Any) -> dict[str, Any]:
    item = _item(gui)
    plan_workflow._save_active(gui, include_outputs=True)
    assessment = risk_assessment.assess(item)
    assessment["ml_signals"] = [_model_signal(gui, target, item) for target in CLASSIFIER_TARGETS]
    assessment["ml_status"] = (
        "Real reviewed-data signals available"
        if any(row["available"] for row in assessment["ml_signals"])
        else "ML unavailable: reviewed data/model insufficient"
    )
    return assessment


def save(gui: Any, assessment: dict[str, Any] | None = None) -> dict[str, Any]:
    item = _item(gui)
    saved = risk_assessment.save_assessment(item, assessment or evaluate(gui))
    data_system.sync_active_run(item)
    try:
        gui.schedule_autosave()
    except Exception:
        pass
    return saved


def acknowledge(gui: Any, finding_id: str, reason: str) -> dict[str, Any]:
    item = _item(gui)
    event = risk_assessment.acknowledge(item, finding_id, reason)
    run = data_system.sync_active_run(item)
    run.setdefault("change_history", []).append({
        "change_id": event["acknowledgement_id"], "timestamp": event["timestamp"],
        "run_id": run["run_id"], "action": "acknowledge", "entity": "risk_finding",
        "before": None, "after": deepcopy(event), "reason": event["reason"],
    })
    try:
        gui.schedule_autosave()
    except Exception:
        pass
    return event


def current(gui: Any) -> dict[str, Any]:
    return deepcopy(risk_assessment.ensure_review(_item(gui)).get("current", {}))


def history(gui: Any) -> dict[str, list[dict[str, Any]]]:
    review = risk_assessment.ensure_review(_item(gui))
    return {"versions": deepcopy(review["versions"]), "acknowledgements": deepcopy(review["acknowledgements"])}


def export_report(gui: Any, path: str | Path) -> Path:
    assessment = current(gui) or save(gui)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in assessment.items() if key not in {"findings", "ml_signals"}}
    with pd.ExcelWriter(destination, engine="openpyxl") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Assessment", index=False)
        pd.DataFrame(assessment.get("findings", [])).to_excel(writer, sheet_name="Findings", index=False)
        pd.DataFrame(assessment.get("ml_signals", [])).to_excel(writer, sheet_name="ML_Signals", index=False)
        pd.DataFrame(history(gui)["acknowledgements"]).to_excel(writer, sheet_name="Acknowledgements", index=False)
    return destination


__all__ = ["acknowledge", "current", "evaluate", "export_report", "history", "save"]
