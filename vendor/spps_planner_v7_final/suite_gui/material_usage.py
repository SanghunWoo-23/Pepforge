"""V5 material-usage importer and cleavage-volume evidence helpers.

This module parses the operator raw-material workbooks without guessing missing units.
Explicit units are normalized to mL. A numeric value without a unit is preserved as raw
source data and marked ``needs_unit_review`` so it cannot silently become ML truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping


_VOLUME_FACTORS_TO_ML = {
    "ml": 1.0,
    "milliliter": 1.0,
    "milliliters": 1.0,
    "l": 1000.0,
    "liter": 1000.0,
    "liters": 1000.0,
    "ul": 0.001,
    "µl": 0.001,
    "μl": 0.001,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def clean_material_product(value: Any) -> str:
    """Remove workbook/client presentation prefixes but preserve the product identity."""
    text = _text(value)
    if "&" in text:
        text = text.split("&")[-1].strip()
    text = re.sub(r"^\s*\d+\s*[.)]\s*", "", text)
    return text.strip()


def clean_material_sequence(value: Any) -> str:
    text = _text(value).replace("–", "-").replace("—", "-")
    # Workbook notation observed in the supplied material-usage files.
    text = re.sub(r"^Acetic\s+acid\s*-", "Ac-", text, flags=re.I)
    text = re.sub(r"\(D\)\s*([A-Za-z])", lambda m: "d" + m.group(1).upper(), text, flags=re.I)
    text = re.sub(r"\(L\)\s*([A-Za-z])", lambda m: m.group(1).upper(), text, flags=re.I)
    return text.strip()


def parse_scale_mmol(values: list[Any]) -> float | None:
    for value in values:
        text = _text(value)
        match = re.search(r"scale\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*mmol", text, flags=re.I)
        if match:
            return float(match.group(1))
    return None


def parse_amount(value: Any) -> dict[str, Any]:
    """Parse one raw reagent amount without guessing a missing unit."""
    raw = _text(value)
    if raw in {"", "-", "–", "—"}:
        return {
            "raw": raw,
            "value": 0.0 if raw else None,
            "unit": "",
            "normalized_ml": 0.0 if raw else None,
            "status": "explicit_zero" if raw else "missing",
        }
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = _num(value)
        return {"raw": raw, "value": number, "unit": "", "normalized_ml": None, "status": "needs_unit_review"}
    match = re.search(r"([-+]?[0-9]+(?:\.[0-9]+)?)\s*(mL|ml|L|l|uL|ul|µL|µl|μL|μl)\b", raw)
    if match:
        number = float(match.group(1))
        unit = match.group(2).lower().replace("μ", "µ")
        factor = _VOLUME_FACTORS_TO_ML.get(unit)
        return {
            "raw": raw,
            "value": number,
            "unit": match.group(2),
            "normalized_ml": number * factor if factor is not None else None,
            "status": "explicit_volume" if factor is not None else "unsupported_unit",
        }
    number_only = re.fullmatch(r"\s*([-+]?[0-9]+(?:\.[0-9]+)?)\s*", raw)
    if number_only:
        return {"raw": raw, "value": float(number_only.group(1)), "unit": "", "normalized_ml": None, "status": "needs_unit_review"}
    return {"raw": raw, "value": None, "unit": "", "normalized_ml": None, "status": "unparsed"}


def _first_nonempty_after(row: tuple[Any, ...] | list[Any], index: int) -> Any:
    for value in list(row)[index + 1:]:
        if value not in (None, ""):
            return value
    return None


def _find_reagent_row(rows: list[tuple[Any, ...]], patterns: tuple[str, ...]) -> tuple[int, Any] | None:
    for row_idx, row in enumerate(rows, 1):
        for col_idx, value in enumerate(row):
            label = _text(value).casefold()
            if not label:
                continue
            if any(pattern.casefold() in label for pattern in patterns):
                return row_idx, _first_nonempty_after(row, col_idx)
    return None


def extract_cleavage_usage_workbook(path: str | Path, *, source_file_label: str = "") -> list[dict[str, Any]]:
    """Extract one cleavage/workup usage observation from a material-usage workbook.

    The supplied workbook family has a top metadata block and a ``합성 정제 원재료``
    section. Only TFA, cleavage water, TIS and Ethyl Ether are read here. Other
    reagents are intentionally left untouched.
    """
    from openpyxl import load_workbook
    from suite_gui import experimental_data

    source = Path(path)
    wb = load_workbook(source, data_only=True, read_only=True)
    records: list[dict[str, Any]] = []
    try:
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(min_row=1, max_row=min(80, int(ws.max_row or 80)), values_only=True))
            if not rows:
                continue
            flat_top = [_text(value) for row in rows[:12] for value in row if value not in (None, "")]
            if not any("펩타이드 명칭" in value for value in flat_top) or not any("scale" in value.lower() for value in flat_top):
                continue
            product_raw = ""
            sequence_raw = ""
            manufacture_period = ""
            operator = ""
            for row in rows[:12]:
                values = list(row)
                for idx, value in enumerate(values):
                    label = _text(value)
                    if "펩타이드 명칭" in label:
                        product_raw = _text(_first_nonempty_after(values, idx))
                    elif label.startswith("서열") or "서열 :" in label:
                        sequence_raw = _text(_first_nonempty_after(values, idx))
                    elif "제조기간" in label:
                        manufacture_period = _text(_first_nonempty_after(values, idx))
                    elif "작업자" in label:
                        # Sometimes operator is in the same cell as the label.
                        same = re.search(r"작업자\s*:\s*(.+)$", label)
                        operator = same.group(1).strip() if same else _text(_first_nonempty_after(values, idx))
            scale = parse_scale_mmol(flat_top)
            product = clean_material_product(product_raw)
            sequence = clean_material_sequence(sequence_raw)
            if not product or scale is None:
                continue

            reagent_specs = {
                "tfa": ("tfa(triflouroacetic acid)", "tfa(trifluoroacetic acid)", "tfa(트리", "tfa("),
                "water": ("h2o (cleavage)", "h2o(cleavage)", "water (cleavage)", "dw (cleavage)"),
                "tis": ("tis", "triisopropylsilane"),
                "ether": ("ethyl ether", "diethyl ether"),
                "hexane": ("n-hexane", "n hexane"),
            }
            parsed: dict[str, dict[str, Any]] = {}
            locators: dict[str, str] = {}
            for key, patterns in reagent_specs.items():
                found = _find_reagent_row(rows, patterns)
                if found is None:
                    parsed[key] = parse_amount(None)
                    locators[key] = ""
                else:
                    row_idx, raw_value = found
                    parsed[key] = parse_amount(raw_value)
                    locators[key] = f"{ws.title}!row{row_idx}"

            cocktail_values = [parsed[key]["normalized_ml"] for key in ("tfa", "water", "tis")]
            cocktail_complete = all(value is not None for value in cocktail_values)
            cocktail_total = sum(float(value) for value in cocktail_values) if cocktail_complete else None
            composition: dict[str, float] = {}
            if cocktail_total is not None and cocktail_total > 0:
                for key, name in (("tfa", "TFA"), ("water", "Water"), ("tis", "TIS")):
                    value = float(parsed[key]["normalized_ml"] or 0.0)
                    if value > 0:
                        composition[name] = value / cocktail_total * 100.0
            source_name = str(source_file_label or source.name)
            aggregate_flag = int(any(token in source_name for token in ("통합본", "총합본", ",")) or "," in product)
            product_key = experimental_data.canonical_product_key(product)
            sequence_key = experimental_data.canonical_sequence_key(sequence)
            period_key = re.sub(r"\s+", "", manufacture_period.casefold())
            synthesis_key = "|".join([product_key, sequence_key, period_key, f"{scale:g}"])
            review_required = int(any(parsed[key]["status"] in {"needs_unit_review", "unparsed", "unsupported_unit"} for key in parsed))
            has_positive_usage = any((parsed[key].get("value") or 0) > 0 for key in parsed)
            records.append({
                "status": "parsed" if has_positive_usage else "incomplete",
                "product_raw": product_raw,
                "product": product,
                "product_key": product_key,
                "sequence_raw": sequence_raw,
                "sequence": sequence,
                "sequence_key": sequence_key,
                "scale_mmol": scale,
                "operator": operator,
                "manufacture_period": manufacture_period,
                "synthesis_key": synthesis_key,
                "record_scope": "aggregate" if aggregate_flag else "single",
                "tfa_raw": parsed["tfa"]["raw"], "tfa_value": parsed["tfa"]["value"], "tfa_unit": parsed["tfa"]["unit"], "tfa_ml": parsed["tfa"]["normalized_ml"], "tfa_status": parsed["tfa"]["status"],
                "water_raw": parsed["water"]["raw"], "water_value": parsed["water"]["value"], "water_unit": parsed["water"]["unit"], "water_ml": parsed["water"]["normalized_ml"], "water_status": parsed["water"]["status"],
                "tis_raw": parsed["tis"]["raw"], "tis_value": parsed["tis"]["value"], "tis_unit": parsed["tis"]["unit"], "tis_ml": parsed["tis"]["normalized_ml"], "tis_status": parsed["tis"]["status"],
                "ether_raw": parsed["ether"]["raw"], "ether_value": parsed["ether"]["value"], "ether_unit": parsed["ether"]["unit"], "ether_ml": parsed["ether"]["normalized_ml"], "ether_status": parsed["ether"]["status"],
                "hexane_raw": parsed["hexane"]["raw"], "hexane_value": parsed["hexane"]["value"], "hexane_unit": parsed["hexane"]["unit"], "hexane_ml": parsed["hexane"]["normalized_ml"], "hexane_status": parsed["hexane"]["status"],
                "cocktail_total_ml": cocktail_total,
                "cocktail_ml_per_mmol": (cocktail_total / scale if cocktail_total is not None and scale > 0 else None),
                "ether_ml_per_mmol": (float(parsed["ether"]["normalized_ml"]) / scale if parsed["ether"]["normalized_ml"] is not None and scale > 0 else None),
                "hexane_ml_per_mmol": (float(parsed["hexane"]["normalized_ml"]) / scale if parsed["hexane"]["normalized_ml"] is not None and scale > 0 else None),
                "composition_pct_json": json.dumps(composition, ensure_ascii=False, sort_keys=True),
                "unit_review_required": review_required,
                "source_file": source_name,
                "source_page": ws.title,
                "source_locator": "; ".join(f"{key}={loc}" for key, loc in locators.items() if loc),
                "raw_note": "Material-usage workbook cleavage/workup amounts; unitless numeric values are not normalized until reviewed.",
            })
    finally:
        wb.close()
    return records


def apply_unit_review(row: Mapping[str, Any], updates: Mapping[str, str]) -> dict[str, Any]:
    """Return normalized unit-review changes for one DB row.

    ``updates`` keys are tfa/water/tis/ether and values are mL/L/uL. Raw values are
    preserved. Only fields explicitly requested by the operator are changed.
    """
    changes: dict[str, Any] = {}
    for key in ("tfa", "water", "tis", "ether", "hexane"):
        unit = _text(updates.get(key))
        if not unit:
            continue
        unit_norm = unit.lower().replace("μ", "µ")
        if unit_norm not in _VOLUME_FACTORS_TO_ML:
            raise ValueError(f"Unsupported volume unit for {key}: {unit}")
        raw_value = _num(row.get(f"{key}_value"))
        if raw_value is None:
            raise ValueError(f"{key} has no numeric raw value to normalize.")
        changes[f"{key}_unit"] = unit
        changes[f"{key}_ml"] = raw_value * _VOLUME_FACTORS_TO_ML[unit_norm]
        changes[f"{key}_status"] = "operator_verified_unit"
    merged = dict(row); merged.update(changes)
    cocktail = [merged.get("tfa_ml"), merged.get("water_ml"), merged.get("tis_ml")]
    if all(value is not None for value in cocktail):
        total = sum(float(value) for value in cocktail)
        changes["cocktail_total_ml"] = total
        scale = _num(merged.get("scale_mmol"))
        changes["cocktail_ml_per_mmol"] = total / scale if scale and scale > 0 else None
        composition = {}
        if total > 0:
            for key, name in (("tfa", "TFA"), ("water", "Water"), ("tis", "TIS")):
                value = float(merged.get(f"{key}_ml") or 0.0)
                if value > 0:
                    composition[name] = value / total * 100.0
        changes["composition_pct_json"] = json.dumps(composition, ensure_ascii=False, sort_keys=True)
    ether_ml = merged.get("ether_ml")
    scale = _num(merged.get("scale_mmol"))
    if ether_ml is not None and scale and scale > 0:
        changes["ether_ml_per_mmol"] = float(ether_ml) / scale
    hexane_ml = merged.get("hexane_ml")
    if hexane_ml is not None and scale and scale > 0:
        changes["hexane_ml_per_mmol"] = float(hexane_ml) / scale
    remaining = []
    for key in ("tfa", "water", "tis", "ether", "hexane"):
        status = str(changes.get(f"{key}_status", merged.get(f"{key}_status", "")))
        if status in {"needs_unit_review", "unparsed", "unsupported_unit"}:
            remaining.append(key)
    changes["unit_review_required"] = int(bool(remaining))
    return changes


__all__ = [
    "clean_material_product", "clean_material_sequence", "parse_amount",
    "extract_cleavage_usage_workbook", "apply_unit_review",
]
