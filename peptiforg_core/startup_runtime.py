from __future__ import annotations

"""Small startup-timing utilities for Pepforge first-party GUIs.

The logger measures UI visibility and lazy backend readiness.  It does not
preload scientific backends or change scientific results.
"""

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any
import json


@dataclass
class StartupTrace:
    tool: str
    log_dir: Path | None = None
    _start: float = field(default_factory=perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, event: str, **detail: Any) -> float:
        elapsed_ms = (perf_counter() - self._start) * 1000.0
        row = {"event": str(event), "elapsed_ms": round(elapsed_ms, 2), **detail}
        self.events.append(row)
        return elapsed_ms

    def write(self) -> Path | None:
        if self.log_dir is None:
            return None
        out = Path(self.log_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"startup_{self.tool}.json"
        payload = {
            "tool": self.tool,
            "events": self.events,
            "note": "Wall-clock startup instrumentation only; not a scientific benchmark.",
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path


def mark_window_visible(window: Any, trace: StartupTrace) -> None:
    """Record first paint after Tk has processed pending geometry work.

    The marker is idempotent so an integration wrapper can safely call it after
    a base GUI that already recorded the first visible shell.
    """
    if any(row.get("event") == "first_window_visible" for row in trace.events):
        return
    try:
        window.update_idletasks()
        trace.mark("first_window_visible")
        trace.write()
    except Exception as exc:
        trace.mark("first_window_visible_unavailable", error=type(exc).__name__)
        trace.write()


__all__ = ["StartupTrace", "mark_window_visible"]
