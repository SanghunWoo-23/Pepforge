"""Runtime contract for the fully composed desktop release."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RouteContract:
    name: str
    allowed_modules: tuple[str, ...]


DIRECT = ("spps_v4_gui.controller",)

ROUTES = (
    RouteContract("_build", DIRECT),
    RouteContract("generate_update_plan", DIRECT),
    RouteContract("apply_change", DIRECT),
    RouteContract("record_plan_correction", DIRECT),
    RouteContract("apply_live_doubling", DIRECT),
    RouteContract("record_step_status", DIRECT),
    RouteContract("record_actual_material", DIRECT),
    RouteContract("revert_last_execution_change", DIRECT),
    RouteContract("synthesis_execution_history", DIRECT),
    RouteContract("ml_ready_execution_history", DIRECT),
    RouteContract("export_outputs", DIRECT),
    RouteContract("pm_on_select", DIRECT),
    RouteContract("open_work_item", DIRECT),
    RouteContract("pm_add_peptide", DIRECT),
    RouteContract("pm_delete_peptide", DIRECT),
    RouteContract("load_project", DIRECT),
    RouteContract("load_autosave_state", DIRECT),
    RouteContract("save_autosave_state", DIRECT),
    RouteContract("schedule_autosave", DIRECT),
    RouteContract("save_project", DIRECT),
    RouteContract("save_project_as", DIRECT),
    RouteContract("list_synthesis_runs", DIRECT),
    RouteContract("create_synthesis_run", DIRECT),
    RouteContract("activate_synthesis_run", DIRECT),
    RouteContract("upsert_hplc_record", DIRECT),
    RouteContract("delete_hplc_record", DIRECT),
    RouteContract("search_hplc_records", DIRECT),
    RouteContract("data_change_history", DIRECT),
    RouteContract("export_data_workbook", DIRECT),
    RouteContract("import_data_workbook", DIRECT),
    RouteContract("import_hplc_table", DIRECT),
    RouteContract("recent_projects", DIRECT),
    RouteContract("restore_custom_db_tab", DIRECT),
    RouteContract("add_custom_material", DIRECT),
    RouteContract("delete_custom_material", DIRECT),
    RouteContract("record_synthesis_result", DIRECT),
    RouteContract("review_ml_observation", DIRECT),
    RouteContract("active_ml_review", DIRECT),
    RouteContract("ml_review_history", DIRECT),
    RouteContract("build_ml_dataset", DIRECT),
    RouteContract("ml_dataset_status", DIRECT),
    RouteContract("refresh_ml_data", DIRECT),
    RouteContract("train_ml_model", DIRECT),
    RouteContract("predict_ml_for_active_item", DIRECT),
    RouteContract("detect_ml_anomalies", DIRECT),
    RouteContract("evaluate_synthesis_risk", DIRECT),
    RouteContract("save_synthesis_risk", DIRECT),
    RouteContract("acknowledge_risk_finding", DIRECT),
    RouteContract("synthesis_risk_history", DIRECT),
    RouteContract("export_synthesis_risk", DIRECT),
)


def active_route_report(gui_cls: type[Any]) -> dict[str, dict[str, Any]]:
    """Describe the final callable bound to every user-facing controller route."""
    report = {}
    for contract in ROUTES:
        function = getattr(gui_cls, contract.name, None)
        report[contract.name] = {
            "callable": callable(function),
            "module": getattr(function, "__module__", ""),
            "name": getattr(function, "__name__", ""),
            "allowed_modules": contract.allowed_modules,
        }
    return report


def validate_release_controller(gui_cls: type[Any]) -> None:
    """Fail fast if a historical late patch becomes an active release route."""
    failures = []
    for route, details in active_route_report(gui_cls).items():
        if not details["callable"]:
            failures.append(f"{route}: missing callable")
        elif details["module"] not in details["allowed_modules"]:
            failures.append(f"{route}: unexpected source {details['module']}")
    if failures:
        raise RuntimeError("Invalid SPPS Planner release composition: " + "; ".join(failures))


__all__ = [
    "ROUTES",
    "RouteContract",
    "active_route_report",
    "validate_release_controller",
]
