from __future__ import annotations
import os
import sys
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
        self.title("Hot Spot Finder")
        self.geometry("1160x720")
        self.minsize(980, 600)
        self.q = queue.Queue()
        self.last_outdir = None
        self._build()
        self.after(120, self._poll)

    def _build(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Hot Spot Finder", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="FASTA/text 서열에서 hotspot 후보 구간만 선별해 (14K) 형식으로 표시하고 저장합니다.").pack(anchor="w", pady=(4, 4))
        explain = ttk.Labelframe(main, text="What is a hotspot? / Hotspot 의미", padding=8)
        explain.pack(fill="x", pady=(0, 10))
        ttk.Label(
            explain,
            text="Hotspot은 결합·기능·표면 노출·보존성·전하/소수성 패턴 때문에 후보 peptide 설계에서 우선 검토할 만한 서열 구간입니다. 이 점수는 실험적으로 검증된 결합 증거가 아니라, downstream Peptide Design Engine에 넘길 후보 구간을 고르는 hypothesis-generating score입니다.",
            wraplength=850,
            justify="left",
        ).pack(anchor="w")

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
        ttk.Button(btns, text="Load example input", command=lambda: self.input_path.set(str(APP / "examples" / "example_input.fasta"))).pack(side="left")

        paned = ttk.PanedWindow(main, orient="vertical")
        paned.pack(fill="both", expand=True)
        input_frame = ttk.Labelframe(paned, text="Input preview / direct edit")
        self.text = tk.Text(input_frame, height=14, wrap="word")
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        paned.add(input_frame, weight=2)
        result_frame = ttk.Labelframe(paned, text="Hot spots only / 계산된 hotspot 결과만 표시")
        result_frame.rowconfigure(0, weight=1); result_frame.columnconfigure(0, weight=1)
        self.result_tabs = ttk.Notebook(result_frame)
        self.result_tabs.grid(row=0, column=0, sticky="nsew")
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
        self.result_tabs.add(hot_tab, text="Hot spots")
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
            messagebox.showwarning("No input", "서열 입력 또는 파일을 선택하세요."); return
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
            return "No hotspot candidates were produced."
        work = df.copy()
        pos_col = "original_position" if "original_position" in work.columns else ("display_position" if "display_position" in work.columns else "model_position")
        aa_col = "input_token" if "input_token" in work.columns else ("base_token" if "base_token" in work.columns else "model_token")
        if pos_col not in work.columns or aa_col not in work.columns:
            return "Hotspot output did not include residue position/token columns."
        work[pos_col] = pd.to_numeric(work[pos_col], errors="coerce")
        work = work.dropna(subset=[pos_col]).copy()
        if work.empty:
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
                    "basis": "local window/context score",
                })
                if len(selected) >= top_n:
                    break
            if len(selected) >= top_n:
                break
        if not selected:
            return "No hotspot passed the current filter. Try increasing Top N or lowering Min score."
        selected = sorted(selected, key=lambda x: x["score"], reverse=True)[:top_n]
        rows = []
        # Fixed-width display for readable aligned output.
        # The GUI intentionally shows only hotspot candidates, not the full residue table.
        header = f"{'rank':>4}  {'hotspot residue(s)':<92}  {'center':<10}  {'score':>7}  {'basis'}"
        lines = [header, "-" * len(header)]
        for i, item in enumerate(selected, start=1):
            score = f"{item['score']:.4f}"
            hotspot_text = str(item['hotspot'])[:92]
            center_text = str(item['center'])[:10]
            basis_text = str(item['basis'])
            lines.append(f"{i:>4}  {hotspot_text:<92}  {center_text:<10}  {score:>7}  {basis_text}")
            rows.append({"rank": i, "hotspot_residues": item["hotspot"], "center": item["center"], "score": score, "basis": item["basis"]})
        try:
            out = Path(self.outdir.get()); out.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(out / "hotspot_top_display_only.csv", index=False, encoding="utf-8-sig")
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

    def open_output(self):
        p = self.last_outdir or Path(self.outdir.get())
        if p.exists(): open_path(p)
        else: messagebox.showinfo("Not found", str(p))


def main():
    app = HotspotGUI(); app.mainloop()

if __name__ == "__main__":
    main()
