"""Independent V3 Work Item editor backed by the active Classic workspace."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any

from spps_v4_gui import execution_workflow, ml_dataset, ui_system
from spps_v4_gui.modules import plan_workflow


TABLES = (
    ("Selected Plan", "pm_selected_plan_tree"),
    ("Selected Materials", "pm_selected_material_tree"),
    ("Total Materials", "pm_selected_total_tree"),
    ("Checklist", "progress_tree"),
    ("Cleavage", "pm_cleavage_tree"),
)

READ_ONLY_PLAN_COLUMNS = {
    "No", "Unit mmol", "Unit amount", "R1 mmol", "R1 amount",
    "R2 mmol", "R2 amount", "Base mmol", "Base amount",
}


def _tree_rows(tree: Any) -> list[dict[str, str]]:
    if tree is None:
        return []
    columns = list(tree["columns"])
    return [
        dict(zip(columns, tree.item(iid, "values")))
        for iid in tree.get_children()
    ]


def _write_rows(tree: ttk.Treeview, rows: list[dict[str, Any]]) -> None:
    columns = list(tree["columns"])
    values = tuple(
        tuple(str(row.get(column, "") or "") for column in columns)
        for row in rows
    )
    if getattr(tree, "_spps_work_item_values", None) == values:
        return
    for iid in tree.get_children():
        tree.delete(iid)
    for row_values in values:
        tree.insert("", "end", values=row_values)
    tree._spps_work_item_values = values


class WorkItemWindow:
    """One real editor window for the selected Project Manager item."""

    def __init__(self, gui: Any):
        self.gui = gui
        self.window = tk.Toplevel(gui)
        self.window.title(self._title())
        ui_system.fit_window(
            self.window, preferred_width=1500, preferred_height=860,
            minimum_width=1000, minimum_height=650,
        )
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.trees: dict[str, ttk.Treeview] = {}
        self._editor: tk.Widget | None = None
        self.step_var = tk.StringVar(value="")
        self.field_var = tk.StringVar(value="Repeat")
        self.value_var = tk.StringVar(value="")
        self.reason_var = tk.StringVar(value="")
        self.operator_note_var = tk.StringVar(value="")
        self.material_var = tk.StringVar(value="")
        self.actual_amount_var = tk.StringVar(value="")
        self.actual_unit_var = tk.StringVar(value="mmol")
        self.material_status_var = tk.StringVar(value="Charged")
        self.ml_yield_var = tk.StringVar(value="")
        self.ml_purity_var = tk.StringVar(value="")
        self.ml_failure_var = tk.StringVar(value="Unknown")
        self.ml_doubling_var = tk.StringVar(value="Auto from execution")
        self.ml_include_var = tk.BooleanVar(value=True)
        self.ml_exclusion_var = tk.StringVar(value="")
        self.ml_review_reason_var = tk.StringVar(value="")
        self.ml_note_var = tk.StringVar(value="")
        self.ml_target_var = tk.StringVar(value="actual_yield_percent")
        self.ml_status_var = tk.StringVar(value="No reviewed dataset yet.")
        self.ml_result_var = tk.StringVar(value="")
        self._ml_loaded_revision = -1
        self.run_name_var = tk.StringVar(value="")
        self.run_reason_var = tk.StringVar(value="")
        self.selected_run_id = ""
        self.hplc_search_var = tk.StringVar(value="")
        self.hplc_sort_var = tk.StringVar(value="acquired_at")
        self.hplc_reason_var = tk.StringVar(value="")
        self.hplc_vars = {
            name: tk.StringVar(value="") for name in (
                "hplc_record_id", "sample_name", "acquired_at", "instrument", "column",
                "method_name", "mobile_phase_a", "mobile_phase_b", "gradient",
                "flow_rate_mL_min", "wavelength_nm", "injection_volume_uL", "runtime_min",
                "retention_time_min", "area_percent", "purity_percent", "analyst",
                "data_file_path", "method_file_path", "notes",
            )
        }
        self.data_status_var = tk.StringVar(value="")
        self.risk_status_var = tk.StringVar(value="Not evaluated.")
        self.risk_ack_reason_var = tk.StringVar(value="")
        self._risk_assessment: dict[str, Any] = {}
        self._build()
        ui_system.apply_theme(self.window, getattr(gui, "_v3_density", "Standard"))
        self._bind_shortcuts()
        self.notebook.bind(
            "<<NotebookTabChanged>>", self._refresh_selected_tab, add="+",
        )
        self.refresh()

    def _title(self) -> str:
        index = getattr(self.gui, "_v229_active_index", None)
        try:
            item = self.gui.pm_items[int(index)]
            label = self.gui.pm_display_name(item)
        except Exception:
            label = "Selected Work Item"
        return f"{label} — SPPS Planner V4.0.0"

    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=10)
        outer.pack(fill="both", expand=True)

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(
            toolbar, text="Work Item", font=("Segoe UI", 15, "bold"),
        ).pack(side="left")
        for text, command in (
            ("Save Item", self.save),
            ("Generate", self.generate),
            ("Apply Change", self.apply_change),
            ("Export", self.gui.export_outputs),
            ("Close", self.close),
        ):
            ttk.Button(toolbar, text=text, command=command).pack(side="right", padx=3)

        form = ttk.LabelFrame(outer, text="Project / Resin / Chemistry", padding=8)
        form.pack(fill="x", pady=(0, 8))
        fields = (
            ("Project", "pm_project", 18),
            ("Peptide", "pm_peptide", 18),
            ("Sequence", "pm_sequence", 30),
            ("Scale (mmol)", "pm_scale", 10),
            ("Copies", "pm_copies", 7),
            ("Loading", "pm_loading", 8),
        )
        for column, (label, variable_name, width) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=column * 2, sticky="w", padx=(3, 3))
            ttk.Entry(
                form, textvariable=getattr(self.gui, variable_name), width=width,
            ).grid(row=0, column=column * 2 + 1, sticky="ew", padx=(0, 8))
            form.columnconfigure(column * 2 + 1, weight=1 if variable_name == "pm_sequence" else 0)
        ttk.Label(form, text="Resin").grid(row=1, column=0, sticky="w", padx=3, pady=(7, 0))
        ttk.Combobox(
            form, textvariable=self.gui.pm_resin,
            values=list(getattr(self.gui, "RESIN_VALUES", [])), state="normal", width=24,
        ).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(7, 0))
        ttk.Label(form, text="Chemistry").grid(row=1, column=2, sticky="w", padx=3, pady=(7, 0))
        ttk.Combobox(
            form, textvariable=self.gui.pm_chemistry,
            values=("DIC/HOBt", "HBTU/NMP 10eq"), state="normal", width=22,
        ).grid(row=1, column=3, sticky="ew", padx=(0, 8), pady=(7, 0))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook
        for label, source_name in TABLES:
            frame = ttk.Frame(notebook)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            notebook.add(frame, text=label)
            source = getattr(self.gui, source_name, None)
            columns = list(source["columns"]) if source is not None else ()
            tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
            ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
            tree.grid(row=0, column=0, sticky="nsew")
            ybar.grid(row=0, column=1, sticky="ns")
            xbar.grid(row=1, column=0, sticky="ew")
            for column in columns:
                tree.heading(column, text=column)
                width = 230 if column in {"Unit name", "Note", "operation"} else 105
                tree.column(column, width=width, minwidth=50, stretch=column in {"Note", "operation"})
            if label == "Selected Plan":
                tree.bind("<Double-1>", self._begin_plan_edit)
                tree.bind("<<TreeviewSelect>>", self._select_plan_step)
            elif label == "Selected Materials":
                tree.bind("<<TreeviewSelect>>", self._select_material)
            self.trees[source_name] = tree

        self._build_execution_tab(notebook)
        self._build_ml_tab(notebook)
        self._build_risk_tab(notebook)
        self._build_data_tab(notebook)
        ttk.Label(
            outer,
            text="Selected Plan is the source of truth. Run / Corrections records every live change and recalculates linked tables.",
            foreground="#4B5563",
        ).pack(anchor="w", pady=(6, 0))

    def _bind_shortcuts(self) -> None:
        bindings = {
            "<Control-s>": lambda _event=None: (self.save(), "break")[-1],
            "<Control-g>": lambda _event=None: (self.generate(), "break")[-1],
            "<Control-Return>": lambda _event=None: (self.apply_change(), "break")[-1],
            "<F5>": lambda _event=None: (self.refresh(), "break")[-1],
            "<Escape>": lambda _event=None: (self.close(), "break")[-1],
        }
        for sequence, callback in bindings.items():
            self.window.bind(sequence, callback, add="+")
        self._shortcut_bindings = bindings

    def _build_execution_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        notebook.add(frame, text="Run / Corrections")

        correction = ttk.LabelFrame(frame, text="Live Plan Correction", padding=8)
        correction.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(correction, text="Step").grid(row=0, column=0, sticky="w")
        ttk.Entry(correction, textvariable=self.step_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(4, 10),
        )
        ttk.Label(correction, text="Field").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            correction,
            textvariable=self.field_var,
            values=execution_workflow.PLAN_EDITABLE_FIELDS,
            state="readonly",
            width=20,
        ).grid(row=0, column=3, sticky="w", padx=(4, 10))
        ttk.Label(correction, text="New value").grid(row=0, column=4, sticky="w")
        ttk.Entry(correction, textvariable=self.value_var, width=15).grid(
            row=0, column=5, sticky="w", padx=(4, 10),
        )
        ttk.Label(correction, text="Reason").grid(row=0, column=6, sticky="w")
        ttk.Entry(correction, textvariable=self.reason_var).grid(
            row=0, column=7, sticky="ew", padx=(4, 8),
        )
        correction.columnconfigure(7, weight=1)
        ttk.Label(correction, text="Operator note").grid(
            row=1, column=0, sticky="w", pady=(7, 0),
        )
        ttk.Entry(
            correction, textvariable=self.operator_note_var,
        ).grid(row=1, column=1, columnspan=7, sticky="ew", padx=(4, 8), pady=(7, 0))
        ttk.Button(
            correction, text="Apply Correction", command=self.apply_live_correction,
        ).grid(row=0, column=8, padx=3)
        ttk.Button(
            correction, text="Apply Doubling (Repeat=2)", command=self.apply_doubling,
        ).grid(row=1, column=8, padx=3, pady=(7, 0))
        ttk.Button(
            correction, text="Revert Last", command=self.revert_last,
        ).grid(row=0, column=9, rowspan=2, padx=(3, 0), sticky="ns")

        execution = ttk.LabelFrame(frame, text="Step Execution", padding=8)
        execution.grid(row=1, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(execution, text="Selected step status").pack(side="left", padx=(0, 8))
        for status in execution_workflow.STEP_STATUSES:
            ttk.Button(
                execution,
                text=status,
                command=lambda value=status: self.record_step_status(value),
            ).pack(side="left", padx=2)

        material = ttk.LabelFrame(frame, text="Actual Material Amount / Status", padding=8)
        material.grid(row=2, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(material, text="Material").grid(row=0, column=0, sticky="w")
        ttk.Entry(material, textvariable=self.material_var, width=30).grid(
            row=0, column=1, sticky="ew", padx=(4, 10),
        )
        ttk.Label(material, text="Actual amount").grid(row=0, column=2, sticky="w")
        ttk.Entry(material, textvariable=self.actual_amount_var, width=12).grid(
            row=0, column=3, padx=(4, 5),
        )
        ttk.Combobox(
            material,
            textvariable=self.actual_unit_var,
            values=("mmol", "mol", "mg", "g", "µL", "mL"),
            state="normal",
            width=8,
        ).grid(row=0, column=4, padx=(0, 10))
        ttk.Label(material, text="Status").grid(row=0, column=5, sticky="w")
        ttk.Combobox(
            material,
            textvariable=self.material_status_var,
            values=execution_workflow.MATERIAL_STATUSES,
            state="readonly",
            width=12,
        ).grid(row=0, column=6, padx=(4, 8))
        ttk.Button(
            material, text="Record Actual", command=self.record_actual_material,
        ).grid(row=0, column=7)
        material.columnconfigure(1, weight=1)

        history_frame = ttk.LabelFrame(frame, text="Append-only Execution History", padding=6)
        history_frame.grid(row=3, column=0, sticky="nsew")
        history_frame.rowconfigure(0, weight=1)
        history_frame.columnconfigure(0, weight=1)
        columns = (
            "timestamp", "event_type", "step_no", "unit", "field",
            "before", "after", "reason", "operator_note", "event_id",
        )
        history = ttk.Treeview(
            history_frame, columns=columns, show="headings", height=10,
        )
        ybar = ttk.Scrollbar(history_frame, orient="vertical", command=history.yview)
        xbar = ttk.Scrollbar(history_frame, orient="horizontal", command=history.xview)
        history.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        history.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        for column in columns:
            history.heading(column, text=column)
            width = 220 if column in {"before", "after", "reason", "operator_note"} else 120
            history.column(column, width=width, minwidth=60, stretch=False)
        self.execution_tree = history

    def _build_ml_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)
        notebook.add(frame, text="Outcome / ML")

        outcome = ttk.LabelFrame(frame, text="Reviewed Actual Outcome", padding=8)
        outcome.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(outcome, text="Yield %").grid(row=0, column=0, sticky="w")
        ttk.Entry(outcome, textvariable=self.ml_yield_var, width=10).grid(row=0, column=1, padx=(4, 10))
        ttk.Label(outcome, text="Crude purity %").grid(row=0, column=2, sticky="w")
        ttk.Entry(outcome, textvariable=self.ml_purity_var, width=10).grid(row=0, column=3, padx=(4, 10))
        ttk.Label(outcome, text="Failure").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            outcome, textvariable=self.ml_failure_var,
            values=("Unknown", "No", "Yes"), state="readonly", width=10,
        ).grid(row=0, column=5, padx=(4, 10))
        ttk.Label(outcome, text="Doubling required").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            outcome, textvariable=self.ml_doubling_var,
            values=("Auto from execution", "No", "Yes"), state="readonly", width=19,
        ).grid(row=0, column=7, padx=(4, 10))
        ttk.Checkbutton(
            outcome, text="Include in ML dataset", variable=self.ml_include_var,
        ).grid(row=0, column=8, sticky="w")

        ttk.Label(outcome, text="Review reason").grid(row=1, column=0, sticky="w", pady=(7, 0))
        ttk.Entry(outcome, textvariable=self.ml_review_reason_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=(4, 10), pady=(7, 0),
        )
        ttk.Label(outcome, text="Exclusion reason").grid(row=1, column=4, sticky="w", pady=(7, 0))
        ttk.Entry(outcome, textvariable=self.ml_exclusion_var).grid(
            row=1, column=5, columnspan=2, sticky="ew", padx=(4, 10), pady=(7, 0),
        )
        ttk.Label(outcome, text="Operator note").grid(row=2, column=0, sticky="w", pady=(7, 0))
        ttk.Entry(outcome, textvariable=self.ml_note_var).grid(
            row=2, column=1, columnspan=7, sticky="ew", padx=(4, 10), pady=(7, 0),
        )
        ttk.Button(outcome, text="Save Reviewed Outcome", command=self.save_ml_review).grid(
            row=1, column=8, rowspan=2, sticky="nsew", pady=(7, 0),
        )
        for column in (1, 3, 5, 6, 7):
            outcome.columnconfigure(column, weight=1)

        dataset = ttk.LabelFrame(frame, text="Dataset Version", padding=8)
        dataset.grid(row=1, column=0, sticky="ew", pady=(0, 7))
        ttk.Button(dataset, text="Build Dataset Version", command=self.build_ml_dataset).pack(side="left")
        ttk.Label(dataset, textvariable=self.ml_status_var, foreground="#4B5563").pack(
            side="left", padx=12,
        )

        model = ttk.LabelFrame(frame, text="Train / Predict", padding=8)
        model.grid(row=2, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(model, text="Target").pack(side="left")
        ttk.Combobox(
            model, textvariable=self.ml_target_var,
            values=ml_dataset.TARGETS, state="readonly", width=24,
        ).pack(side="left", padx=(4, 10))
        ttk.Button(model, text="Train Reviewed Data", command=self.train_ml_model).pack(side="left", padx=3)
        ttk.Button(model, text="Predict Active Item", command=self.predict_ml).pack(side="left", padx=3)
        ttk.Label(model, textvariable=self.ml_result_var, foreground="#1D4ED8").pack(side="left", padx=12)

        ttk.Label(
            frame,
            text="Training requires at least 5 included reviewed rows with a real target; classification also requires two classes.",
            foreground="#4B5563",
        ).grid(row=3, column=0, sticky="w", pady=(0, 7))

        history_frame = ttk.LabelFrame(frame, text="Outcome Review Versions", padding=6)
        history_frame.grid(row=4, column=0, sticky="nsew")
        history_frame.rowconfigure(0, weight=1)
        history_frame.columnconfigure(0, weight=1)
        columns = (
            "revision", "timestamp", "included", "yield", "purity",
            "failure", "doubling", "reason", "version_id",
        )
        history = ttk.Treeview(history_frame, columns=columns, show="headings", height=10)
        ybar = ttk.Scrollbar(history_frame, orient="vertical", command=history.yview)
        xbar = ttk.Scrollbar(history_frame, orient="horizontal", command=history.xview)
        history.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        history.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        for column in columns:
            history.heading(column, text=column)
            history.column(column, width=220 if column == "reason" else 115, minwidth=60, stretch=False)
        self.ml_review_tree = history

    def _build_risk_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        notebook.add(frame, text="Risk Review")

        summary = ttk.LabelFrame(frame, text="Synthesis Risk Triage", padding=8)
        summary.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ttk.Button(summary, text="Refresh Assessment", command=self.evaluate_risk).pack(side="left")
        ttk.Button(summary, text="Save Assessment Version", command=self.save_risk).pack(side="left", padx=4)
        ttk.Button(summary, text="Export Risk Report", command=self.export_risk).pack(side="left", padx=4)
        ttk.Label(summary, textvariable=self.risk_status_var, foreground="#1D4ED8").pack(side="left", padx=12)

        acknowledgement = ttk.LabelFrame(frame, text="Operator Acknowledgement", padding=8)
        acknowledgement.grid(row=1, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(acknowledgement, text="Reason").pack(side="left")
        ttk.Entry(acknowledgement, textvariable=self.risk_ack_reason_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(acknowledgement, text="Acknowledge Selected", command=self.acknowledge_risk).pack(side="left")

        holder = ttk.LabelFrame(frame, text="Findings — evidence, impact and review action", padding=6)
        holder.grid(row=2, column=0, sticky="nsew")
        holder.rowconfigure(0, weight=1); holder.columnconfigure(0, weight=1)
        columns = ("severity", "category", "title", "positions", "evidence", "impact", "recommendation", "source", "confidence", "finding_id")
        tree = ttk.Treeview(holder, columns=columns, show="headings", height=14)
        ybar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew"); ybar.grid(row=0, column=1, sticky="ns"); xbar.grid(row=1, column=0, sticky="ew")
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=300 if column in {"evidence", "impact", "recommendation"} else 130, minwidth=70, stretch=False)
        self.risk_tree = tree
        ttk.Label(
            frame,
            text="Rule score is transparent triage, not failure probability. ML appears only from a valid reviewed-data model. Nothing here changes the Plan automatically.",
            foreground="#4B5563",
        ).grid(row=3, column=0, sticky="w", pady=(6, 0))

    def _build_data_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        notebook.add(frame, text="Data / HPLC")

        runs = ttk.LabelFrame(frame, text="Synthesis Runs", padding=7)
        runs.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        runs.columnconfigure(0, weight=1)
        columns = ("run_id", "name", "status", "created_at", "updated_at", "lot", "event_count", "hplc_count")
        tree = ttk.Treeview(runs, columns=columns, show="headings", height=4)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=190 if column in {"run_id", "created_at", "updated_at"} else 100, stretch=False)
        tree.grid(row=0, column=0, rowspan=2, sticky="ew")
        tree.bind("<<TreeviewSelect>>", self._select_run)
        self.run_tree = tree
        run_actions = ttk.Frame(runs)
        run_actions.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        ttk.Label(run_actions, text="Run name").grid(row=0, column=0, sticky="w")
        ttk.Entry(run_actions, textvariable=self.run_name_var, width=22).grid(row=0, column=1, padx=4)
        ttk.Label(run_actions, text="Reason").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(run_actions, textvariable=self.run_reason_var, width=22).grid(row=1, column=1, padx=4, pady=(5, 0))
        ttk.Button(run_actions, text="New Run", command=self.create_run).grid(row=0, column=2, padx=3)
        ttk.Button(run_actions, text="Activate Selected", command=self.activate_run).grid(row=1, column=2, padx=3, pady=(5, 0))

        form = ttk.LabelFrame(frame, text="HPLC Result / File Link", padding=7)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 7))
        fields = (
            ("Sample", "sample_name", 18), ("Acquired at", "acquired_at", 18),
            ("Instrument", "instrument", 16), ("Column", "column", 16),
            ("Method", "method_name", 16), ("Flow mL/min", "flow_rate_mL_min", 10),
            ("Wavelength nm", "wavelength_nm", 10), ("RT min", "retention_time_min", 10),
            ("Area %", "area_percent", 10), ("Purity %", "purity_percent", 10),
            ("Analyst", "analyst", 14), ("Runtime min", "runtime_min", 10),
        )
        for index, (label, key, width) in enumerate(fields):
            row, pair = divmod(index, 6)
            column = pair * 2
            ttk.Label(form, text=label).grid(row=row, column=column, sticky="w", padx=(2, 3), pady=2)
            ttk.Entry(form, textvariable=self.hplc_vars[key], width=width).grid(row=row, column=column + 1, sticky="ew", padx=(0, 7), pady=2)
            form.columnconfigure(column + 1, weight=1)
        ttk.Label(form, text="Data file").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.hplc_vars["data_file_path"]).grid(row=2, column=1, columnspan=4, sticky="ew", padx=(0, 4))
        ttk.Button(form, text="Browse", command=lambda: self._browse_hplc_file("data_file_path")).grid(row=2, column=5, padx=(0, 7))
        ttk.Label(form, text="Method file").grid(row=2, column=6, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.hplc_vars["method_file_path"]).grid(row=2, column=7, columnspan=4, sticky="ew", padx=(0, 4))
        ttk.Button(form, text="Browse", command=lambda: self._browse_hplc_file("method_file_path")).grid(row=2, column=11)
        ttk.Label(form, text="Mobile A").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(form, textvariable=self.hplc_vars["mobile_phase_a"]).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 7))
        ttk.Label(form, text="Mobile B").grid(row=3, column=3, sticky="w", padx=2)
        ttk.Entry(form, textvariable=self.hplc_vars["mobile_phase_b"]).grid(row=3, column=4, columnspan=2, sticky="ew", padx=(0, 7))
        ttk.Label(form, text="Gradient").grid(row=3, column=6, sticky="w", padx=2)
        ttk.Entry(form, textvariable=self.hplc_vars["gradient"]).grid(row=3, column=7, columnspan=2, sticky="ew", padx=(0, 7))
        ttk.Label(form, text="Notes").grid(row=3, column=9, sticky="w", padx=2)
        ttk.Entry(form, textvariable=self.hplc_vars["notes"]).grid(row=3, column=10, columnspan=2, sticky="ew")
        ttk.Label(form, text="Change reason").grid(row=4, column=0, sticky="w", padx=2, pady=(5, 0))
        ttk.Entry(form, textvariable=self.hplc_reason_var).grid(row=4, column=1, columnspan=8, sticky="ew", padx=(0, 7), pady=(5, 0))
        ttk.Button(form, text="Save / Update HPLC", command=self.save_hplc).grid(row=4, column=9, padx=3, pady=(5, 0))
        ttk.Button(form, text="Remove Selected", command=self.remove_hplc).grid(row=4, column=10, padx=3, pady=(5, 0))
        ttk.Button(form, text="Clear", command=self.clear_hplc_form).grid(row=4, column=11, padx=3, pady=(5, 0))

        bar = ttk.Frame(frame)
        bar.grid(row=2, column=0, sticky="ew", pady=(0, 7))
        ttk.Label(bar, text="Search").pack(side="left")
        search = ttk.Entry(bar, textvariable=self.hplc_search_var, width=28)
        search.pack(side="left", padx=(4, 8)); search.bind("<Return>", lambda _e: self._refresh_data())
        ttk.Label(bar, text="Sort").pack(side="left")
        ttk.Combobox(
            bar, textvariable=self.hplc_sort_var,
            values=("acquired_at", "sample_name", "purity_percent", "retention_time_min", "instrument"),
            state="readonly", width=20,
        ).pack(side="left", padx=(4, 8))
        ttk.Button(bar, text="Refresh", command=self._refresh_data).pack(side="left")
        ttk.Button(bar, text="Import HPLC CSV/XLSX", command=self.import_hplc).pack(side="left", padx=3)
        ttk.Button(bar, text="Export Data Workbook", command=self.export_data_workbook).pack(side="left", padx=3)
        ttk.Button(bar, text="Import Data Workbook", command=self.import_data_workbook).pack(side="left", padx=3)
        ttk.Label(bar, textvariable=self.data_status_var, foreground="#4B5563").pack(side="right")

        lower = ttk.Panedwindow(frame, orient="vertical")
        lower.grid(row=3, column=0, sticky="nsew")
        hplc_frame = ttk.LabelFrame(lower, text="HPLC Records", padding=5)
        history_frame = ttk.LabelFrame(lower, text="Run / HPLC Change History", padding=5)
        lower.add(hplc_frame, weight=3); lower.add(history_frame, weight=2)
        hplc_columns = ("hplc_record_id", "sample_name", "run_name", "acquired_at", "instrument", "column", "retention_time_min", "area_percent", "purity_percent", "analyst", "data_file_path")
        self.hplc_tree = self._make_data_tree(hplc_frame, hplc_columns)
        self.hplc_tree.bind("<<TreeviewSelect>>", self._select_hplc)
        history_columns = ("timestamp", "action", "entity", "reason", "run_id", "change_id", "before", "after")
        self.data_history_tree = self._make_data_tree(history_frame, history_columns)

    @staticmethod
    def _make_data_tree(parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=6)
        ybar = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        xbar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.grid(row=0, column=0, sticky="nsew"); ybar.grid(row=0, column=1, sticky="ns"); xbar.grid(row=1, column=0, sticky="ew")
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=210 if column in {"data_file_path", "before", "after", "reason"} else 125, minwidth=60, stretch=False)
        return tree

    def _begin_plan_edit(self, event: tk.Event) -> None:
        tree = self.trees["pm_selected_plan_tree"]
        if tree.identify("region", event.x, event.y) != "cell":
            return
        iid = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        if not iid or not column_id:
            return
        index = int(column_id[1:]) - 1
        columns = list(tree["columns"])
        if index < 0 or index >= len(columns) or columns[index] in READ_ONLY_PLAN_COLUMNS:
            return
        bbox = tree.bbox(iid, column_id)
        if not bbox:
            return
        if self._editor is not None:
            try:
                self._editor.destroy()
            except Exception:
                pass
        editor = ttk.Entry(tree)
        editor.insert(0, tree.set(iid, columns[index]))
        x, y, width, height = bbox
        editor.place(x=x, y=y, width=max(width, 100), height=height)
        editor.focus_set()
        editor.select_range(0, "end")
        self._editor = editor

        def commit(_event=None):
            tree.set(iid, columns[index], editor.get())
            editor.destroy()
            self._editor = None

        def cancel(_event=None):
            editor.destroy()
            self._editor = None

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)

    def _commit_plan_to_main(self) -> None:
        if self._editor is not None:
            self._editor.event_generate("<Return>")
        target = self.gui.pm_selected_plan_tree
        rows = _tree_rows(self.trees["pm_selected_plan_tree"])
        plan_workflow.v228._write_rows(
            target, rows, plan_workflow.PLAN_COLUMNS, plan_workflow.PLAN_WIDTHS,
        )

    def _select_plan_step(self, _event=None) -> None:
        tree = self.trees["pm_selected_plan_tree"]
        selected = list(tree.selection())
        if not selected:
            return
        row = dict(zip(tree["columns"], tree.item(selected[0], "values")))
        self.step_var.set(str(row.get("No", "")))
        self.value_var.set(str(row.get(self.field_var.get(), "")))

    def _select_material(self, _event=None) -> None:
        tree = self.trees["pm_selected_material_tree"]
        selected = list(tree.selection())
        if not selected:
            return
        row = dict(zip(tree["columns"], tree.item(selected[0], "values")))
        self.material_var.set(str(row.get("material", row.get("Material", ""))))
        step = row.get("step", row.get("No", ""))
        if str(step).strip():
            self.step_var.set(str(step))

    def _show_error(self, exc: Exception) -> None:
        messagebox.showerror("Run / Corrections", str(exc), parent=self.window)

    def apply_live_correction(self) -> None:
        try:
            self._commit_plan_to_main()
            self.gui.record_plan_correction(
                step_no=self.step_var.get(),
                field=self.field_var.get(),
                value=self.value_var.get(),
                reason=self.reason_var.get(),
                operator_note=self.operator_note_var.get(),
            )
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def apply_doubling(self) -> None:
        try:
            self._commit_plan_to_main()
            self.gui.apply_live_doubling(
                step_no=self.step_var.get(),
                reason=self.reason_var.get() or "Operator applied doubling",
                operator_note=self.operator_note_var.get(),
            )
            self.field_var.set("Repeat")
            self.value_var.set("2")
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def record_step_status(self, status: str) -> None:
        try:
            self.gui.record_step_status(
                step_no=self.step_var.get(),
                status=status,
                reason=self.reason_var.get(),
                operator_note=self.operator_note_var.get(),
            )
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def record_actual_material(self) -> None:
        try:
            self.gui.record_actual_material(
                step_no=self.step_var.get(),
                material=self.material_var.get(),
                amount=self.actual_amount_var.get(),
                amount_unit=self.actual_unit_var.get(),
                status=self.material_status_var.get(),
                reason=self.reason_var.get(),
                operator_note=self.operator_note_var.get(),
            )
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def revert_last(self) -> None:
        try:
            self.gui.revert_last_execution_change(
                reason=self.reason_var.get() or "Operator reverted last execution change",
                operator_note=self.operator_note_var.get(),
            )
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    @staticmethod
    def _display_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return "" if value is None else str(value)

    def _refresh_execution_history(self) -> None:
        for iid in self.execution_tree.get_children():
            self.execution_tree.delete(iid)
        try:
            history = self.gui.synthesis_execution_history()
        except Exception:
            history = []
        columns = list(self.execution_tree["columns"])
        for event in history:
            display = dict(event)
            display["before"] = self._display_value(event.get("before"))
            display["after"] = self._display_value(event.get("after"))
            self.execution_tree.insert(
                "", "end", values=[display.get(column, "") for column in columns],
            )
        children = self.execution_tree.get_children()
        if children:
            self.execution_tree.see(children[-1])

    @staticmethod
    def _bool_choice(value: Any) -> str:
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "Unknown"

    def save_ml_review(self) -> None:
        try:
            doubling = self.ml_doubling_var.get()
            self.gui.review_ml_observation(
                actual_yield_percent=self.ml_yield_var.get(),
                actual_purity_percent=self.ml_purity_var.get(),
                failure_flag=self.ml_failure_var.get(),
                doubling_required=("Unknown" if doubling == "Auto from execution" else doubling),
                included=self.ml_include_var.get(),
                exclusion_reason=self.ml_exclusion_var.get(),
                review_reason=self.ml_review_reason_var.get(),
                operator_note=self.ml_note_var.get(),
            )
            self.ml_review_reason_var.set("")
            self._ml_loaded_revision = -1
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def build_ml_dataset(self) -> None:
        try:
            info = self.gui.build_ml_dataset()
            action = "created" if info.get("created") else "unchanged"
            self.ml_result_var.set(f"Dataset v{info.get('version', 0)} {action}")
            self._refresh_ml_review()
        except Exception as exc:
            self._show_error(exc)

    def train_ml_model(self) -> None:
        try:
            metrics = self.gui.train_ml_model(self.ml_target_var.get(), None)
            metric = (
                f"accuracy={metrics.get('accuracy'):.3f}"
                if metrics.get("accuracy") is not None
                else f"MAE={metrics.get('mae'):.3f}"
            )
            self.ml_result_var.set(f"Trained {metrics.get('rows')} rows; {metric}")
            self._refresh_ml_review()
        except Exception as exc:
            self._show_error(exc)

    def predict_ml(self) -> None:
        try:
            result = self.gui.predict_ml_for_active_item(self.ml_target_var.get())
            self.ml_result_var.set(f"Prediction: {result.get('prediction')}")
        except Exception as exc:
            self._show_error(exc)

    def _refresh_ml_review(self) -> None:
        try:
            current = self.gui.active_ml_review()
        except Exception:
            current = {"revision": 0}
        revision = int(current.get("revision", 0) or 0)
        if revision != self._ml_loaded_revision:
            self.ml_yield_var.set("" if current.get("actual_yield_percent") is None else current.get("actual_yield_percent"))
            self.ml_purity_var.set("" if current.get("actual_purity_percent") is None else current.get("actual_purity_percent"))
            self.ml_failure_var.set(self._bool_choice(current.get("failure_flag")))
            doubling = current.get("doubling_required")
            self.ml_doubling_var.set(
                "Auto from execution" if current.get("doubling_source") == "inferred_from_execution"
                else self._bool_choice(doubling)
            )
            self.ml_include_var.set(bool(current.get("included", True)))
            self.ml_exclusion_var.set(str(current.get("exclusion_reason", "")))
            self.ml_note_var.set(str(current.get("operator_note", "")))
            self._ml_loaded_revision = revision
        try:
            status = self.gui.ml_dataset_status()
            targets = status.get("target_rows", {})
            target = self.ml_target_var.get()
            self.ml_status_var.set(
                f"v{status.get('current_version', 0)} | total {status.get('rows', 0)} | "
                f"reviewed {status.get('reviewed_rows', 0)} | included {status.get('included_rows', 0)} | "
                f"{target}: {targets.get(target, 0)} valid"
            )
        except Exception:
            pass
        for iid in self.ml_review_tree.get_children():
            self.ml_review_tree.delete(iid)
        try:
            versions = self.gui.ml_review_history()
        except Exception:
            versions = []
        for version in versions:
            after = dict(version.get("after", {}) or {})
            self.ml_review_tree.insert("", "end", values=(
                version.get("revision", ""), version.get("timestamp", ""),
                after.get("included", ""), after.get("actual_yield_percent", ""),
                after.get("actual_purity_percent", ""), after.get("failure_flag", ""),
                after.get("doubling_required", ""), version.get("reason", ""),
                version.get("version_id", ""),
            ))

    def _select_run(self, _event=None) -> None:
        selected = list(self.run_tree.selection())
        if not selected:
            return
        row = dict(zip(self.run_tree["columns"], self.run_tree.item(selected[0], "values")))
        self.selected_run_id = str(row.get("run_id", ""))
        self.run_name_var.set(str(row.get("name", "")))

    def create_run(self) -> None:
        try:
            run = self.gui.create_synthesis_run(
                self.run_name_var.get(), self.run_reason_var.get() or "New synthesis run",
            )
            self.selected_run_id = str(run.get("run_id", ""))
            self.run_reason_var.set("")
            self._ml_loaded_revision = -1
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def activate_run(self) -> None:
        try:
            if not self.selected_run_id:
                raise ValueError("Select a Run first.")
            self.gui.activate_synthesis_run(
                self.selected_run_id, self.run_reason_var.get() or "Operator selected run",
            )
            self.run_reason_var.set("")
            self._ml_loaded_revision = -1
            self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def _browse_hplc_file(self, key: str) -> None:
        selected = filedialog.askopenfilename(parent=self.window, filetypes=[("All files", "*.*")])
        if selected:
            self.hplc_vars[key].set(selected)

    def clear_hplc_form(self) -> None:
        for variable in self.hplc_vars.values():
            variable.set("")
        self.hplc_reason_var.set("")

    def save_hplc(self) -> None:
        try:
            values = {name: variable.get() for name, variable in self.hplc_vars.items()}
            record = self.gui.upsert_hplc_record(values, self.hplc_reason_var.get())
            self.hplc_vars["hplc_record_id"].set(record.get("hplc_record_id", ""))
            self.hplc_reason_var.set("")
            self._refresh_data()
        except Exception as exc:
            self._show_error(exc)

    def remove_hplc(self) -> None:
        try:
            record_id = self.hplc_vars["hplc_record_id"].get()
            if not record_id:
                raise ValueError("Select an HPLC record first.")
            self.gui.delete_hplc_record(record_id, self.hplc_reason_var.get())
            self.clear_hplc_form()
            self._refresh_data()
        except Exception as exc:
            self._show_error(exc)

    def _select_hplc(self, _event=None) -> None:
        selected = list(self.hplc_tree.selection())
        if not selected:
            return
        row = dict(zip(self.hplc_tree["columns"], self.hplc_tree.item(selected[0], "values")))
        record = getattr(self, "_hplc_row_by_id", {}).get(str(row.get("hplc_record_id", "")), row)
        for name, variable in self.hplc_vars.items():
            value = record.get(name, "")
            variable.set("" if value is None else value)

    def import_hplc(self) -> None:
        try:
            count = self.gui.import_hplc_table(reason="Imported HPLC table")
            self.data_status_var.set(f"Imported {count} HPLC rows")
            self._refresh_data()
        except Exception as exc:
            self._show_error(exc)

    def export_data_workbook(self) -> None:
        try:
            path = self.gui.export_data_workbook()
            if path:
                self.data_status_var.set(f"Exported {path}")
        except Exception as exc:
            self._show_error(exc)

    def import_data_workbook(self) -> None:
        try:
            path = self.gui.import_data_workbook()
            if path:
                self.data_status_var.set(f"Imported {path}")
                self._ml_loaded_revision = -1
                self.refresh()
        except Exception as exc:
            self._show_error(exc)

    def _render_risk(self, assessment: dict[str, Any]) -> None:
        self._risk_assessment = dict(assessment or {})
        for iid in self.risk_tree.get_children():
            self.risk_tree.delete(iid)
        for row in self._risk_assessment.get("findings", []):
            display = dict(row)
            display["positions"] = ", ".join(map(str, row.get("sequence_positions", [])))
            self.risk_tree.insert("", "end", values=[display.get(column, "") for column in self.risk_tree["columns"]])
        signals = [row for row in self._risk_assessment.get("ml_signals", []) if row.get("available")]
        ml_text = self._risk_assessment.get("ml_status", "ML unavailable: reviewed data/model insufficient")
        if signals:
            ml_text += " | " + ", ".join(
                f"{row['target']} p={float(row['positive_probability']):.3f}" if row.get("positive_probability") is not None else f"{row['target']}={row.get('prediction')}"
                for row in signals
            )
        revision = self._risk_assessment.get("revision", "unsaved")
        self.risk_status_var.set(
            f"Rule {self._risk_assessment.get('rule_level', 'INFO')} {self._risk_assessment.get('rule_score', 0)}/100 | "
            f"Findings {len(self._risk_assessment.get('findings', []))} | Revision {revision} | {ml_text}"
        )

    def evaluate_risk(self) -> None:
        try:
            self._commit_plan_to_main()
            self._render_risk(self.gui.evaluate_synthesis_risk())
        except Exception as exc:
            messagebox.showerror("Risk Review", str(exc), parent=self.window)

    def save_risk(self) -> None:
        try:
            assessment = self._risk_assessment or self.gui.evaluate_synthesis_risk()
            self._render_risk(self.gui.save_synthesis_risk(assessment))
        except Exception as exc:
            messagebox.showerror("Risk Review", str(exc), parent=self.window)

    def acknowledge_risk(self) -> None:
        selected = list(self.risk_tree.selection())
        if not selected:
            messagebox.showwarning("Risk Review", "Select a finding first.", parent=self.window); return
        finding_id = str(self.risk_tree.item(selected[0], "values")[-1])
        try:
            if not self._risk_assessment.get("assessment_id"):
                self._render_risk(self.gui.save_synthesis_risk(self._risk_assessment or self.gui.evaluate_synthesis_risk()))
            self.gui.acknowledge_risk_finding(finding_id, self.risk_ack_reason_var.get())
            self.risk_ack_reason_var.set("")
            self.risk_status_var.set(self.risk_status_var.get() + " | Selected finding acknowledged")
        except Exception as exc:
            messagebox.showerror("Risk Review", str(exc), parent=self.window)

    def export_risk(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.window, defaultextension=".xlsx",
            filetypes=[("Risk report", "*.xlsx")], initialfile="SPPS_Risk_Review.xlsx",
        )
        if not path:
            return
        try:
            self.gui.export_synthesis_risk(path)
            self.risk_status_var.set(f"Risk report exported: {path}")
        except Exception as exc:
            messagebox.showerror("Risk Review", str(exc), parent=self.window)

    def _refresh_risk(self) -> None:
        try:
            history = self.gui.synthesis_risk_history()
            versions = history.get("versions", [])
            if versions:
                self._render_risk(versions[-1])
            else:
                self._render_risk(self.gui.evaluate_synthesis_risk())
        except Exception as exc:
            self.risk_status_var.set(f"Risk review unavailable: {exc}")

    def _refresh_data(self) -> None:
        for iid in self.run_tree.get_children():
            self.run_tree.delete(iid)
        try:
            runs = self.gui.list_synthesis_runs()
        except Exception:
            runs = []
        active_id = ""
        try:
            index = int(self.gui._v229_active_index)
            item = self.gui.pm_items[index]
            active_id = str(item.get("active_run_id", ""))
            work_item_id = str(item.get("work_item_id", ""))
        except Exception:
            work_item_id = ""
        for run in runs:
            iid = self.run_tree.insert("", "end", values=[run.get(column, "") for column in self.run_tree["columns"]])
            if str(run.get("run_id", "")) == active_id:
                self.run_tree.selection_set(iid); self.run_tree.see(iid)
                self.selected_run_id = active_id
        try:
            rows = self.gui.search_hplc_records(
                self.hplc_search_var.get(), self.hplc_sort_var.get(), True,
            )
        except Exception:
            rows = []
        rows = [row for row in rows if str(row.get("work_item_id", "")) == work_item_id]
        self._hplc_row_by_id = {str(row.get("hplc_record_id", "")): row for row in rows}
        for iid in self.hplc_tree.get_children(): self.hplc_tree.delete(iid)
        for row in rows:
            self.hplc_tree.insert("", "end", values=[row.get(column, "") for column in self.hplc_tree["columns"]])
        for iid in self.data_history_tree.get_children(): self.data_history_tree.delete(iid)
        try:
            changes = self.gui.data_change_history()
        except Exception:
            changes = []
        for row in changes:
            display = dict(row)
            display["before"] = self._display_value(row.get("before"))
            display["after"] = self._display_value(row.get("after"))
            self.data_history_tree.insert("", "end", values=[display.get(column, "") for column in self.data_history_tree["columns"]])
        self.data_status_var.set(f"Runs {len(runs)} | HPLC {len(rows)} | Changes {len(changes)}")

    def _refresh_selected_tab(self, _event=None) -> None:
        try:
            label = str(self.notebook.tab(self.notebook.select(), "text"))
        except Exception:
            label = "Selected Plan"
        source_by_label = dict(TABLES)
        source_name = source_by_label.get(label)
        if source_name:
            source = getattr(self.gui, source_name, None)
            target = self.trees.get(source_name)
            if target is not None:
                _write_rows(target, _tree_rows(source))
            return
        if label == "Run / Corrections":
            self._refresh_execution_history()
        elif label == "Outcome / ML":
            self._refresh_ml_review()
        elif label == "Risk Review":
            self._refresh_risk()
        elif label == "Data / HPLC":
            self._refresh_data()

    def refresh(self) -> None:
        self.window.title(self._title())
        self._refresh_selected_tab()

    def save(self) -> None:
        self._commit_plan_to_main()
        plan_workflow._save_active(self.gui, include_outputs=True)
        self.gui.save_autosave_state()
        self.refresh()

    def generate(self) -> None:
        self.gui.generate_update_plan()
        self.refresh()

    def apply_change(self) -> None:
        self._commit_plan_to_main()
        self.gui.apply_change()
        self.refresh()

    def close(self) -> None:
        try:
            self.save()
        finally:
            self.gui._v3_work_item_window = None
            self.window.destroy()


def open_selected(gui: Any) -> str:
    """Open one independent window for the currently active item."""
    current = getattr(gui, "_v3_work_item_window", None)
    if current is not None:
        try:
            current.window.destroy()
        except Exception:
            pass
    gui._v3_work_item_window = WorkItemWindow(gui)
    return "break"


__all__ = ["WorkItemWindow", "open_selected"]
