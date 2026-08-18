"""User-writable storage paths for SPPS Planner.

The app may be installed under a protected folder on Windows. Runtime artifacts
should therefore live under a user-writable directory, while bundled CSV files
remain as read-only defaults.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_FOLDER = "SPPS_Planner"


def user_data_dir() -> Path:
    """Return the preferred user-writable data directory."""
    override = os.environ.get("SPPS_PLANNER_USER_DATA")
    if override:
        path = Path(override).expanduser()
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        path = (Path(base) if base else Path.home() / "AppData" / "Local") / APP_FOLDER
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_FOLDER
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_FOLDER
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        if override:
            # An explicit operator path is a contract: surface the error instead
            # of writing data somewhere unexpected.
            raise
        # Sandboxed/read-only-home systems may not permit ~/.local or the
        # platform application-data folder. Keep the application functional in
        # a process-writable temporary location without touching bundled data.
        path = Path(tempfile.gettempdir()) / APP_FOLDER
        path.mkdir(parents=True, exist_ok=True)
    return path


def user_outputs_dir() -> Path:
    path = user_data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_models_dir() -> Path:
    path = user_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_logs_dir() -> Path:
    path = user_data_dir() / "runtime_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_db_dir() -> Path:
    path = user_data_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_file(filename: str, subdir: str | None = None) -> Path:
    base = user_data_dir() / subdir if subdir else user_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def user_data_file(filename: str) -> Path:
    return user_file(filename, "data")
