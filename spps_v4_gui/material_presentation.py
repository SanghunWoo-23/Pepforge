"""User-facing material and resin presentation rules.

These helpers contain no Tk layout or synthesis-engine state.  Keeping them
separate makes the accepted display contract reusable and directly testable.
"""
from __future__ import annotations

import re

import pandas as pd

from spps_v4_gui import catalogs


LIQUID_NAMES = {
    "dic", "diea", "dipea", "dmf", "dcm", "mc", "mc/dcm", "nmp",
    "tfa", "tis", "edt", "acoh", "acetic acid", "tfe", "tee",
    "piperidine", "water", "h2o", "dw", "dw / water", "meoh",
    "methanol", "acetic anhydride", "ac2o", "tea", "triethylamine",
    "pyridine", "thioanisole", "anisole", "dms", "dmso",
    "triethylsilane",
}
AA_REAGENT_NAMES = {
    "A": "Fmoc-Ala-OH", "R": "Fmoc-Arg(Pbf)-OH",
    "N": "Fmoc-Asn(Trt)-OH", "D": "Fmoc-Asp(OtBu)-OH",
    "C": "Fmoc-Cys(Trt)-OH", "Q": "Fmoc-Gln(Trt)-OH",
    "E": "Fmoc-Glu(OtBu)-OH", "G": "Fmoc-Gly-OH",
    "H": "Fmoc-His(Trt)-OH", "I": "Fmoc-Ile-OH",
    "L": "Fmoc-Leu-OH", "K": "Fmoc-Lys(Boc)-OH",
    "M": "Fmoc-Met-OH", "F": "Fmoc-Phe-OH", "P": "Fmoc-Pro-OH",
    "S": "Fmoc-Ser(tBu)-OH", "T": "Fmoc-Thr(tBu)-OH",
    "W": "Fmoc-Trp(Boc)-OH", "Y": "Fmoc-Tyr(tBu)-OH",
    "V": "Fmoc-Val-OH",
}


def user_resin_label(gui=None, value=""):
    """Return the exact operator-facing resin label used by the release."""
    try:
        raw = str(value or "").strip()
        if not raw and gui is not None and hasattr(gui, "pm_resin"):
            raw = str(gui.pm_resin.get() or "").strip()
        if not raw:
            return "Rink Amide AM"
        if raw.lower() in {"ctc/trityl", "ctc_trityl"}:
            return "2-CTC"
        return raw
    except Exception:
        return "Rink Amide AM"


def numeric(value, default=0.0):
    try:
        if value is None:
            return default
        text = str(value).replace(",", "").strip()
        return float(text) if text else default
    except Exception:
        return default


def format_number(value, digits=3):
    try:
        number = float(value)
        if abs(number - round(number)) < 1e-9:
            return str(int(round(number)))
        return f"{number:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value or "")


def base_material_name(value):
    return str(value or "").strip().lower().split(" -")[0].strip()


def is_liquid(name="", cls="", state="", unit="", reagent=""):
    base = base_material_name(name)
    reagent_base = base_material_name(reagent)
    name_text = str(name or "").strip().lower()
    reagent_text = str(reagent or "").strip().lower()
    class_text = str(cls or "").strip().lower()
    state_text = str(state or "").strip().lower()
    unit_text = str(unit or "").strip().lower()
    if unit_text == "ml" or state_text in {"liquid", "solution", "mixture"}:
        return True
    if state_text in {"solid", "solid_wv", "powder"}:
        return False
    if (
        base in LIQUID_NAMES
        or reagent_base in LIQUID_NAMES
        or name_text in LIQUID_NAMES
        or reagent_text in LIQUID_NAMES
    ):
        return True
    if base in {"dic", "diea", "dipea"} or reagent_base in {
        "dic", "diea", "dipea"
    }:
        return True
    return "solvent" in class_text or "solution" in class_text


def extract_ml_from_amount(value):
    """Extract an mL component from legacy combined values such as g;mL."""
    match = re.search(
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*mL\b",
        str(value or ""),
        flags=re.I,
    )
    if not match:
        return 0.0
    try:
        return float(match.group(1))
    except Exception:
        return 0.0


