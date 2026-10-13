"""Controller-facing V6 experimental-data workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from copy import deepcopy
import json
from datetime import datetime, timezone

from suite_gui import experimental_data
from suite_gui.recommendation import loading as loading_recommendation
from suite_gui.recommendation import cleavage as cleavage_recommendation
from suite_gui.recommendation import coupling as coupling_recommendation
from suite_gui.recommendation import models as recommendation_models
from suite_gui.recommendation.provenance import attach_evidence_trace

_SEEDED_DB_PATHS: set[str] = set()


def db_path(gui: Any = None) -> Path:
    override = getattr(gui, "experimental_db_path", None) if gui is not None else None
    return Path(override) if override else experimental_data.default_db_path()


def _set_gui_diagnostic(gui: Any, name: str, value: Any) -> None:
    if gui is None:
        return
    try:
        setattr(gui, name, value)
    except Exception:
        return


def initialize(gui: Any = None) -> Path:
    """Open/migrate the one experimental store and import bundled seed safely.

    Seed failures are deliberately *not* cached as success. All controller-facing
    reads/writes call this function so History, Advisors and Add Result cannot drift
    onto different SQLite files.
    """
    requested = db_path(gui)
    path = experimental_data.initialize(requested)
    _set_gui_diagnostic(gui, "experimental_db_path", Path(path))
    _set_gui_diagnostic(gui, "experimental_db_error", "")
    recovery = experimental_data.legacy_recovery_status(path)
    _set_gui_diagnostic(gui, "experimental_db_recovery_warning", recovery.get("last_error", ""))
    try:
        cache_key = str(Path(path).expanduser().resolve())
    except Exception:
        cache_key = str(path)
    if cache_key in _SEEDED_DB_PATHS:
        return path
    from spps_planner.build_profile import BUNDLE_EXPERIMENTAL_SEEDS
    if not BUNDLE_EXPERIMENTAL_SEEDS:
        _SEEDED_DB_PATHS.add(cache_key)
        return path
    root = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    required = (
        root / "loading_history_seed.csv",
        root / "Cleavage_Report_seed.xlsx",
        root / "synthesis_sequence_history_seed.csv",
        root / "cleavage_usage_seed.csv",
    )
    errors: list[str] = []
    for seed in required:
        if not seed.is_file():
            errors.append(f"missing bundled seed: {seed.name}")
            continue
        try:
            experimental_data.import_path(seed, path)
        except Exception as exc:
            errors.append(f"{seed.name}: {exc}")
            try:
                gui._log(f"Bundled experimental seed import warning: {seed}: {exc}\n")
            except Exception:
                pass
    if errors:
        message = "Experimental seed initialization incomplete: " + " | ".join(errors)
        _set_gui_diagnostic(gui, "experimental_db_error", message)
        # Do not mark the DB as seeded. A later read/write will retry. Existing user
        # records remain usable; seed import is additive and idempotent.
        return path
    _SEEDED_DB_PATHS.add(cache_key)
    return path


def _ready_db(gui: Any = None) -> Path:
    return initialize(gui)


def data_store_status(gui: Any = None) -> dict[str, Any]:
    """Return operator-visible diagnostics for the actual experimental store."""
    path = _ready_db(gui)
    from spps_planner.build_profile import BUILD_FLAVOR, BUNDLE_EXPERIMENTAL_SEEDS
    counts = experimental_data.record_counts(path)
    legacy = [str(p) for p in experimental_data.legacy_db_candidates(path) if p.is_file()]
    recovery = experimental_data.legacy_recovery_status(path)
    return {
        "build_flavor": BUILD_FLAVOR,
        "path": str(path),
        "exists": Path(path).is_file(),
        "seed_enabled": bool(BUNDLE_EXPERIMENTAL_SEEDS),
        "seed_complete": not bool(getattr(gui, "experimental_db_error", "") if gui is not None else ""),
        "error": str(getattr(gui, "experimental_db_error", "") or "") if gui is not None else "",
        "counts": counts,
        "legacy_candidates_found": legacy,
        "last_recovery": recovery.get("last_recovery", ""),
        "last_recovery_error": recovery.get("last_error", ""),
        "last_backup": recovery.get("last_backup", ""),
    }

def backup_data_store(gui: Any = None) -> Path:
    """Create an explicit operator-requested backup of the active SQLite store."""
    path = _ready_db(gui)
    backup = experimental_data.backup_database(path, reason="manual")
    _set_gui_diagnostic(gui, "experimental_db_last_manual_backup", str(backup))
    return backup

def data_health(gui: Any) -> dict[str, Any]:
    return experimental_data.data_health(_ready_db(gui))

def analytics(gui: Any) -> dict[str, Any]:
    return experimental_data.v6_analytics(_ready_db(gui))

def compare_conditions(gui: Any, scenario_a: dict[str, Any], scenario_b: dict[str, Any]) -> dict[str, Any]:
    from suite_gui.decision_support import compare_scenarios
    return compare_scenarios(scenario_a, scenario_b)


def preview_import(gui: Any, path: str | Path) -> dict[str, Any]:
    return experimental_data.preview_path(path)


def import_file(gui: Any, path: str | Path) -> list[dict[str, Any]]:
    result = experimental_data.import_path(path, _ready_db(gui))
    try:
        gui._log(f"Experimental data import: {path} -> {result}\n")
    except Exception as exc:
        _ignored_log_error = exc
    return result


def loading_records(gui: Any, statuses=None):
    return experimental_data.list_records("loading", _ready_db(gui), statuses=statuses)


def cleavage_records(gui: Any, statuses=None):
    return experimental_data.list_records("cleavage", _ready_db(gui), statuses=statuses)


def sequence_records(gui: Any, statuses=None):
    return experimental_data.list_records("sequence", _ready_db(gui), statuses=statuses)

def cleavage_usage_records(gui: Any, statuses=None):
    return experimental_data.list_records("cleavage_usage", _ready_db(gui), statuses=statuses)

def outcome_records(gui: Any, statuses=None):
    return experimental_data.list_records("outcome", _ready_db(gui), statuses=statuses)

def issue_records(gui: Any, statuses=None):
    return experimental_data.list_records("issue", _ready_db(gui), statuses=statuses)

def review_cleavage_usage_units(gui: Any, record_id: str, units: dict[str,str]):
    return experimental_data.review_cleavage_usage_units(record_id, units, _ready_db(gui))

def validation_snapshot(gui: Any):
    return loading_recommendation.validation_snapshot(_ready_db(gui))

def similar_experiments(gui: Any, sequence: str, limit: int = 12):
    return loading_recommendation.similar_experiments(sequence, db_path=_ready_db(gui), limit=limit)

def sequence_difficulty(gui: Any, sequence: str):
    return loading_recommendation.sequence_difficulty_map(sequence)

def loading_model_info(gui: Any = None):
    return recommendation_models.loading_model_info()

def loading_rebuild_status(gui: Any = None):
    return recommendation_models.loading_rebuild_status(_ready_db(gui))

def rebuild_loading_model(gui: Any = None):
    return recommendation_models.rebuild_loading_model(_ready_db(gui))

def stage_risks(gui: Any, sequence: str):
    try:
        from suite_gui.modules import gui_common
        gui_common.save_active(gui)
        items=list(getattr(gui, "pm_items", []) or [])
        idx=gui_common.active_index(gui)
        item=items[int(idx)] if idx is not None and 0 <= int(idx) < len(items) else {}
    except Exception:
        item={}
    return loading_recommendation.stage_risk_advisor(
        sequence=sequence, product=str(item.get("peptide") or getattr(getattr(gui,"pm_peptide",None),"get",lambda:"")()),
        resin=str(item.get("resin") or getattr(getattr(gui,"pm_resin",None),"get",lambda:"")()),
        scale_mmol=item.get("scale") or getattr(getattr(gui,"pm_scale",None),"get",lambda:"")(),
        selected_plan_rows=item.get("selected_plan_rows") or [], db_path=_ready_db(gui),
    )

def loading_model_history(gui: Any = None):
    return recommendation_models.loading_model_history()

def promote_latest_loading_candidate(gui: Any = None):
    return recommendation_models.promote_latest_loading_candidate()


def rollback_loading_model(gui: Any = None):
    return recommendation_models.rollback_loading_model()



def _active_item_and_run(gui: Any, *, save_editor: bool = True):
    """Return the selected Work Item and active Run.

    ``save_editor=False`` is used by transactional operations that must capture
    the exact pre-call project state before any editor-default normalization can
    mutate the Work Item.
    """
    from suite_gui import data_system
    from suite_gui.modules import gui_common
    if save_editor:
        gui_common.save_active(gui)
    items = list(getattr(gui, "pm_items", []) or [])
    idx = gui_common.active_index(gui)
    if idx is None or not (0 <= int(idx) < len(items)):
        return None, None
    item = items[int(idx)]
    run = data_system.sync_active_run(item)
    return item, run


def active_run_context(gui: Any) -> dict[str, str]:
    """Return traceable active Work Item/Run identity and lifecycle state."""
    try:
        item, run = _active_item_and_run(gui)
        if item is None or run is None:
            return {"work_item_id":"", "run_id":"", "run_name":"", "repeat_of_run_id":"", "status":"", "started_at":"", "completed_at":""}
        return {
            "work_item_id": str(item.get("work_item_id") or ""),
            "run_id": str(run.get("run_id") or ""),
            "run_name": str(run.get("name") or ""),
            "repeat_of_run_id": str(run.get("repeat_of_run_id") or ""),
            "status": str(run.get("status") or ""),
            "started_at": str(run.get("started_at") or ""),
            "completed_at": str(run.get("completed_at") or ""),
        }
    except Exception:
        return {"work_item_id":"", "run_id":"", "run_name":"", "repeat_of_run_id":"", "status":"", "started_at":"", "completed_at":""}


def _current_planner_snapshot(gui: Any, item: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Capture the current saved Planner state without consulting the frozen snapshot."""
    def val(name: str, fallback: Any = ""):
        raw = item.get(name, fallback)
        if raw not in (None, ""):
            return raw
        widget = getattr(gui, name, None)
        try:
            return widget.get()
        except Exception:
            return fallback
    return {
        "snapshot_version": "6.0.0",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work_item_id": str(item.get("work_item_id") or ""),
        "run_id": str(run.get("run_id") or ""),
        "product": item.get("peptide") or val("pm_peptide"),
        "sequence": item.get("sequence") or val("pm_sequence"),
        "scale_mmol": item.get("scale") or val("pm_scale"),
        "resin": item.get("resin") or val("pm_resin"),
        "loading_target_mmol_g": item.get("loading") or val("pm_loading"),
        "loading_aa_eq": item.get("loading_aa_eq") or val("loading_aa_eq"),
        "loading_base_eq": item.get("loading_diea_eq") or val("loading_diea_eq"),
        "loading_time_h": item.get("loading_time_h") or val("loading_time_h"),
        "cleavage_eq": item.get("cleavage_eq_override") or val("cleavage_eq_override"),
        "cleavage_time_h": item.get("cleavage_time_h") or val("cleavage_time_h"),
        "post_cleavage_rescue": item.get("post_cleavage_rescue") or val("post_cleavage_rescue"),
        "selected_plan_rows": deepcopy(item.get("selected_plan_rows") or []),
        "selected_cleavage_rows": deepcopy(item.get("selected_cleavage_rows") or []),
    }


