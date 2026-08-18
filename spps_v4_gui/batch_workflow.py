"""Direct connected Batch Manager workflow for SPPS Planner V4.0.0."""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from tkinter import messagebox
from typing import Any

import pandas as pd

from spps_v4_gui.calculation_context import material_lookup
from spps_v4_gui import catalogs
from spps_v4_gui.material_presentation import AA_REAGENT_NAMES
from spps_v4_gui.plan_input_factory import build_batch_plan_input, number, value
from spps_v4_gui.resin_profiles import apply_batch_profile, item_loading_enabled, normalize_resin


BATCH_COLUMNS = [
    "Category", "Item", "Solvent", "Count", "Eq", "Conc_M",
    "Calculated_mL", "Actual_mL", "MW", "Density", "Weight_g",
    "Volume_mL", "Note",
]
SUMMARY_COLUMNS = [
    "No", "Project", "Peptide name", "LOT No", "Sequence", "Copies",
    "Scale mmol", "Resin", "Loading", "Resin_g", "Chemistry",
]
VERSION = "V4.0.0"


def _float(current: Any, default: float = 0.0) -> float:
    try:
        return float(str(current or "").replace(",", "").strip())
    except Exception:
        return float(default)


def _round_actual(gui: Any, calculated: float) -> float:
    if calculated <= 0:
        return 0.0
    step = max(number(gui, "batch_actual_round_ml", 10.0), 1.0)
    extra = max(number(gui, "batch_actual_extra_ml", 10.0), 0.0)
    return math.ceil(calculated / step) * step + extra


def _tree_rows(tree: Any, columns: list[str]) -> list[dict[str, Any]]:
    if tree is None:
        return []
    rows: list[dict[str, Any]] = []
    for item_id in tree.get_children():
        values = list(tree.item(item_id, "values"))
        values += [""] * max(0, len(columns) - len(values))
        row = dict(zip(columns, values))
        if str(row.get("Region 1 seq", "") or "").strip() or str(
            row.get("Peptide name", "") or ""
        ).strip():
            rows.append(row)
    return rows


def _repeat_count(value: Any, default: int = 1) -> int:
    return max(0, int(round(_float(value, default))))


def _batch_sequence(row: dict[str, Any]) -> str:
    """Build one parser-safe sequence from the complete Batch Manager row."""
    try:
        from spps_planner.parser import parse_sequence

        core_tokens: list[str] = []
        detected_nterm = ""
        detected_cterm = ""
        linker = catalogs.canonical_unit_name(row.get("Linker", ""))
        for region_index, (sequence_key, repeat_key) in enumerate((
            ("Region 1 seq", "Region 1 eq"),
            ("Region 2 seq", "Region 2 eq"),
        )):
            text = str(row.get(sequence_key, "") or "").strip()
            if not text:
                if (
                    region_index == 0
                    and linker
                    and linker.lower() not in {"none", "manual", "-"}
                ):
                    core_tokens.append(linker)
                continue
            parsed = parse_sequence(text)
            detected_nterm = detected_nterm or str(parsed.nterm or "")
            detected_cterm = str(parsed.cterm_text or "") or detected_cterm
            repeat = _repeat_count(row.get(repeat_key), 1)
            for _ in range(repeat):
                for token in parsed.core_tokens:
                    token = str(token or "").strip()
                    if not token:
                        continue
                    core_tokens.append(token)
            if (
                region_index == 0
                and linker
                and linker.lower() not in {"none", "manual", "-"}
            ):
                core_tokens.append(linker)
        prefix = []
        for key in ("N-term", "Tag", "Label"):
            value_ = str(row.get(key, "") or "").strip()
            if value_ and value_.lower() not in {"none", "manual", "-"}:
                prefix.append(f"[{value_}]")
        if not prefix and detected_nterm:
            prefix.append(f"[{detected_nterm}]")
        cterm = str(row.get("C-term", "") or "").strip() or detected_cterm
        # Keep adjacent natural residues compact.  A dashed ``A-C-...`` can be
        # mistaken for the historical ``Ac-`` N-terminal alias; ``AC...`` is
        # unambiguous and preserves every amino acid.
        rendered_core: list[str] = []
        natural_buffer: list[str] = []

        def flush_natural() -> None:
            if natural_buffer:
                rendered_core.append("".join(natural_buffer))
                natural_buffer.clear()

        for token in core_tokens:
            if len(token) == 1 and token in AA_REAGENT_NAMES:
                natural_buffer.append(token)
            else:
                flush_natural()
                rendered_core.append(
                    token if len(token) == 2 and token.startswith("d")
                    else f"[{token}]"
                )
        flush_natural()
        parts = prefix + rendered_core
        if cterm and cterm.lower() not in {"none", "manual", "-"}:
            parts.append(cterm)
        return "-".join(parts)
    except Exception:
        return str(row.get("Region 1 seq", row.get("Sequence", "")) or "").strip()


