#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Peptide Design Engine - Desktop GUI / EXE-ready launcher

Design goals
- Preserve the original engine: this GUI calls peptide_engine.run() directly.
- Keep Colab-style controls: target, mode, length, feature toggles, hotspot, docking,
  structure-input export and user-data model import/train/rerank.
- Avoid feature loss: any CONFIG key not exposed as a widget can be supplied through
  Advanced JSON Override.
- EXE packaging friendly: uses only tkinter from the standard library plus the project modules.
"""
from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

import contextlib
import csv
import json
import os
import re
import queue
import secrets
import sys
import threading
import traceback
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.scrolledtext as scrolledtext
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# ---------------------------------------------------------------------
# Project import path handling
# ---------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
PYTHON_DIR = THIS_FILE.parent
ROOT_DIR = PYTHON_DIR.parent
PROJECT_ROOT = PYTHON_DIR.parents[2] if len(PYTHON_DIR.parents) >= 3 else ROOT_DIR
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from peptiforg_core.sandbox_runtime import configured_output  # noqa: E402
from peptiforg_core.ui_theme import apply_pepforge_theme, BACKGROUND  # noqa: E402
try:
    from peptiforg_core.ui_helpers import set_pepforge_icon  # noqa: E402
except Exception:
    def set_pepforge_icon(window) -> None:
        try:
            icon = PROJECT_ROOT / "assets" / "Pepforge_Icon.png"
            if icon.exists():
                img = tk.PhotoImage(file=str(icon))
                window.iconphoto(True, img)
                setattr(window, "_pepforge_icon_img", img)
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
def resource_path(relative: str) -> Path:
    """Return a path that works both in source mode and PyInstaller onefile mode."""
    base = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
    return base / relative

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import peptide_engine as eng  # noqa: E402
try:
    import data_manager  # noqa: E402
except Exception:
    data_manager = None
try:
    import ml_trainer  # noqa: E402
except Exception:
    ml_trainer = None
try:
    import external_parsers  # noqa: E402
except Exception:
    external_parsers = None


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------
def parse_targets(text: str) -> List[List[str]]:
    import re
    return [list(x.strip()) for x in re.split(r"[\n,;|/]+", str(text)) if x.strip()]


def to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def seq_token_to_text(x: Any) -> str:
    """Convert engine sequence/motif tokens to GUI-safe text."""
    if isinstance(x, (list, tuple)):
        return "".join(str(v) for v in x)
    return str(x)


def list_to_gui_text(items: Any) -> str:
    """Convert strings/lists/nested motif lists to comma-separated GUI text."""
    if items is None:
        return ""
    if isinstance(items, str):
        return items
    if isinstance(items, (list, tuple)):
        return ", ".join(seq_token_to_text(x) for x in items)
    return str(items)


def listify_tokens(items: Any) -> List[str]:
    """Normalize CONFIG token lists for GUI checkboxes."""
    if items is None:
        return []
    if isinstance(items, str):
        return [x.strip() for x in items.replace(";", ",").split(",") if x.strip()]
    if isinstance(items, (list, tuple)):
        return [seq_token_to_text(x) for x in items]
    return [str(items)]


def write_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def rebuild_output_zip(output_dir: Path) -> str:
    zip_path = output_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in output_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(output_dir))
    return str(zip_path)


def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f"open {json.dumps(str(path))}")
    else:
        os.system(f"xdg-open {json.dumps(str(path))}")


class QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text: str) -> int:
        if text:
            self.q.put(("log", text))
        return len(text)

    def flush(self) -> None:
        LOGGER.debug("Optional operation skipped", exc_info=True)
# ---------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------
class PeptideDesktopGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pepforge Peptide Design Engine")
        set_pepforge_icon(self)
        apply_pepforge_theme(self)
        self.geometry("1180x820")
        self.minsize(1040, 720)
        self._app_icon_img = None
        self._header_logo_img = None
        self._splash_photo = None
        self._splash = None
        self._set_window_icon()
        self._show_splash()

        self.msg_q: queue.Queue = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.applied_config: Optional[Dict[str, Any]] = None
        self.settings_applied = False
        self.last_output_dir: Optional[Path] = None
        self.last_zip: Optional[Path] = None
        self.last_run_config: Optional[Dict[str, Any]] = None
        self._build_vars()
        self._build_ui()
        self._install_settings_change_tracking()
        self.after(100, self._poll_queue)
        self.after(950, self._close_splash)

    # --------------------------- branding ---------------------------
    def _set_window_icon(self) -> None:
        try:
            ico = resource_path("assets/PeptideDesignEngine_Icon.ico")
            png = resource_path("assets/PeptideDesignEngine_Icon.png")
            if ico.exists():
                self.iconbitmap(str(ico))
            elif Image is not None and ImageTk is not None and png.exists():
                im = Image.open(png).resize((64, 64), Image.Resampling.LANCZOS)
                self._app_icon_img = ImageTk.PhotoImage(im)
                self.iconphoto(True, self._app_icon_img)
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _show_splash(self) -> None:
        try:
            splash_path = resource_path("assets/PeptideDesignEngine_Splash.png")
            if Image is None or ImageTk is None or not splash_path.exists():
                return
            splash = tk.Toplevel(self)
            splash.overrideredirect(True)
            splash.attributes("-topmost", True)
            im = Image.open(splash_path)
            self._splash_photo = ImageTk.PhotoImage(im)
            label = tk.Label(splash, image=self._splash_photo, bd=0)
            label.pack()
            splash.update_idletasks()
            w, h = im.size
            x = (splash.winfo_screenwidth() - w) // 2
            y = (splash.winfo_screenheight() - h) // 2
            splash.geometry(f"{w}x{h}+{x}+{y}")
            self._splash = splash
        except Exception:
            self._splash = None

    def _close_splash(self) -> None:
        try:
            if self._splash is not None and self._splash.winfo_exists():
                self._splash.destroy()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        self.deiconify()

    # --------------------------- vars ---------------------------
    def _build_vars(self) -> None:
        c = eng.CONFIG
        self.var_preset = tk.StringVar(value="custom")
        self.var_targets = tk.StringVar(value="")
        self.var_target_mode = tk.StringVar(value=c.get("TARGET_MODE_LABEL", "MULTI"))
        self.var_design_mode = tk.StringVar(value=c.get("DESIGN_MODE", "MULTI_TARGET_BINDER"))
        self.var_binder_mode = tk.StringVar(value=c.get("BINDER_MODE", "BALANCED"))

        self.var_pop = tk.IntVar(value=int(c.get("POP", 200)))
        self.var_gen = tk.IntVar(value=int(c.get("GEN", 20)))
        self.var_topk = tk.IntVar(value=int(c.get("FINAL_TOPK", 10)))
        self.var_seed = tk.IntVar(value=int(c.get("SEED", 42)))
        self.var_lock_seed = tk.BooleanVar(value=not to_bool(c.get("AUTO_SEED_EACH_RUN", True)))

        self.var_len_mode = tk.StringVar(value=c.get("LEN_MODE", "RANDOM"))
        self.var_fix_len = tk.IntVar(value=int(c.get("FIX_LENGTH", 14)))
        self.var_min_len = tk.IntVar(value=int(c.get("MIN_LENGTH", 12)))
        self.var_max_len = tk.IntVar(value=int(c.get("MAX_LENGTH", 15)))
        self.var_length_metric = tk.StringVar(value=c.get("LENGTH_COUNT_MODE", c.get("LENGTH_METRIC", "TOKEN")))
        self.var_trim = tk.BooleanVar(value=to_bool(c.get("TRIM_TO_LENGTH", True)))

        self.var_use_d = tk.BooleanVar(value=to_bool(c.get("USE_D", True)))
        self.var_use_non_nat = tk.BooleanVar(value=to_bool(c.get("USE_NON_NAT", True)))
        self.var_use_linker = tk.BooleanVar(value=to_bool(c.get("USE_LINKER", True)))
        self.var_use_tag = tk.BooleanVar(value=to_bool(c.get("USE_TAG", True)))
        self.var_use_base_chem = tk.BooleanVar(value=to_bool(c.get("USE_BASE_CHEM", True)))
        self.var_use_label = tk.BooleanVar(value=to_bool(c.get("USE_LABEL", True)))
        self.var_use_cterm_nh2 = tk.BooleanVar(value=to_bool(c.get("USE_CTERM_NH2", True)))

        # Selectable chemistry libraries. Values are still mirrored into CONFIG,
        # while Advanced JSON Override can override them if needed.
        self.tag_choices = listify_tokens(c.get("TAG_TYPES", ["His6", "FLAG", "HA"]))
        self.linker_choices = listify_tokens(c.get("LINKER_TYPES", ["Ahx", "PEG4", "PEG8"]))
        self.label_choices = listify_tokens(c.get("LABEL_TYPES", ["NONE", "BIOTIN", "FITC", "CY5"]))
        self.base_chem_choices = listify_tokens(c.get("BASE_CHEM_TYPES", ["Pal", "Myr", "Nic", "Caf", "Gal", "Ac"]))
        self.non_nat_choices = listify_tokens(c.get("NON_NAT_TYPES", getattr(eng, "NON_NAT", ["Nle", "Orn", "Aib", "Hyp"])))

        self.var_tag_types = {x: tk.BooleanVar(value=True) for x in self.tag_choices}
        self.var_linker_types = {x: tk.BooleanVar(value=True) for x in self.linker_choices}
        self.var_label_types = {x: tk.BooleanVar(value=True) for x in self.label_choices}
        self.var_base_chem_types = {x: tk.BooleanVar(value=True) for x in self.base_chem_choices}
        self.var_non_nat_types = {x: tk.BooleanVar(value=True) for x in self.non_nat_choices}
        self.var_linker_mode = tk.StringVar(value=c.get("LINKER_MODE", "MIX"))
        self.var_fix_linker_type = tk.StringVar(value=c.get("FIX_LINKER_TYPE", self.linker_choices[0] if self.linker_choices else "PEG4"))
        self.var_max_linkers = tk.IntVar(value=int(c.get("MAX_LINKERS", 2)))

        self.var_motif_lock = tk.BooleanVar(value=to_bool(c.get("MOTIF_LOCK", False)))
        self.var_locked_motifs = tk.StringVar(value=list_to_gui_text(c.get("LOCKED_MOTIFS", [])))
        self.var_motif_pos_mode = tk.StringVar(value=c.get("MOTIF_POSITION_MODE", "FREE"))
        self.var_motif_placement_mode = tk.StringVar(value=c.get("MOTIF_PLACEMENT_MODE", "OFF"))
        self.var_motif_placement_specs = tk.StringVar(value=c.get("MOTIF_PLACEMENT_SPECS", ""))
        self.var_motif_preset = tk.StringVar(value="Custom")
        self.var_bridge_anchor_len = tk.IntVar(value=int(c.get("BRIDGE_ANCHOR_LEN", 4)))

        self.var_auto_hotspot = tk.BooleanVar(value=to_bool(c.get("AUTO_HOTSPOT", False)))
        self.var_hotspot_source = tk.StringVar(value=c.get("HOTSPOT_SOURCE", "SEQUENCE"))
        self.var_hotspot_sequence = tk.StringVar(value=c.get("HOTSPOT_SEQUENCE", ""))
        self.var_hotspot_pdb_file = tk.StringVar(value="")
        self.var_hotspot_window = tk.IntVar(value=int(c.get("HOTSPOT_WINDOW", 6)))
        self.var_hotspot_topk = tk.IntVar(value=int(c.get("HOTSPOT_TOPK", 5)))
        self.var_hotspot_replace = tk.BooleanVar(value=to_bool(c.get("HOTSPOT_REPLACE_TARGETS", True)))
        self.var_hotspot_lock_motif = tk.BooleanVar(value=to_bool(c.get("HOTSPOT_LOCK_AS_MOTIF", False)))

        self.var_docking_stage = tk.StringVar(value=c.get("DOCKING_STAGE", "OFF"))
        self.var_docking_engine = tk.StringVar(value=c.get("DOCKING_ENGINE", "NONE"))
        self.var_docking_ready_mode = tk.StringVar(value=c.get("DOCKING_READY_MODE", "BASIC"))
        self.var_docking_bonus = tk.DoubleVar(value=float(c.get("DOCKING_READY_BONUS_WEIGHT", 0.10)))
        self.var_pseudodock = tk.BooleanVar(value=to_bool(c.get("PREPARE_PSEUDODOCKING_COLAB", False)))
        self.var_receptor_sequence = tk.StringVar(value=c.get("RECEPTOR_SEQUENCE", ""))
        self.var_pseudodock_topk = tk.IntVar(value=int(c.get("PSEUDODOCKING_TOPK", 10)))

        self.var_optional_ml = tk.BooleanVar(value=to_bool(c.get("USE_OPTIONAL_ML", False)))
        self.var_ml_weight = tk.DoubleVar(value=float(c.get("ML_RERANK_WEIGHT", 0.20)))
        self.var_use_ml_prior = tk.BooleanVar(value=to_bool(c.get("USE_ML_PRIOR", False)))
        self.var_ml_prior_weight = tk.DoubleVar(value=float(c.get("ML_PRIOR_WEIGHT", 0.45)))
        self.var_ml_prior_table = tk.StringVar(value="")
        self.var_trained_model = tk.StringVar(value="")
        self.var_trained_ml_weight = tk.DoubleVar(value=0.25)
        self.var_training_db = tk.StringVar(value="")
        self.var_ml_label = tk.StringVar(value="experimental_binding")
        self.var_models_dir = tk.StringVar(value=str(ROOT_DIR / "models"))
        self.var_mapping_csv = tk.StringVar(value="")
        self.var_model_status = tk.StringVar(value="Model status: no trained model selected")
        self.var_training_status = tk.StringVar(value="Training DB: not loaded")
        self.var_preview_limit = tk.IntVar(value=50)

        self.var_outdir = tk.StringVar(value="")
        self.var_config_file = tk.StringVar(value="")

    def _default_outdir(self) -> Path:
        return configured_output(ROOT_DIR / "outputs" / "desktop_run", "design")

    def _effective_outdir(self) -> Path:
        raw = str(self.var_outdir.get() or "").strip()
        if raw:
            return Path(raw).expanduser()
        outdir = self._default_outdir()
        self.var_outdir.set(str(outdir))
        return outdir

    # --------------------------- UI construction ---------------------------
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=(12, 10))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(2, weight=1)

        logo_path = resource_path("assets/PeptideDesignEngine_Icon.png")
        if Image is not None and ImageTk is not None and logo_path.exists():
            try:
                im = Image.open(logo_path).resize((54, 54), Image.Resampling.LANCZOS)
                self._header_logo_img = ImageTk.PhotoImage(im)
                ttk.Label(header, image=self._header_logo_img).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
        ttk.Label(header, text="Peptide Design Engine", font=("Segoe UI", 18, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="Design, review, and export peptide candidates", foreground="#555").grid(row=1, column=1, sticky="w")

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        self._tab_basic()
        self._tab_chemistry()
        self._tab_hotspot_docking()
        self._tab_ml_data()
        self._tab_advanced()
        self._tab_run_log()

        footer = ttk.Frame(self, padding=(10, 6))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(4, weight=1)
        self.apply_settings_button = ttk.Button(footer, text="1. Apply Settings", command=self.apply_settings)
        self.apply_settings_button.grid(row=0, column=0, padx=4)
        self.run_engine_button = ttk.Button(footer, text="2. Generate Candidates", command=self.run_engine, state="disabled")
        self.run_engine_button.grid(row=0, column=1, padx=4)
        self.repeat_run_button = ttk.Button(footer, text="Repeat Last Run", command=self.repeat_last_run, state="disabled")
        self.repeat_run_button.grid(row=0, column=2, padx=4)
        ttk.Button(footer, text="Stop", command=self.stop_requested).grid(row=0, column=3, padx=4)
        self.settings_status = tk.StringVar(value="Settings changed — click Apply Settings")
        ttk.Label(footer, textvariable=self.settings_status).grid(row=0, column=4, sticky="ew", padx=8)
        ttk.Button(footer, text="Open Output Folder", command=self.open_output).grid(row=0, column=5, padx=4)
        ttk.Button(footer, text="Open Result ZIP", command=self.open_zip).grid(row=0, column=6, padx=4)

    def _make_scrolled(self, parent: ttk.Frame) -> ttk.Frame:
        canvas = tk.Canvas(parent, highlightthickness=0, background=BACKGROUND)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _configure_inner(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _configure_canvas(event):
            # Keep the inner frame width synced with the visible canvas width.
            canvas.itemconfigure(window_id, width=event.width)

        def _on_mousewheel(event):
            # Windows/macOS: event.delta, Linux: Button-4/5.
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            else:
                delta = getattr(event, "delta", 0)
                if delta:
                    canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        def _bind_mousewheel(_event=None):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        inner.bind("<Configure>", _configure_inner)
        canvas.bind("<Configure>", _configure_canvas)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return inner

    def _row_entry(self, parent, row, label, var, width=18):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        e = ttk.Entry(parent, textvariable=var, width=width)
        e.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
        return e

    def _row_combo(self, parent, row, label, var, values, width=22):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        cb = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
        cb.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
        return cb

    def _tab_basic(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="1. Design Settings")
        inner = self._make_scrolled(tab)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

        ttk.Label(inner, text="Target sequences", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        ttk.Label(inner, text="Comma / newline separated. Example: DELIKFVRWA, YYERWFCAA").grid(row=1, column=0, columnspan=4, sticky="w", padx=6)
        self.target_text = scrolledtext.ScrolledText(inner, height=4, wrap="word")
        self.target_text.grid(row=2, column=0, columnspan=4, sticky="ew", padx=6, pady=4)
        self.target_text.insert("1.0", self.var_targets.get())

        preset_combo = self._row_combo(inner, 3, "Preset", self.var_preset, ["custom", "fast", "paper", "exploration", "hotspot_only"])
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_preset_to_ui(), add=True)
        self._row_combo(inner, 4, "Target Scope", self.var_target_mode, ["SINGLE", "MULTI", "BRIDGE"])
        self._row_combo(inner, 5, "Design Strategy", self.var_design_mode, ["SINGLE_TARGET", "MULTI_TARGET_BINDER", "BRIDGE_LINKER"])
        self._row_combo(inner, 6, "Optimization Goal", self.var_binder_mode, ["BALANCED", "AFFINITY_FIRST", "DEVELOPABILITY", "DUAL_BINDER", "CYCLIC_PEPTIDE"])
        self._row_entry(inner, 7, "Candidates / Generation", self.var_pop)
        self._row_entry(inner, 8, "Optimization Generations", self.var_gen)
        self._row_entry(inner, 9, "Final Candidates", self.var_topk)
        self.seed_entry = self._row_entry(inner, 10, "Random Seed", self.var_seed)
        ttk.Checkbutton(
            inner,
            text="Lock seed for exact repeat",
            variable=self.var_lock_seed,
            command=self._update_seed_control,
        ).grid(row=9, column=2, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Label(
            inner,
            text="Unlocked: every Generate run receives a new recorded seed. Locked: the entered seed is reproduced exactly.",
            foreground="#555",
            wraplength=520,
        ).grid(row=10, column=2, columnspan=2, sticky="w", padx=6, pady=4)
        self._update_seed_control()

        ttk.Label(inner, text="Peptide Length Mode").grid(row=3, column=2, sticky="w", padx=6, pady=4)
        ttk.Combobox(inner, textvariable=self.var_len_mode, values=["RANDOM", "FIX"], state="readonly", width=16).grid(row=3, column=3, sticky="ew", padx=6, pady=4)
        ttk.Label(inner, text="Fixed Length").grid(row=4, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(inner, textvariable=self.var_fix_len, width=18).grid(row=4, column=3, sticky="ew", padx=6, pady=4)
        ttk.Label(inner, text="Min Length").grid(row=5, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(inner, textvariable=self.var_min_len, width=18).grid(row=5, column=3, sticky="ew", padx=6, pady=4)
        ttk.Label(inner, text="Max Length").grid(row=6, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(inner, textvariable=self.var_max_len, width=18).grid(row=6, column=3, sticky="ew", padx=6, pady=4)
        ttk.Label(inner, text="Length Measurement").grid(row=7, column=2, sticky="w", padx=6, pady=4)
        ttk.Combobox(inner, textvariable=self.var_length_metric, values=["TOKEN", "RESIDUE", "EXPANDED"], state="readonly").grid(row=7, column=3, sticky="ew", padx=6, pady=4)
        ttk.Checkbutton(inner, text="Trim to length", variable=self.var_trim).grid(row=8, column=2, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Label(inner, text="Output Folder").grid(row=11, column=0, sticky="w", padx=6, pady=(14, 4))
        ttk.Entry(inner, textvariable=self.var_outdir).grid(row=11, column=1, columnspan=2, sticky="ew", padx=6, pady=(14, 4))
        ttk.Button(inner, text="Browse", command=lambda: self._pick_dir(self.var_outdir)).grid(row=11, column=3, sticky="w", padx=6, pady=(14, 4))

        ttk.Label(inner, text="Optional Settings JSON").grid(row=12, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(inner, textvariable=self.var_config_file).grid(row=12, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(inner, text="Browse", command=lambda: self._pick_file(self.var_config_file, [("JSON", "*.json"), ("All", "*.*")])).grid(row=12, column=3, sticky="w", padx=6, pady=4)

    def _selected_tokens(self, var_map: Dict[str, tk.BooleanVar]) -> List[str]:
        return [token for token, var in var_map.items() if bool(var.get())]

    def _set_token_group(self, var_map: Dict[str, tk.BooleanVar], value: bool) -> None:
        for var in var_map.values():
            var.set(value)

    def _checkbox_group(self, parent, row: int, title: str, var_map: Dict[str, tk.BooleanVar], columns: int = 5) -> int:
        frame = self._checkbox_group_frame(parent, row, title, var_map, columns=columns)
        return row + 1

    def _checkbox_group_frame(self, parent, row: int, title: str, var_map: Dict[str, tk.BooleanVar], columns: int = 5):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=6, pady=8)
        for cidx in range(columns):
            frame.columnconfigure(cidx, weight=1)
        for i, (token, var) in enumerate(var_map.items()):
            ttk.Checkbutton(frame, text=token, variable=var).grid(row=i // columns, column=i % columns, sticky="w", padx=4, pady=2)
        btn_row = (len(var_map) + columns - 1) // columns
        ttk.Button(frame, text="All", command=lambda m=var_map: self._set_token_group(m, True)).grid(row=btn_row, column=0, sticky="w", padx=4, pady=(8, 0))
        ttk.Button(frame, text="None", command=lambda m=var_map: self._set_token_group(m, False)).grid(row=btn_row, column=1, sticky="w", padx=4, pady=(8, 0))
        return frame

    def _toggle_widget_grid(self, widget, visible: bool) -> None:
        if visible:
            widget.grid()
        else:
            widget.grid_remove()

    def _apply_motif_preset(self) -> None:
        """Apply a practical motif preset as an editable starting point."""
        preset = (self.var_motif_preset.get() or "Custom").strip()
        presets = {
            "Custom": ("OFF", ""),
            "RGD integrin-like": ("RANDOM", "RGD"),
            "PXXP SH3-like": ("RANDOM", "PXXP"),
            "LXXLL nuclear-receptor-like": ("RANDOM", "LXXLL"),
            "KLV hydrophobic anchor-like": ("RANDOM", "KLV"),
            "RGD + acidic patch example": ("FIXED", "RGD@1 / EEMQR@4"),
            "Short cationic anchor example": ("RANDOM", "KR / RR"),
        }
        mode, spec = presets.get(preset, ("OFF", ""))
        self.var_motif_placement_mode.set(mode)
        self.var_motif_placement_specs.set(spec)
        if spec:
            self.var_motif_lock.set(True)
        self._update_chemistry_visibility()

    def _update_chemistry_visibility(self, *_args) -> None:
        """Show detailed chemistry libraries only when their feature toggle is enabled."""
        if not hasattr(self, "chem_sections"):
            return

        show_tag = bool(self.var_use_tag.get())
        show_linker = bool(self.var_use_linker.get())
        show_label = bool(self.var_use_label.get())
        show_non_nat = bool(self.var_use_non_nat.get())
        show_base = bool(self.var_use_base_chem.get())
        show_any = show_tag or show_linker or show_label or show_non_nat or show_base

        self._toggle_widget_grid(self.chem_sections["library_header"], show_any)
        self._toggle_widget_grid(self.chem_sections["hidden_note"], not show_any)
        self._toggle_widget_grid(self.chem_sections["tag"], show_tag)
        self._toggle_widget_grid(self.chem_sections["linker"], show_linker)
        self._toggle_widget_grid(self.chem_sections["linker_opts"], show_linker)
        self._toggle_widget_grid(self.chem_sections["label"], show_label)
        self._toggle_widget_grid(self.chem_sections["non_nat"], show_non_nat)
        self._toggle_widget_grid(self.chem_sections["base_chem"], show_base)
        self._toggle_widget_grid(self.chem_sections["base_info"], show_base)
        self._toggle_widget_grid(getattr(self, "motif_frame", None), bool(self.var_motif_lock.get()))

    def _tab_chemistry(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="2. Chemistry / Constraints")
        inner = self._make_scrolled(tab)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

        ttk.Label(inner, text="Feature toggles", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))

        toggle_specs = [
            ("Use D-form residues", self.var_use_d),
            ("Use non-natural residues (uncheck = hide non-natural list)", self.var_use_non_nat),
            ("Use linker system (uncheck = hide linker options)", self.var_use_linker),
            ("Use tag system (uncheck = hide tag options)", self.var_use_tag),
            ("Use base chemistry / N-terminal chemicals (uncheck = hide)", self.var_use_base_chem),
            ("Use label system (uncheck = hide label options)", self.var_use_label),
            ("Allow C-term NH2", self.var_use_cterm_nh2),
            ("Motif lock", self.var_motif_lock),
        ]
        for i, (text, var) in enumerate(toggle_specs):
            ttk.Checkbutton(
                inner,
                text=text,
                variable=var,
                command=self._update_chemistry_visibility
            ).grid(row=1 + i // 2, column=(i % 2) * 2, columnspan=2, sticky="w", padx=6, pady=4)

        r = 5

        library_header = ttk.Label(
            inner,
            text="Selectable chemistry libraries",
            font=("Segoe UI", 11, "bold")
        )
        library_header.grid(row=r, column=0, columnspan=4, sticky="w", padx=6, pady=(16, 4))
        r += 1

        hidden_note = ttk.Label(
            inner,
            text="Detailed option libraries are shown only when their feature toggle is enabled.",
            foreground="#555",
            wraplength=980
        )
        hidden_note.grid(row=r, column=0, columnspan=4, sticky="w", padx=6, pady=(8, 8))
        r += 1

        tag_frame = self._checkbox_group_frame(
            inner, r,
            "Tags / affinity or epitope handles (TAG_TYPES)",
            self.var_tag_types,
            columns=5
        )
        r += 1

        linker_frame = self._checkbox_group_frame(
            inner, r,
            "Linkers / spacers / conjugation handles (LINKER_TYPES)",
            self.var_linker_types,
            columns=5
        )
        r += 1

        linker_opts = ttk.LabelFrame(inner, text="Linker behavior", padding=8)
        linker_opts.grid(row=r, column=0, columnspan=4, sticky="ew", padx=6, pady=8)
        linker_opts.columnconfigure(1, weight=1)
        ttk.Label(linker_opts, text="LINKER_MODE").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(linker_opts, textvariable=self.var_linker_mode, values=["MIX", "FIX", "AUTO"], width=18, state="readonly").grid(row=0, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(linker_opts, text="FIX_LINKER_TYPE").grid(row=0, column=2, sticky="w", padx=4, pady=3)
        ttk.Combobox(linker_opts, textvariable=self.var_fix_linker_type, values=self.linker_choices, width=20, state="normal").grid(row=0, column=3, sticky="w", padx=4, pady=3)
        ttk.Label(linker_opts, text="MAX_LINKERS").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(linker_opts, textvariable=self.var_max_linkers, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=3)
        r += 1

        label_frame = self._checkbox_group_frame(
            inner, r,
            "Labels / fluorophores / biotin / chelators (LABEL_TYPES)",
            self.var_label_types,
            columns=5
        )
        r += 1

        non_nat_frame = self._checkbox_group_frame(
            inner, r,
            "Non-natural residues (NON_NAT_TYPES)",
            self.var_non_nat_types,
            columns=5
        )
        r += 1

        base_chem_frame = self._checkbox_group_frame(
            inner, r,
            "N-terminal chemicals / base chemistry caps (BASE_CHEM_TYPES)",
            self.var_base_chem_types,
            columns=5
        )
        r += 1

        base_info = ttk.Label(
            inner,
            text=(
                "Meaning: N-terminal chemicals are terminal caps/conjugation groups placed at the peptide N-terminus "
                "or treated as N-terminal chemistry tokens, e.g. Ac, Pal, Myr, Chol, BiotinCap, Azide/Alkyne/DBCO. "
                "They are not ordinary amino-acid substitutions."
            ),
            foreground="#555",
            wraplength=980
        )
        base_info.grid(row=r, column=0, columnspan=4, sticky="w", padx=6, pady=(8, 12))
        r += 1

        self.chem_sections = {
            "library_header": library_header,
            "hidden_note": hidden_note,
            "tag": tag_frame,
            "linker": linker_frame,
            "linker_opts": linker_opts,
            "label": label_frame,
            "non_nat": non_nat_frame,
            "base_chem": base_chem_frame,
            "base_info": base_info,
        }

        self.motif_frame = ttk.LabelFrame(inner, text="Motif / bridge constraints", padding=8)
        self.motif_frame.grid(row=r, column=0, columnspan=4, sticky="ew", padx=6, pady=(10, 8))
        self.motif_frame.columnconfigure(1, weight=1)
        mf = self.motif_frame
        mr = 0
        ttk.Label(mf, text="Motif preset").grid(row=mr, column=0, sticky="w", padx=6, pady=4)
        motif_preset_combo = ttk.Combobox(mf, textvariable=self.var_motif_preset, values=["Custom", "RGD integrin-like", "PXXP SH3-like", "LXXLL nuclear-receptor-like", "KLV hydrophobic anchor-like", "RGD + acidic patch example", "Short cationic anchor example"], width=32, state="readonly")
        motif_preset_combo.grid(row=mr, column=1, sticky="ew", padx=6, pady=4)
        motif_preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_motif_preset(), add=True)
        mr += 1
        ttk.Label(mf, text="Locked motifs").grid(row=mr, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(mf, textvariable=self.var_locked_motifs, width=50).grid(row=mr, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        mr += 1
        ttk.Label(mf, text="Motif placement").grid(row=mr, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(mf, textvariable=self.var_motif_placement_mode, values=["OFF", "FIXED", "RANDOM"], width=22, state="readonly").grid(row=mr, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(mf, text="Bridge anchor length").grid(row=mr, column=2, sticky="w", padx=6, pady=4)
        ttk.Entry(mf, textvariable=self.var_bridge_anchor_len, width=12).grid(row=mr, column=3, sticky="w", padx=6, pady=4)
        mr += 1
        ttk.Label(mf, text="Motif specs").grid(row=mr, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(mf, textvariable=self.var_motif_placement_specs, width=50).grid(row=mr, column=1, columnspan=3, sticky="ew", padx=6, pady=4)
        ttk.Label(mf, text="OFF disables motif placement. FIXED: RGD@1, EEMQR@4 or RGD@1 / EEMQR@4   |   RANDOM: RGD, EEMQR or RGD / EEMQR", foreground="#666666").grid(row=mr+1, column=1, columnspan=3, sticky="w", padx=6, pady=(0,4))
        mr += 2
        ttk.Label(mf, text="Legacy position mode").grid(row=mr, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(mf, textvariable=self.var_motif_pos_mode, values=["FREE", "N_TERM", "CENTER", "C_TERM"], width=22, state="readonly").grid(row=mr, column=1, sticky="ew", padx=6, pady=4)
        r += 1

        self._update_chemistry_visibility()

    def _tab_hotspot_docking(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="3. Hot Spot / Docking")
        inner = self._make_scrolled(tab)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(3, weight=1)

        ttk.Label(inner, text="Hot spot / epitope extraction", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=6, pady=(10, 4))
        ttk.Checkbutton(inner, text="Detect hot spots automatically", variable=self.var_auto_hotspot).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self._row_combo(inner, 2, "Hot Spot Source", self.var_hotspot_source, ["SEQUENCE", "PDB"])
        self._row_entry(inner, 3, "Source Sequence", self.var_hotspot_sequence, width=50)
        ttk.Label(inner, text="PDB file").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(inner, textvariable=self.var_hotspot_pdb_file).grid(row=4, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(inner, text="Browse", command=lambda: self._pick_file(self.var_hotspot_pdb_file, [("PDB", "*.pdb"), ("Text", "*.txt"), ("All", "*.*")])).grid(row=4, column=3, sticky="w", padx=6, pady=4)
        self._row_entry(inner, 5, "Analysis Window", self.var_hotspot_window)
        self._row_entry(inner, 6, "Candidate Regions", self.var_hotspot_topk)
        ttk.Checkbutton(inner, text="Use detected regions as targets", variable=self.var_hotspot_replace).grid(row=7, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(inner, text="Use detected region as a locked motif", variable=self.var_hotspot_lock_motif).grid(row=8, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Label(inner, text="Docking preparation / structure-input export", font=("Segoe UI", 11, "bold")).grid(row=10, column=0, columnspan=4, sticky="w", padx=6, pady=(18, 4))
        self._row_combo(inner, 11, "Docking stage", self.var_docking_stage, ["OFF", "FINAL_TOP_ONLY", "EVERY_N_GENERATIONS"])
        self._row_combo(inner, 12, "Docking engine", self.var_docking_engine, ["NONE", "CUSTOM", "ROSETTA", "VINA", "DIFFDOCK"])
        self._row_combo(inner, 13, "Docking-ready mode", self.var_docking_ready_mode, ["BASIC", "ADVANCED"])
        self._row_entry(inner, 14, "Docking-ready bonus", self.var_docking_bonus)
        ttk.Checkbutton(inner, text="Prepare canonical sequence-only complex inputs", variable=self.var_pseudodock).grid(row=15, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._row_entry(inner, 16, "Receptor sequence", self.var_receptor_sequence, width=50)
        self._row_entry(inner, 17, "Structure-input top K", self.var_pseudodock_topk)

    def _tab_ml_data(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="4. Data / ML")
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        top = ttk.Frame(tab, padding=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Continual-learning Data / ML Maintenance", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 6))

        ttk.Label(top, text="Training DB CSV").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(top, textvariable=self.var_training_db).grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(top, text="Browse/Create", command=lambda: self._pick_save_file(self.var_training_db, [("CSV", "*.csv"), ("All", "*.*")])).grid(row=1, column=2, sticky="w", padx=4, pady=3)
        ttk.Button(top, text="Refresh Preview", command=self.refresh_training_preview).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(top, text="Candidate mapping CSV").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(top, textvariable=self.var_mapping_csv).grid(row=2, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(top, text="Browse", command=lambda: self._pick_file(self.var_mapping_csv, [("CSV", "*.csv"), ("All", "*.*")])).grid(row=2, column=2, sticky="w", padx=4, pady=3)
        ttk.Button(top, text="Make Mapping Template", command=self.make_mapping_template).grid(row=2, column=3, sticky="w", padx=4, pady=3)

        import_box = ttk.LabelFrame(top, text="Import / Parse", padding=8)
        import_box.grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=8)
        for i in range(4):
            import_box.columnconfigure(i, weight=1)
        ttk.Button(import_box, text="Import prepared CSVs", command=self.import_training_data).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(import_box, text="Parse AF3 folder -> Import", command=self.parse_import_af3_folder).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(import_box, text="Parse PRODIGY txt/csv/folder -> Import", command=self.parse_import_prodigy).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(import_box, text="Open training DB", command=self.open_training_db).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

        ml_box = ttk.LabelFrame(top, text="Train / Rerank", padding=8)
        ml_box.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=8)
        ml_box.columnconfigure(1, weight=1)
        ttk.Label(ml_box, text="Built-in untrained reranking: disabled; select a user-data trained model below.", foreground="#8a4b08").grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=3)

        ttk.Label(ml_box, text="ML label column").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        self.ml_label_combo = ttk.Combobox(
            ml_box,
            textvariable=self.var_ml_label,
            values=["experimental_binding", "prodigy_delta_g", "prodigy_kd", "docking_score", "hplc_purity", "af3_confidence", "af3_iptm", "af3_ptm", "af3_ranking_score", "activity_score"],
            width=28,
            state="normal"
        )
        self.ml_label_combo.grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(ml_box, text="Models directory").grid(row=3, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(ml_box, textvariable=self.var_models_dir).grid(row=3, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(ml_box, text="Browse", command=lambda: self._pick_dir(self.var_models_dir)).grid(row=3, column=2, sticky="w", padx=4, pady=3)
        ttk.Button(ml_box, text="Train model", command=self.train_ml).grid(row=3, column=3, sticky="ew", padx=4, pady=3)

        ttk.Label(ml_box, text="Trained model JSON").grid(row=4, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(ml_box, textvariable=self.var_trained_model).grid(row=4, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(ml_box, text="Browse", command=lambda: self._pick_file(self.var_trained_model, [("Model JSON", "*.json"), ("All", "*.*")])).grid(row=4, column=2, sticky="w", padx=4, pady=3)
        ttk.Button(ml_box, text="Check model", command=self.update_model_status).grid(row=4, column=3, sticky="ew", padx=4, pady=3)

        ttk.Label(ml_box, text="Trained ML blend weight").grid(row=5, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(ml_box, textvariable=self.var_trained_ml_weight, width=12).grid(row=5, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(ml_box, textvariable=self.var_model_status, foreground="#335").grid(row=6, column=0, columnspan=4, sticky="w", padx=4, pady=(5, 0))
        ttk.Label(ml_box, textvariable=self.var_training_status, foreground="#335").grid(row=7, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 0))

        prior_box = ttk.LabelFrame(top, text="User-reviewed statistical ranking prior", padding=8)
        prior_box.grid(row=5, column=0, columnspan=4, sticky="ew", padx=4, pady=8)
        prior_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(prior_box, text="Use explicit CSV statistical prior", variable=self.var_use_ml_prior).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=3)
        ttk.Label(prior_box, text="Prior weight").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(prior_box, textvariable=self.var_ml_prior_weight, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(prior_box, text="Prior table path").grid(row=2, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(prior_box, textvariable=self.var_ml_prior_table).grid(row=2, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(prior_box, text="Browse", command=lambda: self._pick_file(self.var_ml_prior_table, [("CSV", "*.csv"), ("All", "*.*")])).grid(row=2, column=2, sticky="w", padx=4, pady=3)
        ttk.Label(prior_box, text="Requires an explicit reviewed CSV. This is not ML, affinity, ΔG, Kd, or experimental validation.", foreground="#666").grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=(2,0))

        preview_frame = ttk.LabelFrame(tab, text="training_data.csv preview", padding=6)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        preview_frame.rowconfigure(1, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        bar = ttk.Frame(preview_frame)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text="Preview rows").pack(side="left", padx=4)
        ttk.Entry(bar, textvariable=self.var_preview_limit, width=8).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh", command=self.refresh_training_preview).pack(side="left", padx=4)

        columns = ("candidate_id", "sequence", "target_id", "source_type", "af3_iptm", "af3_ptm", "af3_ranking_score", "prodigy_delta_g", "prodigy_kd", "experimental_binding", "activity_label")
        self.training_tree = ttk.Treeview(preview_frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.training_tree.heading(col, text=col)
            self.training_tree.column(col, width=120 if col != "sequence" else 260, anchor="w")
        ysb = ttk.Scrollbar(preview_frame, orient="vertical", command=self.training_tree.yview)
        xsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.training_tree.xview)
        self.training_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.training_tree.grid(row=1, column=0, sticky="nsew")
        ysb.grid(row=1, column=1, sticky="ns")
        xsb.grid(row=2, column=0, sticky="ew")

        self.after(300, self.refresh_training_preview)
        self.after(350, self.update_model_status)

    def _tab_advanced(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="5. Expert Override")
        tab.rowconfigure(2, weight=1)
        tab.columnconfigure(0, weight=1)

        msg = (
            "Expert Override is optional. It does NOT create new engine features or data. "
            "It only overrides CONFIG keys that are already implemented in peptide_engine.py. "
            "Leave it as {} for normal GUI use."
        )
        ttk.Label(tab, text=msg, padding=8, foreground="#444", wraplength=1050).grid(row=0, column=0, sticky="ew")

        quick = ttk.Frame(tab, padding=(8, 0, 8, 4))
        quick.grid(row=1, column=0, sticky="ew")
        ttk.Button(quick, text="Load JSON file", command=self.load_json_to_advanced).pack(side="left", padx=4)
        ttk.Button(quick, text="Show FULL current CONFIG", command=self.load_full_current_config_to_advanced).pack(side="left", padx=4)
        ttk.Button(quick, text="Insert chemistry override example", command=self.insert_chemistry_override_example).pack(side="left", padx=4)
        ttk.Button(quick, text="Insert constraints/scoring example", command=self.insert_constraints_override_example).pack(side="left", padx=4)
        ttk.Button(quick, text="Reset to {}", command=self.reset_advanced).pack(side="left", padx=4)

        self.advanced_text = scrolledtext.ScrolledText(tab, wrap="none", height=22)
        self.advanced_text.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        self.advanced_text.insert("1.0", "{}")

        bar = ttk.Frame(tab, padding=8)
        bar.grid(row=3, column=0, sticky="ew")
        ttk.Button(bar, text="Validate JSON", command=self.validate_advanced_json).pack(side="left", padx=4)
        ttk.Button(bar, text="Save current GUI config JSON", command=self.save_current_config_json).pack(side="left", padx=4)
        ttk.Label(
            bar,
            text="Tip: normal GUI selections are applied first; this override is applied last.",
            foreground="#555"
        ).pack(side="left", padx=12)

    def _tab_run_log(self) -> None:
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="6. Log / Results")
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        btns = ttk.Frame(tab, padding=6)
        btns.grid(row=0, column=0, sticky="ew")
        ttk.Button(btns, text="Clear log", command=lambda: self.log_text.delete("1.0", "end")).pack(side="left", padx=4)
        ttk.Button(btns, text="Open output folder", command=self.open_output).pack(side="left", padx=4)
        ttk.Button(btns, text="Open output ZIP", command=self.open_zip).pack(side="left", padx=4)
        self.log_text = scrolledtext.ScrolledText(tab, wrap="word", height=14)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.tree = ttk.Treeview(tab, columns=("rank", "score", "length", "valid", "sequence"), show="headings", height=10)
        for col, w in [("rank", 70), ("score", 100), ("length", 80), ("valid", 80), ("sequence", 700)]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.grid(row=2, column=0, sticky="ew", padx=8, pady=(4, 8))

    # --------------------------- file pickers ---------------------------
    def _pick_file(self, var: tk.StringVar, types) -> None:
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            var.set(path)

    def _pick_save_file(self, var: tk.StringVar, types) -> None:
        path = filedialog.asksaveasfilename(filetypes=types, defaultextension=".csv")
        if path:
            var.set(path)

    def _pick_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    # --------------------------- config ---------------------------
    def preset_config(self, name: str) -> Dict[str, Any]:
        """Return a complete, deterministic configuration for preset-owned fields.

        Presets intentionally do not touch user-owned chemistry choices that are
        outside their historical scope (for example USE_CTERM_NH2 or the selected
        chemistry token lists).  Every field that *is* owned by the preset system
        is reset here so applying a preset never depends on which preset was used
        immediately before it.
        """
        baseline = {
            "TARGET_MODE_LABEL": "MULTI",
            "DESIGN_MODE": "MULTI_TARGET_BINDER",
            "BINDER_MODE": "BALANCED",
            "LEN_MODE": "RANDOM",
            "MIN_LENGTH": 18,
            "MAX_LENGTH": 30,
            "FIX_LENGTH": 24,
            "POP": 200,
            "GEN": 20,
            "FINAL_TOPK": 10,
            "USE_D": True,
            "USE_NON_NAT": True,
            "USE_LINKER": True,
            "USE_TAG": True,
            "USE_BASE_CHEM": True,
            "USE_LABEL": True,
            "MOTIF_LOCK": False,
            "USE_OPTIONAL_ML": False,
            "ML_RERANK_WEIGHT": 0.20,
            "AUTO_HOTSPOT": False,
            "HOTSPOT_SOURCE": "SEQUENCE",
            "PREPARE_PSEUDODOCKING_COLAB": False,
        }

        overrides: Dict[str, Dict[str, Any]] = {
            "fast": {
                "MIN_LENGTH": 10, "MAX_LENGTH": 12, "FIX_LENGTH": 12,
                "POP": 100, "GEN": 8, "FINAL_TOPK": 10,
                "USE_D": False, "USE_NON_NAT": False, "USE_LINKER": False,
                "USE_TAG": False, "USE_BASE_CHEM": False, "USE_LABEL": False,
                "MOTIF_LOCK": False,
            },
            "paper": {
                "TARGET_MODE_LABEL": "BRIDGE",
                "DESIGN_MODE": "BRIDGE_LINKER",
                "MIN_LENGTH": 12, "MAX_LENGTH": 15, "FIX_LENGTH": 14,
                "POP": 200, "GEN": 20, "FINAL_TOPK": 25,
            },
            "exploration": {
                "MIN_LENGTH": 12, "MAX_LENGTH": 20, "FIX_LENGTH": 16,
                "POP": 300, "GEN": 30, "FINAL_TOPK": 50,
                "USE_OPTIONAL_ML": False, "ML_RERANK_WEIGHT": 0.20,
            },
            "hotspot_only": {
                "TARGET_MODE_LABEL": "MULTI",
                "DESIGN_MODE": "MULTI_TARGET_BINDER",
                "MIN_LENGTH": 12, "MAX_LENGTH": 15, "FIX_LENGTH": 14,
                "POP": 200, "GEN": 20, "FINAL_TOPK": 25,
                "USE_D": False, "USE_NON_NAT": False, "USE_LINKER": False,
                "USE_TAG": False, "USE_BASE_CHEM": False, "USE_LABEL": False,
                "AUTO_HOTSPOT": True,
            },
        }
        selected = overrides.get(name)
        if selected is None:
            return {}
        cfg = dict(baseline)
        cfg.update(selected)
        return cfg

    def apply_preset_to_ui(self) -> None:
        cfg = self.preset_config(self.var_preset.get())
        if not cfg:
            return
        for key, value in cfg.items():
            mapping = {
                "TARGET_MODE_LABEL": self.var_target_mode,
                "LEN_MODE": self.var_len_mode, "MIN_LENGTH": self.var_min_len, "MAX_LENGTH": self.var_max_len, "FIX_LENGTH": self.var_fix_len,
                "POP": self.var_pop, "GEN": self.var_gen, "FINAL_TOPK": self.var_topk, "DESIGN_MODE": self.var_design_mode,
                "BINDER_MODE": self.var_binder_mode, "USE_D": self.var_use_d, "USE_NON_NAT": self.var_use_non_nat, "USE_LINKER": self.var_use_linker,
                "USE_TAG": self.var_use_tag, "USE_BASE_CHEM": self.var_use_base_chem, "USE_LABEL": self.var_use_label,
                "MOTIF_LOCK": self.var_motif_lock, "USE_OPTIONAL_ML": self.var_optional_ml, "ML_RERANK_WEIGHT": self.var_ml_weight,
                "AUTO_HOTSPOT": self.var_auto_hotspot, "HOTSPOT_SOURCE": self.var_hotspot_source, "PREPARE_PSEUDODOCKING_COLAB": self.var_pseudodock,
            }
            var = mapping.get(key)
            if var is not None:
                var.set(value)
        self._log(f"Preset applied to UI: {self.var_preset.get()}\n")

    def collect_config(self) -> Dict[str, Any]:
        cfg: Dict[str, Any] = dict(eng.CONFIG)

        config_file = self.var_config_file.get().strip()
        if config_file:
            with open(config_file, encoding="utf-8") as f:
                cfg.update(json.load(f))

        target_text = self.target_text.get("1.0", "end").strip()
        cfg.update({
            "TARGETS": parse_targets(target_text),
            "TARGET_MODE_LABEL": self.var_target_mode.get(),
            "DESIGN_MODE": self.var_design_mode.get(),
            "BINDER_MODE": self.var_binder_mode.get(),
            "POP": int(self.var_pop.get()),
            "GEN": int(self.var_gen.get()),
            "FINAL_TOPK": int(self.var_topk.get()),
            "SEED": int(self.var_seed.get()),
            "AUTO_SEED_EACH_RUN": not bool(self.var_lock_seed.get()),
            "LEN_MODE": self.var_len_mode.get(),
            "FIX_LENGTH": int(self.var_fix_len.get()),
            "MIN_LENGTH": int(self.var_min_len.get()),
            "MAX_LENGTH": int(self.var_max_len.get()),
            "LENGTH_COUNT_MODE": self.var_length_metric.get(),
            "LENGTH_METRIC": self.var_length_metric.get(),
            "TRIM_TO_LENGTH": bool(self.var_trim.get()),
            "USE_D": bool(self.var_use_d.get()),
            "USE_NON_NAT": bool(self.var_use_non_nat.get()),
            "USE_LINKER": bool(self.var_use_linker.get()),
            "USE_TAG": bool(self.var_use_tag.get()),
            "USE_BASE_CHEM": bool(self.var_use_base_chem.get()),
            "USE_LABEL": bool(self.var_use_label.get()),
            "USE_CTERM_NH2": bool(self.var_use_cterm_nh2.get()),
            "TAG_TYPES": self._selected_tokens(self.var_tag_types),
            "LINKER_TYPES": self._selected_tokens(self.var_linker_types),
            "LINKER_MODE": self.var_linker_mode.get(),
            "FIX_LINKER_TYPE": self.var_fix_linker_type.get().strip(),
            "MAX_LINKERS": int(self.var_max_linkers.get()),
            "LABEL_TYPES": self._selected_tokens(self.var_label_types),
            "BASE_CHEM_TYPES": self._selected_tokens(self.var_base_chem_types),
            "NON_NAT_TYPES": self._selected_tokens(self.var_non_nat_types),
            "MOTIF_LOCK": bool(self.var_motif_lock.get()),
            "LOCKED_MOTIFS": [x.strip() for x in re.sub(r"[,;/\n]+", ",", self.var_locked_motifs.get()).split(",") if x.strip()],
            "MOTIF_POSITION_MODE": self.var_motif_pos_mode.get(),
            "MOTIF_PLACEMENT_MODE": self.var_motif_placement_mode.get(),
            "MOTIF_PLACEMENT_SPECS": self.var_motif_placement_specs.get().strip(),
            "BRIDGE_ANCHOR_LEN": int(self.var_bridge_anchor_len.get()),
            "AUTO_HOTSPOT": bool(self.var_auto_hotspot.get()),
            "HOTSPOT_SOURCE": self.var_hotspot_source.get(),
            "HOTSPOT_SEQUENCE": self.var_hotspot_sequence.get().strip(),
            "HOTSPOT_WINDOW": int(self.var_hotspot_window.get()),
            "HOTSPOT_TOPK": int(self.var_hotspot_topk.get()),
            "HOTSPOT_REPLACE_TARGETS": bool(self.var_hotspot_replace.get()),
            "HOTSPOT_LOCK_AS_MOTIF": bool(self.var_hotspot_lock_motif.get()),
            "DOCKING_STAGE": self.var_docking_stage.get(),
            "DOCKING_ENGINE": self.var_docking_engine.get(),
            "DOCKING_READY_MODE": self.var_docking_ready_mode.get(),
            "DOCKING_READY_BONUS_WEIGHT": float(self.var_docking_bonus.get()),
            "PREPARE_PSEUDODOCKING_COLAB": bool(self.var_pseudodock.get()),
            "RECEPTOR_SEQUENCE": self.var_receptor_sequence.get().strip(),
            "PSEUDODOCKING_TOPK": int(self.var_pseudodock_topk.get()),
            "USE_OPTIONAL_ML": False,
            "ML_RERANK_WEIGHT": float(self.var_ml_weight.get()),
            "USE_ML_PRIOR": bool(self.var_use_ml_prior.get()),
            "ML_PRIOR_WEIGHT": float(self.var_ml_prior_weight.get()),
            "ML_PRIOR_TABLE_PATH": self.var_ml_prior_table.get().strip(),
        })

        if self.var_target_mode.get() in {"SINGLE", "MULTI", "BRIDGE"}:
            cfg["DESIGN_MODE"] = {"SINGLE": "SINGLE_TARGET", "MULTI": "MULTI_TARGET_BINDER", "BRIDGE": "BRIDGE_LINKER"}[self.var_target_mode.get()]

        pdb_file = self.var_hotspot_pdb_file.get().strip()
        if pdb_file:
            cfg["HOTSPOT_PDB_TEXT"] = Path(pdb_file).read_text(encoding="utf-8")
            cfg["HOTSPOT_SOURCE"] = "PDB"

        # Motif lock is the user-facing master switch. If it is off, motif
        # placement must be disabled internally as well, even if old/preset
        # values remain in hidden fields.
        if not bool(self.var_motif_lock.get()):
            cfg["LOCKED_MOTIFS"] = []
            cfg["MOTIF_PLACEMENT_MODE"] = "OFF"
            cfg["MOTIF_PLACEMENT_SPECS"] = ""
            cfg["MOTIF_POSITION_MODE"] = "FREE"

        adv = self.advanced_text.get("1.0", "end").strip()
        if adv:
            cfg.update(json.loads(adv))

        return cfg

    def load_json_to_advanced(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        data = Path(path).read_text(encoding="utf-8")
        json.loads(data)
        self.advanced_text.delete("1.0", "end")
        self.advanced_text.insert("1.0", data)

    def _replace_advanced_json(self, data: Dict[str, Any]) -> None:
        self.advanced_text.delete("1.0", "end")
        self.advanced_text.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))

    def validate_advanced_json(self) -> None:
        try:
            raw = self.advanced_text.get("1.0", "end").strip() or "{}"
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Advanced override must be a JSON object, e.g. {}")
            messagebox.showinfo("JSON valid", f"Valid JSON object with {len(data)} keys.")
        except Exception as e:
            messagebox.showerror("JSON error", str(e))

    def load_full_current_config_to_advanced(self) -> None:
        """Show the full CONFIG that would be used now.

        This is for inspection/export. Editing the full block is possible, but normal use should
        keep Expert Override small, usually only the keys you intentionally override.
        """
        try:
            # Temporarily ignore current advanced block to avoid nesting stale overrides.
            old = self.advanced_text.get("1.0", "end")
            self.advanced_text.delete("1.0", "end")
            self.advanced_text.insert("1.0", "{}")
            cfg = self.collect_config()
            self.advanced_text.delete("1.0", "end")
            self.advanced_text.insert("1.0", json.dumps(cfg, indent=2, ensure_ascii=False))
            self._log("Loaded full current CONFIG into Expert Override editor for inspection.\n")
        except Exception as e:
            try:
                self.advanced_text.delete("1.0", "end")
                self.advanced_text.insert("1.0", old)
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
            messagebox.showerror("Config error", str(e))

    def insert_chemistry_override_example(self) -> None:
        self._replace_advanced_json({
            "TAG_TYPES": eng.CONFIG.get("TAG_TYPES", ["His6", "FLAG", "HA"]),
            "BASE_CHEM_TYPES": eng.CONFIG.get("BASE_CHEM_TYPES", ["Pal", "Myr", "Nic", "Caf", "Gal", "Ac"]),
            "LABEL_TYPES": eng.CONFIG.get("LABEL_TYPES", ["NONE", "BIOTIN", "FITC", "Cy5"]),
            "LINKER_TYPES": eng.CONFIG.get("LINKER_TYPES", ["Ahx", "PEG4", "PEG8"]),
            "NON_NAT_TYPES": eng.CONFIG.get("NON_NAT_TYPES", getattr(eng, "NON_NAT", ["Nle", "Orn", "Aib", "Hyp"])),
            "LINKER_MODE": eng.CONFIG.get("LINKER_MODE", "MIX"),
            "FIX_LINKER_TYPE": eng.CONFIG.get("FIX_LINKER_TYPE", "PEG4"),
            "MAX_LINKERS": eng.CONFIG.get("MAX_LINKERS", 2)
        })

    def insert_constraints_override_example(self) -> None:
        self._replace_advanced_json({
            "MAX_D_RATIO": eng.CONFIG.get("MAX_D_RATIO", 0.6),
            "MAX_NON_NAT_RATIO": eng.CONFIG.get("MAX_NON_NAT_RATIO", 0.5),
            "MAX_CYS": eng.CONFIG.get("MAX_CYS", 2),
            "MAX_ABS_CHARGE": eng.CONFIG.get("MAX_ABS_CHARGE", 7),
            "MIN_HYDRO_RATIO": eng.CONFIG.get("MIN_HYDRO_RATIO", 0.15),
            "MAX_HYDRO_RATIO": eng.CONFIG.get("MAX_HYDRO_RATIO", 0.75),
            "CHEMISTRY_BONUS_WEIGHT": eng.CONFIG.get("CHEMISTRY_BONUS_WEIGHT", 0.35),
            "DOCKING_READY_BONUS_WEIGHT": eng.CONFIG.get("DOCKING_READY_BONUS_WEIGHT", 1.0),
            "HOTSPOT_BINDING_WEIGHT": eng.CONFIG.get("HOTSPOT_BINDING_WEIGHT", 0.8),
            "BRIDGE_LINKER_BONUS_WEIGHT": eng.CONFIG.get("BRIDGE_LINKER_BONUS_WEIGHT", 1.4)
        })

    def reset_advanced(self) -> None:
        self.advanced_text.delete("1.0", "end")
        self.advanced_text.insert("1.0", "{}")

    def save_current_config_json(self) -> None:
        try:
            cfg = self.collect_config()
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
            if path:
                Path(path).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                self._log(f"Saved config: {path}\n")
        except Exception as e:
            messagebox.showerror("Config error", str(e))

    # --------------------------- actions ---------------------------
    def _install_settings_change_tracking(self) -> None:
        """Require an explicit Apply after any user-editable setting changes."""
        variables = []
        for value in self.__dict__.values():
            if isinstance(value, tk.Variable):
                variables.append(value)
            elif isinstance(value, dict):
                variables.extend(v for v in value.values() if isinstance(v, tk.Variable))
        seen = set()
        for variable in variables:
            if id(variable) in seen or variable is getattr(self, "settings_status", None):
                continue
            seen.add(id(variable))
            variable.trace_add("write", self._mark_settings_dirty)

        def bind_text(widget):
            try:
                widget.edit_modified(False)
                def changed(_event=None, _widget=widget):
                    if _widget.edit_modified():
                        _widget.edit_modified(False)
                        self._mark_settings_dirty()
                widget.bind("<<Modified>>", changed, add=True)
            except Exception:
                LOGGER.debug("Could not track PDE text changes", exc_info=True)

        bind_text(getattr(self, "target_text", None))
        bind_text(getattr(self, "advanced_text", None))

    def _mark_settings_dirty(self, *_args) -> None:
        self.settings_applied = False
        self.applied_config = None
        try:
            self.settings_status.set("Settings changed — click Apply Settings")
            self.run_engine_button.configure(state="disabled")
        except Exception:
            pass

    def apply_settings(self) -> None:
        """Validate and freeze the visible settings used by the next run."""
        try:
            config = self.collect_config()
            has_target = bool(config.get("TARGETS"))
            has_hotspot_input = bool(
                config.get("AUTO_HOTSPOT")
                and (str(config.get("HOTSPOT_SEQUENCE", "")).strip() or str(config.get("HOTSPOT_PDB_TEXT", "")).strip())
            )
            if not has_target and not has_hotspot_input:
                raise ValueError("Enter at least one target sequence, or enable automatic hot-spot detection and provide its sequence/PDB input.")
            if int(config.get("POP", 0)) <= 0 or int(config.get("GEN", 0)) <= 0 or int(config.get("FINAL_TOPK", 0)) <= 0:
                raise ValueError("Candidates per generation, optimization generations, and final candidates must be greater than zero.")
            if str(config.get("LEN_MODE", "RANDOM")).upper() == "FIX":
                if int(config.get("FIX_LENGTH", 0)) <= 0:
                    raise ValueError("Fixed Length must be greater than zero.")
            elif int(config.get("MIN_LENGTH", 0)) <= 0 or int(config.get("MAX_LENGTH", 0)) < int(config.get("MIN_LENGTH", 0)):
                raise ValueError("Min Length must be greater than zero and cannot exceed Max Length.")
        except Exception as exc:
            self.settings_applied = False
            self.applied_config = None
            self.settings_status.set("Settings contain an error")
            self.run_engine_button.configure(state="disabled")
            messagebox.showerror("Settings error", f"Settings could not be applied:\n{exc}")
            return
        self.applied_config = config
        self.settings_applied = True
        self.settings_status.set("Settings applied — ready to generate")
        self.run_engine_button.configure(state="normal")
        self._log("Settings applied. Candidate generation is ready.\n")

    def run_engine(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Running", "Engine is already running.")
            return
        if not self.settings_applied or self.applied_config is None:
            messagebox.showwarning("Apply settings", "Click Apply Settings before generating candidates.")
            return
        cfg = dict(self.applied_config)
        if bool(cfg.get("AUTO_SEED_EACH_RUN", True)):
            cfg["SEED"] = 1 + secrets.randbelow(2_147_483_646)
        self._launch_run(cfg, repeat=False)

    def repeat_last_run(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Running", "Engine is already running.")
            return
        if self.last_run_config is None:
            messagebox.showinfo("No previous run", "Generate candidates once before repeating a run.")
            return
        self._launch_run(dict(self.last_run_config), repeat=True)

    def _launch_run(self, cfg: Dict[str, Any], repeat: bool) -> None:
        outdir = self._effective_outdir()
        outdir.mkdir(parents=True, exist_ok=True)
        run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_outdir = outdir / f"run_{run_stamp}"
        self.last_run_config = dict(cfg)
        self.nb.select(self.nb.tabs()[-1])
        self._log("\n" + "=" * 80 + "\n")
        mode = "exact repeat" if repeat else ("new exploratory seed" if cfg.get("AUTO_SEED_EACH_RUN", True) else "locked reproducible seed")
        self._log(f"Starting run: {run_stamp}\nMode: {mode}\nRandom seed used: {cfg.get('SEED')}\nOutput: {run_outdir}\n")
        self._set_buttons_running(True)
        self.worker = threading.Thread(target=self._run_worker, args=(cfg, run_outdir), daemon=True)
        self.worker.start()

    def _update_seed_control(self) -> None:
        try:
            self.seed_entry.configure(state="normal" if self.var_lock_seed.get() else "disabled")
        except Exception:
            pass

    def _run_worker(self, cfg: Dict[str, Any], outdir: Path) -> None:
        try:
            qwriter = QueueWriter(self.msg_q)
            with contextlib.redirect_stdout(qwriter), contextlib.redirect_stderr(qwriter):
                rows, progress, paths = eng.run(cfg, verbose=True, outdir=str(outdir))
                trained_model = self.var_trained_model.get().strip()
                if trained_model:
                    if ml_trainer is None:
                        raise RuntimeError("ml_trainer.py could not be imported.")
                    rows = ml_trainer.rerank_rows(rows, trained_model, blend_weight=float(self.var_trained_ml_weight.get()))
                    rerank_path = Path(paths["output_dir"]) / "trained_ml_reranked_candidates.csv"
                    write_rows(rerank_path, rows[:int(cfg.get("FINAL_TOPK", 10))])
                    paths["trained_ml_reranked_csv"] = str(rerank_path)
                    paths["zip"] = rebuild_output_zip(Path(paths["output_dir"]))
                    print(f"[OK] trained ML reranking saved: {rerank_path}")
                print("\n[OK] DONE")
                print(f"Output ZIP: {paths.get('zip', '')}")
            self.msg_q.put(("done", rows, paths))
        except Exception:
            self.msg_q.put(("error", traceback.format_exc()))

    def stop_requested(self) -> None:
        self._log("Stop requested. Current engine run cannot be safely killed mid-generation from this GUI; close the app only if absolutely necessary.\n")

    def _training_db_path(self) -> Path:
        return Path(self.var_training_db.get()).expanduser().resolve()

    def refresh_training_preview(self) -> None:
        """Refresh the training_data.csv preview table and label-column choices."""
        path = self._training_db_path()
        if not hasattr(self, "training_tree"):
            return
        for item in self.training_tree.get_children():
            self.training_tree.delete(item)
        if not path.exists():
            self.var_training_status.set(f"Training DB: not found yet - {path}")
            return
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames or []
                rows = []
                limit = max(1, int(self.var_preview_limit.get()))
                for i, row in enumerate(reader):
                    if i >= limit:
                        break
                    rows.append(row)
            numeric_like = []
            for k in fields:
                kl = k.lower()
                if any(token in kl for token in ["binding", "score", "delta", "kd", "purity", "confidence", "iptm", "ptm", "ranking", "activity"]):
                    numeric_like.append(k)
            if numeric_like and hasattr(self, "ml_label_combo"):
                current = self.var_ml_label.get()
                values = list(dict.fromkeys(numeric_like + list(self.ml_label_combo.cget("values"))))
                self.ml_label_combo.configure(values=values)
                if current in values:
                    self.var_ml_label.set(current)
            cols = self.training_tree["columns"]
            for r in rows:
                self.training_tree.insert("", "end", values=[r.get(c, "") for c in cols])
            # Count total lines quickly
            total = max(0, sum(1 for _ in path.open("r", encoding="utf-8-sig")) - 1)
            self.var_training_status.set(f"Training DB: {total} rows | columns={len(fields)} | {path}")
        except Exception as e:
            self.var_training_status.set(f"Training DB preview error: {e}")

    def update_model_status(self) -> None:
        path_text = self.var_trained_model.get().strip()
        if not path_text:
            self.var_model_status.set("Model status: no trained model selected")
            return
        path = Path(path_text).expanduser()
        if not path.exists():
            self.var_model_status.set(f"Model status: not found - {path}")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            label = data.get("label_col", data.get("label", "?"))
            n = data.get("train_rows", data.get("n_train", data.get("n_samples", "?")))
            features = data.get("feature_names", data.get("features", []))
            self.var_model_status.set(f"Model status: ready | label={label} | n={n} | features={len(features)} | {path}")
        except Exception as e:
            self.var_model_status.set(f"Model status: file exists, metadata read failed: {e}")

    def make_mapping_template(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save candidate mapping template",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            defaultextension=".csv",
            initialfile="candidate_mapping_template.csv",
        )
        if not path:
            return
        rows = [{
            "candidate_id": "PDE_0001",
            "sequence": "Ac-A-C-D-E-F-G-NH2",
            "clean_sequence": "ACDEFG",
            "target_id": "TargetA",
            "source_name": "PDE_0001",
            "file": "PDE_0001_scores.json",
            "folder": "PDE_0001",
            "notes": "Fill this file when AF3/PRODIGY filenames do not already contain candidate IDs."
        }]
        write_rows(Path(path), rows)
        self.var_mapping_csv.set(path)
        self._log(f"[OK] mapping template saved: {path}\n")
        messagebox.showinfo("Mapping template", f"Saved:\n{path}")

    def open_training_db(self) -> None:
        path = self._training_db_path()
        if path.exists():
            open_path(path)
        else:
            messagebox.showinfo("Not found", f"Training DB does not exist yet:\n{path}")

    def import_training_data(self) -> None:
        if data_manager is None:
            messagebox.showerror("Missing module", "data_manager.py could not be imported.")
            return
        files = filedialog.askopenfilenames(
            title="Select prepared AF3 / PRODIGY / docking / experimental CSV files",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")]
        )
        if not files:
            return
        try:
            result = data_manager.append_training_csvs(list(files), self.var_training_db.get())
            self._log(f"[OK] training data updated: {result['training_db']} | added={result['added']} | total={result['total']}\n")
            self.refresh_training_preview()
            messagebox.showinfo("Import complete", f"Added {result['added']} rows. Total: {result['total']}")
        except Exception as e:
            messagebox.showerror("Import error", str(e))

    def parse_import_af3_folder(self) -> None:
        if external_parsers is None:
            messagebox.showerror("Missing module", "external_parsers.py could not be imported.")
            return
        folder = filedialog.askdirectory(title="Select AF3 output folder")
        if not folder:
            return
        try:
            db = self._training_db_path()
            parsed_csv = db.parent / "parsed_af3_latest.csv"
            mapping = self.var_mapping_csv.get().strip() or None
            result = external_parsers.parse_and_import_af3(folder, db, parsed_csv=parsed_csv, mapping_csv=mapping)
            pr, ap = result["parse"], result["append"]
            self._log(f"[OK] AF3 parsed: {pr['rows']} rows -> {pr['output_csv']}\n")
            self._log(f"[OK] AF3 imported: added={ap['added']} | total={ap['total']} | db={ap['training_db']}\n")
            self.refresh_training_preview()
            messagebox.showinfo("AF3 parse/import complete", f"Parsed {pr['rows']} rows.\nAdded {ap['added']} rows.\nTotal: {ap['total']}")
        except Exception as e:
            messagebox.showerror("AF3 parse/import error", str(e))

    def parse_import_prodigy(self) -> None:
        if external_parsers is None:
            messagebox.showerror("Missing module", "external_parsers.py could not be imported.")
            return
        # ask file first; user can cancel and choose folder
        path = filedialog.askopenfilename(
            title="Select PRODIGY txt/csv/log file, or cancel to choose a folder",
            filetypes=[("PRODIGY files", "*.txt *.csv *.out *.log"), ("All", "*.*")]
        )
        if not path:
            path = filedialog.askdirectory(title="Select PRODIGY output folder")
        if not path:
            return
        try:
            db = self._training_db_path()
            parsed_csv = db.parent / "parsed_prodigy_latest.csv"
            mapping = self.var_mapping_csv.get().strip() or None
            result = external_parsers.parse_and_import_prodigy(path, db, parsed_csv=parsed_csv, mapping_csv=mapping)
            pr, ap = result["parse"], result["append"]
            self._log(f"[OK] PRODIGY parsed: {pr['rows']} rows -> {pr['output_csv']}\n")
            self._log(f"[OK] PRODIGY imported: added={ap['added']} | total={ap['total']} | db={ap['training_db']}\n")
            self.refresh_training_preview()
            messagebox.showinfo("PRODIGY parse/import complete", f"Parsed {pr['rows']} rows.\nAdded {ap['added']} rows.\nTotal: {ap['total']}")
        except Exception as e:
            messagebox.showerror("PRODIGY parse/import error", str(e))

    def train_ml(self) -> None:
        if ml_trainer is None:
            messagebox.showerror("Missing module", "ml_trainer.py could not be imported.")
            return
        try:
            model_path = ml_trainer.train_from_csv(self.var_training_db.get(), self.var_models_dir.get(), label_col=self.var_ml_label.get())
            self.var_trained_model.set(str(model_path))
            self.update_model_status()
            self._log(f"[OK] user-data ranking model saved: {model_path}\n")
            messagebox.showinfo("ML training complete", f"Saved model:\n{model_path}")
        except Exception as e:
            messagebox.showerror("ML training error", str(e))

    # --------------------------- queue/UI updates ---------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.msg_q.get_nowait()
                tag = item[0]
                if tag == "log":
                    self._log(item[1])
                elif tag == "done":
                    _, rows, paths = item
                    self._show_results(rows)
                    self.last_output_dir = Path(paths.get("output_dir", "")) if paths.get("output_dir") else None
                    self.last_zip = Path(paths.get("zip", "")) if paths.get("zip") else None
                    self._set_buttons_running(False)
                    self._log("Run finished.\n")
                elif tag == "error":
                    self._set_buttons_running(False)
                    self._log("\n[ERROR] ERROR\n" + item[1] + "\n")
                    messagebox.showerror("Run error", item[1][-3000:])
        except queue.Empty:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        self.after(100, self._poll_queue)

    def _log(self, text: str) -> None:
        self.log_text.insert("end", text)
        self.log_text.see("end")

    def _show_results(self, rows: List[Dict[str, Any]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        topk = int(self.var_topk.get())
        for r in rows[:topk]:
            self.tree.insert("", "end", values=(
                r.get("rank", r.get("ml_rerank_rank", "")),
                f"{float(r.get('total_score', r.get('ml_blended_score', 0))):.4f}" if str(r.get("total_score", r.get("ml_blended_score", ""))) != "" else "",
                r.get("length", ""),
                r.get("valid", ""),
                r.get("sequence", ""),
            ))

    def _set_buttons_running(self, running: bool) -> None:
        self.config(cursor="watch" if running else "")
        try:
            self.apply_settings_button.configure(state="disabled" if running else "normal")
            self.run_engine_button.configure(state="disabled" if running or not self.settings_applied else "normal")
            self.repeat_run_button.configure(state="disabled" if running or self.last_run_config is None else "normal")
        except Exception:
            pass

    def open_output(self) -> None:
        target = self.last_output_dir or self._effective_outdir()
        if target.exists():
            open_path(target)
        else:
            messagebox.showinfo("Not found", f"No output folder found yet:\n{target}")

    def open_zip(self) -> None:
        if self.last_zip and self.last_zip.exists():
            open_path(self.last_zip)
        else:
            messagebox.showinfo("Not found", "No output ZIP found yet. Run the engine first.")


def main() -> None:
    app = PeptideDesktopGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