def planner_snapshot(gui: Any) -> dict[str, Any]:
    """Return the immutable start snapshot when a Run has started, else current Planner state."""
    try:
        item, run = _active_item_and_run(gui)
        if item is None or run is None:
            return {}
        frozen = run.get("planner_snapshot_v6")
        if str(run.get("started_at") or "").strip() and isinstance(frozen, dict) and frozen:
            return deepcopy(frozen)
        return _current_planner_snapshot(gui, item, run)
    except Exception:
        return {}


def actual_condition_snapshot(gui: Any) -> dict[str, Any]:
    """Summarize explicit execution deviations and Planner edits since the frozen start.

    Planner edits are reported separately from actual execution deviations so a UI
    edit is never silently promoted to an experimentally performed condition.
    """
    try:
        from suite_gui import synthesis_execution
        item, run = _active_item_and_run(gui)
        if item is None or run is None:
            return {}
        events = synthesis_execution.events(item)
        deviations = [
            {k: event.get(k) for k in ("timestamp","event_type","step_no","unit","field","before","after","reason","operator_note")}
            for event in events
            if str(event.get("event_type") or "") in {"plan_correction", "doubling", "actual_material"}
        ]
        frozen = deepcopy(run.get("planner_snapshot_v6") or {})
        current = _current_planner_snapshot(gui, item, run)
        comparable = (
            "product", "sequence", "scale_mmol", "resin", "loading_target_mmol_g",
            "loading_aa_eq", "loading_base_eq", "loading_time_h", "cleavage_eq",
            "cleavage_time_h", "post_cleavage_rescue", "selected_plan_rows", "selected_cleavage_rows",
        )
        planner_changes = []
        if frozen:
            for key in comparable:
                if frozen.get(key) != current.get(key):
                    planner_changes.append({"field": key, "frozen": deepcopy(frozen.get(key)), "current": deepcopy(current.get(key))})
        result = {
            "deviations": deviations,
            "deviation_count": len(deviations),
            "planner_changes_since_start": planner_changes,
            "planner_change_count": len(planner_changes),
        }
        return result if deviations or planner_changes else {}
    except Exception:
        return {}