def _batch_input_rows(gui: Any) -> list[dict[str, Any]]:
    columns = list(getattr(gui, "batch_columns", []) or [])
    if columns:
        rows = _tree_rows(getattr(gui, "batch_tree", None), columns)
        if rows:
            return rows
    return []


def sync_input_from_projects(gui: Any, *, replace: bool = True) -> list[dict[str, Any]]:
    """Populate the editable Batch Manager table from current Project items."""
    tree = getattr(gui, "batch_tree", None)
    columns = list(getattr(gui, "batch_columns", []) or [])
    if tree is None or not columns:
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(list(getattr(gui, "pm_items", []) or []), 1):
        sequence = str(item.get("sequence", "") or "").strip()
        if not sequence and not str(item.get("peptide", "") or "").strip():
            continue
        rows.append({
            "No": index,
            "Project": item.get("project", ""),
            "Peptide name": item.get("peptide", ""),
            "Form": item.get("form", "linear") or "linear",
            "Copies": item.get("copies", "1") or "1",
            "N-term": item.get("n_term", ""),
            "Region 1 seq": sequence,
            "Region 1 eq": item.get("region1_eq", "1") or "1",
            "Linker": catalogs.canonical_unit_name(item.get("linker", "")),
            "Region 2 seq": item.get("region2_seq", ""),
            "Region 2 eq": item.get("region2_eq", ""),
            "Tag": item.get("tag", ""),
            "Label": item.get("label", ""),
            "C-term": item.get("c_term", "NH2") or "NH2",
            "Chemistry": item.get("chemistry", "DIC/HOBt") or "DIC/HOBt",
            "Scale mmol": item.get("scale", value(gui, "batch_default_scale", "0.2")),
            "AA conc M": value(gui, "batch_solution_conc", "0.25"),
            "AA coupling eq": value(gui, "batch_coupling_eq", "5"),
            "Resin": item.get("resin", value(gui, "batch_default_resin", "Rink Amide AM")),
            "Loading": item.get("loading", value(gui, "batch_default_loading", "0.8")),
            "LOT No": item.get("lot", item.get("lot_no", "")),
            "Status": item.get("status", "Ready") or "Ready",
        })
    if replace:
        children = list(tree.get_children())
        if children:
            tree.delete(*children)
    for row in rows:
        tree.insert("", "end", values=[row.get(column, "") for column in columns])
    invalidate(gui)
    return rows


def restore_input_rows(gui: Any, saved_rows: Any = None) -> list[dict[str, Any]]:
    """Restore a persisted Batch table in one paint, or derive it from Projects."""
    tree = getattr(gui, "batch_tree", None)
    columns = list(getattr(gui, "batch_columns", []) or [])
    if tree is None or not columns:
        return []
    rows = [dict(row) for row in (saved_rows or []) if isinstance(row, dict)]
    for row in rows:
        row["Linker"] = catalogs.canonical_unit_name(row.get("Linker", ""))
    if not rows:
        return sync_input_from_projects(gui, replace=True)
    children = list(tree.get_children())
    if children:
        tree.delete(*children)
    for row in rows:
        tree.insert("", "end", values=[row.get(column, "") for column in columns])
    invalidate(gui)
    return rows


def initialize(gui: Any) -> dict[str, pd.DataFrame]:
    """Connect startup data without blocking launch on full Batch calculation."""
    if not _batch_input_rows(gui):
        sync_input_from_projects(gui, replace=True)
    invalidate(gui)
    return {}


