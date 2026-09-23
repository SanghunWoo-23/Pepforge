from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)
import os
import sys
import threading
import queue
import re
import csv
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.ui_theme import apply_pepforge_theme, fit_window
from peptiforg_core.startup_runtime import StartupTrace, mark_window_visible
from peptiforg_core.sandbox_runtime import configured_output
from peptiforg_core.output_bundle import create_result_bundle, write_bundle_manifest, build_bundle_zip
from peptiforg_core.hotspot_design_transfer import export_hotspot_chemistry_profile
from peptiforg_core.hotspot_workflow_bridge import ranked_region_to_transfer, write_design_handoff
from peptiforg_core.project_io import load_project
from peptiforg_core.workflow_schema import SELECTED_HOTSPOT_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "hotspot_finder"
PKG = APP
sys.path.insert(0, str(PKG))



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
        self.title("Pepforge Hot Spot Finder")
        set_pepforge_icon(self)
        apply_pepforge_theme(self)
        fit_window(self, preferred_width=1280, preferred_height=800, minimum_width=980, minimum_height=600)
        self._startup_trace = StartupTrace("hotspot", ROOT / "workspace" / "hotspot" / "logs")
        self.q = queue.Queue()
        self.last_outdir = None
        self._workflow_project_dir = self._discover_workflow_project()
        self._last_pde_profile_path = None
        self._build()
        self._apply_workflow_context()
        mark_window_visible(self, self._startup_trace)
        self.after(120, self._poll)

    def _discover_workflow_project(self) -> Path | None:
        raw = str(os.environ.get("PEPFORGE_WORKFLOW_PROJECT", "") or "").strip()
        if not raw:
            return None
        folder = Path(raw).expanduser()
        if (folder / "project.json").exists():
            return folder
        return None

    def _apply_workflow_context(self) -> None:
        folder = self._workflow_project_dir
        if folder is None:
            return
        self.outdir.set(str(folder / "hotspot"))
        sequence = str(os.environ.get("PEPFORGE_WORKFLOW_SHARED_SEQUENCE", "") or "").strip()
        if not sequence:
            try:
                sequence = str(load_project(folder).get("input_sequence", "") or "").strip()
            except Exception:
                LOGGER.debug("Workflow project sequence could not be loaded", exc_info=True)
        if sequence:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", sequence)
        self.progress_var.set(f"Workflow linked: {folder.name}")

    def _build(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Hot Spot Finder", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main, text="Paste a protein or peptide sequence, then identify and export candidate regions.", style="Sub.TLabel").pack(anchor="w", pady=(4, 8))

        top = ttk.Frame(main)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        self.input_path = tk.StringVar(value="")
        self.outdir = tk.StringVar(value="")
        self.use_esm = tk.BooleanVar(value=False)
        self.window = tk.IntVar(value=15)
        self.overlap = tk.IntVar(value=5)
        self.top_n = tk.IntVar(value=30)
        self.min_score = tk.DoubleVar(value=0.0)

        def row(ridx, label, textvariable, button=None):
            ttk.Label(top, text=label, width=16).grid(row=ridx, column=0, sticky="w", pady=3)
            entry = ttk.Entry(top, textvariable=textvariable)
            entry.grid(row=ridx, column=1, sticky="ew", pady=3)
            if button:
                button.grid(row=ridx, column=2, sticky="e", padx=(6, 0), pady=3)
            return entry

        row(0, "Sequence file (optional)", self.input_path, ttk.Button(top, text="Browse", command=self.browse_input))
        row(1, "Output folder", self.outdir, ttk.Button(top, text="Browse", command=self.browse_outdir))
        opt = ttk.Frame(top); opt.grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Checkbutton(opt, text="Use ESM (optional, slower)", variable=self.use_esm).pack(side="left")
        ttk.Label(opt, text="Ranking window").pack(side="left", padx=(20, 4)); ttk.Spinbox(opt, from_=3, to=80, textvariable=self.window, width=6).pack(side="left")
        ttk.Label(opt, text="Overlap").pack(side="left", padx=(12, 4)); ttk.Spinbox(opt, from_=0, to=40, textvariable=self.overlap, width=6).pack(side="left")
        ttk.Label(opt, text="Top N").pack(side="left", padx=(12, 4)); ttk.Spinbox(opt, from_=1, to=200, textvariable=self.top_n, width=6).pack(side="left")
        ttk.Label(opt, text="Min priority").pack(side="left", padx=(12, 4)); ttk.Entry(opt, textvariable=self.min_score, width=7).pack(side="left")

        btns = ttk.Frame(main); btns.pack(fill="x", pady=(10, 8))
        self.run_button = ttk.Button(btns, text="Analyze Sequence", command=self.run, style="Accent.TButton")
        self.run_button.pack(side="left")
        ttk.Button(btns, text="Open output folder", command=self.open_output).pack(side="left", padx=8)
        ttk.Button(btns, text="Export Display XLSX", command=self.export_display).pack(side="left", padx=8)
        ttk.Button(btns, text="Export PyMOL PDB", command=self.export_pymol_hotspots).pack(side="left", padx=8)
        ttk.Button(btns, text="Export Motif Hints", command=self.export_motif_hints).pack(side="left", padx=8)
        ttk.Button(btns, text="Load Example", command=self.load_example_input).pack(side="left")
        self.progress_var = tk.StringVar(value="Ready")
        self.progress = ttk.Progressbar(main, mode="indeterminate", style="PepforgeGreen.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(0, 2))
        ttk.Label(main, textvariable=self.progress_var).pack(anchor="w", pady=(0, 6))

        rank_bar = ttk.Frame(main)
        rank_bar.pack(fill="x", pady=(0, 8))
        ttk.Label(rank_bar, text="Ranked recommendation").pack(side="left")
        self.rank_choice_var = tk.StringVar(value="")
        self.rank_choice_combo = ttk.Combobox(rank_bar, textvariable=self.rank_choice_var, state="readonly", width=66)
        self.rank_choice_combo.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.rank_choice_combo.bind("<<ComboboxSelected>>", self._on_rank_choice)
        self.rank_detail_var = tk.StringVar(value="Run analysis to rank candidate regions.")
        ttk.Label(main, textvariable=self.rank_detail_var, style="Sub.TLabel", wraplength=1180).pack(anchor="w", pady=(0, 6))

        paned = ttk.PanedWindow(main, orient="vertical")
        paned.pack(fill="both", expand=True)
        input_frame = ttk.Labelframe(paned, text="Protein or Peptide Sequence")
        self.text = tk.Text(input_frame, height=14, wrap="word")
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        paned.add(input_frame, weight=2)
        result_frame = ttk.Labelframe(paned, text="Candidate Regions")
        result_frame.rowconfigure(0, weight=1); result_frame.columnconfigure(0, weight=1)
        self.result_tabs = ttk.Notebook(result_frame)
        self.result_tabs.grid(row=0, column=0, sticky="nsew")
        table_tab = ttk.Frame(self.result_tabs)
        table_tab.rowconfigure(0, weight=1); table_tab.columnconfigure(0, weight=1)
        self.hotspot_columns = ["rank", "region", "sequence", "center", "priority", "why_hotspot"]
        self.hotspot_tree = ttk.Treeview(table_tab, columns=self.hotspot_columns, show="headings")
        headings = {"rank": "Rank", "region": "Region", "sequence": "Region sequence", "center": "Center", "priority": "Priority", "why_hotspot": "Why recommended"}
        widths = {"rank": 70, "region": 110, "sequence": 360, "center": 100, "priority": 100, "why_hotspot": 430}
        for c in self.hotspot_columns:
            self.hotspot_tree.heading(c, text=headings.get(c, c))
            self.hotspot_tree.column(c, width=widths.get(c, 160), minwidth=70, stretch=True, anchor="w")
        hy = ttk.Scrollbar(table_tab, orient="vertical", command=self.hotspot_tree.yview)
        hx = ttk.Scrollbar(table_tab, orient="horizontal", command=self.hotspot_tree.xview)
        self.hotspot_tree.configure(yscrollcommand=hy.set, xscrollcommand=hx.set)
        self.hotspot_tree.grid(row=0, column=0, sticky="nsew"); hy.grid(row=0, column=1, sticky="ns"); hx.grid(row=1, column=0, sticky="ew")
        self.result_tabs.add(table_tab, text="Candidate Table")
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

    def _default_outdir(self) -> Path:
        return configured_output(ROOT / "outputs" / "hotspot_run", "hotspot")

    def _effective_outdir(self) -> Path:
        raw = str(self.outdir.get() or "").strip()
        if raw:
            return Path(raw).expanduser()
        outdir = self._default_outdir()
        self.outdir.set(str(outdir))
        return outdir

    def load_example_input(self):
        self.input_path.set(str(APP / "examples" / "example_input.fasta"))
        self.load_input_preview()

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("Sequence files", "*.fasta *.fa *.txt"), ("All files", "*.*")])
        if p:
            self.input_path.set(p); self.load_input_preview()

    def browse_outdir(self):
        p = filedialog.askdirectory(initialdir=str(self._effective_outdir().parent if str(self.outdir.get()).strip() else self._default_outdir().parent))
        if p:
            self.outdir.set(p)

    def load_input_preview(self):
        path = str(self.input_path.get() or "").strip()
        if not path:
            self.text.delete("1.0", "end")
            return
        try:
            txt = Path(path).read_text(encoding="utf-8")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", txt)
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def run(self):
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Sequence required", "Paste a protein or peptide sequence, or choose a sequence file."); return
        outbase = self._effective_outdir()
        label = Path(str(self.input_path.get() or "")).stem if str(self.input_path.get() or "").strip() else ""
        outdir = create_result_bundle(outbase, name=label or None, sequence=text if not label else None, tool="Hotspot")
        self.last_outdir = outdir
        tmp_input = outdir / "_hotspot_input.txt"
        tmp_input.write_text(text, encoding="utf-8")
        settings = {
            "use_esm": bool(self.use_esm.get()),
            "ranking_window_size": int(self.window.get()),
            "ranking_overlap": int(self.overlap.get()),
            "ranking_min_score": float(self.min_score.get()),
            "top_n": int(self.top_n.get()),
        }
        self.run_button.configure(state="disabled")
        self.progress_var.set("Analyzing sequence...")
        self.progress.start(12)
        self.log.insert("end", "Analyzing sequence...\n"); self.log.see("end")
        threading.Thread(target=self._worker, args=(tmp_input, outdir, settings), daemon=True).start()

    def _worker(self, input_file: Path, outdir: Path, settings: dict):
        try:
            self._startup_trace.mark("hotspot_backend_load_start")
            from sequence_hotspot_finder.engine import analyze_input, load_config
            self._startup_trace.mark("hotspot_backend_ready")
            self._startup_trace.write()
            cfg = load_config(str(APP / "data" / "default_config.json"))
            cfg.update(settings)
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
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=100)
                    self.progress_var.set("Complete")
                    self.run_button.configure(state="normal")
                    r = item[1]
                    self.last_outdir = Path(r.get("full_csv", self.outdir.get())).parent
                    write_bundle_manifest(self.last_outdir, tool="Hotspot", artifacts={k: v for k, v in r.items() if isinstance(v, str)})
                    self.log.insert("end", f"Done.\nFull CSV: {r.get('full_csv')}\nResidue Top CSV: {r.get('top_csv')}\nRanked regions: {r.get('ranked_regions_csv')}\nZIP: {r.get('zip_path')}\n")
                    self._load_output_preview(r)
                    self.log.see("end")
                    messagebox.showinfo("Complete", "Hot spot analysis complete.")
                else:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.progress_var.set("Failed")
                    self.run_button.configure(state="normal")
                    self.log.insert("end", "ERROR: " + item[1] + "\n")
                    self.log.see("end")
                    messagebox.showerror("Error", item[1])
        except queue.Empty:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        self.after(120, self._poll)


    def _format_hotspot_table(self, df):
        """Render the engine's region ranking as the primary Hot Spot result."""
        try:
            import pandas as pd
            from sequence_hotspot_finder.ranking import rank_hotspot_regions
        except Exception:
            self._last_hotspot_rows = []
            self._last_ranked_region_rows = []
            return "pandas and the Hot Spot ranking backend are required."
        if df is None or len(df) == 0:
            self._last_hotspot_rows = []
            self._last_ranked_region_rows = []
            self._populate_rank_choices([])
            return "No hotspot candidates were produced."
        ranked = df.copy()
        if "priority_score" not in ranked.columns or "region_sequence" not in ranked.columns:
            ranked = rank_hotspot_regions(
                ranked,
                top_n=max(1, int(self.top_n.get())),
                window_size=max(5, int(self.window.get())),
                min_score=float(self.min_score.get()),
                overlap=int(self.overlap.get()),
            )
        if ranked.empty:
            self._last_hotspot_rows = []
            self._last_ranked_region_rows = []
            self._populate_rank_choices([])
            return "No hotspot region passed the current ranking filter."

        ranked = ranked.sort_values("rank").reset_index(drop=True)
        ranked_rows = ranked.fillna("").to_dict("records")
        display_rows = []
        lines = []
        header = f"{'rank':>4}  {'region':<11}  {'sequence':<34}  {'center':<10}  {'priority':>8}  {'why recommended'}"
        lines.append(header)
        lines.append("-" * len(header))
        for raw in ranked_rows:
            rank = int(float(raw.get("rank", len(display_rows) + 1)))
            start = raw.get("region_start", "")
            stop = raw.get("region_end", "")
            region = f"{start}-{stop}" if start != "" and stop != "" else ""
            sequence = str(raw.get("region_sequence", ""))
            center = f"({raw.get('center_position','')}{raw.get('center_residue','')})"
            try:
                priority = f"{float(raw.get('priority_score', 0.0)):.4f}"
            except Exception:
                priority = str(raw.get("priority_score", ""))
            reason = str(raw.get("why_hotspot", "local window/context evidence"))
            display_rows.append({
                "rank": rank,
                "region": region,
                "sequence": sequence,
                "center": center,
                "priority": priority,
                "why_hotspot": reason,
                "hotspot_residues": raw.get("hotspot_residues", ""),
                "basis": raw.get("basis", ""),
                "record_name": raw.get("record_name", ""),
                "region_start": raw.get("region_start", ""),
                "region_end": raw.get("region_end", ""),
                "region_sequence": sequence,
                "priority_score": raw.get("priority_score", ""),
                "center_position": raw.get("center_position", ""),
                "center_residue": raw.get("center_residue", ""),
                "claim_guard": raw.get("claim_guard", ""),
            })
            lines.append(f"{rank:>4}  {region:<11}  {sequence[:34]:<34}  {center:<10}  {priority:>8}  {reason}")
        self._last_ranked_region_rows = display_rows
        self._last_hotspot_rows = display_rows
        self._populate_rank_choices(display_rows)
        return "\n".join(lines)

    def _rank_choice_label(self, row: dict) -> str:
        seq = str(row.get("region_sequence", row.get("sequence", "")))
        if len(seq) > 28:
            seq = seq[:25] + "..."
        return f"#{row.get('rank','?')} | {row.get('region','')} | {seq} | priority {row.get('priority','')}"

    def _populate_rank_choices(self, rows: list[dict]) -> None:
        self._rank_choice_map = {self._rank_choice_label(row): row for row in rows}
        values = list(self._rank_choice_map)
        self.rank_choice_combo.configure(values=values)
        if values:
            self.rank_choice_var.set(values[0])
            self._on_rank_choice()
        else:
            self.rank_choice_var.set("")
            self.rank_detail_var.set("No ranked recommendation is available.")

    def _selected_ranked_row(self) -> dict | None:
        return getattr(self, "_rank_choice_map", {}).get(self.rank_choice_var.get())

    def _on_rank_choice(self, _event=None) -> None:
        row = self._selected_ranked_row()
        if not row:
            return
        self.rank_detail_var.set(
            f"#{row.get('rank')}  region {row.get('region')}  center {row.get('center')}  "
            f"priority {row.get('priority')}  |  {row.get('why_hotspot')}  |  "
            "priority is a within-run heuristic, not binding probability or affinity."
        )
        try:
            children = self.hotspot_tree.get_children()
            idx = max(0, int(row.get("rank", 1)) - 1)
            if idx < len(children):
                item = children[idx]
                self.hotspot_tree.selection_set(item)
                self.hotspot_tree.focus(item)
                self.hotspot_tree.see(item)
        except Exception:
            LOGGER.debug("Rank selection highlight skipped", exc_info=True)
        try:
            self._sync_selected_for_pde(silent=True)
        except Exception:
            LOGGER.debug("Automatic PDE hand-off sync skipped", exc_info=True)

    def _sync_selected_for_pde(self, silent: bool = True) -> dict[str, str]:
        row = self._selected_ranked_row()
        if not row:
            raise ValueError("Run analysis and choose a ranked recommendation first.")
        transfer = ranked_region_to_transfer(row)
        if self._workflow_project_dir is not None:
            paths = write_design_handoff(
                self._workflow_project_dir,
                [transfer],
                ranked_rows=getattr(self, "_last_ranked_region_rows", []),
            )
            profile_path = paths.get("profile_json", "")
            destination = str(self._workflow_project_dir / "design")
        else:
            out = self._active_export_bundle()
            csv_path = out / "selected_hotspot_for_design.csv"
            with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=SELECTED_HOTSPOT_COLUMNS)
                writer.writeheader()
                writer.writerow({key: transfer.get(key, "") for key in SELECTED_HOTSPOT_COLUMNS})
            profile = export_hotspot_chemistry_profile([transfer], out)
            paths = {"selected_hotspots_csv": str(csv_path), **profile}
            profile_path = str(profile.get("profile_json", ""))
            destination = str(out)
        self._last_pde_profile_path = Path(profile_path) if profile_path else None
        if self._workflow_project_dir is not None:
            self.progress_var.set(
                f"PDE linked: Hot Spot #{row.get('rank')} | {row.get('region_sequence', row.get('sequence', ''))}"
            )
        if not silent:
            messagebox.showinfo("PDE hand-off ready", f"Selected Hot Spot #{row.get('rank')} is linked to PDE.\n{destination}")
        return {key: str(value) for key, value in paths.items()}

    def open_selected_in_pde(self):
        row = self._selected_ranked_row()
        if not row:
            messagebox.showinfo("No ranked region", "Run analysis and choose a ranked recommendation first.")
            return
        try:
            paths = self._sync_selected_for_pde(silent=True)
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--tool", "design"]
            else:
                cmd = [sys.executable, str(ROOT / "main_launcher.py"), "--tool", "design"]
            env = os.environ.copy()
            selected_sequence = str(row.get("region_sequence", row.get("sequence", "")) or "").strip()
            if selected_sequence:
                env["PEPFORGE_WORKFLOW_TARGET_SEQUENCE"] = selected_sequence
            env["PEPFORGE_WORKFLOW_HOTSPOT_RANK"] = str(row.get("rank", ""))
            profile_path = str(paths.get("profile_json", "") or "").strip()
            if profile_path:
                env["PEPFORGE_HOTSPOT_PROFILE"] = profile_path
            if self._workflow_project_dir is not None:
                env["PEPFORGE_WORKFLOW_PROJECT"] = str(self._workflow_project_dir)
            import subprocess
            subprocess.Popen(cmd, cwd=str(ROOT), env=env)
            self.progress_var.set(f"PDE opened with Hot Spot #{row.get('rank')}")
        except Exception as exc:
            messagebox.showerror("PDE launch error", str(exc))

    def export_selected_for_pde(self):
        try:
            self._sync_selected_for_pde(silent=False)
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def _load_output_preview(self, result: dict):
        self.top_output.delete("1.0", "end")
        df = result.get("ranked_regions_df")
        try:
            import pandas as pd
            ranked_csv = result.get("ranked_regions_csv")
            if ranked_csv and Path(ranked_csv).exists():
                df = pd.read_csv(ranked_csv)
            elif df is None:
                full_csv = result.get("full_csv")
                if full_csv and Path(full_csv).exists():
                    df = pd.read_csv(full_csv)
                else:
                    df = result.get("full_df", result.get("top_df"))
        except Exception:
            if df is None:
                df = result.get("full_df", result.get("top_df"))
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
            LOGGER.debug("Optional operation skipped", exc_info=True)
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
                    LOGGER.debug("Optional operation skipped", exc_info=True)
            for m in re.finditer(r"\((\d+)([A-Za-z])\)", str(r.get("center", ""))):
                try:
                    pos.add(int(m.group(1)))
                except Exception:
                    LOGGER.debug("Optional operation skipped", exc_info=True)
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

    def _active_export_bundle(self) -> Path:
        if self.last_outdir is not None and Path(self.last_outdir).exists():
            return Path(self.last_outdir)
        text = self.text.get("1.0", "end").strip()
        label = Path(str(self.input_path.get() or "")).stem if str(self.input_path.get() or "").strip() else ""
        bundle = create_result_bundle(self._effective_outdir(), name=label or None, sequence=text if not label else None, tool="Hotspot")
        self.last_outdir = bundle
        return bundle

    def _refresh_export_bundle(self, artifacts: dict | None = None) -> None:
        if self.last_outdir is None:
            return
        bundle = Path(self.last_outdir)
        zip_path = build_bundle_zip(bundle, filename="Hotspot_Result_Package.zip")
        merged = dict(artifacts or {})
        merged["zip"] = zip_path
        write_bundle_manifest(bundle, tool="Hotspot", artifacts=merged)

    def export_pymol_hotspots(self):
        try:
            out = self._active_export_bundle()
            paths = self._write_hotspot_pymol_files(out)
            self.last_outdir = out
            self._refresh_export_bundle(paths)
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
            out = self._active_export_bundle()
            df = pd.DataFrame(getattr(self, "_last_hotspot_rows", []))
            if df.empty:
                messagebox.showinfo("No data", "Run analysis first."); return
            df.to_csv(out / "hotspot_display_table.csv", index=False, encoding="utf-8-sig")
            df.to_excel(out / "hotspot_display_table.xlsx", index=False)
            self.last_outdir = out
            self._refresh_export_bundle({"display_csv": out / "hotspot_display_table.csv", "display_xlsx": out / "hotspot_display_table.xlsx"})
            messagebox.showinfo("Export complete", f"Exported to:\n{out}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def export_motif_hints(self):
        try:
            out = self._active_export_bundle()
            rows = getattr(self, "_last_hotspot_rows", [])
            motifs = []
            for r in rows:
                toks = re.findall(r"\((\d+)([A-Z])\)", str(r.get("hotspot_residues", "")))
                if toks:
                    motifs.append("".join([aa for _, aa in toks[:5]]))
            p = out / "hotspot_motif_hints_for_design_engine.txt"
            p.write_text("\n".join(motifs), encoding="utf-8")
            self.last_outdir = out
            self._refresh_export_bundle({"motif_hints": p})
            messagebox.showinfo("Motif hints exported", str(p))
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    def open_output(self):
        p = self.last_outdir or self._effective_outdir()
        if p.exists():
            open_path(p)
        else:
            messagebox.showinfo("Not found", str(p))


def main():
    app = HotspotGUI(); app.mainloop()

if __name__ == "__main__":
    main()
