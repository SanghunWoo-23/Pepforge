"""V3 Modern/Classic visual system, responsive sizing and keyboard access."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


PALETTE = {
    "background": "#F3F6FA", "surface": "#FFFFFF", "surface_alt": "#EAF0F8",
    "text": "#182230", "muted": "#667085", "border": "#CCD5E1",
    "primary": "#2563EB", "primary_hover": "#1D4ED8", "primary_text": "#FFFFFF",
    "danger": "#B42318", "danger_hover": "#912018", "selection": "#DCE8FF",
}
DENSITIES = {
    "Compact": {"tree_rowheight": 24, "tab_padding": (14, 6), "button_padding": (9, 5)},
    "Standard": {"tree_rowheight": 28, "tab_padding": (18, 8), "button_padding": (11, 6)},
    "Comfortable": {"tree_rowheight": 32, "tab_padding": (22, 10), "button_padding": (13, 7)},
}


def responsive_geometry(screen_width: int, screen_height: int, *,
                        preferred_width: int = 1600, preferred_height: int = 900,
                        minimum_width: int = 1024, minimum_height: int = 680) -> str:
    """Fit a centered window to the usable screen without exceeding it."""
    width = max(minimum_width, min(preferred_width, max(minimum_width, screen_width - 80)))
    height = max(minimum_height, min(preferred_height, max(minimum_height, screen_height - 100)))
    width = min(width, screen_width)
    height = min(height, screen_height)
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    return f"{width}x{height}+{x}+{y}"


def fit_window(window: Any, *, preferred_width: int = 1600, preferred_height: int = 900,
               minimum_width: int = 1024, minimum_height: int = 680) -> str:
    geometry = responsive_geometry(
        int(window.winfo_screenwidth()), int(window.winfo_screenheight()),
        preferred_width=preferred_width, preferred_height=preferred_height,
        minimum_width=minimum_width, minimum_height=minimum_height,
    )
    window.minsize(minimum_width, minimum_height)
    window.geometry(geometry)
    return geometry


def apply_theme(gui: Any, density: str = "Standard") -> str:
    density = density if density in DENSITIES else "Standard"
    values = DENSITIES[density]
    style = ttk.Style(gui)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    style.configure(".", background=PALETTE["background"], foreground=PALETTE["text"],
                    font=("Segoe UI", 10))
    style.configure("TFrame", background=PALETTE["background"])
    style.configure("TLabel", background=PALETTE["background"], foreground=PALETTE["text"])
    style.configure("TLabelframe", background=PALETTE["background"], bordercolor=PALETTE["border"], relief="solid")
    style.configure("TLabelframe.Label", background=PALETTE["background"], foreground=PALETTE["text"], font=("Segoe UI", 10, "bold"))
    style.configure("TButton", padding=values["button_padding"], borderwidth=1, relief="flat")
    style.map("TButton", background=[("active", PALETTE["surface_alt"]), ("pressed", PALETTE["selection"])])
    style.configure("Accent.TButton", background=PALETTE["primary"], foreground=PALETTE["primary_text"], font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("active", PALETTE["primary_hover"]), ("pressed", PALETTE["primary_hover"])])
    style.configure("Danger.TButton", foreground=PALETTE["danger"])
    style.map("Danger.TButton", foreground=[("active", PALETTE["danger_hover"])])
    style.configure("TNotebook", background=PALETTE["background"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=values["tab_padding"], font=("Segoe UI", 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", PALETTE["surface"]), ("active", PALETTE["surface_alt"])],
              foreground=[("selected", PALETTE["primary"])])
    style.configure("Treeview", background=PALETTE["surface"], fieldbackground=PALETTE["surface"],
                    foreground=PALETTE["text"], rowheight=values["tree_rowheight"], bordercolor=PALETTE["border"])
    style.map("Treeview", background=[("selected", PALETTE["primary"])], foreground=[("selected", "#FFFFFF")])
    style.configure("Treeview.Heading", background=PALETTE["surface_alt"], foreground=PALETTE["text"],
                    font=("Segoe UI", 10, "bold"), padding=(7, 6), relief="flat")
    style.map("Treeview.Heading", background=[("active", PALETTE["selection"])])
    style.configure("TEntry", fieldbackground=PALETTE["surface"], bordercolor=PALETTE["border"], padding=4)
    style.configure("TCombobox", fieldbackground=PALETTE["surface"], bordercolor=PALETTE["border"], padding=3)
    try:
        gui.configure(background=PALETTE["background"])
    except Exception:
        pass
    _style_native_children(gui)
    _style_action_buttons(gui)
    gui._v3_density = density
    return density


def _walk(widget: Any):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _style_native_children(gui: Any) -> None:
    for widget in _walk(gui):
        try:
            if isinstance(widget, tk.Listbox):
                widget.configure(background=PALETTE["surface"], foreground=PALETTE["text"],
                                 selectbackground=PALETTE["primary"], selectforeground="#FFFFFF",
                                 highlightcolor=PALETTE["primary"], highlightbackground=PALETTE["border"],
                                 relief="flat", borderwidth=1)
            elif isinstance(widget, tk.Text):
                widget.configure(background=PALETTE["surface"], foreground=PALETTE["text"],
                                 insertbackground=PALETTE["text"], selectbackground=PALETTE["primary"],
                                 relief="flat", borderwidth=1)
        except Exception:
            pass


def _style_action_buttons(gui: Any) -> None:
    primary = {"Generate", "Apply Change", "Save Item", "Apply Correction", "Save Reviewed Outcome", "Refresh Assessment"}
    danger = {"Delete", "Delete Selected", "Delete Selected Work Item", "Remove HPLC"}
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Button):
            continue
        try:
            text = str(widget.cget("text")).strip()
            if text in primary:
                widget.configure(style="Accent.TButton")
            elif text in danger or text.startswith("Delete"):
                widget.configure(style="Danger.TButton")
        except Exception:
            pass


def set_density(gui: Any, density: str) -> str:
    return apply_theme(gui, density)


def bind_shortcuts(gui: Any) -> dict[str, Callable[..., Any]]:
    """Bind one documented shortcut map directly to controller methods."""
    def command(name: str):
        def run(_event=None):
            candidate = getattr(gui, name, None)
            if callable(candidate):
                candidate()
            return "break"
        return run

    bindings: dict[str, Callable[..., Any]] = {
        "<Control-s>": command("save_project"),
        "<Control-Shift-S>": command("save_project_as"),
        "<Control-o>": command("load_project"),
        "<Control-n>": command("pm_add_peptide"),
        "<Control-d>": command("pm_duplicate_peptide"),
        "<Control-g>": command("generate_update_plan"),
        "<Control-Return>": command("apply_change"),
        "<Control-e>": command("export_outputs"),
        "<Control-Key-0>": lambda _event=None: (set_density(gui, "Standard"), "break")[-1],
        "<Control-minus>": lambda _event=None: (set_density(gui, "Compact"), "break")[-1],
        "<Control-equal>": lambda _event=None: (set_density(gui, "Comfortable"), "break")[-1],
    }
    for sequence, callback in bindings.items():
        gui.bind_all(sequence, callback, add="+")
    gui._v3_shortcuts = bindings
    return bindings


__all__ = ["DENSITIES", "PALETTE", "apply_theme", "bind_shortcuts", "fit_window", "responsive_geometry", "set_density"]