def clean_operator_table(gui, frame, *, total=False):
    """Normalize a material table without changing its calculation values."""
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame() if frame is None else frame
    out = frame.copy().astype(object).where(pd.notna(frame), "")
    resin_label = user_resin_label(gui)
    for index, row in out.iterrows():
        material = str(
            row.get("material", row.get("component", "")) or ""
        ).strip()
        canonical_material = catalogs.canonical_unit_name(material)
        if canonical_material != material and "material" in out.columns:
            out.at[index, "material"] = canonical_material
            material = canonical_material
        reagent = str(row.get("reagent", "") or "").strip()
        material_class = str(
            row.get("class", row.get("role", "")) or ""
        ).strip()
        state = str(row.get("physical_state", "") or "").strip()
        unit = str(row.get("unit", "") or "").strip()
        step = str(row.get("step", "") or "").strip().lower()
        if (
            step == "resin"
            or material.lower() == "resin"
            or (
                "resin" in material_class.lower()
                and (
                    "ctc" in material.lower()
                    or "trityl" in material.lower()
                    or not material
                )
            )
        ):
            if "material" in out.columns:
                out.at[index, "material"] = resin_label
            if "reagent" in out.columns:
                out.at[index, "reagent"] = resin_label
            if (
                "class" in out.columns
                and material_class in {"CTC/Trityl", "Amide"}
            ):
                out.at[index, "class"] = "Resin"
            material = resin_label
        if material_class.upper() == "AA" and material.startswith("Fmoc-"):
            if "class" in out.columns:
                out.at[index, "class"] = "AA/Chemical"
        if not is_liquid(material, material_class, state, unit, reagent):
            continue
        density = numeric(
            row.get("density_g_mL", row.get("Density(g/mL)", "")), 0.0
        )
        grams = numeric(
            row.get("planned_g", row.get("total_g", row.get("approx_g", ""))),
            0.0,
        )
        milliliters = numeric(
            row.get(
                "planned_mL",
                row.get("total_mL", row.get("volume_mL", "")),
            ),
            0.0,
        )
        if milliliters <= 0:
            milliliters = extract_ml_from_amount(
                row.get("total amount", row.get("Amount", ""))
            )
        if milliliters <= 0 and grams > 0 and density > 0:
            milliliters = grams / density
        for column in ("planned_g", "planned_mg", "approx_g", "total_g"):
            if column in out.columns:
                out.at[index, column] = ""
        for column in ("planned_mL", "total_mL", "volume_mL"):
            if column in out.columns and milliliters > 0:
                out.at[index, column] = milliliters
        if "unit" in out.columns:
            out.at[index, "unit"] = "mL"
        amount = (
            f"{format_number(milliliters, 3)} mL"
            if milliliters > 0
            else ""
        )
        for column in ("total amount", "Amount"):
            if column in out.columns:
                out.at[index, column] = amount
    return out


def protocol_order_table(gui, frame):
    """Return step materials in the accepted operator protocol order."""
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame() if frame is None else frame
    out = clean_operator_table(gui, frame).copy()

    def step_rank(value):
        text = str(value or "").strip().lower()
        if text == "resin":
            return -100000
        if text == "cleavage":
            return 100000
        try:
            return int(float(text)) * 100
        except Exception:
            return 90000

    def phase_rank(row):
        step = str(row.get("step", "")).strip().lower()
        phase = str(row.get("phase", "")).strip().lower()
        source = str(row.get("source", "")).strip().lower()
        material_class = str(row.get("class", "")).strip().lower()
        material = str(row.get("material", "")).strip().lower()
        if step == "resin":
            return 0
        if "swell" in phase:
            return 1
        if "loading" in phase and ("aa" in material_class or "unit" in source):
            return 10
        if "loading" in phase and ("base" in material_class or "aux" in source):
            return 11
        if "deprotection" in phase and "piperidine" in material:
            return 20
        if "deprotection" in phase:
            return 21
        if "dmf wash" in phase:
            return 30
        if "regular aa" in phase or "coupling" in phase:
            if "aa" in material_class or "unit" in source:
                return 40
            if "coupling reagent" in material_class:
                return 41
            if "catalyst" in material_class:
                return 42
            if "base" in material_class:
                return 43
            if "solvent" in material_class:
                return 44
            return 45
        if "synthesis" in phase or "reaction" in phase:
            return 46
        if "post" in phase:
            return 50
        if "final" in phase:
            return 60
        if "cleavage" in phase:
            return 1000
        return 100

    out["_sort"] = out.apply(
        lambda row: step_rank(row.get("step", "")) + phase_rank(row), axis=1
    )
    out["_order"] = range(len(out))
    return (
        out.sort_values(["_sort", "_order"], kind="mergesort")
        .drop(columns=["_sort", "_order"])
        .reset_index(drop=True)
    )


TOTAL_DISPLAY_COLUMNS = [
    "material", "class", "MW", "Density(g/mL)", "total mmol",
    "total amount", "unit", "note",
]


def total_display_table(gui, frame):
    """Build the accepted concise total-materials display table."""
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame(columns=TOTAL_DISPLAY_COLUMNS)
    rows = []
    for _, row in clean_operator_table(gui, frame, total=True).iterrows():
        material = str(row.get("material", "")).strip()
        if not material:
            continue
        material_class = row.get("class", "")
        liquid = is_liquid(
            material,
            material_class,
            row.get("physical_state", ""),
            row.get("unit", ""),
            row.get("reagent", ""),
        )
        milliliters = numeric(
            row.get("planned_mL", row.get("total_mL", "")), 0.0
        )
        grams = numeric(row.get("planned_g", row.get("total_g", "")), 0.0)
        if milliliters <= 0:
            milliliters = extract_ml_from_amount(row.get("total amount", ""))
        amount = (
            f"{format_number(milliliters, 3)} mL"
            if liquid and milliliters > 0
            else (f"{format_number(grams, 4)} g" if grams > 0 else "")
        )
        rows.append({
            "material": material,
            "class": material_class,
            "MW": row.get("MW", ""),
            "Density(g/mL)": row.get(
                "density_g_mL", row.get("Density(g/mL)", "")
            ),
            "total mmol": row.get(
                "planned_mmol", row.get("total mmol", "")
            ),
            "total amount": amount,
            "unit": "mL" if liquid else row.get("unit", ""),
            "note": (
                row.get("warning", "")
                or row.get("source", "")
                or row.get("note", "")
            ),
        })
    return pd.DataFrame(rows, columns=TOTAL_DISPLAY_COLUMNS)


__all__ = [
    "LIQUID_NAMES",
    "AA_REAGENT_NAMES",
    "base_material_name",
    "clean_operator_table",
    "extract_ml_from_amount",
    "format_number",
    "is_liquid",
    "numeric",
    "protocol_order_table",
    "total_display_table",
    "user_resin_label",
]
