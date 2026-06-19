from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"

from peptiforg_core.project_io import new_project, load_project, save_project, relpath
from peptiforg_core.workflow_schema import SELECTED_HOTSPOT_COLUMNS, SELECTED_CANDIDATE_COLUMNS


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
        self.root.geometry("900x720")
        self.root.minsize(820, 640)
        self.project_dir: Path | None = None
        self._build()

    def _build(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Sec.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=6)

        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Pepforge Workflow Mode", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Standalone modules remain available. Workflow Mode connects Hotspot -> Design -> Docking -> SPPS using project/session files and exported tables.", wraplength=830).pack(anchor="w", pady=(6, 14))

        proj = ttk.LabelFrame(main, text="1. Project / Session", padding=12)
        proj.pack(fill="x", pady=6)
        row = ttk.Frame(proj); row.pack(fill="x")
        ttk.Label(row, text="Project name").pack(side="left")
        self.name_var = tk.StringVar(value="Pepforge_Project")
        ttk.Entry(row, textvariable=self.name_var, width=36).pack(side="left", padx=8)
        ttk.Button(row, text="Create new project", command=self.create_project).pack(side="left", padx=4)
        ttk.Button(row, text="Open existing project", command=self.open_project).pack(side="left", padx=4)
        ttk.Button(row, text="Open project folder", command=self.open_project_folder).pack(side="left", padx=4)
        self.project_label = ttk.Label(proj, text="Current project: none")
        self.project_label.pack(anchor="w", pady=(8,0))

        seqbox = ttk.LabelFrame(main, text="2. Shared Input Sequence", padding=12)
        seqbox.pack(fill="both", expand=False, pady=6)
        self.seq_text = tk.Text(seqbox, height=5, wrap="word")
        self.seq_text.insert("1.0", "DELIKFVRWA")
        self.seq_text.pack(fill="both", expand=True)
        ttk.Button(seqbox, text="Save sequence to project", command=self.save_sequence).pack(anchor="e", pady=(8,0))

        steps = ttk.LabelFrame(main, text="3. Connected Workflow Actions", padding=12)
        steps.pack(fill="x", pady=6)
        ttk.Label(steps, text="Hot Spot Finder -> Peptide Design Engine", style="Sec.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(steps, text="Run Hotspot and save outputs", command=self.run_hotspot).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(steps, text="Create selected_hotspots_for_design.csv", command=self.create_hotspot_transfer).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(steps, text="Open standalone Hot Spot Finder", command=lambda: self.launch_tool("hotspot")).grid(row=1, column=2, sticky="ew", padx=4, pady=4)

        ttk.Label(steps, text="Peptide Design Engine -> Docking Workbench -> SPPS Planner", style="Sec.TLabel").grid(row=2, column=0, sticky="w", pady=(10,0))
        self.candidate_var = tk.StringVar(value="Ac-EEMQRR-NH2")
        ttk.Entry(steps, textvariable=self.candidate_var, width=38).grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(steps, text="Save selected candidate", command=self.save_candidate).grid(row=3, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(steps, text="Open standalone Design Engine", command=lambda: self.launch_tool("design")).grid(row=3, column=2, sticky="ew", padx=4, pady=4)

        ttk.Label(steps, text="SPPS Planning", style="Sec.TLabel").grid(row=4, column=0, sticky="w", pady=(10,0))
        srow = ttk.Frame(steps); srow.grid(row=5, column=0, columnspan=3, sticky="ew")
        ttk.Label(srow, text="Resin").pack(side="left")
        self.resin_var = tk.StringVar(value="Amide")
        ttk.Combobox(srow, textvariable=self.resin_var, values=["Amide", "Rink Amide", "CTC/Trityl", "2-CTC"], width=16).pack(side="left", padx=6)
        ttk.Label(srow, text="Scale mmol").pack(side="left")
        self.scale_var = tk.StringVar(value="400")
        ttk.Entry(srow, textvariable=self.scale_var, width=10).pack(side="left", padx=6)
        ttk.Button(srow, text="Run SPPS plan on selected candidate", command=self.run_spps).pack(side="left", padx=6)
        ttk.Button(srow, text="Open standalone SPPS Planner", command=lambda: self.launch_tool("spps")).pack(side="left", padx=6)
        for col in range(3): steps.columnconfigure(col, weight=1)

        logbox = ttk.LabelFrame(main, text="Status", padding=12)
        logbox.pack(fill="both", expand=True, pady=6)
        self.log = tk.Text(logbox, height=9, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.write_log("Workflow Mode ready. Create or open a project first.")

    def write_log(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def require_project(self) -> Path | None:
        if self.project_dir is None:
            messagebox.showwarning("No project", "Create or open a Pepforge project first.")
            return None
        return self.project_dir

    def set_project(self, folder: Path):
        self.project_dir = folder
        self.project_label.configure(text=f"Current project: {folder}")
        try:
            p = load_project(folder)
            self.seq_text.delete("1.0", "end")
            self.seq_text.insert("1.0", p.get("input_sequence", ""))
            cands = p.get("selected_candidates", [])
            if cands:
                self.candidate_var.set(cands[-1].get("sequence", self.candidate_var.get()))
        except Exception:
            pass
        self.write_log(f"Project set: {folder}")

    def create_project(self):
        seq = self.seq_text.get("1.0", "end").strip()
        folder = new_project(self.name_var.get(), seq)
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

    def run_hotspot(self):
        folder = self.require_project()
        if not folder: return
        self.save_sequence()
        seq = self.seq_text.get("1.0", "end").strip()
        if not seq:
            messagebox.showwarning("Empty sequence", "Input sequence is empty.")
            return
        try:
            sys.path.insert(0, str(APPS / "hotspot_finder"))
            from sequence_hotspot_finder.engine import analyze_input
            outdir = folder / "hotspot"
            token_db = APPS / "hotspot_finder" / "data" / "token_db.csv"
            sidechain = APPS / "hotspot_finder" / "data" / "sidechain_mod_db.csv"
            result = analyze_input(seq, token_db_path=token_db, sidechain_mod_db_path=sidechain, outdir=outdir, config={"use_esm": False, "top_n": 30})
            p = load_project(folder)
            p.setdefault("output_files", {})["hotspot_full_csv"] = relpath(folder, result["full_csv"])
            p.setdefault("output_files", {})["hotspot_top_csv"] = relpath(folder, result["top_csv"])
            p.setdefault("output_files", {})["hotspot_zip"] = relpath(folder, result["zip_path"])
            top_df = result.get("top_df")
            p["hotspot_results"] = [] if top_df is None else top_df.head(30).fillna("").to_dict("records")
            if top_df is not None and not top_df.empty:
                row = top_df.iloc[0].fillna("").to_dict()
                pos = row.get("model_position", row.get("position", ""))
                token = str(row.get("token", row.get("aa", row.get("residue", ""))))
                p["selected_hotspots"] = [{"region_start": pos, "region_end": pos, "sequence": token, "hotspot_score": row.get("hotspot_score", ""), "record_name": row.get("record_name", ""), "note": "Auto-selected top row; edit CSV/project.json if needed."}]
            save_project(folder, p)
            self.write_log(f"Hotspot analysis completed. Outputs saved in: {outdir}")
        except Exception as e:
            messagebox.showerror("Hotspot run failed", str(e))
            self.write_log(f"Hotspot run failed: {type(e).__name__}: {e}")

    def create_hotspot_transfer(self):
        folder = self.require_project()
        if not folder: return
        p = load_project(folder)
        rows = p.get("selected_hotspots") or []
        if not rows:
            seq = self.seq_text.get("1.0", "end").strip()
            rows = [{"region_start": "", "region_end": "", "sequence": seq, "hotspot_score": "", "record_name": "manual", "note": "Manual transfer row"}]
            p["selected_hotspots"] = rows
        out = folder / "design" / "selected_hotspots_for_design.csv"
        out.parent.mkdir(exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=SELECTED_HOTSPOT_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in SELECTED_HOTSPOT_COLUMNS})
        p.setdefault("output_files", {})["selected_hotspots_for_design"] = relpath(folder, out)
        save_project(folder, p)
        self.write_log(f"Created Design transfer file: {out}")

    def save_candidate(self):
        folder = self.require_project()
        if not folder: return
        seq = self.candidate_var.get().strip()
        if not seq:
            messagebox.showwarning("Empty candidate", "Candidate sequence is empty.")
            return
        p = load_project(folder)
        cand = {"candidate_id": f"P{len(p.get('selected_candidates', []))+1:03d}", "sequence": seq, "core_sequence": "", "modifications": "", "rank": len(p.get('selected_candidates', []))+1, "score_total": "", "note": "Manual or Design Engine selected candidate"}
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

    def run_spps(self):
        folder = self.require_project()
        if not folder: return
        seq = self.candidate_var.get().strip()
        if not seq:
            messagebox.showwarning("Empty candidate", "Candidate sequence is empty.")
            return
        try:
            sys.path.insert(0, str(APPS / "spps_planner_app"))
            from spps_planner.engine import PlanInput
            from spps_planner.export import export_csvs, export_excel
            scale = float(self.scale_var.get())
            inp = PlanInput(sequence=seq, resin=self.resin_var.get(), scale_mmol=scale)
            outdir = folder / "spps"
            outdir.mkdir(exist_ok=True)
            export_csvs(inp, outdir)
            xlsx = outdir / "spps_planning_workbook.xlsx"
            export_excel(inp, xlsx)
            p = load_project(folder)
            p["spps_settings"] = {"sequence": seq, "resin_type": self.resin_var.get(), "scale_mmol": scale}
            p.setdefault("output_files", {}).update({
                "spps_summary": "spps/summary.csv",
                "spps_step_matrix": "spps/step_matrix.csv",
                "spps_synthesis_form": "spps/synthesis_form_wash_by_wash.csv",
                "spps_raw_material_use": "spps/raw_material_use.csv",
                "spps_workbook": "spps/spps_planning_workbook.xlsx"
            })
            save_project(folder, p)
            self.write_log(f"SPPS planning completed. Outputs saved in: {outdir}")
        except Exception as e:
            messagebox.showerror("SPPS run failed", str(e))
            self.write_log(f"SPPS run failed: {type(e).__name__}: {e}")

    def launch_tool(self, tool: str):
        try:
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--tool", tool]
            else:
                cmd = [sys.executable, str(ROOT / "main_launcher.py"), "--tool", tool]
            subprocess.Popen(cmd, cwd=str(ROOT))
        except Exception as e:
            messagebox.showerror("Launch failed", str(e))

    def mainloop(self):
        self.root.mainloop()


def main():
    WorkflowApp().mainloop()


if __name__ == "__main__":
    main()
