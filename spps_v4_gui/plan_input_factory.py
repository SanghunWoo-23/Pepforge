"""Build engine PlanInput objects from the accepted desktop UI conditions."""
from __future__ import annotations

from spps_planner.engine import PlanInput


def value(gui, name, default=""):
    try:
        current = getattr(gui, name)
        return current.get() if hasattr(current, "get") else current
    except Exception:
        return default


def number(gui, name, default=0.0):
    try:
        return float(str(value(gui, name, default)).replace(",", "").strip())
    except Exception:
        return float(default)


def integer(gui, name, default=0):
    try:
        return int(round(number(gui, name, default)))
    except Exception:
        return int(default)


def row_number(row, name, default=0.0):
    try:
        current = row.get(name)
        if current is None or str(current).strip() == "":
            return float(default)
        return float(str(current).replace(",", "").strip())
    except Exception:
        return float(default)


def safe_loading(gui):
    loading = number(gui, "pm_loading", 0.8)
    if loading <= 0:
        loading = 0.8
        try:
            gui.pm_loading.set("0.8")
        except Exception:
            pass
    return loading


def safe_scale(gui):
    scale = number(gui, "pm_scale", 400.0)
    if scale <= 0:
        scale = 400.0
        try:
            gui.pm_scale.set("400")
        except Exception:
            pass
    copies = max(1, integer(gui, "pm_copies", 1))
    return scale * copies, scale, copies


def chemistry(gui, text=None):
    text = str(
        text if text is not None else value(gui, "pm_chemistry", "DIC/HOBt")
        or ""
    ).strip()
    normalized = text.upper().replace(" ", "")
    coupling_eq = number(gui, "coupling_eq", 5.0)
    if "HBTU" in normalized:
        return "HBTU", "", "DIEA", "NMP", 10.0
    if "HATU" in normalized:
        return "HATU", "", "DIEA", "DMF", coupling_eq
    if "COMU" in normalized:
        return "COMU", "", "DIEA", "DMF", coupling_eq
    if "DIC" in normalized or "HOBT" in normalized or not text:
        return "DIC", "HOBt", "", "DMF", coupling_eq
    return (
        value(gui, "default_reagent", "DIC") or "DIC",
        value(gui, "default_catalyst", "HOBt") or "",
        value(gui, "default_base", "") or "",
        value(gui, "default_coupling_solution_solvent", "DMF") or "DMF",
        coupling_eq,
    )


def _shared_conditions(gui):
    return {
        "ac_eq": number(gui, "modifier_eq", 3.0),
        "default_coupling_repeats": max(
            1, integer(gui, "coupling_repeats", 1)
        ),
        "default_modifier_repeats": max(
            1, integer(gui, "modifier_repeats", 1)
        ),
        "deprotection_base": (
            value(gui, "default_depro", "Piperidine") or "Piperidine"
        ),
        "deprotection_ratio": (
            value(gui, "default_depro_ratio", "20% in DMF") or "20% in DMF"
        ),
        "deprotection_count": max(
            0, integer(gui, "default_depro_count", 2)
        ),
        "wash_solvent1": value(gui, "default_solvent1", "DMF") or "DMF",
        "wash_solvent1_count": max(
            0, integer(gui, "default_solvent1_count", 6)
        ),
        "wash_solvent2": value(gui, "default_solvent2", "DCM") or "DCM",
        "wash_solvent2_count": max(
            0, integer(gui, "default_solvent2_count", 3)
        ),
        "final_meoh_count": max(0, integer(gui, "final_meoh_count", 0)),
        "loading_dissolve_solvent": (
            value(
                gui,
                "default_loading_dissolve_solvent",
                "90% DCM / 10% DMF",
            )
            or "90% DCM / 10% DMF"
        ),
        "solvent_volume_mode": (
            value(gui, "solvent_volume_mode", "resin_factor")
            or "resin_factor"
        ),
        "amide_ml_per_mmol": number(gui, "amide_ml_per_mmol", 10.0),
        "ctc_ml_per_mmol": number(gui, "ctc_ml_per_mmol", 5.0),
        "solvent_molarity_m": number(gui, "solvent_molarity_m", 0.2),
        "loading_aa_eq": number(gui, "loading_aa_eq", 2.0),
        "loading_diea_eq": number(gui, "loading_diea_eq", 4.0),
        "cleavage_reserve_mL": max(0.0, number(gui, "cleavage_reserve_mL", 0.0)),
        "short_peptide_coupling_eq": number(
            gui, "short_peptide_coupling_eq", 2.0
        ),
    }