def _project_rows(gui: Any) -> list[dict[str, Any]]:
    batch_rows = _batch_input_rows(gui)
    if batch_rows:
        rows = []
        for index, item in enumerate(batch_rows, 1):
            sequence = _batch_sequence(item)
            if not sequence:
                continue
            copies = max(1, _repeat_count(item.get("Copies"), 1))
            scale = _float(item.get("Scale mmol"), 0.2)
            loading = _float(item.get("Loading"), 0.0)
            resin = normalize_resin(item.get("Resin", "Rink Amide AM"))
            rows.append({
                "No": index,
                "Project": item.get("Project", ""),
                "Peptide name": item.get("Peptide name", ""),
                "LOT No": item.get("LOT No", ""),
                "Sequence": sequence,
                "Copies": copies,
                "Scale mmol": scale,
                "Resin": resin,
                "Loading": loading if loading > 0 else "",
                "Resin_g": round(scale * copies / loading, 2) if loading > 0 else "",
                "Chemistry": item.get("Chemistry", "DIC/HOBt") or "DIC/HOBt",
                "_apply_loading_calc": item_loading_enabled(item, resin),
                "_loading_aa_eq": _float(item.get("loading_aa_eq"), 2.0),
                "_loading_diea_eq": _float(item.get("loading_diea_eq"), 4.0),
                "_batch_source": dict(item),
            })
        return rows

    rows = []
    for index, item in enumerate(list(getattr(gui, "pm_items", []) or []), 1):
        sequence = str(item.get("sequence", "") or "").strip()
        if not sequence:
            continue
        copies = max(1, int(round(_float(item.get("copies"), 1))))
        scale = _float(item.get("scale"), 0.2)
        loading = _float(item.get("loading"), 0.0)
        resin = normalize_resin(item.get("resin", "Rink Amide AM"))
        rows.append({
            "No": index,
            "Project": item.get("project", ""),
            "Peptide name": item.get("peptide", ""),
            "LOT No": item.get("lot", item.get("lot_no", "")),
            "Sequence": sequence,
            "Copies": copies,
            "Scale mmol": scale,
            "Resin": resin,
            "Loading": loading if loading > 0 else "",
            "Resin_g": round(scale * copies / loading, 2) if loading > 0 else "",
            "Chemistry": item.get("chemistry", "DIC/HOBt") or "DIC/HOBt",
            "_apply_loading_calc": item_loading_enabled(item, resin),
            "_loading_aa_eq": _float(item.get("loading_aa_eq"), 2.0),
            "_loading_diea_eq": _float(item.get("loading_diea_eq"), 4.0),
        })
    return rows


def _plan_input(gui: Any, row: dict[str, Any]):
    base = build_batch_plan_input(
        gui,
        row,
        bool(value(gui, "reagent_eq_follows_coupling_eq", True)),
    )
    return apply_batch_profile(row, base)


def _sequence_counts(sequence: str, step_plan: Any = None) -> dict[str, int]:
    """Return protected AA bottle names, never one-letter display tokens."""
    try:
        if step_plan is None:
            from spps_planner.engine import PlanInput, generate_step_reagent_plan
            step_plan = generate_step_reagent_plan(PlanInput(sequence=sequence))
        tokens = [
            str(row.get("protected_reagent", "") or row.get("unit", ""))
            for _, row in step_plan.iterrows()
            if str(row.get("reagent_class", "") or "").strip().upper()
            in {"AA", "D-AA"}
        ]
    except Exception:
        try:
            from spps_planner.parser import parse_sequence
            tokens = list(parse_sequence(sequence).core_tokens or [])
        except Exception:
            tokens = list(str(sequence or "").replace("-", ""))
    counts: dict[str, int] = {}
    for token in tokens:
        text = str(token or "").strip()
        text = AA_REAGENT_NAMES.get(text, text)
        if text:
            counts[text] = counts.get(text, 0) + 1
    return counts


