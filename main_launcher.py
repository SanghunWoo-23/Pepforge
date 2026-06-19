from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_VERSION = "2.0.0"
ROOT = Path(__file__).resolve().parent
APPS = ROOT / "apps"
RUNTIME_LOG_DIR = ROOT / "outputs" / "runtime_logs"


def _ensure_runtime_environment() -> None:
    """Normalize paths for both source runs and PyInstaller frozen runs."""
    os.chdir(ROOT)
    for p in [ROOT, ROOT / "suite_gui", ROOT / "peptiforg_core"]:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _resource_path(*parts: str) -> Path:
    """Return a resource path that works in source and PyInstaller modes."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        candidate = Path(frozen_base).joinpath(*parts)
        if candidate.exists():
            return candidate
    return ROOT.joinpath(*parts)


@contextlib.contextmanager
def _pushd(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _add_to_path(path: Path) -> None:
    sp = str(path)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        messagebox.showwarning("Open folder", f"Could not open:\n{path}\n\n{exc}")


def _python_or_self_args(tool: str) -> list[str]:
    """Return command that re-enters this launcher in source or frozen mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--tool", tool]
    return [sys.executable, str(ROOT / "main_launcher.py"), "--tool", tool]


def _run_subprocess(tool: str) -> None:
    _ensure_runtime_environment()
    try:
        subprocess.Popen(_python_or_self_args(tool), cwd=str(ROOT))
    except Exception as exc:
        messagebox.showerror("Launch failed", str(exc))


def run_peptide_design_engine() -> None:
    _ensure_runtime_environment()
    app_dir = APPS / "peptide_design_engine" / "Python"
    _add_to_path(app_dir)
    with _pushd(app_dir):
        from desktop_gui import main
        main()


def run_hotspot_finder() -> None:
    _ensure_runtime_environment()
    from suite_gui.hotspot_gui import main
    main()


def run_spps_planner() -> None:
    _ensure_runtime_environment()
    from suite_gui.spps_tk_gui import main
    main()


def run_docking_workbench() -> None:
    _ensure_runtime_environment()
    from suite_gui.docking_workbench_gui import main
    main()



def run_pymol_structure_builder() -> None:
    _ensure_runtime_environment()
    from suite_gui.pymol_structure_builder_gui import main
    main()

def run_workflow_mode() -> None:
    _ensure_runtime_environment()
    from peptiforg_core.workflow_gui import main
    main()


def _safe_run_tool(tool_name: str, func):
    _ensure_runtime_environment()
    try:
        return func()
    except Exception as exc:
        log_path = RUNTIME_LOG_DIR / f"runtime_error_{tool_name}.log"
        try:
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        try:
            messagebox.showerror(
                f"{tool_name} launch failed",
                f"{tool_name} failed to open.\n\n"
                f"Error: {exc}\n\n"
                f"A detailed log was written to:\n{log_path}"
            )
        except Exception:
            pass
        raise


def _apply_icon(window: tk.Tk | tk.Toplevel) -> None:
    for icon_file in [
        _resource_path("assets", "Pepforge_Icon.png"),
        ROOT / "assets" / "Pepforge_Icon.png",
    ]:
        try:
            if icon_file.exists():
                img = tk.PhotoImage(file=str(icon_file))
                window.iconphoto(True, img)
                setattr(window, "_pepforge_icon_img", img)
                return
        except Exception:
            pass


def launcher_main() -> None:
    _ensure_runtime_environment()
    root = tk.Tk()
    root.title("Pepforge")
    root.geometry("1120x580")
    root.minsize(1040, 520)
    _apply_icon(root)

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
        text="Integrated peptide hotspot analysis, SPPS-aware peptide design, synthesis planning, and structure-oriented screening.",
        style="Sub.TLabel",
        wraplength=820,
    ).pack(anchor="w", pady=(8, 18))

    grid = ttk.Frame(main)
    grid.pack(fill="both", expand=True)
    for i in range(6):
        grid.columnconfigure(i, weight=1)
    grid.rowconfigure(0, weight=1)

    cards = [
        ("Hotspot Finder", "Find sequence hotspots and export motif-ready regions.", "hotspot"),
        ("Peptide Design Engine", "Generate SPPS-aware candidates with D-form, non-natural, linker, and chemical token handling.", "design"),
        ("SPPS Planner", "Build synthesis plans, materials, checklists, logs, and output folders.", "spps"),
        ("Docking Workbench", "Run docking screening, contacts, embedded MD screening, and external validation import/export.", "docking"),
        ("PyMOL Structure Builder", "Build PyMOL-readable PDB/CIF/PML structures from modified peptide notation.", "pymol"),
        ("Workflow Mode", "Connect Hotspot → Design → Docking → SPPS with project files.", "workflow"),
    ]
    for col, (title, desc, tool) in enumerate(cards):
        card = ttk.Frame(grid, style="Card.TFrame")
        card.grid(row=0, column=col, padx=8, pady=6, sticky="nsew")
        ttk.Label(card, text=title, style="CardTitle.TLabel", wraplength=190).pack(anchor="w")
        ttk.Label(card, text=desc, wraplength=190, justify="left").pack(anchor="w", pady=(10, 18), fill="x")
        ttk.Button(card, text="Open", style="Tool.TButton", command=lambda t=tool: _run_subprocess(t)).pack(side="bottom", fill="x")

    bottom = ttk.Frame(main)
    bottom.pack(fill="x", pady=(12, 0))
    ttk.Button(bottom, text="Open project folder", command=lambda: _open_path(ROOT)).pack(side="left")
    ttk.Button(bottom, text="Open runtime logs", command=lambda: _open_path(RUNTIME_LOG_DIR)).pack(side="left", padx=(8, 0))
    ttk.Button(bottom, text="Exit", command=root.destroy).pack(side="right")

    root.mainloop()


def main(argv: list[str] | None = None) -> None:
    _ensure_runtime_environment()
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--tool", default="", choices=["", "design", "hotspot", "spps", "docking", "structure", "pymol", "workflow"])
    args = parser.parse_args(argv)
    tool = args.tool
    if tool == "design":
        return _safe_run_tool("peptide_design_engine", run_peptide_design_engine)
    if tool == "hotspot":
        return _safe_run_tool("hotspot_finder", run_hotspot_finder)
    if tool == "spps":
        return _safe_run_tool("spps_planner", run_spps_planner)
    if tool in ("docking", "structure"):
        return _safe_run_tool("docking_workbench", run_docking_workbench)
    if tool == "pymol":
        return _safe_run_tool("pymol_structure_builder", run_pymol_structure_builder)
    if tool == "workflow":
        return _safe_run_tool("workflow_mode", run_workflow_mode)
    launcher_main()


if __name__ == "__main__":
    main()
