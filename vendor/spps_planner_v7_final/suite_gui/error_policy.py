"""Small explicit error policy for controller/workflow boundaries."""
from __future__ import annotations
from typing import Any


def log_nonfatal(gui: Any, context: str, exc: Exception) -> None:
    """Record a recoverable UI/logging failure instead of silently swallowing it."""
    message = f"{context}: {exc}\n"
    logger = getattr(gui, "_log", None)
    if callable(logger):
        try:
            logger(message)
            return
        except Exception:
            pass
    # Keep the failure inspectable even when the Tk log widget is unavailable.
    try:
        setattr(gui, "_last_nonfatal_error", message.strip())
    except Exception:
        return


__all__ = ["log_nonfatal"]
