from __future__ import annotations

"""Single Pepforge Tk theme contract shared by first-party windows."""

import logging
from tkinter import ttk

LOGGER = logging.getLogger(__name__)
NAVY = "#102A43"
BLUE = "#2563EB"
GREEN = "#169B62"
BACKGROUND = "#F3F6FA"
SURFACE = "#FFFFFF"
MUTED = "#526170"
BORDER = "#D8E1EA"
DENSITIES = {
    "Compact": {"tree_rowheight": 24, "button_padding": (9, 5), "nav_padding": (10, 7)},
    "Standard": {"tree_rowheight": 28, "button_padding": (11, 6), "nav_padding": (12, 9)},
    "Comfortable": {"tree_rowheight": 32, "button_padding": (13, 7), "nav_padding": (14, 11)},
}


def responsive_geometry(screen_width: int, screen_height: int, *,
                        preferred_width: int = 1480, preferred_height: int = 860,
                        minimum_width: int = 1100, minimum_height: int = 680) -> str:
    width = max(minimum_width, min(preferred_width, max(minimum_width, screen_width - 80)))
    height = max(minimum_height, min(preferred_height, max(minimum_height, screen_height - 100)))
    width, height = min(width, screen_width), min(height, screen_height)
    x, y = max(0, (screen_width - width) // 2), max(0, (screen_height - height) // 2)
    return f"{width}x{height}+{x}+{y}"


def fit_window(window, *, preferred_width: int = 1480, preferred_height: int = 860,
               minimum_width: int = 1100, minimum_height: int = 680) -> str:
    geometry = responsive_geometry(
        int(window.winfo_screenwidth()), int(window.winfo_screenheight()),
        preferred_width=preferred_width, preferred_height=preferred_height,
        minimum_width=minimum_width, minimum_height=minimum_height,
    )
    window.minsize(minimum_width, minimum_height)
    window.geometry(geometry)
    return geometry


def apply_pepforge_theme(window, density: str = "Standard") -> ttk.Style:
    density = density if density in DENSITIES else "Standard"
    values = DENSITIES[density]
    try:
        window.configure(background=BACKGROUND)
    except Exception:
        LOGGER.debug("Window background could not be applied", exc_info=True)
    style = ttk.Style(window)
    try:
        style.theme_use("clam")
    except Exception:
        LOGGER.debug("Tk clam theme unavailable", exc_info=True)
    style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=NAVY)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Surface.TFrame", background=SURFACE, relief="solid", borderwidth=1)
    style.configure("Sidebar.TFrame", background=SURFACE)
    style.configure("TLabel", background=BACKGROUND, foreground=NAVY)
    style.configure("Surface.TLabel", background=SURFACE, foreground=NAVY)
    style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED)
    style.configure("SurfaceMuted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("SurfaceSection.TLabel", background=SURFACE, foreground=NAVY, font=("Segoe UI", 11, "bold"))
    style.configure("TLabelframe", background=BACKGROUND, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BACKGROUND, foreground=NAVY, font=("Segoe UI", 10, "bold"))
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
    style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(14, 8))
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground=NAVY, background=BACKGROUND)
    style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=MUTED, background=BACKGROUND)
    style.configure("Card.TFrame", padding=18, relief="solid", borderwidth=1, background=SURFACE, bordercolor=BORDER)
    style.configure("Card.TLabelframe", padding=8, relief="solid", borderwidth=1, background=SURFACE)
    style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=NAVY)
    style.configure("Input.TLabelframe", padding=8, relief="solid", borderwidth=1, background=BACKGROUND, bordercolor=BORDER)
    style.configure("Input.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=NAVY, background=BACKGROUND)
    style.configure("CardTitle.TLabel", font=("Segoe UI Semibold", 13), foreground=NAVY, background=SURFACE)
    style.configure("CardText.TLabel", font=("Segoe UI", 10), foreground=MUTED, background=SURFACE)
    style.configure("Step.TLabel", font=("Segoe UI Semibold", 9), foreground=BLUE, background=SURFACE)
    style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 9), foreground="#FFFFFF", background=BLUE, bordercolor=BLUE)
    style.map("Accent.TButton", background=[("active", "#1D4ED8"), ("disabled", "#9DB7E8")])
    style.configure("Tool.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8), foreground=NAVY, background="#E9F0F8", bordercolor="#C8D5E3")
    style.map("Tool.TButton", background=[("active", "#DCE8F5")])
    style.configure("TButton", padding=values["button_padding"])
    style.configure("Nav.TButton", anchor="w", padding=values["nav_padding"], relief="flat")
    style.configure("NavSelected.TButton", anchor="w", padding=values["nav_padding"], relief="flat", background="#DCE8FF", foreground=BLUE, font=("Segoe UI", 10, "bold"))
    style.map("NavSelected.TButton", background=[("active", "#DCE8FF"), ("pressed", "#DCE8FF")])
    style.configure("Treeview", rowheight=values["tree_rowheight"], font=("Segoe UI", 9))
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), foreground=NAVY)
    style.configure("PepforgeGreen.Horizontal.TProgressbar", troughcolor="#e8edf3", background=GREEN, lightcolor=GREEN, darkcolor=GREEN)
    window._pepforge_density = density
    return style


def set_density(window, density: str) -> ttk.Style:
    return apply_pepforge_theme(window, density)
