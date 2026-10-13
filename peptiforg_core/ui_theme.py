from __future__ import annotations

"""Single Pepforge Tk theme contract shared by first-party windows."""

import logging
import tkinter as tk
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



def maximize_when_roomy(window, *, min_width: int = 1500, min_height: int = 850) -> bool:
    """Maximize a first-party window on roomy desktops, without forcing it on small screens."""
    try:
        if int(window.winfo_screenwidth()) < min_width or int(window.winfo_screenheight()) < min_height:
            return False
        if str(getattr(window, "tk", "")) and window.tk.call("tk", "windowingsystem") == "win32":
            window.state("zoomed")
        else:
            sw, sh = int(window.winfo_screenwidth()), int(window.winfo_screenheight())
            window.geometry(f"{max(1100, sw-24)}x{max(700, sh-80)}+0+0")
        return True
    except Exception:
        LOGGER.debug("Window maximize skipped", exc_info=True)
        return False


def bind_canvas_navigation(canvas: tk.Canvas, *, vertical: bool = True, horizontal: bool = True) -> None:
    """Mouse-wheel + Shift-wheel + middle-button drag navigation for Pepforge canvases."""
    def _wheel(event):
        try:
            delta = int(getattr(event, "delta", 0) or 0)
            number = int(getattr(event, "num", 0) or 0)
            if number == 4:
                units = -3
            elif number == 5:
                units = 3
            elif delta:
                units = -max(1, abs(delta)//120) if delta > 0 else max(1, abs(delta)//120)
            else:
                return None
            if horizontal and (int(getattr(event, "state", 0) or 0) & 0x0001):
                canvas.xview_scroll(units, "units")
            elif vertical:
                canvas.yview_scroll(units, "units")
            elif horizontal:
                canvas.xview_scroll(units, "units")
            return "break"
        except Exception:
            return None

    def _middle_press(event):
        try:
            canvas.scan_mark(event.x, event.y)
            canvas.configure(cursor="fleur")
            return "break"
        except Exception:
            return None

    def _middle_drag(event):
        try:
            canvas.scan_dragto(event.x, event.y, gain=1)
            return "break"
        except Exception:
            return None

    def _middle_release(_event):
        try:
            canvas.configure(cursor="")
        except Exception:
            pass
        return "break"

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.bind(sequence, _wheel, add="+")
    canvas.bind("<ButtonPress-2>", _middle_press, add="+")
    canvas.bind("<B2-Motion>", _middle_drag, add="+")
    canvas.bind("<ButtonRelease-2>", _middle_release, add="+")

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


def bind_page_navigation(container: tk.Misc, canvas: tk.Canvas) -> None:
    """Install conventional large-form scrolling on every descendant widget.

    The supplied SPPS Planner V7 R2 uses a bindtag-based page scroll contract:
    ordinary wheel input moves the outer page even when the pointer is over an
    Entry, Text, Combobox, or table.  Pepforge uses the same interaction here.
    No middle-button panning is installed.
    """
    scroll_tag = f"PepforgePageScroll_{id(canvas)}"

    def _wheel(event):
        try:
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                canvas.yview_scroll(-1 if delta > 0 else 1, "units")
                return "break"
            num = int(getattr(event, "num", 0) or 0)
            if num in (4, 5):
                canvas.yview_scroll(-1 if num == 4 else 1, "units")
                return "break"
        except tk.TclError:
            return None
        return None

    try:
        owner = canvas.winfo_toplevel()
        owner.bind_class(scroll_tag, "<MouseWheel>", _wheel)
        owner.bind_class(scroll_tag, "<Button-4>", _wheel)
        owner.bind_class(scroll_tag, "<Button-5>", _wheel)
    except tk.TclError:
        return

    def _install(widget):
        try:
            tags = list(widget.bindtags())
            if scroll_tag not in tags:
                tags.insert(1, scroll_tag)
                widget.bindtags(tuple(tags))
            for child in widget.winfo_children():
                _install(child)
        except tk.TclError:
            return

    _install(container)
    try:
        canvas.bind("<Prior>", lambda _e: (canvas.yview_scroll(-1, "pages"), "break")[-1], add="+")
        canvas.bind("<Next>", lambda _e: (canvas.yview_scroll(1, "pages"), "break")[-1], add="+")
        canvas.bind("<Home>", lambda _e: (canvas.yview_moveto(0.0), "break")[-1], add="+")
        canvas.bind("<End>", lambda _e: (canvas.yview_moveto(1.0), "break")[-1], add="+")
    except tk.TclError:
        pass
