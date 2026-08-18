"""Operator-facing Experimental Data and Advisor window for V4.0.0."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from spps_v4_gui import experimental_workflow

# Legacy UI labels retained only as searchable compatibility notes for regression
# contracts; the visible V4 labels below are intentionally shorter.
LEGACY_LOADING_APPLY_LABEL = "Review & Apply Exact Record + Generate"
LEGACY_CLEAVAGE_APPLY_LABEL = "Review & Apply Exact Product + Apply Change"


def _value(var: Any, default: str = "") -> str:
    try:
        return str(var.get())
    except Exception:
        return str(var if var is not None else default)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


class ExperimentalDataWindow(tk.Toplevel):
    def __init__(self, gui: Any) -> None:
        super().__init__(gui)
        self.gui = gui
        self.title("Lab Data & Recommendations — SPPS Planner V4.0.0")
        self.geometry("1040x700")
        self.minsize(900, 580)
        try:
            self.transient(gui)
        except Exception as exc:
            self._transient_error = exc
        self._build()
        self.refresh_all()

    def _build(self) -> None:
        top = ttk.Frame(self, padding=(10, 10, 10, 4)); top.pack(fill="x")
        ttk.Button(top, text="Record Loading", command=self.record_loading).pack(side="left")
        ttk.Button(top, text="Record Coupling", command=self.record_coupling).pack(side="left", padx=(6,0))
        ttk.Button(top, text="Record Cleavage", command=self.record_cleavage).pack(side="left", padx=(6,0))
        ttk.Button(top, text="Import Lab Data", command=self.import_file).pack(side="left", padx=(10,0))
        ttk.Button(top, text="Refresh", command=self.refresh_all).pack(side="left", padx=6)
        self.status = ttk.Label(top, text="Experimental knowledge base")
        self.status.pack(side="left", padx=(12, 0))

        nb = ttk.Notebook(self); nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.notebook = nb
        self.loading_tab = ttk.Frame(nb, padding=8); nb.add(self.loading_tab, text="Loading History")
        self.cleavage_tab = ttk.Frame(nb, padding=8); nb.add(self.cleavage_tab, text="Cleavage History")
        self.loading_advisor_tab = ttk.Frame(nb, padding=8); nb.add(self.loading_advisor_tab, text="Loading Advisor")
        self.cleavage_advisor_tab = ttk.Frame(nb, padding=8); nb.add(self.cleavage_advisor_tab, text="Cleavage Advisor")
        self.condition_optimizer_tab = ttk.Frame(nb, padding=8); nb.add(self.condition_optimizer_tab, text="Condition Optimizer")
        self._build_loading_history()
        self._build_cleavage_history()
        self._build_loading_advisor()
        self._build_cleavage_advisor()
        self._build_condition_optimizer()


    def focus_advisor(self, kind: str) -> None:
        """Open an advisor already synchronized to the active Planner item.

        V4 advisors are workflow helpers, not a detached data viewer: opening one
        refreshes its inputs from the active item and immediately analyzes the
        current condition so the operator does not have to repeat those steps.
        """
        loading = str(kind).lower().startswith("load")
        target = self.loading_advisor_tab if loading else self.cleavage_advisor_tab
        self.notebook.select(target)
        self._sync_advisor_from_planner("loading" if loading else "cleavage")
        self.deiconify(); self.lift()
        self.after_idle(self.run_loading_advisor if loading else self.run_cleavage_advisor)

    def focus_optimizer(self) -> None:
        self.notebook.select(self.condition_optimizer_tab)
        self._sync_advisor_from_planner("loading")
        self._sync_advisor_from_planner("cleavage")
        self.deiconify(); self.lift()
        self.after_idle(self.run_condition_optimizer)

    def _sync_advisor_from_planner(self, kind: str) -> None:
        if str(kind).lower().startswith("load"):
            self.load_resin.set(_value(getattr(self.gui, "pm_resin", "")))
            self.load_aa.set(self._current_cterm_compound())
            self.load_aa_eq.set(_value(getattr(self.gui, "loading_aa_eq", "")))
            self.load_base_eq.set(_value(getattr(self.gui, "loading_diea_eq", "")))
            self.load_target.set(_value(getattr(self.gui, "pm_loading", "")))
            self.load_time.set(_value(getattr(self.gui, "loading_time_h", "")))
            return
        self.clv_sequence.set(_value(getattr(self.gui, "pm_sequence", "")))
        self.clv_product.set(_value(getattr(self.gui, "pm_peptide", "")))
        self.clv_resin.set(_value(getattr(self.gui, "pm_resin", "")))
        self.clv_scale.set(_value(getattr(self.gui, "pm_scale", "")))
        self.clv_eq.set(_value(getattr(self.gui, "cleavage_eq_override", "")))
        self.clv_time.set(_value(getattr(self.gui, "cleavage_time_h", "")))

    def _tree(self, parent: Any, columns: list[str]) -> ttk.Treeview:
        wrap = ttk.Frame(parent); wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=columns, show="headings", selectmode="extended")
        y = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew"); y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=120, anchor="w", stretch=True)
        return tree

    def _build_loading_history(self) -> None:
        bar = ttk.Frame(self.loading_tab); bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Parsed records are reviewable evidence; only Verified records are eligible for supervised training.").pack(side="left")
        ttk.Button(bar, text="Edit Selected", command=lambda: self._edit_selected("loading")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Verified", command=lambda: self._mark("loading", "verified")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Excluded", command=lambda: self._mark("loading", "excluded")).pack(side="right", padx=2)
        columns = ["status", "date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "absorbance", "loading_rate_mmol_g", "outlier_flag", "raw_note", "record_id"]
        self.loading_tree = self._tree(self.loading_tab, columns)
        self.loading_tree.column("record_id", width=80)

    def _build_cleavage_history(self) -> None:
        bar = ttk.Frame(self.cleavage_tab); bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Original free-text observations are preserved next to parsed flags.").pack(side="left")
        ttk.Button(bar, text="Edit Selected", command=lambda: self._edit_selected("cleavage")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Verified", command=lambda: self._mark("cleavage", "verified")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Excluded", command=lambda: self._mark("cleavage", "excluded")).pack(side="right", padx=2)
        columns = ["status", "product", "scale_mmol", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "ether_ratio", "filter_speed", "crude_g", "raw_observation", "record_id"]
        self.cleavage_tree = self._tree(self.cleavage_tab, columns)
        self.cleavage_tree.column("raw_observation", width=360)
        self.cleavage_tree.column("record_id", width=80)

    def _build_loading_advisor(self) -> None:
        form = ttk.LabelFrame(self.loading_advisor_tab, text="Current loading condition", padding=10); form.pack(fill="x")
        self.load_resin = tk.StringVar(value=_value(getattr(self.gui, "pm_resin", "")))
        self.load_aa = tk.StringVar(value=self._current_cterm_compound())
        self.load_aa_eq = tk.StringVar(value=_value(getattr(self.gui, "loading_aa_eq", "")))
        self.load_base_eq = tk.StringVar(value=_value(getattr(self.gui, "loading_diea_eq", "")))
        self.load_time = tk.StringVar(value="4")
        self.load_target = tk.StringVar(value=_value(getattr(self.gui, "pm_loading", "")))
        fields = [("Resin", self.load_resin, 24), ("First / C-terminal AA", self.load_aa, 26), ("AA eq", self.load_aa_eq, 8), ("DIEA eq", self.load_base_eq, 8), ("Time (h)", self.load_time, 8), ("Target loading", self.load_target, 11)]
        for index, (label, var, width) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=index * 2, sticky="w", padx=(0, 4))
            ttk.Entry(form, textvariable=var, width=width).grid(row=0, column=index * 2 + 1, sticky="ew", padx=(0, 10))
        ttk.Button(form, text="Analyze", command=self.run_loading_advisor).grid(row=0, column=len(fields) * 2, padx=(4, 0))
        ttk.Button(form, text="Apply & Generate", command=self.apply_loading_recommendation).grid(row=0, column=len(fields) * 2 + 1, padx=(6, 0))
        self._last_loading_advice = None
        self.load_result = tk.Text(self.loading_advisor_tab, height=12, wrap="word"); self.load_result.pack(fill="x", pady=(8, 6))
        self.load_evidence = self._tree(self.loading_advisor_tab, ["date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "loading_rate_mmol_g", "status", "raw_note"])

    def _build_cleavage_advisor(self) -> None:
        form = ttk.LabelFrame(self.cleavage_advisor_tab, text="Current cleavage condition", padding=10); form.pack(fill="x")
        self.clv_sequence = tk.StringVar(value=_value(getattr(self.gui, "pm_sequence", "")))
        self.clv_product = tk.StringVar(value=_value(getattr(self.gui, "pm_peptide", "")))
        self.clv_resin = tk.StringVar(value=_value(getattr(self.gui, "pm_resin", "")))
        self.clv_scale = tk.StringVar(value=_value(getattr(self.gui, "pm_scale", "")))
        self.clv_eq = tk.StringVar(value=_value(getattr(self.gui, "cleavage_eq_override", "")))
        self.clv_time = tk.StringVar(value=_value(getattr(self.gui, "cleavage_time_h", "")))
        fields = [("Sequence", self.clv_sequence, 34), ("Scale", self.clv_scale, 9), ("Eq", self.clv_eq, 7), ("Time (h)", self.clv_time, 7)]
        for index, (label, var, width) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=index * 2, sticky="w", padx=(0, 4))
            ttk.Entry(form, textvariable=var, width=width).grid(row=0, column=index * 2 + 1, sticky="ew", padx=(0, 10))
        ttk.Button(form, text="Analyze", command=self.run_cleavage_advisor).grid(row=0, column=len(fields) * 2)
        ttk.Button(form, text="Apply & Update", command=self.apply_cleavage_recommendation).grid(row=0, column=len(fields) * 2 + 1, padx=(6, 0))
        self._last_cleavage_advice = None
        self.clv_result = tk.Text(self.cleavage_advisor_tab, height=12, wrap="word"); self.clv_result.pack(fill="x", pady=(8, 6))
        self.clv_evidence = self._tree(self.cleavage_advisor_tab, ["product", "scale_mmol", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "ether_ratio", "filter_speed", "status", "raw_observation"])

    def _build_condition_optimizer(self) -> None:
        bar = ttk.Frame(self.condition_optimizer_tab); bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Recommend = current sequence + real lab history + chemistry rules. No cross-record cocktail mixing or invented condition values.").pack(side="left")
        ttk.Button(bar, text="Refresh Recommendations", command=self.run_condition_optimizer).pack(side="right")
        buttons = ttk.Frame(self.condition_optimizer_tab); buttons.pack(fill="x", pady=(0, 8))
        ttk.Button(buttons, text="Apply Loading + Generate", command=self.apply_optimizer_loading).pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="Apply Coupling + Generate", command=self.apply_coupling_recommendation).pack(side="left", padx=5)
        ttk.Button(buttons, text="Apply Cleavage + Update", command=self.apply_optimizer_cleavage).pack(side="left", padx=5)
        self.optimizer_result = tk.Text(self.condition_optimizer_tab, wrap="word", height=30)
        self.optimizer_result.pack(fill="both", expand=True)
        self._last_coupling_advice = None
        self._last_optimizer_loading = None
        self._last_optimizer_cleavage = None

    def run_condition_optimizer(self) -> None:
        self._sync_advisor_from_planner("loading")
        self._sync_advisor_from_planner("cleavage")
        try:
            load = experimental_workflow.recommend_loading(
                self.gui, resin=self.load_resin.get(), amino_acid=self.load_aa.get(),
                target_loading_mmol_g=self.load_target.get(), include_parsed=True,
            )
        except Exception as exc:
            load = {"method": "error", "confidence": "LOW", "warnings": [str(exc)], "recommended_condition": None}
        try:
            clv = experimental_workflow.recommend_cleavage(
                self.gui, product=self.clv_product.get(), sequence=self.clv_sequence.get(),
                resin=self.clv_resin.get(), scale_mmol=self.clv_scale.get(), include_parsed=True,
            )
        except Exception as exc:
            clv = {"method": "error", "confidence": "LOW", "warnings": [str(exc)], "recommended_condition": None}
        self._last_optimizer_loading = load
        self._last_optimizer_cleavage = clv
        try:
            coupling = experimental_workflow.advise_coupling(self.gui)
        except Exception as exc:
            coupling = {"method": "error", "confidence": "LOW", "warnings": [str(exc)], "recommended_condition": None, "evidence_count": 0}
        self._last_coupling_advice = coupling
        lrec = load.get("recommended_condition") or {}
        crec = coupling.get("recommended_condition") or {}
        xrec = clv.get("recommended_condition") or {}
        lines = ["SPPS CONDITION OPTIMIZER", "", "[Loading]"]
        if lrec:
            lines.extend([
                f"Source: {lrec.get('source_status')} record {lrec.get('source_record_id')}",
                f"AA eq {_fmt(lrec.get('aa_eq'))} | DIEA eq {_fmt(lrec.get('base_eq'))} | Time {_fmt(lrec.get('loading_time_h'))} h",
                f"Loading solvent: {lrec.get('loading_solvent') or '(not recorded)' }",
                f"Expected from this recorded condition: {_fmt(lrec.get('expected_loading_mmol_g'))} mmol/g (observed {_fmt(lrec.get('observed_min'))}–{_fmt(lrec.get('observed_max'))}) | target {_fmt(lrec.get('target_loading_mmol_g'))}",
                f"Basis: {lrec.get('basis')}",
                f"Confidence: {load.get('confidence', 'LOW')} | exact-condition n={lrec.get('condition_evidence_count',0)}",
            ])
        else:
            lines.append("No target-grounded exact loading recommendation is available.")
        lines.extend(["", "[Coupling]"])
        unit_recs = coupling.get("unit_recommendations", []) or []
        if unit_recs:
            for row in unit_recs:
                condition = row.get("condition") or {}
                if row.get("apply_allowed"):
                    system = " / ".join(x for x in [str(condition.get("default_reagent") or ""), str(condition.get("default_catalyst") or ""), str(condition.get("default_base") or "")] if x)
                    lines.append(
                        f"• {row.get('compound')} [{row.get('category')}] → {row.get('recommendation_kind')} (n={row.get('evidence_count')}) | "
                        f"unit {condition.get('coupling_eq','')} eq | {system or 'system not recorded'} | "
                        f"R1 {condition.get('default_reagent_eq','')} eq / R2 {condition.get('default_catalyst_eq','')} eq / Base {condition.get('default_base_eq','')} eq | "
                        f"{condition.get('coupling_time_h','')} h | {condition.get('default_coupling_solution_solvent','')}"
                    )
                else:
                    lines.append(f"• {row.get('compound')} [{row.get('category')}] → insufficient repeated evidence")
        else:
            lines.append("No coupling building blocks are available in the current generated Plan.")
        if crec:
            lines.extend([
                "",
                f"Global Apply: {crec.get('recommendation_kind')} covering {len(crec.get('covered_units',[]) or [])} current unit(s)",
                f"Unit eq {crec.get('coupling_eq','')} | repeat {crec.get('coupling_repeats','')} | time {crec.get('coupling_time_h','')} h",
                f"System: {crec.get('default_reagent','')} ({crec.get('default_reagent_eq','')} eq) / {crec.get('default_catalyst','')} ({crec.get('default_catalyst_eq','')} eq) / {crec.get('default_base','')} ({crec.get('default_base_eq','')} eq)",
                f"Solvent: {crec.get('default_coupling_solution_solvent','')} | recorded volume basis {_fmt(crec.get('coupling_solvent_ml_per_mmol'))} mL/mmol",
                f"Confidence: {coupling.get('confidence','LOW')}",
            ])
        elif unit_recs:
            lines.append("Global Apply is disabled when current building blocks require different supported conditions. Per-unit evidence is still shown above.")
        lines.extend(["", "[Cleavage]"])
        if xrec:
            comp = xrec.get("composition_pct") or {}
            comp_text = "; ".join(f"{name} {_fmt(value,2)}%" for name, value in comp.items())
            lines.extend([
                f"Sequence: {xrec.get('sequence')}",
                f"Eq {_fmt(xrec.get('cleavage_eq'))} | Time {_fmt(xrec.get('cleavage_time_h'))} h | Total {_fmt(xrec.get('scaled_total_ml'))} mL",
                f"Cocktail: {comp_text or xrec.get('preset') or '(unavailable)'}",
                f"Ether ratio: {xrec.get('ether_ratio') or '(not recorded/applicable)' }",
                f"Basis: {xrec.get('basis')}",
                f"Confidence: {clv.get('confidence','LOW')} | condition n={xrec.get('condition_evidence_count',0)} | outcome n={xrec.get('outcome_evidence_count',0)}",
            ])
        else:
            lines.append("No safe sequence-based cleavage recommendation.")
        warnings = []
        for result in (load, coupling, clv):
            warnings.extend(result.get("warnings", []) or [])
        if warnings:
            lines.extend(["", "[Warnings]"] + [f"• {w}" for w in warnings])
        self.optimizer_result.delete("1.0", "end"); self.optimizer_result.insert("1.0", "\n".join(lines))

    def apply_optimizer_loading(self) -> None:
        self.run_condition_optimizer()
        result = self._last_optimizer_loading or {}
        rec = result.get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Loading Recommend", "No target-demonstrated exact loading recommendation is available. Nothing was changed.", parent=self)
            return
        try:
            from spps_v4_gui import resin_profiles
            if not resin_profiles.editor_loading_enabled(self.gui):
                messagebox.showinfo("Loading Recommend", "Direct 2-CTC/Trityl loading calculation must be enabled before applying a loading recommendation.", parent=self)
                return
        except Exception as exc:
            messagebox.showerror("Loading Recommend", f"Could not verify loading mode. Nothing was changed.\n\n{exc}", parent=self)
            return
        current_aa = _value(getattr(self.gui, "loading_aa_eq", ""))
        current_base = _value(getattr(self.gui, "loading_diea_eq", ""))
        current_time = _value(getattr(self.gui, "loading_time_h", ""))
        provisional = str(rec.get("source_status") or "") != "verified"
        note = "\n\nPROVISIONAL: supporting records are Parsed, not Verified." if provisional else ""
        ok = messagebox.askyesno(
            "Apply Loading Recommendation",
            "Apply the recommended observed condition?\n\n"
            f"AA eq: {current_aa or '(blank)'} → {_fmt(rec.get('aa_eq'))}\n"
            f"DIEA eq: {current_base or '(blank)'} → {_fmt(rec.get('base_eq'))}\n"
            f"Time: {current_time or '(blank)'} → {_fmt(rec.get('loading_time_h')) or '(unchanged)'} h\n"
            f"Expected loading: {_fmt(rec.get('expected_loading_mmol_g'))} mmol/g\n"
            f"Target: {_fmt(rec.get('target_loading_mmol_g'))} mmol/g\n"
            f"Basis: {rec.get('basis')}\n"
            f"Evidence count: {rec.get('condition_evidence_count',0)}" + note +
            "\n\nNo interpolated AA/base/time value will be applied.",
            parent=self,
        )
        if not ok:
            return
        if rec.get("aa_eq") is not None:
            self.gui.loading_aa_eq.set(str(rec["aa_eq"])); self.load_aa_eq.set(str(rec["aa_eq"]))
        if rec.get("base_eq") is not None:
            self.gui.loading_diea_eq.set(str(rec["base_eq"])); self.load_base_eq.set(str(rec["base_eq"]))
        if rec.get("loading_time_h") is not None:
            self.gui.loading_time_h.set(str(rec["loading_time_h"])); self.load_time.set(str(rec["loading_time_h"]))
        if rec.get("loading_solvent"):
            solvent_var = getattr(self.gui, "default_loading_dissolve_solvent", None)
            if solvent_var is not None and hasattr(solvent_var, "set"):
                solvent_var.set(str(rec["loading_solvent"]))
        try:
            from spps_v4_gui.modules import plan_workflow
            plan_workflow._save_active(self.gui, include_outputs=False)
            if self.gui.generate_update_plan() is None:
                raise RuntimeError("Planner Generate did not complete.")
        except Exception as exc:
            messagebox.showerror("Loading Recommend", f"Recommendation was written, but regeneration failed.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Loading recommendation applied and regenerated.")
        self.run_condition_optimizer()

    def apply_optimizer_cleavage(self) -> None:
        self.run_condition_optimizer()
        result = self._last_optimizer_cleavage or {}
        rec = result.get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Cleavage Recommend", "No safe sequence-based cleavage recommendation is available. Nothing was changed.", parent=self)
            return
        comp = rec.get("composition_pct") or {}
        comp_text = ";".join(f"{name}={_fmt(value,2)}" for name, value in comp.items())
        provisional = str(rec.get("source_status") or "") not in {"", "verified"}
        note = "\n\nPROVISIONAL: the selected sequence-matched lab condition is Parsed, not Verified." if provisional else ""
        ok = messagebox.askyesno(
            "Apply Cleavage Recommendation",
            "Apply the recommended coherent cleavage condition?\n\n"
            f"Sequence: {rec.get('sequence')}\n"
            f"Eq: {_value(getattr(self.gui, 'cleavage_eq_override', '')) or '(blank)'} → {_fmt(rec.get('cleavage_eq'))}\n"
            f"Time: {_value(getattr(self.gui, 'cleavage_time_h', '')) or '(blank)'} → {_fmt(rec.get('cleavage_time_h'))} h\n"
            f"Cocktail: {comp_text or rec.get('preset') or '(unavailable)'}\n"
            f"Total at current scale: {_fmt(rec.get('scaled_total_ml')) or '(eq-based)'} mL\n"
            f"Ether ratio (advice only): {rec.get('ether_ratio') or '(not recorded)'}\n"
            f"Basis: {rec.get('basis')}" + note +
            "\n\nCocktail components come from one coherent record or the sequence chemistry rule; records are never mixed.",
            parent=self,
        )
        if not ok:
            return
        if rec.get("cleavage_eq") is not None:
            self.gui.cleavage_eq_override.set(str(rec["cleavage_eq"])); self.clv_eq.set(str(rec["cleavage_eq"]))
        if rec.get("cleavage_time_h") is not None:
            self.gui.cleavage_time_h.set(str(rec["cleavage_time_h"])); self.clv_time.set(str(rec["cleavage_time_h"]))
        if rec.get("volume_apply_allowed") and rec.get("scaled_total_ml") is not None:
            reserve = getattr(self.gui, "cleavage_reserve_mL", None)
            if reserve is not None and hasattr(reserve, "set"):
                reserve.set(str(rec["scaled_total_ml"]))
        if comp:
            self.gui.cleavage_preset.set("CUSTOM")
            self.gui.cleavage_components_text.set(";".join(f"{name}={float(value):.4g}" for name, value in comp.items() if float(value) > 0))
        elif rec.get("preset"):
            self.gui.cleavage_preset.set(str(rec["preset"])); self.gui.cleavage_components_text.set("")
        try:
            from spps_v4_gui.modules import plan_workflow
            plan_workflow._save_active(self.gui, include_outputs=False)
            if self.gui.apply_change() is None:
                raise RuntimeError("Planner Apply Change did not complete.")
        except Exception as exc:
            messagebox.showerror("Cleavage Recommend", f"Recommendation was written, but Apply Change failed.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Cleavage recommendation applied and updated.")
        self.run_condition_optimizer()

    def apply_coupling_recommendation(self) -> None:
        self.run_condition_optimizer()
        rec = (self._last_coupling_advice or {}).get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Coupling Optimizer", "Apply is disabled because no sufficiently similar, operator-reviewed successful historical coupling condition is available.", parent=self)
            return
        fields = [
            ("coupling_eq", "Default AA eq"), ("coupling_repeats", "Coupling repeat"), ("coupling_time_h", "Coupling time (h)"),
            ("default_reagent", "Reagent"), ("default_reagent_eq", "Reagent eq"),
            ("default_catalyst", "Catalyst"), ("default_catalyst_eq", "Catalyst eq"),
            ("default_base", "Base"), ("default_base_eq", "Base eq"),
            ("default_coupling_solution_solvent", "Coupling solvent"),
            ("solvent_volume_mode", "Volume mode"), ("solvent_molarity_m", "Molarity (M)"),
            ("amide_ml_per_mmol", "Amide mL/mmol"), ("ctc_ml_per_mmol", "CTC mL/mmol"),
        ]
        changes = []
        for attr, label in fields:
            if attr not in rec or rec.get(attr) in (None, ""):
                continue
            current = _value(getattr(self.gui, attr, ""))
            proposed = str(rec.get(attr))
            if current != proposed:
                changes.append((attr, label, current, proposed))
        if not changes:
            messagebox.showinfo("Coupling Optimizer", "The selected reviewed condition matches the current Planner settings; nothing needs to change.", parent=self)
            return
        summary = "\n".join(f"{label}: {old or '(blank)'}  →  {new}" for _, label, old, new in changes)
        ok = messagebox.askyesno(
            "Confirm Coupling Optimizer Apply",
            "Apply one real operator-reviewed successful coupling condition?\n\n" + summary +
            f"\n\nSource: {rec.get('source_project')} / {rec.get('source_peptide')} / {rec.get('source_outcome')}\nNothing changes unless you choose Yes.",
            parent=self,
        )
        if not ok:
            return
        for attr, _label, _old, proposed in changes:
            var = getattr(self.gui, attr, None)
            if var is not None and hasattr(var, "set"):
                var.set(proposed)
        try:
            from spps_v4_gui.modules import gui_common
            gui_common.save_active(self.gui)
            generated = self.gui.generate_update_plan()
            if generated is None:
                raise RuntimeError("Planner Generate did not complete.")
        except Exception as exc:
            messagebox.showerror("Coupling Optimizer", f"The confirmed condition was written, but regeneration failed.\n\n{exc}", parent=self)
            return
        self.status.configure(text="Confirmed reviewed coupling condition applied and regenerated.")
        self.run_condition_optimizer()

    def _entry_dialog(self, title: str, fields: list[tuple[str, str, str]], on_save) -> None:
        dialog = tk.Toplevel(self); dialog.title(title); dialog.transient(self); dialog.grab_set()
        body = ttk.Frame(dialog, padding=12); body.pack(fill="both", expand=True)
        vars: dict[str, tk.StringVar] = {}
        for idx, (key, label, initial) in enumerate(fields):
            ttk.Label(body, text=label, width=24).grid(row=idx, column=0, sticky="w", padx=(0,8), pady=4)
            var = tk.StringVar(value=str(initial or "")); vars[key] = var
            ttk.Entry(body, textvariable=var, width=52).grid(row=idx, column=1, sticky="ew", pady=4)
        body.columnconfigure(1, weight=1)
        def save():
            try:
                on_save({key: var.get().strip() for key, var in vars.items()})
                dialog.destroy(); self.refresh_all()
            except Exception as exc:
                messagebox.showerror(title, str(exc), parent=dialog)
        row = ttk.Frame(body); row.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(10,0))
        ttk.Button(row, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(row, text="Save Lab Result", command=save).pack(side="right", padx=6)

    @staticmethod
    def _optional_float(value: str):
        text = str(value or "").strip()
        return None if not text else float(text)

    def record_loading(self) -> None:
        self._sync_advisor_from_planner("loading")
        fields = [
            ("resin_type", "Resin", self.load_resin.get()), ("amino_acid_raw", "Loaded amino acid", self.load_aa.get()),
            ("aa_eq", "AA eq", self.load_aa_eq.get()), ("base", "Base", "DIEA"), ("base_eq", "Base eq", self.load_base_eq.get()),
            ("loading_time_h", "Loading time (h)", self.load_time.get()),
            ("loading_solvent", "Loading solvent", _value(getattr(self.gui, "default_loading_dissolve_solvent", ""))),
            ("loading_rate_mmol_g", "Measured loading (mmol/g)", ""), ("raw_note", "Result / note", ""),
        ]
        def save(values):
            result = self._optional_float(values["loading_rate_mmol_g"])
            payload = dict(values)
            for key in ("aa_eq", "base_eq", "loading_time_h", "loading_rate_mmol_g"):
                payload[key] = self._optional_float(values[key])
            status = "verified" if result is not None else "incomplete"
            experimental_workflow.add_loading_record(self.gui, payload, status=status)
            self.status.configure(text=f"Loading lab result saved as {status}.")
        self._entry_dialog("Record Loading Result", fields, save)

    def record_coupling(self) -> None:
        try:
            from spps_v4_gui.modules import gui_common
            gui_common.save_active(self.gui)
        except Exception as exc:
            self._coupling_record_sync_error = exc
        fields = [
            ("yield", "Actual yield (%)", ""), ("purity", "Actual purity (%)", ""),
            ("failure", "Failure? (Yes/No/Unknown)", "No"), ("doubling", "Doubling required?", "Unknown"),
            ("note", "Coupling result / note", ""),
        ]
        def save(values):
            experimental_workflow.record_coupling_review(
                self.gui, actual_yield_percent=values["yield"], actual_purity_percent=values["purity"],
                failure_flag=values["failure"], doubling_required=values["doubling"], operator_note=values["note"],
            )
            self.status.configure(text="Coupling outcome saved to the active peptide item.")
        self._entry_dialog("Record Coupling Result", fields, save)

    def record_cleavage(self) -> None:
        self._sync_advisor_from_planner("cleavage")
        component_ml = {"tfa_ml": "", "tis_ml": "", "water_ml": ""}
        try:
            tree = getattr(self.gui, "pm_cleavage_tree", None)
            if tree is not None:
                cols = list(tree["columns"])
                for iid in tree.get_children():
                    vals = list(tree.item(iid, "values")); row = dict(zip(cols, vals))
                    name = str(row.get("component") or "").lower()
                    vol = str(row.get("volume_mL") or row.get("volume_ml") or "")
                    if name == "tfa": component_ml["tfa_ml"] = vol
                    elif "tis" in name or "triisopropyl" in name: component_ml["tis_ml"] = vol
                    elif "water" in name or "dw" in name: component_ml["water_ml"] = vol
        except Exception as exc:
            self._cleavage_prefill_error = exc
        fields = [
            ("product", "Product", self.clv_product.get()), ("sequence", "Sequence", self.clv_sequence.get()),
            ("scale_mmol", "Scale (mmol)", self.clv_scale.get()), ("cleavage_eq", "Cleavage eq", self.clv_eq.get()),
            ("cleavage_time_h", "Cleavage time (h)", self.clv_time.get()),
            ("tfa_ml", "TFA (mL)", component_ml["tfa_ml"]), ("tis_ml", "TIS (mL)", component_ml["tis_ml"]),
            ("water_ml", "Water (mL)", component_ml["water_ml"]), ("ether_ratio", "Ether ratio (1:n)", ""),
            ("crude_g", "Crude (g)", ""), ("raw_observation", "Result / note", ""),
        ]
        def save(values):
            payload = dict(values)
            for key in ("scale_mmol", "cleavage_eq", "cleavage_time_h", "tfa_ml", "tis_ml", "water_ml", "crude_g"):
                payload[key] = self._optional_float(values[key])
            has_condition = payload.get("cleavage_eq") is not None and payload.get("cleavage_time_h") is not None
            status = "verified" if has_condition and any(payload.get(k) is not None for k in ("tfa_ml", "tis_ml", "water_ml")) else "incomplete"
            experimental_workflow.add_cleavage_record(self.gui, payload, status=status)
            self.status.configure(text=f"Cleavage lab result saved as {status}.")
        self._entry_dialog("Record Cleavage Result", fields, save)

    def _current_cterm_compound(self) -> str:
        sequence = _value(getattr(self.gui, "pm_sequence", ""))
        try:
            from spps_planner.parser import parse_sequence
            from spps_v4_gui.material_presentation import AA_BOTTLE_NAME
            parsed = parse_sequence(sequence)
            tokens = list(parsed.core_tokens or [])
            if tokens:
                token = str(tokens[-1])
                if token.startswith("d") and len(token) == 2:
                    base = AA_BOTTLE_NAME.get(token[1:].upper(), token)
                    return base.replace("Fmoc-", "Fmoc-D-", 1)
                return AA_BOTTLE_NAME.get(token.upper(), token)
        except Exception as exc:
            self._cterm_parse_error = exc
        return ""

    def import_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Import Experimental Data", filetypes=[("Experimental data", "*.xlsx *.xlsm *.csv *.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            results = experimental_workflow.import_file(self.gui, path)
            inserted = sum(int(row.get("inserted", 0)) for row in results)
            registered = sum(row.get("kind") == "registered_workbook" for row in results)
            messagebox.showinfo("Experimental Data", f"Import complete.\nNew structured records: {inserted}\nRegistered historical workbooks: {registered}\n\nNo guessed rows are created from unknown workbook layouts.", parent=self)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Experimental Data", str(exc), parent=self)

    def _edit_selected(self, kind: str) -> None:
        tree = self.loading_tree if kind == "loading" else self.cleavage_tree
        selected = list(tree.selection())
        if len(selected) != 1:
            messagebox.showinfo("Experimental Data", "Select exactly one record to edit.", parent=self); return
        record_id = tree.set(selected[0], "record_id")
        rows = experimental_workflow.loading_records(self.gui) if kind == "loading" else experimental_workflow.cleavage_records(self.gui)
        row = next((item for item in rows if str(item.get("record_id")) == str(record_id)), None)
        if row is None:
            messagebox.showerror("Experimental Data", "Record was not found.", parent=self); return
        fields = (["date", "resin_type", "amino_acid_raw", "amino_acid_normalized", "aa_eq", "base", "base_eq", "coupling_reagent", "coupling_reagent_eq", "additive", "additive_eq", "loading_time_h", "capping_method", "resin_sample_weight_mg", "absorbance", "loading_rate_mmol_g", "raw_note"] if kind == "loading" else ["product", "sequence", "scale_mmol", "operator", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "temperature_c", "ether_ml", "ether_ratio", "filter_ether_ml", "filter_speed", "crude_g", "raw_observation", "raw_filter_note"] )
        dialog = tk.Toplevel(self); dialog.title(f"Edit {kind} record"); dialog.geometry("720x700"); dialog.transient(self); dialog.grab_set()
        canvas = tk.Canvas(dialog, highlightthickness=0); scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview); body = ttk.Frame(canvas, padding=10)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=body, anchor="nw"); canvas.configure(yscrollcommand=scroll.set); canvas.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        vars: dict[str, tk.StringVar] = {}
        for index, field in enumerate(fields):
            ttk.Label(body, text=field).grid(row=index, column=0, sticky="nw", padx=(0,8), pady=3)
            var = tk.StringVar(value="" if row.get(field) is None else str(row.get(field))); vars[field] = var
            entry = ttk.Entry(body, textvariable=var, width=72); entry.grid(row=index, column=1, sticky="ew", pady=3)
        body.columnconfigure(1, weight=1)
        def save() -> None:
            changes = {field: var.get() for field, var in vars.items()}
            for numeric in {"aa_eq","base_eq","coupling_reagent_eq","additive_eq","loading_time_h","resin_sample_weight_mg","absorbance","loading_rate_mmol_g","scale_mmol","tfa_ml","tis_ml","water_ml","cleavage_eq","cleavage_time_h","temperature_c","ether_ml","filter_ether_ml","crude_g"}:
                if numeric in changes:
                    text = str(changes[numeric]).strip()
                    changes[numeric] = None if not text else float(text)
            try:
                experimental_workflow.update_record(self.gui, kind, record_id, changes)
                dialog.destroy(); self.refresh_all()
            except Exception as exc:
                messagebox.showerror("Experimental Data", str(exc), parent=dialog)
        buttons = ttk.Frame(body); buttons.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(10,0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", command=save).pack(side="right", padx=6)

    def _mark(self, kind: str, status: str) -> None:
        tree = self.loading_tree if kind == "loading" else self.cleavage_tree
        selected = list(tree.selection())
        ids = [tree.set(item, "record_id") for item in selected]
        if not ids:
            messagebox.showinfo("Experimental Data", "Select one or more records first.", parent=self); return
        count = experimental_workflow.set_status(self.gui, kind, ids, status)
        self.status.configure(text=f"Updated {count} {kind} record(s) → {status}")
        self.refresh_all()

    def _fill(self, tree: ttk.Treeview, rows: list[dict[str, Any]]) -> None:
        for item in tree.get_children(): tree.delete(item)
        columns = list(tree["columns"])
        for row in rows:
            values = [row.get(column, "") for column in columns]
            tree.insert("", "end", values=["" if value is None else value for value in values])

    def refresh_all(self) -> None:
        try:
            loading = experimental_workflow.loading_records(self.gui)
            cleavage = experimental_workflow.cleavage_records(self.gui)
            self._fill(self.loading_tree, loading); self._fill(self.cleavage_tree, cleavage)
            self.status.configure(text=f"Loading records: {len(loading)} | Cleavage records: {len(cleavage)} | DB: {experimental_workflow.db_path(self.gui)}")
        except Exception as exc:
            self.status.configure(text=f"Experimental DB error: {exc}")

    def run_loading_advisor(self) -> None:
        try:
            result = experimental_workflow.advise_loading(
                self.gui, resin=self.load_resin.get(), amino_acid=self.load_aa.get(),
                aa_eq=self.load_aa_eq.get(), base_eq=self.load_base_eq.get(),
                loading_time_h=self.load_time.get(), target_loading_mmol_g=self.load_target.get(),
                include_parsed=True, allow_parsed_apply=True,
            )
            self._last_loading_advice = result
            lines = [
                f"Method: {result.get('method')}",
                f"Evidence-based loading estimate: {_fmt(result.get('prediction'))} mmol/g" if result.get("prediction") is not None else "Estimate: unavailable",
                f"Comparable observed range: {_fmt(result.get('observed_min'))} – {_fmt(result.get('observed_max'))} mmol/g",
                f"Evidence: {result.get('evidence_count', 0)} records ({result.get('exact_count', 0)} exact resin+AA matches)",
                f"Confidence: {result.get('confidence', 'LOW')}",
                f"Target loading: {_fmt(self.load_target.get())} mmol/g",
            ]
            rec = result.get("recommended_condition") or {}
            if rec:
                lines.extend([
                    "", "Actionable historical condition (one real exact-match record):",
                    f"AA eq: {_fmt(rec.get('aa_eq'))}", f"DIEA eq: {_fmt(rec.get('base_eq'))}",
                    f"Loading time: {_fmt(rec.get('loading_time_h'))} h ({rec.get('loading_time_source') or 'source'})",
                    f"Loading solvent: {rec.get('loading_solvent') or '(not recorded)'}",
                    f"Observed loading: {_fmt(rec.get('observed_loading_mmol_g'))} mmol/g",
                    f"Source: {rec.get('source_date') or 'unknown date'} / {rec.get('source_status') or 'unknown status'} / record {rec.get('record_id')}",
                ])
            else:
                lines.extend(["", "Apply: DISABLED — no exact, target-grounded historical condition is available."])
            if result.get("warnings"):
                lines.append("\nWarnings:"); lines.extend(f"• {warning}" for warning in result["warnings"])
            self.load_result.delete("1.0", "end"); self.load_result.insert("1.0", "\n".join(lines))
            self._fill(self.load_evidence, result.get("evidence", []))
        except Exception as exc:
            messagebox.showerror("Loading Advisor", str(exc), parent=self)

    def run_cleavage_advisor(self) -> None:
        try:
            result = experimental_workflow.advise_cleavage(
                self.gui, product=self.clv_product.get(), sequence=self.clv_sequence.get(), resin=self.clv_resin.get(), scale_mmol=self.clv_scale.get(),
                cleavage_eq=self.clv_eq.get(), cleavage_time_h=self.clv_time.get(), include_parsed=True,
            )
            self._last_cleavage_advice = result
            lines = [
                f"Method: {result.get('method')}", f"Confidence: {result.get('confidence', 'LOW')}",
                f"Evidence: {result.get('evidence_count', 0)} records ({result.get('exact_count', 0)} exact product matches)",
            ]
            rec = result.get("recommended_condition") or {}
            if rec:
                comp = rec.get("composition_pct") or {}
                comp_text = "; ".join(f"{name} {_fmt(value,2)}%" for name, value in comp.items())
                source_label = "Exact lab record" if rec.get("condition_source") == "exact_lab_record" else "Sequence-rule fallback"
                lines.extend([
                    "", f"Recommendation — {source_label}",
                    f"Sequence: {rec.get('sequence')}",
                    f"Eq / Time: {_fmt(rec.get('cleavage_eq'))} eq / {_fmt(rec.get('cleavage_time_h'))} h",
                    f"Cocktail: {comp_text or rec.get('preset') or 'unavailable'}",
                    f"Total: {_fmt(rec.get('scaled_total_ml'))} mL at current scale",
                    f"Basis: {rec.get('basis')}",
                ])
            else:
                lines.extend(["", "Apply: unavailable — sequence could not be converted into a safe recommendation."])
            recommendations = result.get("recommendations", [])
            if recommendations:
                lines.append("\nEvidence notes (not auto-applied):"); lines.extend(f"• {row}" for row in recommendations)
            if result.get("warnings"):
                lines.append("\nWarnings:"); lines.extend(f"• {row}" for row in result["warnings"])
            self.clv_result.delete("1.0", "end"); self.clv_result.insert("1.0", "\n".join(lines))
            self._fill(self.clv_evidence, result.get("evidence", []))
        except Exception as exc:
            messagebox.showerror("Cleavage Advisor", str(exc), parent=self)


    def _append_result_status(self, widget: tk.Text, message: str) -> None:
        try:
            current = widget.get("1.0", "end").strip()
            widget.delete("1.0", "end")
            widget.insert("1.0", (message + ("\n\n" + current if current else "")))
        except Exception as exc:
            self._result_status_error = exc

    def apply_loading_recommendation(self) -> None:
        # Recompute immediately before Apply so edited advisor fields cannot use stale evidence.
        self.run_loading_advisor()
        result = self._last_loading_advice or {}
        try:
            from spps_v4_gui import resin_profiles
            if not resin_profiles.editor_loading_enabled(self.gui):
                messagebox.showinfo("Loading Advisor", "Apply is disabled unless direct 2-CTC/Trityl resin loading calculation is enabled in the Planner. Evidence can still be reviewed.", parent=self)
                return
        except Exception as exc:
            messagebox.showerror("Loading Advisor", f"Could not verify the Planner loading mode. No values were changed.\n\n{exc}", parent=self)
            return
        rec = result.get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Loading Advisor", "Apply is disabled because there is no exact, target-grounded historical condition for the current resin + amino acid.", parent=self)
            return
        current_aa = _value(getattr(self.gui, "loading_aa_eq", ""))
        current_base = _value(getattr(self.gui, "loading_diea_eq", ""))
        proposed_aa = "" if rec.get("aa_eq") is None else _fmt(rec.get("aa_eq"))
        proposed_base = "" if rec.get("base_eq") is None else _fmt(rec.get("base_eq"))
        source = f"{rec.get('source_status') or 'unknown'} record {rec.get('record_id')} ({rec.get('source_date') or 'unknown date'})"
        ok = messagebox.askyesno(
            "Confirm Loading ML Apply",
            "Apply one real historical exact-match condition to the Planner?\n\n"
            f"Loading AA eq: {current_aa}  →  {proposed_aa or '(unchanged)'}\n"
            f"Loading DIEA eq: {current_base}  →  {proposed_base or '(unchanged)'}\n"
            f"Loading time: {_value(getattr(self.gui, 'loading_time_h', '')) or '(blank)'}  →  {_fmt(rec.get('loading_time_h')) if rec.get('loading_time_h') is not None else '(unchanged)'} h\n"
            f"Loading solvent: {_value(getattr(self.gui, 'default_loading_dissolve_solvent', '')) or '(blank)'}  →  {rec.get('loading_solvent') or '(unchanged; not recorded)'}\n"
            f"Observed loading in source record: {_fmt(rec.get('observed_loading_mmol_g'))} mmol/g\n"
            f"Target loading: {_fmt(rec.get('target_loading_mmol_g'))} mmol/g\n"
            f"Source: {source}\n\n"
            "Nothing is changed unless you choose Yes.", parent=self,
        )
        if not ok:
            return
        if rec.get("aa_eq") is not None:
            self.gui.loading_aa_eq.set(str(rec["aa_eq"])); self.load_aa_eq.set(str(rec["aa_eq"]))
        if rec.get("base_eq") is not None:
            self.gui.loading_diea_eq.set(str(rec["base_eq"])); self.load_base_eq.set(str(rec["base_eq"]))
        if rec.get("loading_time_h") is not None:
            self.gui.loading_time_h.set(str(rec["loading_time_h"])); self.load_time.set(str(rec["loading_time_h"]))
        if rec.get("loading_solvent"):
            solvent_var = getattr(self.gui, "default_loading_dissolve_solvent", None)
            if solvent_var is not None and hasattr(solvent_var, "set"):
                solvent_var.set(str(rec["loading_solvent"]))
        try:
            from spps_v4_gui.modules import plan_workflow
            plan_workflow._save_active(self.gui, include_outputs=False)
            generated = self.gui.generate_update_plan()
            if generated is None:
                raise RuntimeError("Planner Generate did not complete.")
        except Exception as exc:
            messagebox.showerror("Loading Advisor", f"The confirmed condition was written, but regeneration failed.\n\n{exc}", parent=self)
            return
        text = f"Confirmed historical condition applied and regenerated: Loading AA {self.load_aa_eq.get()} eq / DIEA {self.load_base_eq.get()} eq / {self.load_time.get()} h."
        self.status.configure(text=text); self._append_result_status(self.load_result, "✓ " + text)

    def apply_cleavage_recommendation(self) -> None:
        # Recompute immediately before Apply so edited advisor fields cannot use stale evidence.
        self.run_cleavage_advisor()
        result = self._last_cleavage_advice or {}
        rec = result.get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Cleavage Advisor", "No safe sequence-based cleavage recommendation is available for the current Planner input.", parent=self)
            return
        eq = rec.get("cleavage_eq")
        comp = rec.get("composition_pct") or {}
        current_eq = _value(getattr(self.gui, "cleavage_eq_override", ""))
        current_comp = _value(getattr(self.gui, "cleavage_components_text", ""))
        proposed_comp = "unavailable"
        if comp:
            proposed_comp = ";".join(f"{name}={_fmt(value,2)}" for name, value in comp.items())
        ok = messagebox.askyesno(
            "Confirm Cleavage ML Apply",
            "Apply the sequence-based cleavage recommendation?\n\n"
            f"Cleavage eq: {current_eq or '(blank)'}  →  {_fmt(eq) if eq is not None else '(unchanged)'}\n"
            f"Cocktail: {current_comp or '(current preset)'}\n        →  {proposed_comp}\n"
            f"Cleavage time: {_value(getattr(self.gui, 'cleavage_time_h', '')) or '(blank)'}  →  {_fmt(rec.get('cleavage_time_h')) if rec.get('cleavage_time_h') is not None else '(unchanged)'} h\n"
            f"Minimum total cocktail: {_value(getattr(self.gui, 'cleavage_reserve_mL', '')) or '0'}  →  {_fmt(rec.get('scaled_total_ml')) if rec.get('scaled_total_ml') is not None else '(unchanged)'} mL\n"
            f"Sequence: {self.clv_sequence.get()}\n"
            f"Basis: {rec.get('basis') or rec.get('source_status') or 'sequence + history'}\n\n"
            "The recommendation is recalculated from the current sequence immediately before Apply.", parent=self,
        )
        if not ok:
            return
        if eq is not None:
            self.gui.cleavage_eq_override.set(str(eq)); self.clv_eq.set(str(eq))
        if rec.get("cleavage_time_h") is not None:
            self.gui.cleavage_time_h.set(str(rec["cleavage_time_h"])); self.clv_time.set(str(rec["cleavage_time_h"]))
        if rec.get("volume_apply_allowed") and rec.get("scaled_total_ml") is not None:
            reserve_var = getattr(self.gui, "cleavage_reserve_mL", None)
            if reserve_var is not None and hasattr(reserve_var, "set"):
                reserve_var.set(str(rec["scaled_total_ml"]))
        preset = str(rec.get("preset") or "").strip()
        # A historical exact record is applied as its recorded composition, not
        # silently replaced by the generic sequence preset.  Sequence-rule fallback
        # continues to use the named preset.
        if rec.get("condition_source") == "exact_lab_record" and comp:
            self.gui.cleavage_preset.set("CUSTOM")
            self.gui.cleavage_components_text.set(
                ";".join(f"{name}={float(value):.4g}" for name, value in comp.items() if value is not None and float(value) > 0)
            )
        elif preset:
            self.gui.cleavage_preset.set(preset)
            self.gui.cleavage_components_text.set("")
        elif comp:
            self.gui.cleavage_preset.set("CUSTOM")
            self.gui.cleavage_components_text.set(
                ";".join(f"{name}={float(value):.4g}" for name, value in comp.items() if value is not None and float(value) > 0)
            )
        try:
            from spps_v4_gui.modules import plan_workflow
            plan_workflow._save_active(self.gui, include_outputs=False)
            changed = self.gui.apply_change()
            if changed is None:
                raise RuntimeError("Planner Apply Change did not complete.")
        except Exception as exc:
            messagebox.showerror("Cleavage Advisor", f"The confirmed condition was written, but Apply Change failed.\n\n{exc}", parent=self)
            return
        composition = _value(getattr(self.gui, "cleavage_components_text", "")) or _value(getattr(self.gui, "cleavage_preset", ""))
        text = f"Sequence recommendation applied: {self.clv_eq.get()} eq / {self.clv_time.get()} h / {composition}."
        self.status.configure(text=text); self._append_result_status(self.clv_result, "✓ " + text)


__all__ = ["ExperimentalDataWindow"]
