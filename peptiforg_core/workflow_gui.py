from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

import csv
import json
import os
import subprocess
import sys
import queue
import threading
import traceback
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"

from peptiforg_core.project_io import new_project, load_project, save_project, relpath
from peptiforg_core.workflow_schema import SELECTED_CANDIDATE_COLUMNS
from peptiforg_core.candidate_manifest import stable_candidate_id, new_candidate_manifest, add_artifacts, write_manifest, resolve_candidate_id
from peptiforg_core.design_intent import normalize_design_intent
from peptiforg_core.output_bundle import create_result_bundle, write_bundle_manifest, build_bundle_zip
from peptiforg_core.candidate_summary_report import write_candidate_summary
from peptiforg_core.hotspot_workflow_bridge import ranked_region_to_transfer, write_design_handoff
from peptiforg_core.docking_lineage import lineage_record, export_lineage
from peptiforg_core.candidate_evidence_matrix import export_candidate_evidence_matrix, export_blind_review_matrix
from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.ui_theme import apply_pepforge_theme, fit_window, BORDER, SURFACE
from peptiforg_core.startup_runtime import StartupTrace, mark_window_visible
from peptiforg_core.workflow_pde_bridge import (
    QUALITY_OPTIONS, STRUCTURE_OPTIONS, run_pde_for_workflow,
    WORKFLOW_BASE_CHEM_TYPES, WORKFLOW_LINKER_TYPES, WORKFLOW_TAG_TYPES, WORKFLOW_LABEL_TYPES,
    build_workflow_chemistry_overrides, warm_pde_engine,
)
from peptiforg_core.workflow_state import derive_workflow_progress, mark_pde_dirty, mark_pde_clean
from spps_v4_gui.catalogs import RESIN_VALUES
from spps_v4_gui.resin_profiles import default_loading_for_resin


def _open_folder(path: Path):
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        messagebox.showerror("Open folder failed", str(e))


class WorkflowApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pepforge Workflow Mode")
        set_pepforge_icon(self.root)
        apply_pepforge_theme(self.root)
        fit_window(self.root, preferred_width=1240, preferred_height=880, minimum_width=1040, minimum_height=720)
        self._startup_trace = StartupTrace("workflow", ROOT / "workspace" / "workflow" / "logs")
        self.project_dir: Path | None = None
        self._loading_project = False
        self._external_hotspot_signature = None
        self._pde_queue = queue.Queue()
        self._pde_worker = None
        self._psb_queue = queue.Queue()
        self._psb_worker = None
        self._spps_queue = queue.Queue()
        self._spps_worker = None
        self._runtime_messages: list[str] = []
        self._build()
        # Import the PDE backend after the Workflow window is already visible.
        # This removes most first-click module initialization latency without
        # blocking Tk's event loop.
        threading.Thread(target=self._warm_pde_backend, daemon=True, name="PepforgePDEWarmup").start()
        self.root.after(700, self._poll_external_hotspot_selection)
        mark_window_visible(self.root, self._startup_trace)

    def _build(self):
        style = ttk.Style(self.root)
        style.configure("Sec.TLabel", font=("Segoe UI Semibold", 11))
        style.configure("Action.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Pepforge Workflow Mode", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Project-centered hand-off across Hot Spot → Design → Structure → SPPS, with stable candidate IDs and auditable artifacts.", style="Sub.TLabel", wraplength=1080).pack(anchor="w", pady=(6, 14))

        proj = ttk.LabelFrame(main, text="1. Project / Session", padding=12, style="Card.TLabelframe")
        proj.pack(fill="x", pady=6)
        row = ttk.Frame(proj); row.pack(fill="x")
        ttk.Label(row, text="Project name").pack(side="left")
        self.name_var = tk.StringVar(value="Pepforge_Project")
        ttk.Entry(row, textvariable=self.name_var, width=36).pack(side="left", padx=8)
        ttk.Button(row, text="Create new project", command=self.create_project, style="Action.TButton").pack(side="left", padx=4)
        ttk.Button(row, text="Open existing project", command=self.open_project).pack(side="left", padx=4)
        ttk.Button(row, text="Open project folder", command=self.open_project_folder).pack(side="left", padx=4)
        self.project_label = ttk.Label(proj, text="Current project: none")
        self.project_label.pack(anchor="w", pady=(8,0))

        # Keep only sections 2 and 4 as explicit square/rectangular panels.
        # ttk.LabelFrame borders can look visually open on some Windows/Tk
        # themes, so these two text-heavy areas use a real 1 px rectangle.
        seq_section = ttk.Frame(main)
        seq_section.pack(fill="x", pady=6)
        seq_header = ttk.Frame(seq_section)
        seq_header.pack(fill="x", pady=(0, 5))
        ttk.Label(seq_header, text="2. Shared Input Sequence", style="Sec.TLabel").pack(side="left")
        ttk.Button(seq_header, text="Save sequence to project", command=self.save_sequence).pack(side="left", padx=(12, 0))
        seqbox = tk.Frame(seq_section, background=SURFACE, highlightbackground=BORDER, highlightcolor=BORDER, highlightthickness=1, bd=0)
        seqbox.pack(fill="x")
        self.seq_text = tk.Text(seqbox, height=4, wrap="word", relief="flat", borderwidth=0, highlightthickness=0)
        self.seq_text.pack(fill="both", expand=True, padx=12, pady=12)

        progress_row = ttk.Frame(main)
        progress_row.pack(fill="x", pady=(2, 4))
        ttk.Label(progress_row, text="Workflow progress", style="Sec.TLabel").pack(side="left", padx=(0, 8))
        self.workflow_progress_var = tk.DoubleVar(value=0.0)
        self.workflow_progress = ttk.Progressbar(
            progress_row, variable=self.workflow_progress_var, maximum=100, mode="determinate",
            style="PepforgeGreen.Horizontal.TProgressbar",
        )
        self.workflow_progress.pack(side="left", fill="x", expand=True, padx=4)
        self.workflow_progress_text = tk.StringVar(value="Ready")
        ttk.Label(progress_row, textvariable=self.workflow_progress_text, width=34).pack(side="left", padx=(8, 0))

        steps = ttk.LabelFrame(main, text="3. Connected Workflow Actions", padding=12, style="Card.TLabelframe")
        steps.pack(fill="x", pady=6)

        ttk.Label(steps, text="Hot Spot Finder -> Peptide Design Engine", style="Sec.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        hotspot_flow = ttk.Frame(steps)
        hotspot_flow.grid(row=1, column=0, columnspan=4, sticky="ew", pady=4)
        hotspot_flow.columnconfigure(1, weight=1)
        ttk.Button(hotspot_flow, text="Run Hot Spot + Rank", command=self.run_hotspot).grid(row=0, column=0, sticky="ew", padx=(4, 6))
        self.hotspot_choice_var = tk.StringVar(value="")
        self.hotspot_choice_combo = ttk.Combobox(hotspot_flow, textvariable=self.hotspot_choice_var, state="readonly", width=58)
        self.hotspot_choice_combo.grid(row=0, column=1, sticky="ew", padx=4)
        self.hotspot_choice_combo.bind("<<ComboboxSelected>>", self._on_hotspot_choice)
        ttk.Button(hotspot_flow, text="Open Hot Spot Finder", command=lambda: self.launch_tool("hotspot")).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.hotspot_choice_detail = ttk.Label(steps, text="Run Hot Spot to generate ranked recommendations.", style="Sub.TLabel", wraplength=1080)
        self.hotspot_choice_detail.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 6))

        ttk.Label(steps, text="Peptide Design Engine", style="Sec.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        pde_row = ttk.Frame(steps)
        pde_row.grid(row=4, column=0, columnspan=4, sticky="ew", pady=4)
        pde_row.columnconfigure(1, weight=1)
        ttk.Label(pde_row, text="PDE target sequence").grid(row=0, column=0, sticky="w", padx=(4, 6))
        self.pde_target_var = tk.StringVar(value="")
        self.pde_target_entry = ttk.Entry(pde_row, textvariable=self.pde_target_var)
        self.pde_target_entry.grid(row=0, column=1, sticky="ew", padx=4)
        self.pde_target_entry.bind("<KeyRelease>", self._on_pde_target_manual_edit)
        ttk.Label(pde_row, text="Preferred structure").grid(row=0, column=2, sticky="w", padx=(10, 4))
        self.pde_structure_var = tk.StringVar(value=STRUCTURE_OPTIONS[0])
        self.pde_structure_combo = ttk.Combobox(
            pde_row, textvariable=self.pde_structure_var, values=STRUCTURE_OPTIONS,
            state="readonly", width=24,
        )
        self.pde_structure_combo.grid(row=0, column=3, sticky="ew", padx=4)
        self.pde_structure_combo.bind("<<ComboboxSelected>>", self._on_pde_structure_choice)
        ttk.Label(pde_row, text="Quality").grid(row=0, column=4, sticky="w", padx=(10, 4))
        self.pde_quality_var = tk.StringVar(value=QUALITY_OPTIONS[0])
        self.pde_quality_combo = ttk.Combobox(pde_row, textvariable=self.pde_quality_var, values=QUALITY_OPTIONS, state="readonly", width=22)
        self.pde_quality_combo.grid(row=0, column=5, sticky="ew", padx=4)
        self.pde_quality_combo.bind("<<ComboboxSelected>>", self._on_pde_quality_choice)
        self.pde_run_button = ttk.Button(pde_row, text="Run PDE", command=self.run_pde, style="Action.TButton")
        self.pde_run_button.grid(row=0, column=6, sticky="ew", padx=(8, 4))

        # Workflow exposes the same native PDE length controls rather than a
        # separate approximation. RANDOM uses Min/Max; FIX uses Fixed Length.
        self.pde_len_mode_var = tk.StringVar(value="RANDOM")
        self.pde_fix_len_var = tk.StringVar(value="24")
        self.pde_min_len_var = tk.StringVar(value="18")
        self.pde_max_len_var = tk.StringVar(value="30")
        ttk.Label(pde_row, text="Peptide length").grid(row=1, column=0, sticky="w", padx=(4, 6), pady=(5, 1))
        length_controls = ttk.Frame(pde_row)
        length_controls.grid(row=1, column=1, columnspan=6, sticky="w", padx=4, pady=(5, 1))
        ttk.Label(length_controls, text="Mode").pack(side="left")
        self.pde_len_mode_combo = ttk.Combobox(length_controls, textvariable=self.pde_len_mode_var, values=["RANDOM", "FIX"], state="readonly", width=9)
        self.pde_len_mode_combo.pack(side="left", padx=(4, 10))
        self.pde_len_mode_combo.bind("<<ComboboxSelected>>", self._on_pde_length_choice)
        ttk.Label(length_controls, text="Fixed").pack(side="left")
        self.pde_fix_len_entry = ttk.Entry(length_controls, textvariable=self.pde_fix_len_var, width=6)
        self.pde_fix_len_entry.pack(side="left", padx=(4, 10))
        ttk.Label(length_controls, text="Min").pack(side="left")
        self.pde_min_len_entry = ttk.Entry(length_controls, textvariable=self.pde_min_len_var, width=6)
        self.pde_min_len_entry.pack(side="left", padx=(4, 10))
        ttk.Label(length_controls, text="Max").pack(side="left")
        self.pde_max_len_entry = ttk.Entry(length_controls, textvariable=self.pde_max_len_var, width=6)
        self.pde_max_len_entry.pack(side="left", padx=(4, 10))
        for entry in (self.pde_fix_len_entry, self.pde_min_len_entry, self.pde_max_len_entry):
            entry.bind("<Return>", self._on_pde_length_choice)
            entry.bind("<FocusOut>", self._on_pde_length_choice)

        chemistry = ttk.Frame(steps)
        chemistry.grid(row=5, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 4))
        self.pde_use_d_var = tk.BooleanVar(value=True)
        self.pde_use_non_nat_var = tk.BooleanVar(value=True)
        self.pde_nterm_chem_var = tk.StringVar(value="Any")
        self.pde_linker_var = tk.StringVar(value="Any")
        self.pde_tag_var = tk.StringVar(value="Any")
        self.pde_label_var = tk.StringVar(value="Any")
        self.pde_cterm_var = tk.StringVar(value="NH2")
        ttk.Label(chemistry, text="PDE chemistry").grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 8), pady=(2, 0))
        ttk.Checkbutton(chemistry, text="D-AA", variable=self.pde_use_d_var, command=self._on_pde_chemistry_choice).grid(row=0, column=1, sticky="w", padx=3)
        ttk.Checkbutton(chemistry, text="Non-natural", variable=self.pde_use_non_nat_var, command=self._on_pde_chemistry_choice).grid(row=0, column=2, sticky="w", padx=3)
        top_selectors = [
            ("N-term chem", self.pde_nterm_chem_var, ["Any", "Off"] + WORKFLOW_BASE_CHEM_TYPES, 3),
            ("C-term", self.pde_cterm_var, ["NH2", "COOH"], 5),
        ]
        bottom_selectors = [
            ("Linker", self.pde_linker_var, ["Any", "Off"] + WORKFLOW_LINKER_TYPES, 1),
            ("Tag", self.pde_tag_var, ["Any", "Off"] + WORKFLOW_TAG_TYPES, 3),
            ("Label", self.pde_label_var, ["Any", "Off"] + WORKFLOW_LABEL_TYPES[1:], 5),
        ]
        for label, var, values, col in top_selectors:
            ttk.Label(chemistry, text=label).grid(row=0, column=col, sticky="e", padx=(10, 2), pady=2)
            combo = ttk.Combobox(chemistry, textvariable=var, values=values, state="readonly", width=12)
            combo.grid(row=0, column=col + 1, sticky="w", padx=(0, 4), pady=2)
            combo.bind("<<ComboboxSelected>>", self._on_pde_chemistry_choice)
        for label, var, values, col in bottom_selectors:
            ttk.Label(chemistry, text=label).grid(row=1, column=col, sticky="e", padx=(10, 2), pady=2)
            combo = ttk.Combobox(chemistry, textvariable=var, values=values, state="readonly", width=12)
            combo.grid(row=1, column=col + 1, sticky="w", padx=(0, 4), pady=2)
            combo.bind("<<ComboboxSelected>>", self._on_pde_chemistry_choice)

        self.pde_status_var = tk.StringVar(value="Select a Hot Spot recommendation; its sequence will appear here automatically.")
        ttk.Label(steps, textvariable=self.pde_status_var, style="Sub.TLabel", wraplength=1080).grid(row=6, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 4))

        candidate_row = ttk.Frame(steps)
        candidate_row.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(2, 4))
        candidate_row.columnconfigure(1, weight=1)
        ttk.Label(candidate_row, text="PDE candidate").grid(row=0, column=0, sticky="w", padx=(4, 6))
        self.candidate_var = tk.StringVar(value="")
        self.pde_candidate_var = tk.StringVar(value="")
        self.pde_candidate_combo = ttk.Combobox(candidate_row, textvariable=self.pde_candidate_var, state="readonly", width=70)
        self.pde_candidate_combo.grid(row=0, column=1, sticky="ew", padx=4)
        self.pde_candidate_combo.bind("<<ComboboxSelected>>", self._on_pde_candidate_choice)
        self.candidate_sequence_label = ttk.Label(candidate_row, text="No PDE candidate selected", style="Sub.TLabel")
        self.candidate_sequence_label.grid(row=0, column=2, sticky="w", padx=(8, 4))

        ttk.Label(steps, text="Peptide Structure Builder", style="Sec.TLabel").grid(row=8, column=0, columnspan=4, sticky="w", pady=(10, 0))

        # PDE candidates are handed directly into PSB.  Keep a second, explicit
        # selector under the PSB heading so the hand-off is visible instead of
        # forcing the user to infer it from the PDE row above.
        psb_input_row = ttk.Frame(steps)
        psb_input_row.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(3, 2))
        psb_input_row.columnconfigure(1, weight=1)
        ttk.Label(psb_input_row, text="PSB input candidate").grid(row=0, column=0, sticky="w", padx=(4, 6))
        self.psb_candidate_var = tk.StringVar(value="")
        self.psb_candidate_combo = ttk.Combobox(
            psb_input_row, textvariable=self.psb_candidate_var, state="readonly", width=70
        )
        self.psb_candidate_combo.grid(row=0, column=1, sticky="ew", padx=4)
        self.psb_candidate_combo.bind("<<ComboboxSelected>>", self._on_psb_candidate_choice)
        ttk.Label(psb_input_row, text="▼ PDE candidates", style="Sub.TLabel").grid(row=0, column=2, sticky="w", padx=(8, 4))

        struct_row = ttk.Frame(steps)
        struct_row.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(2, 0))
        struct_row.columnconfigure(2, weight=1)
        self.psb_run_button = ttk.Button(struct_row, text="Build Structure", command=self.run_psb, style="Action.TButton")
        self.psb_run_button.grid(row=0, column=0, sticky="ew", padx=(4, 8))
        ttk.Label(struct_row, text="Ranked structure").grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.structure_choice_var = tk.StringVar(value="")
        self.structure_choice_combo = ttk.Combobox(struct_row, textvariable=self.structure_choice_var, state="readonly", width=70)
        self.structure_choice_combo.grid(row=0, column=2, sticky="ew", padx=4)
        self.structure_choice_combo.bind("<<ComboboxSelected>>", self._on_structure_choice)
        ttk.Button(struct_row, text="Open Structure Output", command=self.open_selected_structure).grid(row=0, column=3, sticky="ew", padx=(8, 4))
        self.psb_status_var = tk.StringVar(value="Select a PDE candidate from the PSB input dropdown, then build its ranked structures.")
        ttk.Label(steps, textvariable=self.psb_status_var, style="Sub.TLabel", wraplength=1080).grid(row=11, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 4))

        evidence_row = ttk.Frame(steps)
        evidence_row.grid(row=12, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(evidence_row, text="Export Candidate Evidence Matrix", command=self.export_candidate_evidence_matrix).pack(side="left", padx=4)
        ttk.Button(evidence_row, text="Export Blind Review", command=self.export_blind_candidate_review).pack(side="left", padx=4)

        ttk.Label(steps, text="SPPS Planning", style="Sec.TLabel").grid(row=13, column=0, columnspan=4, sticky="w", pady=(10,0))
        srow = ttk.Frame(steps)
        srow.grid(row=14, column=0, columnspan=4, sticky="ew")
        ttk.Label(srow, text="Resin").pack(side="left")
        self.resin_var = tk.StringVar(value="Amide")
        self._workflow_resin_values = list(dict.fromkeys(RESIN_VALUES))
        self.resin_combo = ttk.Combobox(
            srow, textvariable=self.resin_var, values=self._workflow_resin_values,
            state="readonly", width=24
        )
        self.resin_combo.pack(side="left", padx=(6, 12))
        self.resin_combo.bind("<<ComboboxSelected>>", self._on_workflow_resin_choice)
        ttk.Label(srow, text="Loading mmol/g").pack(side="left")
        _default_workflow_loading = default_loading_for_resin("Amide")
        self.loading_var = tk.StringVar(value=f"{_default_workflow_loading:g}" if _default_workflow_loading is not None else "0.8")
        ttk.Entry(srow, textvariable=self.loading_var, width=10).pack(side="left", padx=(6, 12))
        ttk.Label(srow, text="Scale mmol").pack(side="left")
        self.scale_var = tk.StringVar(value="400")
        ttk.Entry(srow, textvariable=self.scale_var, width=10).pack(side="left", padx=(6, 12))
        self.spps_run_button = ttk.Button(srow, text="Open SPPS Planner", command=self.run_spps, style="Action.TButton")
        self.spps_run_button.pack(side="left", padx=6)
        self.spps_status_var = tk.StringVar(value="Select a PDE candidate; the standalone SPPS Planner will open with sequence/resin/loading/scale prefilled.")
        ttk.Label(steps, textvariable=self.spps_status_var, style="Sub.TLabel", wraplength=1080).grid(row=15, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 4))
        for col in range(4):
            steps.columnconfigure(col, weight=1)

        # The old bottom runtime text box duplicated the per-stage
        # status labels, progress bar, message dialogs, and Python logging.
        # Keep runtime messages internally/logged but do not spend Workflow UI
        # space on a second, non-actionable status panel.
        self.write_log("Workflow Mode ready. Create or open a project first.")

    def write_log(self, msg: str):
        text = str(msg)
        self._runtime_messages.append(text)
        if len(self._runtime_messages) > 500:
            del self._runtime_messages[:-500]
        LOGGER.info("Workflow: %s", text)

    def _set_workflow_progress(self, value: float, text: str) -> None:
        try:
            self.workflow_progress_var.set(max(0.0, min(100.0, float(value))))
            self.workflow_progress_text.set(str(text))
            self.root.update_idletasks()
        except Exception:
            LOGGER.debug("Workflow progress update skipped", exc_info=True)

    def _warm_pde_backend(self) -> None:
        try:
            warm_pde_engine()
            self.root.after(0, lambda: self.write_log("PDE backend ready."))
        except Exception:
            LOGGER.debug("PDE background warm-up failed", exc_info=True)

    def _pde_chemistry_overrides(self) -> dict:
        return build_workflow_chemistry_overrides(
            use_d=bool(self.pde_use_d_var.get()),
            use_non_nat=bool(self.pde_use_non_nat_var.get()),
            nterm_chem=self.pde_nterm_chem_var.get(),
            linker=self.pde_linker_var.get(),
            tag=self.pde_tag_var.get(),
            label=self.pde_label_var.get(),
            cterm=self.pde_cterm_var.get(),
        )

    def _pde_length_overrides(self) -> dict:
        mode = str(self.pde_len_mode_var.get() or "RANDOM").strip().upper()
        if mode not in {"RANDOM", "FIX"}:
            raise ValueError("Peptide length mode must be RANDOM or FIX.")
        try:
            fixed = int(str(self.pde_fix_len_var.get()).strip())
            minimum = int(str(self.pde_min_len_var.get()).strip())
            maximum = int(str(self.pde_max_len_var.get()).strip())
        except Exception as exc:
            raise ValueError("Peptide length values must be integers.") from exc
        if fixed <= 0 or minimum <= 0 or maximum <= 0:
            raise ValueError("Peptide length values must be greater than zero.")
        if mode == "RANDOM" and maximum < minimum:
            raise ValueError("PDE Max Length must be greater than or equal to Min Length.")
        return {
            "LEN_MODE": mode,
            "FIX_LENGTH": fixed,
            "MIN_LENGTH": minimum,
            "MAX_LENGTH": maximum,
            "LENGTH_COUNT_MODE": "TOKEN",
            "LENGTH_METRIC": "TOKEN",
            "TRIM_TO_LENGTH": True,
        }

    def _current_pde_settings_snapshot(self) -> dict:
        return {
            "target_sequence": self.pde_target_var.get().strip(),
            "preferred_structure": self.pde_structure_var.get(),
            "quality": self.pde_quality_var.get(),
            "length": {
                "mode": self.pde_len_mode_var.get(),
                "fixed": self.pde_fix_len_var.get(),
                "min": self.pde_min_len_var.get(),
                "max": self.pde_max_len_var.get(),
                "measurement": "TOKEN",
            },
            "chemistry": {
                "use_d": bool(self.pde_use_d_var.get()),
                "use_non_nat": bool(self.pde_use_non_nat_var.get()),
                "nterm_chem": self.pde_nterm_chem_var.get(),
                "linker": self.pde_linker_var.get(),
                "tag": self.pde_tag_var.get(),
                "label": self.pde_label_var.get(),
                "cterm": self.pde_cterm_var.get(),
            },
        }

    def _refresh_workflow_progress_from_project(self) -> None:
        if not self.project_dir:
            self._set_workflow_progress(0, "Ready")
            return
        try:
            project = load_project(self.project_dir)
            _stage, value, text = derive_workflow_progress(project)
            self._set_workflow_progress(value, text)
        except Exception:
            LOGGER.debug("Workflow progress derivation skipped", exc_info=True)

    def _mark_pde_inputs_dirty(self, status_text: str) -> None:
        self._clear_downstream_selection_ui()
        if self.project_dir:
            try:
                project = load_project(self.project_dir)
                mark_pde_dirty(project, self._current_pde_settings_snapshot())
                save_project(self.project_dir, project)
            except Exception:
                LOGGER.debug("Could not persist PDE dirty state", exc_info=True)
        self.pde_status_var.set(status_text)
        self._refresh_workflow_progress_from_project()

    def _on_pde_chemistry_choice(self, _event=None) -> None:
        self._mark_pde_inputs_dirty("PDE chemistry changed. Run PDE to regenerate candidates before PSB/SPPS.")

    def require_project(self) -> Path | None:
        if self.project_dir is None:
            messagebox.showwarning("No project", "Create or open a Pepforge project first.")
            return None
        return self.project_dir

    def set_project(self, folder: Path):
        self.project_dir = folder
        self.project_label.configure(text=f"Current project: {folder}")
        self._loading_project = True
        try:
            p = load_project(folder)
            self.seq_text.delete("1.0", "end")
            self.seq_text.insert("1.0", p.get("input_sequence", ""))
            cands = p.get("selected_candidates", [])
            self._populate_hotspot_choices(p.get("hotspot_ranked_regions", []), preserve_selected=p.get("selected_hotspots", []))
            selected_hotspots = p.get("selected_hotspots") or []
            selected_target = str(selected_hotspots[0].get("sequence", "")).strip() if selected_hotspots else ""

            workflow_state = dict(p.get("workflow_state") or {})
            pde_dirty = bool(workflow_state.get("pde_dirty"))
            pde_settings = dict(p.get("pde_settings") or {})
            pending_settings = dict(workflow_state.get("pending_pde_settings") or {}) if pde_dirty else {}
            visible_settings = pending_settings or pde_settings

            target = str(visible_settings.get("target_sequence", "")).strip() or selected_target
            self.pde_target_var.set(target)
            saved_structure = str(visible_settings.get("preferred_structure", "")).strip()
            if saved_structure in STRUCTURE_OPTIONS:
                self.pde_structure_var.set(saved_structure)
            saved_quality = str(visible_settings.get("quality", "")).strip()
            if saved_quality in QUALITY_OPTIONS:
                self.pde_quality_var.set(saved_quality)
            length_settings = dict(visible_settings.get("length") or {})
            if length_settings:
                mode = str(length_settings.get("mode", "RANDOM") or "RANDOM").upper()
                if mode in {"RANDOM", "FIX"}:
                    self.pde_len_mode_var.set(mode)
                self.pde_fix_len_var.set(str(length_settings.get("fixed", "24")))
                self.pde_min_len_var.set(str(length_settings.get("min", "18")))
                self.pde_max_len_var.set(str(length_settings.get("max", "30")))
            chemistry_settings = dict(visible_settings.get("chemistry") or {})
            if chemistry_settings:
                self.pde_use_d_var.set(bool(chemistry_settings.get("use_d", True)))
                self.pde_use_non_nat_var.set(bool(chemistry_settings.get("use_non_nat", True)))
                self.pde_nterm_chem_var.set(str(chemistry_settings.get("nterm_chem", "Any")))
                self.pde_linker_var.set(str(chemistry_settings.get("linker", "Any")))
                self.pde_tag_var.set(str(chemistry_settings.get("tag", "Any")))
                self.pde_label_var.set(str(chemistry_settings.get("label", "Any")))
                self.pde_cterm_var.set(str(chemistry_settings.get("cterm", "NH2")))

            saved_pde_target = str(pde_settings.get("target_sequence", "")).strip()
            target_mismatch = bool(selected_target and saved_pde_target and selected_target != saved_pde_target and not pending_settings)
            candidate_rows = [] if pde_dirty or target_mismatch else (p.get("design_results") or cands)
            self._populate_pde_candidates(candidate_rows, preserve_candidate_id=p.get("active_candidate_id"))
            if pde_dirty:
                self.pde_status_var.set("PDE settings changed after the last run. Rerun PDE before PSB/SPPS.")
            elif not candidate_rows:
                self.pde_status_var.set("Hot Spot target is ready. Run PDE to generate candidates in this Workflow window.")

            active_structure = p.get("active_structure") or {}
            candidate_id = str(p.get("active_candidate_id") or "") if candidate_rows else ""
            structure_rows = self._structure_rows_from_project(p, candidate_id)
            self._populate_structure_choices(structure_rows, preserve_path=active_structure.get("path"))
            _stage, value, text = derive_workflow_progress(p)
            self._set_workflow_progress(value, text)
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        finally:
            self._loading_project = False
        self.write_log(f"Project set: {folder}")

    def create_project(self):
        seq = self.seq_text.get("1.0", "end").strip()
        initial = Path.home()
        if self.project_dir is not None:
            initial = self.project_dir.parent
        base = filedialog.askdirectory(
            initialdir=str(initial),
            title="Choose location for the new Pepforge project",
            mustexist=True,
        )
        if not base:
            return
        folder = new_project(self.name_var.get(), seq, base_dir=Path(base))
        self.set_project(folder)

    def open_project(self):
        folder = filedialog.askdirectory(initialdir=str(ROOT / "projects"), title="Select Pepforge project folder")
        if folder:
            self.set_project(Path(folder))

    def open_project_folder(self):
        folder = self.require_project()
        if folder: _open_folder(folder)

    def save_sequence(self):
        folder = self.require_project()
        if not folder: return
        seq = self.seq_text.get("1.0", "end").strip()
        (folder / "input").mkdir(exist_ok=True)
        (folder / "input" / "input_sequence.txt").write_text(seq, encoding="utf-8")
        p = load_project(folder)
        p["input_sequence"] = seq
        p.setdefault("output_files", {})["input_sequence"] = "input/input_sequence.txt"
        save_project(folder, p)
        self.write_log("Saved input sequence to project.json and input/input_sequence.txt")

    def _hotspot_choice_label(self, row: dict) -> str:
        seq = str(row.get("region_sequence", row.get("sequence", "")))
        if len(seq) > 30:
            seq = seq[:27] + "..."
        try:
            priority = f"{float(row.get('priority_score', row.get('hotspot_score', 0.0))):.4f}"
        except Exception:
            priority = str(row.get("priority_score", row.get("hotspot_score", "")))
        return f"#{row.get('rank','?')} | {row.get('region_start','')}-{row.get('region_end','')} | {seq} | priority {priority}"

    def _populate_hotspot_choices(self, rows, preserve_selected=None):
        cleaned = [dict(row) for row in (rows or []) if str(row.get("region_sequence", row.get("sequence", ""))).strip()]
        self._hotspot_ranked_rows = cleaned
        self._hotspot_choice_map = {self._hotspot_choice_label(row): row for row in cleaned}
        values = list(self._hotspot_choice_map)
        self.hotspot_choice_combo.configure(values=values)
        wanted_rank = None
        if preserve_selected:
            try:
                wanted_rank = int((preserve_selected[0] or {}).get("rank", 0) or 0)
            except Exception:
                wanted_rank = None
        chosen = ""
        if wanted_rank:
            for label, row in self._hotspot_choice_map.items():
                if int(row.get("rank", 0) or 0) == wanted_rank:
                    chosen = label
                    break
        if not chosen and values:
            chosen = values[0]
        self.hotspot_choice_var.set(chosen)
        if chosen:
            self._on_hotspot_choice()
        else:
            self.hotspot_choice_detail.configure(text="No ranked Hot Spot recommendation is available.")

    def _selected_hotspot_rank_row(self):
        return getattr(self, "_hotspot_choice_map", {}).get(self.hotspot_choice_var.get())

    def _hotspot_transfer_row(self, row: dict) -> dict:
        return ranked_region_to_transfer(row)

    def _on_hotspot_choice(self, _event=None):
        row = self._selected_hotspot_rank_row()
        if not row:
            return
        try:
            priority = f"{float(row.get('priority_score', 0.0)):.4f}"
        except Exception:
            priority = str(row.get("priority_score", ""))
        self.hotspot_choice_detail.configure(
            text=f"Selected #{row.get('rank')} | region {row.get('region_start')}-{row.get('region_end')} | "
                 f"center ({row.get('center_position')}{row.get('center_residue')}) | priority {priority} | "
                 f"{row.get('why_hotspot','local window/context evidence')}"
        )
        self._sync_hotspot_to_pde_field(row)
        folder = self.project_dir
        if not folder:
            return
        try:
            transfer = self._hotspot_transfer_row(row)
            write_design_handoff(
                folder,
                [transfer],
                ranked_rows=getattr(self, "_hotspot_ranked_rows", []),
            )
            self._external_hotspot_signature = (str(transfer.get("rank", "")), str(transfer.get("sequence", "")))
            self.write_log(f"PDE hand-off synced to Hot Spot #{transfer.get('rank', '')}: {transfer.get('sequence', '')}")
        except Exception:
            LOGGER.debug("Hot Spot selection could not be synchronized", exc_info=True)

    def _on_pde_target_manual_edit(self, _event=None) -> None:
        target = self.pde_target_var.get().strip()
        self._mark_pde_inputs_dirty("PDE target edited manually. Run PDE for this target." if target else "PDE target sequence is empty.")

    def _on_pde_structure_choice(self, _event=None) -> None:
        self._mark_pde_inputs_dirty(f"Preferred structure set to {self.pde_structure_var.get()}. Run PDE to regenerate candidates.")

    def _on_pde_quality_choice(self, _event=None) -> None:
        self._mark_pde_inputs_dirty(f"PDE quality set to {self.pde_quality_var.get()}. Run PDE to regenerate candidates.")

    def _on_pde_length_choice(self, _event=None) -> None:
        if getattr(self, "_loading_project", False):
            return
        mode = self.pde_len_mode_var.get()
        self._mark_pde_inputs_dirty(f"PDE peptide length settings changed ({mode}). Run PDE to regenerate candidates.")

    def _on_workflow_resin_choice(self, _event=None) -> None:
        value = default_loading_for_resin(self.resin_var.get())
        if value is not None:
            self.loading_var.set(f"{value:g}")
            self.spps_status_var.set(f"{self.resin_var.get()} default loading applied from the SPPS settings database: {value:g} mmol/g.")

    def _clear_downstream_selection_ui(self) -> None:
        self._pde_candidate_rows = []
        self._pde_candidate_map = {}
        self.pde_candidate_combo.configure(values=[])
        self.pde_candidate_var.set("")
        self.candidate_var.set("")
        self.candidate_sequence_label.configure(text="No PDE candidate selected")
        if hasattr(self, "psb_candidate_combo"):
            self.psb_candidate_combo.configure(values=[])
            self.psb_candidate_var.set("")
        self._structure_choice_map = {}
        self.structure_choice_combo.configure(values=[])
        self.structure_choice_var.set("")
        self.psb_status_var.set("Select a PDE candidate from the PSB input dropdown, then build its ranked structures.")
        if hasattr(self, "spps_status_var"):
            self.spps_status_var.set("Select a PDE candidate; the standalone SPPS Planner will open with sequence/resin/loading/scale prefilled.")

    def _sync_hotspot_to_pde_field(self, row: dict | None) -> None:
        if not row:
            return
        sequence = str(row.get("region_sequence", row.get("sequence", ""))).strip()
        if not sequence:
            return
        previous = self.pde_target_var.get().strip()
        self.pde_target_var.set(sequence)
        if getattr(self, "_loading_project", False):
            self.pde_status_var.set(f"Hot Spot #{row.get('rank', '?')} linked to PDE target sequence.")
            return
        if previous and previous != sequence:
            self._mark_pde_inputs_dirty(f"Hot Spot #{row.get('rank', '?')} changed the PDE target. Run PDE for this target.")
        else:
            self.pde_status_var.set(f"Hot Spot #{row.get('rank', '?')} linked to PDE target sequence. Run PDE for this target.")

    def _pde_candidate_label(self, row: dict, fallback_rank: int) -> str:
        rank = row.get("rank", fallback_rank)
        seq = str(row.get("sequence", "")).strip()
        shown = seq if len(seq) <= 36 else seq[:33] + "..."
        score = row.get("total_score", row.get("score_total", ""))
        try:
            score_text = f"{float(score):.4f}"
        except Exception:
            score_text = str(score)
        structure = str(row.get("preferred_structure", "") or row.get("structure_preference", "")).strip()
        suffix = f" | score {score_text}" if score_text not in {"", "None"} else ""
        if structure and structure.upper() != "NONE":
            suffix += f" | {structure}"
        return f"#{rank} | {shown}{suffix}"

    def _populate_pde_candidates(self, rows, preserve_candidate_id=None) -> None:
        cleaned = [dict(row) for row in (rows or []) if str(row.get("sequence", "")).strip()]
        self._pde_candidate_rows = cleaned
        self._pde_candidate_map = {}
        values = []
        selected_label = ""
        for idx, row in enumerate(cleaned, start=1):
            label = self._pde_candidate_label(row, idx)
            while label in self._pde_candidate_map:
                label += " "
            self._pde_candidate_map[label] = row
            values.append(label)
            candidate_id = str(row.get("candidate_id", ""))
            if preserve_candidate_id and candidate_id == str(preserve_candidate_id):
                selected_label = label
        self.pde_candidate_combo.configure(values=values)
        if hasattr(self, "psb_candidate_combo"):
            self.psb_candidate_combo.configure(values=values)
        if not selected_label and values:
            selected_label = values[0]
        self.pde_candidate_var.set(selected_label)
        if hasattr(self, "psb_candidate_var"):
            self.psb_candidate_var.set(selected_label)
        if selected_label:
            self._on_pde_candidate_choice()
        else:
            self.candidate_var.set("")
            self.candidate_sequence_label.configure(text="No PDE candidate selected")

    def _selected_pde_candidate_row(self):
        return getattr(self, "_pde_candidate_map", {}).get(self.pde_candidate_var.get())

    def _on_psb_candidate_choice(self, _event=None) -> None:
        """Mirror the visible PSB input selector back to the active PDE candidate."""
        label = self.psb_candidate_var.get()
        if not label or label not in getattr(self, "_pde_candidate_map", {}):
            return
        self.pde_candidate_var.set(label)
        self._on_pde_candidate_choice()

    def _on_pde_candidate_choice(self, _event=None) -> None:
        row = self._selected_pde_candidate_row()
        if not row:
            return
        seq = str(row.get("sequence", "")).strip()
        self.candidate_var.set(seq)
        if hasattr(self, "psb_candidate_var"):
            self.psb_candidate_var.set(self.pde_candidate_var.get())
        rank = row.get("rank", "?")
        candidate_id = str(row.get("candidate_id", "")).strip() or stable_candidate_id(seq)
        self.candidate_sequence_label.configure(text=f"#{rank}  {seq}")
        self.psb_status_var.set(f"PDE candidate #{rank} selected. Build Structure will use this sequence.")
        self.spps_status_var.set(f"PDE candidate #{rank} linked to SPPS: {seq}")
        folder = self.project_dir
        if folder:
            try:
                p = load_project(folder)
                p["active_candidate_id"] = candidate_id
                p["active_candidate_sequence"] = seq
                p["active_structure"] = {}
                save_project(folder, p)
                self._populate_structure_choices(self._structure_rows_from_project(p, candidate_id))
                self._refresh_workflow_progress_from_project()
            except Exception:
                LOGGER.debug("Could not persist active PDE candidate", exc_info=True)

    def _ingest_pde_rows(self, rows, *, source_label: str = "workflow_pde") -> list[dict]:
        folder = self.require_project()
        if not folder:
            return []
        p = load_project(folder)
        imported = []
        for fallback_rank, row in enumerate(rows or [], start=1):
            row = dict(row)
            seq = str(row.get("sequence", "")).strip()
            if not seq:
                continue
            candidate_id = str(row.get("candidate_id", "")).strip() or stable_candidate_id(seq)
            manifest = new_candidate_manifest(
                seq,
                candidate_id=candidate_id,
                source=source_label,
                pareto_rank=row.get("pareto_rank", ""),
                legacy_total_score=row.get("total_score", row.get("score_total", "")),
                design_intent=normalize_design_intent({
                    "pde_objective_mode": row.get("pde_objective_mode", ""),
                    "preferred_structure": row.get("preferred_structure", ""),
                    "structure_direction_active": row.get("structure_direction_active", ""),
                    "structure_bias": row.get("structure_bias", ""),
                    "environment": row.get("structure_environment", ""),
                    "conformational_strategy": row.get("conformational_strategy", ""),
                    "hotspot_complementarity_mode": row.get("hotspot_complementarity_mode", ""),
                }),
                sequence_context={
                    "structure_preference_score": row.get("structure_preference_score", ""),
                    "hotspot_chemistry_complementarity_score": row.get("hotspot_chemistry_complementarity_score", ""),
                    "hotspot_chemistry_complementarity_status": row.get("hotspot_chemistry_complementarity_status", ""),
                    "hotspot_chemistry_complementarity_selection_active": row.get("hotspot_chemistry_complementarity_selection_active", ""),
                    "canonical_L_coverage": row.get("structure_context_canonical_L_coverage", ""),
                    "unsupported_structure_tokens": row.get("structure_context_unsupported_tokens", ""),
                    "spps_positional_risk_count": row.get("spps_positional_risk_count", ""),
                    "assembly_risk_positions": row.get("spps_assembly_risk_positions", ""),
                    "cleavage_risk_positions": row.get("spps_cleavage_risk_positions", ""),
                    "aggregation_risk_positions": row.get("aggregation_risk_positions", ""),
                },
            )
            manifest_path = folder / "design" / "candidate_manifests" / f"{candidate_id}.json"
            write_manifest(manifest_path, manifest)
            enriched = dict(row)
            enriched.update({
                "candidate_id": candidate_id,
                "sequence": manifest["sequence"],
                "core_sequence": row.get("clean_sequence", row.get("core_sequence", "")),
                "modifications": row.get("construct_tokens", row.get("modifications", "")),
                "rank": row.get("rank", fallback_rank),
                "score_total": row.get("total_score", row.get("score_total", "")),
                "pareto_rank": row.get("pareto_rank", ""),
                "manifest": relpath(folder, manifest_path),
                "note": "Pepforge Workflow PDE candidate",
            })
            imported.append(enriched)
            p.setdefault("candidate_manifests", {})[candidate_id] = relpath(folder, manifest_path)
        if not imported:
            raise ValueError("PDE returned no usable candidate sequences.")
        p["design_results"] = imported
        p["selected_candidates"] = [
            {key: row.get(key, "") for key in SELECTED_CANDIDATE_COLUMNS}
            for row in imported
        ]
        p["active_candidate_id"] = imported[0]["candidate_id"]
        p["active_candidate_sequence"] = imported[0]["sequence"]
        p["active_structure"] = {}
        out = folder / "design" / "selected_candidates.csv"
        out.parent.mkdir(exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=SELECTED_CANDIDATE_COLUMNS)
            writer.writeheader()
            for row in p["selected_candidates"]:
                writer.writerow(row)
        p.setdefault("output_files", {})["selected_candidates"] = relpath(folder, out)
        save_project(folder, p)
        self._populate_pde_candidates(imported, preserve_candidate_id=imported[0]["candidate_id"])
        return imported

    def run_pde(self) -> None:
        folder = self.require_project()
        if not folder:
            return
        if self._pde_worker and self._pde_worker.is_alive():
            messagebox.showinfo("PDE running", "Peptide Design Engine is already running in this Workflow window.")
            return
        target = "".join(self.pde_target_var.get().split()).upper()
        if not target:
            messagebox.showwarning("PDE target is empty", "Select a Hot Spot recommendation or enter a PDE target sequence.")
            return
        preferred_structure = self.pde_structure_var.get().strip() or STRUCTURE_OPTIONS[0]
        quality_profile = self.pde_quality_var.get().strip() or QUALITY_OPTIONS[0]
        profile_path = folder / "design" / "hotspot_chemistry_profile_for_PDE.json"
        try:
            chemistry_overrides = self._pde_chemistry_overrides()
            length_overrides = self._pde_length_overrides()
        except ValueError as exc:
            messagebox.showwarning("Invalid PDE settings", str(exc))
            return
        pde_overrides = {**chemistry_overrides, **length_overrides}
        outdir = create_result_bundle(folder / "design", name="PDE_Workflow", tool="PDE")
        self.pde_run_button.configure(state="disabled")
        self._pde_started_at = time.monotonic()
        self._set_workflow_progress(35, "PDE running")
        _length_label = (f"fixed {length_overrides['FIX_LENGTH']}" if length_overrides["LEN_MODE"] == "FIX" else f"{length_overrides['MIN_LENGTH']}-{length_overrides['MAX_LENGTH']}")
        self.pde_status_var.set(f"PDE running inside Workflow Mode: target {target} | length {_length_label} | structure {preferred_structure} | {quality_profile}")
        self.write_log(f"PDE started in Workflow Mode for target: {target}")

        def worker():
            try:
                result = run_pde_for_workflow(
                    target,
                    preferred_structure,
                    outdir,
                    quality_profile=quality_profile,
                    hotspot_profile_path=profile_path if profile_path.exists() else None,
                    config_overrides=pde_overrides,
                )
                self._pde_queue.put(("done", result))
            except Exception:
                self._pde_queue.put(("error", traceback.format_exc()))

        self._pde_worker = threading.Thread(target=worker, daemon=True, name="PepforgeWorkflowPDE")
        self._pde_worker.start()
        self.root.after(150, self._poll_pde_worker)

    def _poll_pde_worker(self) -> None:
        try:
            kind, payload = self._pde_queue.get_nowait()
        except queue.Empty:
            if self._pde_worker and self._pde_worker.is_alive():
                elapsed = int(time.monotonic() - getattr(self, "_pde_started_at", time.monotonic()))
                self.workflow_progress_text.set(f"PDE running · {elapsed}s")
                self.root.after(150, self._poll_pde_worker)
            else:
                self.pde_run_button.configure(state="normal")
            return
        self.pde_run_button.configure(state="normal")
        if kind == "error":
            self._set_workflow_progress(25, "PDE failed")
            self.pde_status_var.set("PDE failed. See the error dialog/log for details.")
            self.write_log(payload)
            messagebox.showerror("PDE run failed", payload.splitlines()[-1] if payload else "Unknown PDE error")
            return
        try:
            result = dict(payload)
            imported = self._ingest_pde_rows(result.get("top_rows") or [], source_label="workflow_pde")
            paths = result.get("paths") or {}
            folder = self.require_project()
            if folder:
                p = load_project(folder)
                for key, value in paths.items():
                    try:
                        path = Path(value)
                    except Exception:
                        continue
                    if path.exists():
                        p.setdefault("output_files", {})[f"pde_{key}"] = relpath(folder, path)
                p["pde_settings"] = self._current_pde_settings_snapshot()
                mark_pde_clean(p)
                save_project(folder, p)
                active_id = str(p.get("active_candidate_id") or "")
                self._populate_structure_choices(self._structure_rows_from_project(p, active_id))
            self._refresh_workflow_progress_from_project()
            self.pde_status_var.set(f"PDE complete: {len(imported)} ranked candidate(s). Choose one below; PSB/SPPS use it immediately.")
            self.write_log(f"PDE completed in Workflow Mode. {len(imported)} candidate(s) ready.")
        except Exception as exc:
            self.pde_status_var.set("PDE result import failed.")
            self.write_log(f"PDE result import failed: {type(exc).__name__}: {exc}")
            messagebox.showerror("PDE result import failed", str(exc))

    def _structure_rows_from_project(self, project: dict, candidate_id: str) -> list[dict]:
        if not candidate_id:
            return []
        result = dict((project.get("structure_results") or {}).get(candidate_id) or {})
        current_revision = int((project.get("workflow_state") or {}).get("pde_revision") or 0)
        result_revision = int(result.get("workflow_pde_revision") or 0)
        if current_revision and result_revision != current_revision:
            return []
        rows = []
        for rank in range(1, 6):
            rel = result.get(f"top{rank}_pdb") or result.get(f"top{rank}_canonical_view_pdb")
            if not rel:
                continue
            path = Path(rel)
            if not path.is_absolute() and self.project_dir:
                path = self.project_dir / path
            rows.append({"rank": rank, "path": str(path)})
        return rows

    def _populate_structure_choices(self, rows, preserve_path=None) -> None:
        cleaned = [dict(row) for row in (rows or []) if str(row.get("path", "")).strip()]
        self._structure_choice_map = {}
        values = []
        selected = ""
        for row in cleaned:
            path = Path(str(row["path"]))
            label = f"#{row.get('rank', '?')} | {path.name}"
            self._structure_choice_map[label] = row
            values.append(label)
            if preserve_path and str(path) == str(preserve_path):
                selected = label
        self.structure_choice_combo.configure(values=values)
        if not selected and values:
            selected = values[0]
        self.structure_choice_var.set(selected)
        if selected:
            self._on_structure_choice()

    def _on_structure_choice(self, _event=None) -> None:
        row = getattr(self, "_structure_choice_map", {}).get(self.structure_choice_var.get())
        if not row or not self.project_dir:
            return
        try:
            p = load_project(self.project_dir)
            p["active_structure"] = {"rank": row.get("rank"), "path": row.get("path"), "candidate_id": p.get("active_candidate_id", "")}
            save_project(self.project_dir, p)
        except Exception:
            LOGGER.debug("Could not persist active structure", exc_info=True)

    def open_selected_structure(self) -> None:
        row = getattr(self, "_structure_choice_map", {}).get(self.structure_choice_var.get())
        if not row:
            messagebox.showinfo("No structure", "Build Structure first and select a structure result.")
            return
        path = Path(str(row.get("path", "")))
        if path.exists():
            _open_folder(path.parent)
        else:
            messagebox.showwarning("Structure missing", f"Structure file not found:\n{path}")

    def run_hotspot(self):
        folder = self.require_project()
        if not folder: return
        self.save_sequence()
        seq = self.seq_text.get("1.0", "end").strip()
        if not seq:
            messagebox.showwarning("Empty sequence", "Input sequence is empty.")
            return
        try:
            self._set_workflow_progress(8, "Hot Spot ranking")
            sys.path.insert(0, str(APPS / "hotspot_finder"))
            from sequence_hotspot_finder.engine import analyze_input
            outdir = create_result_bundle(folder / "hotspot", sequence=seq, tool="Hotspot")
            token_db = APPS / "hotspot_finder" / "data" / "token_db.csv"
            sidechain = APPS / "hotspot_finder" / "data" / "sidechain_mod_db.csv"
            result = analyze_input(
                seq, token_db_path=token_db, sidechain_mod_db_path=sidechain, outdir=outdir,
                config={"use_esm": False, "top_n": 30, "ranking_window_size": 15, "ranking_overlap": 5, "ranking_min_score": 0.0},
            )
            p = load_project(folder)
            had_downstream = bool(p.get("design_results") or p.get("active_candidate_id") or p.get("spps_settings"))
            p.setdefault("output_files", {})["hotspot_full_csv"] = relpath(folder, result["full_csv"])
            p.setdefault("output_files", {})["hotspot_top_csv"] = relpath(folder, result["top_csv"])
            if result.get("ranked_regions_csv"):
                p.setdefault("output_files", {})["hotspot_ranked_regions_csv"] = relpath(folder, result["ranked_regions_csv"])
            p.setdefault("output_files", {})["hotspot_zip"] = relpath(folder, result["zip_path"])
            top_df = result.get("top_df")
            p["hotspot_results"] = [] if top_df is None else top_df.head(30).fillna("").to_dict("records")
            ranked_df = result.get("ranked_regions_df")
            ranked_rows = [] if ranked_df is None else ranked_df.fillna("").to_dict("records")
            p["hotspot_ranked_regions"] = ranked_rows
            if ranked_rows:
                p["selected_hotspots"] = [self._hotspot_transfer_row(ranked_rows[0])]
            else:
                p["selected_hotspots"] = []
            save_project(folder, p)
            self._populate_hotspot_choices(ranked_rows, preserve_selected=p.get("selected_hotspots"))
            if had_downstream:
                latest = load_project(folder)
                mark_pde_dirty(latest, self._current_pde_settings_snapshot())
                save_project(folder, latest)
                self._clear_downstream_selection_ui()
                self.pde_status_var.set("Hot Spot ranking was regenerated. Rerun PDE so downstream results use the current evidence.")
                self._refresh_workflow_progress_from_project()
            else:
                self._set_workflow_progress(25, "Hot Spot ready")
            self.write_log(f"Hot Spot ranking completed. {len(ranked_rows)} recommendation(s) available. Outputs: {outdir}")
        except Exception as e:
            self._set_workflow_progress(0, "Hot Spot failed")
            messagebox.showerror("Hot Spot run failed", str(e))
            self.write_log(f"Hot Spot run failed: {type(e).__name__}: {e}")

    def create_hotspot_transfer(self, silent: bool = False):
        folder = self.require_project()
        if not folder:
            return
        p = load_project(folder)
        rows = p.get("selected_hotspots") or []
        if not rows:
            seq = self.seq_text.get("1.0", "end").strip()
            rows = [{"region_start": "", "region_end": "", "sequence": seq, "hotspot_score": "", "record_name": "manual", "note": "Manual transfer row"}]
        paths = write_design_handoff(folder, rows, ranked_rows=p.get("hotspot_ranked_regions", []))
        self.write_log(f"Design hand-off prepared: {paths['selected_hotspots_csv']}")
        if not silent:
            self.write_log("Hot Spot chemistry evidence profile is ready for PDE; the ranking is heuristic and not an affinity claim.")

    def _poll_external_hotspot_selection(self):
        try:
            if self.project_dir is not None:
                p = load_project(self.project_dir)
                selected = p.get("selected_hotspots") or []
                row = selected[0] if selected else {}
                signature = (str(row.get("rank", "")), str(row.get("sequence", "")))
                if signature != self._external_hotspot_signature and str(row.get("sequence", "")).strip():
                    self._external_hotspot_signature = signature
                    self._populate_hotspot_choices(p.get("hotspot_ranked_regions", []), preserve_selected=selected)
        except Exception:
            LOGGER.debug("External Hot Spot selection poll skipped", exc_info=True)
        finally:
            self.root.after(700, self._poll_external_hotspot_selection)

    def save_candidate(self):
        folder = self.require_project()
        if not folder: return
        seq = self.candidate_var.get().strip()
        if not seq:
            messagebox.showwarning("Empty candidate", "Candidate sequence is empty.")
            return
        p = load_project(folder)
        candidate_id = stable_candidate_id(seq)
        manifest = new_candidate_manifest(seq, candidate_id=candidate_id, source="workflow_manual_selection")
        manifest_path = folder / "design" / "candidate_manifests" / f"{candidate_id}.json"
        write_manifest(manifest_path, manifest)
        cand = {"candidate_id": candidate_id, "sequence": manifest["sequence"], "core_sequence": "", "modifications": "", "rank": len(p.get('selected_candidates', []))+1, "score_total": "", "pareto_rank": "", "manifest": relpath(folder, manifest_path), "note": "Manual or Design Engine selected candidate"}
        p.setdefault("candidate_manifests", {})[candidate_id] = relpath(folder, manifest_path)
        p.setdefault("selected_candidates", []).append(cand)
        out = folder / "design" / "selected_candidates.csv"
        out.parent.mkdir(exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=SELECTED_CANDIDATE_COLUMNS)
            writer.writeheader()
            for r in p["selected_candidates"]:
                writer.writerow({k: r.get(k, "") for k in SELECTED_CANDIDATE_COLUMNS})
        p.setdefault("output_files", {})["selected_candidates"] = relpath(folder, out)
        save_project(folder, p)
        self.write_log(f"Saved selected candidate and transfer CSV: {seq}")

    def export_candidate_evidence_matrix(self):
        folder = self.require_project()
        if not folder:
            return
        try:
            p = load_project(folder)
            summaries = []
            for candidate_id, manifest_rel in dict(p.get("candidate_manifests") or {}).items():
                manifest_path = folder / manifest_rel
                if not manifest_path.exists():
                    continue
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                summary = write_candidate_summary(folder / "exports" / candidate_id, manifest, project_dir=folder)
                summaries.append(json.loads(Path(summary["summary_json"]).read_text(encoding="utf-8")))
            outdir = folder / "exports" / "candidate_comparison"
            paths = export_candidate_evidence_matrix(summaries, outdir)
            p.setdefault("output_files", {})["candidate_evidence_matrix_json"] = relpath(folder, paths["json"])
            p.setdefault("output_files", {})["candidate_evidence_matrix_csv"] = relpath(folder, paths["csv"])
            save_project(folder, p)
            self.write_log(f"Exported candidate evidence matrix for {len(summaries)} candidate(s): {outdir}")
        except Exception as exc:
            messagebox.showerror("Candidate comparison failed", str(exc))
            self.write_log(f"Candidate comparison failed: {type(exc).__name__}: {exc}")

    def export_blind_candidate_review(self):
        folder = self.require_project()
        if not folder:
            return
        try:
            p = load_project(folder)
            summaries=[]
            for candidate_id, manifest_rel in dict(p.get("candidate_manifests") or {}).items():
                manifest_path=folder/manifest_rel
                if not manifest_path.exists(): continue
                manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
                summary_paths=write_candidate_summary(folder/"exports"/candidate_id,manifest,project_dir=folder)
                summaries.append(json.loads(Path(summary_paths["summary_json"]).read_text(encoding="utf-8")))
            outdir=folder/"exports"/"candidate_comparison"/"blind_review"
            paths=export_blind_review_matrix(summaries,outdir,hide_sequence=True)
            p.setdefault("output_files",{})["candidate_blind_review_json"]=relpath(folder,paths["blind_json"])
            p.setdefault("output_files",{})["candidate_blind_review_csv"]=relpath(folder,paths["blind_csv"])
            p.setdefault("output_files",{})["candidate_blind_reveal_mapping_json"]=relpath(folder,paths["reveal_mapping_json"])
            save_project(folder,p)
            self.write_log(f"Exported de-identified candidate evidence review for {len(summaries)} candidate(s): {outdir}")
        except Exception as exc:
            messagebox.showerror("Blind candidate review failed",str(exc))
            self.write_log(f"Blind candidate review failed: {type(exc).__name__}: {exc}")

    def _execute_psb_build(self, folder: Path, seq: str) -> dict:
        from peptiforg_core.pymol_structure_builder import export_modified_peptide_structure

        p = load_project(folder)
        candidate_id = resolve_candidate_id(seq, p.get("selected_candidates", []))
        outdir = create_result_bundle(folder / "structure", sequence=seq, tool="PSB")
        manifest_rel = p.get("candidate_manifests", {}).get(candidate_id)
        manifest_path = folder / manifest_rel if manifest_rel else folder / "design" / "candidate_manifests" / f"{candidate_id}.json"
        prior_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        design_intent = normalize_design_intent(prior_manifest.get("design_intent") or {})
        paths = export_modified_peptide_structure(
            seq, outdir, name=candidate_id,
            environment_conditions={
                "environment": design_intent.get("environment") or "aqueous_unspecified",
                "pde_design_intent": design_intent,
            },
            num_confs=12, max_iters=200, num_threads=2,
            search_profile="evidence_balanced", min_final_conformers=5, max_embedding_retries=3,
        )
        lineage_rows = []
        for rank in range(1, 6):
            structure_path = paths.get(f"top{rank}_canonical_view_pdb") or paths.get(f"top{rank}_pdb")
            if structure_path:
                lineage_rows.append(lineage_record(
                    candidate_id, seq, conformer_rank=rank, structure_path=structure_path,
                    docking_status="prepared_only",
                    notes="Pepforge V4 lineage preparation; actual docking pose generation is reserved for a validated docking workflow."
                ))
        lineage_paths = export_lineage(lineage_rows, folder / "exports" / candidate_id / "docking_lineage")
        paths.update({
            "docking_lineage_json": lineage_paths["lineage_json"],
            "docking_lineage_csv": lineage_paths["lineage_csv"],
            "pymol_docking_review_pml": lineage_paths["pymol_review_pml"],
        })
        p = load_project(folder)
        manifest_rel = p.get("candidate_manifests", {}).get(candidate_id)
        manifest_path = folder / manifest_rel if manifest_rel else folder / "design" / "candidate_manifests" / f"{candidate_id}.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = new_candidate_manifest(seq, candidate_id=candidate_id, source="workflow_structure_build")
        manifest = add_artifacts(manifest, "structure_builder", paths)
        summary_paths = write_candidate_summary(folder / "exports" / candidate_id, manifest, project_dir=folder)
        manifest = add_artifacts(manifest, "candidate_summary", summary_paths)
        write_manifest(manifest_path, manifest)
        p.setdefault("candidate_manifests", {})[candidate_id] = relpath(folder, manifest_path)
        structure_record = {
            key: relpath(folder, value) for key, value in paths.items() if Path(value).exists()
        }
        structure_record["workflow_pde_revision"] = int((p.get("workflow_state") or {}).get("pde_revision") or 0)
        p.setdefault("structure_results", {})[candidate_id] = structure_record
        p.setdefault("output_files", {})[f"summary_{candidate_id}_json"] = relpath(folder, summary_paths["summary_json"])
        p.setdefault("output_files", {})[f"summary_{candidate_id}_txt"] = relpath(folder, summary_paths["summary_txt"])
        zip_path = build_bundle_zip(outdir, filename="PSB_Result_Package.zip")
        write_bundle_manifest(outdir, tool="PSB", sequence=seq, artifacts={**paths, "zip": zip_path})
        p.setdefault("output_files", {})[f"psb_{candidate_id}_json"] = relpath(folder, paths["json"])
        p.setdefault("output_files", {})[f"psb_{candidate_id}_zip"] = relpath(folder, zip_path)
        save_project(folder, p)
        return {"candidate_id": candidate_id, "outdir": str(outdir)}

    def run_psb(self):
        folder = self.require_project()
        if not folder:
            return
        if self._psb_worker and self._psb_worker.is_alive():
            messagebox.showinfo("Structure build running", "Peptide Structure Builder is already running in this Workflow window.")
            return
        seq = self.candidate_var.get().strip()
        if not seq:
            messagebox.showwarning("Empty candidate", "Choose a PDE candidate (PDE or PSB input dropdown) first.")
            return
        self.psb_run_button.configure(state="disabled")
        self._psb_started_at = time.monotonic()
        self._set_workflow_progress(70, "Structure building")
        self.psb_status_var.set(f"Building ranked structures for: {seq}")
        self.write_log("Structure Builder started in Workflow Mode. The UI remains responsive while conformers are generated.")

        def worker():
            try:
                self._psb_queue.put(("done", self._execute_psb_build(folder, seq)))
            except Exception:
                self._psb_queue.put(("error", traceback.format_exc()))

        self._psb_worker = threading.Thread(target=worker, daemon=True, name="PepforgeWorkflowPSB")
        self._psb_worker.start()
        self.root.after(150, self._poll_psb_worker)

    def _poll_psb_worker(self) -> None:
        try:
            kind, payload = self._psb_queue.get_nowait()
        except queue.Empty:
            if self._psb_worker and self._psb_worker.is_alive():
                elapsed = int(time.monotonic() - getattr(self, "_psb_started_at", time.monotonic()))
                self.workflow_progress_text.set(f"Structure building · {elapsed}s")
                self.root.after(150, self._poll_psb_worker)
            else:
                self.psb_run_button.configure(state="normal")
            return
        self.psb_run_button.configure(state="normal")
        if kind == "error":
            self._set_workflow_progress(60, "Structure build failed")
            self.psb_status_var.set("Structure build failed. See the error dialog/log for details.")
            self.write_log(payload)
            messagebox.showerror("PSB run failed", payload.splitlines()[-1] if payload else "Unknown PSB error")
            return
        result = dict(payload)
        candidate_id = str(result.get("candidate_id", ""))
        try:
            p = load_project(self.project_dir) if self.project_dir else {}
            structure_rows = self._structure_rows_from_project(p, candidate_id)
            self._populate_structure_choices(structure_rows)
            self._refresh_workflow_progress_from_project()
            self.psb_status_var.set(f"Structure build complete: {len(structure_rows)} ranked structure(s) ready.")
            self.write_log(f"Structure build completed for {candidate_id}. Outputs: {result.get('outdir', '')}")
        except Exception as exc:
            self.psb_status_var.set("Structure build completed, but result refresh failed.")
            self.write_log(f"Structure result refresh failed: {type(exc).__name__}: {exc}")

    def _execute_spps_plan(self, folder: Path, seq: str, resin: str, loading: float, scale: float) -> dict:
        sys.path.insert(0, str(APPS / "spps_planner_app"))
        from spps_planner.engine import PlanInput
        from spps_planner.export import export_csvs, export_excel

        inp = PlanInput(sequence=seq, resin=resin, scale_mmol=scale, resin_loading_mmol_g=loading)
        outdir = create_result_bundle(folder / "spps", sequence=seq, tool="SPPS")
        export_csvs(inp, outdir)
        xlsx = outdir / "spps_planning_workbook.xlsx"
        export_excel(inp, xlsx)
        p = load_project(folder)
        zip_path = build_bundle_zip(outdir, filename="SPPS_Result_Package.zip")
        write_bundle_manifest(outdir, tool="SPPS", sequence=seq, artifacts={"zip": zip_path, "workbook": xlsx})
        p.setdefault("output_files", {}).update({
            "spps_summary": relpath(folder, outdir / "summary.csv"),
            "spps_step_matrix": relpath(folder, outdir / "step_matrix.csv"),
            "spps_synthesis_form": relpath(folder, outdir / "synthesis_form_wash_by_wash.csv"),
            "spps_raw_material_use": relpath(folder, outdir / "raw_material_use.csv"),
            "spps_workbook": relpath(folder, xlsx),
            "spps_zip": relpath(folder, zip_path),
        })
        candidate_id = resolve_candidate_id(seq, p.get("selected_candidates", []))
        p["spps_settings"] = {
            "sequence": seq, "candidate_id": candidate_id, "resin_type": resin, "resin_loading_mmol_g": loading, "scale_mmol": scale,
            "workflow_pde_revision": int((p.get("workflow_state") or {}).get("pde_revision") or 0),
        }
        manifest_rel = p.get("candidate_manifests", {}).get(candidate_id)
        manifest_path = folder / manifest_rel if manifest_rel else folder / "design" / "candidate_manifests" / f"{candidate_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else new_candidate_manifest(seq, candidate_id=candidate_id, source="workflow_spps")
        manifest = add_artifacts(manifest, "spps_planner", {
            "summary": outdir / "summary.csv", "step_matrix": outdir / "step_matrix.csv",
            "synthesis_form": outdir / "synthesis_form_wash_by_wash.csv",
            "raw_material_use": outdir / "raw_material_use.csv", "workbook": xlsx,
        })
        summary_paths = write_candidate_summary(folder / "exports" / candidate_id, manifest, project_dir=folder)
        manifest = add_artifacts(manifest, "candidate_summary", summary_paths)
        write_manifest(manifest_path, manifest)
        p.setdefault("candidate_manifests", {})[candidate_id] = relpath(folder, manifest_path)
        p.setdefault("output_files", {})[f"summary_{candidate_id}_json"] = relpath(folder, summary_paths["summary_json"])
        p.setdefault("output_files", {})[f"summary_{candidate_id}_txt"] = relpath(folder, summary_paths["summary_txt"])
        save_project(folder, p)
        return {"candidate_id": candidate_id, "outdir": str(outdir), "sequence": seq}

    def run_spps(self):
        """Open the full SPPS Planner with the active Workflow candidate prefilled."""
        folder = self.require_project()
        if not folder:
            return
        seq = self.candidate_var.get().strip()
        if not seq:
            messagebox.showwarning("Empty candidate", "Choose a PDE candidate first.")
            return
        resin = self.resin_var.get().strip()
        try:
            loading = float(self.loading_var.get())
            scale = float(self.scale_var.get())
        except Exception:
            messagebox.showwarning("Invalid SPPS input", "Loading mmol/g and Scale mmol must both be numeric.")
            return
        if loading <= 0 or scale <= 0:
            messagebox.showwarning("Invalid SPPS input", "Loading mmol/g and Scale mmol must both be greater than zero.")
            return

        # Save only a hand-off snapshot.  Do not mark SPPS complete until the
        # planner itself has produced a plan/artifact.
        try:
            project = load_project(folder)
            state = dict(project.get("workflow_state") or {})
            state["spps_handoff"] = {
                "sequence": seq,
                "candidate_id": str(project.get("active_candidate_id") or ""),
                "resin": resin,
                "resin_loading_mmol_g": loading,
                "scale_mmol": scale,
                "workflow_pde_revision": int(state.get("pde_revision") or 0),
            }
            project["workflow_state"] = state
            save_project(folder, project)
        except Exception:
            LOGGER.debug("Could not persist SPPS hand-off snapshot", exc_info=True)

        self.spps_status_var.set(
            f"Opening SPPS Planner for {seq} | {resin} | loading {loading:g} mmol/g | scale {scale:g} mmol"
        )
        self.write_log("Opening the full SPPS Planner with the Workflow candidate and synthesis inputs prefilled.")
        self.launch_tool("spps")
        self._refresh_workflow_progress_from_project()

    def _poll_spps_worker(self) -> None:
        try:
            kind, payload = self._spps_queue.get_nowait()
        except queue.Empty:
            if self._spps_worker and self._spps_worker.is_alive():
                elapsed = int(time.monotonic() - getattr(self, "_spps_started_at", time.monotonic()))
                self.workflow_progress_text.set(f"SPPS planning · {elapsed}s")
                self.root.after(150, self._poll_spps_worker)
            else:
                self.spps_run_button.configure(state="normal")
            return
        self.spps_run_button.configure(state="normal")
        if kind == "error":
            self._set_workflow_progress(85, "SPPS planning failed")
            self.spps_status_var.set("SPPS planning failed. See the error dialog/log for details.")
            self.write_log(payload)
            messagebox.showerror("SPPS run failed", payload.splitlines()[-1] if payload else "Unknown SPPS error")
            return
        result = dict(payload)
        self._refresh_workflow_progress_from_project()
        self.spps_status_var.set(f"SPPS plan complete for: {result.get('sequence', '')}")
        self.write_log(f"SPPS planning completed. Outputs saved in: {result.get('outdir', '')}")

    def launch_tool(self, tool: str):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--tool", tool]
            else:
                cmd = [sys.executable, str(ROOT / "main_launcher.py"), "--tool", tool]
            env = os.environ.copy()
            tool_key = str(tool).lower()
            if self.project_dir and tool_key in {"design", "hotspot"}:
                env["PEPFORGE_WORKFLOW_PROJECT"] = str(self.project_dir)
            if self.project_dir and tool_key == "hotspot":
                shared_sequence = self.seq_text.get("1.0", "end").strip()
                if shared_sequence:
                    env["PEPFORGE_WORKFLOW_SHARED_SEQUENCE"] = shared_sequence
            if tool_key == "spps" and self.project_dir:
                env["PEPFORGE_WORKFLOW_SPPS_PROJECT"] = str(self.project_dir)
                env["PEPFORGE_WORKFLOW_SPPS_SEQUENCE"] = self.candidate_var.get().strip()
                env["PEPFORGE_WORKFLOW_SPPS_RESIN"] = self.resin_var.get().strip()
                env["PEPFORGE_WORKFLOW_SPPS_LOADING"] = self.loading_var.get().strip()
                env["PEPFORGE_WORKFLOW_SPPS_SCALE"] = self.scale_var.get().strip()
                env["PEPFORGE_WORKFLOW_SPPS_APPLY_LOADING"] = "1"
            if tool_key == "design" and self.project_dir:
                profile_path = Path(self.project_dir) / "design" / "hotspot_chemistry_profile_for_PDE.json"
                if profile_path.exists():
                    env["PEPFORGE_HOTSPOT_PROFILE"] = str(profile_path)
                row = self._selected_hotspot_rank_row()
                if row:
                    selected_sequence = str(row.get("region_sequence", row.get("sequence", ""))).strip()
                    if selected_sequence:
                        env["PEPFORGE_WORKFLOW_TARGET_SEQUENCE"] = selected_sequence
                        env["PEPFORGE_WORKFLOW_HOTSPOT_RANK"] = str(row.get("rank", ""))
                self.write_log("Opening PDE with the selected ranked Hot Spot region and its chemistry evidence.")
            subprocess.Popen(cmd, cwd=str(ROOT), env=env)
        except Exception as e:
            messagebox.showerror("Launch failed", str(e))

    def mainloop(self):
        self.root.mainloop()


def main():
    WorkflowApp().mainloop()


if __name__ == "__main__":
    main()
