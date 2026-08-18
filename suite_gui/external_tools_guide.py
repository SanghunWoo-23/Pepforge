from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.sandbox_runtime import configured_output

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = configured_output(ROOT / "workspace" / "external" / "outputs", "external")


def find_program(*names: str) -> str:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return ""


def open_path(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def detect_environment() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "vina": find_program("vina", "vina.exe"),
        "openbabel": find_program("obabel", "obabel.exe", "babel"),
        "gromacs": find_program("gmx", "gmx_mpi", "gmx.exe"),
        "wsl": find_program("wsl", "wsl.exe") if os.name == "nt" else "not required on native Linux/macOS",
    }


def export_vina_package(output: Path, receptor: str, ligand: str) -> Path:
    folder = output / "vina_package"
    folder.mkdir(parents=True, exist_ok=True)
    config = """# AutoDock Vina configuration\nreceptor = receptor.pdbqt\nligand = ligand.pdbqt\ncenter_x = 0\ncenter_y = 0\ncenter_z = 0\nsize_x = 22\nsize_y = 22\nsize_z = 22\nexhaustiveness = 16\nnum_modes = 20\nout = docked.pdbqt\n"""
    (folder / "vina_config.txt").write_text(config, encoding="utf-8")
    guide = f"""Pepforge AutoDock Vina hand-off package

Pepforge does not run or replace AutoDock Vina.

Detected/selected inputs
- receptor source: {receptor or 'not selected'}
- ligand source: {ligand or 'not selected'}

Required external software
1. AutoDock Vina
2. Open Babel or another validated PDBQT preparation tool

Required final files in this folder
- receptor.pdbqt
- ligand.pdbqt
- vina_config.txt

Typical command
vina --config vina_config.txt

Review protonation, charges, atom types, rotatable bonds and docking box before execution.
"""
    (folder / "README_VINA.txt").write_text(guide, encoding="utf-8")
    for src, dst in [(receptor, "receptor_source"), (ligand, "ligand_source")]:
        if src and Path(src).is_file():
            target = folder / f"{dst}{Path(src).suffix.lower()}"
            shutil.copy2(src, target)
    return folder


def export_gromacs_package(output: Path, peptide_pdb: str) -> Path:
    folder = output / "gromacs_prep"
    folder.mkdir(parents=True, exist_ok=True)
    guide = f"""Pepforge GROMACS preparation guide

Pepforge does not run or replace GROMACS. This folder is a hand-off workspace.

Selected peptide structure
- {peptide_pdb or 'not selected'}

Recommended Windows environment
1. Enable WSL2
2. Install Ubuntu
3. Install GROMACS inside Ubuntu
4. Copy or access this preparation folder from WSL

Preparation sequence to perform externally
1. Validate peptide geometry, chirality, termini and protonation.
2. Select a compatible force field and water model.
3. Create or review parameters for every non-natural residue, linker, label and chemical cap.
4. Generate topology and coordinates with gmx pdb2gmx when supported.
5. Define box, solvate, add ions, energy-minimize, equilibrate and only then run production MD.

Files normally required
- peptide.pdb or peptide.gro
- topol.top
- additional .itp files for modified residues
- ions.mdp, minim.mdp, nvt.mdp, npt.mdp and md.mdp

Do not claim validated all-atom MD until topology, parameters and the external run have been reviewed.
"""
    (folder / "README_GROMACS.txt").write_text(guide, encoding="utf-8")
    checklist = {
        "peptide_structure": bool(peptide_pdb and Path(peptide_pdb).is_file()),
        "terminal_state_reviewed": False,
        "chirality_reviewed": False,
        "non_natural_parameters_reviewed": False,
        "force_field_selected": False,
        "topology_generated_externally": False,
    }
    (folder / "parameterization_checklist.json").write_text(json.dumps(checklist, indent=2), encoding="utf-8")
    if peptide_pdb and Path(peptide_pdb).is_file():
        shutil.copy2(peptide_pdb, folder / "peptide_input.pdb")
    return folder


