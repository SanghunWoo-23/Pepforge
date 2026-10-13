"""SPPS Planner V7 quick-workflow helpers.

The V7 quick layer is intentionally orchestration-only.  It edits the same
Project Manager / Batch Manager variables as the canonical application and
never implements a second chemistry engine.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping


PRESET_SCHEMA_VERSION = 1
PRESET_FIELDS: dict[str, str] = {
    "chemistry": "pm_chemistry",
    "aa_conc": "batch_solution_conc",
    "aa_eq": "batch_coupling_eq",
    "hbtu_conc": "batch_hbtu_conc",
    "hbtu_eq": "batch_hbtu_eq",
    "nmm_conc": "batch_nmm_conc",
    "nmm_eq": "batch_nmm_eq",
    "round_ml": "batch_actual_round_ml",
    "extra_ml": "batch_actual_extra_ml",
    "reagent": "default_reagent",
    "reagent_eq": "default_reagent_eq",
    "catalyst": "default_catalyst",
    "catalyst_eq": "default_catalyst_eq",
    "base": "default_base",
    "base_eq": "default_base_eq",
    "solvent": "default_coupling_solution_solvent",
    "coupling_repeats": "coupling_repeats",
}


def _get(var: Any, default: str = "") -> str:
    if var is None:
        return str(default)
    getter = getattr(var, "get", None)
    if callable(getter):
        try:
            return str(getter())
        except Exception:
            return str(default)
    try:
        return str(var)
    except Exception:
        return str(default)


def _set(gui: Any, attr: str, value: Any) -> None:
    try:
        getattr(gui, attr).set(value)
    except Exception:
        pass


def _num(var: Any, default: float = 0.0) -> float:
    try:
        return float(_get(var, str(default)).replace(",", "").strip())
    except Exception:
        return float(default)


def _sequence_tokens(sequence: str) -> list[str]:
    try:
        from spps_planner.parser import parse_sequence

        parsed = parse_sequence(sequence)
        return [str(token) for token in (parsed.core_tokens or [])]
    except Exception:
        return [c for c in sequence if c.isalpha() and c.isupper()]


def _sequence_length(sequence: str) -> int:
    return len(_sequence_tokens(sequence))


def current_project_payload(gui: Any) -> dict[str, Any]:
    """Return the Quick editor as one canonical Project Manager row.

    Keep project-specific recipe state with the work item so a custom method does
    not silently fall back to DIC/HOBt when Quick creates a new Project Manager
    row. Batch stock-preparation defaults intentionally remain global and are not
    copied here.
    """
    return {
        "project": _get(getattr(gui, "pm_project", ""), ""),
        "peptide": _get(getattr(gui, "pm_peptide", ""), ""),
        "sequence": _get(getattr(gui, "pm_sequence", ""), "").strip(),
        "copies": _get(getattr(gui, "pm_copies", ""), "1") or "1",
        "scale": _get(getattr(gui, "pm_scale", ""), "0.2") or "0.2",
        "scale_preset": _get(getattr(gui, "scale_preset", ""), "Custom / manual"),
        "resin": _get(getattr(gui, "pm_resin", ""), "Rink Amide AM"),
        "loading": _get(getattr(gui, "pm_loading", ""), "0.8") or "0.8",
        "lot": _get(getattr(gui, "pm_lot", ""), ""),
        "lot_no": _get(getattr(gui, "pm_lot", ""), ""),
        "chemistry": _get(getattr(gui, "pm_chemistry", ""), "DIC/HOBt"),
        "status": "Ready",
        "loading_aa_eq": _get(getattr(gui, "loading_aa_eq", ""), "2"),
        "loading_diea_eq": _get(getattr(gui, "loading_diea_eq", ""), "4"),
        "loading_time_h": _get(getattr(gui, "loading_time_h", ""), ""),
        "coupling_eq": _get(getattr(gui, "coupling_eq", ""), "5"),
        "coupling_time_h": _get(getattr(gui, "coupling_time_h", ""), "0.5"),
        "modifier_eq": _get(getattr(gui, "modifier_eq", ""), "3"),
        "coupling_repeats": _get(getattr(gui, "coupling_repeats", ""), "1"),
        "modifier_repeats": _get(getattr(gui, "modifier_repeats", ""), "1"),
        "default_reagent": _get(getattr(gui, "default_reagent", ""), "DIC"),
        "default_catalyst": _get(getattr(gui, "default_catalyst", ""), "HOBt"),
        "default_base": _get(getattr(gui, "default_base", ""), ""),
        "default_coupling_solution_solvent": _get(
            getattr(gui, "default_coupling_solution_solvent", ""), "DMF"
        ),
        "auto_short_peptide_eq": _get(getattr(gui, "auto_short_peptide_eq", ""), "True"),
        "short_peptide_coupling_eq": _get(getattr(gui, "short_peptide_coupling_eq", ""), "2"),
        "cleavage_eq_override": _get(getattr(gui, "cleavage_eq_override", ""), "0"),
        "cleavage_preset": _get(getattr(gui, "cleavage_preset", ""), "AUTO"),
        "cleavage_components_text": _get(getattr(gui, "cleavage_components_text", ""), ""),
        "cleavage_time_h": _get(getattr(gui, "cleavage_time_h", ""), ""),
        "post_cleavage_rescue": _get(getattr(gui, "post_cleavage_rescue", ""), "None"),
        "nh4i_eq": _get(getattr(gui, "nh4i_eq", ""), "2"),
        "nh4i_concentration_m": _get(getattr(gui, "nh4i_concentration_m", ""), "0.2"),
        "nh4i_time_h": _get(getattr(gui, "nh4i_time_h", ""), "1"),
    }


def ensure_active_project(gui: Any) -> int:
    """Ensure the Quick editor is backed by a real Project Manager row.

    Important: when Quick Synthesis is used before a project exists, preserve the
    values already typed into the Quick editor instead of replacing them with a
    blank/default starter row.
    """
    items = list(getattr(gui, "pm_items", []) or [])
    if not items:
        gui.pm_add_peptide(current_project_payload(gui))
        items = list(getattr(gui, "pm_items", []) or [])

    idx = gui.pm_current_index() if hasattr(gui, "pm_current_index") else None
    if idx is None:
        idx = 0
        try:
            gui.pm_list.selection_clear(0, "end")
            gui.pm_list.selection_set(idx)
            gui.pm_list.activate(idx)
        except Exception:
            pass
    try:
        gui.pm_live_sync_selected()
    except Exception:
        pass
    return int(idx)




def sync_active_project(gui: Any, create: bool = False) -> bool:
    """Synchronize Quick values into the active Project Manager row.

    Quick and Project Manager intentionally share the same editor variables, but
    this explicit bridge makes the connection deterministic for Batch/Prepare
    workflows.  No blank project is created unless ``create`` is requested.
    """
    items = list(getattr(gui, "pm_items", []) or [])
    sequence = _get(getattr(gui, "pm_sequence", ""), "").strip()
    try:
        active = gui.pm_current_index() if hasattr(gui, "pm_current_index") else None
    except Exception:
        active = None
    if active is None:
        if not create or not sequence or not hasattr(gui, "pm_add_peptide"):
            return False
        # The application may boot with one intentionally blank editor row.
        # Reuse that phantom row for the first Quick peptide instead of showing
        # an empty project plus a second real project.  Never reuse a real saved
        # row, even if no list selection is currently active.
        phantom_index = None
        if len(items) == 1:
            row = dict(items[0] or {})
            is_phantom = (
                not str(row.get("sequence") or "").strip()
                and not str(row.get("project") or "").strip()
                and not str(row.get("peptide") or "").strip()
                and not str(row.get("work_item_id") or "").strip()
            )
            if is_phantom:
                phantom_index = 0
        if phantom_index is not None:
            try:
                gui.pm_list.selection_clear(0, "end")
                gui.pm_list.selection_set(phantom_index)
                gui.pm_list.activate(phantom_index)
            except Exception:
                pass
        else:
            # Quick is starting a new work item.  Do not silently select/overwrite
            # an older saved project merely because nothing is selected.
            gui.pm_add_peptide(current_project_payload(gui))
    try:
        if hasattr(gui, "pm_live_sync_selected"):
            gui.pm_live_sync_selected()
    except Exception:
        pass
    try:
        from suite_gui import batch_workflow
        batch_workflow.invalidate_and_refresh_if_visible(gui)
    except Exception:
        pass
    try:
        gui.schedule_autosave()
    except Exception:
        pass
    return bool(list(getattr(gui, "pm_items", []) or []))

def preflight(gui: Any) -> dict[str, list[str]]:
    """Validate operator-editable Quick inputs without changing chemistry.

    Errors block Quick Generate. Warnings are advisory and remain visible in
    the summary so unusual but intentional expert-scale work is still allowed.
    """
    errors: list[str] = []
    warnings: list[str] = []

    sequence = _get(getattr(gui, "pm_sequence", ""), "").strip()
    if not sequence:
        errors.append("Peptide sequence is required")
    else:
        try:
            from spps_planner.parser import parse_sequence

            parsed = parse_sequence(sequence)
            if not list(parsed.core_tokens or []):
                errors.append("Sequence contains no recognized core residues")
            warnings.extend(str(x) for x in (parsed.warnings or []) if str(x).strip())
        except Exception as exc:
            errors.append(f"Sequence could not be parsed: {exc}")

    scale = _num(getattr(gui, "pm_scale", None), 0.0)
    if scale <= 0:
        errors.append("Scale must be greater than 0 mmol")
    elif scale > 10:
        warnings.append(f"Scale is {scale:g} mmol; verify the unit before generating")

    copies_raw = _get(getattr(gui, "pm_copies", None), "").strip()
    try:
        copies_f = float(copies_raw)
        if copies_f < 1 or not copies_f.is_integer():
            raise ValueError
    except Exception:
        errors.append("Copies must be a positive whole number")

    loading = _num(getattr(gui, "pm_loading", None), 0.0)
    if loading <= 0:
        errors.append("Resin loading must be greater than 0 mmol/g")

    def positive(attr: str, label: str) -> None:
        value = _num(getattr(gui, attr, None), 0.0)
        if value <= 0:
            errors.append(f"{label} must be greater than 0")

    def nonnegative(attr: str, label: str) -> None:
        value = _num(getattr(gui, attr, None), 0.0)
        if value < 0:
            errors.append(f"{label} cannot be negative")

    positive("batch_solution_conc", "AA stock concentration")
    positive("batch_coupling_eq", "AA coupling equivalents")
    nonnegative("batch_actual_round_ml", "Practical round volume")
    nonnegative("batch_actual_extra_ml", "Extra reserve volume")

    chemistry = _get(getattr(gui, "pm_chemistry", ""), "").upper()
    reagent = _get(getattr(gui, "default_reagent", ""), "").upper()
    if "HBTU" in chemistry or reagent == "HBTU":
        positive("batch_hbtu_conc", "HBTU stock concentration")
        positive("batch_hbtu_eq", "HBTU equivalents")
        positive("batch_nmm_conc", "NMM stock concentration")
        positive("batch_nmm_eq", "NMM equivalents")

    expert = bool(getattr(getattr(gui, "quick_expert_enabled", None), "get", lambda: False)())
    if expert:
        nonnegative("cleavage_eq_override", "Cleavage equivalent override")
        nonnegative("cleavage_time_h", "Cleavage time")

    return {"errors": errors, "warnings": warnings}

def generate(gui: Any) -> Any:
    check = preflight(gui)
    if check["errors"]:
        raise ValueError("Preflight failed:\n- " + "\n- ".join(check["errors"]))
    sync_active_project(gui, create=True)
    result = gui.pm_generate_selected()
    sync_active_project(gui, create=False)
    refresh_summary(gui)
    return result


def method_snapshot(gui: Any) -> dict[str, str]:
    """Capture only operator-editable method fields; no project/private data."""
    return {
        key: _get(getattr(gui, attr, ""), "")
        for key, attr in PRESET_FIELDS.items()
    }


def apply_method_snapshot(gui: Any, snapshot: Mapping[str, Any]) -> None:
    for key, attr in PRESET_FIELDS.items():
        if key in snapshot:
            _set(gui, attr, snapshot[key])
    try:
        gui.schedule_autosave()
    except Exception:
        pass
    refresh_summary(gui)


def capture_baseline(gui: Any) -> dict[str, str]:
    baseline = method_snapshot(gui)
    gui._quick_baseline = dict(baseline)
    return baseline


def reset_to_baseline(gui: Any) -> None:
    baseline = dict(getattr(gui, "_quick_baseline", {}) or {})
    if baseline:
        apply_method_snapshot(gui, baseline)


def default_preset_path() -> Path:
    override = os.environ.get("SPPS_PLANNER_USER_DIR", "").strip()
    if override:
        root = Path(override)
    else:
        try:
            from spps_planner.build_profile import FALLBACK_DOT_DIR
            folder = str(FALLBACK_DOT_DIR or ".spps_planner")
        except Exception:
            folder = ".spps_planner"
        root = Path.home() / folder
    return root / "v7_method_presets.json"


def load_presets(path: Path | None = None) -> dict[str, dict[str, str]]:
    source = Path(path or default_preset_path())
    if not source.exists():
        return {}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    raw = data.get("presets", data)
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for name, values in raw.items():
        clean_name = str(name or "").strip()
        if not clean_name or not isinstance(values, dict):
            continue
        result[clean_name] = {
            key: str(values[key]) for key in PRESET_FIELDS if key in values
        }
    return result


def _write_presets(presets: Mapping[str, Mapping[str, Any]], path: Path | None = None) -> Path:
    destination = Path(path or default_preset_path())
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": PRESET_SCHEMA_VERSION,
        "presets": {
            str(name): {key: str(value) for key, value in values.items() if key in PRESET_FIELDS}
            for name, values in sorted(presets.items())
        },
    }
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def save_preset(name: str, snapshot: Mapping[str, Any], path: Path | None = None) -> Path:
    clean = re.sub(r"\s+", " ", str(name or "").strip())
    if not clean:
        raise ValueError("Preset name is required.")
    presets = load_presets(path)
    presets[clean] = {key: str(snapshot[key]) for key in PRESET_FIELDS if key in snapshot}
    return _write_presets(presets, path)


def delete_preset(name: str, path: Path | None = None) -> bool:
    clean = str(name or "").strip()
    presets = load_presets(path)
    if clean not in presets:
        return False
    del presets[clean]
    _write_presets(presets, path)
    return True


def apply_named_preset(gui: Any, name: str, path: Path | None = None) -> bool:
    presets = load_presets(path)
    snapshot = presets.get(str(name or "").strip())
    if not snapshot:
        return False
    apply_method_snapshot(gui, snapshot)
    return True


def _expert_override_lines(gui: Any) -> list[str]:
    lines: list[str] = []
    enabled = bool(getattr(getattr(gui, "quick_expert_enabled", None), "get", lambda: False)())
    if not enabled:
        return lines
    eq = _num(getattr(gui, "cleavage_eq_override", None), 0.0)
    preset = _get(getattr(gui, "cleavage_preset", ""), "AUTO").strip() or "AUTO"
    time_h = _num(getattr(gui, "cleavage_time_h", None), 0.0)
    if eq > 0:
        lines.append(f"EXPERT: manual cleavage equivalent override active ({eq:g} eq)")
    if preset.upper() not in {"", "AUTO"}:
        lines.append(f"EXPERT: cleavage preset override = {preset}")
    if time_h > 0:
        lines.append(f"EXPERT: cleavage time = {time_h:g} h")
    if not lines:
        lines.append("Expert controls unlocked; no cleavage override is currently active")
    return lines


def summary(gui: Any) -> str:
    seq = _get(getattr(gui, "pm_sequence", ""), "").strip()
    if not seq:
        return (
            "Start here\n"
            "1) Paste or type the peptide sequence\n"
            "2) Pick HBTU + NMM, DIC + HOBt, or your custom method\n"
            "3) Press Make plan"
        )

    tokens = _sequence_tokens(seq)
    length = len(tokens)
    cys_count = sum(1 for token in tokens if token.upper() in {"C", "DC"})
    met_count = sum(1 for token in tokens if token.upper() in {"M", "DM"})
    scale = _get(getattr(gui, "pm_scale", ""), "")
    copies = _get(getattr(gui, "pm_copies", ""), "1")
    resin = _get(getattr(gui, "pm_resin", ""), "")
    chemistry = _get(getattr(gui, "pm_chemistry", ""), "")

    check = preflight(gui)
    if check["errors"]:
        status = "CHECK THESE ITEMS BEFORE CREATING THE PLAN"
    elif check["warnings"]:
        status = "READY — WITH A NOTE TO CHECK"
    else:
        status = "READY"

    lines = [
        status,
        f"Peptide: {seq}",
        f"Size: {length} amino acids",
        f"Amount: {scale} mmol × {copies} copy/copies",
        f"Resin: {resin}",
        f"Coupling: {chemistry}",
        "",
    ]

    if check["errors"]:
        lines.append("Please fix:")
        lines.extend(f"• {item}" for item in check["errors"])
        lines.append("")

    lines.append("Planner checks:")
    if cys_count:
        lines.append(f"• Cys detected ({cys_count}); the automatic 100 eq/Cys cleavage rule will be used")
    if met_count:
        lines.append(f"• Met detected ({met_count}); NH4I is not auto-added")
    if length >= 18:
        lines.append("• Long peptide detected; review repeat/doubling settings if your method needs them")
    if not cys_count and not met_count and length < 18:
        lines.append("• No special sequence warning detected")
    lines.extend(f"• Check: {item}" for item in check["warnings"])
    lines.extend(f"• {item}" for item in _expert_override_lines(gui))
    if not check["errors"]:
        lines.append("")
        lines.append("Next: Make the plan, then choose Prepare solutions / Check loading / Check cleavage.")

    return "\n".join(lines)

def method_display(gui: Any) -> str:
    """Return a short human-readable coupling-method label for the Quick page."""
    chemistry = _get(getattr(gui, "pm_chemistry", ""), "").strip()
    compact = chemistry.upper().replace(" ", "")
    if compact in {"HBTU/NMM", "HBTU+NMM", "HBTU/NMP"}:
        return "HBTU + NMM"
    if compact in {"DIC/HOBT", "DIC+HOBT"}:
        return "DIC + HOBt"

    reagent = _get(getattr(gui, "default_reagent", ""), "").strip()
    additive = _get(getattr(gui, "default_catalyst", ""), "").strip()
    base = _get(getattr(gui, "default_base", ""), "").strip()
    parts = [x for x in (reagent, additive, base) if x]
    if parts:
        return " + ".join(parts)
    return chemistry or "Custom method"


def simple_summary(gui: Any) -> str:
    """Beginner-facing result text. Detailed chemistry stays in :func:`summary`."""
    seq = _get(getattr(gui, "pm_sequence", ""), "").strip()
    if not seq:
        return "Paste the peptide sequence above to start."

    tokens = _sequence_tokens(seq)
    length = len(tokens)
    cys_count = sum(1 for token in tokens if token.upper() in {"C", "DC"})
    met_count = sum(1 for token in tokens if token.upper() in {"M", "DM"})
    check = preflight(gui)

    if check["errors"]:
        lines = ["⚠ Fix these before making the plan:"]
        lines.extend(f"• {item}" for item in check["errors"][:4])
        if len(check["errors"]) > 4:
            lines.append(f"• +{len(check['errors']) - 4} more item(s)")
    elif check["warnings"]:
        lines = ["✓ Ready, but check the note(s) below."]
    else:
        lines = ["✓ Ready to make the plan."]

    lines.extend([
        f"Peptide: {seq}  ({length} aa)",
        f"Method: {method_display(gui)}",
    ])

    notes: list[str] = []
    if cys_count:
        notes.append(f"Cys found: {cys_count} — the automatic Cys cleavage rule will be used")
    if met_count:
        notes.append(f"Met found: {met_count} — NH4I will not be added automatically")
    if length >= 18:
        notes.append("Long peptide — check repeat/doubling settings if needed")
    notes.extend(str(item) for item in check["warnings"][:3])

    if notes:
        lines.append("Things to check:")
        lines.extend(f"• {item}" for item in notes)
    elif not check["errors"]:
        lines.append("No special sequence warning was found.")

    return "\n".join(lines)


def comparison(gui: Any) -> str:
    seq = _get(getattr(gui, "pm_sequence", ""), "").strip()
    if not seq:
        return "Method comparison appears after a sequence is entered."
    length = max(_sequence_length(seq), 1)
    try:
        copies = max(1, int(round(_num(getattr(gui, "pm_copies", 1), 1))))
    except Exception:
        copies = 1
    scale = max(0.0, _num(getattr(gui, "pm_scale", 0), 0))
    steps = length * copies
    baseline = getattr(gui, "_quick_baseline", {}) or {}

    def volume(eq_name: str, conc_name: str, default_eq: float, default_conc: float) -> float:
        eq = _num(getattr(gui, eq_name, None), default_eq)
        conc = _num(getattr(gui, conc_name, None), default_conc)
        return steps * scale * eq / conc if conc > 0 else 0.0

    aa = volume("batch_coupling_eq", "batch_solution_conc", 10, 0.25)
    hbtu = volume("batch_hbtu_eq", "batch_hbtu_conc", 10, 0.4)
    nmm = volume("batch_nmm_eq", "batch_nmm_conc", 5, 0.8)

    def baseline_volume(eq_key: str, conc_key: str, default_eq: float, default_conc: float) -> float:
        try:
            eq = float(baseline.get(eq_key, default_eq))
            conc = float(baseline.get(conc_key, default_conc))
        except Exception:
            eq, conc = default_eq, default_conc
        return steps * scale * eq / conc if conc > 0 else 0.0

    baa = baseline_volume("aa_eq", "aa_conc", 10, 0.25)
    bh = baseline_volume("hbtu_eq", "hbtu_conc", 10, 0.4)
    bn = baseline_volume("nmm_eq", "nmm_conc", 5, 0.8)

    def line(name: str, before: float, current: float) -> str:
        delta = ((current - before) / before * 100.0) if before else 0.0
        return f"{name:<10} baseline {before:>8.2f} mL   current {current:>8.2f} mL   {delta:+6.1f}%"

    return "\n".join([
        line("AA stock", baa, aa),
        line("HBTU", bh, hbtu),
        line("NMM", bn, nmm),
    ])


def _amount_text(row: Mapping[str, Any]) -> str:
    actual_ml = _num(row.get("Actual_mL"), 0.0)
    calc_ml = _num(row.get("Calculated_mL"), 0.0)
    weight_g = _num(row.get("Weight_g"), 0.0)
    if actual_ml > 0:
        return f"{actual_ml:g} mL"
    if calc_ml > 0:
        return f"{calc_ml:g} mL calc"
    if weight_g > 0:
        return f"{weight_g:g} g"
    return "review"


def prepare_today_frames(gui: Any) -> dict[str, Any]:
    """Return compact sequence-driven prep tables, never project chemistry totals."""
    from suite_gui import batch_workflow

    try:
        sync_active_project(gui, create=bool(_get(getattr(gui, "pm_sequence", ""), "").strip()))
    except Exception:
        pass
    return batch_workflow.calculate_compact(gui)


def prepare_today_text(gui: Any) -> str:
    frames = prepare_today_frames(gui)
    summary_frame = frames.get("Summary")
    if summary_frame is None or summary_frame.empty:
        return "No real Project Manager sequence is available. Add a sequence first."

    lines = [
        "TODAY'S PREPARATION",
        "=" * 64,
        f"Projects: {len(summary_frame)}   Source: Project Manager sequences + Solution prep defaults",
        "",
    ]
    for title in ("AA stock", "Coupling reagents", "Base/Deprotection", "Chemicals"):
        frame = frames.get(title)
        if frame is None or frame.empty:
            continue
        lines.append(title.upper())
        for _, row in frame.iterrows():
            item = str(row.get("Item", "") or "").strip()
            if not item:
                continue
            conc = _num(row.get("Conc_M"), 0.0)
            eq = _num(row.get("Eq"), 0.0)
            detail = []
            if conc > 0:
                detail.append(f"{conc:g} M")
            if eq > 0:
                detail.append(f"{eq:g} eq")
            suffix = f" ({' / '.join(detail)})" if detail else ""
            lines.append(f"  {item:<28} {_amount_text(row):>12}{suffix}")
        lines.append("")
    lines.append("Preparation amounts include the configured Batch round-up/reserve rules where applicable.")
    return "\n".join(lines)


def export_prepare_today(gui: Any, directory: Path | str) -> list[Path]:
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    frames = prepare_today_frames(gui)
    created: list[Path] = []
    for title, frame in frames.items():
        if frame is None or frame.empty:
            continue
        safe = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_").upper()
        path = destination / f"PREP_{safe}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        created.append(path)
    summary_path = destination / "PREP_README.txt"
    summary_path.write_text(prepare_today_text(gui), encoding="utf-8")
    created.append(summary_path)
    return created


def refresh_summary(gui: Any) -> str:
    detailed = summary(gui)
    beginner = simple_summary(gui)
    widget = getattr(gui, "quick_summary_text", None)
    if widget is not None:
        try:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", beginner)
            widget.configure(state="disabled")
        except Exception:
            pass
    refresh_comparison(gui)
    return detailed


def refresh_comparison(gui: Any) -> str:
    text = comparison(gui)
    widget = getattr(gui, "quick_compare_text", None)
    if widget is not None:
        try:
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state="disabled")
        except Exception:
            pass
    return text


__all__ = [
    "PRESET_FIELDS", "apply_method_snapshot", "apply_named_preset",
    "capture_baseline", "comparison", "current_project_payload", "delete_preset",
    "ensure_active_project", "export_prepare_today", "generate", "load_presets",
    "method_display", "method_snapshot", "preflight", "prepare_today_frames", "prepare_today_text",
    "refresh_comparison", "refresh_summary", "reset_to_baseline", "save_preset",
    "simple_summary", "summary", "sync_active_project",
]
