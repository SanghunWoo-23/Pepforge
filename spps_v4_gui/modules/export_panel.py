"""Export routing helpers for SPPS Planner V4.0.0."""
from __future__ import annotations
from pathlib import Path
from . import gui_common as state
from .cleavage_panel import refresh_cleavage_panel


def generate_update(gui, ns: dict | None = None):
    try:
        state.save_active(gui)
        if not str(state.get_var(gui, "pm_sequence", "") or "").strip():
            state.clear_selected_outputs(gui)
            idx = state.active_index(gui)
            if idx is not None and 0 <= idx < len(getattr(gui, "pm_items", []) or []):
                gui.pm_items[idx]["status"] = "Ready"
                state.refresh_list(gui, [idx])
            try:
                gui.schedule_autosave()
            except Exception:
                pass
            return {}
        tables = state.refresh_selected_outputs(gui)
        try: refresh_cleavage_panel(gui)
        except Exception: pass
        idx = state.active_index(gui)
        if idx is not None and 0 <= idx < len(getattr(gui, "pm_items", []) or []):
            gui.pm_items[idx]["status"] = "Calculated"
            state.refresh_list(gui, [idx])
        try: gui.schedule_autosave()
        except Exception: pass
        return tables
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror("Generate / Update", str(exc))
        except Exception:
            pass
        return None


def export_outputs(gui, ns: dict | None = None):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.export import export_csvs, export_excel
        from spps_planner.version import VERSION_NUMBER
        state.save_active(gui)
        inp, meta, tables = state.core_tables(gui)
        out: Path = state.project_outdir(gui)
        out.mkdir(parents=True, exist_ok=True)
        export_csvs(inp, out / "core_engine_outputs")
        export_excel(inp, out / "spps_plan_core_engine.xlsx")
        visible_plan = state.tree_to_df(getattr(gui, "pm_selected_plan_tree", None))
        visible_mats = state.tree_to_df(getattr(gui, "pm_selected_material_tree", None))
        if visible_plan.empty or visible_mats.empty:
            state.refresh_selected_outputs(gui)
            visible_plan = state.tree_to_df(getattr(gui, "pm_selected_plan_tree", None))
            visible_mats = state.tree_to_df(getattr(gui, "pm_selected_material_tree", None))
        # The visible sheets mirror the GUI trees: step/material columns first,
        # with LOT/loading conditions retained but without noisy app/project metadata.
        visible_plan = state.display_columns(visible_plan, state.SELECTED_PLAN_DISPLAY_COLUMNS)
        visible_mats = state.display_columns(visible_mats, state.SELECTED_MATERIAL_DISPLAY_COLUMNS)
        xlsx = out / f"project_manager_selected_outputs_v{VERSION_NUMBER}.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
            pd.DataFrame([meta]).to_excel(w, index=False, sheet_name="00_EDITOR_SUMMARY")
            visible_plan.to_excel(w, index=False, sheet_name="01_SELECTED_PLAN_VISIBLE")
            visible_mats.to_excel(w, index=False, sheet_name="02_SELECTED_MATERIALS_VISIBLE")
            tables["selected_plan_core"].to_excel(w, index=False, sheet_name="03_SELECTED_PLAN_CORE")
            tables["selected_materials_core"].to_excel(w, index=False, sheet_name="04_MATERIALS_CORE")
            tables["operations_core"].to_excel(w, index=False, sheet_name="05_OPERATIONS_CORE")
            tables["cleavage_cocktail"].to_excel(w, index=False, sheet_name="06_CLEAVAGE_COCKTAIL")
            tables["cleavage_presets"].to_excel(w, index=False, sheet_name="07_CLEAVAGE_PRESETS")
            tables["validation"].to_excel(w, index=False, sheet_name="08_VALIDATION")
            tables["summary"].to_excel(w, index=False, sheet_name="09_SUMMARY")
        for name, df in [("01_SELECTED_PLAN_VISIBLE", visible_plan), ("02_SELECTED_MATERIALS_VISIBLE", visible_mats)] + list(tables.items()):
            try: df.to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")
            except Exception: pass
        state.save_state_json(gui, out, f"project_manager_state_v{VERSION_NUMBER}.json")
        try: gui.last_outdir = out
        except Exception: pass
        try: gui._log(f"V{VERSION_NUMBER} export completed: {xlsx}\n")
        except Exception: pass
        try:
            from tkinter import messagebox
            messagebox.showinfo("Export complete", f"CSV/XLSX exported to:\n{out}")
        except Exception:
            pass
        return xlsx
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror("Export error", str(exc))
        except Exception:
            pass
        return None
