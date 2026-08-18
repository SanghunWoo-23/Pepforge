from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _user_data_root() -> Path:
    """Return a writable Pepforge data root without modifying packaged resources."""
    explicit = os.environ.get("PEPFORGE_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Pepforge"
        return Path.home() / ".pepforge"
    return PROJECT_ROOT


USER_DATA_ROOT = _user_data_root()
SANDBOX_ROOT = USER_DATA_ROOT / "workspace"


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "tool"


@dataclass(frozen=True)
class ToolSandbox:
    name: str
    root: Path
    inputs: Path
    outputs: Path
    cache: Path
    logs: Path

    def ensure(self) -> "ToolSandbox":
        for path in (self.root, self.inputs, self.outputs, self.cache, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        return self

    def environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "PEPFORGE_HOME": str(USER_DATA_ROOT),
            "PEPFORGE_SANDBOX": str(self.root),
            "PEPFORGE_INPUT_DIR": str(self.inputs),
            "PEPFORGE_OUTPUT_DIR": str(self.outputs),
            "PEPFORGE_CACHE_DIR": str(self.cache),
            "PEPFORGE_LOG_DIR": str(self.logs),
            "PYTHONPYCACHEPREFIX": str(self.cache / "pycache"),
        })
        if self.name == "spps":
            # Keep the embedded standalone SPPS V2 autosave/custom DB inside
            # Pepforge's own writable sandbox rather than a second app folder.
            env["SPPS_PLANNER_USER_DATA"] = str(self.root)
        return env


def get_tool_sandbox(tool_name: str) -> ToolSandbox:
    name = _safe_name(tool_name)
    root = SANDBOX_ROOT / name
    return ToolSandbox(
        name=name,
        root=root,
        inputs=root / "inputs",
        outputs=root / "outputs",
        cache=root / "cache",
        logs=root / "logs",
    ).ensure()


def configured_output(default: Path, tool_name: str) -> Path:
    value = os.environ.get("PEPFORGE_OUTPUT_DIR", "").strip()
    output = Path(value) if value else default
    output.mkdir(parents=True, exist_ok=True)
    return output
