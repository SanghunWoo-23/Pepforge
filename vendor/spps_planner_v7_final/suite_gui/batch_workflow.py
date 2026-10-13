"""Direct connected Batch Manager workflow for SPPS Planner V6.0.0."""
from __future__ import annotations
from suite_gui import runtime_state

from datetime import datetime
import json
import math
from pathlib import Path
from tkinter import messagebox
from typing import Any

import pandas as pd

from suite_gui.calculation_context import material_lookup
from suite_gui import catalogs
from suite_gui.material_presentation import AA_REAGENT_NAMES
from suite_gui.plan_input_factory import build_batch_plan_input, number, value
from suite_gui.resin_profiles import apply_batch_profile, item_loading_enabled, normalize_resin


BATCH_COLUMNS = [
    "Category", "Item", "Solvent", "Count", "Eq", "Conc_M",
    "Calculated_mL", "Actual_mL", "MW", "Density", "Weight_g",
    "Volume_mL", "Note",
]
SUMMARY_COLUMNS = [
    "No", "Project", "Peptide name", "LOT No", "Sequence", "Copies",
    "Scale mmol", "Resin", "Loading", "Resin_g", "Chemistry",
]
VERSION = "V7.0.0"


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
        has_residue_core = False
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
            parsed_core = list(parsed.core_tokens or [])
            if parsed_core:
                has_residue_core = True
            repeat = _repeat_count(row.get(repeat_key), 1)
            for _ in range(repeat):
                for token in parsed_core:
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
        # A Batch total represents a real peptide synthesis.  Terminal defaults
        # (for example C-term NH2 on an otherwise blank starter project) must
        # never manufacture a phantom sequence such as ``NH2``.
        if not has_residue_core:
            return ""

        prefix = []
        # Preserve the N-terminal modifier detected from the Project Manager
        # sequence even when Tag/Label fields are also configured.  The old
        # fallback only kept Ac when there were no other prefix units.
        explicit_nterm = str(row.get("N-term", "") or "").strip()
        nterm_value = explicit_nterm if explicit_nterm.lower() not in {"", "none", "manual", "-"} else detected_nterm
        if nterm_value:
            prefix.append(f"[{nterm_value}]")
        for key in ("Tag", "Label"):
            value_ = str(row.get(key, "") or "").strip()
            if value_ and value_.lower() not in {"none", "manual", "-"}:
                prefix.append(f"[{value_}]")
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
    """Restore only persisted Batch rows; never infer Batch rows from Projects.

    Batch Manager is an operator-owned workspace.  Project Manager entries can be
    copied into it explicitly with ``Sync from Project Manager``, but loading a
    project/session that has no saved Batch rows must leave the Batch table empty.
    This prevents an unrelated or previously selected Project sequence from
    appearing as if it were an operator-created Batch entry.
    """
    tree = getattr(gui, "batch_tree", None)
    columns = list(getattr(gui, "batch_columns", []) or [])
    if tree is None or not columns:
        return []
    rows = [dict(row) for row in (saved_rows or []) if isinstance(row, dict)]
    for row in rows:
        row["Linker"] = catalogs.canonical_unit_name(row.get("Linker", ""))
    children = list(tree.get_children())
    if children:
        tree.delete(*children)
    for row in rows:
        tree.insert("", "end", values=[row.get(column, "") for column in columns])
    invalidate(gui)
    return rows


def _saved_batch_rows(gui: Any) -> list[dict[str, Any]]:
    """Read only explicitly persisted Batch rows from the local session.

    Project Manager rows are intentionally ignored here.  A session may contain
    Project history without ever having contained a Batch workspace; in that
    case startup must remain empty.
    """
    source = getattr(gui, "state_file", None)
    if source is None:
        return []
    try:
        from suite_gui import state_persistence
        path = Path(source)
        if not path.exists():
            return []
        data, _loaded_source, _recovered = state_persistence.read_json_with_recovery(path)
        raw = data.get("batch_rows", []) if isinstance(data, dict) else []
        return [dict(row) for row in raw if isinstance(row, dict)]
    except Exception:
        return []


