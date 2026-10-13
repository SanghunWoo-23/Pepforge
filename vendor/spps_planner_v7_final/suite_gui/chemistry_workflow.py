"""Non-generating chemistry preset actions for SPPS Planner V3.0.0."""
from __future__ import annotations

from typing import Any


def _set(gui: Any, name: str, value: Any) -> None:
    try:
        getattr(gui, name).set(value)
    except Exception:
        pass


def _finish(gui: Any) -> None:
    try:
        gui.schedule_autosave()
    except Exception:
        pass


def apply_dic_hobt(gui: Any) -> None:
    for name, value in (
        ("pm_chemistry", "DIC/HOBt"),
        ("default_reagent", "DIC"),
        ("default_reagent_eq", "5"),
        ("default_reagent_count", "1"),
        ("default_catalyst", "HOBt"),
        ("default_catalyst_eq", "5"),
        ("default_catalyst_count", "1"),
        ("default_base", ""),
        ("default_base_eq", "0"),
        ("default_base_count", "0"),
        ("default_coupling_solution_solvent", "DMF"),
        ("coupling_eq", "5"),
    ):
        _set(gui, name, value)
    _finish(gui)


def apply_hbtu_nmm(gui: Any) -> None:
    """Apply the lab HBTU + NMM method without treating NMM as a solvent."""
    for name, value in (
        ("pm_chemistry", "HBTU/NMM"),
        ("default_reagent", "HBTU"),
        ("default_reagent_eq", "10"),
        ("default_reagent_count", "1"),
        ("default_catalyst", ""),
        ("default_catalyst_eq", "0"),
        ("default_catalyst_count", "0"),
        ("default_base", "NMM"),
        ("default_base_eq", "5"),
        ("default_base_count", "1"),
        ("default_coupling_solution_solvent", "DMF"),
        ("coupling_eq", "10"),
        ("batch_hbtu_eq", "10"),
        ("batch_hbtu_conc", "0.4"),
        ("batch_nmm_eq", "5"),
        ("batch_nmm_conc", "0.8"),
    ):
        _set(gui, name, value)
    _finish(gui)


def apply_hbtu_nmp(gui: Any) -> None:
    """Legacy name retained for saved V6 routes; behavior is HBTU + NMM."""
    apply_hbtu_nmm(gui)


__all__ = ["apply_dic_hobt", "apply_hbtu_nmm", "apply_hbtu_nmp"]
