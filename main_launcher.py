from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import traceback
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_VERSION = "3.0.0"
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
APPS = ROOT / "apps"

def _launcher_log_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return (Path(base) if base else Path.home() / ".pepforge") / "Pepforge" / "workspace" / "launcher" / "logs"
    return Path(__file__).resolve().parent / "workspace" / "launcher" / "logs"

RUNTIME_LOG_DIR = _launcher_log_dir()
LOGGER = logging.getLogger("pepforge.launcher")


def _ensure_runtime_environment() -> None:
    """Normalize paths for both source runs and PyInstaller frozen runs."""
    os.chdir(ROOT)
    for p in [ROOT, ROOT / "suite_gui", ROOT / "peptiforg_core"]:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)


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
    from peptiforg_core.sandbox_runtime import get_tool_sandbox
    sandbox = get_tool_sandbox(tool)
    try:
        subprocess.Popen(
            _python_or_self_args(tool),
            cwd=str(sandbox.root),
            env=sandbox.environment(),
        )
    except Exception as exc:
        LOGGER.exception("Could not launch tool %s", tool)
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


def run_external_tools_guide() -> None:
    _ensure_runtime_environment()
    from suite_gui.external_tools_guide import main
    main()



def run_pymol_structure_builder() -> None:
    _ensure_runtime_environment()
    from suite_gui.pymol_structure_builder_gui import main
    main()

def run_workflow_mode() -> None:
    _ensure_runtime_environment()
    from peptiforg_core.workflow_gui import main
    main()


def run_structure_worker(request_path: str) -> int:
    """Run the isolated PSB worker used by the current Structure Builder."""
    _ensure_runtime_environment()
    from peptiforg_core.structure_worker import run_structure_request
    return run_structure_request(request_path)


def _safe_run_tool(tool_name: str, func):
    _ensure_runtime_environment()
    try:
        return func()
    except Exception as exc:
        log_path = RUNTIME_LOG_DIR / f"runtime_error_{tool_name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        messagebox.showerror(
            f"{tool_name} launch failed",
            f"{tool_name} failed to open.\n\n"
            f"Error: {exc}\n\n"
            f"A detailed log was written to:\n{log_path}"
        )
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
        except (tk.TclError, OSError) as exc:
            LOGGER.debug("Icon could not be applied: %s", exc)


