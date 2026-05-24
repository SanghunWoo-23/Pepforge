from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
APPS = ROOT / "apps"


def _python_or_self_args(tool: str):
    """Return command that re-enters this launcher in source or frozen mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tool", tool]
    return [sys.executable, str(ROOT / "main_launcher.py"), "--tool", tool]


def _run_subprocess(tool: str):
    try:
        subprocess.Popen(_python_or_self_args(tool), cwd=str(ROOT))
    except Exception as e:
        messagebox.showerror("Launch failed", str(e))


def run_peptide_design_engine():
    app_dir = APPS / "peptide_design_engine" / "Python"
    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))
    from desktop_gui import main
    main()


def run_hotspot_finder():
    sys.path.insert(0, str(ROOT))
    from suite_gui.hotspot_gui import main
    main()


def run_spps_planner():
    sys.path.insert(0, str(ROOT))
    from suite_gui.spps_tk_gui import main
    main()


def run_workflow_mode():
    sys.path.insert(0, str(ROOT))
    from peptiforg_core.workflow_gui import main
    main()



def _safe_run_tool(tool_name: str, func):
    try:
        return func()
    except Exception as e:
        import traceback
        log_path = ROOT / f"runtime_error_{tool_name}.log"
        try:
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        try:
            messagebox.showerror(
                f"{tool_name} launch failed",
                f"{tool_name} failed to open.\n\nError: {e}\n\nA detailed log was written to:\n{log_path}"
            )
        except Exception:
            pass
        raise

def launcher_main():
    root = tk.Tk()
    root.title("Pepforge")
    root.geometry("900x560")
    root.minsize(840, 520)

    icon_png = ROOT / "assets" / "Pepforge_Icon.png"
    try:
        if icon_png.exists():
            img = tk.PhotoImage(file=str(icon_png))
            root.iconphoto(True, img)
            root._icon_img = img
    except Exception:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
    style.configure("Sub.TLabel", font=("Segoe UI", 10))
    style.configure("Card.TFrame", padding=18, relief="groove", borderwidth=1)
    style.configure("CardTitle.TLabel", font=("Segoe UI", 13, "bold"))
    style.configure("Tool.TButton", font=("Segoe UI", 11, "bold"), padding=10)

    main = ttk.Frame(root, padding=24)
    main.pack(fill="both", expand=True)

    header = ttk.Frame(main)
    header.pack(fill="x")
    ttk.Label(header, text="Pepforge", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Standalone Mode에서는 각 기능을 독립 실행하고, Workflow Mode에서는 project.json + CSV로 Hot Spot Finder → Peptide Design Engine → SPPS Planner를 연동합니다.",
        style="Sub.TLabel",
        wraplength=680,
    ).pack(anchor="w", pady=(8, 18))

    grid = ttk.Frame(main)
    grid.pack(fill="both", expand=True)
    for i in range(4):
        grid.columnconfigure(i, weight=1)
    grid.rowconfigure(0, weight=1)

    cards = [
        ("Hot Spot Finder", "Standalone: 서열 FASTA/text를 입력하거나 파일로 불러와 hotspot/top-region CSV와 ZIP을 생성합니다.", "hotspot"),
        ("Peptide Design Engine", "Standalone: 기존 branded desktop GUI를 그대로 실행합니다. multi-target/bridge/linker/ML/export 기능을 유지합니다.", "design"),
        ("SPPS Planner", "Standalone: 서열·레진·scale 입력 후 synthesis form, wash-by-wash form, raw material CSV/XLSX를 생성합니다.", "spps"),
        ("Workflow Mode", "Connected: project/session 폴더를 만들고 Hotspot → Design → SPPS를 CSV/JSON 기반으로 추적 가능하게 연결합니다.", "workflow"),
    ]
    for col, (title, desc, tool) in enumerate(cards):
        card = ttk.Frame(grid, style="Card.TFrame")
        card.grid(row=0, column=col, padx=8, pady=6, sticky="nsew")
        ttk.Label(card, text=title, style="CardTitle.TLabel", wraplength=190).pack(anchor="w")
        ttk.Label(card, text=desc, wraplength=190, justify="left").pack(anchor="w", pady=(10, 18), fill="x")
        ttk.Button(card, text="Open", style="Tool.TButton", command=lambda t=tool: _run_subprocess(t)).pack(side="bottom", fill="x")

    bottom = ttk.Frame(main)
    bottom.pack(fill="x", pady=(12, 0))
    ttk.Button(bottom, text="Open project folder", command=lambda: os.startfile(ROOT) if os.name == "nt" else subprocess.Popen(["xdg-open", str(ROOT)])).pack(side="left")
    ttk.Button(bottom, text="Exit", command=root.destroy).pack(side="right")

    root.mainloop()


def main():
    if "--tool" in sys.argv:
        idx = sys.argv.index("--tool")
        tool = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if tool == "design":
            return _safe_run_tool("peptide_design_engine", run_peptide_design_engine)
        if tool == "hotspot":
            return _safe_run_tool("hotspot_finder", run_hotspot_finder)
        if tool == "spps":
            return _safe_run_tool("spps_planner", run_spps_planner)
        if tool == "workflow":
            return _safe_run_tool("workflow_mode", run_workflow_mode)
        raise SystemExit(f"Unknown tool: {tool}")
    launcher_main()


if __name__ == "__main__":
    main()
