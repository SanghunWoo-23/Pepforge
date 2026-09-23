"""Small, explicit lazy-import helpers for GUI-first startup paths.

The proxy defers importing an optional/heavy module until one of its attributes
is actually used. It does not replace functions/classes at runtime and does not
silently substitute missing dependencies: the original ImportError is raised at
first real use so callers can surface an honest unavailable/error state.
"""
from __future__ import annotations

from importlib import import_module
from threading import RLock
from types import ModuleType
from typing import Any


class LazyModuleProxy:
    """Thread-safe proxy that imports one named module on first attribute use."""

    __slots__ = ("_module_name", "_module", "_lock")

    def __init__(self, module_name: str) -> None:
        self._module_name = str(module_name)
        self._module: ModuleType | None = None
        self._lock = RLock()

    @property
    def module_name(self) -> str:
        return self._module_name

    @property
    def is_loaded(self) -> bool:
        return self._module is not None

    def load(self) -> ModuleType:
        module = self._module
        if module is not None:
            return module
        with self._lock:
            module = self._module
            if module is None:
                module = import_module(self._module_name)
                self._module = module
        return module

    def __getattr__(self, name: str) -> Any:
        return getattr(self.load(), name)

    def __dir__(self) -> list[str]:
        if self._module is None:
            return ["module_name", "is_loaded", "load"]
        return sorted(set(dir(type(self)) + dir(self._module)))

    def __repr__(self) -> str:
        state = "loaded" if self.is_loaded else "pending"
        return f"<LazyModuleProxy {self._module_name!r} {state}>"


def lazy_module(module_name: str) -> LazyModuleProxy:
    """Return a lazy module proxy for a GUI/backend boundary."""

    return LazyModuleProxy(module_name)
