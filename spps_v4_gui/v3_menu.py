"""Compact native menu bar for the V3 Modern/Classic hybrid interface."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable


def _command(gui: Any, name: str, fallback: Callable[[], Any] | None = None):
    candidate = getattr(gui, name, None)
    return candidate if callable(candidate) else (fallback or (lambda: None))


def _about(gui: Any) -> None:
    from spps_v4_gui.runtime_selftest import BUILD_REVISION
    messagebox.showinfo(
        "About SPPS Planner",
        "SPPS Planner V4.0.0\n\n"
        f"Build revision: {BUILD_REVISION}\n"
        "Modern/Classic hybrid workspace\n"
        "V3 planning workflow preserved + V4 Experimental Data / ML Advisors",
        parent=gui,
    )


def _select_result_tab(gui: Any, label: str) -> None:
    """Select a result tab even after the V3 label-cleanup pass renames it.

    V3 intentionally removes the user-facing ``Selected`` prefix, while the
    menu historically retained the old names.  Match both canonical labels so
    View commands never become silent no-ops.
    """
    notebook = getattr(gui, "pm_results_notebook", None)
    if notebook is None:
        return
    aliases = {
        "Selected Plan": {"Selected Plan", "Plan"},
        "Selected Materials": {"Selected Materials", "Materials"},
        "Selected Total Materials": {"Selected Total Materials", "Total Materials"},
        "Selected Checklist": {"Selected Checklist", "Checklist"},
        "Cleavage Cocktail": {"Cleavage Cocktail", "Selected Cleavage Cocktail"},
    }
    wanted = aliases.get(label, {label})
    for tab in notebook.tabs():
        if str(notebook.tab(tab, "text")) in wanted:
            notebook.select(tab)
            return


def _open_work_item_tab(gui: Any, label: str) -> None:
    gui.open_work_item()
    current = getattr(gui, "_v3_work_item_window", None)
    if current is not None:
        try:
            for tab in current.notebook.tabs():
                if str(current.notebook.tab(tab, "text")) == label:
                    current.notebook.select(tab)
                    break
        except Exception:
            pass


def _open_recent(gui: Any) -> None:
    rows = list(gui.recent_projects())
    window = tk.Toplevel(gui)
    window.title("Recent Projects")
    window.geometry("760x320")
    frame = ttk.Frame(window, padding=10); frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=("path", "opened_at", "exists", "recovered"), show="headings")
    for column in tree["columns"]:
        tree.heading(column, text=column)
        tree.column(column, width=450 if column == "path" else 100, stretch=column == "path")
    tree.pack(fill="both", expand=True)
    for row in rows:
        tree.insert("", "end", values=[row.get(column, "") for column in tree["columns"]])

    def open_selected(_event=None):
        selected = list(tree.selection())
        if not selected:
            return
        values = tree.item(selected[0], "values")
        exists = str(values[2]).strip().lower() in {"true", "1", "yes"} if values else False
        if values and exists:
            gui.load_project(values[0]); window.destroy()
        else:
            messagebox.showerror("Recent Projects", "The selected file is no longer available.", parent=window)

    tree.bind("<Double-1>", open_selected)
    ttk.Button(frame, text="Open Selected", command=open_selected).pack(anchor="e", pady=(7, 0))


def install_menu(gui: Any) -> tk.Menu:
    """Attach one functional, space-efficient application menu."""
    menu = tk.Menu(gui, tearoff=False)

    file_menu = tk.Menu(menu, tearoff=False)
    file_menu.add_command(label="Save Project", accelerator="Ctrl+S", command=_command(gui, "save_project"))
    file_menu.add_command(label="Save Project As...", accelerator="Ctrl+Shift+S", command=_command(gui, "save_project_as"))
    file_menu.add_command(label="Load Project", accelerator="Ctrl+O", command=_command(gui, "load_project"))
    file_menu.add_command(label="Open Recent Project...", command=lambda: _open_recent(gui))
    file_menu.add_command(label="Save Session Now", command=_command(gui, "save_autosave_state"))
    file_menu.add_separator()
    file_menu.add_command(label="Export Data Workbook...", command=_command(gui, "export_data_workbook"))
    file_menu.add_command(label="Import Data Workbook...", command=_command(gui, "import_data_workbook"))
    file_menu.add_separator()
    file_menu.add_command(label="Export Current Work", accelerator="Ctrl+E", command=_command(gui, "export_outputs"))
    file_menu.add_command(label="Export Batch Tables", command=_command(gui, "export_batch_tables"))
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=_command(gui, "destroy"))
    menu.add_cascade(label="File", menu=file_menu)

    edit_menu = tk.Menu(menu, tearoff=False)
    edit_menu.add_command(label="Add Work Item", accelerator="Ctrl+N", command=_command(gui, "pm_add_peptide"))
    edit_menu.add_command(label="Duplicate Work Item", accelerator="Ctrl+D", command=_command(gui, "pm_duplicate_peptide"))
    edit_menu.add_command(label="Delete Selected Work Item", command=_command(gui, "pm_delete_peptide"))
    menu.add_cascade(label="Edit", menu=edit_menu)

    project_menu = tk.Menu(menu, tearoff=False)
    project_menu.add_command(label="Open Selected Work Item", command=_command(gui, "open_work_item"))
    project_menu.add_command(label="Save Active Item", command=lambda: _save_active_item(gui))
    project_menu.add_command(label="Refresh Batch Preview", command=_command(gui, "refresh_batch_workspace_preview"))
    menu.add_cascade(label="Project", menu=project_menu)

    synthesis_menu = tk.Menu(menu, tearoff=False)
    synthesis_menu.add_command(
        label="Open Run / Corrections",
        command=lambda: _open_work_item_tab(gui, "Run / Corrections"),
    )
    synthesis_menu.add_command(
        label="Open Risk Review",
        command=lambda: _open_work_item_tab(gui, "Risk Review"),
    )
    synthesis_menu.add_separator()
    synthesis_menu.add_command(label="Generate Plan", accelerator="Ctrl+G", command=_command(gui, "generate_update_plan"))
    synthesis_menu.add_command(label="Apply Change", accelerator="Ctrl+Enter", command=_command(gui, "apply_change"))
    synthesis_menu.add_separator()
    synthesis_menu.add_command(label="DIC / HOBt Preset", command=_command(gui, "apply_dic_hobt_preset"))
    synthesis_menu.add_command(label="HBTU / NMP 10 eq Preset", command=_command(gui, "apply_hbtu_nmp_preset"))
    menu.add_cascade(label="Synthesis", menu=synthesis_menu)

    view_menu = tk.Menu(menu, tearoff=False)
    view_menu.add_command(label="Show / Hide Setup", command=_command(gui, "toggle_setup_panel"))
    density_menu = tk.Menu(view_menu, tearoff=False)
    from spps_v4_gui import ui_system
    for density in ("Compact", "Standard", "Comfortable"):
        density_menu.add_command(label=density, command=lambda value=density: ui_system.set_density(gui, value))
    view_menu.add_cascade(label="Display Density", menu=density_menu)
    view_menu.add_separator()
    for label in (
        "Selected Plan", "Selected Materials", "Selected Total Materials",
        "Selected Checklist", "Cleavage Cocktail",
    ):
        view_menu.add_command(
            label=f"Open {label}",
            command=lambda value=label: _select_result_tab(gui, value),
        )
    menu.add_cascade(label="View", menu=view_menu)

    data_menu = tk.Menu(menu, tearoff=False)
    data_menu.add_command(
        label="Open Data / HPLC",
        command=lambda: _open_work_item_tab(gui, "Data / HPLC"),
    )
    data_menu.add_command(
        label="Open Outcome / ML",
        command=lambda: _open_work_item_tab(gui, "Outcome / ML"),
    )
    data_menu.add_command(label="Build Reviewed Dataset", command=_command(gui, "build_ml_dataset"))
    data_menu.add_separator()
    data_menu.add_command(label="Experimental Data / ML Advisors...", command=_command(gui, "open_experimental_data"))
    data_menu.add_separator()
    data_menu.add_command(label="Custom Material DB", command=_command(gui, "restore_custom_db_tab"))
    data_menu.add_command(label="Refresh ML Data", command=_command(gui, "refresh_ml_data"))
    data_menu.add_command(label="Detect ML Anomalies", command=_command(gui, "detect_ml_anomalies"))
    menu.add_cascade(label="Data / ML", menu=data_menu)

    help_menu = tk.Menu(menu, tearoff=False)
    help_menu.add_command(label="User Manual (한국어)", command=lambda: _open_manual(gui, "USER_MANUAL_KO.md"))
    help_menu.add_command(label="User Manual (English)", command=lambda: _open_manual(gui, "USER_MANUAL_EN.md"))
    help_menu.add_command(label="Keyboard Shortcuts", command=lambda: _shortcuts(gui))
    help_menu.add_separator()
    help_menu.add_command(label="About", command=lambda: _about(gui))
    menu.add_cascade(label="Help", menu=help_menu)

    gui.configure(menu=menu)
    gui._v3_menu = menu
    return menu


def _save_active_item(gui: Any) -> None:
    from spps_v4_gui.modules import plan_workflow

    plan_workflow._save_active(gui, include_outputs=True)
    gui.save_autosave_state()


def _open_manual(gui: Any, filename: str) -> None:
    from pathlib import Path
    from spps_v4_gui.gui_primitives import open_path
    path = Path(__file__).resolve().parents[1] / "docs" / filename
    if not path.is_file():
        messagebox.showerror("Manual", f"Manual file was not found:\n{path}", parent=gui)
        return
    open_path(path)


def _shortcuts(gui: Any) -> None:
    messagebox.showinfo(
        "Keyboard Shortcuts",
        "Ctrl+S  Save Project\nCtrl+Shift+S  Save As\nCtrl+O  Load Project\n"
        "Ctrl+N  Add Work Item\nCtrl+D  Duplicate Work Item\nCtrl+G  Generate Plan\n"
        "Ctrl+Enter  Apply Change\nCtrl+E  Export\nCtrl+- / Ctrl+0 / Ctrl+=  Display density\n\n"
        "Work Item: F5 Refresh, Esc Save and Close",
        parent=gui,
    )


__all__ = ["install_menu"]