def _attach_run_context(gui: Any, values: dict[str, Any]) -> dict[str, Any]:
    payload=dict(values)
    context=active_run_context(gui)
    if not str(payload.get("work_item_id") or context.get("work_item_id") or "").strip() or not str(payload.get("run_id") or context.get("run_id") or "").strip():
        raise ValueError("Select a peptide Work Item with an active Run before recording a Result or Issue. This prevents orphan experimental evidence.")
    if not str(payload.get("work_item_id") or "").strip():
        payload["work_item_id"]=context.get("work_item_id", "")
    if not str(payload.get("run_id") or "").strip():
        payload["run_id"]=context.get("run_id", "")
    # Result/Issue writers may accept only a subset of these fields; the DB layer
    # filters them safely. New V6-capable records retain both planned and actual context.
    if not str(payload.get("planner_snapshot_json") or "").strip():
        payload["planner_snapshot_json"]=json.dumps(planner_snapshot(gui), ensure_ascii=False, default=str)
    if not str(payload.get("actual_condition_json") or "").strip():
        payload["actual_condition_json"]=json.dumps(actual_condition_snapshot(gui), ensure_ascii=False, default=str)
    return payload


def preflight_check(gui: Any) -> dict[str, Any]:
    """Run read-only validation against the current Planner condition."""
    from suite_gui.preflight import check_snapshot
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        return {"schema_version":"6.0.0", "ready":False, "requires_review":False, "block_count":1, "review_count":0,
                "checks":[{"code":"RUN", "status":"BLOCK", "label":"Active Run", "detail":"Select a peptide Work Item first."}]}
    return check_snapshot(_current_planner_snapshot(gui, item, run))