def initialize(gui: Any) -> dict[str, pd.DataFrame]:
    """Restore saved Batch rows only; otherwise keep startup completely empty."""
    if not _batch_input_rows(gui):
        restore_input_rows(gui, _saved_batch_rows(gui))
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

    # Legacy editable Batch tables remain operator-owned and require explicit
    # rows/sync.  The accepted compact desktop Batch dashboard, however, is a
    # live aggregate of the current Project Manager items and must therefore
    # calculate from ``pm_items`` automatically.  No sample/default sequence is
    # synthesized here: only records actually present in Project Manager are
    # eligible for aggregation.
    if getattr(gui, "batch_tree", None) is not None:
        return []

    # Compact desktop / headless compatibility: calculate directly from the
    # explicit Project Manager collection when there is no editable Batch table.
    rows = []
    for index, item in enumerate(list(getattr(gui, "pm_items", []) or []), 1):
        pm_row = {
            "N-term": item.get("n_term", ""),
            "Region 1 seq": item.get("sequence", ""),
            "Region 1 eq": item.get("region1_eq", "1") or "1",
            "Linker": item.get("linker", ""),
            "Region 2 seq": item.get("region2_seq", ""),
            "Region 2 eq": item.get("region2_eq", ""),
            "Tag": item.get("tag", ""),
            "Label": item.get("label", ""),
            "C-term": item.get("c_term", "NH2") or "NH2",
        }
        sequence = _batch_sequence(pm_row)
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
            "_batch_source": {
                "AA conc M": value(gui, "batch_solution_conc", "0.25"),
                "AA coupling eq": value(gui, "batch_coupling_eq", value(gui, "coupling_eq", "5")),
            },
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


def _grouped_material_category(item: Any, category: Any) -> str:
    """Map one prepared material to the four operator-facing groups.

    Display order is fixed by the lab workflow: L-AA, D-AA, Non-natural AA,
    then Chemical (including linkers, tags, labels and terminal caps).
    """
    item_text = str(item or "").strip()
    category_text = str(category or "").strip().lower()
    if item_text in set(getattr(catalogs, "FMOC_D_AA_VALUES", [])) or item_text.startswith("Fmoc-D-"):
        return "D-AA"
    if item_text in set(getattr(catalogs, "FMOC_NON_NATURAL_AA_VALUES", [])) or "non-natural aa" in category_text:
        return "Non-natural AA"
    l_aa_values = set(getattr(catalogs, "FMOC_AA_VALUES", []))
    l_aa_values.update(getattr(catalogs, "FMOC_PROTECTED_VARIANT_VALUES", []))
    l_aa_values.update(getattr(catalogs, "AC_AA_VALUES", []))
    if item_text in l_aa_values or category_text in {"aa", "aa stock", "protected amino acid", "ac-amino acid"}:
        return "L-AA"
    return "Chemical"


def grouped_aa_chemical_frame(aa_frame: pd.DataFrame, chemical_frame: pd.DataFrame) -> pd.DataFrame:
    """Combine AA and chemical tables in one deterministic operator order.

    Each group is alphabetized by the physical bottle/reagent name.  This is a
    presentation merge only; the underlying AA and Chemical calculation tables
    remain available separately for export and compatibility.
    """
    frames = []
    for source in (aa_frame, chemical_frame):
        if source is None or source.empty:
            continue
        frame = source.copy().reindex(columns=BATCH_COLUMNS)
        frame["Category"] = [
            _grouped_material_category(item, category)
            for item, category in zip(frame["Item"], frame["Category"])
        ]
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=BATCH_COLUMNS)
    merged = pd.concat(frames, ignore_index=True).reindex(columns=BATCH_COLUMNS)
    order = {"L-AA": 0, "D-AA": 1, "Non-natural AA": 2, "Chemical": 3}
    merged["_group_order"] = merged["Category"].map(order).fillna(99)
    merged["_alpha"] = merged["Item"].astype(str).str.casefold()
    merged = merged.sort_values(["_group_order", "_alpha"], kind="stable")
    return merged[BATCH_COLUMNS].reset_index(drop=True)


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


def _compact_sequence_prep_projects(gui: Any) -> list[dict[str, Any]]:
    """Return Project Manager sequences for the compact Batch preparation view.

    The compact desktop Batch Manager is intentionally *not* a second synthesis
    history/condition aggregator.  It reads the peptide sequence (plus copies for
    the number of synthesizer columns) from Project Manager, then recalculates all
    preparation amounts from the Batch ``Solution prep defaults``.  Project-level
    coupling chemistry, resin/loading and per-project reagent equivalents must not
    leak into this calculation.
    """
    scale = number(gui, "batch_default_scale", 0.2)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(list(getattr(gui, "pm_items", []) or []), 1):
        sequence = str(item.get("sequence", "") or "").strip()
        if not sequence:
            continue
        copies = max(1, _repeat_count(item.get("copies"), 1))
        rows.append({
            "No": index,
            "Project": item.get("project", ""),
            "Peptide name": item.get("peptide", ""),
            "LOT No": item.get("lot", item.get("lot_no", "")),
            "Sequence": sequence,
            "Copies": copies,
            "Scale mmol": scale,
            "Resin": "",
            "Loading": "",
            "Resin_g": "",
            "Chemistry": "Solution prep defaults",
        })
    return rows