def launcher_main() -> None:
    _ensure_runtime_environment()
    from peptiforg_core.ui_theme import (
        apply_pepforge_theme,
        fit_window,
        set_density as apply_display_density,
    )
    from peptiforg_core.sandbox_runtime import get_tool_sandbox

    root = tk.Tk()
    root.title(f"Pepforge V{APP_VERSION}")
    fit_window(root)
    _apply_icon(root)

    density_var = tk.StringVar(value="Standard")
    selected_tool = tk.StringVar(value="hotspot")
    run_status = tk.StringVar(value="Ready")
    apply_pepforge_theme(root, density_var.get())

    tools = {
        "hotspot": {
            "group": "WORKFLOW", "number": "1", "name": "Hotspot Finder",
            "summary": "Find sequence hotspots and export candidate regions for downstream peptide design.",
            "workflow": "Input sequence / structure → validate → hotspot analysis → candidate regions → export",
            "outputs": "Hotspot candidates, analysis tables, sandbox outputs",
        },
        "design": {
            "group": "WORKFLOW", "number": "2", "name": "Peptide Design Engine",
            "summary": "Generate SPPS-aware modified-peptide candidates with canonical, D-form and non-natural chemistry options.",
            "workflow": "Design constraints → candidate generation → ranking / review → structure hand-off",
            "outputs": "Designed peptide candidates and design-engine exports",
        },
        "pymol": {
            "group": "WORKFLOW", "number": "3", "name": "Peptide Structure Builder",
            "summary": "Generate and analyze peptide conformational candidates and ensembles without pretending to replace MD.",
            "workflow": "Modified peptide → conformer generation → relaxation → family / torsion analysis → representative outputs",
            "outputs": "PDB, SDF, ensemble SDF, conformer families, backbone torsions, reports",
        },
        "spps": {
            "group": "WORKFLOW", "number": "4", "name": "SPPS Planner",
            "summary": "Prepare synthesis plans and material estimates through the integrated SPPS workflow.",
            "workflow": "Sequence / resin / scale → synthesis plan → materials → checklist / export",
            "outputs": "SPPS plan, selected materials, total materials and checklist outputs",
        },
        "external": {
            "group": "WORKFLOW", "number": "6", "name": "External Validation",
            "summary": "Check external-tool prerequisites and prepare hand-off packages for Vina or GROMACS.",
            "workflow": "Pepforge output → prerequisite check → input preparation → external program hand-off",
            "outputs": "Prepared external-validation folders and guidance; no fabricated docking or MD results",
        },
        "docking": {
            "group": "WORKFLOW", "number": "5", "name": "Docking Workbench",
            "summary": "Run Pepforge screening with visible validation, staged progress, contacts, scoring and ranking.",
            "workflow": "Validation → target / peptide preparation → poses → contacts → scoring → ranking → export",
            "outputs": "Screening poses, contacts, ranked results and diagnostics",
        },
        "workflow": {
            "group": "ADVANCED", "number": "", "name": "Workflow Mode",
            "summary": "Coordinate supported Pepforge workflow steps and project-oriented hand-offs.",
            "workflow": "Project inputs → configured Pepforge stages → outputs / hand-offs",
            "outputs": "Workflow-generated project artifacts and stage outputs",
        },
    }

    nav_buttons: dict[str, ttk.Button] = {}

    def tool_sandbox_text(tool: str) -> str:
        try:
            return str(get_tool_sandbox(tool).root)
        except Exception as exc:
            LOGGER.warning("Could not resolve sandbox for %s: %s", tool, exc)
            return "Sandbox path unavailable until launch"

    def update_selection(tool: str) -> None:
        if tool not in tools:
            return
        selected_tool.set(tool)
        data = tools[tool]
        detail_title.configure(text=data["name"])
        detail_summary.configure(text=data["summary"])
        workflow_value.configure(text=data["workflow"])
        output_value.configure(text=data["outputs"])
        sandbox_value.configure(text=tool_sandbox_text(tool))
        launch_button.configure(text=f"Open {data['name']}", command=lambda: launch_selected(tool))
        for key, button in nav_buttons.items():
            button.configure(style="NavSelected.TButton" if key == tool else "Nav.TButton")

    def launch_selected(tool: str | None = None) -> None:
        target = tool or selected_tool.get()
        data = tools[target]
        try:
            _run_subprocess(target)
            run_status.set(f"Launch requested: {data['name']}")
        except Exception as exc:
            run_status.set(f"Launch failed: {data['name']}")
            raise exc

    def open_selected_workspace() -> None:
        target = selected_tool.get()
        try:
            _open_path(get_tool_sandbox(target).root)
        except Exception as exc:
            messagebox.showerror("Workspace", f"Could not open workspace.\n\n{exc}", parent=root)

    def change_density(value: str) -> None:
        density_var.set(value)
        apply_display_density(root, value)
        update_selection(selected_tool.get())

    def show_about() -> None:
        messagebox.showinfo(
            "About Pepforge",
            f"Pepforge V{APP_VERSION}\n\n"
            "Modern / Classic Hybrid Workspace\n"
            "Modified-peptide design, conformational preparation, SPPS planning, screening, and external-validation hand-off.\n\n"
            "Pepforge does not present external Vina or GROMACS calculations as internal results.",
            parent=root,
        )

    menu = tk.Menu(root, tearoff=False)
    file_menu = tk.Menu(menu, tearoff=False)
    file_menu.add_command(label="Open Project Folder", command=lambda: _open_path(ROOT))
    file_menu.add_command(label="Open Runtime Logs", command=lambda: _open_path(RUNTIME_LOG_DIR))
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.destroy)
    menu.add_cascade(label="File", menu=file_menu)

    workflow_menu = tk.Menu(menu, tearoff=False)
    for key in ("hotspot", "design", "pymol", "spps", "docking", "external"):
        workflow_menu.add_command(label=tools[key]["name"], command=lambda value=key: update_selection(value))
    menu.add_cascade(label="Workflow", menu=workflow_menu)

    tools_menu = tk.Menu(menu, tearoff=False)
    tools_menu.add_command(label="Workflow Mode", command=lambda: update_selection("workflow"))
    tools_menu.add_separator()
    tools_menu.add_command(label="Open Selected Tool", command=lambda: launch_selected())
    menu.add_cascade(label="Tools", menu=tools_menu)

    view_menu = tk.Menu(menu, tearoff=False)
    density_menu = tk.Menu(view_menu, tearoff=False)
    for value in ("Compact", "Standard", "Comfortable"):
        density_menu.add_command(label=value, command=lambda chosen=value: change_density(chosen))
    view_menu.add_cascade(label="Display Density", menu=density_menu)
    menu.add_cascade(label="View", menu=view_menu)

    help_menu = tk.Menu(menu, tearoff=False)
    help_menu.add_command(label="About", command=show_about)
    menu.add_cascade(label="Help", menu=help_menu)
    root.configure(menu=menu)

    shell = ttk.Frame(root, padding=(18, 14, 18, 14))
    shell.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    shell.columnconfigure(0, weight=0)
    shell.columnconfigure(1, weight=3)
    shell.columnconfigure(2, weight=2)
    shell.rowconfigure(1, weight=1)

    header = ttk.Frame(shell)
    header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text="Pepforge", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(header, text=f"V{APP_VERSION}  •  Modern / Classic Hybrid Workspace", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
    ttk.Label(header, textvariable=run_status, style="Muted.TLabel").grid(row=0, column=1, rowspan=2, sticky="e")

    sidebar = ttk.Frame(shell, style="Surface.TFrame", padding=(10, 12))
    sidebar.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
    sidebar.columnconfigure(0, weight=1)
    row = 0
    for group in ("WORKFLOW", "ADVANCED"):
        ttk.Label(sidebar, text=group, style="SurfaceMuted.TLabel", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", padx=6, pady=(3 if row == 0 else 15, 5))
        row += 1
        for key in ("hotspot", "design", "pymol", "spps", "docking", "external", "workflow"):
            data = tools[key]
            if data["group"] != group:
                continue
            label = f"{data['number']}  {data['name']}" if data["number"] else data["name"]
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda value=key: update_selection(value))
            button.grid(row=row, column=0, sticky="ew", pady=2)
            nav_buttons[key] = button
            row += 1

    center = ttk.Frame(shell, style="Surface.TFrame", padding=(22, 20))
    center.grid(row=1, column=1, sticky="nsew", padx=(0, 10))
    center.columnconfigure(0, weight=1)
    center.rowconfigure(6, weight=1)
    detail_title = ttk.Label(center, text="", style="SurfaceSection.TLabel", font=("Segoe UI", 17, "bold"))
    detail_title.grid(row=0, column=0, sticky="w")
    detail_summary = ttk.Label(center, text="", style="SurfaceMuted.TLabel", wraplength=650, justify="left")
    detail_summary.grid(row=1, column=0, sticky="ew", pady=(7, 18))

    ttk.Label(center, text="WORKFLOW", style="SurfaceMuted.TLabel", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w")
    workflow_value = ttk.Label(center, text="", style="Surface.TLabel", wraplength=650, justify="left")
    workflow_value.grid(row=3, column=0, sticky="ew", pady=(5, 16))
    ttk.Label(center, text="OUTPUTS", style="SurfaceMuted.TLabel", font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w")
    output_value = ttk.Label(center, text="", style="Surface.TLabel", wraplength=650, justify="left")
    output_value.grid(row=5, column=0, sticky="ew", pady=(5, 16))

    action_bar = ttk.Frame(center, style="Sidebar.TFrame")
    action_bar.grid(row=7, column=0, sticky="ew", pady=(18, 0))
    launch_button = ttk.Button(action_bar, text="Open", style="Accent.TButton")
    launch_button.pack(side="left")
    ttk.Button(action_bar, text="Open workspace", command=open_selected_workspace).pack(side="left", padx=(8, 0))

    context = ttk.Frame(shell, style="Surface.TFrame", padding=(18, 18))
    context.grid(row=1, column=2, sticky="nsew")
    context.columnconfigure(0, weight=1)
    ttk.Label(context, text="CONTEXT", style="SurfaceMuted.TLabel", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(context, text="Selected tool", style="SurfaceSection.TLabel").grid(row=1, column=0, sticky="w", pady=(13, 3))
    selected_label = ttk.Label(context, textvariable=selected_tool, style="SurfaceMuted.TLabel")
    selected_label.grid(row=2, column=0, sticky="w")
    ttk.Label(context, text="Sandbox workspace", style="SurfaceSection.TLabel").grid(row=3, column=0, sticky="w", pady=(18, 3))
    sandbox_value = ttk.Label(context, text="", style="SurfaceMuted.TLabel", wraplength=360, justify="left")
    sandbox_value.grid(row=4, column=0, sticky="ew")
    ttk.Separator(context).grid(row=5, column=0, sticky="ew", pady=18)
    ttk.Label(context, text="Workflow rule", style="SurfaceSection.TLabel").grid(row=6, column=0, sticky="w")
    ttk.Label(
        context,
        text="Pepforge prepares, analyzes and hands off peptide-specific work. External Vina/GROMACS calculations remain external and must not be represented as Pepforge-computed results.",
        style="SurfaceMuted.TLabel", wraplength=360, justify="left",
    ).grid(row=7, column=0, sticky="ew", pady=(5, 0))

    footer = ttk.Frame(shell)
    footer.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    ttk.Label(footer, text="Display density:", style="Muted.TLabel").pack(side="left")
    ttk.Label(footer, textvariable=density_var, style="Muted.TLabel").pack(side="left", padx=(5, 0))
    ttk.Button(footer, text="Project folder", command=lambda: _open_path(ROOT)).pack(side="right")
    ttk.Button(footer, text="Runtime logs", command=lambda: _open_path(RUNTIME_LOG_DIR)).pack(side="right", padx=(0, 8))

    update_selection("hotspot")
    root.mainloop()


def main(argv: list[str] | None = None) -> None:
    _ensure_runtime_environment()
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--tool", default="", choices=["", "design", "hotspot", "spps", "docking", "structure", "pymol", "workflow", "external"])
    parser.add_argument("--structure-worker", default="", metavar="REQUEST_JSON", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.structure_worker:
        raise SystemExit(run_structure_worker(args.structure_worker))
    tool = args.tool
    if tool == "design":
        return _safe_run_tool("peptide_design_engine", run_peptide_design_engine)
    if tool == "hotspot":
        return _safe_run_tool("hotspot_finder", run_hotspot_finder)
    if tool == "spps":
        return _safe_run_tool("spps_planner", run_spps_planner)
    if tool == "docking":
        return _safe_run_tool("docking_workbench", run_docking_workbench)
    if tool in ("structure", "pymol"):
        return _safe_run_tool("pymol_structure_builder", run_pymol_structure_builder)
    if tool == "external":
        return _safe_run_tool("external_tools_guide", run_external_tools_guide)
    if tool == "workflow":
        return _safe_run_tool("workflow_mode", run_workflow_mode)
    launcher_main()


if __name__ == "__main__":
    main()
