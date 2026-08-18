"""Direct calculation lookups used by the V3.0.0 desktop workflows."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from spps_v4_gui import catalogs


@lru_cache(maxsize=1)
def _database_records() -> dict[str, tuple[float, float]]:
    records: dict[str, tuple[float, float]] = {}
    try:
        from spps_planner.database import load_compounds, load_reagent_library

        compounds = load_compounds()
        for _, row in compounds.iterrows():
            names = (
                row.get("Token", ""),
                row.get("Reagent/protected form", ""),
            )
            mw = _number(row.get("Reagent MW (g/mol)", 0))
            for name in names:
                key = normalized(name)
                if key:
                    records[key] = (mw, 0.0)
        reagents = load_reagent_library()
        for _, row in reagents.iterrows():
            key = normalized(row.get("name", ""))
            if key:
                records[key] = (
                    _number(row.get("MW", 0)),
                    _number(row.get("density_g_mL", 0)),
                )
    except Exception:
        pass
    return records


def _number(value: Any) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except Exception:
        return 0.0


def normalized(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(value or "").lower())


def canonical(value: Any) -> str:
    raw = str(value or "").strip()
    key = normalized(raw)
    aliases = {
        "hobt": "HOBt",
        "hobtanhydrous": "HOBt",
        "dic": "DIC",
        "diea": "DIEA",
        "dipea": "DIEA",
        "ac2o": "Acetic anhydride (Ac2O)",
        "aceticanhydride": "Acetic anhydride (Ac2O)",
    }
    return aliases.get(key, raw)


def material_lookup(name: Any) -> tuple[float, float]:
    raw = str(name or "").strip()
    key = normalized(raw)
    if not key:
        return 0.0, 0.0
    if key in _database_records():
        return _database_records()[key]
    mw = 0.0
    for candidate, value in catalogs.MW_FALLBACK.items():
        if normalized(candidate) == key:
            mw = float(value)
            break
    density = 0.0
    for candidate, value in catalogs.LIQUID_DENSITY.items():
        if normalized(candidate) == key:
            density = float(value)
            break
    return mw, density


def options_for_column(gui: Any, column: str) -> list[str]:
    from spps_v4_gui.custom_db_workflow import options_for_column as add_custom

    if column == "Unit name":
        base = list(getattr(gui, "UNIT_VALUES", catalogs.UNIT_VALUES) or [])
    elif column == "Reagent 1":
        base = list(getattr(gui, "REAGENT_VALUES", catalogs.REAGENT_VALUES) or [])
    elif column == "Reagent 2 / catalyst":
        base = list(
            getattr(gui, "CATALYST_VALUES", catalogs.CATALYST_VALUES) or [],
        )
    elif column == "Base":
        base = list(getattr(gui, "BASE_VALUES", catalogs.BASE_VALUES) or [])
    elif column == "Coupling solvent":
        base = list(
            getattr(gui, "SOLVENT_VALUES", catalogs.SOLVENT_VALUES) or [],
        )
    else:
        base = []
    return add_custom(gui, column, base)


def namespace() -> dict[str, Any]:
    """Compatibility-free context accepted by remaining workflow signatures."""
    return {}


__all__ = [
    "canonical",
    "material_lookup",
    "namespace",
    "normalized",
    "options_for_column",
]