def _calculate_compact_sequence_prep(gui: Any) -> dict[str, pd.DataFrame]:
    """Calculate the compact Batch Manager strictly from sequence + prep defaults.

    This is the operator-facing synthesizer preparation calculator.  It deliberately
    ignores Project Manager DIC/HOBt/HBTU selections and any project-specific reagent
    equivalents.  AA stock, HBTU stock and NMM base-stock quantities are controlled only by the visible
    ``Solution prep defaults`` fields.  Sequence-defined modifiers (Ac, linker, tag,
    label, non-natural residues) are still recognized from the sequence itself.
    """
    from spps_planner.engine import PlanInput, generate_step_reagent_plan

    projects = _compact_sequence_prep_projects(gui)
    aa_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    chemical_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    reagent_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    base_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    solvent_totals: dict[tuple[str, str], dict[str, Any]] = {}

    aa_concentration = number(gui, "batch_solution_conc", 0.25)
    aa_eq = number(gui, "batch_coupling_eq", 10.0)
    hbtu_eq = number(gui, "batch_hbtu_eq", 10.0)
    hbtu_concentration = number(gui, "batch_hbtu_conc", 0.4)
    nmm_eq = number(gui, "batch_nmm_eq", 5.0)
    nmm_concentration = number(gui, "batch_nmm_conc", 0.8)
    total_coupling_count = 0.0
    total_hbtu_mmol = 0.0
    total_nmm_mmol = 0.0

    for project in projects:
        sequence = str(project.get("Sequence", "") or "").strip()
        copies = max(1, _repeat_count(project.get("Copies"), 1))
        scale_each = _float(project.get("Scale mmol"), number(gui, "batch_default_scale", 0.2))

        # ``AC`` is a legitimate Ala-Cys dipeptide, while the parser also accepts
        # ``Ac`` as the acetyl terminal alias.  Preserve the operator's uppercase
        # two-residue sequence unambiguously for preparation counting.
        parser_sequence = "A-C" if sequence == "AC" else sequence

        # Generate only a parser/protected-reagent view of the sequence.  The PlanInput
        # chemistry defaults are not used for Batch coupling-reagent totals below.
        plan = PlanInput(sequence=parser_sequence, scale_mmol=scale_each)
        step_plan = generate_step_reagent_plan(plan)
        aa_counts = _sequence_counts(parser_sequence, step_plan)
        local_residue_count = sum(aa_counts.values())
        total_coupling_count += local_residue_count * copies
        total_hbtu_mmol += local_residue_count * copies * scale_each * hbtu_eq
        total_nmm_mmol += local_residue_count * copies * scale_each * nmm_eq

        for amino_acid, local_count in aa_counts.items():
            count = local_count * copies
            _add_record(
                aa_records, "AA stock", amino_acid, "DMF", count, aa_eq,
                aa_concentration, count * scale_each * aa_eq,
                "Sequence count × prep scale × AA eq; actual mL is rounded up + reserve",
            )

        # Sequence-defined chemicals/modifiers are still useful in the prep view, but
        # they are derived from the sequence only.  No Project Manager chemistry fields
        # participate here.
        for unit in _unit_records(plan, step_plan):
            eq = _float(unit.get("eq"), 0.0)
            repeat = max(1, _repeat_count(unit.get("repeat"), 1))
            if eq <= 0:
                continue
            _add_record(
                chemical_records, unit.get("category", "Chemical"),
                unit.get("item"), unit.get("solvent", ""), copies * repeat,
                eq, "", copies * scale_each * eq * repeat,
                unit.get("note") or "Detected from sequence; verify reagent form/vendor when required",
            )

    stock_solvent = str(value(gui, "default_coupling_solution_solvent", "DMF") or "DMF")
    if total_coupling_count > 0 and hbtu_eq > 0:
        _add_record(
            reagent_records, "Coupling reagent stock", "HBTU", stock_solvent,
            total_coupling_count, hbtu_eq, hbtu_concentration, total_hbtu_mmol,
            "Batch default HBTU stock; independent of Project Manager coupling chemistry",
        )
        if hbtu_concentration > 0:
            calculated_stock_solvent = total_hbtu_mmol / hbtu_concentration
            solvent_totals[("HBTU stock solvent", stock_solvent)] = {
                "mL": calculated_stock_solvent,
                "count": total_coupling_count,
                "note": "Configured solvent volume for HBTU stock; actual mL uses Batch round-up + reserve",
            }
    if total_coupling_count > 0 and nmm_eq > 0:
        _add_record(
            base_records, "Coupling base stock", "NMM", stock_solvent,
            total_coupling_count, nmm_eq, nmm_concentration, total_nmm_mmol,
            "N-Methylmorpholine (NMM) base stock; calculated independently from HBTU",
        )

    aa_frame = _records_frame(gui, aa_records)
    chemical_frame = _records_frame(gui, chemical_records)
    return {
        "AA + Chemicals": grouped_aa_chemical_frame(aa_frame, chemical_frame),
        "AA stock": aa_frame,
        "Resin loading": pd.DataFrame(columns=BATCH_COLUMNS),
        "Coupling reagents": _records_frame(gui, reagent_records),
        "Catalyst/additive": pd.DataFrame(columns=BATCH_COLUMNS),
        "Base/Deprotection": _records_frame(gui, base_records),
        "Solvents": _direct_volume_frame(gui, solvent_totals),
        "Chemicals": chemical_frame,
        "Summary": pd.DataFrame(projects, columns=SUMMARY_COLUMNS),
    }



