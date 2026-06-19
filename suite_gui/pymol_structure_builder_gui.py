from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import json
import csv
import traceback
from datetime import datetime
from peptiforg_core.ui_helpers import set_pepforge_icon

from peptiforg_core.pymol_structure_builder import (
    classify_tokens,
    export_modified_peptide_structure,
    environment_report,
    supported_token_table,
    template_manifest,
    audit_template_files,
    STRUCTURE_TOOL_VERSION,
)
from peptiforg_core.low_spec_validation_bridge import export_low_spec_validation_bridge, BRIDGE_VERSION
from peptiforg_core.external_docking_runner_bridge import export_external_docking_runner_bridge, DOCKING_BRIDGE_VERSION
from peptiforg_core.all_atom_md_preparation_bridge import export_all_atom_md_preparation_bridge, MD_PREP_BRIDGE_VERSION
from peptiforg_core.external_md_result_import_bridge import export_external_md_result_import_bridge, MD_RESULT_IMPORT_BRIDGE_VERSION
from peptiforg_core.publication_validation_report_builder import export_publication_validation_report, PUBLICATION_REPORT_BUILDER_VERSION


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
        "cif": str(out / f"{safe}.cif"),
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
- SDF/PDB/CIF/PML/metadata/report using the same build path as Build SDF/PDB/PML
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
        self.title("PyMOL Structure Builder")
        set_pepforge_icon(self)
        self.geometry("1500x900")
        self.minsize(1180, 720)
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "outputs" / "pymol_structure_builder"))
        self.sequence_var = tk.StringVar(value="FITC-Cha-AEEA-dK-NH2")
        self.name_var = tk.StringVar(value="modified_peptide")
        # User-editable bridge settings. Bridge buttons are not magic one-click
        # final MD/docking; they export packages according to these values.
        self.bridge_receptor_path = tk.StringVar(value="")
        self.bridge_md_result_csv = tk.StringVar(value="")
        self.bridge_conformers = tk.IntVar(value=8)
        self.bridge_exhaustiveness = tk.IntVar(value=16)
        self.bridge_num_modes = tk.IntVar(value=20)
        self.bridge_quick_mode = tk.BooleanVar(value=True)
        self.bridge_center_x = tk.DoubleVar(value=0.0)
        self.bridge_center_y = tk.DoubleVar(value=0.0)
        self.bridge_center_z = tk.DoubleVar(value=0.0)
        self.bridge_size_x = tk.DoubleVar(value=22.0)
        self.bridge_size_y = tk.DoubleVar(value=22.0)
        self.bridge_size_z = tk.DoubleVar(value=22.0)
        self._build()

    def _build(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Head.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("PepforgeGreen.Horizontal.TProgressbar", troughcolor="#e8e8e8", background="#2dbb55", lightcolor="#2dbb55", darkcolor="#2dbb55")

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="PyMOL Structure Builder", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text=(
                f"Integrated Pepforge PyMOL Structure Tool v{STRUCTURE_TOOL_VERSION}. "
                "Build RDKit-backed SDF/PDB/JSON/PML files from modified peptide notation. "
                "v2.5.0 adds publication validation report building on top of external MD result import and validation summary on top of low-spec simulation and external docking runner bridge export. "
                "Output is screening/validation-preparation grade, not final all-atom MD."
            ),
            wraplength=1200,
        ).pack(anchor="w", pady=(4, 12))

        input_box = ttk.LabelFrame(root, text="Input")
        input_box.pack(fill="x")
        ttk.Label(input_box, text="Peptide notation").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ent = ttk.Entry(input_box, textvariable=self.sequence_var)
        ent.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        ttk.Label(input_box, text="Output name").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(input_box, textvariable=self.name_var, width=36).grid(row=1, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(input_box, text="Output folder").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(input_box, textvariable=self.output_dir).grid(row=2, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(input_box, text="Browse", command=self._browse).grid(row=2, column=2, padx=8, pady=8)
        input_box.columnconfigure(1, weight=1)

        bridge_box = ttk.LabelFrame(root, text="Bridge settings / user-defined external workflow parameters")
        bridge_box.pack(fill="x", pady=(8, 0))
        ttk.Label(bridge_box, text="Receptor PDB/CIF/PDBQT").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(bridge_box, textvariable=self.bridge_receptor_path).grid(row=0, column=1, columnspan=5, sticky="ew", padx=6, pady=4)
        ttk.Button(bridge_box, text="Browse", command=self._browse_receptor).grid(row=0, column=6, padx=6, pady=4)
        ttk.Label(bridge_box, text="MD result CSV").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(bridge_box, textvariable=self.bridge_md_result_csv).grid(row=1, column=1, columnspan=5, sticky="ew", padx=6, pady=4)
        ttk.Button(bridge_box, text="Browse", command=self._browse_md_csv).grid(row=1, column=6, padx=6, pady=4)
        ttk.Label(bridge_box, text="Confs").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Spinbox(bridge_box, from_=1, to=64, textvariable=self.bridge_conformers, width=7).grid(row=2, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(bridge_box, text="Dock center XYZ").grid(row=2, column=2, sticky="e", padx=6, pady=4)
        for i, var in enumerate([self.bridge_center_x, self.bridge_center_y, self.bridge_center_z], start=3):
            ttk.Entry(bridge_box, textvariable=var, width=8).grid(row=2, column=i, sticky="w", padx=2, pady=4)
        ttk.Label(bridge_box, text="Box size XYZ").grid(row=3, column=2, sticky="e", padx=6, pady=4)
        for i, var in enumerate([self.bridge_size_x, self.bridge_size_y, self.bridge_size_z], start=3):
            ttk.Entry(bridge_box, textvariable=var, width=8).grid(row=3, column=i, sticky="w", padx=2, pady=4)
        ttk.Label(bridge_box, text="Vina exhaustiveness / modes").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Spinbox(bridge_box, from_=1, to=128, textvariable=self.bridge_exhaustiveness, width=7).grid(row=3, column=1, sticky="w", padx=6, pady=4)
        ttk.Spinbox(bridge_box, from_=1, to=100, textvariable=self.bridge_num_modes, width=7).grid(row=3, column=1, sticky="e", padx=6, pady=4)
        ttk.Checkbutton(bridge_box, text="Quick safe bridge mode 권장: Build SDF/PDB/PML 경로를 재사용해서 템플릿을 즉시 생성", variable=self.bridge_quick_mode).grid(row=4, column=0, columnspan=7, sticky="w", padx=6, pady=(0, 2))
        ttk.Label(bridge_box, text="Bridge buttons export templates/packages using these values; external Vina/OpenMM/GROMACS/PRODIGY-style tools still run outside Pepforge.").grid(row=5, column=0, columnspan=7, sticky="w", padx=6, pady=(0, 6))
        bridge_box.columnconfigure(1, weight=1)

        actions = ttk.LabelFrame(root, text="Actions")
        actions.pack(fill="x", pady=8)
        self.progress_var = tk.StringVar(value="Ready")
        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100, value=0, style="PepforgeGreen.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, columnspan=6, sticky="ew", padx=6, pady=(6, 2))
        ttk.Label(actions, textvariable=self.progress_var).grid(row=0, column=6, columnspan=2, sticky="w", padx=6)

        self.action_buttons = []
        button_specs = [
            ("Analyze", self.analyze),
            ("Build SDF/PDB/PML", self.export),
            ("Simulation Bridge", self.export_bridge),
            ("Docking Bridge", self.export_docking_bridge),
            ("MD Prep Bridge", self.export_md_prep_bridge),
            ("MD Result Import", self.export_md_result_import_bridge),
            ("Publication Report", self.export_publication_report),
            ("Open Token Map", self.open_token_map),
            ("Environment", self.show_environment),
            ("Supported Tokens", self.show_supported_tokens),
            ("Template Audit", self.show_template_audit),
            ("Open Output", lambda: _open_path(Path(self.output_dir.get()))),
        ]
        for idx, (label, cmd) in enumerate(button_specs):
            btn = ttk.Button(actions, text=label, command=cmd, width=18)
            btn.grid(row=1 + idx // 6, column=idx % 6, padx=4, pady=4, sticky="ew")
            self.action_buttons.append(btn)
        for col in range(6):
            actions.columnconfigure(col, weight=1)

        pane = ttk.PanedWindow(root, orient="vertical")
        pane.pack(fill="both", expand=True)

        token_frame = ttk.LabelFrame(pane, text="Token interpretation")
        pane.add(token_frame, weight=3)
        cols = ("position", "raw", "token", "class", "note", "warning")
        self.tree = ttk.Treeview(token_frame, columns=cols, show="headings", height=15)
        widths = {"position": 80, "raw": 130, "token": 180, "class": 180, "note": 420, "warning": 420}
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=widths.get(c, 160), stretch=True)
        self.tree.pack(side="left", fill="both", expand=True)
        y = ttk.Scrollbar(token_frame, orient="vertical", command=self.tree.yview)
        y.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=y.set)

        note_frame = ttk.LabelFrame(pane, text="Output and interpretation")
        pane.add(note_frame, weight=2)
        self.note = tk.Text(note_frame, height=12, wrap="word")
        self.note.pack(fill="both", expand=True)
        self.analyze()

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.cwd()))
        if d:
            self.output_dir.set(d)

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
        win.geometry("980x700")
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
            pass

    def _set_busy(self, text: str = "Working..."):
        try:
            self._set_progress(8, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="disabled")
        except Exception:
            pass

    def _set_done(self, text: str = "Done"):
        try:
            self._set_progress(100, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="normal")
        except Exception:
            pass

    def _set_failed(self, text: str = "Failed"):
        try:
            self._set_progress(0, text)
            for b in getattr(self, "action_buttons", []):
                b.configure(state="normal")
        except Exception:
            pass

    def _write_diagnostics(self, stage: str, exc: Exception) -> dict[str, str]:
        """Write bridge diagnostics instead of ending with only a popup."""
        diag_dir = Path(self.output_dir.get()).expanduser() / "bridge_diagnostics"
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
            "common_causes": ["unsupported modified token", "RDKit/template fallback", "D-amino acid or lipid/label parameter warning", "non-ASCII path", "optional dependency missing"],
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
        name = self.name_var.get().strip() or "modified_peptide"
        return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)



    def open_token_map(self):
        """Open or create the token_map.csv that users need as step 2."""
        name = self._safe_name()
        out = Path(self.output_dir.get()).expanduser()
        token_map = out / f"{name}_token_map.csv"
        try:
            if not token_map.exists():
                self._set_busy("Creating token map...")
                paths = export_modified_peptide_structure(self.sequence_var.get(), out, name)
                token_map = Path(paths.get("token_map", token_map))
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

    def show_environment(self):
        self._write_json_popup("Pepforge Structure Tool Environment", environment_report())

    def show_supported_tokens(self):
        table = supported_token_table()
        slim = {k: v for k, v in table.items() if k not in {"template_registry", "template_manifest"}}
        self._write_json_popup("Supported Tokens", slim)

    def show_template_audit(self):
        try:
            payload = audit_template_files(Path(__file__).resolve().parents[1])
        except Exception as exc:
            payload = {"error": str(exc), "note": "Template audit is optional. Generation uses RDKit SMILES if templates are not curated."}
        self._write_json_popup("Template Audit", payload)

    def analyze(self):
        for x in self.tree.get_children():
            self.tree.delete(x)
        try:
            toks = classify_tokens(self.sequence_var.get())
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
        self.note.insert("end", f"v2.5.0 uses the v1.3.0 attachment-aware PyMOL Structure Tool core, Low-Spec Validation Bridge v{BRIDGE_VERSION}, External Docking Runner Bridge v{DOCKING_BRIDGE_VERSION}, MD Preparation Bridge v{MD_PREP_BRIDGE_VERSION}, External MD Import Bridge v{MD_RESULT_IMPORT_BRIDGE_VERSION}, and Publication Report Builder v{PUBLICATION_REPORT_BUILDER_VERSION}.\n")
        self.note.insert("end", "Primary outputs: SDF, PDB, JSON metadata, TXT report, portable PyMOL PML, conformer metrics, parameter requirements, evidence report, external docking runner templates, and all-atom MD preparation templates.\n")
        self.note.insert("end", "Generated structures are connected 3D starting models for PyMOL inspection/screening. They are not fully parameterized all-atom MD structures.\n")
        if warnings:
            self.note.insert("end", "\nWarnings:\n")
            for w in warnings:
                self.note.insert("end", f"- {w}\n")

    def export(self):
        self.analyze()
        name = self._safe_name()
        self._set_busy("Building SDF/PDB/PML...")
        try:
            self._set_progress(35, "Generating 3D structure...")
            paths = export_modified_peptide_structure(self.sequence_var.get(), self.output_dir.get(), name)
            self._set_progress(82, "Writing SDF/PDB/PML files...")
            self.note.insert("end", "\nExported files:\n")
            for k, p in paths.items():
                self.note.insert("end", f"- {k}: {p}\n")
            self._set_done("SDF/PDB/PML complete")
            messagebox.showinfo("Export complete", "SDF/PDB/JSON/report/PML/token map exported.")
        except Exception as exc:
            diag = self._write_diagnostics("build_sdf_pdb_pml", exc)
            self.note.insert("end", "\nSDF/PDB/PML diagnostic written:\n")
            for k, p in diag.items():
                self.note.insert("end", f"- {k}: {p}\n")
            self._set_failed("SDF/PDB/PML diagnostic written")
            messagebox.showerror("Export failed", "Build failed, but diagnostic files were written.\n\n" + str(exc))


    def _export_bridge_kind(self, label: str, kind: str, advanced_runner):
        self.analyze()
        name = self._safe_name()
        self._set_busy(f"Building {label}...")
        try:
            self._set_progress(25, "Preparing base structure and token map...")
            if bool(self.bridge_quick_mode.get()):
                paths = export_gui_quick_bridge_package(
                    self.sequence_var.get(), self.output_dir.get(), name, label,
                    receptor_path=self._bridge_receptor(),
                    external_md_csv=self._bridge_md_csv(),
                    center=self._bridge_center(),
                    size=self._bridge_size(),
                    exhaustiveness=max(1, int(self.bridge_exhaustiveness.get())),
                    num_modes=max(1, int(self.bridge_num_modes.get())),
                    num_confs=max(1, int(self.bridge_conformers.get())),
                )
            else:
                try:
                    paths = advanced_runner(name)
                except Exception as advanced_exc:
                    self.note.insert("end", chr(10) + f"Advanced bridge failed, falling back to quick safe bridge: {advanced_exc}" + chr(10))
                    paths = export_gui_quick_bridge_package(
                        self.sequence_var.get(), self.output_dir.get(), name, label,
                        receptor_path=self._bridge_receptor(),
                        external_md_csv=self._bridge_md_csv(),
                        center=self._bridge_center(),
                        size=self._bridge_size(),
                        exhaustiveness=max(1, int(self.bridge_exhaustiveness.get())),
                        num_modes=max(1, int(self.bridge_num_modes.get())),
                        num_confs=max(1, int(self.bridge_conformers.get())),
                    )
            self._set_progress(86, f"Writing {label} files...")
            self.note.insert("end", chr(10) + f"{label} exported:" + chr(10))
            for k, p in paths.items():
                self.note.insert("end", f"- {k}: {p}" + chr(10))
            self.note.insert("end", chr(10) + "Bridge is a hand-off/template export, not a final external docking or MD run. Open token_map.csv and parameter_requirements.csv first." + chr(10))
            self.note.insert("end", self._bridge_settings_note() + chr(10))
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
            lambda name: export_low_spec_validation_bridge(self.sequence_var.get(), self.output_dir.get(), name, num_confs=max(1, int(self.bridge_conformers.get())))
        )

    def export_docking_bridge(self):
        self._export_bridge_kind(
            "Docking Bridge", "docking_bridge",
            lambda name: export_external_docking_runner_bridge(
                self.sequence_var.get(), self.output_dir.get(), name,
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
                self.sequence_var.get(), self.output_dir.get(), name,
                receptor_path=self._bridge_receptor(), center=self._bridge_center(), size=self._bridge_size(),
                low_spec_num_confs=max(1, int(self.bridge_conformers.get())),
            )
        )

    def export_md_result_import_bridge(self):
        self._export_bridge_kind(
            "MD Result Import", "md_result_import_bridge",
            lambda name: export_external_md_result_import_bridge(
                self.sequence_var.get(), self.output_dir.get(), name,
                external_md_csv=self._bridge_md_csv(), receptor_path=self._bridge_receptor(),
                center=self._bridge_center(), size=self._bridge_size(),
                low_spec_num_confs=max(1, int(self.bridge_conformers.get())),
            )
        )

    def export_publication_report(self):
        self._export_bridge_kind(
            "Publication Report", "publication_report",
            lambda name: export_publication_validation_report(self.sequence_var.get(), self.output_dir.get(), name)
        )


def main():
    app = PyMOLStructureBuilderGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
