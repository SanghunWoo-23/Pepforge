"""Legacy-compatible session persistence for the desktop planner."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from spps_v4_gui.gui_primitives import const_var
from spps_v4_gui import state_persistence


DEFAULT_STATE_FIELDS = (
    "project_name", "seq", "lot_no", "resin", "scale", "loading",
    "coupling_eq", "modifier_eq", "coupling_repeats", "modifier_repeats",
    "default_reagent", "default_reagent_eq", "default_reagent_count",
    "default_catalyst", "default_catalyst_eq", "default_catalyst_count",
    "default_base", "default_base_eq", "default_base_count", "default_depro",
    "default_depro_ratio", "default_depro_count", "default_solvent1",
    "default_solvent1_count", "default_solvent2", "default_solvent2_count",
    "final_meoh_count", "default_coupling_solution_solvent",
    "default_loading_dissolve_solvent", "outdir", "batch_solution_conc",
    "batch_coupling_eq", "batch_actual_round_ml", "batch_actual_extra_ml",
    "batch_default_scale", "batch_default_resin", "batch_default_loading",
    "loading_aa_eq", "loading_diea_eq", "loading_time_h", "cleavage_time_h", "batch_hbtu_eq", "batch_hbtu_conc",
    "batch_hbtu_mw", "batch_nmp_density", "solvent_volume_mode",
    "amide_ml_per_mmol", "ctc_ml_per_mmol", "solvent_molarity_m",
)


class SessionStateMixin:
    """Autosave, restore, close, and LOT behaviour from the accepted release."""

    def _state_file_path(self) -> Path:
        if os.name == "nt":
            base = (
                Path(
                    os.environ.get("LOCALAPPDATA")
                    or os.environ.get("APPDATA")
                    or Path.home()
                )
                / "SPPS Planner"
            )
        else:
            base = Path.home() / ".spps_planner"
        base.mkdir(parents=True, exist_ok=True)
        return base / "spps_planner_session_v1.json"

    def schedule_autosave(self):
        if getattr(self, "_restoring_state", False):
            return
        try:
            if getattr(self, "_autosave_after_id", None):
                self.after_cancel(self._autosave_after_id)
            self._autosave_after_id = self.after(450, self.save_autosave_state)
        except Exception:
            pass

    def _collect_state(self) -> dict:
        try:
            if hasattr(self, "pm_live_sync_selected"):
                self.pm_live_sync_selected()
        except Exception:
            pass
        try:
            batch_rows = self._batch_rows_from_tree()
        except Exception:
            batch_rows = []
        try:
            selection = self.pm_list.curselection()
            selected_pm = int(selection[0]) if selection else 0
        except Exception:
            selected_pm = 0

        defaults = {}
        for name in DEFAULT_STATE_FIELDS:
            try:
                variable = getattr(self, name, None)
                if variable is not None and hasattr(variable, "get"):
                    defaults[name] = variable.get()
            except Exception:
                pass
        return state_persistence.project_state(
            app_version="V4.0.0",
            saved_at=datetime.now().isoformat(timespec="seconds"),
            selected_pm_index=selected_pm,
            pm_items=getattr(self, "pm_items", []),
            batch_rows=batch_rows,
            defaults=defaults,
        )

    def save_autosave_state(self):
        try:
            state = self._collect_state()
            state_persistence.atomic_write_json(self.state_file, state)
            self._autosave_after_id = None
        except Exception as exc:
            try:
                self._log(f"Autosave warning: {exc}\n")
            except Exception:
                pass

    def load_autosave_state(self):
        try:
            if not self.state_file.exists():
                return
            state = state_persistence.read_json_object(self.state_file)
            self._restoring_state = True
            defaults = dict(state.get("defaults", {})) if isinstance(state, dict) else {}
            legacy_volume = defaults.pop("ml_per_mmol", None)
            if legacy_volume not in (None, ""):
                defaults.setdefault("amide_ml_per_mmol", legacy_volume)
                defaults.setdefault("ctc_ml_per_mmol", legacy_volume)
            for name, value in defaults.items():
                try:
                    variable = getattr(self, name, None)
                    if variable is not None and hasattr(variable, "set"):
                        variable.set(value)
                except Exception:
                    pass

            items = state.get("pm_items", []) if isinstance(state, dict) else []
            if isinstance(items, list) and items:
                self.pm_items = state_persistence.normalize_items(items)
                keep = int(state.get("selected_pm_index", 0) or 0)
                self.pm_refresh_list(keep_index=keep, reload_editor=True)

            rows = state.get("batch_rows", []) if isinstance(state, dict) else []
            if hasattr(self, "batch_tree") and isinstance(rows, list) and rows:
                for item_id in list(self.batch_tree.get_children()):
                    self.batch_tree.delete(item_id)
                for row in rows:
                    if isinstance(row, dict):
                        self.batch_add_row(row)
                self._renumber_batch_rows()
                self.refresh_batch_workspace_preview()
            try:
                self._log(f"Autosaved session restored: {self.state_file}\n")
            except Exception:
                pass
        except Exception as exc:
            try:
                self._log(f"Autosave restore warning: {exc}\n")
            except Exception:
                pass
        finally:
            self._restoring_state = False

    def on_close(self):
        try:
            self.save_autosave_state()
        finally:
            self.destroy()

    def _generate_lot_no(self) -> str:
        today = datetime.now().strftime("%y%m%d")
        sequence = getattr(self, "seq", const_var("SPPS")).get() or "SPPS"
        hint = re.sub(r"[^A-Za-z0-9]+", "", str(sequence).upper())[:6] or "SPPS"
        return f"SPPS-{today}-{hint}"

    def refresh_lot_no(self):
        try:
            self.lot_no.set(self._generate_lot_no())
            self.refresh_outputs_from_tree()
        except Exception:
            pass


__all__ = ["DEFAULT_STATE_FIELDS", "SessionStateMixin"]
