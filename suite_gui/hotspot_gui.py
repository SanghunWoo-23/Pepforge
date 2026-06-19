from __future__ import annotations
import os
import sys
import threading
import queue
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "hotspot_finder"
PKG = APP
sys.path.insert(0, str(PKG))

from sequence_hotspot_finder.engine import analyze_input, load_config


def open_path(path: Path):
    import subprocess
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class HotspotGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pepforge Hotspot Finder")
        set_pepforge_icon(self)
        self.geometry("1280x800")
        self.minsize(980, 600)
        self.q = queue.Queue()
        self.last_outdir = None
        self._build()
        self.after(120, self._poll)

    def _build(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Hot Spot Finder", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Excel-like hotspot table, cluster view, token-aware motif export, and CSV/XLSX output.").pack(anchor="w", pady=(4, 8))

        top = ttk.Frame(main)
        top.pack(fill="x")
        self.input_path = tk.StringVar(value=str(APP / "examples" / "example_input.fasta"))
        self.outdir = tk.StringVar(value=str(ROOT / "outputs" / "hotspot_run"))
        self.use_esm = tk.BooleanVar(value=False)
        self.window = tk.IntVar(value=15)
        self.overlap = tk.IntVar(value=5)
        self.top_n = tk.IntVar(value=30)
        self.min_score = tk.DoubleVar(value=0.0)

        def row(label, widget, button=None):
            f = ttk.Frame(top); f.pack(fill="x", pady=3)
            ttk.Label(f, text=label, width=16).pack(side="left")
            widget.pack(side="left", fill="x", expand=True)
            if button: button.pack(side="left", padx=(6, 0))

        row("Input file", ttk.Entry(top, textvariable=self.input_path), ttk.Button(top, text="Browse", command=self.browse_input))
        row("Output folder", ttk.Entry(top, textvariable=self.outdir), ttk.Button(top, text="Browse", command=self.browse_outdir))
        opt = ttk.Frame(top); opt.pack(fill="x", pady=6)
        ttk.Checkbutton(opt, text="Use ESM (optional, slower)", variable=self.use_esm).pack(side="left")
        ttk.Label(opt, text="Window").pack(side="left", padx=(20, 4)); ttk.Spinbox(opt, from_=3, to=80, textvariable=self.window, width=6).pack(side="left")
        ttk.Label(opt, text="Overlap").pack(side="left", padx=(12, 4)); ttk.Spinbox(opt, from_=0, to=40, textvariable=self.overlap, width=6).pack(side="left")
        ttk.Label(opt, text="Top N").pack(side="left", padx=(12, 4)); ttk.Spinbox(opt, from_=1, to=200, textvariable=self.top_n, width=6).pack(side="left")
        ttk.Label(opt, text="Min score").pack(side="left", padx=(12, 4)); ttk.Entry(opt, textvariable=self.min_score, width=7).pack(side="left")

        btns = ttk.Frame(main); btns.pack(fill="x", pady=(10, 8))
        ttk.Button(btns, text="Run analysis", command=self.run).pack(side="left")
        ttk.Button(btns, text="Open output folder", command=self.open_output).pack(side="left", padx=8)
        ttk.Button(btns, text="Export Display XLSX", command=self.export_display).pack(side="left", padx=8)
        ttk.Button(btns, text="Export PyMOL PDB", command=self.export_pymol_hotspots).pack(side="left", padx=8)
        ttk.Button(btns, text="Export Motif Hints", command=self.export_motif_hints).pack(side="left", padx=8)
        ttk.Button(btns, text="Load example input", command=lambda: self.input_path.set(str(APP / "examples" / "example_input.fasta"))).pack(side="left")

        paned = ttk.PanedWindow(main, orient="vertical")
        paned.pack(fill="both", expand=True)
        input_frame = ttk.Labelframe(paned, text="Input preview / direct edit")
        self.text = tk.Text(input_frame, height=14, wrap="word")
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        paned.add(input_frame, weight=2)
        result_frame = ttk.Labelframe(paned, text="Hot spots only")
        result_frame.rowconfigure(0, weight=1); result_frame.columnconfigure(0, weight=1)
        self.result_tabs = ttk.Notebook(result_frame)
        self.result_tabs.grid(row=0, column=0, sticky="nsew")
        table_tab = ttk.Frame(self.result_tabs)
        table_tab.rowconfigure(0, weight=1); table_tab.columnconfigure(0, weight=1)
        self.hotspot_columns = ["rank", "hotspot_residues", "center", "score", "why_hotspot", "basis"]
        self.hotspot_tree = ttk.Treeview(table_tab, columns=self.hotspot_columns, show="headings")
        for c in self.hotspot_columns:
            self.hotspot_tree.heading(c, text=c)
            self.hotspot_tree.column(c, width=260 if c == "why_hotspot" else (180 if c != "hotspot_residues" else 520), minwidth=70, stretch=True, anchor="w")
        hy = ttk.Scrollbar(table_tab, orient="vertical", command=self.hotspot_tree.yview)
        hx = ttk.Scrollbar(table_tab, orient="horizontal", command=self.hotspot_tree.xview)
        self.hotspot_tree.configure(yscrollcommand=hy.set, xscrollcommand=hx.set)
        self.hotspot_tree.grid(row=0, column=0, sticky="nsew"); hy.grid(row=0, column=1, sticky="ns"); hx.grid(row=1, column=0, sticky="ew")
        self.result_tabs.add(table_tab, text="Hotspot Table")
        # Hotspot output is a fixed-width text table. Scrollbars are required
        # because hotspot-region strings can be wider than the visible window.
        hot_tab = ttk.Frame(self.result_tabs)
        hot_tab.rowconfigure(0, weight=1)
        hot_tab.columnconfigure(0, weight=1)
        self.top_output = tk.Text(hot_tab, height=10, wrap="none")
        self.top_output.configure(font=("Consolas", 9))
        hot_y = ttk.Scrollbar(hot_tab, orient="vertical", command=self.top_output.yview)
        hot_x = ttk.Scrollbar(hot_tab, orient="horizontal", command=self.top_output.xview)
        self.top_output.configure(yscrollcommand=hot_y.set, xscrollcommand=hot_x.set)
        self.top_output.grid(row=0, column=0, sticky="nsew")
        hot_y.grid(row=0, column=1, sticky="ns")
        hot_x.grid(row=1, column=0, sticky="ew")
        self.log = tk.Text(self.result_tabs, height=10, wrap="word")
        self.result_tabs.add(hot_tab, text="Formatted Text")
        self.result_tabs.add(self.log, text="Log")
        paned.add(result_frame, weight=2)
        self.load_input_preview()

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("Sequence files", "*.fasta *.fa *.txt"), ("All files", "*.*")])
        if p:
            self.input_path.set(p); self.load_input_preview()

    def browse_outdir(self):
        p = filedialog.askdirectory()
        if p: self.outdir.set(p)

    def load_input_preview(self):
        try:
            txt = Path(self.input_path.get()).read_text(encoding="utf-8")
            self.text.delete("1.0", "end"); self.text.insert("1.0", txt)
        except Exception:
            pass

    def run(self):
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("No input", "Enter a sequence or choose an input file."); return
        outdir = Path(self.outdir.get())
        outdir.mkdir(parents=True, exist_ok=True)
        tmp_input = outdir / "_hotspot_input.txt"
        tmp_input.write_text(text, encoding="utf-8")
        self.log.insert("end", "Running hotspot analysis...\n"); self.log.see("end")
        threading.Thread(target=self._worker, args=(tmp_input, outdir), daemon=True).start()

    def _worker(self, input_file: Path, outdir: Path):
        try:
            cfg = load_config(str(APP / "data" / "default_config.json"))
            cfg["use_esm"] = bool(self.use_esm.get())
            cfg["window_size"] = int(self.window.get())
            cfg["overlap"] = int(self.overlap.get())
            cfg["top_n"] = int(self.top_n.get())
            result = analyze_input(
                user_input=input_file.read_text(encoding="utf-8"),
                config=cfg,
                token_db_path=str(APP / "data" / "token_db.csv"),
                sidechain_mod_db_path=str(APP / "data" / "sidechain_mod_db.csv"),
                outdir=str(outdir),
            )
            self.q.put(("done", result))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "done":
                    self.last_outdir = Path(self.outdir.get())
                    r = item[1]
                    self.log.insert("end", f"Done.\nFull CSV: {r.get('full_csv')}\nTop CSV: {r.get('top_csv')}\nZIP: {r.get('zip_path')}\n")
                    self._load_output_preview(r)
                    self.log.see("end")
                    messagebox.showinfo("Complete", "Hotspot analysis complete.")
                else:
                    self.log.insert("end", "ERROR: " + item[1] + "\n")
                    self.log.see("end")
                    messagebox.showerror("Error", item[1])
        except queue.Empty:
            pass
        self.after(120, self._poll)


    def _why_hotspot_reason(self, region, center_row):
        try:
            charge = float(region.get("_charge_density", 0).mean()) if "_charge_density" in region else 0.0
            arom = float(region.get("_arom_density", 0).mean()) if "_arom_density" in region else 0.0
            local = float(region.get("_local_density", 0).mean()) if "_local_density" in region else 0.0
            bal = float(region.get("_local_balanced", 0).mean()) if "_local_balanced" in region else 0.0
            aa = str(center_row.get("amino_acid", center_row.get("residue", ""))).upper()
            reasons = []
            if charge >= 0.35:
                reasons.append("charged cluster")
            if arom >= 0.22:
                reasons.append("aromatic enrichment")
            if local >= 0.35:
                reasons.append("contact-like residue density")
            if bal >= 0.22:
                reasons.append("balanced local context")
            if aa in ("K", "R", "D", "E", "H"):
                reasons.append("charged center")
            elif aa in ("F", "W", "Y"):
                reasons.append("aromatic center")
            elif aa == "C":
                reasons.append("special Cys context")
            return "; ".join(dict.fromkeys(reasons)) or "local window/context score"
        except Exception:
            return "local window/context score"

    def _format_hotspot_table(self, df):
        """Display only compact hotspot regions, not the full residue table.

        Output format is intentionally short: hotspot residues are shown as
        position+amino-acid tokens such as (14K), (17Y), (19R).
        The scoring uses local window context and de-emphasizes isolated Y/C
        so a single aromatic/cysteine residue does not dominate every result.
        """
        try:
            import pandas as pd
            import numpy as np
        except Exception:
            return "pandas/numpy are required to format hotspot output."
        if df is None or len(df) == 0:
            self._last_hotspot_rows = []
            return "No hotspot candidates were produced."
        work = df.copy()
        pos_col = "original_position" if "original_position" in work.columns else ("display_position" if "display_position" in work.columns else "model_position")
        aa_col = "input_token" if "input_token" in work.columns else ("base_token" if "base_token" in work.columns else "model_token")
        if pos_col not in work.columns or aa_col not in work.columns:
            self._last_hotspot_rows = []
            return "Hotspot output did not include residue position/token columns."
        work[pos_col] = pd.to_numeric(work[pos_col], errors="coerce")
        work = work.dropna(subset=[pos_col]).copy()
        if work.empty:
            self._last_hotspot_rows = []
            return "No valid residue positions were found in hotspot output."
        work[pos_col] = work[pos_col].astype(int)
        for c in ["hotspot_score", "rule_score", "conservation_score", "structure_score", "supervised_score", "esm_embedding_score"]:
            if c in work.columns:
                work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
            else:
                work[c] = 0.0
        # Feature flags. These are deliberately balanced; aromatic/Cys are useful
        # but not enough to become a hotspot alone.
        for c in ["aromatic_flag", "positive_flag", "negative_flag", "polar_flag", "special_flag", "abs_charge", "hydrophobicity_norm"]:
            if c in work.columns:
                work[c] = pd.to_numeric(work[c], errors="coerce").fillna(0.0)
            else:
                work[c] = 0.0
        aa = work[aa_col].astype(str).str.upper()
        work["_is_yc"] = aa.isin(["Y", "C"]).astype(float)
        work["_is_c"] = aa.eq("C").astype(float)
        work["_is_y"] = aa.eq("Y").astype(float)
        work["_is_strong_contact_like"] = aa.isin(["K", "R", "D", "E", "W", "F", "Y", "H", "C", "P"]).astype(float)
        # Start from existing score if available, but mix it with balanced sequence context.
        raw = work["hotspot_score"].astype(float)
        if float(raw.max()) > float(raw.min()):
            work["_raw_norm"] = (raw - raw.min()) / (raw.max() - raw.min())
        else:
            work["_raw_norm"] = raw.clip(0, 1)
        work["_balanced_residue"] = (
            0.20 * work["positive_flag"] +
            0.20 * work["negative_flag"] +
            0.18 * work["aromatic_flag"] +
            0.13 * work["polar_flag"] +
            0.10 * work["abs_charge"].clip(0, 1) +
            0.08 * work["_is_strong_contact_like"] +
            0.06 * work["special_flag"] +
            0.05 * (1.0 - (work["hydrophobicity_norm"] - 0.55).abs().clip(0, 1))
        )
        # Clamp isolated Y/C contribution: they should help only if supported by a local region.
        work["_balanced_residue"] = work["_balanced_residue"] - 0.10 * work["_is_yc"]
        work["_balanced_residue"] = work["_balanced_residue"].clip(lower=0.0)
        try:
            top_n = max(1, int(self.top_n.get()))
        except Exception:
            top_n = 20
        try:
            min_score = float(self.min_score.get())
        except Exception:
            min_score = 0.0
        try:
            window_size = max(5, int(self.window.get()))
        except Exception:
            window_size = 9
        half = max(2, min(8, window_size // 2))
        min_distance = max(3, half)
        selected = []
        group_key = "record_name" if "record_name" in work.columns else None
        grouped = work.groupby(group_key) if group_key else [("input", work)]
        for record, g in grouped:
            g = g.sort_values(pos_col).reset_index(drop=True).copy()
            # Window scores are based on neighborhoods, not single residues.
            g["_local_balanced"] = g["_balanced_residue"].rolling(2*half+1, center=True, min_periods=1).mean()
            g["_local_density"] = g["_is_strong_contact_like"].rolling(2*half+1, center=True, min_periods=1).mean()
            g["_charge_density"] = (g["positive_flag"] + g["negative_flag"]).rolling(2*half+1, center=True, min_periods=1).mean()
            g["_arom_density"] = g["aromatic_flag"].rolling(2*half+1, center=True, min_periods=1).mean()
            g["_yc_density"] = g["_is_yc"].rolling(2*half+1, center=True, min_periods=1).mean()
            g["_composite"] = (
                0.30 * g["_raw_norm"] +
                0.34 * g["_local_balanced"] +
                0.16 * g["_local_density"] +
                0.12 * g["_charge_density"] +
                0.08 * g["_arom_density"]
            )
            # Penalize isolated Y/C peaks unless local context is also strong.
            isolated_yc = (g["_is_yc"] > 0) & (g["_local_density"] < 0.30) & (g["_charge_density"] < 0.15)
            g.loc[isolated_yc, "_composite"] *= 0.62
            if min_score > 0:
                g = g[g["_composite"] >= min_score].copy()
            if g.empty:
                continue
            used = []
            for _, row in g.sort_values("_composite", ascending=False).iterrows():
                center_pos = int(row[pos_col])
                if any(abs(center_pos - u) < min_distance for u in used):
                    continue
                region = g[(g[pos_col] >= center_pos-half) & (g[pos_col] <= center_pos+half)].copy()
                if region.empty:
                    continue
                # choose only a few representative residues, not full sequence
                region["_token_score"] = 0.55*region["_balanced_residue"] + 0.30*region["_raw_norm"] + 0.15*region["_is_strong_contact_like"]
                reps = region.sort_values("_token_score", ascending=False).head(5).sort_values(pos_col)
                tokens = []
                for _, rr in reps.iterrows():
                    tokens.append(f"({int(rr[pos_col])}{str(rr.get(aa_col,''))})")
                if not tokens:
                    continue
                used.append(center_pos)
                selected.append({
                    "record": record,
                    "hotspot": ", ".join(tokens),
                    "center": f"({center_pos}{str(row.get(aa_col,''))})",
                    "score": float(row["_composite"]),
                    "why_hotspot": self._why_hotspot_reason(region, row),
                    "basis": "local window/context score",
                })
                if len(selected) >= top_n:
                    break
            if len(selected) >= top_n:
                break
        if not selected:
            self._last_hotspot_rows = []
            return "No hotspot passed the current filter. Try increasing Top N or lowering Min score."
        selected = sorted(selected, key=lambda x: x["score"], reverse=True)[:top_n]
        rows = []
        # Fixed-width display for readable aligned output.
        # The GUI intentionally shows only hotspot candidates, not the full residue table.
        header = f"{'rank':>4}  {'hotspot residue(s)':<80}  {'center':<10}  {'score':>7}  {'why hotspot':<34}  {'basis'}"
        lines = [header, "-" * len(header)]
        for i, item in enumerate(selected, start=1):
            score = f"{item['score']:.4f}"
            hotspot_text = str(item['hotspot'])[:80]
            center_text = str(item['center'])[:10]
            basis_text = str(item['basis'])
            lines.append(f"{i:>4}  {hotspot_text:<80}  {center_text:<10}  {score:>7}  {str(item.get('why_hotspot',''))[:34]:<34}  {basis_text}")
            rows.append({"rank": i, "hotspot_residues": item["hotspot"], "center": item["center"], "score": score, "why_hotspot": item.get("why_hotspot", "local context"), "basis": item["basis"]})
        try:
            out = Path(self.outdir.get()); out.mkdir(parents=True, exist_ok=True)
            self._last_hotspot_rows = rows
            pd.DataFrame(rows).to_csv(out / "hotspot_top_display_only.csv", index=False, encoding="utf-8-sig")
            try:
                self._write_hotspot_pymol_files(out)
            except Exception:
                pass
        except Exception:
            pass
        return "\n".join(lines)

    def _load_output_preview(self, result: dict):
        self.top_output.delete("1.0", "end")
        df = None
        try:
            import pandas as pd
            full_csv = result.get("full_csv")
            top_csv = result.get("top_csv")
            if full_csv and Path(full_csv).exists():
                df = pd.read_csv(full_csv)
            elif top_csv and Path(top_csv).exists():
                df = pd.read_csv(top_csv)
            else:
                df = result.get("top_df")
        except Exception:
            df = result.get("top_df")
        try:
            txt = self._format_hotspot_table(df)
        except Exception as e:
            txt = f"Failed to format hotspot output: {e}"
        self.top_output.insert("1.0", txt)
        self._write_hotspot_tree()

    def _write_hotspot_tree(self):
        try:
            self.hotspot_tree.delete(*self.hotspot_tree.get_children())
            for r in getattr(self, "_last_hotspot_rows", []):
                self.hotspot_tree.insert("", "end", values=[r.get(c, "") for c in self.hotspot_columns])
        except Exception:
            pass


    def _extract_sequence_for_pdb(self) -> tuple[str, str]:
        """Return a simple record name and canonical AA sequence for hotspot PDB export."""
        raw = self.text.get("1.0", "end").strip()
        name = "Pepforge_hotspot_sequence"
        seq_parts = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                name = re.sub(r"[^A-Za-z0-9_.-]+", "_", line[1:].strip() or name)[:40]
                continue
            seq_parts.append(line)
        seq_raw = "".join(seq_parts).upper()
        # Keep only canonical one-letter amino-acid symbols for the pseudo-CA model.
        # Modified tokens are represented in the CSV/table outputs; the PyMOL hotspot
        # pseudo-PDB is meant for residue-position visualization.
        seq = "".join(ch for ch in seq_raw if ch in "ACDEFGHIKLMNPQRSTVWY")
        return name, seq

    def _hotspot_position_set(self) -> set[int]:
        rows = getattr(self, "_last_hotspot_rows", []) or []
        pos = set()
        for r in rows:
            for m in re.finditer(r"\((\d+)([A-Za-z])\)", str(r.get("hotspot_residues", ""))):
                try:
                    pos.add(int(m.group(1)))
                except Exception:
                    pass
            for m in re.finditer(r"\((\d+)([A-Za-z])\)", str(r.get("center", ""))):
                try:
                    pos.add(int(m.group(1)))
                except Exception:
                    pass
        return pos

    def _write_hotspot_pymol_files(self, out: Path) -> dict[str, Path]:
        """Write a PyMOL-friendly pseudo-PDB and coloring script.

        PDB files do not reliably store display colors by themselves. Therefore
        Pepforge writes both:
          1. hotspot_pymol_colored.pdb with hotspot residues marked by chain H
             and high B-factor values, and
          2. hotspot_pymol_color_hotspots.pml, which PyMOL can run to color the
             hotspot residues directly.

        Dragging the PDB into PyMOL will show the hotspot residues as a separate
        chain in many default views. For explicit coloring, drag/run the PML file
        after loading the PDB.
        """
        out.mkdir(parents=True, exist_ok=True)
        name, seq = self._extract_sequence_for_pdb()
        hotspots = self._hotspot_position_set()
        if not seq:
            raise ValueError("No canonical amino-acid sequence was available for PDB export.")
        if not hotspots:
            raise ValueError("No hotspot residues were available. Run analysis first.")
        aa3 = {
            "A":"ALA","R":"ARG","N":"ASN","D":"ASP","C":"CYS","Q":"GLN","E":"GLU","G":"GLY","H":"HIS","I":"ILE",
            "L":"LEU","K":"LYS","M":"MET","F":"PHE","P":"PRO","S":"SER","T":"THR","W":"TRP","Y":"TYR","V":"VAL",
        }
        pdb_path = out / "hotspot_pymol_colored.pdb"
        pml_path = out / "hotspot_pymol_color_hotspots.pml"
        csv_path = out / "hotspot_pymol_residue_map.csv"
        lines = []
        lines.append("REMARK Pepforge hotspot visualization pseudo-PDB")
        lines.append(f"REMARK Source record: {name}")
        lines.append("REMARK Hotspot residues are marked with chain H and B-factor 100.00")
        lines.append("REMARK Non-hotspot residues are marked with chain A and B-factor 10.00")
        atom_id = 1
        map_rows = ["position,residue,is_hotspot,b_factor,chain"]
        for i, aa in enumerate(seq, start=1):
            is_hot = i in hotspots
            chain = "H" if is_hot else "A"
            bfac = 100.00 if is_hot else 10.00
            x = (i - 1) * 3.8
            y = 0.0 if not is_hot else 2.5
            z = 0.0
            resn = aa3.get(aa, "UNK")
            # ATOM formatting follows a minimal CA-only PDB model.
            lines.append(f"ATOM  {atom_id:5d}  CA  {resn:>3s} {chain}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00{bfac:6.2f}           C")
            map_rows.append(f"{i},{aa},{int(is_hot)},{bfac:.2f},{chain}")
            atom_id += 1
        lines.append("TER")
        lines.append("END")
        pdb_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # PyMOL coloring script. Users can run: pymol hotspot_pymol_colored.pdb hotspot_pymol_color_hotspots.pml
        hot_resi = "+".join(str(i) for i in sorted(hotspots))
        pml_lines = [
            "# Pepforge hotspot coloring script",
            "hide everything",
            "show cartoon, all",
            "show spheres, chain H",
            "color gray80, chain A",
            "color red, chain H",
            "set sphere_scale, 0.65, chain H",
            "set cartoon_transparency, 0.15, chain A",
            "select pepforge_hotspots, chain H",
            "label pepforge_hotspots and name CA, \"%s%s\" % (resi, resn)",
            "zoom all",
        ]
        if hot_resi:
            pml_lines.insert(8, f"# Hotspot residue positions: {hot_resi}")
        pml_path.write_text("\n".join(pml_lines) + "\n", encoding="utf-8")
        csv_path.write_text("\n".join(map_rows) + "\n", encoding="utf-8")
        return {"pdb": pdb_path, "pml": pml_path, "map": csv_path}

    def export_pymol_hotspots(self):
        try:
            out = Path(self.outdir.get()); out.mkdir(parents=True, exist_ok=True)
            paths = self._write_hotspot_pymol_files(out)
            self.last_outdir = out
            messagebox.showinfo(
                "PyMOL hotspot export complete",
                "Exported PyMOL visualization files:\n"
                f"PDB: {paths['pdb']}\n"
                f"PML: {paths['pml']}\n\n"
                "Load the PDB in PyMOL. For explicit hotspot coloring, also run or drag the PML file."
            )
        except Exception as e:
            messagebox.showerror("PyMOL export error", str(e))

    def export_display(self):
        try:
            import pandas as pd
            out = Path(self.outdir.get()); out.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(getattr(self, "_last_hotspot_rows", []))
            if df.empty:
                messagebox.showinfo("No data", "Run analysis first."); return
            df.to_csv(out / "hotspot_display_table.csv", index=False, encoding="utf-8-sig")
            df.to_excel(out / "hotspot_display_table.xlsx", index=False)
            self.last_outdir = out
            messagebox.showinfo("Export complete", f"Exported to:\n{out}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def export_motif_hints(self):
        try:
            out = Path(self.outdir.get()); out.mkdir(parents=True, exist_ok=True)
            rows = getattr(self, "_last_hotspot_rows", [])
            motifs = []
            for r in rows:
                toks = re.findall(r"\((\d+)([A-Z])\)", str(r.get("hotspot_residues", "")))
                if toks:
                    motifs.append("".join([aa for _, aa in toks[:5]]))
            p = out / "hotspot_motif_hints_for_design_engine.txt"
            p.write_text("\n".join(motifs), encoding="utf-8")
            self.last_outdir = out
            messagebox.showinfo("Motif hints exported", str(p))
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def open_output(self):
        p = self.last_outdir or Path(self.outdir.get())
        if p.exists(): open_path(p)
        else: messagebox.showinfo("Not found", str(p))


def main():
    app = HotspotGUI(); app.mainloop()

if __name__ == "__main__":
    main()