def build_editor_plan_input(gui, resin, reagent_eq_follows=None):
    total_scale, _, _ = safe_scale(gui)
    reagent, catalyst, base, solvent, coupling_eq = chemistry(gui)
    sequence = str(
        value(gui, "pm_sequence", "") or ""
    ).strip()
    if reagent_eq_follows is None:
        reagent_eq_follows = bool(value(gui, "reagent_range_mode", False))
    return PlanInput(
        sequence=sequence,
        resin=resin,
        scale_mmol=total_scale,
        resin_loading_mmol_g=safe_loading(gui),
        coupling_eq=coupling_eq,
        default_coupling_reagent=reagent,
        default_catalyst=catalyst,
        default_base=base,
        default_reaction_solvent=solvent,
        default_reagent_eq=number(gui, "default_reagent_eq", coupling_eq),
        default_reagent_count=max(
            0, integer(gui, "default_reagent_count", 1)
        ),
        default_catalyst_eq=number(
            gui, "default_catalyst_eq", coupling_eq if catalyst else 0.0
        ),
        default_catalyst_count=max(
            0,
            integer(
                gui, "default_catalyst_count", 1 if catalyst else 0
            ),
        ),
        default_base_eq=number(
            gui, "default_base_eq", coupling_eq if base else 0.0
        ),
        default_base_count=max(
            0, integer(gui, "default_base_count", 1 if base else 0)
        ),
        reagent_eq_follows_coupling_eq=bool(reagent_eq_follows),
        auto_short_peptide_eq=False,
        step_overrides_text="",
        cleavage_eq_override=number(gui, "cleavage_eq_override", 0.0),
        cleavage_preset=value(gui, "cleavage_preset", "AUTO") or "AUTO",
        cleavage_components_text=value(
            gui, "cleavage_components_text", ""
        ),
        loading_time_h=number(gui, "loading_time_h", 0.0),
        cleavage_time_h=number(gui, "cleavage_time_h", 0.0),
        **_shared_conditions(gui),
    )


def build_batch_plan_input(gui, row, reagent_eq_follows=None):
    copies = max(1, int(round(row_number(row, "Copies", 1))))
    scale_each = row_number(row, "Scale mmol", 0.2)
    coupling_eq = number(
        gui, "batch_coupling_eq", number(gui, "coupling_eq", 5.0)
    )
    chemistry_text = str(row.get("Chemistry", "") or "DIC/HOBt")
    if "HBTU" in chemistry_text.upper().replace(" ", ""):
        reagent, catalyst, base, solvent = "HBTU", "", "DIEA", "NMP"
        reagent_eq = number(gui, "batch_hbtu_eq", 10.0)
        reagent_count, catalyst_eq, catalyst_count = 1, 0.0, 0
        base_eq = number(gui, "default_base_eq", reagent_eq)
        if base_eq <= 0:
            base_eq = reagent_eq
        base_count = max(1, integer(gui, "default_base_count", 1))
        follows = False
    else:
        reagent = str(value(gui, "default_reagent", "DIC") or "DIC")
        catalyst = str(value(gui, "default_catalyst", "HOBt") or "")
        base = str(value(gui, "default_base", "") or "")
        solvent = str(
            value(gui, "default_coupling_solution_solvent", "DMF") or "DMF"
        )
        reagent_eq = number(gui, "default_reagent_eq", coupling_eq)
        reagent_count = max(0, integer(gui, "default_reagent_count", 1))
        catalyst_eq = number(
            gui, "default_catalyst_eq", coupling_eq if catalyst else 0.0
        )
        catalyst_count = max(
            0,
            integer(gui, "default_catalyst_count", 1 if catalyst else 0),
        )
        base_eq = number(
            gui, "default_base_eq", coupling_eq if base else 0.0
        )
        base_count = max(
            0, integer(gui, "default_base_count", 1 if base else 0)
        )
        follows = (
            bool(value(gui, "reagent_range_mode", False))
            if reagent_eq_follows is None
            else bool(reagent_eq_follows)
        )
    return PlanInput(
        sequence=str(row.get("Sequence", "") or "").strip(),
        resin=str(row.get("Resin", "") or "Rink Amide AM"),
        scale_mmol=scale_each * copies,
        resin_loading_mmol_g=row_number(row, "Loading", 0.8) or 0.8,
        coupling_eq=coupling_eq,
        default_coupling_reagent=reagent,
        default_catalyst=catalyst,
        default_base=base,
        default_reaction_solvent=solvent,
        default_reagent_eq=reagent_eq,
        default_reagent_count=reagent_count,
        default_catalyst_eq=catalyst_eq,
        default_catalyst_count=catalyst_count,
        default_base_eq=base_eq,
        default_base_count=base_count,
        reagent_eq_follows_coupling_eq=follows,
        auto_short_peptide_eq=False,
        cleavage_preset="AUTO",
        **_shared_conditions(gui),
    )


__all__ = [
    "build_batch_plan_input",
    "build_editor_plan_input",
    "chemistry",
    "integer",
    "number",
    "row_number",
    "safe_loading",
    "safe_scale",
    "value",
]
