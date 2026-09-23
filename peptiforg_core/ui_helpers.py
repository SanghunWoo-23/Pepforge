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
    """Apply the Pepforge suite icon across Tk windows.

    Windows title bars/taskbars prefer ``.ico`` while Tk's cross-platform
    ``iconphoto`` path is more reliable elsewhere.  We try both so packaged
    EXEs do not fall back to the generic feather/window icon in individual
    tools such as PDE.
    """
    ico = ROOT / "assets" / "Pepforge_Icon.ico"
    png = ROOT / "assets" / "Pepforge_Icon.png"
    # On Windows, the small caption/taskbar icon is most reliable through
    # iconbitmap(.ico).  Keep iconphoto as a fallback and for other platforms.
    if os.name == "nt" and ico.exists():
        try:
            window.iconbitmap(default=str(ico))
        except (tk.TclError, OSError) as exc:
            LOGGER.debug("Pepforge .ico icon unavailable: %s", exc)
    if not png.exists():
        return
    try:
        img = tk.PhotoImage(file=str(png))
        window.iconphoto(True, img)
        setattr(window, "_pepforge_icon_img", img)
    except (tk.TclError, OSError) as exc:
        LOGGER.debug("Pepforge PNG icon unavailable: %s", exc)


def open_path(path: str | Path) -> None:
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