def calculate_compact(gui: Any) -> dict[str, pd.DataFrame]:
    """Public V7 entry point for sequence-driven preparation totals.

    The compact path always uses Project Manager sequences/copies plus visible
    Solution prep defaults and never re-aggregates project-specific chemistry.
    """
    return _calculate_compact_sequence_prep(gui)

def calculate(gui: Any) -> dict[str, pd.DataFrame]:
    """Calculate Batch tables.

    Compact desktop Batch Manager = Project Manager sequence + Solution prep defaults.
    Legacy editable Batch tables keep their explicit row-driven connected-plan behavior.
    """
    if getattr(gui, "batch_tree", None) is None:
        return _calculate_compact_sequence_prep(gui)

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

    aa_frame = _records_frame(gui, aa_records)
    chemical_frame = _records_frame(gui, chemical_records)
    return {
        "AA + Chemicals": grouped_aa_chemical_frame(aa_frame, chemical_frame),
        "AA stock": aa_frame,
        "Resin loading": _loading_frame(gui, projects, prepared_plans),
        "Coupling reagents": _records_frame(gui, reagent_records),
        "Catalyst/additive": _records_frame(gui, catalyst_records),
        "Base/Deprotection": base_frame,
        "Solvents": _direct_volume_frame(gui, solvent_totals),
        "Chemicals": chemical_frame,
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


def _format_tree_value(value_: Any, column: str) -> str:
    """Keep the operator dashboard readable while exports retain raw precision."""
    if value_ is None:
        return ""
    text = str(value_).strip()
    if text.lower() in {"", "nan", "none", "<na>"}:
        return ""
    try:
        number_ = float(text)
        if not math.isfinite(number_):
            return ""
    except Exception:
        return text
    col = str(column or "")
    if col in {"Count", "count", "Copies", "copies", "No", "no"}:
        return str(int(round(number_))) if abs(number_ - round(number_)) < 1e-9 else f"{number_:.2f}"
    if col in {"Conc_M", "conc_M", "Density", "density"}:
        return f"{number_:.3f}".rstrip("0").rstrip(".")
    if col in {"Eq", "eq"}:
        return f"{number_:.2f}".rstrip("0").rstrip(".")
    if col in {"Calculated_mL", "Actual_mL", "Volume_mL", "calculated", "actual", "volume_mL", "MW", "Weight_g", "weight_g", "Scale mmol", "scale_mmol"}:
        return f"{number_:.2f}".rstrip("0").rstrip(".")
    return f"{number_:.3f}".rstrip("0").rstrip(".")


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
            _format_tree_value(_display_value(row.to_dict(), column), column)
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
    "batch_default_scale", "batch_solution_conc", "batch_coupling_eq",
    "batch_hbtu_eq", "batch_hbtu_conc", "batch_nmm_eq", "batch_nmm_conc",
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
            "project", "peptide", "sequence", "copies", "lot", "lot_no",
        )
        inputs = tuple(
            tuple(str(item.get(field, "") or "") for field in project_fields)
            for item in (getattr(gui, "pm_items", []) or [])
        )
    settings = tuple(str(value(gui, name, "") or "") for name in _SIGNATURE_SETTINGS)
    return columns, inputs, settings


