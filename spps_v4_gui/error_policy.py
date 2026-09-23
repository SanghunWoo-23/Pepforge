"""Explicit handling for recoverable embedded-SPPS controller failures."""
from __future__ import annotations

from typing import Any


def log_nonfatal(gui: Any, context: str, exc: Exception) -> None:
    """Record a recoverable failure without converting it into a fake success."""
    message = f"{context}: {exc}\n"
    logger = getattr(gui, "_log", None)
    if callable(logger):
        try:
            logger(message)
            return
        except Exception:
            # The Tk log itself can be unavailable during startup/shutdown.
            pass
    try:
        setattr(gui, "_last_nonfatal_error", message.strip())
    except Exception:
        return


__all__ = ["log_nonfatal"]
