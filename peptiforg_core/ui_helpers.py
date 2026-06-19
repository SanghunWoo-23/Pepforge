from __future__ import annotations
import os, sys
from pathlib import Path
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]

def set_pepforge_icon(window: tk.Tk | tk.Toplevel) -> None:
    """Apply the Pepforge icon to every standalone Tk window."""
    try:
        png = ROOT / "assets" / "Pepforge_Icon.png"
        if png.exists():
            img = tk.PhotoImage(file=str(png))
            window.iconphoto(True, img)
            # keep a Python reference; otherwise Tk may discard the image
            setattr(window, "_pepforge_icon_img", img)
    except Exception:
        pass

def open_path(path: str | Path) -> None:
    p = Path(path)
    if os.name == "nt":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')
    else:
        os.system(f'xdg-open "{p}"')
