from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import sys
import tempfile
import time
import json
import csv
import traceback
import threading
from datetime import datetime
from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.ui_scroll import VerticalPageScroller
from peptiforg_core.ui_theme import apply_pepforge_theme, fit_window, maximize_when_roomy
from peptiforg_core.startup_runtime import StartupTrace, mark_window_visible
from peptiforg_core.sandbox_runtime import configured_output
from peptiforg_core.output_bundle import create_result_bundle, write_bundle_manifest, build_bundle_zip, compact_sequence_label
from peptiforg_core.docking_followup_v1 import load_normalized_result_export, run_native_docking_followup
from peptiforg_core.docking_result_contract_v1 import combine_normalized_results
from peptiforg_core.native_mechanics_v2 import NativeMechanicsV2Config
from suite_gui.shared_native_result_panel import SharedNativeResultPanel

from pepforge_structure_tool.version import STRUCTURE_TOOL_VERSION

_STRUCTURE_API = None

def _structure_api():
    """Load RDKit-backed structure code only when a structure action needs it."""
    global _STRUCTURE_API
    if _STRUCTURE_API is None:
        from peptiforg_core import pymol_structure_builder as api
        _STRUCTURE_API = api
    return _STRUCTURE_API

def classify_tokens(sequence):
    return _structure_api().classify_tokens(sequence)

def export_modified_peptide_structure(*args, **kwargs):
    return _structure_api().export_modified_peptide_structure(*args, **kwargs)

def environment_report():
    return _structure_api().environment_report()

def supported_token_table():
    return _structure_api().supported_token_table()

def template_manifest():
    return _structure_api().template_manifest()

def audit_template_files(*args, **kwargs):
    return _structure_api().audit_template_files(*args, **kwargs)
from peptiforg_core.component_versions import (
    LOW_SPEC_VALIDATION_BRIDGE_VERSION as BRIDGE_VERSION,
    EXTERNAL_DOCKING_BRIDGE_VERSION as DOCKING_BRIDGE_VERSION,
    MD_PREP_BRIDGE_VERSION, EXTERNAL_MD_RESULT_IMPORT_BRIDGE_VERSION as MD_RESULT_IMPORT_BRIDGE_VERSION,
    PUBLICATION_REPORT_BUILDER_VERSION,
)

def export_low_spec_validation_bridge(*args, **kwargs):
    from peptiforg_core.low_spec_validation_bridge import export_low_spec_validation_bridge as func
    return func(*args, **kwargs)

def export_external_docking_runner_bridge(*args, **kwargs):
    from peptiforg_core.external_docking_runner_bridge import export_external_docking_runner_bridge as func
    return func(*args, **kwargs)

def export_all_atom_md_preparation_bridge(*args, **kwargs):
    from peptiforg_core.all_atom_md_preparation_bridge import export_all_atom_md_preparation_bridge as func
    return func(*args, **kwargs)

def export_external_md_result_import_bridge(*args, **kwargs):
    from peptiforg_core.external_md_result_import_bridge import export_external_md_result_import_bridge as func
    return func(*args, **kwargs)

def export_publication_validation_report(*args, **kwargs):
    from peptiforg_core.publication_validation_report_builder import export_publication_validation_report as func
    return func(*args, **kwargs)


CONDITION_PRESETS = {
    "Physiological aqueous": {"pH": "7.4", "temperature_C": "37", "ionic_strength_mM": "150", "environment": "Aqueous buffer"},
    "Neutral room temperature": {"pH": "7.0", "temperature_C": "25", "ionic_strength_mM": "100", "environment": "Aqueous buffer"},
    "Membrane-mimetic metadata": {"pH": "7.4", "temperature_C": "37", "ionic_strength_mM": "150", "environment": "Membrane-mimetic"},
    "Custom": None,
}

BUILD_PRESETS = {
    "Fast Top 5": {"num_confs": 5, "max_iters": 80, "num_threads": 2, "search_profile": "evidence_fast", "min_final_conformers": 5, "max_embedding_retries": 2},
    # Backward-compatible programmatic alias. It is intentionally omitted from
    # the visible combobox because Balanced is now the safer default.
    "Fast Top 5 (recommended)": {"num_confs": 5, "max_iters": 80, "num_threads": 2, "search_profile": "evidence_fast", "min_final_conformers": 5, "max_embedding_retries": 2},
    "Balanced Top 5": {"num_confs": 12, "max_iters": 200, "num_threads": 2, "search_profile": "evidence_balanced", "min_final_conformers": 5, "max_embedding_retries": 3},
    "Balanced Top 5 (recommended)": {"num_confs": 12, "max_iters": 200, "num_threads": 2, "search_profile": "evidence_balanced", "min_final_conformers": 5, "max_embedding_retries": 3},
    "Thorough Top 5": {"num_confs": 30, "max_iters": 500, "num_threads": 4, "search_profile": "evidence_thorough", "min_final_conformers": 5, "max_embedding_retries": 4},
}
BUILD_PRESET_DISPLAY_ORDER = ("Balanced Top 5 (recommended)", "Fast Top 5", "Thorough Top 5")


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))
        elif os.sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        messagebox.showwarning("Open folder", f"Could not open:\n{path}\n\n{exc}")