def invalidate(gui: Any) -> None:
    runtime_state.set_batch_signature(gui,None)


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
    return runtime_state.get_batch_tables(gui)


def request_refresh(gui: Any, *, delay_ms: int = 80, force: bool = False):
    """Coalesce rapid UI edits into one Batch calculation."""
    try:
        pending = runtime_state.get_batch_refresh_after_id(gui)
        if pending:
            gui.after_cancel(pending)

        def run():
            runtime_state.set_batch_refresh_after_id(gui,None)
            refresh(gui, force=force)

        runtime_state.set_batch_refresh_after_id(gui,gui.after(max(0, int(delay_ms)), run))
        return runtime_state.get_batch_tables(gui)
    except Exception:
        return refresh(gui, force=True) if force else refresh(gui)


def refresh(gui: Any, *, force: bool = False) -> dict[str, pd.DataFrame]:
    try:
        signature = _calculation_signature(gui)
        cached = runtime_state.get_batch_tables(gui)
        if (
            not force
            and isinstance(cached, dict)
            and runtime_state.get_batch_signature(gui) == signature
        ):
            tables = cached
        else:
            tables = calculate(gui)
            runtime_state.set_batch_signature(gui,signature)
        for name, tree in (getattr(gui, "v29_batch_trees", {}) or {}).items():
            _write_tree(tree, tables.get(name, pd.DataFrame()))
        aa_tree = getattr(gui, "batch_aa_tree", None)
        modifier_tree = getattr(gui, "batch_modifier_tree", None)
        if aa_tree is not None and aa_tree is modifier_tree:
            # Compact V5 dashboard: one visible material list.  Do not paint the
            # Chemical table a second time over the AA rows.
            _write_tree(aa_tree, tables.get("AA + Chemicals", pd.DataFrame()))
        else:
            _write_tree(aa_tree, tables.get("AA stock", pd.DataFrame()))
            _write_tree(modifier_tree, tables.get("Chemicals", pd.DataFrame()))
        named = {
            "batch_coupling_reagent_tree": "Coupling reagents",
            "batch_catalyst_tree": "Catalyst/additive",
            "batch_base_tree": "Base/Deprotection",
            "batch_solvent_tree": "Solvents",
            "batch_project_tree": "Summary",
        }
        for attribute, name in named.items():
            _write_tree(getattr(gui, attribute, None), tables.get(name, pd.DataFrame()))
        layout = getattr(gui, "batch_layout_text", None)
        layout_builder = getattr(gui, "_batch_layout_text", None)
        if layout is not None and callable(layout_builder):
            text = layout_builder(_batch_input_rows(gui))
            if runtime_state.get_batch_layout_signature(gui) != text:
                layout.delete("1.0", "end")
                layout.insert("end", text)
                runtime_state.set_batch_layout_signature(gui,text)
        runtime_state.set_batch_tables(gui,tables)
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
            "calculation_source": "suite_gui.batch_workflow.calculate",
            "project_count": len(_compact_sequence_prep_projects(gui)) if getattr(gui, "batch_tree", None) is None else len(_project_rows(gui)),
            "conditions": {
                "prep_scale_mmol": number(gui, "batch_default_scale", 0.2),
                "aa_conc_M": number(gui, "batch_solution_conc", 0.25),
                "aa_eq": number(gui, "batch_coupling_eq", 5.0),
                "hbtu_eq": number(gui, "batch_hbtu_eq", 10.0),
                "hbtu_conc_M": number(gui, "batch_hbtu_conc", 0.4),
                "nmm_eq": number(gui, "batch_nmm_eq", 5.0),
                "nmm_conc_M": number(gui, "batch_nmm_conc", 0.8),
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
    "BATCH_COLUMNS", "calculate", "calculate_compact", "export", "initialize", "invalidate",
    "invalidate_and_refresh_if_visible", "is_visible", "refresh",
    "request_refresh", "restore_input_rows",
    "sync_input_from_projects", "grouped_aa_chemical_frame",
]
