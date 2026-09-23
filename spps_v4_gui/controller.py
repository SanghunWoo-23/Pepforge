"""Direct SPPS V5.0.0 controller embedded in Pepforge V4.0.0.

Every operator-facing route is a normal class method. The controller composes
an explicit base class and named workflow services; it does not install or
replace class methods at runtime.
"""
from __future__ import annotations

from typing import Any
import tkinter as tk

from peptiforg_core.lazy_imports import lazy_module
from spps_v4_gui.classic_base import ClassicControllerBase
from spps_v4_gui.ui_build import build_ui

chemistry_workflow = lazy_module("spps_v4_gui.chemistry_workflow")
custom_db_workflow = lazy_module("spps_v4_gui.custom_db_workflow")
data_workflow = lazy_module("spps_v4_gui.data_workflow")
export_workflow = lazy_module("spps_v4_gui.export_workflow")
execution_workflow = lazy_module("spps_v4_gui.execution_workflow")
experimental_workflow = lazy_module("spps_v4_gui.experimental_workflow")
ml_workflow = lazy_module("spps_v4_gui.ml_workflow")
persistence_workflow = lazy_module("spps_v4_gui.persistence_workflow")
project_workflow = lazy_module("spps_v4_gui.project_workflow")
risk_workflow = lazy_module("spps_v4_gui.risk_workflow")
synthesis_workflow = lazy_module("spps_v4_gui.synthesis_workflow")
from spps_v4_gui.modules.release_ui import ACTIVE_RESINS


