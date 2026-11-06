from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "spps_planner_app"
for path in (ROOT, APP):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

# Keep tests isolated from a developer's real SPPS Planner profile and make
# the suite runnable in containers whose home directory is read-only.
_TEST_PROFILE = Path(tempfile.gettempdir()) / "spps-planner-test-profile"
os.environ.setdefault("XDG_DATA_HOME", str(_TEST_PROFILE / "data"))
os.environ.setdefault("XDG_CONFIG_HOME", str(_TEST_PROFILE / "config"))


def _normalize_gui_test_marker() -> None:
    """Make legacy DISPLAY-based GUI skips reflect real Tk availability.

    Windows/macOS can run Tk without DISPLAY, while Linux can have a stale
    DISPLAY value that points to no server.  Existing GUI tests use DISPLAY as
    their collection-time marker, so probe Tk once and normalize that marker.
    """
    if sys.platform.startswith("linux"):
        display = str(os.environ.get("DISPLAY", "") or "").strip()
        if display.startswith(":"):
            number = display[1:].split(".", 1)[0]
            if number.isdigit() and not Path(f"/tmp/.X11-unix/X{number}").exists():
                os.environ.pop("DISPLAY", None)
                return
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
    except Exception:
        os.environ.pop("DISPLAY", None)
    else:
        os.environ.setdefault("DISPLAY", "native")


_normalize_gui_test_marker()
