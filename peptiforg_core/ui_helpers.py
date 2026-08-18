from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("pepforge.ui")


def set_pepforge_icon(window: tk.Tk | tk.Toplevel) -> None:
    """Apply the Pepforge icon without hiding icon-loading failures."""
    png = ROOT / "assets" / "Pepforge_Icon.png"
    if not png.exists():
        return
    try:
        img = tk.PhotoImage(file=str(png))
        window.iconphoto(True, img)
        setattr(window, "_pepforge_icon_img", img)
    except (tk.TclError, OSError) as exc:
        LOGGER.debug("Pepforge icon unavailable: %s", exc)


def open_path(path: str | Path) -> None:
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
