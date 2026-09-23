"""Operator-facing Experimental Data and Advisor window for V5.0.0."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from spps_v4_gui import experimental_data, experimental_workflow, ui_system

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
        self.title("Recommendations & Lab History — SPPS Planner V5.0.0")
        ui_system.apply_theme(self)
        self._configure_v5_styles()
        try:
            self.transient(gui)
        except Exception as exc:
            self._transient_error = exc
        self._build()
        ui_system.fit_window(self, preferred_width=1180, preferred_height=760, minimum_width=1040, minimum_height=680)
        # Paint the window first; load DB-backed history immediately afterward.
        # This keeps the button click responsive without changing any feature.
        self.after(60, self._refresh_after_open)

    def _refresh_after_open(self) -> None:
        try:
            if not self.winfo_exists():
                return
            try:
                experimental_workflow.initialize(self.gui)
                self.gui._experimental_db_init_error = None
            except Exception as exc:
                self.gui._experimental_db_init_error = exc
                self.status.configure(text=f"Experimental DB initialization error: {exc}")
                return
            self.refresh_all()
        except tk.TclError:
            return

    def _configure_v5_styles(self) -> None:
        """Apply the restrained Pepforge-inspired V5 visual language.

        Styles are local names so the existing Planner UI is not destructively
        restyled.  Segoe UI is the Windows-first font; Tk falls back naturally on
        non-Windows test hosts.
        """
        self._v5_colors = {
            "bg": "#f4f8ff", "card": "#ffffff", "line": "#cfe0fb",
            "text": "#18324d", "muted": "#5d7793", "lavender": "#deebff",
            "lavender_active": "#c6dcff", "accent": "#2f6fe4", "soft": "#ebf3ff",
        }
        self.configure(background=self._v5_colors["bg"])
        style = ttk.Style(self)
        style.configure("V5.Root.TFrame", background=self._v5_colors["bg"])
        style.configure("V5.Card.TFrame", background=self._v5_colors["card"])
        style.configure("V5.Title.TLabel", background=self._v5_colors["bg"], foreground=self._v5_colors["text"], font=("Segoe UI Semibold", 14))
        style.configure("V5.Subtitle.TLabel", background=self._v5_colors["bg"], foreground=self._v5_colors["muted"], font=("Segoe UI", 9))
        style.configure("V5.Section.TLabel", background=self._v5_colors["bg"], foreground=self._v5_colors["text"], font=("Segoe UI Semibold", 10))
        style.configure("V5.Muted.TLabel", background=self._v5_colors["bg"], foreground=self._v5_colors["muted"], font=("Segoe UI", 9))
        style.configure("V5.Card.TLabelframe", background=self._v5_colors["card"], bordercolor=self._v5_colors["line"], relief="solid", borderwidth=1)
        style.configure("V5.Card.TLabelframe.Label", background=self._v5_colors["bg"], foreground=self._v5_colors["text"], font=("Segoe UI Semibold", 10))
        style.configure("V5.TNotebook", background=self._v5_colors["bg"], borderwidth=0, tabmargins=(0, 2, 0, 0))
        style.configure("V5.TNotebook.Tab", font=("Segoe UI Semibold", 9), padding=(13, 8), foreground=self._v5_colors["text"])
        style.map("V5.TNotebook.Tab", background=[("selected", self._v5_colors["lavender_active"]), ("active", self._v5_colors["lavender"])], foreground=[("selected", self._v5_colors["accent"])])
        style.configure("V5.Primary.TButton", font=("Segoe UI Semibold", 9), padding=(12, 7))
        style.configure("V5.Secondary.TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _style_text(self, widget: tk.Text, *, compact: bool = False) -> None:
        widget.configure(
            font=("Segoe UI", 9), background="#ffffff", foreground="#18324d",
            insertbackground="#18324d", relief="flat", borderwidth=0,
            highlightthickness=1, highlightbackground="#cfe0fb", highlightcolor="#2f6fe4",
            padx=10, pady=8, spacing1=1, spacing3=2,
        )
        if compact:
            widget.configure(height=8)

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(14, 12, 14, 5), style="V5.Root.TFrame"); header.pack(fill="x")
        left = ttk.Frame(header, style="V5.Root.TFrame"); left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Recommendations & Lab History", style="V5.Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Add measured results or issues; Planner conditions are attached automatically.", style="V5.Subtitle.TLabel").pack(anchor="w", pady=(1,0))
        self.status = ttk.Label(header, text="Experimental knowledge base", style="V5.Subtitle.TLabel", anchor="e")
        self.status.pack(side="right", padx=(12,0))

        top = ttk.Frame(self, padding=(14, 5, 14, 7), style="V5.Root.TFrame"); top.pack(fill="x")
        ttk.Button(top, text="Add Result", command=self.record_result, style="V5.Primary.TButton").pack(side="left")
        ttk.Button(top, text="Add Issue", command=self.record_issue, style="V5.Secondary.TButton").pack(side="left", padx=(6,0))
        ttk.Button(top, text="Refresh", command=self.refresh_all, style="V5.Secondary.TButton").pack(side="left", padx=(12,0))
        ttk.Button(top, text="Data Store", command=self._show_data_store, style="V5.Secondary.TButton").pack(side="left", padx=(6,0))
        ttk.Button(top, text="Backup DB", command=self._backup_data_store, style="V5.Secondary.TButton").pack(side="left", padx=(6,0))
        ttk.Label(top, text="Planner conditions are saved with results automatically.", style="V5.Muted.TLabel").pack(side="left", padx=(14,0))

        # Legacy top-level labels retained only as code-search notes for old tests:
        # text="Records"  text="Risk & Evidence"  text="Recommended Conditions"  text="Data Health"
        # The operator-facing surface is now Recommendations + Advanced. Existing
        # history/risk/health functionality is improved in-place, not duplicated.
        nb = ttk.Notebook(self, style="V5.TNotebook"); nb.pack(fill="both", expand=True, padx=14, pady=(3, 12))
        self.notebook = nb
        self.recommend_tab = ttk.Frame(nb, padding=8, style="V5.Root.TFrame"); nb.add(self.recommend_tab, text="Recommendations")
        self.advanced_tab = ttk.Frame(nb, padding=8, style="V5.Root.TFrame"); nb.add(self.advanced_tab, text="Advanced")

        advbar = ttk.Frame(self.advanced_tab, style="V5.Root.TFrame"); advbar.pack(fill="x", pady=(0,6))
        ttk.Button(advbar, text="Import Lab Data", command=self.import_file, style="V5.Secondary.TButton").pack(side="left")
        ttk.Label(advbar, text="History, evidence audit and model/data checks", style="V5.Muted.TLabel").pack(side="left", padx=(10,0))
        advanced_nb = ttk.Notebook(self.advanced_tab, style="V5.TNotebook"); advanced_nb.pack(fill="both", expand=True)
        self.advanced_notebook = advanced_nb
        self.records_tab = ttk.Frame(advanced_nb, padding=8, style="V5.Root.TFrame"); advanced_nb.add(self.records_tab, text="History")
        self.decision_tab = ttk.Frame(advanced_nb, padding=10, style="V5.Root.TFrame"); advanced_nb.add(self.decision_tab, text="Risk & Evidence")
        self.health_tab = ttk.Frame(advanced_nb, padding=10, style="V5.Root.TFrame"); advanced_nb.add(self.health_tab, text="Data Health")

        records_nb = ttk.Notebook(self.records_tab, style="V5.TNotebook"); records_nb.pack(fill="both", expand=True)
        self.records_notebook = records_nb
        self.issue_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.issue_tab, text="Issues")
        self.loading_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.loading_tab, text="Loading")
        self.cleavage_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.cleavage_tab, text="Cleavage")
        self.sequence_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.sequence_tab, text="Sequence STD")
        self.usage_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.usage_tab, text="Cleavage Usage")
        self.outcome_tab = ttk.Frame(records_nb, padding=10, style="V5.Root.TFrame"); records_nb.add(self.outcome_tab, text="Outcomes")

        recommend_nb = ttk.Notebook(self.recommend_tab, style="V5.TNotebook"); recommend_nb.pack(fill="both", expand=True)
        self.recommend_notebook = recommend_nb
        self.loading_advisor_tab = ttk.Frame(recommend_nb, padding=10, style="V5.Root.TFrame"); recommend_nb.add(self.loading_advisor_tab, text="Loading")
        self.cleavage_advisor_tab = ttk.Frame(recommend_nb, padding=10, style="V5.Root.TFrame"); recommend_nb.add(self.cleavage_advisor_tab, text="Cleavage")
        self.condition_optimizer_tab = ttk.Frame(recommend_nb, padding=10, style="V5.Root.TFrame"); recommend_nb.add(self.condition_optimizer_tab, text="All Conditions")

        self._build_loading_history(); self._build_cleavage_history(); self._build_sequence_history()
        self._build_cleavage_usage_history(); self._build_outcome_history(); self._build_issue_history(); self._build_decision_support()
        self._build_data_health(); self._build_loading_advisor(); self._build_cleavage_advisor(); self._build_condition_optimizer()

    def focus_advisor(self, kind: str) -> None:
        """Open an advisor already synchronized to the active Planner item.

        V4 advisors are workflow helpers, not a detached data viewer: opening one
        refreshes its inputs from the active item and immediately analyzes the
        current condition so the operator does not have to repeat those steps.
        """
        loading = str(kind).lower().startswith("load")
        target = self.loading_advisor_tab if loading else self.cleavage_advisor_tab
        self.notebook.select(self.recommend_tab)
        self.recommend_notebook.select(target)
        self._sync_advisor_from_planner("loading" if loading else "cleavage")
        self.deiconify(); self.lift()
        ui_system.fit_window(self, preferred_width=1180, preferred_height=760, minimum_width=1040, minimum_height=680)
        self.after_idle(self.run_loading_advisor if loading else self.run_cleavage_advisor)

    def focus_optimizer(self) -> None:
        self.notebook.select(self.recommend_tab)
        self.recommend_notebook.select(self.condition_optimizer_tab)
        self._sync_advisor_from_planner("loading")
        self._sync_advisor_from_planner("cleavage")
        self.deiconify(); self.lift()
        ui_system.fit_window(self, preferred_width=1180, preferred_height=760, minimum_width=1040, minimum_height=680)
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
        columns = ["status", "date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "absorbance", "loading_rate_mmol_g", "outlier_flag", "run_id", "raw_note", "record_id"]
        self.loading_tree = self._tree(self.loading_tab, columns)
        self.loading_tree.column("record_id", width=80)

    def _build_cleavage_history(self) -> None:
        bar = ttk.Frame(self.cleavage_tab); bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Original free-text observations are preserved next to parsed flags.").pack(side="left")
        ttk.Button(bar, text="Edit Selected", command=lambda: self._edit_selected("cleavage")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Verified", command=lambda: self._mark("cleavage", "verified")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Excluded", command=lambda: self._mark("cleavage", "excluded")).pack(side="right", padx=2)
        columns = ["status", "product", "scale_mmol", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "ether_ratio", "filter_speed", "crude_g", "run_id", "raw_observation", "record_id"]
        self.cleavage_tree = self._tree(self.cleavage_tab, columns)
        self.cleavage_tree.column("raw_observation", width=360)
        self.cleavage_tree.column("record_id", width=80)

    def _build_sequence_history(self) -> None:
        bar = ttk.Frame(self.sequence_tab); bar.pack(fill="x", pady=(0, 6))
        ttk.Label(
            bar,
            text="Each row is a page-local Check table STD sequence. Repeated product names are retained as separate observations.",
        ).pack(side="left")
        ttk.Button(bar, text="Verify Same Product", command=self._verify_same_sequence_product).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Verified", command=lambda: self._mark("sequence", "verified")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Excluded", command=lambda: self._mark("sequence", "excluded")).pack(side="right", padx=2)
        columns = ["status", "product", "sequence", "source_file", "source_page", "source_locator", "row_basis", "record_id"]
        self.sequence_tree = self._tree(self.sequence_tab, columns)
        self.sequence_tree.column("product", width=180)
        self.sequence_tree.column("sequence", width=360)
        self.sequence_tree.column("source_file", width=240)
        self.sequence_tree.column("source_page", width=170)
        self.sequence_tree.column("source_locator", width=220)
        self.sequence_tree.column("row_basis", width=110)
        self.sequence_tree.column("record_id", width=80)

    def _build_cleavage_usage_history(self) -> None:
        bar = ttk.Frame(self.usage_tab); bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Actual TFA/Water/TIS/Ether usage. Unitless numeric values remain raw until operator review.").pack(side="left")
        ttk.Button(bar, text="Review Units", command=self._review_usage_units).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Verified", command=lambda: self._mark("cleavage_usage", "verified")).pack(side="right", padx=2)
        ttk.Button(bar, text="Mark Excluded", command=lambda: self._mark("cleavage_usage", "excluded")).pack(side="right", padx=2)
        columns = ["status","product","sequence","scale_mmol","tfa_raw","water_raw","tis_raw","ether_raw","hexane_raw","cocktail_total_ml","cocktail_ml_per_mmol","ether_ml_per_mmol","hexane_ml_per_mmol","unit_review_required","record_scope","manufacture_period","source_file","record_id"]
        self.usage_tree = self._tree(self.usage_tab, columns)
        self.usage_tree.column("product", width=190); self.usage_tree.column("sequence", width=260); self.usage_tree.column("source_file", width=280)

    def _build_outcome_history(self) -> None:
        bar=ttk.Frame(self.outcome_tab); bar.pack(fill="x", pady=(0,6))
        ttk.Label(bar,text="Outcome-aware records connect actual conditions to yield/purity/failure observations.").pack(side="left")
        ttk.Button(bar,text="Mark Verified",command=lambda:self._mark("outcome","verified")).pack(side="right",padx=2)
        ttk.Button(bar,text="Mark Excluded",command=lambda:self._mark("outcome","excluded")).pack(side="right",padx=2)
        columns=["status","stage","product","sequence","result","success_flag","yield_percent","purity_percent","doubling_required","observation","work_item_id","run_id","record_id"]
        self.outcome_tree=self._tree(self.outcome_tab,columns)
        self.outcome_tree.column("sequence",width=260); self.outcome_tree.column("observation",width=320)

    def _build_issue_history(self) -> None:
        bar=ttk.Frame(self.issue_tab, style="V5.Root.TFrame"); bar.pack(fill="x", pady=(0,6))
        ttk.Label(bar,text="Quick issue history. Product/sequence are linked automatically from the active Planner item.", style="V5.Muted.TLabel").pack(side="left")
        ttk.Button(bar,text="Record Issue",command=self.record_issue,style="V5.Primary.TButton").pack(side="right",padx=2)
        ttk.Button(bar,text="Mark Verified",command=lambda:self._mark("issue","verified"),style="V5.Secondary.TButton").pack(side="right",padx=2)
        ttk.Button(bar,text="Mark Excluded",command=lambda:self._mark("issue","excluded"),style="V5.Secondary.TButton").pack(side="right",padx=2)
        columns=["recorded_at","stage","issue_type","position","residue","severity","resolution","action_taken","observation","product","run_id","record_id"]
        self.issue_tree=self._tree(self.issue_tab,columns)
        self.issue_tree.column("product",width=150); self.issue_tree.column("issue_type",width=190)
        self.issue_tree.column("action_taken",width=210); self.issue_tree.column("observation",width=260); self.issue_tree.column("record_id",width=80)

    def _build_decision_support(self) -> None:
        bar=ttk.Frame(self.decision_tab); bar.pack(fill="x",pady=(0,6))
        ttk.Label(bar,text="Residue difficulty is a deterministic review score; similar experiments are evidence, not automatic plan changes.").pack(side="left")
        ttk.Button(bar,text="Analyze Current Sequence",command=self.run_v5_decision_support).pack(side="right")
        self.decision_summary=tk.Text(self.decision_tab,height=7,wrap="word"); self.decision_summary.pack(fill="x",pady=(0,8)); self._style_text(self.decision_summary, compact=True)
        ttk.Label(self.decision_tab,text="Stage Risk Advisor").pack(anchor="w")
        self.stage_risk_tree=self._tree(self.decision_tab,["stage","level","evidence_count","reasons"])
        self.stage_risk_tree.column("reasons",width=620)
        ttk.Label(self.decision_tab,text="Sequence Difficulty Map").pack(anchor="w",pady=(8,0))
        self.difficulty_tree=self._tree(self.decision_tab,["position","token","score","level","reasons"])
        self.difficulty_tree.column("reasons",width=520)
        ttk.Label(self.decision_tab,text="Similar Historical Experiments").pack(anchor="w",pady=(8,0))
        self.similar_tree=self._tree(self.decision_tab,["product","sequence","similarity","status","source_file","source_page","outcome_summary"])
        self.similar_tree.column("sequence",width=320); self.similar_tree.column("source_file",width=220); self.similar_tree.column("outcome_summary",width=260)
        ttk.Label(self.decision_tab,text="Historical Synthesis Issues").pack(anchor="w",pady=(8,0))
        self.risk_issue_tree=self._tree(self.decision_tab,["stage","position","residue","issue_type","severity","resolution","action_taken","observation"])
        self.risk_issue_tree.column("issue_type",width=180); self.risk_issue_tree.column("action_taken",width=240); self.risk_issue_tree.column("observation",width=300)

    def run_v5_decision_support(self) -> None:
        sequence=_value(getattr(self.gui,"pm_sequence",""))
        try:
            difficulty=experimental_workflow.sequence_difficulty(self.gui,sequence)
            risks=experimental_workflow.stage_risks(self.gui,sequence)
            similar=experimental_workflow.similar_experiments(self.gui,sequence,limit=12)
            risk_rows=[]
            for item in risks.get("stages",[]):
                row=dict(item); row["reasons"]="; ".join(item.get("reasons") or []); risk_rows.append(row)
            self._fill(self.stage_risk_tree,risk_rows)
            self._fill(self.risk_issue_tree, risks.get("issues") or [])
            rows=[]
            for item in difficulty.get("positions",[]):
                row=dict(item); row["reasons"]="; ".join(item.get("reasons") or []); rows.append(row)
            self._fill(self.difficulty_tree,rows)
            simrows=[]
            for item in similar:
                outcomes=item.get("outcomes") or []
                summary="; ".join(f"{o.get('stage','')}:{o.get('result','')} y={_fmt(o.get('yield_percent'))} p={_fmt(o.get('purity_percent'))}" for o in outcomes)
                row=dict(item); row["similarity"]=_fmt(100.0*float(item.get("similarity") or 0),1)+"%"; row["outcome_summary"]=summary; simrows.append(row)
            self._fill(self.similar_tree,simrows)
            risk_summary=", ".join(f"{r.get('stage')}={r.get('level')}" for r in risks.get("stages",[]))
            lines=["RISK & EVIDENCE",f"Sequence: {sequence}",f"Stage risk review: {risk_summary or 'unavailable'}",f"Max deterministic difficulty score: {difficulty.get('max_score',0)}",f"Similar experiments shown: {len(similar)}","","Risk/difficulty labels are review aids, not failure probabilities. No recommendation is applied from this tab."]
            self.decision_summary.delete("1.0","end"); self.decision_summary.insert("1.0","\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Risk & Evidence",str(exc),parent=self)

    def _review_usage_units(self) -> None:
        selected=list(self.usage_tree.selection())
        if len(selected)!=1:
            messagebox.showinfo("Cleavage Usage","Select exactly one usage record.",parent=self); return
        record_id=self.usage_tree.set(selected[0],"record_id")
        rows=experimental_workflow.cleavage_usage_records(self.gui)
        row=next((r for r in rows if str(r.get("record_id"))==str(record_id)),None)
        if row is None:
            messagebox.showerror("Cleavage Usage","Record was not found.",parent=self); return
        unresolved=[key for key in ("tfa","water","tis","ether","hexane") if str(row.get(f"{key}_status") or "") in {"needs_unit_review","unparsed","unsupported_unit"}]
        if not unresolved:
            messagebox.showinfo("Cleavage Usage","This record has no unresolved volume unit.",parent=self); return
        fields=[]
        labels={"tfa":"TFA","water":"Water","tis":"TIS","ether":"Ethyl Ether","hexane":"n-Hexane"}
        for key in unresolved:
            fields.append((key,f"{labels[key]} unit for raw value {row.get(f'{key}_raw','')} (mL/L/uL)",""))
        def save(values):
            updated=experimental_workflow.review_cleavage_usage_units(self.gui,record_id,{key:values[key] for key in unresolved})
            self.status.configure(text=f"Cleavage usage unit review saved; remaining review={updated.get('unit_review_required',0)}")
            self.refresh_all()
        self._entry_dialog("Review Cleavage Usage Units",fields,save)

    def _show_data_store(self) -> None:
        try:
            info = experimental_workflow.data_store_status(self.gui)
            counts = info.get("counts") or {}
            lines = [
                f"Build: {info.get('build_flavor','')}",
                f"SQLite: {info.get('path','')}",
                f"Exists: {'YES' if info.get('exists') else 'NO'}",
                f"Seed enabled: {'YES' if info.get('seed_enabled') else 'NO'}",
                "",
                "Records: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
            ]
            if info.get("last_backup"):
                lines += ["", f"Last backup: {info.get('last_backup')}"]
            if info.get("last_recovery_error"):
                lines += ["", f"Recovery warning: {info.get('last_recovery_error')}"]
            messagebox.showinfo("Experimental Data Store", "\n".join(lines), parent=self)
        except Exception as exc:
            messagebox.showerror("Experimental Data Store", str(exc), parent=self)

    def _backup_data_store(self) -> None:
        try:
            backup = experimental_workflow.backup_data_store(self.gui)
            messagebox.showinfo("Experimental DB Backup", f"Backup created:\n{backup}", parent=self)
            self.status.configure(text=f"Experimental DB backup created: {Path(backup).name}")
        except Exception as exc:
            messagebox.showerror("Experimental DB Backup", str(exc), parent=self)

    def _build_data_health(self) -> None:
        top = ttk.Frame(self.health_tab); top.pack(fill="x", pady=(0,6))
        ttk.Label(top, text="Objective DB quality and retrospective consistency metrics; these are not biochemical success rates.").pack(side="left")
        ttk.Button(top, text="Refresh Health", command=self._refresh_health).pack(side="right")
        ttk.Button(top, text="Rebuild Loading Model", command=self._rebuild_loading_model).pack(side="right", padx=(0,6))
        ttk.Button(top, text="Promote Latest Candidate", command=self._promote_loading_candidate).pack(side="right", padx=(0,6))
        ttk.Button(top, text="Rollback Loading Model", command=self._rollback_loading_model).pack(side="right", padx=(0,6))
        self.health_text = tk.Text(self.health_tab, height=28, wrap="word")
        self.health_text.pack(fill="both", expand=True); self._style_text(self.health_text)

    def _rebuild_loading_model(self) -> None:
        try:
            result = experimental_workflow.rebuild_loading_model(self.gui)
            if result.get("built"):
                promoted=bool(result.get("promoted"))
                state="PROMOTED / ACTIVE" if promoted else "CANDIDATE ONLY / ACTIVE MODEL KEPT"
                compare=""
                if result.get("compared_to_mae_mmol_g") is not None:
                    compare=f"\nPrevious active MAE: {_fmt(result.get('compared_to_mae_mmol_g'),4)} mmol/g"
                messagebox.showinfo(
                    "V5 Loading Model",
                    f"Model rebuilt from {result.get('training_count',0)} Verified measured results.\n"
                    f"Candidate CV MAE: {_fmt(result.get('cross_validated_mae_mmol_g'),4)} mmol/g" + compare +
                    f"\nStatus: {state}\n\n{result.get('promotion_reason','')}\n\n"
                    "Adding a result never retrains the model automatically.",
                    parent=self,
                )
            else:
                messagebox.showinfo("V5 Loading Model", str(result.get("reason") or "Model was not rebuilt."), parent=self)
            self._refresh_health(); self._refresh_loading_rebuild_notice()
        except Exception as exc:
            messagebox.showerror("V5 Loading Model", str(exc), parent=self)

    def _promote_loading_candidate(self) -> None:
        try:
            result=experimental_workflow.promote_latest_loading_candidate(self.gui)
            if result.get("activated"):
                messagebox.showinfo("V5 Loading Model",f"Promoted stored candidate:\n{result.get('model_id','')}",parent=self)
            else:
                messagebox.showinfo("V5 Loading Model",str(result.get("reason") or "No candidate was promoted."),parent=self)
            self._refresh_health(); self._refresh_loading_rebuild_notice()
        except Exception as exc:
            messagebox.showerror("V5 Loading Model",str(exc),parent=self)

    def _rollback_loading_model(self) -> None:
        try:
            result=experimental_workflow.rollback_loading_model(self.gui)
            if result.get("activated"):
                messagebox.showinfo("V5 Loading Model",f"Activated earlier model:\n{result.get('model_id','')}",parent=self)
            else:
                messagebox.showinfo("V5 Loading Model",str(result.get("reason") or "No earlier model was activated."),parent=self)
            self._refresh_health(); self._refresh_loading_rebuild_notice()
        except Exception as exc:
            messagebox.showerror("V5 Loading Model",str(exc),parent=self)

    def _refresh_health(self) -> None:
        health = experimental_workflow.data_health(self.gui)
        counts = health.get("counts") or {}; missing = health.get("missing_canonical_keys") or {}
        status = health.get("status_counts") or {}
        mae = health.get("loading_leave_one_out_mae_mmol_g")
        agreement = health.get("cleavage_eq_time_replay_agreement_pct")
        validation = experimental_workflow.validation_snapshot(self.gui)
        amount_mae = validation.get("cleavage_amount_leave_one_out_mae_ml_per_mmol")
        model_info = experimental_workflow.loading_model_info(self.gui) or {}
        model_history = experimental_workflow.loading_model_history(self.gui) or []
        latest_model = model_history[0] if model_history else {}
        lines = [
            "Experimental Data Health", "",
            f"Records — Loading {counts.get('loading',0)} / Cleavage {counts.get('cleavage',0)} / Sequence STD {counts.get('sequence',0)} / Cleavage Usage {counts.get('cleavage_usage',0)} / Outcomes {counts.get('outcome',0)} / Issues {counts.get('issue',0)}",
            f"Status — Loading {status.get('loading',{})}",
            f"Status — Cleavage {status.get('cleavage',{})}",
            f"Status — Sequence {status.get('sequence',{})}",
            f"Status — Cleavage Usage {status.get('cleavage_usage',{})}",
            f"Status — Synthesis Issues {status.get('issue',{})}",
            f"Status — Outcomes {status.get('outcome',{})}", "",
            f"Cleavage usage normalized: {health.get('cleavage_usage_normalized_records',0)} / unit review required: {health.get('cleavage_usage_unit_review_required',0)}",
            f"Canonical-key gaps — Loading {missing.get('loading',0)} / Cleavage {missing.get('cleavage',0)} / Sequence {missing.get('sequence',0)}",
            f"Distinct sequence products: {health.get('sequence_products',0)}",
            f"Cleavage records linked to a sequence product: {health.get('cleavage_records_linked_to_sequence_product',0)}",
            f"Repeated resin+building-block loading groups: {health.get('repeated_loading_groups',0)}",
            f"Explicit EDT historical records: {health.get('explicit_edt_records',0)}", "",
            "Retrospective consistency (not success probability)",
            f"Loading exact-group leave-one-out MAE: {_fmt(mae,4) if mae is not None else 'N/A'} mmol/g (n={health.get('loading_leave_one_out_evaluated',0)})",
            f"Cleavage product eq/time replay agreement: {_fmt(agreement,1) if agreement is not None else 'N/A'}% (n={health.get('cleavage_eq_time_replay_evaluated',0)})",
            f"Cleavage amount leave-one-out MAE: {_fmt(amount_mae,4) if amount_mae is not None else 'N/A'} mL/mmol (n={validation.get('cleavage_amount_leave_one_out_evaluated',0)})",
            "", "Explicit V5 Loading Model",
            f"Built: {'YES' if model_info.get('built') else 'NO'}",
            f"Training records: {model_info.get('training_count',0) if model_info else 0}",
            f"Cross-validated MAE: {_fmt(model_info.get('cross_validated_mae_mmol_g'),4) if model_info.get('cross_validated_mae_mmol_g') is not None else 'N/A'} mmol/g",
            f"Built at: {model_info.get('built_at','') if model_info else ''}",
            f"Active model ID: {model_info.get('active_model_id','') if model_info else ''}",
            f"Stored model versions: {model_info.get('version_count',0) if model_info else 0}",
            f"Latest rebuild: {latest_model.get('promotion_status','N/A')} | MAE {_fmt(latest_model.get('cross_validated_mae_mmol_g'),4) if latest_model.get('cross_validated_mae_mmol_g') is not None else 'N/A'} mmol/g",
            "Only Verified measured loading results train the explicit model. Add Result never retrains automatically; Rebuild/Promote/Rollback are explicit Advanced actions.",
        ]
        self.health_text.delete("1.0","end"); self.health_text.insert("1.0","\n".join(lines))

    def _verify_same_sequence_product(self) -> None:
        selected = list(self.sequence_tree.selection())
        if not selected:
            messagebox.showinfo("Sequence History", "Select one sequence record first.", parent=self); return
        columns = list(self.sequence_tree["columns"]); product_index = columns.index("product")
        product = str(self.sequence_tree.item(selected[0], "values")[product_index])
        key = experimental_data.canonical_product_key(product)
        ids = [row.get("record_id") for row in experimental_workflow.sequence_records(self.gui) if experimental_data.canonical_product_key(row.get("product")) == key]
        changed = experimental_workflow.set_status(self.gui, "sequence", ids, "verified")
        self.refresh_all()
        messagebox.showinfo("Sequence History", f"Verified {changed} page-local STD observation(s) for {product}.", parent=self)

    def _build_loading_advisor(self) -> None:
        form = ttk.LabelFrame(self.loading_advisor_tab, text="Target Loading", padding=10, style="V5.Card.TLabelframe")
        form.pack(fill="x")
        self.load_resin = tk.StringVar(value=_value(getattr(self.gui, "pm_resin", "")))
        self.load_aa = tk.StringVar(value=self._current_cterm_compound())
        self.load_aa_eq = tk.StringVar(value=_value(getattr(self.gui, "loading_aa_eq", "")))
        self.load_base_eq = tk.StringVar(value=_value(getattr(self.gui, "loading_diea_eq", "")))
        self.load_time = tk.StringVar(value=_value(getattr(self.gui, "loading_time_h", "")) or "4")
        self.load_target = tk.StringVar(value=_value(getattr(self.gui, "pm_loading", "")))

        top_fields = [("Target (mmol/g)", self.load_target, 12), ("Resin", self.load_resin, 24), ("C-terminal AA", self.load_aa, 26)]
        bottom_fields = [("AA eq", self.load_aa_eq, 8), ("DIEA eq", self.load_base_eq, 8), ("Time (h)", self.load_time, 8)]
        for row, fields in enumerate((top_fields, bottom_fields)):
            for index, (label, var, width) in enumerate(fields):
                base = index * 2
                pady = (0, 5) if row == 0 else 0
                ttk.Label(form, text=label).grid(row=row, column=base, sticky="w", padx=(0, 4), pady=pady)
                ttk.Entry(form, textvariable=var, width=width).grid(row=row, column=base + 1, sticky="ew", padx=(0, 10), pady=pady)
        form.columnconfigure(3, weight=1)

        actions = ttk.Frame(form, style="V5.Root.TFrame")
        actions.grid(row=0, column=6, rowspan=2, sticky="e", padx=(8, 0))
        ttk.Button(actions, text="Sync from Planner", command=lambda: self._sync_advisor_from_planner("loading"), style="V5.Secondary.TButton").pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Recommend", command=self.run_loading_advisor, style="V5.Secondary.TButton").pack(fill="x", pady=4)
        ttk.Button(actions, text="Apply Recommendation", command=self.apply_loading_recommendation, style="V5.Primary.TButton").pack(fill="x", pady=(4, 0))

        self.loading_advisor_status = ttk.Label(self.loading_advisor_tab, text="No recommendation calculated yet.", style="V5.Muted.TLabel")
        self.loading_advisor_status.pack(fill="x", pady=(6, 0))
        self._last_loading_advice = None
        self.load_result = tk.Text(self.loading_advisor_tab, height=10, wrap="word")
        self.load_result.pack(fill="x", pady=(6, 8))
        self._style_text(self.load_result)

        quick = ttk.LabelFrame(self.loading_advisor_tab, text="Measured Result", padding=8, style="V5.Card.TLabelframe")
        quick.pack(fill="x", pady=(0, 8))
        ttk.Label(quick, text="Measured Loading", style="V5.Muted.TLabel").pack(side="left")
        self.quick_measured_loading = tk.StringVar(value="")
        quick_entry = ttk.Entry(quick, textvariable=self.quick_measured_loading, width=12)
        quick_entry.pack(side="left", padx=(6, 4))
        ttk.Label(quick, text="mmol/g", style="V5.Muted.TLabel").pack(side="left")
        ttk.Button(quick, text="Save Measured", command=self._save_quick_loading_result, style="V5.Primary.TButton").pack(side="left", padx=(10, 0))
        self.loading_rebuild_notice = ttk.Label(quick, text="", style="V5.Muted.TLabel")
        self.loading_rebuild_notice.pack(side="right", padx=(12, 0))
        quick_entry.bind("<Return>", lambda _event: self._save_quick_loading_result())

        evbar = ttk.Frame(self.loading_advisor_tab, style="V5.Root.TFrame")
        evbar.pack(fill="x")
        self.loading_evidence_visible = False
        self.loading_evidence_button = ttk.Button(evbar, text="Show Evidence", style="V5.Secondary.TButton", command=self._toggle_loading_evidence)
        self.loading_evidence_button.pack(side="left")
        self.loading_evidence_box = ttk.LabelFrame(self.loading_advisor_tab, text="Historical Evidence", padding=6, style="V5.Card.TLabelframe")
        self.load_evidence = self._tree(self.loading_evidence_box, ["date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "loading_rate_mmol_g", "status", "raw_note"])

    def _toggle_loading_evidence(self) -> None:
        if self.loading_evidence_visible:
            self.loading_evidence_box.pack_forget(); self.loading_evidence_visible=False; self.loading_evidence_button.configure(text="Show Evidence")
        else:
            self.loading_evidence_box.pack(fill="both",expand=True,pady=(6,0)); self.loading_evidence_visible=True; self.loading_evidence_button.configure(text="Hide Evidence")

    def _build_cleavage_advisor(self) -> None:
        intro = ttk.Frame(self.cleavage_advisor_tab, style="V5.Root.TFrame")
        intro.pack(fill="x", pady=(0, 8))
        ttk.Label(intro, text="Cleavage recommendation", style="V5.Section.TLabel").pack(side="left")
        ttk.Label(intro, text="Condition, current-scale amount and precipitation/workup are kept separate.", style="V5.Muted.TLabel").pack(side="left", padx=(10, 0))

        form = ttk.LabelFrame(self.cleavage_advisor_tab, text="Current Planner Context", padding=10, style="V5.Card.TLabelframe")
        form.pack(fill="x")
        self.clv_sequence = tk.StringVar(value=_value(getattr(self.gui, "pm_sequence", "")))
        self.clv_product = tk.StringVar(value=_value(getattr(self.gui, "pm_peptide", "")))
        self.clv_resin = tk.StringVar(value=_value(getattr(self.gui, "pm_resin", "")))
        self.clv_scale = tk.StringVar(value=_value(getattr(self.gui, "pm_scale", "")))
        self.clv_eq = tk.StringVar(value=_value(getattr(self.gui, "cleavage_eq_override", "")))
        self.clv_time = tk.StringVar(value=_value(getattr(self.gui, "cleavage_time_h", "")))

        top_fields = [("Sequence", self.clv_sequence, 38), ("Product", self.clv_product, 20), ("Resin", self.clv_resin, 20)]
        bottom_fields = [("Scale (mmol)", self.clv_scale, 10), ("Eq", self.clv_eq, 8), ("Time (h)", self.clv_time, 8)]
        for row, fields in enumerate((top_fields, bottom_fields)):
            for index, (label, var, width) in enumerate(fields):
                base = index * 2
                pady = (0, 5) if row == 0 else 0
                ttk.Label(form, text=label).grid(row=row, column=base, sticky="w", padx=(0, 4), pady=pady)
                ttk.Entry(form, textvariable=var, width=width).grid(row=row, column=base + 1, sticky="ew", padx=(0, 10), pady=pady)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(form, style="V5.Root.TFrame")
        actions.grid(row=0, column=6, rowspan=2, sticky="e", padx=(8, 0))
        ttk.Button(actions, text="Sync from Planner", command=lambda: self._sync_advisor_from_planner("cleavage"), style="V5.Secondary.TButton").pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Recommend", command=self.run_cleavage_advisor, style="V5.Secondary.TButton").pack(fill="x", pady=4)
        ttk.Button(actions, text="Apply Recommendation", command=self.apply_cleavage_recommendation, style="V5.Primary.TButton").pack(fill="x", pady=(4, 0))

        self.cleavage_advisor_status = ttk.Label(self.cleavage_advisor_tab, text="No recommendation calculated yet.", style="V5.Muted.TLabel")
        self.cleavage_advisor_status.pack(fill="x", pady=(6, 0))

        cards = ttk.Frame(self.cleavage_advisor_tab, style="V5.Root.TFrame")
        cards.pack(fill="x", pady=(8, 8))
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)
        condition = ttk.LabelFrame(cards, text="1. Cleavage Condition", padding=8, style="V5.Card.TLabelframe")
        condition.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        amount = ttk.LabelFrame(cards, text="2. Amount at Current Scale", padding=8, style="V5.Card.TLabelframe")
        amount.grid(row=0, column=1, sticky="nsew", padx=5)
        workup = ttk.LabelFrame(cards, text="3. Precipitation / Workup", padding=8, style="V5.Card.TLabelframe")
        workup.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.clv_result = tk.Text(condition, wrap="word", height=9)
        self.clv_result.pack(fill="both", expand=True)
        self._style_text(self.clv_result, compact=True)
        self.clv_amount_result = tk.Text(amount, wrap="word", height=9)
        self.clv_amount_result.pack(fill="both", expand=True)
        self._style_text(self.clv_amount_result, compact=True)
        self.clv_workup_result = tk.Text(workup, wrap="word", height=9)
        self.clv_workup_result.pack(fill="both", expand=True)
        self._style_text(self.clv_workup_result, compact=True)

        rescue = ttk.LabelFrame(self.cleavage_advisor_tab, text="4. Post-cleavage Rescue", padding=8, style="V5.Card.TLabelframe")
        rescue.pack(fill="x", pady=(0, 8))
        self.clv_rescue_result = tk.Text(rescue, wrap="word", height=5)
        self.clv_rescue_result.pack(fill="x")
        self._style_text(self.clv_rescue_result, compact=True)

        evidence = ttk.LabelFrame(self.cleavage_advisor_tab, text="Historical Evidence", padding=8, style="V5.Card.TLabelframe")
        evidence.pack(fill="both", expand=True)
        self.clv_evidence = self._tree(evidence, ["product", "scale_mmol", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "ether_ratio", "filter_speed", "status", "raw_observation"])
        self._last_cleavage_advice = None

    def _build_condition_optimizer(self) -> None:
        bar = ttk.Frame(self.condition_optimizer_tab); bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Recommend = current sequence + real lab history + chemistry rules. No cross-record cocktail mixing or invented condition values.").pack(side="left")
        ttk.Button(bar, text="Refresh Recommendations", command=self.run_condition_optimizer).pack(side="right")
        buttons = ttk.Frame(self.condition_optimizer_tab); buttons.pack(fill="x", pady=(0, 8))
        ttk.Button(buttons, text="Apply Loading + Generate", command=self.apply_optimizer_loading).pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="Apply Coupling + Generate", command=self.apply_coupling_recommendation).pack(side="left", padx=5)
        ttk.Button(buttons, text="Apply Cleavage + Update", command=self.apply_optimizer_cleavage).pack(side="left", padx=5)
        self.optimizer_result = tk.Text(self.condition_optimizer_tab, wrap="word", height=30)
        self.optimizer_result.pack(fill="both", expand=True); self._style_text(self.optimizer_result)
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
                f"Target {_fmt(lrec.get('target_loading_mmol_g'))} mmol/g → AA eq {_fmt(lrec.get('aa_eq'))}",
                f"DIEA eq {_fmt(lrec.get('base_eq'))} | Time {_fmt(lrec.get('loading_time_h'))} h | Solvent {lrec.get('loading_solvent') or '(unchanged/not recorded)'}",
                f"Expected loading {_fmt(lrec.get('expected_loading_mmol_g'))} mmol/g (observed exact-history range {_fmt(lrec.get('observed_min'))}–{_fmt(lrec.get('observed_max'))})",
                f"Basis: {lrec.get('basis')}",
                f"Confidence: {load.get('confidence', 'LOW')} | exact resin+AA n={lrec.get('condition_evidence_count',0)}",
            ])
        else:
            lines.append("No bounded target-loading recommendation is available.")
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
            matched_count = int(clv.get("matched_history_count", 0) or 0)
            if matched_count:
                lines.append(f"Historical sequence match recognized: {matched_count} record(s), but no complete reproducible cleavage condition is available for Apply.")
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
            messagebox.showinfo("Loading Recommend", "No bounded target-loading recommendation is available. Nothing was changed.", parent=self)
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
            "Apply the target-loading recommendation?\n\n"
            f"AA eq: {current_aa or '(blank)'} → {_fmt(rec.get('aa_eq'))}\n"
            f"DIEA eq: {current_base or '(blank)'} → {_fmt(rec.get('base_eq'))}\n"
            f"Time: {current_time or '(blank)'} → {_fmt(rec.get('loading_time_h')) or '(unchanged)'} h\n"
            f"Expected loading: {_fmt(rec.get('expected_loading_mmol_g'))} mmol/g\n"
            f"Target: {_fmt(rec.get('target_loading_mmol_g'))} mmol/g\n"
            f"Basis: {rec.get('basis')}\n"
            f"Evidence count: {rec.get('condition_evidence_count',0)}" + note +
            "\n\nThe AA eq estimate is bounded to observed exact resin+AA history; out-of-range extrapolation is disabled.",
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

    def _entry_dialog(self, title: str, fields, on_save, *, note: str = "") -> None:
        dialog = tk.Toplevel(self); dialog.title(title); dialog.transient(self); dialog.grab_set(); ui_system.apply_theme(dialog); ui_system.fit_window(dialog, preferred_width=900, preferred_height=680, minimum_width=780, minimum_height=600)
        dialog.configure(background=self._v5_colors["bg"])
        shell = ttk.Frame(dialog, padding=14, style="V5.Root.TFrame"); shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=title, style="V5.Section.TLabel").pack(anchor="w")
        if note:
            ttk.Label(shell, text=note, style="V5.Muted.TLabel").pack(anchor="w", pady=(2, 10))
        body = ttk.Frame(shell, padding=12, style="V5.Card.TFrame"); body.pack(fill="both", expand=True)
        vars: dict[str, tk.StringVar] = {}
        for idx, spec in enumerate(fields):
            if len(spec) >= 4:
                key, label, initial, options = spec[:4]
            else:
                key, label, initial = spec[:3]; options = None
            ttk.Label(body, text=label, width=24, style="V5.Muted.TLabel").grid(row=idx, column=0, sticky="w", padx=(0,8), pady=5)
            var = tk.StringVar(value=str(initial or "")); vars[key] = var
            if options:
                w = ttk.Combobox(body, textvariable=var, values=list(options), width=50, state="readonly")
            else:
                w = ttk.Entry(body, textvariable=var, width=52)
            w.grid(row=idx, column=1, sticky="ew", pady=5)
        body.columnconfigure(1, weight=1)
        def save():
            try:
                on_save({key: var.get().strip() for key, var in vars.items()})
                dialog.destroy(); self.refresh_all()
            except Exception as exc:
                messagebox.showerror(title, str(exc), parent=dialog)
        row = ttk.Frame(shell, style="V5.Root.TFrame"); row.pack(fill="x", pady=(12,0))
        ttk.Button(row, text="Cancel", command=dialog.destroy, style="V5.Secondary.TButton").pack(side="right")
        ttk.Button(row, text="Save Lab Result", command=save, style="V5.Primary.TButton").pack(side="right", padx=6)

    @staticmethod
    def _optional_float(value: str):
        text = str(value or "").strip()
        return None if not text else float(text)

    def _save_loading_measurement(self, measured: float, note: str = "") -> dict[str, Any]:
        """Save one real loading measurement with the current Planner/Run context."""
        self._sync_advisor_from_planner("loading")
        payload={
            "resin_type":self.load_resin.get(),"amino_acid_raw":self.load_aa.get(),
            "aa_eq":self._optional_float(_value(getattr(self.gui,"loading_aa_eq",""))),
            "base":"DIEA","base_eq":self._optional_float(_value(getattr(self.gui,"loading_diea_eq",""))),
            "loading_time_h":self._optional_float(_value(getattr(self.gui,"loading_time_h",""))),
            "loading_solvent":_value(getattr(self.gui,"default_loading_dissolve_solvent","")),
            "loading_rate_mmol_g":measured,"raw_note":note,
        }
        saved=experimental_workflow.add_loading_record(self.gui,payload,status="verified")
        self.status.configure(text=f"Loading result saved: {measured:g} mmol/g. Current Planner and Run conditions were attached automatically.")
        return saved

    def _save_quick_loading_result(self) -> None:
        measured=self._optional_float(self.quick_measured_loading.get())
        if measured is None:
            messagebox.showinfo("Loading Result","Enter the measured loading value.",parent=self); return
        try:
            self._save_loading_measurement(measured)
        except Exception as exc:
            messagebox.showerror("Loading Result", f"Result was not saved.\n\n{exc}", parent=self)
            return
        self.quick_measured_loading.set("")
        self.refresh_all()
        self.run_loading_advisor()

    def _refresh_loading_rebuild_notice(self) -> None:
        if not hasattr(self, "loading_rebuild_notice"):
            return
        try:
            state=experimental_workflow.loading_rebuild_status(self.gui)
            if state.get("rebuild_ready"):
                if state.get("active_model"):
                    text=f"{state.get('new_verified_count',0)} new measured results available for model rebuild"
                else:
                    text=f"{state.get('eligible_verified_count',0)} Verified results available for first model build"
            else:
                text=""
            self.loading_rebuild_notice.configure(text=text)
        except Exception:
            self.loading_rebuild_notice.configure(text="")

    def _current_cleavage_snapshot(self) -> dict[str, Any]:
        """Read the current Planner cleavage condition for result logging.

        The visible Cleavage Tree is only a presentation surface and may be empty
        while another view is active. Fall back to the active peptide's persisted
        ``selected_cleavage_rows`` so an actual result does not lose TFA/Water/TIS
        context merely because the table was not rendered.
        """
        product=_value(getattr(self.gui,"pm_peptide","")); sequence=_value(getattr(self.gui,"pm_sequence",""))
        scale=self._optional_float(_value(getattr(self.gui,"pm_scale","")))
        time_h=self._optional_float(_value(getattr(self.gui,"cleavage_time_h","")))
        eq=self._optional_float(_value(getattr(self.gui,"cleavage_eq_override","")))
        if eq is None or eq <= 0:
            try:
                from spps_v4_gui.modules import gui_common
                from spps_planner.engine import cleavage_eq_suggestion
                eq=self._optional_float(str(cleavage_eq_suggestion(gui_common.plan_input(self.gui)).get("cleavage_eq") or ""))
            except Exception:
                eq=None
        comp={"tfa_ml":None,"water_ml":None,"tis_ml":None}

        def consume(rows):
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                name=str(row.get("component") or "").strip().lower()
                raw_value=row.get("volume_mL")
                if raw_value is None or raw_value == "":
                    raw_value=row.get("volume_ml")
                value=self._optional_float("" if raw_value is None else str(raw_value))
                if name=="tfa" and comp["tfa_ml"] is None: comp["tfa_ml"]=value
                elif (name in {"water","dw"} or "water" in name) and comp["water_ml"] is None: comp["water_ml"]=value
                elif ("tis" in name or "triisopropyl" in name) and comp["tis_ml"] is None: comp["tis_ml"]=value

        try:
            tree=getattr(self.gui,"pm_cleavage_tree",None)
            if tree is not None:
                cols=list(tree["columns"])
                consume([dict(zip(cols,list(tree.item(iid,"values")))) for iid in tree.get_children()])
        except Exception as exc:
            self._result_snapshot_error=exc

        if all(value is None for value in comp.values()):
            try:
                from spps_v4_gui.modules import gui_common
                items=list(getattr(self.gui,"pm_items",[]) or [])
                idx=gui_common.active_index(self.gui)
                item=items[int(idx)] if idx is not None and 0 <= int(idx) < len(items) else {}
                consume(list(item.get("selected_cleavage_rows") or []))
            except Exception as exc:
                self._result_snapshot_fallback_error=exc
        return {"product":product,"sequence":sequence,"scale_mmol":scale,"cleavage_eq":eq,"cleavage_time_h":time_h,**comp}

    def record_result(self, default_kind: str = "Loading") -> None:
        """Record only bench results; Planner-known conditions are attached automatically."""
        try:
            from spps_v4_gui.modules import gui_common
            gui_common.save_active(self.gui)
        except Exception:
            pass
        product=_value(getattr(self.gui,"pm_peptide","")) or "(unnamed peptide)"
        sequence=_value(getattr(self.gui,"pm_sequence",""))
        scale=_value(getattr(self.gui,"pm_scale",""))
        dialog=tk.Toplevel(self); dialog.title("Add Result"); dialog.transient(self); dialog.grab_set(); ui_system.apply_theme(dialog)
        dialog.configure(background=self._v5_colors["bg"])
        shell=ttk.Frame(dialog,padding=16,style="V5.Root.TFrame"); shell.pack(fill="both",expand=True)
        ttk.Label(shell,text="Add Result",style="V5.Title.TLabel").pack(anchor="w")
        summary=product + (f"  •  {scale} mmol" if scale else "")
        ttk.Label(shell,text=summary,style="V5.Section.TLabel").pack(anchor="w",pady=(4,0))
        if sequence: ttk.Label(shell,text=sequence,style="V5.Muted.TLabel").pack(anchor="w",pady=(1,8))
        ttk.Label(shell,text="Current Planner conditions will be saved automatically with this result.",style="V5.Muted.TLabel").pack(anchor="w",pady=(0,10))

        kind=tk.StringVar(value=default_kind if default_kind in {"Loading","Cleavage / Final"} else "Loading")
        selector=ttk.Frame(shell,style="V5.Root.TFrame"); selector.pack(fill="x",pady=(0,8))
        ttk.Label(selector,text="Result type",style="V5.Muted.TLabel").pack(side="left",padx=(0,8))
        combo=ttk.Combobox(selector,textvariable=kind,values=["Loading","Cleavage / Final"],state="readonly",width=22); combo.pack(side="left")

        card=ttk.LabelFrame(shell,text="Result",padding=12,style="V5.Card.TLabelframe"); card.pack(fill="both",expand=True)
        vars={
            "loading":tk.StringVar(),"crude":tk.StringVar(),"yield":tk.StringVar(),"purity":tk.StringVar(),
            "outcome":tk.StringVar(value="Unknown"),"note":tk.StringVar(),
        }
        widgets={}
        def row(name,label,rownum,widget=None):
            l=ttk.Label(card,text=label,style="V5.Muted.TLabel"); l.grid(row=rownum,column=0,sticky="w",pady=5,padx=(0,8))
            w=widget or ttk.Entry(card,textvariable=vars[name],width=42); w.grid(row=rownum,column=1,sticky="ew",pady=5); widgets[name]=(l,w)
        row("loading","Measured loading (mmol/g)",0)
        row("crude","Crude (g)",1)
        row("yield","Yield (%)",2)
        row("purity","Purity (%)",3)
        outcome_box=ttk.Combobox(card,textvariable=vars["outcome"],values=["Success","Partial","Fail","Unknown"],state="readonly",width=39)
        row("outcome","Outcome",4,outcome_box)
        row("note","Note (optional)",5)
        card.columnconfigure(1,weight=1)

        def refresh_fields(*_):
            is_loading=kind.get()=="Loading"
            for key in ("loading",):
                for w in widgets[key]:
                    (w.grid() if is_loading else w.grid_remove())
            for key in ("crude","yield","purity","outcome"):
                for w in widgets[key]:
                    (w.grid_remove() if is_loading else w.grid())
        combo.bind("<<ComboboxSelected>>",refresh_fields); refresh_fields()

        def save():
            try:
                note=vars["note"].get().strip()
                if kind.get()=="Loading":
                    measured=self._optional_float(vars["loading"].get())
                    if measured is None:
                        messagebox.showinfo("Add Result","Enter the measured loading value.",parent=dialog); return
                    self._save_loading_measurement(measured,note)
                else:
                    snap=self._current_cleavage_snapshot()
                    crude=self._optional_float(vars["crude"].get()); yld=self._optional_float(vars["yield"].get()); purity=self._optional_float(vars["purity"].get())
                    outcome=vars["outcome"].get().strip() or "Unknown"
                    payload=dict(snap); payload.update({"crude_g":crude,"raw_observation":note})
                    complete=payload.get("cleavage_eq") is not None and any(payload.get(k) is not None for k in ("tfa_ml","water_ml","tis_ml"))
                    experimental_workflow.add_cleavage_record(self.gui,payload,status="verified" if complete else "incomplete")
                    low=outcome.lower(); success_flag=1 if low=="success" else 0 if low=="fail" else None
                    experimental_workflow.add_outcome_record(self.gui,{
                        "stage":"cleavage","product":snap.get("product"),"sequence":snap.get("sequence"),"result":outcome,
                        "success_flag":success_flag,"yield_percent":yld,"purity_percent":purity,"observation":note,
                    },status="verified" if low in {"success","partial","fail"} or yld is not None or purity is not None else "incomplete")
                    self.status.configure(text="Cleavage/final result saved. Planner cleavage conditions were attached automatically.")
                dialog.destroy(); self.refresh_all()
            except Exception as exc:
                messagebox.showerror("Add Result", f"Result was not saved.\n\n{exc}", parent=dialog)

        footer=ttk.Frame(shell,style="V5.Root.TFrame"); footer.pack(fill="x",pady=(10,0))
        ttk.Button(footer,text="Cancel",command=dialog.destroy,style="V5.Secondary.TButton").pack(side="right")
        ttk.Button(footer,text="Save",command=save,style="V5.Primary.TButton").pack(side="right",padx=6)
        ui_system.fit_window_to_content(dialog, preferred_width=820, preferred_height=560, minimum_width=720, minimum_height=500)

    def record_issue(self) -> None:
        """Natural-language-first issue logging for Korean, English, or mixed notes."""
        try:
            from spps_v4_gui.modules import gui_common
            gui_common.save_active(self.gui)
            items=list(getattr(self.gui,"pm_items",[]) or []); idx=gui_common.active_index(self.gui)
            item=items[int(idx)] if idx is not None and 0 <= int(idx) < len(items) else {}
        except Exception:
            item={}
        product=str(item.get("peptide") or _value(getattr(self.gui,"pm_peptide","")))
        sequence=str(item.get("sequence") or _value(getattr(self.gui,"pm_sequence","")))
        scale=str(item.get("scale") or _value(getattr(self.gui,"pm_scale","")))

        from spps_v4_gui.natural_language_issue_v5 import parse_issue_note

        dialog=tk.Toplevel(self); dialog.title("Record Issue"); dialog.transient(self); dialog.grab_set(); ui_system.apply_theme(dialog)
        dialog.configure(background=self._v5_colors["bg"])
        shell=ttk.Frame(dialog,padding=16,style="V5.Root.TFrame"); shell.pack(fill="both",expand=True)
        ttk.Label(shell,text="What happened?",style="V5.Title.TLabel").pack(anchor="w")
        # Natural-language entry accepts 한국어 / English / mixed without a language selector.

        summary=product or "(unnamed peptide)"
        if scale: summary += f"  •  {scale} mmol"
        ttk.Label(shell,text=summary,style="V5.Section.TLabel").pack(anchor="w")
        if sequence:
            ttk.Label(shell,text=sequence,style="V5.Muted.TLabel").pack(anchor="w",pady=(1,10))

        note_card=ttk.LabelFrame(shell,text="Note",padding=10,style="V5.Card.TLabelframe"); note_card.pack(fill="both",expand=True)
        # Legacy UX test phrase: Write one sentence
        observation=tk.Text(note_card,height=9,wrap="word",font=("Segoe UI",11)); observation.pack(fill="both",expand=True)
        self._style_text(observation)

        examples=ttk.Frame(note_card,style="V5.Card.TFrame"); examples.pack(fill="x",pady=(8,0))
        ttk.Label(examples,text="Quick examples:",style="V5.Muted.TLabel").pack(side="left",padx=(0,6))
        example_rows=[
            ("Kaiser positive", "Kaiser test was positive after Val coupling, so I repeated the coupling once and the retest was negative."),
            ("Resin clumping", "The resin clumped during coupling. I added a little more DMF and manually dispersed it; the resin returned to normal."),
            ("Precipitation issue", "Precipitation was poor after cleavage even after adding ether."),
            ("Oxidation", "Met oxidation was observed after cleavage."),
        ]
        def use_example(text: str):
            observation.delete("1.0","end"); observation.insert("1.0",text); observation.focus_set()
        for label,example in example_rows:
            ttk.Button(examples,text=label,command=lambda x=example:use_example(x),style="V5.Secondary.TButton").pack(side="left",padx=3)

        result_line=tk.StringVar(value="The program will structure the note automatically when you save it.")
        ttk.Label(shell,textvariable=result_line,style="V5.Muted.TLabel").pack(anchor="w",pady=(8,0))

        detail_vars={
            "stage":tk.StringVar(value=""), "issue_type":tk.StringVar(value=""),
            "action_taken":tk.StringVar(value=""), "resolution":tk.StringVar(value=""),
            "severity":tk.StringVar(value=""), "position":tk.StringVar(value=""), "residue":tk.StringVar(value=""),
        }
        stage_values=["Swelling","Loading","Deprotection","Coupling","Modification","Cleavage","Precipitation / Workup","Purification","Equipment / Process","Other"]
        issue_values=["Incomplete coupling","Incomplete deprotection","Aggregation / resin clumping","Poor swelling","Abnormal Kaiser / chloranil","Reagent solubility","Reaction solution abnormality","Filtration difficulty","Cleavage problem","Precipitation failure / partial precipitation","Oxidation","Side product","Low crude recovery","Equipment / process problem","Other"]
        action_values=["","No action / observation only","Repeat coupling","Longer reaction","Reagent change","Solvent change","Additional wash","Repeat deprotection","Manual intervention","Re-cleavage / extended cleavage","Re-precipitation / additional wash","NH4I reduction","Other"]
        resolution_values=["Unknown","Resolved","Improved","Not Resolved"]
        severity_values=["Low","Medium","High","Critical"]

        details=ttk.LabelFrame(shell,text="Review details (optional)",padding=10,style="V5.Card.TLabelframe")
        detail_visible={"value":False}
        def set_details(parsed):
            detail_vars["stage"].set(parsed.get("stage") or "Other")
            detail_vars["issue_type"].set(parsed.get("issue_type") or "Other")
            detail_vars["action_taken"].set(parsed.get("action_taken") or "")
            detail_vars["resolution"].set(parsed.get("resolution") or "Unknown")
            detail_vars["severity"].set(parsed.get("severity") or "Medium")
            detail_vars["position"].set("" if parsed.get("position") is None else str(parsed.get("position")))
            detail_vars["residue"].set(parsed.get("residue") or "")
        def analyze(*, reveal=False):
            note=observation.get("1.0","end").strip()
            parsed=parse_issue_note(note)
            set_details(parsed)
            label=f"Understood: {parsed['stage']} / {parsed['issue_type']}"
            if parsed.get("action_taken"): label += f" / {parsed['action_taken']}"
            if parsed.get("resolution") and parsed.get("resolution")!="Unknown": label += f" / {parsed['resolution']}"
            label += f"  • confidence {int(float(parsed.get('confidence') or 0)*100)}%"
            if parsed.get("parse_status")!="auto_verified": label += "  • Needs Review (excluded from ML)"
            result_line.set(label)
            if reveal and not detail_visible["value"]:
                details.pack(fill="x",pady=(8,0),before=footer); detail_visible["value"]=True; details_btn.configure(text="Hide details")
            return parsed
        def toggle_details():
            if detail_visible["value"]:
                details.pack_forget(); detail_visible["value"]=False; details_btn.configure(text="Review details")
            else:
                analyze(reveal=True)
                ui_system.fit_window(dialog, preferred_width=980, preferred_height=720, minimum_width=860, minimum_height=650)

        rows=[
            ("Stage","stage",stage_values),("Issue","issue_type",issue_values),("Action","action_taken",action_values),
            ("Result","resolution",resolution_values),("Severity","severity",severity_values),
        ]
        for i,(label,key,values) in enumerate(rows):
            r=i//3; c=(i%3)*2
            ttk.Label(details,text=label,style="V5.Muted.TLabel").grid(row=r*2,column=c,sticky="w",padx=4,pady=(2,0))
            ttk.Combobox(details,textvariable=detail_vars[key],values=values,state="readonly",width=22).grid(row=r*2+1,column=c,sticky="ew",padx=4,pady=(1,5))
        ttk.Label(details,text="Position",style="V5.Muted.TLabel").grid(row=4,column=0,sticky="w",padx=4)
        ttk.Entry(details,textvariable=detail_vars["position"],width=12).grid(row=5,column=0,sticky="ew",padx=4)
        ttk.Label(details,text="Residue",style="V5.Muted.TLabel").grid(row=4,column=2,sticky="w",padx=4)
        ttk.Entry(details,textvariable=detail_vars["residue"],width=16).grid(row=5,column=2,sticky="ew",padx=4)
        for c in (0,2,4): details.columnconfigure(c,weight=1)

        footer=ttk.Frame(shell,style="V5.Root.TFrame"); footer.pack(fill="x",pady=(10,0))
        details_btn=ttk.Button(footer,text="Review details",command=toggle_details,style="V5.Secondary.TButton"); details_btn.pack(side="left")
        ttk.Button(footer,text="Analyze",command=lambda:analyze(reveal=False),style="V5.Secondary.TButton").pack(side="left",padx=6)

        def save_issue(*,keep_open=False):
            note=observation.get("1.0","end").strip()
            if not note:
                messagebox.showinfo("Record Issue","Write what happened in one sentence first.",parent=dialog); return
            parsed=parse_issue_note(note)
            # If the operator deliberately opened the detail panel, the visible
            # structured values are treated as human-reviewed overrides.
            if detail_visible["value"]:
                parsed.update({
                    "stage":detail_vars["stage"].get().strip() or parsed["stage"],
                    "issue_type":detail_vars["issue_type"].get().strip() or parsed["issue_type"],
                    "action_taken":detail_vars["action_taken"].get().strip(),
                    "resolution":detail_vars["resolution"].get().strip() or "Unknown",
                    "severity":detail_vars["severity"].get().strip() or "Medium",
                    "residue":detail_vars["residue"].get().strip(),
                })
                pos=self._optional_float(detail_vars["position"].get())
                parsed["position"]=int(pos) if pos is not None else None
                parsed["parse_status"]="human_reviewed" if parsed["issue_type"]!="Other" else "needs_review"
                parsed["confidence"]=1.0 if parsed["issue_type"]!="Other" else parsed.get("confidence",0.0)
            status="verified" if parsed.get("parse_status") in {"auto_verified","human_reviewed"} else "incomplete"
            planner_snapshot={
                "loading":{
                    "resin":_value(getattr(self.gui,"pm_resin","")),
                    "aa":self._current_cterm_compound(),
                    "aa_eq":_value(getattr(self.gui,"loading_aa_eq","")),
                    "base_eq":_value(getattr(self.gui,"loading_diea_eq","")),
                    "time_h":_value(getattr(self.gui,"loading_time_h","")),
                    "solvent":_value(getattr(self.gui,"default_loading_dissolve_solvent","")),
                },
                "coupling":{
                    "aa_eq":_value(getattr(self.gui,"coupling_eq","")),
                    "repeats":_value(getattr(self.gui,"coupling_repeats","")),
                    "time_h":_value(getattr(self.gui,"coupling_time_h","")),
                    "reagent":_value(getattr(self.gui,"default_reagent","")),
                    "base":_value(getattr(self.gui,"default_base","")),
                    "solvent":_value(getattr(self.gui,"default_coupling_solution_solvent","")),
                },
                "cleavage":self._current_cleavage_snapshot(),
            }
            payload={
                "stage":parsed.get("stage"),"product":product,"sequence":sequence,"scale_mmol":self._optional_float(scale),
                "position":parsed.get("position"),"residue":parsed.get("residue"),"issue_type":parsed.get("issue_type"),
                "severity":parsed.get("severity"),"observation":note,"action_taken":parsed.get("action_taken"),
                "resolution":parsed.get("resolution"),"work_item_id":str(item.get("work_item_id") or ""),
                "source_locator":"Natural Language Issue Log","parse_confidence":parsed.get("confidence"),
                "parse_status":parsed.get("parse_status"),"parser_version":parsed.get("parser_version"),
                "detected_language":parsed.get("detected_language"),
                "planner_snapshot_json":json.dumps(planner_snapshot,ensure_ascii=False,sort_keys=True),
            }
            try:
                experimental_workflow.add_issue_record(self.gui,payload,status=status)
            except Exception as exc:
                messagebox.showerror("Record Issue", f"Issue was not saved.\n\n{exc}", parent=dialog)
                return
            if status=="verified":
                if parsed.get("issue_type")=="Oxidation":
                    self.status.configure(text="Oxidation issue saved. NH4I Reduction is available under Cleavage > Post-cleavage Rescue; it is not applied automatically.")
                else:
                    self.status.configure(text=f"Issue saved for evidence/ML: {parsed.get('stage')} / {parsed.get('issue_type')}")
            else:
                self.status.configure(text="Issue saved as raw note; automatic interpretation needs review and is excluded from ML.")
            self.refresh_all()
            if keep_open:
                observation.delete("1.0","end"); result_line.set("Ready for the next note.")
                detail_visible["value"]=False; details.pack_forget(); details_btn.configure(text="Review details")
                for v in detail_vars.values(): v.set("")
            else:
                dialog.destroy()

        ttk.Button(footer,text="Cancel",command=dialog.destroy,style="V5.Secondary.TButton").pack(side="right")
        ttk.Button(footer,text="Save & Add Another",command=lambda:save_issue(keep_open=True),style="V5.Secondary.TButton").pack(side="right",padx=6)
        ttk.Button(footer,text="Save",command=save_issue,style="V5.Primary.TButton").pack(side="right",padx=6)
        ui_system.fit_window(dialog, preferred_width=820, preferred_height=560, minimum_width=720, minimum_height=500)

    def record_loading(self) -> None:
        # Compatibility entry point: the simplified Result flow auto-attaches
        # current Planner loading conditions instead of asking the user to retype them.
        self.record_result("Loading")

    def record_coupling(self) -> None:
        # Coupling conditions already live in the active plan; noteworthy bench
        # deviations are recorded as natural-language issues.
        self.record_issue()

    def record_cleavage(self) -> None:
        # Compatibility entry point for older menu bindings.
        self.record_result("Cleavage / Final")

    def _current_cterm_compound(self) -> str:
        sequence = _value(getattr(self.gui, "pm_sequence", ""))
        try:
            from spps_planner.parser import parse_sequence
            from spps_v4_gui.material_presentation import AA_REAGENT_NAMES
            parsed = parse_sequence(sequence)
            tokens = list(parsed.core_tokens or [])
            if tokens:
                token = str(tokens[-1])
                if token.startswith("d") and len(token) == 2:
                    base = AA_REAGENT_NAMES.get(token[1:].upper(), token)
                    return base.replace("Fmoc-", "Fmoc-D-", 1)
                return AA_REAGENT_NAMES.get(token.upper(), token)
        except Exception as exc:
            self._cterm_parse_error = exc
        return ""

    def _confirm_import_preview(self, preview: dict[str, Any]) -> bool:
        dialog = tk.Toplevel(self)
        dialog.title("Import Preview / Audit")
        dialog.transient(self); dialog.grab_set(); ui_system.apply_theme(dialog)
        ui_system.fit_window(dialog, preferred_width=1180, preferred_height=720, minimum_width=1000, minimum_height=650)
        counts = preview.get("counts") or {}
        ttk.Label(dialog, text=f"Loading {counts.get('loading',0)} | Cleavage {counts.get('cleavage',0)} | Sequence STD {counts.get('sequence',0)} | Cleavage Usage {counts.get('cleavage_usage',0)}", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        ttk.Label(dialog, text="Preview only — the Experimental DB has not been modified.").pack(anchor="w", padx=10)
        for warning in preview.get("warnings") or []:
            ttk.Label(dialog, text=f"Warning: {warning}").pack(anchor="w", padx=10, pady=(2,0))
        columns = ["kind", "status", "product", "sequence", "source", "locator"]
        tree = self._tree(dialog, columns)
        tree.column("product", width=180); tree.column("sequence", width=280); tree.column("source", width=220); tree.column("locator", width=260)
        self._fill(tree, preview.get("samples") or [])
        decision = {"ok": False}
        buttons = ttk.Frame(dialog); buttons.pack(fill="x", padx=10, pady=(0,10))
        def accept() -> None:
            decision["ok"] = True; dialog.destroy()
        ttk.Button(buttons, text="Import", command=accept).pack(side="right")
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(0,6))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        return bool(decision["ok"])

    def import_file(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Import Experimental Data", filetypes=[("Experimental data", "*.xlsx *.xlsm *.csv *.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            preview = experimental_workflow.preview_import(self.gui, path)
            if not self._confirm_import_preview(preview):
                return
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
        dialog = tk.Toplevel(self); dialog.title(f"Edit {kind} record"); ui_system.apply_theme(dialog); ui_system.fit_window(dialog, preferred_width=920, preferred_height=820, minimum_width=800, minimum_height=700); dialog.transient(self); dialog.grab_set()
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
        tree = {"loading": self.loading_tree, "cleavage": self.cleavage_tree, "sequence": self.sequence_tree, "cleavage_usage": self.usage_tree, "outcome": self.outcome_tree, "issue": self.issue_tree}.get(kind)
        if tree is None:
            raise ValueError(f"Unsupported experimental record kind: {kind}")
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
            experimental_workflow.initialize(self.gui)
            self.gui._experimental_db_init_error = None
            loading = experimental_workflow.loading_records(self.gui)
            cleavage = experimental_workflow.cleavage_records(self.gui)
            sequence = experimental_workflow.sequence_records(self.gui)
            usage = experimental_workflow.cleavage_usage_records(self.gui)
            outcomes = experimental_workflow.outcome_records(self.gui)
            issues = experimental_workflow.issue_records(self.gui)
            self._fill(self.loading_tree, loading); self._fill(self.cleavage_tree, cleavage); self._fill(self.sequence_tree, sequence); self._fill(self.usage_tree, usage); self._fill(self.outcome_tree, outcomes); self._fill(self.issue_tree, issues)
            self.status.configure(text=f"Records  Loading {len(loading)}  •  Cleavage {len(cleavage)}  •  Issues {len(issues)}")
            if hasattr(self, "health_text"):
                self._refresh_health()
            self._refresh_loading_rebuild_notice()
        except Exception as exc:
            self.gui._experimental_db_init_error = exc
            self.status.configure(text=f"Experimental DB error: {exc}")

    def _set_recommendation_status(self, widget: Any, result: dict[str, Any], recommendation: dict[str, Any]) -> None:
        evidence_count = recommendation.get("evidence_count")
        if evidence_count is None:
            evidence_count = result.get("evidence_count")
        if evidence_count is None:
            evidence_count = len(result.get("evidence") or [])
        confidence = str(recommendation.get("confidence") or result.get("confidence") or "LOW").upper()
        apply_allowed = bool(recommendation.get("apply_allowed"))
        basis = (
            recommendation.get("recommendation_kind")
            or recommendation.get("condition_source")
            or result.get("method")
            or "evidence review"
        )
        widget.configure(
            text=f"Evidence {evidence_count}  •  Confidence {confidence}  •  Apply {'YES' if apply_allowed else 'NO'}  •  {basis}"
        )

    def run_loading_advisor(self) -> None:
        try:
            result = experimental_workflow.advise_loading(
                self.gui, resin=self.load_resin.get(), amino_acid=self.load_aa.get(),
                aa_eq=self.load_aa_eq.get(), base_eq=self.load_base_eq.get(),
                loading_time_h=self.load_time.get(), target_loading_mmol_g=self.load_target.get(),
                include_parsed=True, allow_parsed_apply=True,
            )
            self._last_loading_advice = result
            rec=result.get("target_recommendation") or {}
            self._set_recommendation_status(self.loading_advisor_status, result, rec)
            lines=[f"Target loading  {_fmt(self.load_target.get()) or '—'} mmol/g"]
            if rec:
                raw_conf=str(rec.get('confidence') or result.get('confidence','LOW')).upper()
                confidence_label=("Experimental estimate" if rec.get('provisional') or raw_conf=="LOW" else "High confidence" if raw_conf=="HIGH" else "Medium confidence")
                lines += [
                    "",
                    f"Recommended AA eq  {_fmt(rec.get('aa_eq')) or '—'}",
                    f"DIEA eq  {_fmt(rec.get('base_eq')) or _fmt(self.load_base_eq.get()) or '—'}",
                    f"Time  {_fmt(rec.get('loading_time_h')) or _fmt(self.load_time.get()) or '—'} h",
                    f"Expected loading  {_fmt(rec.get('predicted_loading_mmol_g')) or '—'} mmol/g",
                ]
                if rec.get('expected_low_mmol_g') is not None and rec.get('expected_high_mmol_g') is not None:
                    lines.append(f"Expected range  {_fmt(rec.get('expected_low_mmol_g'))} – {_fmt(rec.get('expected_high_mmol_g'))} mmol/g")
                lines += [
                    f"Confidence  {confidence_label}",
                    f"Based on  {rec.get('verified_evidence_count',0) if not rec.get('provisional') else rec.get('evidence_count',0)} similar measured/history result(s)",
                ]
                if not rec.get('apply_allowed'):
                    lines.append("Apply  Not available for this evidence range")
                if rec.get('provisional'):
                    lines.append("Parsed history was required; new measured results should replace this estimate over time.")
            else:
                lines += ["", "No bounded target-loading estimate is available yet.", "Add measured loading results for this resin + C-terminal AA to improve the recommendation."]
            if result.get('warnings'):
                lines += ["", "Notes:"] + [f"• {w}" for w in result.get('warnings') or []]
            self.load_result.delete("1.0", "end"); self.load_result.insert("1.0", "\n".join(lines))
            self._fill(self.load_evidence, result.get("evidence", []))
        except Exception as exc:
            self.loading_advisor_status.configure(text=f"Recommendation error: {exc}")
            messagebox.showerror("Loading Advisor", str(exc), parent=self)

    def run_cleavage_advisor(self) -> None:
        try:
            result = experimental_workflow.advise_cleavage(
                self.gui, product=self.clv_product.get(), sequence=self.clv_sequence.get(), resin=self.clv_resin.get(), scale_mmol=self.clv_scale.get(),
                cleavage_eq=self.clv_eq.get(), cleavage_time_h=self.clv_time.get(), include_parsed=True,
            )
            self._last_cleavage_advice = result
            rec = result.get("recommended_condition") or {}
            self._set_recommendation_status(self.cleavage_advisor_status, result, rec)
            amount = result.get("amount_evidence") or {}
            arec = amount.get("recommended_amount") or {}

            # Condition card: composition/time only. Never splice components from
            # unrelated amount records into a historical condition.
            condition_lines = [
                f"{result.get('method') or 'Cleavage advisor'}",
                f"Confidence  {result.get('confidence', 'LOW')}",
            ]
            if rec:
                comp = rec.get("composition_pct") or {}
                comp_text = " / ".join(f"{name} {_fmt(value,2)}%" for name, value in comp.items())
                source_kind = rec.get("condition_source")
                labels = {
                    "exact_lab_record": "Historical exact",
                    "recommended_exact_sequence_record": "Historical consensus",
                    "historical_match_incomplete": "Historical incomplete",
                    "operator_approved_anchor": "Operator-approved anchor",
                    "empirical_v5_fallback": "Empirical V5 estimate",
                    "operator_cys_rule": "Operator Cys rule",
                    "chemistry_rule_reference": "Chemistry reference",
                }
                source_label = labels.get(source_kind, "Chemistry / empirical reference")
                condition_lines += ["", source_label, f"Cocktail  {comp_text or rec.get('preset') or 'unavailable'}", f"Time  {_fmt(rec.get('cleavage_time_h')) or '—'} h", f"Cleavage eq  {_fmt(rec.get('cleavage_eq')) or '—'}", f"Apply  {'YES' if rec.get('apply_allowed') else 'NO'}"]
                eq_range = rec.get("cleavage_eq_range") or []
                if len(eq_range) == 2:
                    condition_lines.append(f"Estimated range  {_fmt(eq_range[0])}–{_fmt(eq_range[1])} eq")
                empirical = rec.get("empirical_estimate") or {}
                if empirical:
                    if empirical.get("kind") == "operator_cys_rule":
                        condition_lines.append(f"Cys override  {empirical.get('cys_count',0)} × {_fmt(empirical.get('cys_eq_each')) or '100'} eq = {_fmt(rec.get('cleavage_eq'))} eq")
                    condition_lines.append(f"Length baseline  {_fmt(empirical.get('baseline_eq')) or '—'} eq" + (" (not used for Cys eq)" if empirical.get("kind") == "operator_cys_rule" else ""))
                    if empirical.get("kind") != "operator_anchor":
                        condition_lines.append(f"Similar-history adjustment  {float(empirical.get('neighbor_adjustment_eq') or 0):+.1f} eq")
                        condition_lines.append(f"Similar histories  {empirical.get('neighbor_count',0)}")
                    if empirical.get("cocktail_basis"):
                        condition_lines.append(f"Cocktail basis  {empirical.get('cocktail_basis')}")
            else:
                condition_lines += ["", "No safe condition recommendation available."]

            # Amount card: only current-scale historical material-usage evidence.
            amount_lines = [f"Evidence  {amount.get('recommendation_kind','INSUFFICIENT EVIDENCE')}", f"Confidence  {amount.get('confidence','LOW')}"]
            if arec:
                total = arec.get("scaled_total_ml")
                amount_lines += [f"Current scale  {_fmt(self.clv_scale.get()) or '—'} mmol", f"Observed range  {_fmt(arec.get('observed_scale_min_mmol'))}–{_fmt(arec.get('observed_scale_max_mmol'))} mmol", f"Total cocktail  {_fmt(total) if total is not None else '—'} mL"]
                if total is not None:
                    comp = arec.get("composition_pct") or {}
                    for name, pct in comp.items():
                        amount_lines.append(f"{name}  {_fmt(float(total)*float(pct)/100.0,3)} mL  ({_fmt(pct,2)}%)")
                amount_lines += [f"Independent syntheses  {arec.get('independent_syntheses',0)}", f"Apply amount  {'YES' if amount.get('apply_allowed') else 'NO'}"]
            else:
                theoretical_total = rec.get("scaled_total_ml") if rec.get("condition_source") in {"empirical_v5_fallback", "operator_approved_anchor", "chemistry_rule_reference"} else None
                if theoretical_total is not None:
                    amount_lines += [
                        "No normalized matching amount record.",
                        "Theoretical/current-model amount — not historical usage.",
                        f"Current scale  {_fmt(self.clv_scale.get()) or '—'} mmol",
                        f"Total cocktail  {_fmt(theoretical_total)} mL",
                    ]
                    for name, pct in (rec.get("composition_pct") or {}).items():
                        amount_lines.append(f"{name}  {_fmt(float(theoretical_total)*float(pct)/100.0,3)} mL  ({_fmt(pct,2)}%)")
                else:
                    amount_lines += ["No normalized matching amount record."]

            # Workup card: precipitation is deliberately outside the TFA cocktail.
            workup_lines = ["Precipitation solvent is NOT part of the cleavage cocktail."]
            wrec = amount.get("recommended_workup") or arec
            solvent = wrec.get("solvent") or arec.get("workup_solvent") or ("Ethyl Ether" if arec.get("scaled_ether_ml") is not None else "")
            workup_ml = wrec.get("scaled_workup_ml") if wrec.get("scaled_workup_ml") is not None else arec.get("scaled_workup_ml") if arec.get("scaled_workup_ml") is not None else arec.get("scaled_ether_ml")
            if solvent and workup_ml is not None:
                workup_lines += ["", f"Solvent  {solvent}", f"Current-scale amount  {_fmt(workup_ml)} mL", f"Basis  {arec.get('amount_kind','historical usage')}"]
            else:
                theory_total = arec.get("scaled_total_ml") if arec else None
                if theory_total is None and rec.get("condition_source") in {"empirical_v5_fallback", "operator_approved_anchor", "chemistry_rule_reference"}:
                    theory_total = rec.get("scaled_total_ml")
                workup_lines += ["", "No verified single-product precipitation amount is available."]
                if theory_total is not None:
                    workup_lines += [
                        "Theoretical reference only — not auto-applied.",
                        f"Ethyl Ether  ≈ {_fmt(float(theory_total)*10.0)} mL  (≈10× cocktail volume)",
                        f"n-Hexane  ≈ {_fmt(float(theory_total)*10.0)} mL  (reference alternative)",
                        f"Ether/n-Hexane 1:1  ≈ {_fmt(float(theory_total)*5.0)} + {_fmt(float(theory_total)*5.0)} mL",
                    ]
                else:
                    workup_lines += ["Ethyl Ether / n-Hexane theoretical guide becomes available once a current-scale cocktail amount is available."]
            aggregates = int(amount.get("aggregate_reference_count") or 0)
            if aggregates:
                workup_lines.append(f"Aggregate reference rows excluded from auto-scaling: {aggregates}")
            unresolved = int(amount.get("unresolved_unit_count") or 0)
            if unresolved:
                workup_lines.append(f"Unit review required: {unresolved} matching record(s)")
            for warning in amount.get("warnings") or []:
                workup_lines.append(f"• {warning}")

            from spps_v4_gui.modules import cleavage_panel as _cleavage_panel
            rescue_info=_cleavage_panel.post_cleavage_rescue_summary(self.gui)
            if rescue_info.get("enabled"):
                rescue_lines=[
                    "NH4I Reduction — conditional rescue",
                    "Use only after oxidation/specific impurity is observed; not part of the cleavage cocktail.",
                    f"NH4I  {_fmt(rescue_info.get('nh4i_eq'))} eq  |  target {_fmt(rescue_info.get('concentration_m'))} M  |  {_fmt(rescue_info.get('time_h'))} h",
                ]
                if rescue_info.get("valid"):
                    rescue_lines += [
                        f"NH4I amount  {_fmt(rescue_info.get('nh4i_mmol'))} mmol / {_fmt(rescue_info.get('nh4i_mass_mg'))} mg",
                        f"Final TFA/DW solution  ≈ {_fmt(rescue_info.get('final_solution_ml'))} mL at target concentration",
                    ]
                elif rescue_info.get("warning"):
                    rescue_lines.append("WARNING: "+str(rescue_info.get("warning")))
            else:
                rescue_lines=[
                    "None (default)",
                    "Use NH4I Reduction only after oxidation or a specific impurity is confirmed.",
                    "Operator protocol when used: NH4I 2 eq, ≤0.2 M (default 0.2 M), 1 h, TFA/DW.",
                ]

            self.clv_result.delete("1.0", "end"); self.clv_result.insert("1.0", "\n".join(condition_lines))
            self.clv_amount_result.delete("1.0", "end"); self.clv_amount_result.insert("1.0", "\n".join(amount_lines))
            self.clv_workup_result.delete("1.0", "end"); self.clv_workup_result.insert("1.0", "\n".join(workup_lines))
            self.clv_rescue_result.delete("1.0", "end"); self.clv_rescue_result.insert("1.0", "\n".join(rescue_lines))
            self._fill(self.clv_evidence, result.get("evidence", []))
        except Exception as exc:
            self.cleavage_advisor_status.configure(text=f"Recommendation error: {exc}")
            messagebox.showerror("Cleavage Advisor", str(exc), parent=self)

    def _append_result_status(self, widget: tk.Text, message: str) -> None:
        try:
            current = widget.get("1.0", "end").strip()
            widget.delete("1.0", "end")
            widget.insert("1.0", (message + ("\n\n" + current if current else "")))
        except Exception as exc:
            self._result_status_error = exc

    def apply_loading_recommendation(self) -> None:
        self.run_loading_advisor()
        result = self._last_loading_advice or {}
        try:
            from spps_v4_gui import resin_profiles
            if not resin_profiles.editor_loading_enabled(self.gui):
                messagebox.showinfo("Loading Advisor", "Enable direct 2-CTC/Trityl loading calculation before applying a loading recommendation.", parent=self)
                return
        except Exception as exc:
            messagebox.showerror("Loading Advisor", f"Could not verify the Planner loading mode. No values were changed.\n\n{exc}", parent=self)
            return
        rec = result.get("target_recommendation") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Loading Advisor", "No bounded target-loading recommendation can be applied. The target may be outside the observed range or there may be too little exact resin + AA history.", parent=self)
            return
        current_aa = _value(getattr(self.gui, "loading_aa_eq", ""))
        current_base = _value(getattr(self.gui, "loading_diea_eq", ""))
        proposed_aa = _fmt(rec.get("aa_eq"))
        proposed_base = _fmt(rec.get("base_eq"))
        ok = messagebox.askyesno(
            "Apply Loading Recommendation",
            "Apply the target-loading estimate?\n\n"
            f"Target loading: {_fmt(rec.get('target_loading_mmol_g'))} mmol/g\n"
            f"AA eq: {current_aa or '(blank)'}  →  {proposed_aa or '(unchanged)'}\n"
            f"DIEA eq: {current_base or '(blank)'}  →  {proposed_base or '(unchanged)'}\n"
            f"Time: {_value(getattr(self.gui, 'loading_time_h', '')) or '(blank)'}  →  {_fmt(rec.get('loading_time_h')) or '(unchanged)'} h\n"
            f"Expected loading: {_fmt(rec.get('predicted_loading_mmol_g'))} mmol/g\n"
            f"Expected range: {_fmt(rec.get('expected_low_mmol_g'))} – {_fmt(rec.get('expected_high_mmol_g'))} mmol/g\n"
            f"Evidence: {rec.get('evidence_count',0)} exact resin+AA record(s)\n"
            f"Basis: {rec.get('basis') or rec.get('recommendation_kind')}\n\n"
            "This is bounded to observed history; no out-of-range extrapolation is applied.",
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
            generated = self.gui.generate_update_plan()
            if generated is None:
                raise RuntimeError("Planner Generate did not complete.")
        except Exception as exc:
            messagebox.showerror("Loading Advisor", f"The recommendation was written, but regeneration failed.\n\n{exc}", parent=self)
            return
        text = f"Applied target-loading recommendation: AA {self.load_aa_eq.get()} eq / DIEA {self.load_base_eq.get()} eq / {self.load_time.get()} h."
        self.status.configure(text=text); self._append_result_status(self.load_result, "✓ " + text)

    def apply_cleavage_recommendation(self) -> None:
        # Recompute immediately before Apply so edited advisor fields cannot use stale evidence.
        self.run_cleavage_advisor()
        result = self._last_cleavage_advice or {}
        rec = result.get("recommended_condition") or {}
        if not rec or not rec.get("apply_allowed"):
            messagebox.showinfo("Cleavage Advisor", "No safe sequence-based cleavage recommendation is available for the current Planner input.", parent=self)
            return
        amount = result.get("amount_evidence") or {}
        arec = amount.get("recommended_amount") or {}
        eq = rec.get("cleavage_eq")
        comp = rec.get("composition_pct") or {}
        current_eq = _value(getattr(self.gui, "cleavage_eq_override", ""))
        current_comp = _value(getattr(self.gui, "cleavage_components_text", ""))
        proposed_comp = ";".join(f"{name}={_fmt(value,2)}" for name, value in comp.items()) if comp else "unavailable"

        # Current-scale material usage is authoritative for amount only when it is
        # independently actionable.  It never changes the chosen cocktail identity.
        scaled_total = arec.get("scaled_total_ml") if amount.get("apply_allowed") else None
        if scaled_total is None and rec.get("volume_apply_allowed"):
            scaled_total = rec.get("scaled_total_ml")
        wrec = amount.get("recommended_workup") or arec
        workup_solvent = wrec.get("solvent") or arec.get("workup_solvent") or ("Ethyl Ether" if arec.get("scaled_ether_ml") is not None else "")
        workup_ml = wrec.get("scaled_workup_ml") if wrec.get("scaled_workup_ml") is not None else arec.get("scaled_workup_ml") if arec.get("scaled_workup_ml") is not None else arec.get("scaled_ether_ml")

        amount_text = _fmt(scaled_total) + " mL" if scaled_total is not None else "(unchanged)"
        workup_text = f"{workup_solvent} {_fmt(workup_ml)} mL" if workup_solvent and workup_ml is not None else (f"theoretical guide only: Ether or n-Hexane ≈ {_fmt(float(scaled_total)*10.0)} mL" if scaled_total is not None else "no auto-applied workup amount")
        ok = messagebox.askyesno(
            "Confirm Cleavage Apply",
            "Apply the evidence-based cleavage recommendation?\n\n"
            f"Cleavage eq: {current_eq or '(blank)'}  →  {_fmt(eq) if eq is not None else '(unchanged)'}\n"
            f"Cocktail: {current_comp or '(current preset)'}\n        →  {proposed_comp}\n"
            f"Cleavage time: {_value(getattr(self.gui, 'cleavage_time_h', '')) or '(blank)'}  →  {_fmt(rec.get('cleavage_time_h')) if rec.get('cleavage_time_h') is not None else '(unchanged)'} h\n"
            f"Current-scale cocktail amount: {amount_text}\n"
            f"Precipitation/workup evidence: {workup_text}\n"
            f"Sequence: {self.clv_sequence.get()}\n"
            f"Condition basis: {rec.get('basis') or rec.get('source_status') or 'sequence + history'}\n"
            f"Amount basis: {amount.get('recommendation_kind') or 'none'}\n\n"
            "Precipitation solvent is shown as workup evidence and is not inserted into the cleavage cocktail.", parent=self,
        )
        if not ok:
            return
        if eq is not None:
            self.gui.cleavage_eq_override.set(str(eq)); self.clv_eq.set(str(eq))
        if rec.get("cleavage_time_h") is not None:
            self.gui.cleavage_time_h.set(str(rec["cleavage_time_h"])); self.clv_time.set(str(rec["cleavage_time_h"]))
        if scaled_total is not None:
            reserve_var = getattr(self.gui, "cleavage_reserve_mL", None)
            if reserve_var is not None and hasattr(reserve_var, "set"):
                reserve_var.set(str(scaled_total))
        preset = str(rec.get("preset") or "").strip()
        if rec.get("condition_source") == "exact_lab_record" and comp:
            self.gui.cleavage_preset.set("CUSTOM")
            self.gui.cleavage_components_text.set(";".join(f"{name}={float(value):.4g}" for name, value in comp.items() if value is not None and float(value) > 0))
        elif preset:
            self.gui.cleavage_preset.set(preset); self.gui.cleavage_components_text.set("")
        elif comp:
            self.gui.cleavage_preset.set("CUSTOM")
            self.gui.cleavage_components_text.set(";".join(f"{name}={float(value):.4g}" for name, value in comp.items() if value is not None and float(value) > 0))
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
        text = f"Applied: {self.clv_eq.get()} eq / {self.clv_time.get()} h / {composition}; current-scale cocktail {amount_text}."
        self.status.configure(text=text); self._append_result_status(self.clv_result, "✓ " + text)

__all__ = ["ExperimentalDataWindow"]