class ExternalToolsGuide(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pepforge External Tools Guide")
        self.geometry("980x680")
        self.minsize(860, 580)
        set_pepforge_icon(self)
        self.output = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.receptor = tk.StringVar()
        self.ligand = tk.StringVar()
        self.peptide = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        self._build()
        self.check_tools()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="External Validation Tools", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="Pepforge prepares modified-peptide structures and hand-off files. AutoDock Vina and GROMACS are installed and executed separately.", wraplength=930).pack(anchor="w", pady=(4, 10))

        env = ttk.LabelFrame(root, text="Installation check")
        env.pack(fill="x")
        self.tree = ttk.Treeview(env, columns=("tool", "status", "path"), show="headings", height=6)
        for c, w in (("tool", 180), ("status", 120), ("path", 580)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="x", padx=8, pady=8)
        ttk.Button(env, text="Check again", command=self.check_tools).pack(anchor="e", padx=8, pady=(0, 8))

        files = ttk.LabelFrame(root, text="Hand-off files")
        files.pack(fill="x", pady=10)
        rows = [("Output folder", self.output, self.pick_output), ("Vina receptor", self.receptor, lambda: self.pick_file(self.receptor)), ("Vina ligand / peptide", self.ligand, lambda: self.pick_file(self.ligand)), ("GROMACS peptide PDB", self.peptide, lambda: self.pick_file(self.peptide))]
        for r, (label, var, cmd) in enumerate(rows):
            ttk.Label(files, text=label, width=23).grid(row=r, column=0, sticky="w", padx=8, pady=5)
            ttk.Entry(files, textvariable=var).grid(row=r, column=1, sticky="ew", padx=8, pady=5)
            ttk.Button(files, text="Browse", command=cmd).grid(row=r, column=2, padx=8, pady=5)
        files.columnconfigure(1, weight=1)

        actions = ttk.Frame(root)
        actions.pack(fill="x")
        ttk.Button(actions, text="Export Vina Package", command=self.make_vina).pack(side="left", padx=4)
        ttk.Button(actions, text="Export GROMACS Prep Folder", command=self.make_gromacs).pack(side="left", padx=4)
        ttk.Button(actions, text="Open Output Folder", command=lambda: open_path(Path(self.output.get()))).pack(side="left", padx=4)
        ttk.Label(actions, textvariable=self.status).pack(side="right", padx=4)

        note = tk.Text(root, wrap="word", height=14)
        note.pack(fill="both", expand=True, pady=(10, 0))
        note.insert("1.0", "Pepforge boundary\n\n• Structure generation is peptide-focused.\n• Vina performs external docking.\n• GROMACS performs external molecular dynamics.\n• Modified residues, D-amino acids, linkers, tags and labels require parameter review before quantitative claims.\n")
        note.configure(state="disabled")

    def pick_output(self) -> None:
        value = filedialog.askdirectory(initialdir=self.output.get() or str(DEFAULT_OUTPUT))
        if value:
            self.output.set(value)

    def pick_file(self, variable: tk.StringVar) -> None:
        value = filedialog.askopenfilename(filetypes=[("Structure files", "*.pdb *.pdbqt *.sdf *.mol2"), ("All files", "*.*")])
        if value:
            variable.set(value)

    def check_tools(self) -> None:
        self.tree.delete(*self.tree.get_children())
        report = detect_environment()
        labels = [("AutoDock Vina", "vina"), ("Open Babel", "openbabel"), ("GROMACS", "gromacs"), ("WSL", "wsl")]
        for label, key in labels:
            value = report[key]
            installed = bool(value) and value != "not required on native Linux/macOS"
            status = "Available" if installed else ("Not required" if value.startswith("not required") else "Not found")
            self.tree.insert("", "end", values=(label, status, value))
        self.status.set("Environment checked")

    def make_vina(self) -> None:
        folder = export_vina_package(Path(self.output.get()), self.receptor.get(), self.ligand.get())
        self.status.set(f"Vina package: {folder.name}")
        messagebox.showinfo("Vina package", f"Created:\n{folder}")

    def make_gromacs(self) -> None:
        folder = export_gromacs_package(Path(self.output.get()), self.peptide.get())
        self.status.set(f"GROMACS prep: {folder.name}")
        messagebox.showinfo("GROMACS preparation", f"Created:\n{folder}")


def main() -> None:
    ExternalToolsGuide().mainloop()


if __name__ == "__main__":
    main()