def _safe_write_csv(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return str(path)
    keys = []
    for row in rows:
        for k in row.keys():
            if k not in keys:
                keys.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _safe_write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _token_rows_for_bridge(sequence: str) -> list[dict]:
    rows = []
    for t in classify_tokens(sequence):
        rows.append({
            "position": t.position or "",
            "raw": t.raw,
            "token": t.token,
            "class": t.cls,
            "note": t.note,
            "warning": t.warning,
        })
    return rows


def export_gui_quick_bridge_package(
    sequence: str,
    output_dir: str | Path,
    name: str,
    bridge_kind: str,
    receptor_path: str = "",
    external_md_csv: str = "",
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float, float] = (22.0, 22.0, 22.0),
    exhaustiveness: int = 16,
    num_modes: int = 20,
    num_confs: int = 1,
) -> dict[str, str]:
    """GUI-safe bridge exporter that reuses the Build SDF/PDB/PML path."""
    out = Path(output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (name or "modified_peptide")).strip("_") or "modified_peptide"
    expected_paths = {
        "sdf": str(out / f"{safe}.sdf"),
        "pdb": str(out / f"{safe}.pdb"),
                "json": str(out / f"{safe}.json"),
        "report": str(out / f"{safe}_report.txt"),
        "pml": str(out / f"{safe}.pml"),
        "token_map": str(out / f"{safe}_token_map.csv"),
        "csv": str(out / f"{safe}_token_map.csv"),
    }
    # If Build SDF/PDB/PML was already run, reuse those files. This is the
    # important GUI fix for users whose Build works but Bridge appears to hang
    # or fail because it regenerates conformers unnecessarily.
    if all(Path(v).exists() for k, v in expected_paths.items() if k != "csv"):
        build_paths = expected_paths
    else:
        build_paths = export_modified_peptide_structure(sequence, out, safe)
    bridge_slug = "".join(ch if ch.isalnum() else "_" for ch in bridge_kind.lower()).strip("_")
    bridge_dir = out / "bridge_packages" / bridge_slug
    bridge_dir.mkdir(parents=True, exist_ok=True)
    token_rows = _token_rows_for_bridge(sequence)
    token_csv = Path(build_paths.get("token_map", out / f"{safe}_token_map.csv"))

    parameter_rows = []
    for r in token_rows:
        cls = str(r.get("class", ""))
        token = str(r.get("token", ""))
        needs = any(x in cls.lower() for x in ["label", "chemical", "cap", "linker", "d-amino", "modified"]) or token.startswith("d") or token in {"Pal", "Myr", "FITC", "FAM", "TAMRA", "Biotin", "DOTA", "AEEA", "Ahx", "PEG"}
        parameter_rows.append({
            "token": token,
            "class": cls,
            "parameter_review_needed": "yes" if needs else "usually no",
            "reason": "modified/linker/label/cap token or D-form residue" if needs else "standard amino-acid-like unit",
            "action": "verify bonding, charge, and force-field parameters before external MD/docking claims" if needs else "inspect generated geometry",
        })
    parameter_csv = _safe_write_csv(bridge_dir / "parameter_requirements.csv", parameter_rows)

    settings = {
        "sequence": sequence,
        "name": safe,
        "bridge_kind": bridge_kind,
        "mode": "GUI quick hand-off package",
        "meaning": "Bridge exports hand-off templates for external tools. It does not run Vina, Gnina, Smina, PRODIGY, GROMACS, OpenMM, or AMBER inside Pepforge.",
        "receptor_path": receptor_path or "not set",
        "external_md_csv": external_md_csv or "not set",
        "center": center,
        "size": size,
        "exhaustiveness": int(exhaustiveness),
        "num_modes": int(num_modes),
        "num_confs_requested": int(num_confs),
        "base_outputs": build_paths,
        "token_map": str(token_csv),
    }
    settings_json = bridge_dir / "bridge_settings.json"
    settings_json.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = f"""Pepforge PyMOL Structure Builder - {bridge_kind}
{'=' * (42 + len(bridge_kind))}

Input sequence: {sequence}
Output name: {safe}

Bridge meaning
--------------
Bridge is a hand-off/export step. Pepforge builds a modified-peptide starting structure and writes templates/checklists so the result can be inspected in PyMOL or transferred to external docking/MD/affinity workflows.

Important boundary
------------------
This package does not execute or replace external tools. Vina/Smina/Gnina/PRODIGY/GROMACS/OpenMM/AMBER must still be run outside Pepforge when real docking/MD/affinity data are required.

What was written
----------------
- SDF/PDB/PML/metadata/report using the same build path as Build SDF/PDB/PML
- token_map.csv for token interpretation
- parameter_requirements.csv for modified-token review
- bridge_settings.json for user-selected receptor/box/MD settings

Recommended order
-----------------
1. Open the PML/PDB/SDF in PyMOL and visually check Pal/linker/label/NH2 geometry.
2. Open token_map.csv and confirm every token is classified correctly.
3. Open parameter_requirements.csv before docking/MD claims.
4. For docking, set receptor and docking box manually, then use the config templates.
5. For MD, prepare force-field parameters externally before claiming all-atom MD validity.
"""
    summary_md = _safe_write_text(bridge_dir / f"{safe}_{bridge_slug}_summary.md", summary)
    howto_kr = _safe_write_text(bridge_dir / "HOW_TO_USE_THIS_BRIDGE_KR.txt", f"""Bridge 사용법 요약
===================

이 버튼은 외부 계산을 직접 끝내는 버튼이 아니라, Build SDF/PDB/PML에서 만든 구조를 기준으로 외부 docking/MD/affinity 분석으로 넘길 준비 파일을 만드는 버튼이다.

현재 Bridge 종류: {bridge_kind}
입력 서열: {sequence}

확인 순서:
1. {safe}_token_map.csv 확인
2. parameter_requirements.csv 확인
3. PyMOL에서 PDB/SDF/PML 구조 확인
4. docking이면 receptor와 box center/size를 사용자가 직접 지정
5. MD면 Pal, label, linker, D-amino acid, NH2의 parameter/charge를 외부 도구에서 검토

이 패키지는 외부 Vina/Gnina/Smina/PRODIGY/GROMACS/OpenMM/AMBER를 대신 실행하지 않는다.
""")
    paths = {
        "bridge_dir": str(bridge_dir),
        "summary_md": summary_md,
        "how_to_use_kr": howto_kr,
        "bridge_settings_json": str(settings_json),
        "parameter_requirements_csv": parameter_csv,
    }
    for k, v in build_paths.items():
        paths[f"base_{k}"] = v

    if bridge_slug in {"docking_bridge", "publication_report"}:
        docking_config = _safe_write_text(bridge_dir / "vina_like_config_template.txt", f"""# External docking template generated by Pepforge GUI Bridge
# Convert receptor/ligand to PDBQT externally before running Vina/Smina/Gnina.
receptor = receptor.pdbqt
ligand = ligand.pdbqt
center_x = {center[0]}
center_y = {center[1]}
center_z = {center[2]}
size_x = {size[0]}
size_y = {size[1]}
size_z = {size[2]}
exhaustiveness = {int(exhaustiveness)}
num_modes = {int(num_modes)}
""")
        import_schema = _safe_write_csv(bridge_dir / "external_docking_scores_import_schema.csv", [
            {"column": "pose_id", "required": "yes", "example": "pose_001"},
            {"column": "score_kcal_mol", "required": "yes", "example": "-7.5"},
            {"column": "rmsd_lb", "required": "optional", "example": "0.0"},
            {"column": "rmsd_ub", "required": "optional", "example": "1.5"},
            {"column": "source_engine", "required": "optional", "example": "vina/smina/gnina"},
        ])
        paths.update({"vina_like_config_template": docking_config, "external_docking_scores_import_schema": import_schema})

    if bridge_slug in {"md_prep_bridge", "md_result_import", "publication_report"}:
        md_check = _safe_write_csv(bridge_dir / "md_parameterization_checklist.csv", [
            {"item": "modified labels/caps", "status": "review required", "note": "Pal/FITC/FAM/TAMRA/Biotin/DOTA may require force-field parameters"},
            {"item": "linkers", "status": "review required", "note": "Ahx/AEEA/PEG/G4S should be checked as amino-acid-like linker units"},
            {"item": "D-amino acids", "status": "review required", "note": "Confirm chirality and residue naming before MD"},
            {"item": "C-terminal NH2", "status": "review required", "note": "Confirm terminal amide charge/state"},
        ])
        md_import = _safe_write_csv(bridge_dir / "external_md_result_import_schema.csv", [
            {"column": "frame", "required": "yes", "example": "0"},
            {"column": "time_ns", "required": "recommended", "example": "0.0"},
            {"column": "rmsd_nm", "required": "optional", "example": "0.25"},
            {"column": "rmsf_nm", "required": "optional", "example": "0.08"},
            {"column": "energy_kj_mol", "required": "optional", "example": "-1200"},
            {"column": "contact_count", "required": "optional", "example": "14"},
        ])
        paths.update({"md_parameterization_checklist": md_check, "external_md_result_import_schema": md_import})

    if bridge_slug == "publication_report":
        pub = _safe_write_text(bridge_dir / "publication_validation_claim_guard.md", f"""# Publication validation claim guard

Input: `{sequence}`

Allowed wording: generated starting structure, PyMOL-inspected model, external docking/MD-ready hand-off package.

Do not claim: final Kd, true nM binder, full all-atom MD validation, or experimental binding unless external validated data are imported and reviewed.
""")
        paths["publication_validation_claim_guard"] = pub
    return paths


class PyMOLStructureBuilderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pepforge Peptide Structure & Docking Studio")
        set_pepforge_icon(self)
        apply_pepforge_theme(self)
        fit_window(self, preferred_width=1820, preferred_height=1000, minimum_width=1260, minimum_height=780)
        self.after(80, lambda: maximize_when_roomy(self, min_width=1600, min_height=900))
        self._startup_trace = StartupTrace("structure_builder", Path.cwd() / "workspace" / "pymol" / "logs")
        self.output_dir = tk.StringVar(value="")
        self.sequence_var = tk.StringVar(value="")
        self.name_var = tk.StringVar(value="")
        self.condition_preset = tk.StringVar(value="Physiological aqueous")
        self.condition_ph = tk.StringVar(value="7.4")
        self.condition_temperature = tk.StringVar(value="37")
        self.condition_ionic_strength = tk.StringVar(value="150")
        self.condition_environment = tk.StringVar(value="Aqueous buffer")
        self.build_preset = tk.StringVar(value="Balanced Top 5 (recommended)")
        self._build_process = None
        self._build_job_dir: Path | None = None
        self._build_started_at = 0.0
        self.structure_generation_backend_ready = False
        self._active_result_bundle: Path | None = None
        self._active_result_key: tuple[str, str] | None = None
        # User-editable bridge settings. Bridge buttons are not magic one-click
        # final MD/docking; they export packages according to these values.
        self.bridge_receptor_path = tk.StringVar(value="")
        self.bridge_md_result_csv = tk.StringVar(value="")
        self.bridge_conformers = tk.IntVar(value=5)
        self.bridge_exhaustiveness = tk.IntVar(value=16)
        self.bridge_num_modes = tk.IntVar(value=20)
        self.bridge_quick_mode = tk.BooleanVar(value=True)
        self.bridge_center_x = tk.DoubleVar(value=0.0)
        self.bridge_center_y = tk.DoubleVar(value=0.0)
        self.bridge_center_z = tk.DoubleVar(value=0.0)
        self.bridge_size_x = tk.DoubleVar(value=22.0)
        self.bridge_size_y = tk.DoubleVar(value=22.0)
        self.bridge_size_z = tk.DoubleVar(value=22.0)
        # V5 one-click PSB -> docking -> DockBench -> PyMOL -> optional MD.
        self.v5_receptor_source = tk.StringVar(value="file")
        self.v5_receptor_sequence = tk.StringVar(value="")
        self.v5_binding_mode = tk.StringVar(value="blind")
        self.v5_binding_residues = tk.StringVar(value="")
        self.v5_docking_preset = tk.StringVar(value="standard")
        self.v5_docking_backend = tk.StringVar(value="native")
        self.v5_execution_mode = tk.StringVar(value="offline")
        self.v5_resource_root = tk.StringVar(value="")
        self.v5_initial_conformers = tk.IntVar(value=100)
        self.v5_run_md = tk.BooleanVar(value=False)
        self.v5_run_native_followup = tk.BooleanVar(value=True)
        self.v5_native_mechanics_steps = tk.IntVar(value=400)
        self.v5_md_production_ns = tk.DoubleVar(value=1.0)
        self.v5_md_replicates = tk.IntVar(value=3)
        self._v5_pipeline_thread = None
        self._v5_pipeline_result = None
        self._v5_pipeline_error = None
        self._v5_pending_after_build = False
        self._build()
        mark_window_visible(self, self._startup_trace)

    def _ensure_structure_generation_backend(self):
        if not self.structure_generation_backend_ready:
            self._startup_trace.mark("structure_generation_backend_load_start")
        api = _structure_api()
        if not self.structure_generation_backend_ready:
            self.structure_generation_backend_ready = True
            self._startup_trace.mark("structure_generation_backend_ready", backend="RDKit/PSB")
            self._startup_trace.write()
        return api

    def _default_output_dir(self) -> Path:
        return configured_output(Path.cwd() / "outputs" / "pymol_structure_builder", "pymol")

    def _effective_output_dir(self) -> Path:
        raw = str(self.output_dir.get() or "").strip()
        if raw:
            return Path(raw).expanduser()
        outdir = self._default_output_dir()
        self.output_dir.set(str(outdir))
        return outdir

    def _effective_output_name(self) -> str:
        name = str(self.name_var.get() or "").strip()
        if name:
            return name
        seq = str(self.sequence_var.get() or "").strip()
        if seq:
            return compact_sequence_label(seq)
        return "PSB"

    def _result_bundle(self, sequence: str, name: str, *, force_new: bool = False) -> Path:
        key = (str(sequence or "").strip(), str(name or "").strip())
        if not force_new and self._active_result_bundle is not None and self._active_result_key == key and self._active_result_bundle.exists():
            return self._active_result_bundle
        bundle = create_result_bundle(
            self._effective_output_dir(), name=name or None, sequence=sequence or None, tool="PSB"
        )
        self._active_result_bundle = bundle
        self._active_result_key = key
        return bundle

    def _sync_sequence_var_from_text(self, _event=None) -> None:
        widget = getattr(self, "sequence_text", None)
        if widget is None:
            return
        try:
            value = widget.get("1.0", "end-1c").strip()
            if value != str(self.sequence_var.get() or ""):
                self.sequence_var.set(value)
        except Exception:
            pass

    def _sync_sequence_text_from_var(self, *_args) -> None:
        widget = getattr(self, "sequence_text", None)
        if widget is None:
            return
        try:
            value = str(self.sequence_var.get() or "")
            current = widget.get("1.0", "end-1c")
            if current != value:
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
        except Exception:
            pass

    def _require_sequence(self) -> str | None:
        self._sync_sequence_var_from_text()
        seq = str(self.sequence_var.get() or "").strip()
        if not seq:
            messagebox.showwarning("Input required", "Enter a peptide sequence first.")
            return None
        return seq

    def _build(self):
        # One vertically scrollable Studio page: PSB and docking are a single
        # primary workflow.  This follows the SPPS Planner's large-window /
        # work-item approach and prevents lower controls from disappearing.
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)

        # R4: one vertical-only analysis page. The shared helper coalesces
        # high-resolution wheel events, clamps at page edges, and debounces
        # scrollregion updates so the last part of long PSB pages does not
        # stutter. The inner frame is always viewport-width; child widgets can
        # never push the outer canvas wider (prevents the Windows stretching bug).
        self._studio_scroller = VerticalPageScroller(self, shell, background="#F3F6FA", padding=14, wheel_step=2)
        self._studio_scroller.grid(row=0, column=0, sticky="nsew")
        self._studio_scroller.scrollbar.grid(row=0, column=1, sticky="ns")
        root = self._studio_scroller.inner
        root.columnconfigure(0, weight=1)
        self._studio_canvas = self._studio_scroller.canvas
        self._studio_page = root
        self._studio_scrollbar = self._studio_scroller.scrollbar
        self._studio_page_window = self._studio_scroller.window

        ttk.Label(root, text="Peptide Structure & Docking Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text=(
                f"Pepforge Structure & Docking Studio v{STRUCTURE_TOOL_VERSION}. "
                "Build canonical or modified peptide conformers, prepare a receptor, run Pepforge Native docking, and review shared native results in one window. "
                "Generated structures and docking scores remain computational evidence, not experimental structures or affinity measurements."
            ),
            wraplength=1200,
        ).pack(anchor="w", pady=(4, 12))

        input_box = ttk.LabelFrame(root, text="Input", style="Input.TLabelframe")
        input_box.pack(fill="x")
        ttk.Label(input_box, text="Peptide sequence").grid(row=0, column=0, sticky="nw", padx=8, pady=8)
        # Keep the sequence field visibly large even before focus/click.  A
        # multi-line entry is easier for long/modified constructs than the old
        # narrow single-line widget.
        seq_frame = ttk.Frame(input_box)
        seq_frame.grid(row=0, column=1, columnspan=2, sticky="nsew", padx=8, pady=8)
        self.sequence_text = tk.Text(seq_frame, height=3, wrap="none", font=("Consolas", 11), undo=True)
        seq_x = ttk.Scrollbar(seq_frame, orient="horizontal", command=self.sequence_text.xview)
        self.sequence_text.configure(xscrollcommand=seq_x.set)
        self.sequence_text.pack(fill="x", expand=True)
        seq_x.pack(fill="x")
        self.sequence_text.insert("1.0", str(self.sequence_var.get() or ""))
        self.sequence_text.bind("<KeyRelease>", self._sync_sequence_var_from_text, add="+")
        self.sequence_text.bind("<FocusOut>", self._sync_sequence_var_from_text, add="+")
        self.sequence_var.trace_add("write", self._sync_sequence_text_from_var)
        ttk.Label(input_box, text="Output name").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(input_box, textvariable=self.name_var, width=36).grid(row=1, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(input_box, text="Output folder").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        output_row = ttk.Frame(input_box)
        output_row.grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=8)
        ttk.Entry(output_row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(output_row, text="Browse", command=self._browse).pack(side="left", padx=(8, 0))
        ttk.Label(input_box, text="Condition preset").grid(row=3, column=0, sticky="w", padx=8, pady=(8, 3))
        condition_preset_combo = ttk.Combobox(
            input_box, textvariable=self.condition_preset, state="readonly",
            values=tuple(CONDITION_PRESETS), width=34,
        )
        condition_preset_combo.grid(row=3, column=1, sticky="w", padx=8, pady=(8, 3))
        condition_preset_combo.bind("<<ComboboxSelected>>", self._apply_condition_preset)
        ttk.Label(
            input_box,
            text="Conditions are recorded for interpretation/export; RDKit does not simulate constant-pH solvent physics.",
            style="Sub.TLabel",
        ).grid(row=3, column=2, sticky="w", padx=8, pady=(8, 3))
        ttk.Label(input_box, text="Condition values").grid(row=4, column=0, sticky="w", padx=8, pady=5)
        condition_row = ttk.Frame(input_box)
        condition_row.grid(row=4, column=1, columnspan=2, sticky="ew", padx=8, pady=5)
        ttk.Label(condition_row, text="pH").pack(side="left")
        ttk.Entry(condition_row, textvariable=self.condition_ph, width=8).pack(side="left", padx=(4, 12))
        ttk.Label(condition_row, text="Temperature °C").pack(side="left")
        ttk.Entry(condition_row, textvariable=self.condition_temperature, width=8).pack(side="left", padx=(4, 12))
        ttk.Label(condition_row, text="Ionic strength mM").pack(side="left")
        ttk.Entry(condition_row, textvariable=self.condition_ionic_strength, width=9).pack(side="left", padx=(4, 12))
        ttk.Combobox(condition_row, textvariable=self.condition_environment, state="readonly", width=24,
                     values=("Aqueous / unspecified", "Aqueous buffer", "Membrane-mimetic", "Organic / mixed solvent")).pack(side="left")
        ttk.Label(input_box, text="Build preset").grid(row=5, column=0, sticky="w", padx=8, pady=(3, 8))
        ttk.Combobox(
            input_box, textvariable=self.build_preset, state="readonly",
            values=BUILD_PRESET_DISPLAY_ORDER, width=34,
        ).grid(row=5, column=1, sticky="w", padx=8, pady=(3, 8))
        ttk.Label(
            input_box,
            text="Balanced is recommended because it samples evidence-prioritized basins and guided variants; Fast remains available for quick screening, while Thorough spends more sampling time.",
            style="Sub.TLabel",
        ).grid(row=5, column=2, sticky="w", padx=8, pady=(3, 8))
        input_box.columnconfigure(1, weight=1)

        scope_box = ttk.LabelFrame(root, text="Evidence-aware peptide-only modelling", style="Card.TLabelframe")
        scope_box.pack(fill="x", pady=(8, 0))
        ttk.Label(
            scope_box,
            text=("PDE structure intent, when supplied, guides Top-5 selection inside the requested geometry basin; otherwise PSB ranks clash-free geometry without forcing one-per-family diversity. "
                  "Terminal chemistry, chirality and modifications are preserved. Results are plausible starting conformers—not a claimed in-vivo structure."),
            wraplength=1180,
        ).pack(anchor="w", padx=8, pady=7)

        actions = ttk.LabelFrame(root, text="Build workflow", style="Card.TLabelframe")
        actions.pack(fill="x", pady=8)
        self.progress_var = tk.StringVar(value="Ready")
        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100, value=0, style="PepforgeGreen.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, columnspan=3, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(actions, textvariable=self.progress_var).grid(row=0, column=3, sticky="w", padx=6)

        self.action_buttons = []
        button_specs = [
            ("Analyze", self.analyze),
            ("Build Structure", self.export),
            ("Open Token Map", self.open_token_map),
            ("Open Output", lambda: _open_path(self._active_result_bundle or self._effective_output_dir())),
        ]
        for idx, (label, cmd) in enumerate(button_specs):
            btn = ttk.Button(actions, text=label, command=cmd, width=18, style="TButton")
            btn.grid(row=1, column=idx, padx=4, pady=4, sticky="ew")
            self.action_buttons.append(btn)
        for col in range(4):
            actions.columnconfigure(col, weight=1)
        # V4 scope stops at static structure generation/review. Actual MD and
        # trajectory analysis belong to the V5 simulation workflow.
        ttk.Button(actions, text="Analyze Structures", command=self.analyze_structure_files, width=18).grid(row=2, column=0, columnspan=2, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="Compare Structures", command=self.compare_structure_files, width=18).grid(row=2, column=2, columnspan=2, padx=4, pady=4, sticky="ew")

        v5_box = ttk.LabelFrame(root, text="Integrated Docking & Simulation", style="Card.TLabelframe")
        v5_box.pack(fill="x", pady=(0, 8))
        ttk.Label(
            v5_box,
            text="PSB and native docking are unified here. The legacy Docking Workbench is retained only as an advanced compatibility/review tool.",
            style="Sub.TLabel", wraplength=1450,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(6, 4))
        ttk.Label(v5_box, text="Receptor source").grid(row=1, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(v5_box, textvariable=self.v5_receptor_source, state="readonly", values=("file","ESMFold"), width=12).grid(row=1, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="AF3: advanced CLI adapter").grid(row=1, column=2, sticky="e", padx=6, pady=5)
        ttk.Label(v5_box, text="Receptor PDB/mmCIF").grid(row=2, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(v5_box, textvariable=self.bridge_receptor_path).grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        ttk.Button(v5_box, text="Browse", command=self._browse_receptor).grid(row=2, column=2, padx=6, pady=5)
        ttk.Label(v5_box, text="Receptor sequence").grid(row=3, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(v5_box, textvariable=self.v5_receptor_sequence).grid(row=3, column=1, columnspan=2, sticky="ew", padx=6, pady=5)
        ttk.Label(v5_box, text="Binding").grid(row=4, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(v5_box, textvariable=self.v5_binding_mode, state="readonly", values=("blind","hotspot","manual"), width=12).grid(row=4, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Residues (e.g. A:10;A:24)").grid(row=4, column=1, sticky="e", padx=(140,6), pady=5)
        ttk.Entry(v5_box, textvariable=self.v5_binding_residues, width=26).grid(row=4, column=2, sticky="ew", padx=6, pady=5)
        ttk.Label(v5_box, text="Docking backend").grid(row=5, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(v5_box, textvariable=self.v5_docking_backend, state="readonly", values=("native","haddock3"), width=12).grid(row=5, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Native = Pepforge-owned experimental search; HADDOCK3 = optional external validation.", style="Sub.TLabel").grid(row=5, column=2, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Docking preset").grid(row=6, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(v5_box, textvariable=self.v5_docking_preset, state="readonly", values=("fast","standard","deep"), width=12).grid(row=6, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Peptide sampling N").grid(row=6, column=1, sticky="e", padx=(120,6), pady=5)
        ttk.Entry(v5_box, textvariable=self.v5_initial_conformers, width=7).grid(row=6, column=2, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Execution").grid(row=7, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(v5_box, textvariable=self.v5_execution_mode, state="readonly", values=("offline","auto","online_enhanced"), width=16).grid(row=7, column=1, sticky="w", padx=6, pady=5)
        ttk.Label(v5_box, text="Offline blocks optional network fetches; Pepforge native docking stays available.", style="Sub.TLabel").grid(row=7, column=2, sticky="w", padx=6, pady=5)
        ttk.Checkbutton(v5_box, text="Run Pepforge Native Mechanics + Trajectory after native docking", variable=self.v5_run_native_followup).grid(row=8, column=0, columnspan=2, sticky="w", padx=6, pady=5)
        native_row = ttk.Frame(v5_box)
        native_row.grid(row=8, column=2, sticky="e", padx=6, pady=5)
        ttk.Label(native_row, text="Mechanics steps").pack(side="left")
        ttk.Spinbox(native_row, from_=20, to=20000, textvariable=self.v5_native_mechanics_steps, width=8).pack(side="left", padx=(5,0))
        ttk.Checkbutton(v5_box, text="Optional OpenMM MD backend", variable=self.v5_run_md).grid(row=9, column=0, sticky="w", padx=6, pady=5)
        mdrow=ttk.Frame(v5_box); mdrow.grid(row=9, column=1, columnspan=2, sticky="w", padx=6, pady=5)
        ttk.Label(mdrow, text="production ns").pack(side="left"); ttk.Entry(mdrow, textvariable=self.v5_md_production_ns, width=6).pack(side="left", padx=(4,12))
        ttk.Label(mdrow, text="replicates").pack(side="left"); ttk.Entry(mdrow, textvariable=self.v5_md_replicates, width=4).pack(side="left", padx=(4,8))
        self.v5_run_button = ttk.Button(v5_box, text="BUILD + DOCK + ANALYZE", command=self.run_v5_full_simulation, style="Accent.TButton")
        self.v5_run_button.grid(row=10, column=0, columnspan=3, sticky="ew", padx=6, pady=(8,10))
        v5_box.columnconfigure(1, weight=1); v5_box.columnconfigure(2, weight=1)

        # Results are normal stacked sections, not a PanedWindow inside a
        # scrolling Canvas.  A resizable paned container inside another scrolling
        # geometry manager created a width/height feedback loop on Windows and
        # was the remaining cause of the reported "spaghetti" stretching.
        results_stack = ttk.Frame(root)
        results_stack.pack(fill="x", pady=(0, 8))

        token_frame = ttk.LabelFrame(results_stack, text="Chemistry interpretation", style="Card.TLabelframe")
        token_frame.pack(fill="x", pady=(0, 8))
        token_frame.columnconfigure(0, weight=1)
        token_frame.rowconfigure(0, weight=1)
        cols = ("position", "raw", "token", "class", "note", "warning")
        self.tree = ttk.Treeview(token_frame, columns=cols, show="headings", height=11)
        widths = {"position": 80, "raw": 130, "token": 180, "class": 180, "note": 420, "warning": 420}
        for c in cols:
            self.tree.heading(c, text=c)
            # Keep the page width stable.  This table owns any extra horizontal
            # width through its own scrollbar instead of pushing the outer page.
            self.tree.column(c, width=widths.get(c, 160), minwidth=60, stretch=False)
        tree_y = ttk.Scrollbar(token_frame, orient="vertical", command=self.tree.yview)
        tree_x = ttk.Scrollbar(token_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_y.grid(row=0, column=1, sticky="ns")
        tree_x.grid(row=1, column=0, sticky="ew")

        note_frame = ttk.LabelFrame(results_stack, text="Top-five ensemble and evidence", style="Card.TLabelframe")
        note_frame.pack(fill="x", pady=(0, 8))
        note_frame.columnconfigure(0, weight=1)
        note_frame.rowconfigure(0, weight=1)
        self.note = tk.Text(note_frame, height=10, wrap="word")
        note_y = ttk.Scrollbar(note_frame, orient="vertical", command=self.note.yview)
        self.note.configure(yscrollcommand=note_y.set)
        self.note.grid(row=0, column=0, sticky="nsew")
        note_y.grid(row=0, column=1, sticky="ns")
        self.note.insert("1.0", "Enter a peptide sequence, review the chemistry interpretation, then build the evidence-aware top five structures.")

        unified_frame = ttk.LabelFrame(results_stack, text="Unified Native Results", style="Card.TLabelframe")
        unified_frame.pack(fill="x")
        self.shared_native_result_panel = SharedNativeResultPanel(
            unified_frame,
            open_path_callback=lambda p: _open_path(Path(p)),
            rerun_followup_callback=self._rerun_selected_native_followup,
            title="Structure & Docking Shared Native Result Viewer",
        )
        self.shared_native_result_panel.pack(fill="both", expand=False)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=str(self._effective_output_dir().parent if str(self.output_dir.get()).strip() else self._default_output_dir().parent))
        if d:
            self.output_dir.set(d)

    def _environment_conditions(self) -> dict:
        def optional_float(value: str, label: str, minimum: float, maximum: float):
            text = str(value or "").strip()
            if not text:
                return None
            number = float(text)
            if not minimum <= number <= maximum:
                raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}.")
            return number
        return {
            "pH": optional_float(self.condition_ph.get(), "pH", 0.0, 14.0),
            "temperature_C": optional_float(self.condition_temperature.get(), "Temperature", -20.0, 120.0),
            "ionic_strength_mM": optional_float(self.condition_ionic_strength.get(), "Ionic strength", 0.0, 5000.0),
            "environment": str(self.condition_environment.get() or "Aqueous / unspecified"),
        }

    def _apply_condition_preset(self, _event=None):
        values = CONDITION_PRESETS.get(str(self.condition_preset.get()))
        if values is None:
            return
        self.condition_ph.set(values["pH"])
        self.condition_temperature.set(values["temperature_C"])
        self.condition_ionic_strength.set(values["ionic_strength_mM"])
        self.condition_environment.set(values["environment"])

    def _build_settings(self) -> dict:
        return dict(BUILD_PRESETS.get(
            str(self.build_preset.get()),
            BUILD_PRESETS["Balanced Top 5 (recommended)"],
        ))

    def _worker_command(self, request_path: Path) -> list[str]:
        root = Path(__file__).resolve().parents[1]
        if getattr(sys, "frozen", False):
            return [sys.executable, "--structure-worker", str(request_path)]
        return [sys.executable, str(root / "main_launcher.py"), "--structure-worker", str(request_path)]

    def _start_structure_worker(self, sequence: str, name: str, conditions: dict) -> None:
        settings = self._build_settings()
        if self._v5_pending_after_build:
            # V5 full simulation deliberately samples a larger peptide ensemble
            # before retaining the physics/evidence-ranked Top 5.  The value is
            # user-editable because cost grows rapidly with peptide size.
            requested_n = max(5, min(2000, int(self.v5_initial_conformers.get())))
            settings["num_confs"] = requested_n
            settings["min_final_conformers"] = 5
            settings["search_profile"] = "evidence_thorough" if requested_n >= 50 else "evidence_balanced"
            settings["max_embedding_retries"] = max(int(settings.get("max_embedding_retries", 3)), 4)
        job_dir = Path(tempfile.mkdtemp(prefix="pepforge_psb_job_"))
        request_path = job_dir / "request.json"
        result_path = job_dir / "result.json"
        log_path = job_dir / "worker.log"
        request = {
            "sequence": sequence,
            "name": name,
            "output_dir": str(self._result_bundle(sequence, name, force_new=True)),
            "environment_conditions": conditions,
            "result_path": str(result_path),
            **settings,
        }
        request_path.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
        log_handle = log_path.open("w", encoding="utf-8")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                self._worker_command(request_path),
                cwd=str(Path(__file__).resolve().parents[1]),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        except Exception:
            log_handle.close()
            raise
        self._build_process = process
        self._build_log_handle = log_handle
        self._build_job_dir = job_dir
        self._build_started_at = time.monotonic()
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_var.set(f"Building in isolated worker · {self.build_preset.get()}")
        for button in self.action_buttons:
            button.configure(state="disabled")
        self.after(150, self._poll_structure_worker)

    def _poll_structure_worker(self) -> None:
        process = self._build_process
        if process is None:
            return
        return_code = process.poll()
        if return_code is None:
            elapsed = int(time.monotonic() - self._build_started_at)
            self.progress_var.set(f"Building in isolated worker · {elapsed}s elapsed")
            self.after(250, self._poll_structure_worker)
            return

        self.progress.stop()
        self.progress.configure(mode="determinate")
        log_handle = getattr(self, "_build_log_handle", None)
        if log_handle is not None:
            log_handle.close()
        job_dir = self._build_job_dir
        self._build_process = None
        result_path = job_dir / "result.json" if job_dir else None
        try:
            if result_path is None or not result_path.exists():
                raise RuntimeError(f"Structure worker stopped with exit code {return_code} before writing a result. Worker log: {job_dir / 'worker.log' if job_dir else 'unavailable'}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if not result.get("ok"):
                raise RuntimeError(f"{result.get('error_type', 'BuildError')}: {result.get('error', 'unknown structure-build failure')}")
            paths = dict(result.get("paths") or {})
            self._render_export_result(paths)
            if self._active_result_bundle and self._active_result_bundle.exists():
                zip_path = build_bundle_zip(self._active_result_bundle, filename="PSB_Result_Package.zip")
                write_bundle_manifest(self._active_result_bundle, tool="PSB", name=self._effective_output_name(), sequence=self.sequence_var.get(), artifacts={**paths, "zip": zip_path})
                self.note.insert("end", f"\nResult bundle ZIP: {zip_path}\n")
            self._set_done("Top-five ensemble complete")
            if self._v5_pending_after_build:
                self._v5_pending_after_build = False
                meta_path = paths.get("json") or paths.get("meta_path")
                if not meta_path:
                    raise RuntimeError("PSB build completed but metadata JSON was not returned for the V5 pipeline.")
                self.after(50, lambda p=meta_path: self._start_v5_pipeline(p))
            else:
                messagebox.showinfo("Export complete", "The ranked top five structures plus evidence report, ensemble, family CSV, torsion CSV, JSON and PyMOL files were exported.")
        except Exception as exc:
            diag = self._write_diagnostics("build_sdf_pdb_pml", exc)
            self.note.insert("end", "\nStructure worker diagnostic written:\n")
            for key, path in diag.items():
                self.note.insert("end", f"- {key}: {path}\n")
            if job_dir:
                self.note.insert("end", f"- worker_log: {job_dir / 'worker.log'}\n")
            self._set_failed("Build failed; PSB remains open")
            messagebox.showerror("Export failed", "The isolated structure build failed, but PSB remains open and diagnostic files were written.\n\n" + str(exc))

    def _render_export_result(self, paths: dict[str, str]) -> None:
        self.note.insert("end", "\nExported files:\n")
        for key, path in paths.items():
            self.note.insert("end", f"- {key}: {path}\n")
        meta = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
        ca = meta.get("conformation_analysis") or {}
        he = meta.get("canonical_L_helix_evidence") or {}
        seq_ev = meta.get("sequence_conformation_evidence") or {}
        conditions = meta.get("environment_conditions") or {}
        conf = meta.get("conformer_summary") or {}
        self.note.insert("end", "\nConformational ensemble analysis:\n")
        self.note.insert("end", f"- sampled family counts: {ca.get('family_counts', {})}\n")
        self.note.insert("end", f"- search workload: {conf.get('requested_conformers')} conformers, {conf.get('max_optimization_iterations')} max iterations, {conf.get('worker_threads')} threads\n")
        plan = meta.get("evidence_guided_family_plan") or {}
        self.note.insert("end", f"- build preset profile: {plan.get('profile')}\n")
        self.note.insert("end", f"- evidence-guided family priority: {plan.get('family_priority', [])}\n")
        self.note.insert("end", f"- family evidence identifiers: {plan.get('family_evidence', {})}\n")
        self.note.insert("end", f"- adaptive Top-5 retries: {conf.get('adaptive_embedding_attempts', [])}\n")
        audit = ca.get("top5_diversity_audit") or {}
        pfee_sel = ca.get("pfee_representative_selection") or {}
        pool = ca.get("pfee_candidate_pool") or {}
        self.note.insert("end", f"- PFEE candidate pool: usable={pool.get('usable_candidates')} / total={pool.get('total_candidates')} | rejected={pool.get('rejected_candidates')}\n")
        self.note.insert("end", f"- PFEE representative selection: {pfee_sel.get('status', 'unavailable')} | threshold={pfee_sel.get('minimum_rmsd_A')} Å | observed min={pfee_sel.get('minimum_observed_pairwise_rmsd_A')} Å | fallback={pfee_sel.get('fallback_count')}\n")
        self.note.insert("end", f"- Top-5 post-selection RMSD audit: {audit.get('status', 'unavailable')} | unique families={audit.get('unique_family_count')} | min pairwise RMSD={audit.get('minimum_pairwise_rmsd_A')} Å\n")
        self.note.insert("end", f"- canonical-L seed status: {conf.get('canonical_seed_status', 'unavailable')} | applied={conf.get('applied_backbone_seed_count', 0)} | labels={conf.get('applied_backbone_seed_labels', [])}\n")
        self.note.insert("end", f"- requested evidence-guided canonical seed families: {conf.get('requested_canonical_seed_labels', [])}; variants/preferred={conf.get('guided_seed_variants_per_preferred', 0)}\n")
        self.note.insert("end", "- ranked top five:\n")
        for row in ca.get("top_conformers", []) or []:
            self.note.insert("end", f"  {row.get('rank')}. {row.get('family')} | role={row.get('candidate_role')} | support={row.get('sequence_support')} | energy={row.get('energy')}\n")
        self.note.insert("end", f"- canonical-L helix evidence coverage: {he.get('supported_residues', 0)}/{he.get('peptide_like_residues', 0)}\n")
        self.note.insert("end", f"- i,i+3/i+4 opposite-charge pairs: {seq_ev.get('opposite_charge_i3_i4_pairs', [])}\n")
        lit = seq_ev.get("literature_sequence_screen") or {}
        self.note.insert("end", f"- alpha/beta/gamma backbone: {(lit.get('alpha_beta_gamma_peptidomimetic') or {}).get('detected_pattern')}\n")
        self.note.insert("end", f"- recorded conditions: pH={conditions.get('pH')}, temperature={conditions.get('temperature_C')} °C, ionic strength={conditions.get('ionic_strength_mM')} mM, environment={conditions.get('environment')}\n")
        self.note.insert("end", "- Conditions are metadata for interpretation/external validation, not an invented solvent or constant-pH energy correction.\n")
        self.note.insert("end", "- Generated family fractions are search outcomes, not experimental populations.\n")

    def _browse_receptor(self):
        p = filedialog.askopenfilename(title="Select receptor/target file", filetypes=[("Structure files", "*.pdb *.cif *.mmcif *.pdbqt"), ("All files", "*.*")])
        if p:
            self.bridge_receptor_path.set(p)

    def _browse_md_csv(self):
        p = filedialog.askopenfilename(title="Select external MD result CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if p:
            self.bridge_md_result_csv.set(p)

    def _bridge_receptor(self):
        p = str(self.bridge_receptor_path.get() or "").strip()
        return p or None

    def _bridge_md_csv(self):
        p = str(self.bridge_md_result_csv.get() or "").strip()
        return p or None

    def _bridge_center(self):
        return (float(self.bridge_center_x.get()), float(self.bridge_center_y.get()), float(self.bridge_center_z.get()))

    def _bridge_size(self):
        return (float(self.bridge_size_x.get()), float(self.bridge_size_y.get()), float(self.bridge_size_z.get()))

    def _bridge_settings_note(self):
        return (
            f"Bridge settings: receptor={self._bridge_receptor() or 'not set'}, "
            f"center={self._bridge_center()}, size={self._bridge_size()}, "
            f"confs={int(self.bridge_conformers.get())}, "
            f"exhaustiveness={int(self.bridge_exhaustiveness.get())}, modes={int(self.bridge_num_modes.get())}, "
            f"md_csv={self._bridge_md_csv() or 'not set'}"
        )

    def _write_json_popup(self, title: str, payload):
        win = tk.Toplevel(self)
        win.title(title)
        set_pepforge_icon(win)
        apply_pepforge_theme(win)
        fit_window(win, preferred_width=980, preferred_height=700, minimum_width=780, minimum_height=560)
        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("end", json.dumps(payload, indent=2, ensure_ascii=False))


    def _set_progress(self, value: float, text: str):
        """Set a determinate left-to-right green progress bar."""
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=max(0, min(100, float(value))))
            self.progress_var.set(text)
            self.update_idletasks()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _set_busy(self, text: str = "Working..."):
        try:
            self._set_progress(8, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="disabled")
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _set_done(self, text: str = "Done"):
        try:
            self._set_progress(100, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="normal")
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _set_failed(self, text: str = "Failed"):
        try:
            self._set_progress(0, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="normal")
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _write_diagnostics(self, stage: str, exc: Exception) -> dict[str, str]:
        """Write bridge diagnostics instead of ending with only a popup."""
        diag_dir = (self._active_result_bundle or self._effective_output_dir()) / "bridge_diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stage = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in stage)
        base = diag_dir / f"{safe_stage}_{stamp}_diagnostic"
        payload = {
            "stage": stage,
            "input_sequence": self.sequence_var.get(),
            "output_name": self._safe_name(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "meaning": "분석 오류 발견됨은 입력 토큰/구조/템플릿/환경 분석 중 경고 또는 실패가 감지됐다는 뜻이다. 출력 일부가 만들어졌을 수 있으므로 이 파일과 output 폴더를 확인한다.",
            "common_causes": ["unsupported modified token", "RDKit unavailable or template audit issue", "D-amino acid or lipid/label parameter warning", "non-ASCII path", "optional dependency missing"],
        }
        json_path = base.with_suffix(".json")
        txt_path = base.with_suffix(".txt")
        csv_path = base.with_suffix(".csv")
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        txt_path.write_text("Pepforge Bridge Diagnostic\n==========================\n\n" + json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["field", "value"])
            w.writeheader()
            for k, v in payload.items():
                w.writerow({"field": k, "value": json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)})
        return {"diagnostic_json": str(json_path), "diagnostic_txt": str(txt_path), "diagnostic_csv": str(csv_path)}

    def _safe_name(self):
        name = self._effective_output_name()
        return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)



    def open_token_map(self):
        """Create the interpretation map without running a 3D calculation."""
        seq = self._require_sequence()
        if seq is None:
            return
        name = self._safe_name()
        out = self._result_bundle(seq, name, force_new=False)
        token_map = out / f"{name}_token_map.csv"
        try:
            if not token_map.exists():
                self._set_busy("Creating token map...")
                rows = _token_rows_for_bridge(seq)
                _safe_write_csv(token_map, rows)
            self.note.insert("end", f"\nToken map ready: {token_map}\n")
            self._set_done("Token map ready")
            _open_path(token_map)
        except Exception as exc:
            diag = self._write_diagnostics("open_token_map", exc)
            self.note.insert("end", "\nToken map diagnostic written:\n")
            for k, p in diag.items():
                self.note.insert("end", f"- {k}: {p}\n")
            self._set_failed("Token map diagnostic written")
            messagebox.showerror("Token map failed", "Token map could not be opened, but diagnostic files were written.\n\n" + str(exc))

    def analyze_structure_files(self):
        files = filedialog.askopenfilenames(title="Select one or more PDB/SDF structure files", filetypes=[("Structure files", "*.pdb *.sdf"), ("PDB", "*.pdb"), ("SDF", "*.sdf"), ("All files", "*.*")])
        if not files:
            return
        name = self._effective_output_name() + "_Structure_Files"
        try:
            self._startup_trace.mark("structure_file_backend_load_start")
            from peptiforg_core.structure_file_analyzer import analyze_structure_files
            self._startup_trace.mark("structure_file_backend_ready")
            self._startup_trace.write()
            paths = analyze_structure_files(files, self._effective_output_dir(), name=name)
            self.note.insert("end", "\nStructure-file analysis exported:\n")
            for key in ("summary_csv", "summary_json", "zip_path", "bundle_dir"):
                if key in paths:
                    self.note.insert("end", f"- {key}: {paths[key]}\n")
            self.note.insert("end", f"- models: {paths.get('model_count')} | files: {paths.get('file_count')} | mean Rg: {paths.get('mean_radius_of_gyration_A')} Å | mean RMSD to first model: {paths.get('mean_rmsd_to_first_model_A')} Å\n")
            messagebox.showinfo("Structure analysis complete", "Selected PDB/SDF structure files were analyzed. Open the result bundle for geometry summaries without requiring trajectory files.")
        except Exception as exc:
            messagebox.showerror("Structure analysis failed", str(exc))

    def compare_structure_files(self):
        reference = filedialog.askopenfilename(title="Select reference/independent structure PDB", filetypes=[("PDB", "*.pdb"), ("All files", "*.*")])
        if not reference:
            return
        comparison = filedialog.askopenfilename(title="Select comparison structure PDB", filetypes=[("PDB", "*.pdb"), ("All files", "*.*")])
        if not comparison:
            return
        name = self._effective_output_name() + "_Structure_Consensus"
        try:
            self._startup_trace.mark("structure_consensus_backend_load_start")
            from peptiforg_core.structure_consensus import compare_structures
            self._startup_trace.mark("structure_consensus_backend_ready")
            self._startup_trace.write()
            paths = compare_structures(reference, comparison, self._effective_output_dir(), name=name)
            self.note.insert("end", "\nStructure consensus diagnostic exported:\n")
            for key in ("summary_json", "per_residue_csv", "zip_path"):
                if key in paths:
                    self.note.insert("end", f"- {key}: {paths[key]}\n")
            mode = paths.get("comparison_mode", "residue_CA_backbone")
            if mode == "heavy_atom_order":
                self.note.insert("end", f"- heavy-atom aligned RMSD: {paths.get('heavy_atom_order_rmsd_A')} Å | comparison mode: atom-order geometry\n")
            else:
                self.note.insert("end", f"- Cα RMSD: {paths.get('ca_rmsd_A')} Å | backbone RMSD: {paths.get('backbone_rmsd_A')} Å | DSSP agreement: {paths.get('dssp_residue_agreement_fraction')}\n")
            messagebox.showinfo("Structure comparison complete", "PDB structures were compared as a static V4 structure review. Production MD and trajectory analysis are reserved for V5.")
        except Exception as exc:
            messagebox.showerror("Structure comparison failed", str(exc))

    def show_environment(self):
        self._ensure_structure_generation_backend()
        self._write_json_popup("Pepforge Structure Tool Environment", environment_report())

    def show_supported_tokens(self):
        self._ensure_structure_generation_backend()
        table = supported_token_table()
        slim = {k: v for k, v in table.items() if k not in {"template_registry", "template_manifest"}}
        self._write_json_popup("Supported Tokens", slim)

    def show_template_audit(self):
        self._ensure_structure_generation_backend()
        try:
            payload = audit_template_files(Path(__file__).resolve().parents[1])
        except Exception as exc:
            payload = {
                "error": str(exc),
                "note": "Template audit could not be completed. Pepforge does not fabricate a substitute structure for chemistry that requires a curated derivative.",
            }
        self._write_json_popup("Template Audit", payload)

    def analyze(self):
        self._ensure_structure_generation_backend()
        seq = self._require_sequence()
        if seq is None:
            return
        for x in self.tree.get_children():
            self.tree.delete(x)
        try:
            toks = classify_tokens(seq)
        except Exception as exc:
            self.note.delete("1.0", "end")
            self.note.insert("end", f"Parse failed: {exc}\n")
            return
        for t in toks:
            self.tree.insert("", "end", values=(t.position or "", t.raw, t.token, t.cls, t.note, t.warning))
        self.note.delete("1.0", "end")
        warnings = [t.warning for t in toks if t.warning]
        self.note.insert("end", f"Parsed {len(toks)} tokens.\n")
        self.note.insert("end", "Examples: Ac-K(FITC)-LVFF-NH2, Ac-K(Ahx-Biotin)-LVFF-NH2, FITC-Cha-AEEA-dK-NH2, Pal-EEMQRR-NH2.\n")
        self.note.insert("end", "The V5 workflow can continue from peptide analysis/Top-5 structure generation into real HADDOCK3 docking, DockBench interaction review, PyMOL export, and optional OpenMM MD when those optional backends are installed.\n")
        self.note.insert("end", "Primary outputs: ranked top-five SDF/PDB structures, JSON evidence, TXT report, PyMOL PML, and audit CSV files.\n")
        self.note.insert("end", "Generated structures are connected 3D starting models for PyMOL inspection/screening. They are not fully parameterized all-atom MD structures.\n")
        if warnings:
            self.note.insert("end", "\nWarnings:\n")
            for w in warnings:
                self.note.insert("end", f"- {w}\n")

    def export(self):
        seq = self._require_sequence()
        if seq is None:
            return
        if self._build_process is not None:
            messagebox.showinfo("Build in progress", "A structure build is already running.")
            return
        self.analyze()
        name = self._safe_name()
        try:
            conditions = self._environment_conditions()
            self._start_structure_worker(seq, name, conditions)
        except Exception as exc:
            diag = self._write_diagnostics("build_sdf_pdb_pml", exc)
            self.note.insert("end", "\nSDF/PDB/PML diagnostic written:\n")
            for k, p in diag.items():
                self.note.insert("end", f"- {k}: {p}\n")
            self._set_failed("Build could not start")
            messagebox.showerror("Export failed", "The isolated build could not start, but diagnostic files were written.\n\n" + str(exc))


    def _v5_binding_residue_list(self):
        text=str(self.v5_binding_residues.get() or "")
        return [x.strip() for x in text.replace(",",";").split(";") if x.strip()]

    def run_v5_full_simulation(self):
        """One-click V5 path: fresh PSB Top-5 build, then real docking/analysis."""
        seq=self._require_sequence()
        if seq is None:
            return
        receptor_source=str(self.v5_receptor_source.get() or "file").strip()
        receptor=str(self.bridge_receptor_path.get() or "").strip()
        if receptor_source == "file" and not receptor:
            messagebox.showwarning("Receptor required", "Select a receptor PDB/mmCIF before running the V5 full simulation.")
            return
        if receptor_source == "ESMFold" and not str(self.v5_receptor_sequence.get() or "").strip():
            messagebox.showwarning("Receptor sequence required", "Enter a canonical receptor protein sequence for ESMFold prediction.")
            return
        mode=str(self.v5_binding_mode.get() or "blind")
        if mode in {"manual","hotspot"} and not self._v5_binding_residue_list():
            messagebox.showwarning("Binding residues required", "Manual/Hotspot docking requires receptor residues such as A:10;A:24.")
            return
        if self._build_process is not None or (self._v5_pipeline_thread is not None and self._v5_pipeline_thread.is_alive()):
            messagebox.showinfo("Run in progress", "A PSB build or V5 simulation is already running.")
            return
        self._v5_pending_after_build=True
        self.note.insert("end", "\nV5 full simulation requested. Building a fresh PSB Top-5 ensemble first...\n")
        self.export()

    def _start_v5_pipeline(self, meta_path):
        from peptiforg_core.psb_v5_full_pipeline import run_psb_v5_pipeline
        from peptiforg_core.openmm_md_backend import OpenMMProtocol
        receptor_source=str(self.v5_receptor_source.get() or "file").strip()
        receptor=str(self.bridge_receptor_path.get() or "").strip()
        receptor_sequence=str(self.v5_receptor_sequence.get() or "").strip()
        output=(self._active_result_bundle or self._effective_output_dir()) / "V5_Full_Simulation"
        protocol=OpenMMProtocol(
            production_ns=max(0.001,float(self.v5_md_production_ns.get())),
            replicates=max(1,int(self.v5_md_replicates.get())),
        )
        kwargs=dict(
            psb_meta_path=meta_path, receptor_path=receptor, output_dir=output,
            model_limit=5, pose_limit_per_model=5,
            binding_site_mode=str(self.v5_binding_mode.get() or "blind"),
            binding_site_residues=self._v5_binding_residue_list(),
            docking_preset=str(self.v5_docking_preset.get() or "standard"),
            docking_backend=str(self.v5_docking_backend.get() or "native"),
            run_docking=True, run_dockbench=True, run_md=bool(self.v5_run_md.get()),
            run_native_mechanics_followup=bool(self.v5_run_native_followup.get()),
            native_mechanics_steps=max(20,int(self.v5_native_mechanics_steps.get() or 400)),
            md_protocol=protocol, execution_mode=str(self.v5_execution_mode.get() or "offline"),
            resource_root=(str(self.v5_resource_root.get() or "").strip() or None),
        )
        self._v5_pipeline_result=None; self._v5_pipeline_error=None
        self._set_busy("V5 docking/simulation running...")
        try: self.v5_run_button.configure(state="disabled")
        except Exception: pass
        def worker():
            try:
                if receptor_source == "ESMFold":
                    from peptiforg_core.structure_predictor_backends import run_esmfold_prediction
                    execution_mode = str(self.v5_execution_mode.get() or "offline")
                    pred = run_esmfold_prediction(
                        receptor_sequence, output / "Receptor_Prediction",
                        local_files_only=(execution_mode == "offline"),
                    )
                    if pred.get("status") != "COMPLETED" or not pred.get("pdb"):
                        raise RuntimeError(f"ESMFold receptor prediction did not complete: {pred.get('status')}")
                    kwargs["receptor_path"] = pred["pdb"]
                self._v5_pipeline_result=run_psb_v5_pipeline(**kwargs)
            except Exception as exc:
                self._v5_pipeline_error=(type(exc).__name__,str(exc),traceback.format_exc())
        self._v5_pipeline_thread=threading.Thread(target=worker,daemon=True,name="pepforge-v5-pipeline")
        self._v5_pipeline_thread.start()
        self.after(500,self._poll_v5_pipeline)

    def _rerun_selected_native_followup(self, pose_id: str):
        """Re-run native mechanics/trajectory for a viewer-selected PSB pose."""
        result = getattr(self, "_v5_pipeline_result", None)
        if not isinstance(result, dict):
            messagebox.showinfo("Native follow-up", "Run PSB Full Simulation first.")
            return None
        import re as _re
        m = _re.match(r"^m(\d{2})_(.+)$", str(pose_id or ""))
        if not m:
            messagebox.showerror("Native follow-up", f"Could not resolve PSB model from pose id: {pose_id}")
            return None
        model_rank = int(m.group(1))
        local_pose_id = m.group(2)
        model = next((x for x in (result.get("model_results") or []) if int(x.get("model_rank") or 0) == model_rank), None)
        if not isinstance(model, dict):
            messagebox.showerror("Native follow-up", f"PSB model {model_rank} is unavailable.")
            return None
        exported = model.get("normalized_result") or {}
        contract_path = exported.get("contract_json") if isinstance(exported, dict) else ""
        if not contract_path:
            messagebox.showerror("Native follow-up", "Shared docking-result contract is unavailable for the selected model.")
            return None

        def worker():
            try:
                normalized = load_normalized_result_export(contract_path)
                steps = max(20, min(20000, int(self.v5_native_mechanics_steps.get() or 400)))
                cfg = NativeMechanicsV2Config(steps=steps, save_every=max(1, steps // 10), freeze_receptor=True, peptide_chain="P")
                out = Path(contract_path).resolve().parent / f"native_followup_{local_pose_id.replace(':','_').replace('/','_')}"
                payload = run_native_docking_followup(normalized, out, mechanics_config=cfg, pose_id=local_pose_id)
                model["native_followup"] = payload
                self.after(0, lambda: self._update_shared_native_result_view(result))
                self.after(0, lambda: self.progress_var.set(f"Native follow-up completed for {pose_id}"))
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Native follow-up failed", str(e)))
        self.progress_var.set(f"Running native follow-up for {pose_id}...")
        threading.Thread(target=worker, daemon=True, name="pepforge-selected-followup").start()
        return True

    def _update_shared_native_result_view(self, result):
        if not hasattr(self, "shared_native_result_panel"):
            return
        normalized_items=[]
        followups=[]
        for model in (result.get("model_results") or []):
            rank=int(model.get("model_rank") or 0)
            exported=model.get("normalized_result") or {}
            contract_path=exported.get("contract_json") if isinstance(exported,dict) else ""
            if contract_path:
                try:
                    normalized_items.append((rank, load_normalized_result_export(contract_path)))
                except Exception:
                    LOGGER.debug("Could not load model %s normalized docking result", rank, exc_info=True)
            follow=model.get("native_followup")
            if isinstance(follow,dict):
                item={"model_rank":rank, "payload":follow, "status":follow.get("status","")}
                frames_path=follow.get("frames_csv")
                if frames_path and Path(str(frames_path)).exists():
                    try:
                        import pandas as _pd
                        item["frames"]=_pd.read_csv(frames_path)
                    except Exception:
                        LOGGER.debug("Could not load model %s native follow-up frames", rank, exc_info=True)
                followups.append(item)
        combined=combine_normalized_results(normalized_items) if normalized_items else {}
        self.shared_native_result_panel.load_result(
            combined, followups=followups, source="PSB Full Simulation",
            output_dir=(Path(result.get("manifest")).parent if result.get("manifest") else self._effective_output_dir()),
        )

    def _poll_v5_pipeline(self):
        thread=self._v5_pipeline_thread
        if thread is not None and thread.is_alive():
            self.progress_var.set("V5 docking/simulation running · see run folders/logs for backend progress")
            self.after(1000,self._poll_v5_pipeline)
            return
        try: self.v5_run_button.configure(state="normal")
        except Exception: pass
        if self._v5_pipeline_error:
            etype,msg,tb=self._v5_pipeline_error
            exc=RuntimeError(f"{etype}: {msg}")
            diag=self._write_diagnostics("v5_full_simulation",exc)
            self.note.insert("end", f"\nV5 full simulation failed: {etype}: {msg}\n{tb}\n")
            for k,p in diag.items(): self.note.insert("end",f"- {k}: {p}\n")
            self._set_failed("V5 full simulation failed")
            messagebox.showerror("V5 simulation failed", f"{etype}: {msg}")
            return
        result=self._v5_pipeline_result or {}
        self.note.insert("end", "\nV5 full simulation result:\n")
        self.note.insert("end", f"- status: {result.get('status')}\n- verified docking poses: {result.get('verified_pose_count',0)}\n")
        if result.get("manifest"): self.note.insert("end",f"- manifest: {result['manifest']}\n")
        if isinstance(result.get("pymol"),dict) and result["pymol"].get("pml"): self.note.insert("end",f"- PyMOL: {result['pymol']['pml']}\n")
        bs=result.get("backend_status") or {}
        self.note.insert("end", f"- docking backend: {result.get('docking_backend')}\n")
        if result.get("verified_pose_count",0)==0 and result.get("docking_backend") == "haddock3":
            self.note.insert("end", f"- HADDOCK3: {(bs.get('haddock3') or {}).get('status')}\n")
        if bool(self.v5_run_md.get()): self.note.insert("end",f"- OpenMM: {(bs.get('openmm') or {}).get('status')}\n")
        if result.get("native_followup_results"):
            self.note.insert("end",f"- native mechanics/trajectory follow-ups: {len(result.get('native_followup_results') or [])}\n")
        try:
            self._update_shared_native_result_view(result)
        except Exception:
            LOGGER.debug("Could not refresh shared native result viewer", exc_info=True)
        self._set_done(f"V5: {result.get('status','complete')}")
        messagebox.showinfo("V5 simulation finished", f"Status: {result.get('status')}\nVerified poses: {result.get('verified_pose_count',0)}\n\nNo unavailable backend is replaced with a fake result.")

    def _export_bridge_kind(self, label: str, kind: str, advanced_runner):
        seq = self._require_sequence()
        if seq is None:
            return
        self.analyze()
        name = self._safe_name()
        self._set_busy(f"Building {label}...")
        try:
            self._set_progress(25, "Preparing base structure and token map...")
            if bool(self.bridge_quick_mode.get()):
                paths = export_gui_quick_bridge_package(
                    self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name, label,
                    receptor_path=self._bridge_receptor(),
                    external_md_csv=self._bridge_md_csv(),
                    center=self._bridge_center(),
                    size=self._bridge_size(),
                    exhaustiveness=max(1, int(self.bridge_exhaustiveness.get())),
                    num_modes=max(1, int(self.bridge_num_modes.get())),
                    num_confs=max(1, int(self.bridge_conformers.get())),
                )
            else:
                # Advanced mode must either complete its requested workflow or fail
                # visibly. Do not silently substitute a different Quick-bridge
                # workflow, because that can make an advanced failure look like a
                # successful advanced export.
                paths = advanced_runner(name)
            self._set_progress(86, f"Writing {label} files...")
            self.note.insert("end", chr(10) + f"{label} exported:" + chr(10))
            for k, p in paths.items():
                self.note.insert("end", f"- {k}: {p}" + chr(10))
            self.note.insert("end", chr(10) + "Bridge is a hand-off/template export, not a final external docking or MD run. Open token_map.csv and parameter_requirements.csv first." + chr(10))
            self.note.insert("end", self._bridge_settings_note() + chr(10))
            if self._active_result_bundle and self._active_result_bundle.exists():
                zip_path = build_bundle_zip(self._active_result_bundle, filename="PSB_Result_Package.zip")
                write_bundle_manifest(self._active_result_bundle, tool="PSB", name=name, sequence=self.sequence_var.get(), artifacts={**paths, "zip": zip_path})
            self._set_done(f"{label} complete")
            messagebox.showinfo(f"{label} complete", f"{label} package exported. Open the output folder and check bridge_packages.")
        except Exception as exc:
            diag = self._write_diagnostics(kind, exc)
            self.note.insert("end", chr(10) + f"{label} diagnostic written:" + chr(10))
            for k, p in diag.items():
                self.note.insert("end", f"- {k}: {p}" + chr(10))
            self._set_failed(f"{label} diagnostic written")
            messagebox.showerror(f"{label} failed", f"{label} failed, but diagnostic files were written." + chr(10) + chr(10) + str(exc))

    def export_bridge(self):
        self._export_bridge_kind(
            "Simulation Bridge", "simulation_bridge",
            lambda name: export_low_spec_validation_bridge(self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name, num_confs=max(1, int(self.bridge_conformers.get())))
        )

    def export_docking_bridge(self):
        self._export_bridge_kind(
            "Docking Bridge", "docking_bridge",
            lambda name: export_external_docking_runner_bridge(
                self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name,
                receptor_path=self._bridge_receptor(), center=self._bridge_center(), size=self._bridge_size(),
                exhaustiveness=max(1, int(self.bridge_exhaustiveness.get())),
                num_modes=max(1, int(self.bridge_num_modes.get())),
                low_spec_num_confs=max(1, int(self.bridge_conformers.get())),
            )
        )

    def export_md_prep_bridge(self):
        self._export_bridge_kind(
            "MD Prep Bridge", "md_prep_bridge",
            lambda name: export_all_atom_md_preparation_bridge(
                self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name,
                receptor_path=self._bridge_receptor(), center=self._bridge_center(), size=self._bridge_size(),
                low_spec_num_confs=max(1, int(self.bridge_conformers.get())),
            )
        )

    def export_md_result_import_bridge(self):
        self._export_bridge_kind(
            "MD Result Import", "md_result_import_bridge",
            lambda name: export_external_md_result_import_bridge(
                self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name,
                external_md_csv=self._bridge_md_csv(), receptor_path=self._bridge_receptor(),
                center=self._bridge_center(), size=self._bridge_size(),
                low_spec_num_confs=max(1, int(self.bridge_conformers.get())),
            )
        )

    def export_publication_report(self):
        self._export_bridge_kind(
            "Publication Report", "publication_report",
            lambda name: export_publication_validation_report(self.sequence_var.get(), str(self._result_bundle(self.sequence_var.get(), name, force_new=False)), name)
        )


def main():
    app = PyMOLStructureBuilderGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
