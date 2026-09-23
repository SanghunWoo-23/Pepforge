from __future__ import annotations

from typing import Any


def write_log(owner: Any, message: Any) -> None:
    """Append a diagnostic message without requiring a visible log widget.

    SPPS startup and persistence code may report diagnostics before the optional
    log surface is constructed.  Buffer those messages until a compatible text
    widget is available instead of turning a recoverable diagnostic into a GUI
    launch failure.
    """
    text = str(message)
    widget = getattr(owner, "log_text", None)
    if widget is not None:
        try:
            widget.insert("end", text)
            widget.see("end")
            return
        except Exception:
            # A closing/destroyed Tk widget is no longer a usable sink.  Keep
            # the message so it can still be inspected by another log surface.
            pass

    pending = getattr(owner, "_pending_log_messages", None)
    if not isinstance(pending, list):
        pending = []
        owner._pending_log_messages = pending
    pending.append(text)


def flush_pending_log(owner: Any) -> int:
    """Flush buffered messages to ``owner.log_text`` when it is available."""
    pending = list(getattr(owner, "_pending_log_messages", []) or [])
    if not pending:
        return 0
    widget = getattr(owner, "log_text", None)
    if widget is None:
        return 0

    written = 0
    for message in pending:
        try:
            widget.insert("end", str(message))
            written += 1
        except Exception:
            break
    if written:
        owner._pending_log_messages = pending[written:]
        try:
            widget.see("end")
        except Exception:
            pass
    return written


__all__ = ["write_log", "flush_pending_log"]
