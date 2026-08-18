"""Real synthesis outcomes, reviewed datasets and ML for SPPS Planner V4.0.0."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from spps_v4_gui import ml_dataset, state_persistence
from spps_v4_gui.modules import plan_workflow


MIN_TRAIN_ROWS = 5


def _value(value: Any, default: Any = "") -> Any:
    try:
        result = value.get()
    except Exception:
        result = value
    return default if result is None else result


def _gui_value(gui: Any, name: str, default: Any = "") -> Any:
    return _value(getattr(gui, name, default), default)


def log_path(gui: Any = None) -> Path:
    override = getattr(gui, "actual_runs_path", None) if gui is not None else None
    if override:
        return Path(override)
    try:
        from spps_v4_gui.modules.data_log_panel import _log_path
        return Path(_log_path())
    except Exception:
        return Path.home() / ".spps_planner" / "data" / "actual_runs.csv"


def dataset_dir(gui: Any = None) -> Path:
    override = getattr(gui, "ml_dataset_dir", None) if gui is not None else None
    return Path(override) if override else log_path(gui).parent / "ml_datasets"


def _read(path: Path) -> pd.DataFrame:
    if path.exists() and path.stat().st_size:
        return pd.read_csv(path)
    return pd.DataFrame()


def _atomic_csv(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    temporary.replace(path)
    return path


def _active_item_ref(gui: Any) -> dict[str, Any]:
    items = getattr(gui, "pm_items", []) or []
    try:
        index = int(getattr(gui, "_v229_active_index", -1))
    except Exception as exc:
        raise ValueError("No active Work Item.") from exc
    if not (0 <= index < len(items)):
        raise ValueError("No active Work Item.")
    return items[index]


def _active_item(gui: Any) -> dict[str, Any]:
    try:
        return dict(_active_item_ref(gui))
    except ValueError:
        return {
            "project": _gui_value(gui, "pm_project"),
            "peptide": _gui_value(gui, "pm_peptide"),
            "sequence": _gui_value(gui, "pm_sequence"),
            "scale": _gui_value(gui, "pm_scale"),
            "resin": _gui_value(gui, "pm_resin"),
            "loading": _gui_value(gui, "pm_loading"),
            "lot": _gui_value(gui, "pm_lot"),
            "chemistry": _gui_value(gui, "pm_chemistry"),
        }


def _tree_rows(tree: Any) -> list[dict[str, Any]]:
    if tree is None:
        return []
    try:
        columns = list(tree["columns"])
        return [
            dict(zip(columns, tree.item(item_id, "values")))
            for item_id in tree.get_children()
        ]
    except Exception:
        return []


def _planned_volume(gui: Any, token: str) -> float:
    total = 0.0
    for row in _tree_rows(getattr(gui, "pm_selected_total_tree", None)):
        if token.lower() not in " ".join(str(value) for value in row.values()).lower():
            continue
        for value in row.values():
            text = str(value or "").replace(",", "")
            if "ml" in text.lower():
                try:
                    total += float(text.lower().replace("ml", "").strip())
                except ValueError:
                    pass
    return total


def append_actual_run(
    gui: Any,
    *,
    actual_yield_percent: Any = None,
    actual_purity_percent: Any = None,
    failure_flag: Any = None,
    doubling_adjustment: Any = None,
    issue_note: Any = None,
) -> dict[str, Any]:
    """Keep the accepted CSV log route for imported and historical runs."""
    item = _active_item(gui)
    now = datetime.now()
    events = list((item.get("synthesis_execution") or {}).get("events", []) or [])
    row = {
        "date": now.isoformat(timespec="seconds"),
        "run_id": f"{item.get('lot', item.get('lot_no', ''))}_{now.strftime('%H%M%S')}",
        "work_item_id": item.get("work_item_id", ""),
        "project": item.get("project", item.get("project_name", "")),
        "peptide": item.get("peptide", item.get("peptide_name", "")),
        "sequence": item.get("sequence", ""),
        "sequence_length": len(str(item.get("sequence", "")).replace("-", "").replace(" ", "")),
        "scale_mmol": item.get("scale", item.get("scale_mmol", "")),
        "resin": item.get("resin", ""),
        "loading_mmol_g": item.get("loading", item.get("loading_mmol_g", "")),
        "chemistry": item.get("chemistry", ""),
        "execution_event_count": len(events),
        "planned_dmf_mL": _planned_volume(gui, "dmf"),
        "planned_tfa_mL": _planned_volume(gui, "tfa"),
        "actual_yield_percent": _gui_value(gui, "actual_yield_percent") if actual_yield_percent is None else actual_yield_percent,
        "actual_purity_percent": _gui_value(gui, "actual_purity_percent") if actual_purity_percent is None else actual_purity_percent,
        "failure_flag": _gui_value(gui, "actual_failure_flag", False) if failure_flag is None else failure_flag,
        "doubling_adjustment": _gui_value(gui, "actual_doubling_adjustment") if doubling_adjustment is None else doubling_adjustment,
        "issue_note": _gui_value(gui, "actual_issue_note") if issue_note is None else issue_note,
    }
    path = log_path(gui)
    frame = pd.concat([_read(path), pd.DataFrame([row])], ignore_index=True)
    _atomic_csv(path, frame)
    try:
        gui._log(f"Actual synthesis run appended: {path}\n")
    except Exception:
        pass
    return row


def review_active_item(gui: Any, **review: Any) -> dict[str, Any]:
    version = ml_dataset.review_item(_active_item_ref(gui), **review)
    plan_workflow._save_active(gui, include_outputs=True)
    try:
        gui.schedule_autosave()
    except Exception:
        try:
            gui.save_autosave_state()
        except Exception:
            pass
    return version


def review_history(gui: Any) -> list[dict[str, Any]]:
    return ml_dataset.review_versions(_active_item_ref(gui))


def active_review(gui: Any) -> dict[str, Any]:
    review = ml_dataset.normalize_review(_active_item_ref(gui).get(ml_dataset.REVIEW_KEY))
    return {"revision": review["revision"], **dict(review.get("current", {}))}


def execution_dataset_frame(gui: Any) -> pd.DataFrame:
    return ml_dataset.dataset_frame(getattr(gui, "pm_items", []) or [])


def _manifest_path(gui: Any) -> Path:
    return dataset_dir(gui) / "manifest.json"


def _manifest(gui: Any) -> dict[str, Any]:
    path = _manifest_path(gui)
    if not path.exists():
        return {"schema_version": 1, "current_version": 0, "versions": []}
    data = state_persistence.read_json_object(path)
    return {
        "schema_version": 1,
        "current_version": int(data.get("current_version", 0) or 0),
        "versions": [dict(row) for row in data.get("versions", []) if isinstance(row, Mapping)],
    }


def build_execution_dataset(gui: Any) -> dict[str, Any]:
    """Write a new immutable dataset snapshot only when its content changes."""
    frame = execution_dataset_frame(gui)
    if frame.empty:
        return {
            "version": 0, "rows": 0, "included_rows": 0,
            "fingerprint": "", "path": "", "created": False,
        }
    root = dataset_dir(gui)
    root.mkdir(parents=True, exist_ok=True)
    fingerprint = ml_dataset.dataset_fingerprint(frame)
    manifest = _manifest(gui)
    versions = manifest["versions"]
    latest = versions[-1] if versions else {}
    if latest.get("fingerprint") == fingerprint:
        return {
            "version": int(latest.get("version", 0)),
            "rows": len(frame),
            "included_rows": int(frame.get("included", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
            "fingerprint": fingerprint,
            "path": str(root / str(latest.get("file", ""))),
            "created": False,
        }
    version = int(manifest["current_version"]) + 1
    filename = f"execution_dataset_v{version:04d}.csv"
    snapshot = _atomic_csv(root / filename, frame)
    _atomic_csv(root / "execution_dataset_current.csv", frame)
    entry = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fingerprint": fingerprint,
        "rows": len(frame),
        "included_rows": int(frame["included"].fillna(False).astype(bool).sum()),
        "file": filename,
    }
    manifest["current_version"] = version
    manifest["versions"].append(entry)
    state_persistence.atomic_write_json(_manifest_path(gui), manifest)
    return {**entry, "path": str(snapshot), "created": True}


def dataset_status(gui: Any) -> dict[str, Any]:
    frame = execution_dataset_frame(gui)
    reviewed = frame[frame.get("review_status", "") == "reviewed"] if not frame.empty else frame
    included = reviewed[reviewed.get("included", False).fillna(False).astype(bool)] if not reviewed.empty else reviewed
    targets = {
        target: int(included[target].notna().sum()) if target in included else 0
        for target in ml_dataset.TARGETS
    }
    manifest = _manifest(gui)
    return {
        "rows": len(frame),
        "reviewed_rows": len(reviewed),
        "included_rows": len(included),
        "excluded_rows": max(0, len(reviewed) - len(included)),
        "current_version": manifest["current_version"],
        "target_rows": targets,
    }


def refresh(gui: Any) -> pd.DataFrame:
    frame = execution_dataset_frame(gui)
    tree = getattr(gui, "ml_data_tree", None) or getattr(gui, "data_log_tree", None)
    if tree is not None:
        try:
            from spps_v4_gui.modules.gui_common import write_tree
            write_tree(tree, frame)
        except Exception:
            pass
    combo = getattr(gui, "ml_target_combo", None)
    if combo is not None:
        try:
            combo.configure(values=ml_dataset.TARGETS)
        except Exception:
            pass
    return frame


def _eligible(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    if frame.empty or target not in frame:
        return pd.DataFrame()
    result = frame.copy()
    if "included" in result:
        result = result[result["included"].fillna(False).astype(bool)]
    return result[result[target].notna()]


def _models_dir(gui: Any) -> Path:
    override = getattr(gui, "ml_models_dir", None)
    if override:
        return Path(override)
    try:
        from spps_planner.user_paths import user_models_dir
        return Path(user_models_dir())
    except Exception:
        return log_path(gui).parent / "models"


def train(gui: Any, target: str | None = None, task: str | None = None) -> dict[str, Any]:
    target = str(target or _gui_value(gui, "ml_target", "")).strip()
    if target not in ml_dataset.TARGETS:
        raise ValueError("Choose yield, purity, failure, or doubling target first.")
    expected_task = ml_dataset.TARGET_TASKS[target]
    task = str(expected_task if task is None else task).strip()
    if task in {"", "auto"}:
        task = expected_task
    if task != expected_task:
        raise ValueError(f"{target} requires {expected_task}.")

    frame = execution_dataset_frame(gui)
    eligible = _eligible(frame, target)
    source = "execution_dataset"
    dataset_info: dict[str, Any] = {}
    if len(eligible) >= MIN_TRAIN_ROWS:
        dataset_info = build_execution_dataset(gui)
        training_path = Path(dataset_info["path"])
    else:
        legacy = _read(log_path(gui))
        legacy_eligible = _eligible(legacy, target)
        if len(legacy_eligible) < MIN_TRAIN_ROWS:
            raise ValueError(
                f"Need at least {MIN_TRAIN_ROWS} actual run rows with target values "
                "that are included and reviewed. "
                f"Current valid rows for {target}: {len(eligible)}."
            )
        source = "actual_runs.csv"
        eligible = legacy_eligible
        training_path = log_path(gui)
    if task == "classification" and eligible[target].nunique(dropna=True) < 2:
        raise ValueError(f"{target} needs at least two observed classes before training.")

    from spps_planner.ml import train_supervised
    output = _models_dir(gui)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / f"{target}_{task}.joblib"
    metrics = train_supervised(training_path, target, model_path, task=task)
    metadata = {
        **metrics,
        "model_path": str(model_path),
        "data_source": source,
        "dataset_version": dataset_info.get("version"),
        "dataset_fingerprint": dataset_info.get("fingerprint", ""),
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    state_persistence.atomic_write_json(model_path.with_suffix(".metadata.json"), metadata)
    return metadata


def predict_active(gui: Any, target: str | None = None) -> dict[str, Any]:
    target = str(target or _gui_value(gui, "ml_target", "")).strip()
    if target not in ml_dataset.TARGETS:
        raise ValueError("Choose a supported target first.")
    task = ml_dataset.TARGET_TASKS[target]
    model_path = _models_dir(gui) / f"{target}_{task}.joblib"
    if not model_path.exists():
        raise ValueError(f"No trained model for {target}.")
    from spps_planner.ml import predict_supervised
    row = ml_dataset.observation(_active_item_ref(gui))
    prediction = predict_supervised(model_path, pd.DataFrame([row]))[0]
    return {
        "target": target,
        "task": task,
        "prediction": prediction.item() if hasattr(prediction, "item") else prediction,
        "model_path": str(model_path),
        "work_item_id": row["work_item_id"],
    }


def detect_anomalies(gui: Any) -> pd.DataFrame:
    info = build_execution_dataset(gui)
    path = Path(info["path"]) if info.get("path") else log_path(gui)
    output = dataset_dir(gui) / "execution_dataset_anomaly.csv"
    from spps_planner.ml import detect_anomalies as run
    result = run(path, output)
    result.attrs["output_path"] = str(output)
    return result


__all__ = [
    "MIN_TRAIN_ROWS", "active_review", "append_actual_run",
    "build_execution_dataset", "dataset_dir", "dataset_status",
    "detect_anomalies", "execution_dataset_frame", "log_path",
    "predict_active", "refresh", "review_active_item", "review_history",
    "train",
]