class SPPSGui(ClassicControllerBase):
    """Canonical SPPS Planner V5.0.0 controller with a static method surface."""

    TITLE = "SPPS Planner V5.0.0"
    RESIN_VALUES = list(ACTIVE_RESINS)

    def _build(self) -> Any:
        return build_ui(self)

    def destroy(self) -> Any:
        if getattr(self, "_direct_destroying", False):
            return None
        self._direct_destroying = True
        try:
            try:
                for after_id in list(self.tk.call("after", "info")):
                    try:
                        self.after_cancel(after_id)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                return super().destroy()
            except tk.TclError:
                return None
        finally:
            self._direct_destroying = False

    def generate_update_plan(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.generate(self, *args, **kwargs)

    def pm_generate_selected(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.generate(self, *args, **kwargs)

    def pm_calculate_all(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.generate(self, *args, **kwargs)

    def apply_change(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.apply_change(self, *args, **kwargs)

    def pm_apply_change(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.apply_change(self, *args, **kwargs)

    def apply_plan_mw_density(self, *args: Any, **kwargs: Any) -> Any:
        return synthesis_workflow.apply_change(self, *args, **kwargs)

    def record_plan_correction(self, **change: Any) -> Any:
        return execution_workflow.record_plan_correction(self, **change)

    def apply_live_doubling(self, **change: Any) -> Any:
        return execution_workflow.apply_doubling(self, **change)

    def record_step_status(self, **change: Any) -> Any:
        return execution_workflow.record_step_status(self, **change)

    def record_actual_material(self, **change: Any) -> Any:
        return execution_workflow.record_actual_material(self, **change)

    def revert_last_execution_change(self, **change: Any) -> Any:
        return execution_workflow.revert_last(self, **change)

    def synthesis_execution_history(self) -> Any:
        return execution_workflow.history(self)

    def ml_ready_execution_history(self) -> Any:
        return execution_workflow.ml_ready_history(self)

    def apply_dic_hobt_preset(self) -> Any:
        return chemistry_workflow.apply_dic_hobt(self)

    def apply_hbtu_nmp_preset(self) -> Any:
        return chemistry_workflow.apply_hbtu_nmp(self)

    def export_outputs(self, *args: Any, **kwargs: Any) -> Any:
        return export_workflow.export(self, *args, **kwargs)

    def export_selected_outputs(self, *args: Any, **kwargs: Any) -> Any:
        return export_workflow.export(self, *args, **kwargs)

    def pm_on_select(self, event: Any = None) -> Any:
        return project_workflow.select(self, event)

    def pm_on_double_click(self, event: Any = None) -> Any:
        return project_workflow.open_selected(self, event)

    def open_work_item(self) -> Any:
        return project_workflow.open_selected(self)

    def pm_add_peptide(self, item: Any = None) -> Any:
        return project_workflow.add(self, item)

    def pm_duplicate_peptide(self) -> Any:
        return project_workflow.duplicate(self)

    def pm_delete_peptide(self) -> Any:
        return project_workflow.delete(self)

    def save_project(self, show: bool = True) -> Any:
        return persistence_workflow.save_project(self, show)

    def save_project_as(self, path: Any = None, show: bool = True) -> Any:
        return persistence_workflow.save_project_as(self, path, show)

    def load_project(self, path: Any = None) -> Any:
        return persistence_workflow.load_project(self, path)

    def _collect_state(self) -> Any:
        return persistence_workflow.collect_state(self)

    def save_autosave_state(self) -> Any:
        return persistence_workflow.save_autosave_state(self)

    def schedule_autosave(self) -> Any:
        return persistence_workflow.schedule_autosave(self)

    def load_autosave_state(self) -> Any:
        return persistence_workflow.load_autosave_state(self)

    def list_synthesis_runs(self) -> Any:
        return data_workflow.list_runs(self)

    def create_synthesis_run(self, name: str = "", reason: str = "New synthesis run") -> Any:
        return data_workflow.create_run(self, name, reason)

    def activate_synthesis_run(self, run_id: str, reason: str = "Operator selected run") -> Any:
        return data_workflow.activate_run(self, run_id, reason)

    def upsert_hplc_record(self, values: Any, reason: str) -> Any:
        return data_workflow.upsert_hplc(self, values, reason)

    def delete_hplc_record(self, record_id: str, reason: str) -> Any:
        return data_workflow.delete_hplc(self, record_id, reason)

    def search_hplc_records(self, query: str = "", sort_by: str = "acquired_at", descending: bool = True) -> Any:
        return data_workflow.search_hplc(self, query, sort_by, descending)

    def data_change_history(self) -> Any:
        return data_workflow.change_history(self)

    def export_data_workbook(self, path: Any = None) -> Any:
        return data_workflow.export_workbook(self, path)

    def import_data_workbook(self, path: Any = None, column_mapping: Any = None) -> Any:
        return data_workflow.import_workbook(self, path, column_mapping)

    def import_hplc_table(self, path: Any = None, column_mapping: Any = None, reason: str = "Imported HPLC table") -> Any:
        return data_workflow.import_hplc(self, path, column_mapping, reason)

    def recent_projects(self) -> Any:
        return data_workflow.recent_projects(self)

    def restore_custom_db_tab(self) -> Any:
        return custom_db_workflow.restore_tab(self)

    def add_custom_material(self) -> Any:
        return custom_db_workflow.add_or_update(self)

    def delete_custom_material(self) -> Any:
        return custom_db_workflow.delete_selected(self)

    def load_custom_material_selection(self, event: Any = None) -> Any:
        return custom_db_workflow.load_selected(self, event)

    def record_synthesis_result(self, **results: Any) -> Any:
        return ml_workflow.append_actual_run(self, **results)

    def review_ml_observation(self, **review: Any) -> Any:
        return ml_workflow.review_active_item(self, **review)

    def active_ml_review(self) -> Any:
        return ml_workflow.active_review(self)

    def ml_review_history(self) -> Any:
        return ml_workflow.review_history(self)

    def build_ml_dataset(self) -> Any:
        return ml_workflow.build_execution_dataset(self)

    def ml_dataset_status(self) -> Any:
        return ml_workflow.dataset_status(self)

    def refresh_ml_data(self) -> Any:
        return ml_workflow.refresh(self)

    def train_ml_model(
        self,
        target: str | None = None,
        task: str | None = None,
    ) -> Any:
        return ml_workflow.train(self, target, task)

    def predict_ml_for_active_item(self, target: str | None = None) -> Any:
        return ml_workflow.predict_active(self, target)

    def detect_ml_anomalies(self) -> Any:
        return ml_workflow.detect_anomalies(self)


    def open_msds_lookup(self) -> Any:
        """Open a Google-linked SDS/MSDS lookup using the active SPPS context."""
        from peptiforg_core.msds_lookup import show_msds_lookup, terms_from_text, unique_terms

        terms: list[str] = []

        def selected_row_terms(tree: Any, preferred_columns: tuple[str, ...]) -> None:
            if tree is None or not hasattr(tree, "selection"):
                return
            try:
                selection = list(tree.selection())
                columns = list(tree.cget("columns"))
            except Exception:
                return
            for iid in selection[:4]:
                try:
                    values = list(tree.item(iid, "values"))
                except Exception:
                    continue
                row = dict(zip(columns, values))
                for column in preferred_columns:
                    for term in terms_from_text(row.get(column, "")):
                        terms.append(term)

        # Prefer what the operator has selected in Materials/Plan/Cleavage.
        selected_row_terms(
            getattr(self, "pm_selected_material_tree", None),
            ("material", "Material", "name", "component"),
        )
        selected_row_terms(
            getattr(self, "pm_selected_plan_tree", None),
            (
                "Unit name", "Coupling reagent 1", "Coupling reagent 2 / catalyst",
                "Coupling base", "Coupling cocktail solvent", "Deprotection base",
                "Solvent 1", "Solvent 2",
            ),
        )
        selected_row_terms(
            getattr(self, "pm_cleavage_tree", None),
            ("component",),
        )

        # With no selected row, seed the dialog from the visible synthesis setup.
        if not terms:
            for attr in (
                "pm_resin", "default_reagent", "default_catalyst", "default_base",
                "default_depro", "default_coupling_solution_solvent",
                "default_solvent1", "default_solvent2",
                "default_loading_dissolve_solvent",
            ):
                value = getattr(self, attr, None)
                try:
                    value = value.get() if hasattr(value, "get") else value
                except Exception:
                    value = ""
                terms.extend(terms_from_text(value))

        return show_msds_lookup(
            self,
            unique_terms(terms),
            title="SPPS Planner — MSDS / SDS lookup",
            note=(
                "Selected Materials/Plan/Cleavage rows are preferred. For exact lab use, "
                "verify the SDS against the supplier and product actually used."
            ),
        )

    def open_experimental_data(self) -> Any:
        return experimental_workflow.open_window(self)

    def open_loading_advisor(self) -> Any:
        return experimental_workflow.open_advisor(self, "loading")

    def open_cleavage_advisor(self) -> Any:
        return experimental_workflow.open_advisor(self, "cleavage")

    def open_condition_optimizer(self) -> Any:
        return experimental_workflow.open_condition_optimizer(self)

    def import_experimental_data(self, path: Any) -> Any:
        return experimental_workflow.import_file(self, path)

    def experimental_loading_records(self, statuses: Any = None) -> Any:
        return experimental_workflow.loading_records(self, statuses)

    def experimental_cleavage_records(self, statuses: Any = None) -> Any:
        return experimental_workflow.cleavage_records(self, statuses)

    def loading_advisor(self, **query: Any) -> Any:
        return experimental_workflow.advise_loading(self, **query)

    def cleavage_advisor(self, **query: Any) -> Any:
        return experimental_workflow.advise_cleavage(self, **query)

    def coupling_advisor(self) -> Any:
        return experimental_workflow.advise_coupling(self)

    def evaluate_synthesis_risk(self) -> Any:
        return risk_workflow.evaluate(self)

    def save_synthesis_risk(self, assessment: Any = None) -> Any:
        return risk_workflow.save(self, assessment)

    def acknowledge_risk_finding(self, finding_id: str, reason: str) -> Any:
        return risk_workflow.acknowledge(self, finding_id, reason)

    def synthesis_risk_history(self) -> Any:
        return risk_workflow.history(self)

    def export_synthesis_risk(self, path: Any) -> Any:
        return risk_workflow.export_report(self, path)


def main() -> None:
    app = SPPSGui()
    app.mainloop()


def launch() -> None:
    main()


__all__ = ["SPPSGui", "main", "launch"]
