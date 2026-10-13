from __future__ import annotations
import os, sys
from pathlib import Path
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]

def _asset_path(name: str) -> Path:
    # PyInstaller one-file/frozen support
    base = Path(getattr(sys, "_MEIPASS", ROOT))
    p = base / "assets" / name
    if p.exists():
        return p
    return ROOT / "assets" / name

def set_spps_planner_icon(window: tk.Tk | tk.Toplevel) -> None:
    """Apply the SPPS Planner icon to standalone Tk windows.

    The historical function name is retained only as an import-compatibility API.
    SPPS Planner release assets are SPPS-only and never fall back to Pepforge icons.
    """
    applied = False
    ico = _asset_path("SPPS_Planner_Icon.ico")
    if os.name == "nt" and ico.exists():
        try:
            window.iconbitmap(default=str(ico))
            applied = True
        except tk.TclError:
            try:
                window.iconbitmap(str(ico))
                applied = True
            except tk.TclError:
                applied = False

    if not applied:
        png = _asset_path("SPPS_Planner_Icon.png")
        if png.exists():
            try:
                img = tk.PhotoImage(file=str(png))
                window.iconphoto(True, img)
                # Keep a Python reference; otherwise Tk may discard the image.
                setattr(window, "_spps_icon_img", img)
                applied = True
            except tk.TclError:
                applied = False

    setattr(window, "_spps_icon_status", "OK" if applied else "MISSING")

# Backward-compatible historical import name. New code must use set_spps_planner_icon.
set_pepforge_icon = set_spps_planner_icon

def open_path(path: str | Path) -> None:
    p = Path(path)
    if os.name == "nt":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')
    else:
        os.system(f'xdg-open "{p}"')