def finish_review(gui: Any) -> dict[str, Any]:
    """Summarize frozen-vs-actual context before a Run is marked complete."""
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a peptide Work Item before reviewing Finish.")
    if not str(run.get("started_at") or "").strip():
        raise ValueError("Start the active Run before reviewing Finish.")
    actual = actual_condition_snapshot(gui)
    summary = execution_summary(gui)
    planner_changes = list(actual.get("planner_changes_since_start") or [])
    deviations = list(actual.get("deviations") or [])
    warnings = []
    if summary.get("held_steps"):
        warnings.append(f"{summary.get('held_steps')} step(s) are on hold.")
    if summary.get("failed_steps"):
        warnings.append(f"{summary.get('failed_steps')} step(s) are marked failed.")
    if summary.get("completed_steps",0) < summary.get("total_steps",0):
        warnings.append(f"Execution progress is {summary.get('completed_steps',0)}/{summary.get('total_steps',0)} steps.")
    return {
        "run": active_run_context(gui),
        "planner_changes": planner_changes,
        "execution_deviations": deviations,
        "planner_change_count": len(planner_changes),
        "deviation_count": len(deviations),
        "warnings": warnings,
        "execution": summary,
    }


def repeat_experiment(gui: Any, *, scale_mmol: Any = None, name: str = "") -> dict[str, Any]:
    """Repeat a completed Run atomically without copying measured records."""
    from suite_gui import data_system
    from suite_gui.modules import gui_common

    # Repeat is transactional. Resolve the selected item without saving editor
    # defaults first, then snapshot the exact caller-visible state. This prevents
    # save_active() normalization from leaking into a failed Repeat operation.
    item, source = _active_item_and_run(gui, save_editor=False)
    if item is None or source is None:
        raise ValueError("Select a peptide Work Item before repeating a Run.")
    before_item = deepcopy(item)
    frozen = deepcopy(source.get("planner_snapshot_v6") or _current_planner_snapshot(gui, item, source))
    source_id = str(source.get("run_id") or "")
    chosen_scale = scale_mmol if scale_mmol not in (None, "") else frozen.get("scale_mmol")
    try:
        scale_number = float(str(chosen_scale).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Repeat Run scale must be numeric and > 0 mmol.") from exc
    if scale_number <= 0:
        raise ValueError("Repeat Run scale must be numeric and > 0 mmol.")

    # The repeat operation is one user action. If regeneration fails, restore the
    # entire Work Item so no half-created Run or normalization residue remains.
    run = None
    try:
        run = data_system.repeat_active_run(item, name=name)
        values = {
            "pm_peptide": frozen.get("product"), "pm_sequence": frozen.get("sequence"),
            "pm_scale": str(chosen_scale),
            "pm_resin": frozen.get("resin"), "pm_loading": frozen.get("loading_target_mmol_g"),
            "loading_aa_eq": frozen.get("loading_aa_eq"), "loading_diea_eq": frozen.get("loading_base_eq"),
            "loading_time_h": frozen.get("loading_time_h"), "cleavage_eq_override": frozen.get("cleavage_eq"),
            "cleavage_time_h": frozen.get("cleavage_time_h"), "post_cleavage_rescue": frozen.get("post_cleavage_rescue"),
        }
        for attr, value in values.items():
            var = getattr(gui, attr, None)
            if value not in (None, "") and hasattr(var, "set"):
                var.set(str(value))
        gui_common.save_active(gui)
        generator = getattr(gui, "generate_update_plan", None)
        if callable(generator):
            generated = generator()
            if generated is None:
                raise RuntimeError("Planner regeneration did not complete for the Repeat Run.")
            gui_common.save_active(gui)
            data_system.sync_active_run(item)
    except Exception:
        item.clear()
        item.update(before_item)
        try:
            idx = gui_common.active_index(gui)
            if idx is not None:
                gui_common.load_item_to_editor(gui, int(idx))
        except Exception as restore_exc:
            from suite_gui.error_policy import log_nonfatal
            log_nonfatal(gui, "Restore editor after failed Repeat Run", restore_exc)
        raise
    return {"source_run_id": source_id, "run_id": run.get("run_id","") if run else "", "run_name": run.get("name","") if run else "", "status": run.get("status","") if run else ""}


def export_run_package(gui: Any, output_zip: str | Path) -> Path:
    """Export one traceable Run package as a ZIP of XLSX/JSON records."""
    from suite_gui import run_package
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a peptide Work Item before exporting a Run package.")
    payload = run_export_payload(gui, detailed=True)
    snapshots = dict(run.get("start_snapshots_v6") or run.get("snapshots") or {})
    return run_package.build_package(
        payload, output_zip,
        materials=deepcopy(snapshots.get("selected_material_rows") or item.get("selected_material_rows") or []),
        checklist=deepcopy(snapshots.get("selected_checklist_rows") or item.get("selected_checklist_rows") or []),
    )


def start_experiment(gui: Any) -> dict[str, Any]:
    """Start the active Run and freeze its Planner snapshot exactly once."""
    from suite_gui import data_system
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a peptide Work Item before starting an experiment.")
    was_started = bool(str(run.get("started_at") or "").strip())
    snapshot = _current_planner_snapshot(gui, item, run)
    if not was_started:
        from suite_gui.preflight import check_snapshot, format_report
        report = check_snapshot(snapshot)
        if not report.get("ready"):
            raise ValueError("Preflight failed. Resolve blocking items before Start Experiment.\n\n" + format_report(report))
    run = data_system.start_active_run(item, snapshot)
    try:
        from suite_gui.modules import gui_common
        gui_common.save_active(gui)
    except Exception as exc:
        from suite_gui.error_policy import log_nonfatal
        log_nonfatal(gui, "Save active item after Start Experiment", exc)
    return {
        "work_item_id": item.get("work_item_id", ""),
        "run_id": run.get("run_id", ""),
        "status": run.get("status", ""),
        "started_at": run.get("started_at", ""),
        "already_started": was_started,
        "planner_snapshot_frozen": True,
    }


def finish_experiment(gui: Any, *, status: str = "Completed") -> dict[str, Any]:
    """Finish the active Run without changing its frozen start snapshot."""
    from suite_gui import data_system
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a peptide Work Item before finishing an experiment.")
    was_finished = bool(str(run.get("completed_at") or "").strip())
    run = data_system.finish_active_run(item, status=status)
    try:
        from suite_gui.modules import gui_common
        gui_common.save_active(gui)
    except Exception as exc:
        from suite_gui.error_policy import log_nonfatal
        log_nonfatal(gui, "Save active item after Finish Experiment", exc)
    return {
        "work_item_id": item.get("work_item_id", ""),
        "run_id": run.get("run_id", ""),
        "status": run.get("status", ""),
        "started_at": run.get("started_at", ""),
        "completed_at": run.get("completed_at", ""),
        "already_finished": was_finished,
    }


def run_export_payload(gui: Any, *, detailed: bool = False) -> dict[str, Any]:
    """Build a truthful simple/detailed Run export payload from one frozen Run."""
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a peptide Work Item before exporting a Run summary.")
    execution = execution_summary(gui)
    actual = actual_condition_snapshot(gui)
    payload = {
        "schema_version": "6.0.0",
        "format": "detailed" if detailed else "simple",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": active_run_context(gui),
        "execution": {
            key: deepcopy(execution.get(key))
            for key in ("total_steps", "completed_steps", "progress_percent", "held_steps", "failed_steps", "resume_step", "event_count")
        },
    }
    if detailed:
        payload["planner_snapshot_frozen"] = deepcopy(run.get("planner_snapshot_v6") or planner_snapshot(gui))
        payload["actual_condition"] = actual
        payload["execution"] = execution
        run_id = str(run.get("run_id") or "")
        try:
            loading = [r for r in loading_records(gui) if str(r.get("run_id") or "") == run_id]
            cleavage = [r for r in cleavage_records(gui) if str(r.get("run_id") or "") == run_id]
            outcomes = [r for r in outcome_records(gui) if str(r.get("run_id") or "") == run_id]
            issues = [r for r in issue_records(gui) if str(r.get("run_id") or "") == run_id]
            analytical = [r for r in run.get("analytical_records", []) if not r.get("deleted")]
            traces = experimental_data.list_recommendation_traces(_ready_db(gui), run_id=run_id)
        except Exception:
            loading, cleavage, outcomes, issues, analytical, traces = [], [], [], [], [], []
        payload["linked_records"] = {
            "loading": [
                {k: deepcopy(r.get(k)) for k in ("record_id","date","resin_type","amino_acid_normalized","aa_eq","base_eq","loading_time_h","loading_rate_mmol_g","record_state","status","created_at")}
                for r in loading
            ],
            "cleavage": [
                {k: deepcopy(r.get(k)) for k in ("record_id","product","scale_mmol","cleavage_eq","cleavage_time_h","tfa_ml","tis_ml","water_ml","record_state","status","created_at")}
                for r in cleavage
            ],
            "outcomes": [
                {k: deepcopy(r.get(k)) for k in ("record_id","stage","result","success_flag","yield_percent","purity_percent","crude_weight_g","record_state","status","created_at")}
                for r in outcomes
            ],
            "issues": [
                {k: deepcopy(r.get(k)) for k in ("record_id","stage","issue_type","severity","observation","action_taken","resolution","record_state","status","created_at")}
                for r in issues
            ],
            "analytical": [deepcopy(dict(r)) for r in analytical],
            "recommendation_traces": [deepcopy(dict(r)) for r in traces],
        }
    return payload


def execution_summary(gui: Any) -> dict[str, Any]:
    from suite_gui.modules import gui_common
    from suite_gui.decision_support import execution_summary as summarize
    gui_common.save_active(gui)
    items=list(getattr(gui, "pm_items", []) or []); idx=gui_common.active_index(gui)
    if idx is None or not (0 <= int(idx) < len(items)): return summarize({})
    return summarize(items[int(idx)])


def run_ui_state(gui: Any) -> dict[str, Any]:
    """Return one normalized operator-facing Run lifecycle/progress state.

    This helper is intentionally read-only. It lets multiple windows expose the same
    Start/Finish/New-Run affordances without duplicating lifecycle rules.
    """
    context = active_run_context(gui)
    summary = execution_summary(gui)
    status = str(context.get("status") or "").strip()
    started = bool(str(context.get("started_at") or "").strip())
    finished = bool(str(context.get("completed_at") or "").strip()) or status.lower() in {
        "completed", "failed", "excluded", "closed"
    }
    has_run = bool(str(context.get("run_id") or "").strip())
    return {
        **context,
        "has_run": has_run,
        "started": started,
        "finished": finished,
        "can_start": bool(has_run and not started and not finished),
        "can_finish": bool(has_run and started and not finished),
        "can_create_new_run": bool(has_run and not (started and not finished)),
        "can_repeat": bool(has_run and finished),
        "can_export_package": bool(has_run),
        "can_record_result": bool(has_run and started),
        "can_record_issue": bool(has_run and started),
        "progress_percent": summary.get("progress_percent", 0),
        "completed_steps": summary.get("completed_steps", 0),
        "total_steps": summary.get("total_steps", 0),
        "resume_step": summary.get("resume_step", "N/A"),
        "held_steps": summary.get("held_steps", 0),
        "failed_steps": summary.get("failed_steps", 0),
    }


def recommendation_traces(gui: Any, run_id: str = "") -> list[dict[str, Any]]:
    path = _ready_db(gui)
    if not run_id:
        run_id = str(active_run_context(gui).get("run_id") or "")
    return experimental_data.list_recommendation_traces(path, run_id=run_id)


def link_recommendation_results(gui: Any, trace_id: str, result_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return experimental_data.link_recommendation_results(trace_id, result_ids, _ready_db(gui))


def _run_metric_from_outcomes(rows: list[dict[str, Any]], run_id: str, field: str) -> float | None:
    for row in reversed(rows):
        if str(row.get("run_id") or "") != str(run_id):
            continue
        value = row.get(field)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def matched_repeat_observation(gui: Any, run_id: str | None = None) -> dict[str, Any]:
    """Return descriptive parent/repeat condition and measured-result deltas.

    The comparison is intentionally non-causal. Outcome records are preferred;
    HPLC purity and reviewed ML outcome fields are used only as transparent
    fallbacks when the canonical outcome field is absent.
    """
    from suite_gui import data_system
    from suite_gui.modules import gui_common
    gui_common.save_active(gui)
    items = list(getattr(gui, "pm_items", []) or [])
    idx = gui_common.active_index(gui)
    if idx is None or not (0 <= int(idx) < len(items)):
        return {"available": False, "reason": "No active Work Item.", "causal_claim_allowed": False}
    item = items[int(idx)]
    base = data_system.matched_repeat_observation(item, run_id=run_id)
    if not base.get("available"):
        return base
    parent_id = str(base.get("parent_run_id") or "")
    repeat_id = str(base.get("repeat_run_id") or "")
    outcomes = outcome_records(gui)
    parent = next((r for r in item.get("runs", []) if str(r.get("run_id")) == parent_id), {})
    repeat = next((r for r in item.get("runs", []) if str(r.get("run_id")) == repeat_id), {})

    def metric(run: dict[str, Any], rid: str, field: str) -> tuple[float | None, str]:
        outcome_field = "yield_percent" if field == "yield" else "purity_percent"
        value = _run_metric_from_outcomes(outcomes, rid, outcome_field)
        if value is not None:
            return value, "experimental outcome"
        review = dict((run.get("ml_review") or {}).get("current") or {})
        review_field = "actual_yield_percent" if field == "yield" else "actual_purity_percent"
        try:
            if review.get(review_field) not in (None, ""):
                return float(review[review_field]), "reviewed outcome"
        except (TypeError, ValueError):
            pass
        if field == "purity":
            for record in reversed(list(run.get("hplc_records") or [])):
                if record.get("deleted"):
                    continue
                try:
                    if record.get("purity_percent") not in (None, ""):
                        return float(record["purity_percent"]), "HPLC purity"
                except (TypeError, ValueError):
                    continue
        return None, ""

    result: dict[str, Any] = dict(base)
    parent_metrics: dict[str, Any] = {}
    repeat_metrics: dict[str, Any] = {}
    deltas: dict[str, Any] = {}
    for field in ("yield", "purity"):
        pval, psrc = metric(parent, parent_id, field)
        rval, rsrc = metric(repeat, repeat_id, field)
        parent_metrics[field + "_percent"] = pval
        parent_metrics[field + "_source"] = psrc
        repeat_metrics[field + "_percent"] = rval
        repeat_metrics[field + "_source"] = rsrc
        deltas[field + "_percentage_points"] = (rval - pval) if pval is not None and rval is not None else None
    result.update({
        "parent_metrics": parent_metrics,
        "repeat_metrics": repeat_metrics,
        "outcome_deltas": deltas,
    })
    return result


def frozen_run_theoretical_mass(gui: Any) -> dict[str, Any]:
    """Calculate expected product mass only from the frozen Run plan snapshot."""
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        raise ValueError("Select a Work Item and Run first.")
    frozen = dict(run.get("planner_snapshot_v6") or {})
    sequence = str(frozen.get("sequence") or "").strip()
    resin = str(frozen.get("resin") or "").strip()
    if not sequence or not resin:
        raise ValueError("The frozen Run snapshot does not contain sequence/resin identity.")
    from spps_planner.engine import PlanInput, plan_summary
    def number(name: str, default: float) -> float:
        try:
            return float(frozen.get(name) if frozen.get(name) not in (None, "") else default)
        except (TypeError, ValueError):
            return default
    summary = plan_summary(PlanInput(
        sequence=sequence, resin=resin,
        scale_mmol=number("scale_mmol", 0.1),
        resin_loading_mmol_g=number("loading_target_mmol_g", 0.8),
    ))
    return {
        "run_id": str(run.get("run_id") or ""),
        "source": "frozen Run Planner snapshot",
        "product_mw": summary.get("product_mw"),
        "mh": summary.get("mh"),
        "mna": summary.get("mna"),
    }


def analytical_completeness(gui: Any) -> dict[str, Any]:
    """Report completeness only; never auto-approve scientific identity."""
    item, run = _active_item_and_run(gui)
    if item is None or run is None:
        return {"complete": False, "items": {}, "unresolved": ["No active Run"]}
    hplc = [r for r in run.get("hplc_records", []) if not r.get("deleted")]
    analytical = [r for r in run.get("analytical_records", []) if not r.get("deleted")]
    rid = str(run.get("run_id") or "")
    outcomes = [r for r in outcome_records(gui) if str(r.get("run_id") or "") == rid]
    hplc_recorded = bool(hplc)
    ms_identity_recorded = any(str(r.get("analytical_type") or "").upper() in {"LC-MS", "MALDI"} for r in analytical)
    yield_recorded = any(r.get("yield_percent") not in (None, "") for r in outcomes)
    if not yield_recorded:
        review = dict((run.get("ml_review") or {}).get("current") or {})
        yield_recorded = review.get("actual_yield_percent") not in (None, "")
    unresolved = []
    if not hplc_recorded: unresolved.append("HPLC result not recorded")
    if not ms_identity_recorded: unresolved.append("MS identity not recorded")
    if not yield_recorded: unresolved.append("Yield not recorded")
    return {
        "complete": not unresolved,
        "items": {"hplc": hplc_recorded, "ms_identity": ms_identity_recorded, "yield": yield_recorded},
        "unresolved": unresolved,
        "note": "Completeness only; no automatic scientific pass/fail is inferred.",
    }

def set_status(gui: Any, kind: str, ids, status: str) -> int:
    return experimental_data.set_status(kind, ids, status, _ready_db(gui))

def update_record(gui: Any, kind: str, record_id: str, changes: dict[str, Any]):
    return experimental_data.update_record(kind, record_id, changes, _ready_db(gui))



def _require_saved_record(kind: str, saved: Any, path: Path) -> dict[str, Any]:
    if not isinstance(saved, dict) or not str(saved.get("record_id") or "").strip():
        raise RuntimeError(f"{kind} result was not confirmed by the experimental database.")
    record_id = str(saved["record_id"])
    rows = experimental_data.list_records(kind, path)
    if not any(str(row.get("record_id") or "") == record_id for row in rows):
        raise RuntimeError(f"{kind} result write could not be read back from {path}.")
    return saved


def add_loading_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    path = _ready_db(gui)
    saved = experimental_data.add_record("loading", _attach_run_context(gui, values), path, status=status)
    return _require_saved_record("loading", saved, path)


def add_cleavage_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    path = _ready_db(gui)
    saved = experimental_data.add_record("cleavage", _attach_run_context(gui, values), path, status=status)
    return _require_saved_record("cleavage", saved, path)

def add_outcome_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    path = _ready_db(gui)
    saved = experimental_data.add_outcome(_attach_run_context(gui, values), path, status=status)
    if not isinstance(saved, dict) or not str(saved.get("record_id") or "").strip():
        raise RuntimeError("Outcome result was not confirmed by the experimental database.")
    return saved

def add_issue_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    path = _ready_db(gui)
    saved = experimental_data.add_issue(_attach_run_context(gui, values), path, status=status)
    if not isinstance(saved, dict) or not str(saved.get("record_id") or "").strip():
        raise RuntimeError("Issue result was not confirmed by the experimental database.")
    return saved


def record_coupling_review(gui: Any, *, actual_yield_percent: Any = None, actual_purity_percent: Any = None, failure_flag: Any = None, doubling_required: Any = None, operator_note: str = ""):
    """Record a simple operator coupling outcome on the active Work Item."""
    from suite_gui import ml_dataset
    from suite_gui.modules import gui_common
    gui_common.save_active(gui)
    items = list(getattr(gui, "pm_items", []) or [])
    idx = gui_common.active_index(gui)
    if idx is None or not (0 <= int(idx) < len(items)):
        raise ValueError("Select a peptide item before recording a coupling result.")
    item = items[int(idx)]
    item_before_review = deepcopy(item)
    version = ml_dataset.review_item(
        item, actual_yield_percent=actual_yield_percent, actual_purity_percent=actual_purity_percent,
        failure_flag=failure_flag, doubling_required=doubling_required, included=True,
        review_reason="Operator lab result entry", operator_note=operator_note,
    )
    gui_common.save_active(gui)
    def _tri(value):
        text=str(value or '').strip().lower()
        if text in {'yes','y','true','1','fail','failed'}: return 1
        if text in {'no','n','false','0','success','passed'}: return 0
        return None
    try:
        context=active_run_context(gui)
        saved = experimental_data.add_outcome({
            "stage": "coupling", "product": item.get("peptide", ""), "sequence": item.get("sequence", ""),
            "work_item_id": item.get("work_item_id", ""), "run_id": context.get("run_id", ""), "result": "failed" if _tri(failure_flag)==1 else "completed" if _tri(failure_flag)==0 else "recorded",
            "success_flag": (0 if _tri(failure_flag)==1 else 1 if _tri(failure_flag)==0 else None),
            "yield_percent": actual_yield_percent, "purity_percent": actual_purity_percent,
            "doubling_required": _tri(doubling_required), "observation": operator_note,
            "source_locator": "Record Coupling / active Work Item",
        }, _ready_db(gui), status="verified")
        if not isinstance(saved, dict) or not str(saved.get("record_id") or "").strip():
            raise RuntimeError("Coupling outcome was not confirmed by the experimental database.")
    except Exception as exc:
        # Keep the Work Item review and the measured-evidence store transactional:
        # an operator must never see a reviewed coupling result that failed to
        # enter the canonical experimental DB.
        item.clear()
        item.update(deepcopy(item_before_review))
        try:
            gui.pm_items[int(idx)] = item
        except Exception:
            pass
        raise RuntimeError(f"Coupling result was not saved; Work Item review was restored: {exc}") from exc
    return version

def advise_loading(gui: Any, **query: Any):
    return attach_evidence_trace(loading_recommendation.advise(db_path=_ready_db(gui), **query))


def advise_cleavage(gui: Any, **query: Any):
    return attach_evidence_trace(cleavage_recommendation.advise(db_path=_ready_db(gui), **query))


def recommend_loading(gui: Any, **query: Any):
    return attach_evidence_trace(loading_recommendation.recommend(db_path=_ready_db(gui), **query))


def recommend_cleavage(gui: Any, **query: Any):
    return attach_evidence_trace(cleavage_recommendation.recommend(db_path=_ready_db(gui), **query))


def advise_coupling(gui: Any):
    try:
        from suite_gui.modules import gui_common
        gui_common.save_active(gui)
    except Exception as exc:
        try:
            gui._log(f"Coupling advisor save-active warning: {exc}\n")
        except Exception as log_exc:
            _coupling_save_log_error = log_exc
    items = list(getattr(gui, "pm_items", []) or [])
    active = None
    try:
        from suite_gui.modules import gui_common
        idx = gui_common.active_index(gui)
        if idx is not None and 0 <= int(idx) < len(items):
            active = items[int(idx)]
    except Exception as exc:
        active = None
        try:
            gui._log(f"Coupling advisor active-item warning: {exc}\n")
        except Exception as log_exc:
            _coupling_active_log_error = log_exc
    if active is None:
        active = {
            "sequence": getattr(getattr(gui, "pm_sequence", None), "get", lambda: "")(),
            "resin": getattr(getattr(gui, "pm_resin", None), "get", lambda: "")(),
        }
    return attach_evidence_trace(coupling_recommendation.advise(items, active))


def open_window(gui: Any) -> Any:
    from suite_gui.modules.experimental_data_panel import ExperimentalDataWindow
    existing = getattr(gui, "_experimental_data_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.deiconify(); existing.lift(); return existing
        except Exception as exc:
            _ignored_window_probe_error = exc
    window = ExperimentalDataWindow(gui)
    gui._experimental_data_window = window
    return window


def open_advisor(gui: Any, kind: str) -> Any:
    window = open_window(gui)
    try:
        window.focus_advisor(kind)
    except Exception as exc:
        try:
            gui._log(f"Experimental advisor focus warning: {exc}\n")
        except Exception as log_exc:
            _ignored_focus_log_error = log_exc
    return window


def open_condition_optimizer(gui: Any) -> Any:
    window = open_window(gui)
    try:
        window.focus_optimizer()
    except Exception as exc:
        try:
            gui._log(f"Condition optimizer focus warning: {exc}\n")
        except Exception as log_exc:
            _condition_optimizer_log_error = log_exc
    return window

__all__ = ["initialize", "data_store_status", "data_health", "analytics", "compare_conditions", "planner_snapshot", "actual_condition_snapshot", "preflight_check", "finish_review", "repeat_experiment", "export_run_package", "start_experiment", "finish_experiment", "run_export_payload", "execution_summary", "run_ui_state", "preview_import", "import_file", "loading_records", "cleavage_records", "sequence_records", "cleavage_usage_records", "outcome_records", "issue_records", "review_cleavage_usage_units", "validation_snapshot", "similar_experiments", "sequence_difficulty", "stage_risks", "loading_model_info", "loading_rebuild_status", "loading_model_history", "rebuild_loading_model", "promote_latest_loading_candidate", "rollback_loading_model", "active_run_context", "recommendation_traces", "link_recommendation_results", "matched_repeat_observation", "frozen_run_theoretical_mass", "analytical_completeness", "set_status", "update_record", "add_loading_record", "add_cleavage_record", "add_outcome_record", "add_issue_record", "record_coupling_review", "advise_loading", "advise_cleavage", "recommend_loading", "recommend_cleavage", "advise_coupling", "open_window", "open_advisor", "open_condition_optimizer", "db_path"]