def _unit_records(plan: Any, step_plan: Any = None) -> list[dict[str, Any]]:
    """Return recognized chemical/linker/tag/label units from the engine plan."""
    if step_plan is None:
        from spps_planner.engine import generate_step_reagent_plan
        step_plan = generate_step_reagent_plan(plan)

    output: list[dict[str, Any]] = []
    for _, step in step_plan.iterrows():
        unit_class = str(step.get("reagent_class", "") or "").strip()
        if unit_class.upper() in {"", "AA", "D-AA", "UNKNOWN"}:
            continue
        item = str(
            step.get("protected_reagent", "") or step.get("unit", "") or ""
        ).strip()
        unit = str(step.get("unit", "") or "").strip()
        # The Plan keeps the explanatory protected-form label.  The preparation
        # dashboard must use the physical bottle name so the reagent-library
        # density is found and Ac2O is calculated as a liquid, not an unknown
        # solid.
        if unit == "Ac":
            item = "Acetic anhydride"
        if not item or item.lower() == "fmoc removal":
            continue
        output.append({
            "category": unit_class,
            "item": item,
            "unit": unit,
            "eq": _float(step.get("reagent_eq"), 0.0),
            "repeat": max(1, _repeat_count(step.get("coupling_repeat"), 1)),
            "solvent": step.get("reaction_solvent", plan.default_reaction_solvent),
            "note": str(step.get("note", "") or "").strip(),
        })
    return output


def _add_record(
    records: dict[tuple[Any, ...], dict[str, Any]],
    category: str,
    item: Any,
    solvent: Any,
    count: float,
    eq: Any,
    concentration: Any,
    mmol: float,
    note: str,
) -> None:
    item = str(item or "").strip()
    if not item:
        return
    key = (category, item, str(solvent or ""), str(eq), str(concentration), note)
    record = records.setdefault(key, {
        "Category": category,
        "Item": item,
        "Solvent": str(solvent or ""),
        "Count": 0.0,
        "Eq": eq,
        "Conc_M": concentration,
        "mmol": 0.0,
        "Note": note,
    })
    record["Count"] += float(count or 0)
    record["mmol"] += float(mmol or 0)


