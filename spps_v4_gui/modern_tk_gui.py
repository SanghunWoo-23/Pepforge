"""Alternate modular Tk GUI components retained for SPPS Planner V4.0.0.

The canonical release UI is assembled by ``spps_v4_gui.ui_build``. Project
Manager, advanced settings, DB,
data-log, ML, export, and self-test actions are delegated to focused modules.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "spps_planner_app"
for _p in (ROOT, APP):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from spps_planner.version import VERSION_NAME, VERSION_NUMBER  # noqa: E402
from spps_planner.user_paths import user_outputs_dir, user_file  # noqa: E402
from spps_v4_gui.modules import gui_common as state  # noqa: E402
from spps_v4_gui.modules.project_manager_panel import normalize_project_manager  # noqa: E402
from spps_v4_gui.modules import export_panel, cleavage_panel  # noqa: E402
from spps_v4_gui.modules.advanced_settings_panel import build_advanced_tab, apply_scale_preset  # noqa: E402
from spps_v4_gui.modules.db_editor_panel import build_db_editor_tab  # noqa: E402
from spps_v4_gui.modules.data_log_panel import build_data_log_tab  # noqa: E402
from spps_v4_gui.modules.ml_lab_panel import build_ml_lab_tab  # noqa: E402
from spps_v4_gui.modules.windows_selftest_panel import build_selftest_tab  # noqa: E402


class SPPSGui(tk.Tk):
    """Compact Tk front end focused on SPPS calculation and Project Manager."""

    UI_MODES = {
        "Essential": ["Project Manager"],
        "Workbench": ["Project Manager", "Advanced Settings", "Data Log"],
        "Expert": ["Project Manager", "Advanced Settings", "DB Editor", "Data Log", "ML Lab", "Windows Self-Test"],
        "QA": ["Project Manager", "Data Log", "Windows Self-Test"],
    }
    MODE_HELP = {
        "Essential": "핵심 합성 계산과 작업용 결과만 표시합니다.",
        "Workbench": "필요할 때만 여는 실무 도구 화면: Advanced와 Data Log를 추가 표시합니다.",
        "Expert": "전체 기능 표시: DB Editor, ML Lab, QA까지 모두 엽니다.",
        "QA": "검증용: Project Manager, Data Log, Windows Self-Test만 표시합니다.",
    }

    TITLE = VERSION_NAME

    def _asset_path(self, *parts: str) -> Path:
        """Resolve bundled assets in source tree or PyInstaller runtime."""
        frozen_root = Path(getattr(sys, "_MEIPASS", ROOT))
        candidates = [
            frozen_root / "assets" / Path(*parts),
            ROOT / "assets" / Path(*parts),
            Path(__file__).resolve().parents[1] / "assets" / Path(*parts),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _set_window_icon(self) -> None:
        """Apply SPPS Planner icon for Windows titlebar/taskbar and Tk fallback.

        Tk handles icons differently by platform. Windows prefers .ico via
        iconbitmap; other platforms and some frozen runtimes need iconphoto
        with a PhotoImage. Keeping the PhotoImage on ``self`` prevents garbage
        collection from clearing the icon.
        """
        ico = self._asset_path("SPPS_Planner_Icon.ico")
        png = self._asset_path("SPPS_Planner_Icon.png")
        applied = False
        if os.name == "nt" and ico.exists():
            try:
                self.iconbitmap(default=str(ico))
                applied = True
            except tk.TclError:
                try:
                    self.iconbitmap(str(ico))
                    applied = True
                except tk.TclError:
                    applied = False
        if not applied and png.exists():
            try:
                self._spps_icon_image = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._spps_icon_image)
                applied = True
            except tk.TclError:
                applied = False
        try:
            self._icon_status = "OK" if applied else "missing"
        except Exception:
            pass

    def __init__(self) -> None:
        super().__init__()
        self.title(self.TITLE)
        self._set_window_icon()
        self.geometry("1360x820")
        self.minsize(1100, 680)
        self.last_outdir: Path | None = None
        self._autosave_path = user_file("project_manager_autosave.json")
        self._tab_frames_by_title: dict[str, Any] = {}
        self.pm_items: list[dict[str, Any]] = [self._default_item()]
        self._build_variables()
        self._build_ui()
        self._bind_native_events()
        self.apply_ui_mode()
        # Hidden autosave restore caused non-deterministic startup item lists.
        # Restore only when explicitly requested by environment variable.
        if os.environ.get("SPPS_RESTORE_AUTOSAVE", "").strip() == "1":
            self.load_autosave_if_available()
        state.refresh_list(self, [0])
        state.load_item_to_editor(self, 0)
        normalize_project_manager(self)
        export_panel.generate_update(self)
        self.apply_ui_mode()

    # ---------- state / basic helpers ----------
    def _build_variables(self) -> None:
        first = (self.pm_items[0] if getattr(self, "pm_items", None) else {})
        self.pm_project = tk.StringVar(value=first.get("project", ""))
        self.pm_peptide = tk.StringVar(value=first.get("peptide", ""))
        self.pm_sequence = tk.StringVar(value=first.get("sequence", ""))
        self.scale_preset = tk.StringVar(value=first.get("scale_preset", "Lab STD 400 mmol"))
        self.pm_scale = tk.StringVar(value=first.get("scale", "400"))
        self.pm_resin = tk.StringVar(value=first.get("resin", "Rink Amide AM"))
        self.pm_loading = tk.StringVar(value=first.get("loading", "0.8"))
        self.pm_chemistry = tk.StringVar(value=first.get("chemistry", "DIC/HOBt"))
        self.pm_copies = tk.StringVar(value=first.get("copies", "1"))
        self.loading_aa_eq = tk.StringVar(value=first.get("loading_aa_eq", "2"))
        self.loading_diea_eq = tk.StringVar(value=first.get("loading_diea_eq", "4"))
        self.loading_time_h = tk.StringVar(value=first.get("loading_time_h", ""))
        self.coupling_eq = tk.StringVar(value=first.get("coupling_eq", "5"))
        self.modifier_eq = tk.StringVar(value=first.get("modifier_eq", "3"))
        self.coupling_repeats = tk.StringVar(value=first.get("coupling_repeats", "1"))
        self.modifier_repeats = tk.StringVar(value=first.get("modifier_repeats", "1"))
        self.default_reagent = tk.StringVar(value=first.get("default_reagent", "DIC"))
        self.default_catalyst = tk.StringVar(value=first.get("default_catalyst", "HOBt"))
        self.default_base = tk.StringVar(value=first.get("default_base", ""))
        self.default_coupling_solution_solvent = tk.StringVar(value=first.get("default_coupling_solution_solvent", "DMF"))
        self.auto_short_peptide_eq = tk.BooleanVar(value=bool(first.get("auto_short_peptide_eq", True)))
        self.short_peptide_coupling_eq = tk.StringVar(value=first.get("short_peptide_coupling_eq", "2"))
        self.cleavage_eq_override = tk.StringVar(value=first.get("cleavage_eq_override", "0"))
        self.cleavage_preset = tk.StringVar(value=first.get("cleavage_preset", "AUTO"))
        self.cleavage_components_text = tk.StringVar(value=first.get("cleavage_components_text", ""))
        self.cleavage_time_h = tk.StringVar(value=first.get("cleavage_time_h", ""))
        self.project_outdir = tk.StringVar(value=str(user_outputs_dir() / "project_manager_exports"))
        self.gui_mode = tk.StringVar(value=first.get("gui_mode", "Essential"))
        self.show_advanced_item_controls = tk.BooleanVar(value=bool(first.get("show_advanced_item_controls", False)))

    def _default_item(self) -> dict[str, Any]:
        return {
            "project": "",
            "peptide": "",
            "sequence": "",
            "scale": "400",
            "scale_preset": "Lab STD 400 mmol",
            "resin": "Rink Amide AM",
            "loading": "0.8",
            "chemistry": "DIC/HOBt",
            "copies": "1",
            "status": "Ready",
            "loading_aa_eq": "2",
            "loading_diea_eq": "4",
            "coupling_eq": "5",
            "modifier_eq": "3",
            "coupling_repeats": "1",
            "modifier_repeats": "1",
            "default_reagent": "DIC",
            "default_catalyst": "HOBt",
            "default_base": "",
            "default_coupling_solution_solvent": "DMF",
            "auto_short_peptide_eq": True,
            "short_peptide_coupling_eq": "2",
            "step_overrides_text": "",
            "cleavage_eq_override": "0",
            "cleavage_preset": "AUTO",
            "cleavage_components_text": "",
            "cleavage_time_h": "",
            "gui_mode": "Essential",
            "show_advanced_item_controls": False,
        }

    def pm_display_name(self, item: dict[str, Any]) -> str:
        project = item.get("project", "")
        peptide = item.get("peptide", item.get("name", ""))
        seq = item.get("sequence", "")
        status = item.get("status", "Ready")
        return f"{project} | {peptide} | {seq} | {status}"

    def _log(self, msg: str) -> None:
        try:
            self.log_text.insert("end", str(msg))
            self.log_text.see("end")
        except Exception:
            pass

    def pm_update_summary(self) -> None:
        try:
            self.item_count_label.configure(text=f"Items: {len(self.pm_items)}")
        except Exception:
            pass

    def schedule_autosave(self) -> None:
        try:
            self._autosave_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"version": VERSION_NUMBER, "pm_items": self.pm_items, "active_index": state.active_index(self)}
            self._autosave_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_autosave_if_available(self) -> None:
        # Keep startup deterministic: only restore when the saved state is valid and non-empty.
        try:
            if not self._autosave_path.exists():
                return
            payload = json.loads(self._autosave_path.read_text(encoding="utf-8"))
            items = payload.get("pm_items")
            if isinstance(items, list) and items:
                self.pm_items = [x for x in items if isinstance(x, dict)] or self.pm_items
        except Exception:
            pass

    # ---------- UI construction ----------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, padding=(10, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        self.title_label = ttk.Label(header, text=VERSION_NAME, font=("Segoe UI", 17, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Solid Phase Peptide Synthesis Calculator", foreground="#555").grid(row=1, column=0, sticky="w")
        self.mode_help_label = ttk.Label(header, text="", foreground="#555")
        self.mode_help_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        mode_box = ttk.Frame(header)
        mode_box.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Label(mode_box, text="UI Mode").grid(row=0, column=0, sticky="e")
        self.ui_mode_combo = ttk.Combobox(
            mode_box,
            textvariable=self.gui_mode,
            values=list(self.UI_MODES),
            state="readonly",
            width=13,
        )
        self.ui_mode_combo.grid(row=0, column=1, sticky="e", padx=(5, 0))
        ttk.Checkbutton(
            mode_box,
            text="Show item advanced",
            variable=self.show_advanced_item_controls,
            command=self.apply_ui_mode,
        ).grid(row=1, column=0, columnspan=2, sticky="e", pady=(4, 0))
        self.item_count_label = ttk.Label(header, text="Items: 0")
        self.item_count_label.grid(row=0, column=3, sticky="e", padx=(12, 0))

        nb = ttk.Notebook(self)
        nb.grid(row=1, column=0, sticky="nsew")
        self.main_notebook = nb
        pm = ttk.Frame(nb, padding=8)
        nb.add(pm, text="Project Manager")
        self._build_project_manager(pm)
        build_advanced_tab(self, nb)
        build_db_editor_tab(self, nb)
        build_data_log_tab(self, nb)
        build_ml_lab_tab(self, nb)
        build_selftest_tab(self, nb)
        self._capture_tab_frames()

    def _build_project_manager(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Peptide Items", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.pm_list = tk.Listbox(left, width=54, height=22, selectmode=tk.EXTENDED, exportselection=False)
        self.pm_list.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.pm_list.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.pm_list.configure(yscrollcommand=sb.set)
        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        for i in range(3): btns.columnconfigure(i, weight=1)
        ttk.Button(btns, text="Add", command=self.pm_add_item).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(btns, text="Duplicate").grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(btns, text="Delete").grid(row=0, column=2, sticky="ew", padx=2)

        editor = ttk.LabelFrame(left, text="Selected Item", padding=8)
        editor.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        fields = [
            ("Project", self.pm_project), ("Peptide", self.pm_peptide), ("Sequence", self.pm_sequence),
            ("Scale preset", self.scale_preset), ("Scale mmol", self.pm_scale), ("Resin", self.pm_resin), ("Loading mmol/g", self.pm_loading),
            ("Chemistry", self.pm_chemistry),
        ]
        for r, (label, var) in enumerate(fields):
            ttk.Label(editor, text=label).grid(row=r, column=0, sticky="w", pady=2)
            if label == "Resin":
                w = ttk.Combobox(editor, textvariable=var, values=["Rink Amide AM", "Amide", "2-CTC", "CTC/Trityl", "Trityl"], width=34)
            elif label == "Chemistry":
                w = ttk.Combobox(editor, textvariable=var, values=["DIC/HOBt", "HBTU", "HATU", "COMU", "PyBOP", "DCC/HOBt"], width=34)
            elif label == "Scale preset":
                w = ttk.Combobox(editor, textvariable=var, values=["Lab STD 400 mmol", "Small bench 0.4 mmol", "Micro test 0.2 mmol", "Custom / manual"], state="readonly", width=34)
                w.bind("<<ComboboxSelected>>", lambda _e: (apply_scale_preset(self), export_panel.generate_update(self)), add=True)
            else:
                w = ttk.Entry(editor, textvariable=var, width=36)
            w.grid(row=r, column=1, sticky="ew", padx=(6, 0), pady=2)
        editor.columnconfigure(1, weight=1)

        self.pm_item_advanced_frame = ttk.LabelFrame(left, text="Advanced Item Controls", padding=8)
        self.pm_item_advanced_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        self.pm_item_advanced_frame.columnconfigure(1, weight=1)
        advanced_fields = [
            ("Loading AA eq", self.loading_aa_eq),
            ("Loading DIEA eq", self.loading_diea_eq),
            ("Loading time (h)", self.loading_time_h),
            ("AA coupling eq", self.coupling_eq),
            ("Modifier eq", self.modifier_eq),
            ("AA repeat", self.coupling_repeats),
            ("Modifier repeat", self.modifier_repeats),
        ]
        for r, (label, var) in enumerate(advanced_fields):
            ttk.Label(self.pm_item_advanced_frame, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(self.pm_item_advanced_frame, textvariable=var, width=18).grid(row=r, column=1, sticky="ew", padx=(6, 0), pady=2)
        ttk.Label(
            self.pm_item_advanced_frame,
            text="고급 조건은 계산/export에 반영됩니다. 평소에는 숨겨서 화면을 단순하게 유지합니다.",
            foreground="#555",
        ).grid(row=len(advanced_fields), column=0, columnspan=2, sticky="w", pady=(4, 0))

        chem = ttk.LabelFrame(left, text="Cleavage Control", padding=8)
        self.pm_cleavage_control_frame = chem
        chem.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 4))
        ttk.Label(chem, text="Eq override (0=auto)").grid(row=0, column=0, sticky="w")
        ttk.Entry(chem, textvariable=self.cleavage_eq_override, width=8).grid(row=0, column=1, sticky="w", padx=(6, 10))
        ttk.Label(chem, text="Preset").grid(row=1, column=0, sticky="w")
        ttk.Combobox(chem, textvariable=self.cleavage_preset, values=self._cleavage_preset_values(), width=28, state="readonly").grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=2)
        ttk.Label(chem, text="Custom").grid(row=2, column=0, sticky="w")
        ttk.Entry(chem, textvariable=self.cleavage_components_text, width=30).grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=2)
        ttk.Label(chem, text="Time (h)").grid(row=3, column=0, sticky="w")
        ttk.Entry(chem, textvariable=self.cleavage_time_h, width=12).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=2)
        chem.columnconfigure(1, weight=1)

        bottom = ttk.Frame(left)
        bottom.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Entry(bottom, textvariable=self.project_outdir).grid(row=0, column=0, sticky="ew")
        ttk.Button(bottom, text="Browse", command=self.pm_browse_outdir).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(bottom, text="Generate / Update Plan").grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(bottom, text="Export").grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))

        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1); right.columnconfigure(0, weight=1)
        self.results_notebook = ttk.Notebook(right)
        self.results_notebook.grid(row=0, column=0, sticky="nsew")
        self.pm_summary_tree = self._add_tree_tab(self.results_notebook, "Summary")
        self.pm_selected_plan_tree = self._add_tree_tab(self.results_notebook, "Selected Plan")
        self.pm_selected_material_tree = self._add_tree_tab(self.results_notebook, "Selected Materials")
        self.pm_validation_tree = self._add_tree_tab(self.results_notebook, "Validation")
        ops_frame = ttk.Frame(self.results_notebook)
        ops_frame.rowconfigure(0, weight=1); ops_frame.columnconfigure(0, weight=1)
        self.results_notebook.add(ops_frame, text="Operations")
        self.pm_selected_check_text = tk.Text(ops_frame, wrap="none", height=14)
        self.pm_selected_check_text.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(ops_frame, orient="vertical", command=self.pm_selected_check_text.yview)
        y.grid(row=0, column=1, sticky="ns")
        self.pm_selected_check_text.configure(yscrollcommand=y.set)
        cleavage_panel.ensure_cleavage_panel(self)
        self._capture_result_tabs()
        log_frame = ttk.LabelFrame(right, text="Log", padding=4)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.log_text = tk.Text(log_frame, height=4, wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _add_tree_tab(self, notebook: ttk.Notebook, title: str):
        frame = ttk.Frame(notebook)
        frame.rowconfigure(0, weight=1); frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=[], show="headings", height=20, selectmode="extended")
        tree.grid(row=0, column=0, sticky="nsew")
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        y.grid(row=0, column=1, sticky="ns"); x.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        notebook.add(frame, text=title)
        return tree

    def _capture_tab_frames(self) -> None:
        """Remember every notebook tab so UI modes can hide/show without rebuilding."""
        self._tab_frames_by_title = {}
        try:
            for tab_id in self.main_notebook.tabs():
                title = str(self.main_notebook.tab(tab_id, "text"))
                self._tab_frames_by_title[title] = tab_id
        except Exception:
            self._tab_frames_by_title = {}

    def _capture_result_tabs(self) -> None:
        """Remember result tabs so Essential mode can show only work-facing tables."""
        self._result_tab_frames_by_title = {}
        try:
            for tab_id in self.results_notebook.tabs():
                title = str(self.results_notebook.tab(tab_id, "text"))
                self._result_tab_frames_by_title[title] = tab_id
        except Exception:
            self._result_tab_frames_by_title = {}

    def _apply_result_tabs(self, mode: str) -> None:
        essential = ["Summary", "Selected Plan", "Selected Materials"]
        detail = ["Summary", "Selected Plan", "Selected Materials", "Cleavage Cocktail", "Validation", "Operations"]
        wanted = detail if mode in {"Workbench", "Expert", "QA"} else essential
        try:
            current = {str(self.results_notebook.tab(t, "text")): t for t in self.results_notebook.tabs()}
            for title, tab_id in list(current.items()):
                if title not in wanted:
                    self.results_notebook.forget(tab_id)
            current = {str(self.results_notebook.tab(t, "text")): t for t in self.results_notebook.tabs()}
            for title in wanted:
                if title not in current and title in self._result_tab_frames_by_title:
                    self.results_notebook.add(self._result_tab_frames_by_title[title], text=title)
            if "Summary" in self._result_tab_frames_by_title:
                self.results_notebook.select(self._result_tab_frames_by_title["Summary"])
        except Exception:
            pass

    def apply_ui_mode(self) -> None:
        """Reduce visual noise while keeping all features available by mode."""
        try:
            mode = self.gui_mode.get() if hasattr(self, "gui_mode") else "Essential"
        except Exception:
            mode = "Essential"
        if mode not in self.UI_MODES:
            mode = "Essential"
            try:
                self.gui_mode.set(mode)
            except Exception:
                pass
        wanted = list(self.UI_MODES.get(mode, self.UI_MODES["Essential"]))
        try:
            current = {str(self.main_notebook.tab(t, "text")): t for t in self.main_notebook.tabs()}
            for title, tab_id in list(current.items()):
                if title not in wanted:
                    self.main_notebook.forget(tab_id)
            current = {str(self.main_notebook.tab(t, "text")): t for t in self.main_notebook.tabs()}
            for title in wanted:
                if title not in current and title in self._tab_frames_by_title:
                    self.main_notebook.add(self._tab_frames_by_title[title], text=title)
            if "Project Manager" in wanted and "Project Manager" in self._tab_frames_by_title:
                self.main_notebook.select(self._tab_frames_by_title["Project Manager"])
        except Exception:
            pass
        show_item_advanced = mode in {"Workbench", "Expert"} or bool(state.as_bool(getattr(self, "show_advanced_item_controls", False)))
        for attr, show in [
            ("pm_item_advanced_frame", show_item_advanced),
            ("pm_cleavage_control_frame", mode in {"Workbench", "Expert", "QA"} or show_item_advanced),
        ]:
            try:
                widget = getattr(self, attr)
                if show:
                    widget.grid()
                else:
                    widget.grid_remove()
            except Exception:
                pass
        self._apply_result_tabs(mode)
        try:
            self.mode_help_label.configure(text=self.MODE_HELP.get(mode, ""))
        except Exception:
            pass
        try:
            self.schedule_autosave()
        except Exception:
            pass

    def _cleavage_preset_values(self) -> list[str]:
        try:
            from spps_planner.engine import cleavage_cocktail_presets
            return ["AUTO"] + cleavage_cocktail_presets()["preset"].astype(str).tolist() + ["CUSTOM"]
        except Exception:
            return ["AUTO", "DEFAULT_TFA_TIS_WATER", "CYS_EDT", "REAGENT_K", "CUSTOM"]

    def _bind_native_events(self) -> None:
        self.pm_list.bind("<<ListboxSelect>>", self._on_item_select, add=True)
        try:
            self.ui_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_ui_mode(), add=True)
        except Exception:
            pass
        self.bind("<Control-s>", lambda e: (export_panel.export_outputs(self), "break"))
        for var in (self.cleavage_eq_override, self.cleavage_preset, self.cleavage_components_text, self.cleavage_time_h):
            try:
                var.trace_add("write", lambda *_: self.after_idle(lambda: export_panel.generate_update(self)))
            except Exception:
                pass

    # ---------- UI actions ----------
    def _on_item_select(self, event=None):
        try:
            sels = state.selected_indices(self)
            if not sels:
                return None
            state.save_active(self)
            state.load_item_to_editor(self, sels[0])
            export_panel.generate_update(self)
        except Exception:
            pass
        return None

    def pm_add_item(self) -> None:
        try:
            state.save_active(self)
            item = state.blank_item(self, len(self.pm_items) + 1)
            self.pm_items.append(item)
            idx = len(self.pm_items) - 1
            state.refresh_list(self, [idx])
            state.load_item_to_editor(self, idx)
            export_panel.generate_update(self)
            self.schedule_autosave()
        except Exception as exc:
            messagebox.showerror("Add peptide", str(exc))

    def pm_browse_outdir(self) -> None:
        path = filedialog.askdirectory(initialdir=str(Path.cwd()))
        if path:
            self.project_outdir.set(path)


def main() -> None:
    app = SPPSGui()
    app.mainloop()


def launch() -> None:
    main()


if __name__ == "__main__":
    launch()