def _records_frame(gui: Any, records: dict[tuple[Any, ...], dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records.values():
        item = record["Item"]
        mmol = float(record.get("mmol", 0) or 0)
        concentration = _float(record.get("Conc_M"), 0)
        mw, density = material_lookup(item)
        calculated = mmol / concentration if concentration else 0.0
        actual = _round_actual(gui, calculated) if calculated else 0.0
        grams = (
            actual / 1000.0 * concentration * mw
            if actual and concentration and mw
            else (mmol * mw / 1000.0 if mw else 0.0)
        )
        volume = grams / density if density and grams and not concentration else actual
        rows.append({
            **{key: record.get(key, "") for key in BATCH_COLUMNS},
            "Calculated_mL": calculated or "",
            "Actual_mL": actual or "",
            "MW": mw or "",
            "Density": density or "",
            "Weight_g": grams or "",
            "Volume_mL": volume or "",
        })
    return pd.DataFrame(rows, columns=BATCH_COLUMNS)


def _direct_volume_frame(gui: Any, totals: dict[tuple[str, str], dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for (category, item), record in totals.items():
        calculated = float(record.get("mL", 0) or 0)
        if calculated <= 0:
            continue
        actual = _round_actual(gui, calculated)
        mw, density = material_lookup(item)
        rows.append({
            "Category": category,
            "Item": item,
            "Solvent": item,
            "Count": record.get("count", 0),
            "Eq": "",
            "Conc_M": "",
            "Calculated_mL": calculated,
            "Actual_mL": actual,
            "MW": mw or "",
            "Density": density or "",
            "Weight_g": actual * density if density else "",
            "Volume_mL": actual,
            "Note": record.get("note", ""),
        })
    return pd.DataFrame(rows, columns=BATCH_COLUMNS)


def _loading_frame(
    gui: Any,
    rows: list[dict[str, Any]],
    prepared_plans: list[tuple[dict[str, Any], Any]] | None = None,
) -> pd.DataFrame:
    from spps_planner.engine import direct_loading_enabled, generate_step_materials

    output = []
    prepared = prepared_plans or [
        (project, _plan_input(gui, project)) for project in rows
    ]
    for project, plan in prepared:
        if not direct_loading_enabled(plan):
            continue
        materials = generate_step_materials(plan)
        keep = materials[
            materials.get("step", pd.Series(dtype=object)).astype(str).str.lower().eq("resin")
            | materials.get("phase", pd.Series(dtype=object)).astype(str).str.lower().eq("loading")
        ]
        for _, material in keep.iterrows():
            item = str(material.get("material", "") or "").strip()
            if not item:
                continue
            material_class = str(material.get("class", "") or "")
            mmol = _float(material.get("planned_mmol"), 0)
            grams = _float(material.get("planned_g"), 0)
            milliliters = _float(material.get("planned_mL"), 0)
            mw, density = material_lookup(item)
            output.append({
                "Category": "Resin loading",
                "Item": item,
                "Solvent": "" if material_class.lower() == "resin" else str(plan.loading_dissolve_solvent or ""),
                "Count": project["Copies"],
                "Eq": round(mmol / plan.scale_mmol, 2) if plan.scale_mmol else "",
                "Conc_M": "",
                "Calculated_mL": round(milliliters, 2) if milliliters else "",
                "Actual_mL": round(milliliters, 2) if milliliters else "",
                "MW": round(mw, 2) if mw else material.get("MW", ""),
                "Density": round(density, 2) if density else material.get("density_g_mL", ""),
                "Weight_g": round(grams, 2) if grams else "",
                "Volume_mL": round(milliliters, 2) if milliliters else "",
                "Note": material.get("note", "") or material.get("source", ""),
            })
    return pd.DataFrame(output, columns=BATCH_COLUMNS)


def calculate(gui: Any) -> dict[str, pd.DataFrame]:
    """Calculate every Batch table from Project items and the shared engine."""
    from spps_planner.engine import generate_detailed_operations, generate_step_reagent_plan, resin_family

    projects = _project_rows(gui)
    aa_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    reagent_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    catalyst_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    base_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    chemical_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    solvent_totals: dict[tuple[str, str], dict[str, Any]] = {}
    deprotection_totals: dict[tuple[str, str], dict[str, Any]] = {}
    hbtu_concentration = number(gui, "batch_hbtu_conc", 0.4)
    prepared_plans: list[tuple[dict[str, Any], Any]] = []

    def add_volume(
        totals: dict[tuple[str, str], dict[str, Any]],
        category: str,
        item: Any,
        milliliters: Any,
        note: str,
    ):
        item = str(item or "").strip()
        amount = _float(milliliters, 0)
        if not item or amount <= 0:
            return
        item = "DCM" if item.upper() == "MC/DCM" else item
        record = totals.setdefault(
            (category, item), {"mL": 0.0, "count": 0, "note": note},
        )
        record["mL"] += amount
        record["count"] += 1

    for project in projects:
        plan = _plan_input(gui, project)
        prepared_plans.append((project, plan))
        step_plan = generate_step_reagent_plan(plan)
        copies = int(project["Copies"])
        scale_each = float(project["Scale mmol"])
        total_scale = scale_each * copies
        source = dict(project.get("_batch_source", {}) or {})
        aa_concentration = _float(
            source.get("AA conc M"), number(gui, "batch_solution_conc", 0.25)
        )
        aa_eq = _float(
            source.get("AA coupling eq"),
            number(gui, "batch_coupling_eq", number(gui, "coupling_eq", 5.0)),
        )
        for amino_acid, local_count in _sequence_counts(
            plan.sequence, step_plan,
        ).items():
            count = local_count * copies
            _add_record(
                aa_records, "AA stock", amino_acid, "DMF", count, aa_eq,
                aa_concentration, count * scale_each * aa_eq,
                "AA stock final concentration; actual mL includes reserve",
            )

        for unit in _unit_records(plan, step_plan):
            eq = unit["eq"]
            repeat = unit["repeat"]
            if eq <= 0:
                continue
            _add_record(
                chemical_records,
                unit["category"],
                unit["item"],
                unit["solvent"],
                copies * repeat,
                eq,
                "",
                total_scale * eq * repeat,
                unit["note"] or (
                    f"Recognized {unit['category'].lower()} unit "
                    f"({unit['unit']}); verify vendor form when required"
                ),
            )

        for _, step in step_plan.iterrows():
            repeat = max(0, int(_float(step.get("coupling_repeat"), 0)))
            if repeat <= 0:
                continue
            skip_loading = (
                str(step.get("phase", "")) == "Loading"
                and resin_family(plan.resin) == "CTC/Trityl"
            )
            if not skip_loading:
                for category, bucket, name, eq, count in (
                    ("Coupling reagent", reagent_records, step.get("coupling_reagent"), step.get("coupling_reagent_eq"), step.get("coupling_reagent_count")),
                    ("Catalyst/additive", catalyst_records, step.get("catalyst"), step.get("catalyst_eq"), step.get("catalyst_count")),
                    ("Base", base_records, step.get("base"), step.get("base_eq"), step.get("base_count")),
                ):
                    name = str(name or "").strip()
                    protected = str(step.get("protected_reagent", "") or "").strip()
                    unit_class = str(step.get("reagent_class", "") or "").strip().upper()
                    if (
                        category == "Coupling reagent"
                        and unit_class in {"TAG", "LABEL", "CHEMICAL", "MODIFIER"}
                        and name == protected
                    ):
                        # Macro tags/labels are recognized in Chemicals; their
                        # display name is not a separate coupling reagent bottle.
                        continue
                    eq = _float(eq, 0)
                    count = max(0, int(_float(count, 0)))
                    if name and name.upper() not in {"N/A", "NONE"} and eq > 0 and count > 0:
                        _add_record(
                            bucket, category, name,
                            step.get("reaction_solvent", plan.default_reaction_solvent),
                            count * repeat, eq,
                            hbtu_concentration if name.upper() == "HBTU" else "",
                            total_scale * eq * count * repeat,
                            f"{category} total from connected plan; count/use={count}; reaction repeat={repeat}",
                        )

        for _, operation in generate_detailed_operations(plan).iterrows():
            add_volume(solvent_totals, "Solvent/operation", operation.get("solvent1_name"), operation.get("solvent1_mL"), "Operation solvent 1 total from selected resin/volume mode.")
            add_volume(deprotection_totals, "Deprotection base", operation.get("deprotection_base_name"), operation.get("deprotection_base_mL"), f"Deprotection condition: {plan.deprotection_ratio}.")
            add_volume(solvent_totals, "Solvent/operation", operation.get("solvent2_name"), operation.get("solvent2_mL"), "Operation solvent 2 total from selected resin/volume mode.")

    base_parts = [
        frame for frame in (
            _records_frame(gui, base_records),
            _direct_volume_frame(gui, deprotection_totals),
        ) if not frame.empty
    ]
    base_frame = (
        pd.concat(base_parts, ignore_index=True).reindex(columns=BATCH_COLUMNS)
        if base_parts else pd.DataFrame(columns=BATCH_COLUMNS)
    )

    return {
        "AA stock": _records_frame(gui, aa_records),
        "Resin loading": _loading_frame(gui, projects, prepared_plans),
        "Coupling reagents": _records_frame(gui, reagent_records),
        "Catalyst/additive": _records_frame(gui, catalyst_records),
        "Base/Deprotection": base_frame,
        "Solvents": _direct_volume_frame(gui, solvent_totals),
        "Chemicals": _records_frame(gui, chemical_records),
        "Summary": pd.DataFrame(projects, columns=SUMMARY_COLUMNS),
    }


def _display_value(record: dict[str, Any], column: str) -> Any:
    """Translate canonical Batch data to the accepted Classic dashboard."""
    direct = {
        "AA": "Item", "count": "Count", "eq": "Eq", "conc_M": "Conc_M",
        "calc_mL": "Calculated_mL", "calculated_mL": "Calculated_mL",
        "actual_mL": "Actual_mL", "MW": "MW",
        "weight_g": "Weight_g", "note": "Note", "item": "Item",
        "purpose": "Category", "solvent": "Solvent", "density": "Density",
        "volume_mL": "Volume_mL",
        "no": "No", "project": "Project", "peptide_name": "Peptide name",
        "lot_no": "LOT No", "copies": "Copies", "sequence": "Sequence",
        "scale_mmol": "Scale mmol", "resin": "Resin",
        "loading_mmol_g": "Loading", "chemistry": "Chemistry",
    }
    if column in direct:
        return record.get(direct[column], "")
    if column == "output_folder":
        return record.get("Output folder", "")
    if column in {"calculated", "actual", "unit"}:
        calculated_ml = _float(record.get("Calculated_mL"), 0)
        actual_ml = _float(record.get("Actual_mL"), 0)
        volume_ml = _float(record.get("Volume_mL"), 0)
        weight_g = _float(record.get("Weight_g"), 0)
        density = _float(record.get("Density"), 0)
        is_volume = bool(calculated_ml or actual_ml or volume_ml or density)
        if column == "unit":
            return "mL" if is_volume else ("g" if weight_g else "")
        if is_volume:
            if column == "calculated":
                return calculated_ml or volume_ml or ""
            return actual_ml or volume_ml or ""
        return weight_g or ""
    return record.get(column, "")


def _write_tree(tree: Any, frame: pd.DataFrame) -> None:
    if tree is None:
        return
    columns = list(tree.cget("columns") or []) or list(frame.columns)
    schema = tuple(columns)
    if getattr(tree, "_spps_batch_schema", None) != schema:
        tree.configure(columns=columns, show="headings")
        for column in columns:
            tree.heading(column, text=column)
            tree.column(
                column, width=280 if column == "Note" else 120,
                minwidth=55, anchor="w",
            )
        tree._spps_batch_schema = schema
    row_values = tuple(
        tuple(
            str(_display_value(row.to_dict(), column) or "")
            for column in columns
        )
        for _, row in frame.iterrows()
    )
    paint_signature = (schema, row_values)
    if getattr(tree, "_spps_batch_paint_signature", None) == paint_signature:
        return
    children = list(tree.get_children())
    if children:
        tree.delete(*children)
    for values_ in row_values:
        tree.insert("", "end", values=values_)
    tree._spps_batch_paint_signature = paint_signature


_SIGNATURE_SETTINGS = (
    "batch_solution_conc", "batch_coupling_eq", "batch_hbtu_conc",
    "batch_actual_round_ml", "batch_actual_extra_ml",
    "reagent_eq_follows_coupling_eq", "coupling_eq",
    "solvent_volume_mode", "amide_ml_per_mmol", "ctc_ml_per_mmol",
    "solvent_molarity_m",
)


def _calculation_signature(gui: Any) -> tuple[Any, ...]:
    columns = tuple(getattr(gui, "batch_columns", []) or [])
    batch_rows = _batch_input_rows(gui)
    if batch_rows:
        inputs = tuple(
            tuple(str(row.get(column, "") or "") for column in columns)
            for row in batch_rows
        )
    else:
        project_fields = (
            "project", "peptide", "sequence", "copies", "scale", "resin",
            "loading", "lot", "lot_no", "chemistry", "apply_loading_calc",
            "loading_aa_eq", "loading_diea_eq", "n_term", "linker",
            "region2_seq", "region2_eq", "tag", "label", "c_term",
        )
        inputs = tuple(
            tuple(str(item.get(field, "") or "") for field in project_fields)
            for item in (getattr(gui, "pm_items", []) or [])
        )
    settings = tuple(str(value(gui, name, "") or "") for name in _SIGNATURE_SETTINGS)
    return columns, inputs, settings


def invalidate(gui: Any) -> None:
    gui._v3_batch_signature = None


def is_visible(gui: Any) -> bool:
    """Return whether the top-level Batch Manager tab is currently selected."""
    tabs = getattr(gui, "tabs", None)
    if tabs is None:
        return False
    try:
        selected = tabs.select()
        return str(tabs.tab(selected, "text")) == "Batch Manager"
    except Exception:
        return False


def invalidate_and_refresh_if_visible(
    gui: Any, *, delay_ms: int = 80, force: bool = False,
):
    """Invalidate totals immediately and recalculate only while Batch is open."""
    invalidate(gui)
    if is_visible(gui):
        return request_refresh(gui, delay_ms=delay_ms, force=force)
    return getattr(gui, "_v225_batch_tables", {})


def request_refresh(gui: Any, *, delay_ms: int = 80, force: bool = False):
    """Coalesce rapid UI edits into one Batch calculation."""
    try:
        pending = getattr(gui, "__dict__", {}).get(
            "_v3_batch_refresh_after_id",
        )
        if pending:
            gui.after_cancel(pending)

        def run():
            gui._v3_batch_refresh_after_id = None
            refresh(gui, force=force)

        gui._v3_batch_refresh_after_id = gui.after(max(0, int(delay_ms)), run)
        return getattr(gui, "__dict__", {}).get("_v225_batch_tables", {})
    except Exception:
        return refresh(gui, force=True) if force else refresh(gui)


def refresh(gui: Any, *, force: bool = False) -> dict[str, pd.DataFrame]:
    try:
        signature = _calculation_signature(gui)
        cached = getattr(gui, "_v225_batch_tables", None)
        if (
            not force
            and isinstance(cached, dict)
            and getattr(gui, "_v3_batch_signature", None) == signature
        ):
            tables = cached
        else:
            tables = calculate(gui)
            gui._v3_batch_signature = signature
        for name, tree in (getattr(gui, "v29_batch_trees", {}) or {}).items():
            _write_tree(tree, tables.get(name, pd.DataFrame()))
        named = {
            "batch_aa_tree": "AA stock",
            "batch_coupling_reagent_tree": "Coupling reagents",
            "batch_catalyst_tree": "Catalyst/additive",
            "batch_base_tree": "Base/Deprotection",
            "batch_solvent_tree": "Solvents",
            "batch_modifier_tree": "Chemicals",
            "batch_project_tree": "Summary",
        }
        for attribute, name in named.items():
            _write_tree(getattr(gui, attribute, None), tables.get(name, pd.DataFrame()))
        layout = getattr(gui, "batch_layout_text", None)
        layout_builder = getattr(gui, "_batch_layout_text", None)
        if layout is not None and callable(layout_builder):
            text = layout_builder(_batch_input_rows(gui))
            if getattr(gui, "_v3_batch_layout_signature", None) != text:
                layout.delete("1.0", "end")
                layout.insert("end", text)
                gui._v3_batch_layout_signature = text
        gui._v225_batch_tables = tables
        return tables
    except Exception as exc:
        try:
            gui._log(f"Batch refresh warning: {exc}\n")
        except Exception:
            pass
        return {}


def _output_directory(gui: Any) -> Path:
    text = value(gui, "batch_outdir", "")
    if not str(text or "").strip():
        text = Path(str(value(gui, "outdir", "spps_output"))) / "batch_manager"
    return Path(str(text)).expanduser()


def export(
    gui: Any,
    output_dir: str | Path | None = None,
    notify: bool = True,
) -> Path | None:
    try:
        output = Path(output_dir) if output_dir is not None else _output_directory(gui)
        output.mkdir(parents=True, exist_ok=True)
        tables = calculate(gui)
        xlsx = output / "batch_manager_tables.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            for name, frame in tables.items():
                frame.to_excel(writer, index=False, sheet_name=str(name)[:31])
        state = {
            "app_version": VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "calculation_source": "spps_v4_gui.batch_workflow.calculate",
            "project_count": len(_project_rows(gui)),
            "conditions": {
                "aa_conc_M": number(gui, "batch_solution_conc", 0.25),
                "aa_eq": number(gui, "batch_coupling_eq", 5.0),
                "hbtu_eq": number(gui, "batch_hbtu_eq", 10.0),
                "hbtu_conc_M": number(gui, "batch_hbtu_conc", 0.4),
                "solvent_volume_mode": value(gui, "solvent_volume_mode", "resin_factor"),
                "amide_mL_per_mmol": number(gui, "amide_ml_per_mmol", 10.0),
                "ctc_mL_per_mmol": number(gui, "ctc_ml_per_mmol", 5.0),
            },
        }
        (output / "batch_manager_export_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        gui.last_batch_outdir = output
        if notify:
            try:
                messagebox.showinfo("Export complete", f"Batch Manager export saved:\n{xlsx}")
            except Exception:
                pass
        return xlsx
    except Exception as exc:
        try:
            messagebox.showerror("Batch export error", str(exc))
        except Exception:
            pass
        return None


__all__ = [
    "BATCH_COLUMNS", "calculate", "export", "initialize", "invalidate",
    "invalidate_and_refresh_if_visible", "is_visible", "refresh",
    "request_refresh", "restore_input_rows",
    "sync_input_from_projects",
]
