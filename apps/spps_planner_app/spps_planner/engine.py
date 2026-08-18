from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from typing import Any
import csv
import io
import re
import pandas as pd
from .parser import parse_sequence
from .database import load_compounds, load_rules, compound_lookup, load_reagent_library, reagent_lookup
from .literature_guidance import generate_literature_guidance

AA_TOKENS = set("ARNDCQEGHILKMFPSTWYV")

@dataclass
class Step:
    step: int
    synthesis_direction: str
    sequence_position_from_cterm: int
    sequence_position_from_nterm: int
    unit: str
    phase: str
    chemistry: str
    depro_x: int
    dmf_wash_x: int
    reaction_x: int
    post_dmf_wash_x: int
    dcm_wash_x: int
    rxn_dmf_frac: float
    rxn_dcm_frac: float
    dmf_mL: float
    piperidine_mL: float
    dcm_mL: float
    note: str
    protected_reagent: str = ""
    reagent_class: str = ""
    reagent_mw: float = 0.0
    product_mw_contribution: float = 0.0
    coupling_reagent: str = "DIC"
    catalyst: str = "HOBt"
    additive: str = ""
    base: str = ""
    reaction_solvent: str = "DMF"
    reagent_eq: float = 1.0
    reagent_eq_source: str = "global_default"
    coupling_repeat: int = 1
    coupling_repeat_source: str = "global_default"
    total_reagent_eq: float = 1.0
    planned_reagent_mmol: float = 0.0
    planned_reagent_g: float = 0.0
    planned_reagent_mg: float = 0.0
    resin_g: float = 0.0
    override_source: str = "default"
    ml_feature_source: str = "planned"
    coupling_reagent_eq: float = 0.0
    coupling_reagent_count: int = 0
    catalyst_eq: float = 0.0
    catalyst_count: int = 0
    base_eq: float = 0.0
    base_count: int = 0
    deprotection_base_name: str = "Piperidine"
    wash_solvent1_name: str = "DMF"
    wash_solvent2_name: str = "DCM"

@dataclass
class PlanInput:
    sequence: str = ""
    resin: str = "Amide"
    scale_mmol: float = 400.0
    resin_loading_mmol_g: float = 0.8
    coupling_eq: float = 5.0
    ac_eq: float = 3.0
    default_coupling_repeats: int = 1
    default_modifier_repeats: int = 1
    default_coupling_reagent: str = "DIC"
    default_catalyst: str = "HOBt"
    default_base: str = ""
    default_reaction_solvent: str = "DMF"
    # Fully connected setup conditions (restored from the classic UI).
    default_reagent_eq: float = 5.0
    default_reagent_count: int = 1
    default_catalyst_eq: float = 5.0
    default_catalyst_count: int = 1
    default_base_eq: float = 0.0
    default_base_count: int = 0
    # When enabled, coupling reagent/catalyst/base eq follows the resolved AA eq
    # (including the confirmed 1-5 mer = 2 eq rule). The Classic UI exposes
    # this as “Tie Reagent/Catalyst/Base to AA range”.
    reagent_eq_follows_coupling_eq: bool = True
    deprotection_base: str = "Piperidine"
    deprotection_ratio: str = "20% in DMF"
    deprotection_count: int = 2
    wash_solvent1: str = "DMF"
    wash_solvent1_count: int = 6
    wash_solvent2: str = "DCM"
    wash_solvent2_count: int = 3
    final_meoh_count: int = 0
    loading_dissolve_solvent: str = "90% DCM / 10% DMF"
    solvent_volume_mode: str = "resin_factor"
    amide_ml_per_mmol: float = 10.0
    ctc_ml_per_mmol: float = 5.0
    solvent_molarity_m: float = 0.2
    tfa_factor: float = 10.0
    cleavage_tfa_percent: float = 95.0
    cleavage_tis_percent: float = 2.5
    cleavage_water_percent: float = 2.5
    cleavage_eq_override: float = 0.0
    cleavage_preset: str = "AUTO"
    cleavage_components_text: str = ""
    cleavage_reserve_mL: float = 0.0
    step_overrides_text: str = ""
    loading_aa_eq: float = 2.0
    loading_diea_eq: float = 4.0
    loading_time_h: float = 0.0
    cleavage_time_h: float = 0.0
    auto_short_peptide_eq: bool = True
    short_peptide_max_len: int = 5
    short_peptide_coupling_eq: float = 2.0
    # Direct-loading calculation is independently controlled by the established
    # Classic-UI checkbox.  CTC(합성기) is always treated as preloaded.
    apply_resin_loading: bool = True


def resin_profile(resin: str) -> str:
    """Return the operational resin profile without collapsing user labels.

    ``2-CTC`` is a direct-loading resin. ``CTC(합성기)`` (and the deleted
    saved alias ``CTC(합성용)``) means a preloaded CTC resin used on the
    synthesizer, so the C-terminal residue and loading DIEA are not prepared
    again.  Both remain in the CTC/Trityl family for C-terminal output and
    cleavage-volume rules.
    """
    raw = str(resin or "").strip()
    key = re.sub(r"[^0-9a-z가-힣]+", "", raw.lower())
    # Operator classification: CTC(합성용) is a preloaded item prepared
    # outside the calculator and follows the Amide-resin calculation profile.
    if "합성용" in raw:
        return "AMIDE_PRELOADED"
    if "합성기" in raw or any(token in key for token in ("preloaded", "synthesizer")):
        return "CTC_PRELOADED"
    if "2ctc" in key or key in {"ctctrityl", "tritylchlorideresin", "2chlorotritylchlorideresin"} or "chlorotrityl" in key:
        return "CTC_DIRECT"
    return "AMIDE"


def resin_family(resin: str) -> str:
    return "CTC/Trityl" if resin_profile(resin).startswith("CTC_") else "Amide"


def is_direct_loading_resin(resin: str) -> bool:
    return resin_profile(resin) == "CTC_DIRECT"


def is_preloaded_ctc_resin(resin: str) -> bool:
    return resin_profile(resin) == "CTC_PRELOADED"


def direct_loading_enabled(inp: "PlanInput") -> bool:
    return is_direct_loading_resin(getattr(inp, "resin", "")) and bool(getattr(inp, "apply_resin_loading", True))


def operation_volume_mL(resin: str, scale_mmol: float) -> float:
    """Legacy default working volume retained for API compatibility.

    The connected GUI/engine path uses :func:`working_volume_mL`, which honors
    the editable Amide/CTC factors or molarity-basis volume.
    """
    return float(scale_mmol or 0.0) * (5.0 if is_direct_loading_resin(resin) else 10.0)


def working_volume_mL(inp: "PlanInput", *, unit_mmol: float | None = None, unit_eq: float | None = None, repeat: int = 1) -> float:
    """Return one-use working volume from the actual selected UI condition.

    resin_factor mode: scale x editable resin-family mL/mmol factor.
    molarity mode: planned reagent mmol / selected molarity (mmol/M == mL).
    """
    mode = str(getattr(inp, "solvent_volume_mode", "resin_factor") or "resin_factor").strip().lower()
    if mode == "molarity":
        molarity = max(float(getattr(inp, "solvent_molarity_m", 0.2) or 0.2), 1e-12)
        if unit_mmol is None:
            eq = float(unit_eq if unit_eq is not None else getattr(inp, "coupling_eq", 1.0) or 1.0)
            unit_mmol = float(getattr(inp, "scale_mmol", 0.0) or 0.0) * eq * max(1, int(repeat or 1))
        return max(0.0, float(unit_mmol or 0.0) / molarity)
    factor = float(getattr(inp, "ctc_ml_per_mmol", 5.0) or 0.0) if direct_loading_enabled(inp) else float(getattr(inp, "amide_ml_per_mmol", 10.0) or 0.0)
    return max(0.0, float(getattr(inp, "scale_mmol", 0.0) or 0.0) * factor)


def deprotection_fractions(inp: "PlanInput", rules: dict | None = None) -> tuple[float, float]:
    """Parse the editable deprotection ratio and return (solvent, base) fractions."""
    text = str(getattr(inp, "deprotection_ratio", "20% in DMF") or "20% in DMF")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", text)
    if match:
        base_frac = max(0.0, min(1.0, float(match.group(1)) / 100.0))
    else:
        rules = rules or {}
        base_frac = float(rules.get("depro_piperidine_ratio", 0.2) or 0.2)
    return 1.0 - base_frac, base_frac


def cterm_output(resin: str) -> str:
    return "COOH / OH" if resin_family(resin) == "CTC/Trityl" else "CONH2 / NH2"


def _resolve_coupling_eq(inp: PlanInput, token_count: int) -> tuple[float, str]:
    """Apply confirmed SPPS rule: 1-5 mer uses 2 eq, >5 mer uses default coupling_eq.

    Manual step overrides still win later in _make_step.
    """
    try:
        max_len = int(getattr(inp, "short_peptide_max_len", 5) or 5)
        short_eq = float(getattr(inp, "short_peptide_coupling_eq", 2.0) or 2.0)
        if bool(getattr(inp, "auto_short_peptide_eq", True)) and int(token_count or 0) <= max_len:
            return short_eq, f"length_rule_1_{max_len}_mer"
    except Exception:
        pass
    return float(inp.coupling_eq), "global_aa"


def _cterm_resin_warnings(parsed, resin: str) -> list[str]:
    marker = str(getattr(parsed, "cterm_text", "") or "").strip().upper()
    if not marker:
        return []
    fam = resin_family(resin)
    if marker in {"NH2", "CONH2", "AMIDE"} and fam != "Amide":
        return [f"C-terminal marker -{marker} conflicts with {resin} resin; {fam} resin gives COOH/OH output."]
    if marker in {"OH", "COOH", "CO2H", "ACID"} and fam == "Amide":
        return [f"C-terminal marker -{marker} conflicts with {resin} resin; Amide/Rink resin gives CONH2/NH2 output."]
    return []


def _normalize_coupling_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    """Keep coupling chemistry internally consistent.

    DIC/DCC/EDC/CDI/Ghosez do not force DIEA. Uronium/phosphonium and
    related modern couplers generally require an amine base, so the planner
    auto-adds DIEA only when the user left base blank.
    """
    d = dict(defaults or {})
    reagent = str(d.get("coupling_reagent", "") or "").upper().replace("-", "")
    catalyst = str(d.get("catalyst", "") or "")
    base = str(d.get("base", "") or "")
    base_required = {
        "HBTU", "HATU", "HCTU", "TBTU", "TSTU", "TNTU",
        "PYBOP", "PYBROP", "PYBRO", "PYBR", "PYCLOCK", "BOP", "COMU",
    }
    requires_base = any(key in reagent for key in base_required)
    if requires_base:
        if not base.strip():
            d["base"] = "DIEA"
            d["note"] = (str(d.get("note", "") or "") + " | Auto-added DIEA for base-required uronium/phosphonium/COMU-style coupling.").strip(" |")
        if catalyst.strip().upper() in {"HOBT", "HOAT"}:
            d["catalyst"] = ""
            d["note"] = (str(d.get("note", "") or "") + " | Cleared HOBt/HOAt catalyst for base-required coupling preset unless manually overridden.").strip(" |")
    return d


def _clear_non_reaction_reagents(defaults: dict[str, Any]) -> dict[str, Any]:
    """Display-only cleanup for rows with no coupling/reaction step.

    Final free N-terminal Fmoc removal and branch-handle prep are operation
    rows.  They should not show HBTU/DIEA/DIC in the operator-facing columns
    because no reagent coupling is calculated for those rows.
    """
    d = dict(defaults or {})
    d.update({
        "coupling_reagent": "N/A",
        "catalyst": "N/A",
        "additive": "",
        "base": "N/A",
        "reaction_solvent": "DMF",
        "reagent_eq": 0.0,
        "reagent_eq_source": "no_reagent_operation",
        "coupling_repeat": 0,
        "coupling_repeat_source": "no_reaction",
    })
    # Do not carry HBTU/DIEA auto-normalization notes into a non-reaction row.
    # The row is final Fmoc removal/wash only, so reagent/base notes are noise.
    d.pop("note", None)
    return d


def _format_coupling_system(reagent: str, catalyst: str = "", base: str = "") -> str:
    parts = [str(x or "").strip() for x in (reagent, catalyst, base)]
    parts = [p for p in parts if p and p.upper() != "N/A"]
    return " / ".join(parts) if parts else "N/A"


def _normalized_default_coupling_system(inp: PlanInput) -> str:
    d = _normalize_coupling_defaults({
        "coupling_reagent": inp.default_coupling_reagent or "DIC",
        "catalyst": inp.default_catalyst or "",
        "base": inp.default_base or "",
    })
    return _format_coupling_system(d.get("coupling_reagent", ""), d.get("catalyst", ""), d.get("base", ""))

def _row_for(token: str, lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if token in lookup:
        return lookup[token]
    if token.upper() in lookup:
        return lookup[token.upper()]
    if token.lower() in lookup:
        return lookup[token.lower()]
    return {}


def _profile_for(token: str, lookup: dict[str, dict[str, Any]]) -> str:
    row = _row_for(token, lookup)
    return str(row.get("Chemistry profile") or row.get("Class") or "Selected")


def _class_for(token: str, lookup: dict[str, dict[str, Any]]) -> str:
    return str(_row_for(token, lookup).get("Class") or "").strip()


def _float_row(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key)
        if v is None or str(v).strip() == "" or str(v).lower() == "nan":
            return default
        return float(v)
    except Exception:
        return default


def _canon_key(k: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (k or "").strip().lower()).strip("_")


def _split_kv_line(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    parts = re.split(r"\s*(?:;|/|\||,)\s*", line.strip())
    for part in parts:
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        elif ":" in part:
            k, v = part.split(":", 1)
        else:
            continue
        out[_canon_key(k)] = v.strip()
    return out


def _parse_repeat(v: Any) -> int | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    words = {"single": 1, "once": 1, "double": 2, "triple": 3, "quad": 4, "quadruple": 4}
    if s in words:
        return words[s]
    try:
        return max(1, int(float(s)))
    except Exception:
        return None


def parse_step_overrides(text: str | None) -> list[dict[str, Any]]:
    """Parse full manual step/reagent overrides.

    Selectors:
    - step: exact generated step number
    - unit/token/residue/modifier: exact unit name, e.g. A, R, dR, Hyp, FITC, BIOTIN, Ac
    - phase: substring match, e.g. Loading, Regular, Last

    Values:
    - coupling_reagent / reagent / coupling
    - catalyst
    - additive
    - base
    - reaction_solvent / solvent
    - reagent_eq / eq / equiv / coupling_eq
    - coupling_repeat / reaction_x / repeat / double / triple
    - note

    Examples:
    step=2; reagent_eq=6; coupling_repeat=2; coupling_reagent=HBTU; base=DIEA
    unit=FITC; coupling_reagent=FITC; base=DIEA; reagent_eq=2; coupling_repeat=1
    phase=Regular; reagent_eq=5; coupling_repeat=2
    """
    if not text or not str(text).strip():
        return []
    raw_lines = [ln.strip() for ln in str(text).replace("\r", "\n").split("\n") if ln.strip()]
    if not raw_lines:
        return []
    rows: list[dict[str, str]] = []
    first = raw_lines[0].lower()
    if ("step" in first or "unit" in first or "phase" in first) and ("," in raw_lines[0] or "\t" in raw_lines[0]):
        sample = "\n".join(raw_lines)
        dialect = csv.excel_tab if "\t" in raw_lines[0] else csv.excel
        reader = csv.DictReader(io.StringIO(sample), dialect=dialect)
        for row in reader:
            rows.append({_canon_key(k or ""): (v or "").strip() for k, v in row.items()})
    else:
        for ln in raw_lines:
            if "=" in ln or ":" in ln:
                d = _split_kv_line(ln)
                m = re.match(r"^\s*(\d+)\s*(?:[,;/|]\s*)", ln)
                if m and "step" not in d:
                    d["step"] = m.group(1)
                if "unit" not in d and "token" not in d and "residue" not in d and "modifier" not in d and "step" not in d and "phase" not in d:
                    head = re.split(r"\s*(?:;|/|\||,)\s*", ln.strip(), maxsplit=1)[0]
                    if head and "=" not in head and ":" not in head:
                        d["unit"] = head.strip()
                rows.append(d)
            else:
                parts = [p.strip() for p in re.split(r"\s*,\s*|\s*\t\s*", ln)]
                if not parts:
                    continue
                if parts[0].isdigit():
                    keys = ["step", "coupling_reagent", "coupling_reagent_eq", "coupling_reagent_count", "catalyst", "catalyst_eq", "catalyst_count", "additive", "base", "base_eq", "base_count", "reaction_solvent", "reagent_eq", "coupling_repeat", "note"]
                else:
                    keys = ["unit", "coupling_reagent", "coupling_reagent_eq", "coupling_reagent_count", "catalyst", "catalyst_eq", "catalyst_count", "additive", "base", "base_eq", "base_count", "reaction_solvent", "reagent_eq", "coupling_repeat", "note"]
                rows.append({k: parts[i] if i < len(parts) else "" for i, k in enumerate(keys)})
    aliases = {
        "reagent": "coupling_reagent", "coupling": "coupling_reagent", "couplingreagent": "coupling_reagent",
        "solvent": "reaction_solvent", "rxn_solvent": "reaction_solvent", "reactionsolvent": "reaction_solvent",
        "eq": "reagent_eq", "equiv": "reagent_eq", "equivalent": "reagent_eq", "equivalents": "reagent_eq", "coupling_eq": "reagent_eq",
        "aa": "unit", "residue": "unit", "modifier": "unit", "token": "unit",
        "reaction_x": "coupling_repeat", "reaction_repeat": "coupling_repeat", "coupling_x": "coupling_repeat", "repeat": "coupling_repeat", "repeats": "coupling_repeat", "double": "coupling_repeat", "triple": "coupling_repeat",
    }
    clean_rows: list[dict[str, Any]] = []
    for row in rows:
        norm: dict[str, Any] = {}
        for k, v in row.items():
            if not k:
                continue
            key = aliases.get(_canon_key(k), _canon_key(k))
            if v is None or str(v).strip() == "":
                continue
            norm[key] = str(v).strip()
        if "step" in norm:
            try:
                norm["step"] = int(float(norm["step"]))
            except Exception:
                norm.pop("step", None)
        if "reagent_eq" in norm:
            try:
                norm["reagent_eq"] = float(norm["reagent_eq"])
            except Exception:
                norm.pop("reagent_eq", None)
        if "coupling_repeat" in norm:
            rep = _parse_repeat(norm["coupling_repeat"])
            if rep is None:
                norm.pop("coupling_repeat", None)
            else:
                norm["coupling_repeat"] = rep
        if any(k in norm for k in ["step", "unit", "phase"]):
            clean_rows.append(norm)
    return clean_rows



def _norm_material_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip())


def _library_row(name: str, lib_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nm = _norm_material_name(name)
    if not nm:
        return {}
    for key in (nm, nm.upper(), nm.lower()):
        if key in lib_lookup:
            return lib_lookup[key]
    # Strip explanatory suffixes from GUI/default strings, e.g. "DIC / verify".
    head = re.split(r"\s*(?:/|;|\(|,)\s*", nm, maxsplit=1)[0].strip()
    for key in (head, head.upper(), head.lower()):
        if key in lib_lookup:
            return lib_lookup[key]
    return {}


def _float_any(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        s = str(value).strip()
        if not s or s.lower() in {"nan", "none", "null"}:
            return default
        return float(s)
    except Exception:
        return default


def _mass_volume_from_library(name: str, mmol: float, lib_lookup: dict[str, dict[str, Any]]) -> tuple[float, float, float, float, str]:
    """Return (g, mL, MW, density, warning) for an auxiliary reagent.

    Liquid volume is calculated only when density is available. Missing MW is
    returned as a warning instead of silently pretending the material is zero.
    """
    row = _library_row(name, lib_lookup)
    mw = _float_any(row.get("MW") if row else 0.0)
    density = _float_any(row.get("density_g_mL") if row else 0.0)
    if not str(name or "").strip():
        return 0.0, 0.0, 0.0, 0.0, ""
    if not row:
        return 0.0, 0.0, 0.0, 0.0, f"No auxiliary reagent library row for {name}; amount requires manual check."
    if not mw:
        return 0.0, 0.0, 0.0, density, f"No MW for auxiliary reagent {name}; amount requires manual check."
    g = float(mmol or 0.0) * mw / 1000.0
    mL = g / density if density else 0.0
    return g, mL, mw, density, ""



def _sequence_key_for_cleavage(seq: str) -> str:
    parsed = parse_sequence(seq)
    core = "".join(str(t).upper().replace("D", "d", 1) if str(t).startswith("d") else str(t).upper() for t in (parsed.core_tokens or []))
    nt = str(parsed.nterm or "").strip().upper()
    ct = str(parsed.cterm_text or "").strip().upper()
    return f"{nt}-{core}-{ct}".strip("-")


def cleavage_eq_suggestion(inp: PlanInput) -> dict[str, float | str]:
    """Return the working cleavage-cocktail equivalent rule.

    Confirmed operator contracts are applied before generic sequence rules:
    - GHK = 18 eq
    - Ac-EEMQRR-NH2 = 30 eq
    - default/STD 30 eq, >=15mer 80 eq, >=22mer 100 eq
    - each Cys adds +100 eq
    Manual override wins over all automatic rules.
    """
    parsed = parse_sequence(inp.sequence)
    tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
    n = len(tokens)
    cys_count = sum(1 for t in tokens if str(t).upper() in {"C", "DC", "dC"})
    override = float(getattr(inp, "cleavage_eq_override", 0.0) or 0.0)
    if override > 0:
        eq = override
        source = "manual_override"
    else:
        key = _sequence_key_for_cleavage(inp.sequence)
        if key in {"GHK", "GHK-NH2", "GHK-CONH2"}:
            eq = 18.0
            source = "confirmed_GHK_contract"
        elif key in {"AC-EEMQRR-NH2", "AC-EEMQRR-CONH2"}:
            eq = 30.0
            source = "confirmed_Ac-EEMQRR-NH2_contract"
        elif n >= 22:
            eq = 100.0
            source = "length>=22mer"
        elif n >= 15:
            eq = 80.0
            source = "length>=15mer"
        else:
            eq = 30.0
            source = "STD/default"
    if cys_count:
        eq += 100.0 * cys_count
        source += f" + Cys x{cys_count}"
    tfa_mmol = float(inp.scale_mmol or 0.0) * eq
    tfa_g = tfa_mmol * 114.02 / 1000.0
    tfa_mL = tfa_g / 1.49 if tfa_g else 0.0
    return {"cleavage_eq": eq, "source": source, "tfa_mL_neat_equiv": tfa_mL, "tfa_g_neat_equiv": tfa_g, "length_tokens": n, "cys_count": cys_count}


_CLEAVAGE_COMPONENT_INFO = {
    "TFA": {"role": "cleavage acid", "density": 1.49, "state": "liquid"},
    "TIS": {"role": "silane scavenger", "density": 0.773, "state": "liquid"},
    "TIPS": {"role": "silane scavenger", "density": 0.773, "state": "liquid", "canonical": "TIS"},
    "DW / water": {"role": "cation scavenger", "density": 1.0, "state": "liquid"},
    "Water": {"role": "cation scavenger", "density": 1.0, "state": "liquid", "canonical": "DW / water"},
    "H2O": {"role": "cation scavenger", "density": 1.0, "state": "liquid", "canonical": "DW / water"},
    "EDT": {"role": "thiol/reducing scavenger", "density": 1.123, "state": "liquid"},
    "Thioanisole": {"role": "aryl/thioether scavenger", "density": 1.06, "state": "liquid"},
    "Anisole": {"role": "aryl scavenger", "density": 0.995, "state": "liquid"},
    "DMS": {"role": "methionine scavenger", "density": 0.846, "state": "liquid"},
    "DMSO": {"role": "oxidation/reduction additive", "density": 1.10, "state": "liquid"},
    "Phenol": {"role": "solid scavenger", "density": 1.07, "state": "solid_or_melt"},
    "DTT": {"role": "reducing scavenger", "density": 0.0, "state": "solid_wv"},
    "Ammonium iodide": {"role": "Met oxidation suppressor", "density": 0.0, "state": "solid_wv"},
    "DMB": {"role": "Rink linker stabilizer", "density": 0.0, "state": "solid_wv"},
    "p-Cresol": {"role": "phenolic scavenger", "density": 1.034, "state": "liquid_or_solid"},
    "Triethylsilane": {"role": "silane scavenger", "density": 0.728, "state": "liquid"},
}








def _parse_cleavage_components_text(text: str) -> dict[str, float]:
    comps: dict[str, float] = {}
    for part in re.split(r"\s*(?:;|,|\n|\|)\s*", str(text or "").strip()):
        if not part:
            continue
        if "=" in part:
            name, value = part.split("=", 1)
        elif ":" in part:
            name, value = part.split(":", 1)
        else:
            continue
        name = _canonical_cleavage_component(name)
        try:
            pct = float(str(value).replace("%", "").strip())
        except Exception:
            continue
        if pct > 0:
            comps[name] = comps.get(name, 0.0) + pct
    return comps


def _recommend_cleavage_preset_initial(inp: PlanInput | str) -> dict[str, Any]:
    """Recommend a cleavage cocktail preset from peptide composition.

    This does not claim a universal bench method.  It makes the UI useful by
    choosing a conservative default and explaining why.  The operator can always
    override the preset or component list.
    """
    seq = inp.sequence if hasattr(inp, "sequence") else str(inp or "")
    resin = inp.resin if hasattr(inp, "resin") else "Amide"
    parsed = parse_sequence(seq)
    tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
    aas = [str(t).replace("d", "").upper() for t in tokens]
    counts = {aa: aas.count(aa) for aa in sorted(set(aas))}
    if resin_family(resin) == "CTC/Trityl":
        return {"preset": "REAGENT_B", "reason": "2-CTC/Trityl resin detected; full deprotection still requires SOP check."}
    if counts.get("C", 0) and any(counts.get(x, 0) for x in ("M", "W", "Y")):
        return {"preset": "REAGENT_K", "reason": "Cys plus Met/Trp/Tyr detected; broad sensitive-residue scavenger mix recommended."}
    if counts.get("C", 0):
        return {"preset": "CYS_EDT", "reason": "Cys detected; EDT/TIS/water-containing cocktail recommended for thiol-sensitive cases."}
    if counts.get("M", 0):
        return {"preset": "REAGENT_H", "reason": "Met detected; Reagent H is shown as the methionine-oxidation-suppression route and still requires SOP review."}
    if counts.get("W", 0):
        return {"preset": "REDUCING_TFA_TIS_WATER_EDT", "reason": "Trp detected; a reducing EDT-containing mixture is shown, but exposure time requires SOP review."}
    if counts.get("Y", 0):
        return {"preset": "REAGENT_B", "reason": "Tyr detected; phenolic/scavenger-rich option suggested."}
    return {"preset": "DEFAULT_TFA_TIS_WATER", "reason": "No Cys/Met/Trp/Tyr sensitivity trigger detected; standard TFA/TIS/water preset selected."}


def _format_cleavage_components_name(components: dict[str, float]) -> str:
    """Return an operator-facing preset name that states the actual contents."""
    parts = []
    for name, value in components.items():
        try:
            number = float(value)
        except Exception:
            continue
        if number <= 0:
            continue
        label = _canonical_cleavage_component(name)
        text = f"{number:g}"
        parts.append(f"{label}={text}")
    return "; ".join(parts)


def _selected_cleavage_preset_name(inp: PlanInput) -> str:
    custom = _parse_cleavage_components_text(getattr(inp, "cleavage_components_text", ""))
    if custom:
        return _format_cleavage_components_name(custom) or "CUSTOM"
    requested = str(getattr(inp, "cleavage_preset", "AUTO") or "AUTO").strip()
    if requested.upper() in {"", "AUTO", "AUTO_SEQUENCE", "AUTO_RECOMMEND"}:
        requested = str(recommend_cleavage_preset(inp).get("preset") or "DEFAULT_TFA_TIS_WATER")
    components = _preset_components(requested)
    return _format_cleavage_components_name(components) or requested


def _selected_cleavage_components(inp: PlanInput) -> dict[str, float]:
    custom = _parse_cleavage_components_text(getattr(inp, "cleavage_components_text", ""))
    if custom:
        return custom
    requested = str(getattr(inp, "cleavage_preset", "AUTO") or "AUTO").strip()
    if requested.upper() in {"", "AUTO", "AUTO_SEQUENCE", "AUTO_RECOMMEND"}:
        requested = str(recommend_cleavage_preset(inp).get("preset") or "DEFAULT_TFA_TIS_WATER")
    parsed_direct = _parse_cleavage_components_text(requested)
    if parsed_direct:
        return parsed_direct
    if requested.strip().upper() in {"", "CUSTOM"}:
        comps = {"TFA": float(getattr(inp, "cleavage_tfa_percent", 95.0) or 0.0), "TIS": float(getattr(inp, "cleavage_tis_percent", 2.5) or 0.0), "DW / water": float(getattr(inp, "cleavage_water_percent", 2.5) or 0.0)}
        return {k: v for k, v in comps.items() if v > 0}
    return _preset_components(requested)


def _generate_cleavage_cocktail_initial(inp: PlanInput) -> pd.DataFrame:
    """Generate a dedicated cleavage cocktail calculator table.

    Component volumes are calculated from the equivalent-based neat TFA volume.
    Components with zero or omitted percentages are excluded. AUTO uses the
    sequence-based recommendation while manual preset/custom text wins.
    """
    sug = cleavage_eq_suggestion(inp)
    comps = _selected_cleavage_components(inp)
    if not comps:
        comps = _parse_cleavage_components_text("TFA=95;TIS=2.5;Water=2.5")
    pct_sum = sum(max(0.0, float(v or 0.0)) for v in comps.values())
    if pct_sum <= 0:
        comps = _parse_cleavage_components_text("TFA=95;TIS=2.5;Water=2.5")
        pct_sum = 100.0
    tfa_pct = sum(v for k, v in comps.items() if _canonical_cleavage_component(k) == "TFA")
    if tfa_pct <= 0:
        comps = dict(comps)
        comps["TFA"] = 95.0
        pct_sum = sum(comps.values())
        tfa_pct = 95.0
    selected_preset = _selected_cleavage_preset_name(inp)
    rec = recommend_cleavage_preset(inp)
    tfa_frac = tfa_pct / pct_sum
    tfa_mL = float(sug.get("tfa_mL_neat_equiv", 0.0) or 0.0)
    total_mL = tfa_mL / tfa_frac if tfa_frac else tfa_mL
    reserve = float(getattr(inp, "cleavage_reserve_mL", 0.0) or 0.0)
    if reserve > 0:
        total_mL = max(total_mL, reserve)
    rows = []
    for name, raw_pct in comps.items():
        name = _canonical_cleavage_component(name)
        pct_norm = max(0.0, float(raw_pct or 0.0)) / pct_sum * 100.0
        if pct_norm <= 0:
            continue
        info = dict(_CLEAVAGE_COMPONENT_INFO.get(name, {}))
        density = float(info.get("density") or 0.0)
        state = str(info.get("state") or "liquid")
        vol = total_mL * pct_norm / 100.0
        approx_g = ""
        vol_out: float | str = round(vol, 6)
        if density and state in {"liquid", "liquid_or_solid", "solid_or_melt"}:
            approx_g = round(vol * density, 6)
        elif state == "solid_wv":
            approx_g = round(total_mL * pct_norm / 100.0, 6)
            vol_out = ""
        rows.append({
            "component": name,
            "role": info.get("role", "scavenger"),
            "recommended_eq": sug.get("cleavage_eq") if name == "TFA" else "",
            "percent": round(pct_norm, 3),
            "percent_basis": "v/v" if state not in {"solid_wv"} else "approx w/v",
            "volume_mL": vol_out,
            "density_g_mL": density or "",
            "approx_g": approx_g,
            "physical_state": state,
            "selected_preset": selected_preset,
            "auto_recommended_preset": rec.get("preset", ""),
            "include": "YES",
            "note": f"Eq basis: {sug.get('source')} ; peptide length={sug.get('length_tokens')} ; Cys={sug.get('cys_count')} ; auto reason: {rec.get('reason','')}" if name == "TFA" else "Included by selected/custom cleavage cocktail preset.",
        })
    rows.append({
        "component": "Total cocktail", "role": "total", "recommended_eq": sug.get("cleavage_eq"), "percent": 100.0,
        "percent_basis": "normalized", "volume_mL": round(total_mL, 6), "density_g_mL": "", "approx_g": "", "physical_state": "mixture",
        "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "YES",
        "note": f"Preset={selected_preset}; requested={getattr(inp, 'cleavage_preset', 'AUTO') or 'AUTO'}; custom={bool(str(getattr(inp, 'cleavage_components_text', '') or '').strip())}. Prepare fresh and verify sequence-specific scavengers by SOP.",
    })
    if int(float(sug.get("cys_count", 0) or 0)) > 0:
        rows.append({"component": "Cys warning", "role": "manual check", "recommended_eq": "", "percent": "", "percent_basis": "", "volume_mL": "", "density_g_mL": "", "approx_g": "", "physical_state": "", "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "INFO", "note": "Cys detected: planner adds +100 eq per Cys. EDT/thioanisole/TIS/water selection should be confirmed by lab SOP."})
    if resin_family(inp.resin) == "CTC/Trityl":
        rows.append({"component": "2-CTC/Trityl warning", "role": "manual check", "recommended_eq": "", "percent": "", "percent_basis": "", "volume_mL": "", "density_g_mL": "", "approx_g": "", "physical_state": "", "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "INFO", "note": "2-CTC/Trityl full cleavage/deprotection may require different acid strength than test cleavage. Confirm cocktail before bench use."})
    return pd.DataFrame(rows)


def _liquid_display_policy(df: pd.DataFrame) -> pd.DataFrame:
    """Show true liquid/solution reagents as mL-only in operator-facing tables.

    V2.1.9 rule: DIC is treated as a liquid reagent/solvent-like component for
    bench display, and DIEA/DIPEA/DIC/DMF/DCM/MC/NMP/TFA/TIS/EDT/AcOH/TFE/
    piperidine/water rows must not show grams in Selected Materials or Selected
    Total Materials.  Grams can still exist internally for calculations, but the
    operator-facing table is mL-only for these rows.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    if "density_g_mL" not in out.columns:
        return out
    mat = out.get("material", pd.Series([""] * len(out))).astype(str).str.lower().str.strip()
    reagent = out.get("reagent", pd.Series([""] * len(out))).astype(str).str.lower().str.strip()
    state = out.get("physical_state", pd.Series([""] * len(out))).astype(str).str.lower().str.strip()
    dens = pd.to_numeric(out["density_g_mL"], errors="coerce").fillna(0.0)
    liquid_names = (
        "dic", "diea", "dipea", "dmf", "dcm", "mc", "mc/dcm", "nmp",
        "tfa", "tis", "edt", "acoh", "acetic acid", "tfe", "tee",
        "piperidine", "water", "h2o", "dw", "dw / water", "meoh", "methanol",
        "acetic anhydride", "ac2o", "thioanisole", "anisole", "dms", "dmso", "triethylsilane"
    )
    def _is_named_liquid(x: str) -> bool:
        x = str(x or "").lower().strip()
        base = x.split(" -")[0].strip()
        return any(base == n or x == n or x.startswith(n + " ") or x.startswith(n + " -") for n in liquid_names)
    is_liquid_name = mat.map(_is_named_liquid) | reagent.map(_is_named_liquid)
    liquid_like = is_liquid_name | state.isin(["liquid", "solution"]) | (dens.gt(0) & is_liquid_name)
    for col in ("planned_g", "planned_mg", "approx_g"):
        if col in out.columns:
            out.loc[liquid_like, col] = 0.0
    if "unit" in out.columns:
        out.loc[liquid_like, "unit"] = "mL"
    if "warning" in out.columns:
        existing = out.loc[liquid_like, "warning"].fillna("").astype(str)
        add = "Liquid/solution reagent: operator table reports mL only."
        out.loc[liquid_like, "warning"] = existing.map(lambda x: (x + " | " + add).strip(" |") if add not in x else x)
    return out

def validate_plan(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    """Return user-visible validation warnings for the current SPPS plan.

    This intentionally reports risky assumptions instead of blocking the run:
    branch handling, terminal/resin conflicts, missing DB MW, and manual-required
    generic labels/linkers/tags.
    """
    compounds = compounds if compounds is not None else load_compounds()
    lookup = compound_lookup(compounds)
    lib_lookup = reagent_lookup(load_reagent_library())
    parsed = parse_sequence(inp.sequence)
    rows: list[dict[str, Any]] = []
    def add(level: str, area: str, item: str, message: str):
        rows.append({"level": level, "area": area, "item": item, "message": message})
    if not parsed.core_tokens:
        add("ERROR", "sequence", inp.sequence, "Core sequence is empty or could not be parsed.")
    for w in list(getattr(parsed, "warnings", []) or []):
        add("WARNING", "sequence", inp.sequence, w)
    for w in _cterm_resin_warnings(parsed, inp.resin):
        add("WARNING", "resin/C-terminal", inp.resin, w)
    tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or []) + ([parsed.nterm] if parsed.nterm else [])
    for tok in tokens:
        row = _row_for(tok, lookup)
        if not row:
            add("WARNING", "compound DB", tok, "Token is not in compounds.csv; MW/material/product contribution will be zero until added.")
            continue
        profile = str(row.get("Chemistry profile") or "").upper()
        cls = str(row.get("Class") or "")
        counts = str(row.get("Counts as coupling unit?") or "").strip().lower()
        mw = _float_row(row, "Reagent MW (g/mol)")
        prod = _float_row(row, "Product MW contribution (g/mol)")
        if "MANUAL_REQUIRED" in profile:
            add("WARNING", "compound DB", tok, "Generic/manual-required token: choose exact reagent form or override MW/chemistry before relying on amounts.")
        if counts != "no" and not mw and cls.lower() not in {"tag"}:
            add("WARNING", "compound DB", tok, "Reagent MW is missing; planned gram amount will be 0 or manual.")
        if counts != "no" and not prod and cls.lower() not in {"control", "c-terminal"}:
            add("WARNING", "compound DB", tok, "Product MW contribution is missing; product MW/M+H may be underestimated.")
    try:
        matrix = generate_step_matrix(inp, compounds, rules)
        for _, s in matrix.iterrows():
            protected_name = str(s.get("protected_reagent", "") or "").strip().lower()
            unit_name = str(s.get("unit", "") or "").strip().lower()
            for mat in [s.get("coupling_reagent", ""), s.get("catalyst", ""), s.get("additive", ""), s.get("base", "")]:
                mat = str(mat or "").strip()
                mat_l = mat.lower()
                if not mat or mat.upper() == "N/A" or "MANUAL" in mat.upper() or "VERIFY" in mat.upper():
                    continue
                if mat_l and (mat_l == protected_name or mat_l == unit_name):
                    continue
                _, _, mw, _, warn = _mass_volume_from_library(mat, float(inp.scale_mmol) * float(s.get("total_reagent_eq", 0) or 0), lib_lookup)
                if warn:
                    add("WARNING", "auxiliary reagent DB", mat, warn)
    except Exception as exc:
        add("ERROR", "engine", inp.sequence, f"Plan generation failed during validation: {exc}")
    try:
        guidance = generate_literature_guidance(inp)
        for _, item in guidance.iterrows():
            level = str(item.get("severity", "") or item.get("priority", "INFO") or "INFO").upper()
            message = str(
                item.get("guidance", "")
                or item.get("recommendation", "")
                or item.get("message", "")
            ).strip()
            if message:
                add(
                    level,
                    f"literature/{item.get('category', '')}",
                    str(item.get("trigger", "")),
                    message,
                )
    except Exception as exc:
        add("ERROR", "literature guidance", inp.sequence, f"Literature guidance generation failed: {exc}")
    if not rows:
        add("OK", "validation", inp.sequence, "No blocking validation issue detected by automated checks.")
    return pd.DataFrame(rows)

def _modifier_defaults(unit: str, lookup: dict[str, dict[str, Any]], inp: PlanInput) -> dict[str, Any] | None:
    token = str(unit or "").strip()
    t = token.upper()
    cls = _class_for(token, lookup).lower()
    profile = _profile_for(token, lookup).upper()
    row = _row_for(token, lookup)
    reagent_name = str(row.get("Reagent/protected form") or token)
    if token in {"Ac", "Acetic acid", "Acetyl"} or t == "AC":
        return {
            "coupling_reagent": "",
            "catalyst": "",
            "additive": "",
            "base": "DIEA",
            "reaction_solvent": "DMF",
            "reagent_eq": inp.ac_eq,
            "coupling_repeat": inp.default_modifier_repeats,
            "reagent_eq_source": "modifier_default_ac",
            "note_add": "N-terminal acetylation. Display as Ac; actual reagent is Acetic anhydride (Ac2O, MW 102.09 g/mol, density 1.08 g/mL) unless user overrides SOP."
        }
    if "MANUAL_REQUIRED" in profile:
        return {"coupling_reagent": reagent_name or "Manual required", "catalyst": "", "additive": "MANUAL REQUIRED: select exact vendor form/CoA before material calculation", "base": "", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "manual_required", "note_add": "Manual-required generic token: product/reagent MW may be excluded until a form-specific row is selected."}
    if any(x in profile for x in ["CHLOROFORMATE", "ANHYDRIDE_BASE", "ACOH_ROUTE"]):
        return {"coupling_reagent": reagent_name or token, "catalyst": "", "additive": "VERIFY base/solvent by lab SOP", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_activated_cap", "note_add": "Activated cap/protecting reagent default; exact base/solvent can be overridden per SOP."}
    if cls == "tag" or "MACRO_SEQUENCE" in profile:
        return {"coupling_reagent": reagent_name or "Tag macro", "catalyst": "", "additive": "MACRO TAG: product MW included; material usage requires expanded residues or prebuilt reagent", "base": "", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "macro_sequence_manual_materials", "note_add": "Tag macro: final product MW includes tag residue mass, but reagent MW/material usage is manual unless expanded residue-by-residue."}
    if "NHS" in profile or t.endswith("-NHS") or "NHS" in t:
        return {"coupling_reagent": reagent_name, "catalyst": "", "additive": "activated ester; verify reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_nhs", "note_add": "NHS/activated ester default; no DIC/HOBt unless actual reagent form requires it."}
    if "FITC" in t or "ISOTHIOCYANATE" in profile:
        return {"coupling_reagent": reagent_name if reagent_name else "FITC / isothiocyanate dye", "catalyst": "", "additive": "protect from light; verify reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_fitc", "note_add": "FITC default assumes amine-labeling/isothiocyanate chemistry; verify SOP."}
    if "BIOTIN" in t:
        return {"coupling_reagent": reagent_name if reagent_name else "Biotin reagent (acid/NHS; verify form)", "catalyst": "", "additive": "VERIFY acid vs NHS/sulfo-NHS", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_biotin", "note_add": "Biotin chemistry depends on reagent form; override reagent/catalyst/base/eq."}
    if any(x in t for x in ["CY5", "CY3", "FAM", "TAMRA", "DABCYL", "BHQ", "DOTA", "NOTA"]):
        return {"coupling_reagent": reagent_name or "Activated label / chelator reagent", "catalyst": "", "additive": "protect from light; verify label reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_label", "note_add": "Label/chelator default is conservative; exact chemistry depends on reagent form."}
    if token in {"Pal", "Myr", "Nic", "Caf", "Gal", "Stear", "Ole"} or "ACID" in profile or "CARBOXYLIC" in profile:
        return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_acid", "note_add": "Acid-like modifier/label/cap default follows selected coupling system; override as needed."}
    if cls in {"label", "base chem", "chemical", "modifier", "n-term modifier"} or "SPECIAL" in profile:
        return {"coupling_reagent": reagent_name or "Selected modifier reagent; verify form", "catalyst": "", "additive": "VERIFY chemistry", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_verify", "note_add": "Generic modifier default; override based on actual reagent/SOP."}
    return None


def _default_step_reagents(phase: str, unit: str, inp: PlanInput, lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    lookup = lookup or {}
    if phase == "Loading" and direct_loading_enabled(inp):
        # 2-CTC/trityl loading is performed under DCM conditions.
        # DIEA/DIPEA is a base, not a coupling reagent, so do not duplicate it
        # as both reagent and base.
        return {"coupling_reagent": "", "catalyst": "", "additive": "", "base": inp.default_base or "DIEA", "reaction_solvent": "DCM", "reagent_eq": float(getattr(inp, "loading_aa_eq", 2.0) or 2.0), "coupling_repeat": 1, "coupling_repeat_source": "trityl_loading_1x", "reagent_eq_source": "trityl_loading_user_ratio", "note": f"2-CTC/Trityl loading stoichiometry: resin:AA:DIEA = 1:{float(getattr(inp, 'loading_aa_eq', 2.0) or 2.0):g}:{float(getattr(inp, 'loading_diea_eq', 4.0) or 4.0):g}" + (f"; time={float(getattr(inp, 'loading_time_h', 0.0) or 0.0):g} h" if float(getattr(inp, 'loading_time_h', 0.0) or 0.0) > 0 else "")}
    if phase == "Loading":
        return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.coupling_eq, "coupling_repeat": 1, "coupling_repeat_source": "loading_default", "reagent_eq_source": getattr(inp, "_coupling_eq_source", "global_loading")}
    if phase == "Last / N-term cap":
        md = _modifier_defaults(unit, lookup, inp)
        if md:
            note_add = md.pop("note_add", "")
            return md | {"default_note_add": note_add}
    return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.coupling_eq, "coupling_repeat": inp.default_coupling_repeats, "reagent_eq_source": getattr(inp, "_coupling_eq_source", "global_aa")}


def _match_override(step_no: int, unit: str, phase: str, overrides: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    source_parts: list[str] = []
    unit_l = str(unit or "").strip().lower()
    phase_l = str(phase or "").strip().lower()
    for row in overrides:
        matched = False
        if "phase" in row and str(row["phase"]).strip().lower() in phase_l:
            matched = True
        if "unit" in row and str(row["unit"]).strip().lower() == unit_l:
            matched = True
        if "step" in row and int(row["step"]) == int(step_no):
            matched = True
        if matched:
            for key in ["coupling_reagent", "catalyst", "additive", "base", "reaction_solvent", "reagent_eq", "coupling_repeat", "note"]:
                if key in row:
                    merged[key] = row[key]
            if "step" in row: source_parts.append(f"step:{row['step']}")
            if "unit" in row: source_parts.append(f"unit:{row['unit']}")
            if "phase" in row: source_parts.append(f"phase:{row['phase']}")
    if merged:
        merged["override_source"] = "+".join(source_parts) or "manual_override"
        if "reagent_eq" in merged:
            merged["reagent_eq_source"] = "manual_override"
        if "coupling_repeat" in merged:
            merged["coupling_repeat_source"] = "manual_override"
    return merged


def _operator_solvent_name(name: Any) -> str:
    """Normalize legacy operator-facing solvent aliases without losing selection semantics."""
    raw = str(name or "").strip()
    key = re.sub(r"[^A-Za-z0-9]+", "", raw).upper()
    if key in {"DCM", "MC", "METHYLENECHLORIDE", "DICHLOROMETHANE"}:
        return "MC/DCM"
    return raw


def _parse_solvent_mix(text: Any, default: str = "90% DCM / 10% DMF") -> list[tuple[str, float]]:
    """Parse editable solvent text such as ``90% DCM / 10% DMF``.

    Percentages are normalized to 1.0. A single solvent name is treated as
    100%. DCM/MC aliases retain the established operator label MC/DCM.
    """
    raw = str(text or default).strip() or default
    matches = re.findall(
        r"([0-9]+(?:\.[0-9]+)?)\s*%\s*([A-Za-z][A-Za-z0-9 /_-]*?)(?=(?:\s*[/,;+]\s*)?[0-9]+(?:\.[0-9]+)?\s*%|$)",
        raw,
        flags=re.IGNORECASE,
    )
    parts: list[tuple[str, float]] = []
    for pct, name in matches:
        clean = re.sub(r"[\s/,;+_-]+$", "", str(name)).strip()
        if clean:
            parts.append((_operator_solvent_name(clean), max(0.0, float(pct))))
    if not parts:
        return [(_operator_solvent_name(raw), 1.0)]
    total = sum(v for _, v in parts)
    if total <= 0:
        return [(_operator_solvent_name(default), 1.0)]
    merged: dict[str, float] = {}
    order: list[str] = []
    for name, value in parts:
        if name not in merged:
            order.append(name)
            merged[name] = 0.0
        merged[name] += value / total
    # Keep DMF/NMP-type fraction in the legacy solvent1 column and MC/DCM in
    # solvent2 so old exports remain meaningful.
    order.sort(key=lambda n: 1 if n.upper() == "MC/DCM" else 0)
    return [(name, merged[name]) for name in order]


def _loading_solvent_pair(inp: "PlanInput") -> tuple[str, float, str, float]:
    parts = _parse_solvent_mix(getattr(inp, "loading_dissolve_solvent", "90% DCM / 10% DMF"))
    first_name, first_frac = parts[0]
    if len(parts) > 1:
        second_name = " + ".join(name for name, _ in parts[1:])
        second_frac = sum(frac for _, frac in parts[1:])
    else:
        second_name, second_frac = "", 0.0
    return first_name, first_frac, second_name, second_frac


def _make_step(step_no: int, unit: str, phase: str, chemistry: str, depro: int, wash: int, rxn: int, post: int, dcmx: int,
               dmf_frac: float, dcm_frac: float, dmf: float, pip: float, dcm: float, note: str,
               inp: PlanInput, overrides: list[dict[str, Any]], lookup: dict[str, dict[str, Any]], pos_cterm: int, pos_nterm: int) -> Step:
    defaults = _default_step_reagents(phase, unit, inp, lookup)
    extra_note = defaults.pop("default_note_add", "") if "default_note_add" in defaults else ""
    ov = _match_override(step_no, unit, phase, overrides)
    source = "default"
    if ov:
        defaults.update({k: v for k, v in ov.items() if k not in {"override_source"}})
        source = str(ov.get("override_source") or "manual_override")
    defaults = _normalize_coupling_defaults(defaults)
    old_rxn = max(0, int(rxn or 0))
    if old_rxn == 0:
        rep = 0
        defaults = _clear_non_reaction_reagents(defaults)
    else:
        rep = _parse_repeat(defaults.get("coupling_repeat", rxn)) or old_rxn
    if rep != old_rxn:
        # Reaction solvent volume scales with the number of coupling/reaction repeats.
        # Deprotection and wash volumes are unchanged.
        dmf += max(0, rep - old_rxn) * working_volume_mL(inp) * float(dmf_frac)
        dcm += max(0, rep - old_rxn) * working_volume_mL(inp) * float(dcm_frac)
    rxn = rep
    if extra_note and extra_note not in note:
        note = f"{note} | {extra_note}"
    if "note" in defaults and str(defaults["note"]).strip():
        note = f"{note} | manual note: {defaults['note']}"
    row = _row_for(unit, lookup)
    protected = str(row.get("Reagent/protected form") or unit)
    reagent_class = str(row.get("Class") or "Unknown")
    mw = _float_row(row, "Reagent MW (g/mol)")
    prod = _float_row(row, "Product MW contribution (g/mol)")
    raw_eq = defaults.get("reagent_eq", 1.0)
    try:
        eq = float(raw_eq)
    except Exception:
        eq = 1.0
    total_eq = eq * rep
    mmol = float(inp.scale_mmol) * total_eq
    g = mmol * mw / 1000.0 if mw else 0.0
    resin_g = float(inp.scale_mmol) / float(inp.resin_loading_mmol_g) if inp.resin_loading_mmol_g else 0.0
    reagent_name = str(defaults.get("coupling_reagent", "") or "")
    catalyst_name = str(defaults.get("catalyst", "") or "")
    base_name = str(defaults.get("base", "") or "")
    follow_aa_eq = bool(getattr(inp, "reagent_eq_follows_coupling_eq", True))
    reagent_eq = (eq if follow_aa_eq else float(getattr(inp, "default_reagent_eq", eq) or 0.0)) if reagent_name and reagent_name.upper() != "N/A" else 0.0
    catalyst_eq = (eq if follow_aa_eq else float(getattr(inp, "default_catalyst_eq", eq) or 0.0)) if catalyst_name and catalyst_name.upper() != "N/A" else 0.0
    base_eq = (eq if follow_aa_eq else float(getattr(inp, "default_base_eq", 0.0) or 0.0)) if base_name and base_name.upper() != "N/A" else 0.0
    reagent_count = max(0, int(getattr(inp, "default_reagent_count", 1) or 0)) if reagent_name and reagent_name.upper() != "N/A" else 0
    catalyst_count = max(0, int(getattr(inp, "default_catalyst_count", 1) or 0)) if catalyst_name and catalyst_name.upper() != "N/A" else 0
    base_count = max(0, int(getattr(inp, "default_base_count", 0) or 0)) if base_name and base_name.upper() != "N/A" else 0
    # Modifier-specific routes can intentionally replace/clear the global system.
    if phase == "Last / N-term cap":
        if reagent_name and reagent_name != str(getattr(inp, "default_coupling_reagent", "") or ""):
            reagent_eq, reagent_count = eq, 1
        if catalyst_name and catalyst_name != str(getattr(inp, "default_catalyst", "") or ""):
            catalyst_eq, catalyst_count = eq, 1
        if base_name and (not str(getattr(inp, "default_base", "") or "") or base_name != str(getattr(inp, "default_base", "") or "")):
            base_eq, base_count = eq, 1
    if phase == "Last / N-term cap" and unit in {"Ac", "Acetic acid", "Acetyl"}:
        reagent_eq = reagent_count = catalyst_eq = catalyst_count = 0
        if base_name:
            base_eq = float(getattr(inp, "default_base_eq", inp.ac_eq) or inp.ac_eq)
            base_count = max(1, base_count)
    auto_base_added = "auto-added diea" in str(defaults.get("note", "") or "").lower()
    if base_name and auto_base_added and base_count <= 0:
        # Base added by chemistry normalization (e.g. HBTU/HATU/COMU) must
        # remain an active calculated reagent even when the editable global
        # base count was blank/zero.
        if base_eq <= 0:
            base_eq = reagent_eq if reagent_eq > 0 else eq
        base_count = 1
    elif base_name and base_eq <= 0 and base_count <= 0:
        # Legacy fallback for a non-empty selected base without explicit values.
        base_eq = reagent_eq if reagent_eq > 0 else eq
        base_count = 1
    if direct_loading_enabled(inp) and phase == "Loading":
        reagent_eq = reagent_count = catalyst_eq = catalyst_count = 0
        if base_name:
            base_eq = float(getattr(inp, "loading_diea_eq", 4.0) or 4.0)
            base_count = 1
    return Step(
        step_no, "C-term to N-term", pos_cterm, pos_nterm, unit, phase, chemistry, depro, wash, rxn, post, dcmx, dmf_frac, dcm_frac, dmf, pip, dcm, note,
        protected, reagent_class, mw, prod,
        str(defaults.get("coupling_reagent", "")), str(defaults.get("catalyst", "")), str(defaults.get("additive", "")),
        str(defaults.get("base", "")), str(defaults.get("reaction_solvent", "")), eq,
        str(defaults.get("reagent_eq_source", "global_default")), rep, str(defaults.get("coupling_repeat_source", defaults.get("reagent_eq_source", "global_default"))), total_eq, mmol, g, g*1000.0, resin_g,
        source, "spps_ml_ready",
        reagent_eq, reagent_count, catalyst_eq, catalyst_count, base_eq, base_count,
        str(getattr(inp, "deprotection_base", "Piperidine") or "Piperidine"),
        str(getattr(inp, "wash_solvent1", "DMF") or "DMF"),
        _operator_solvent_name(getattr(inp, "wash_solvent2", "DCM") or "DCM"),
    )


def generate_step_matrix(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    compounds = compounds if compounds is not None else load_compounds()
    lookup = compound_lookup(compounds)
    rules = rules or load_rules()
    overrides = parse_step_overrides(inp.step_overrides_text)
    parsed = parse_sequence(inp.sequence)
    tokens = parsed.core_tokens or list(parsed.core)
    if not tokens:
        raise ValueError("Core sequence is empty")
    effective_eq, effective_eq_source = _resolve_coupling_eq(inp, len(tokens) + len(getattr(parsed, "branch_tokens", []) or []))
    inp = replace(inp, coupling_eq=effective_eq)
    setattr(inp, "_coupling_eq_source", effective_eq_source)
    plan_warnings = list(getattr(parsed, "warnings", []) or []) + _cterm_resin_warnings(parsed, inp.resin)
    family = resin_family(inp.resin)
    profile = resin_profile(inp.resin)
    vol = working_volume_mL(inp)
    dmf_ratio, pip_ratio = deprotection_fractions(inp, rules)
    steps: list[Step] = []
    step_no = 1
    cterm_unit = tokens[-1]
    n = len(tokens)
    # The Sequence field always contains only the residues that the operator
    # intends to synthesize in this run for both preloaded CTC profiles.
    # Therefore CTC(합성기) and CTC(합성용) must couple every entered token.
    # Only ordinary Amide/direct-loading profiles represent the written
    # C-terminal residue via a separate loading row and omit it from regular
    # coupling rows.
    full_sequence_profiles = {"AMIDE_PRELOADED", "CTC_PRELOADED"}
    coupling_tokens = tokens if profile in full_sequence_profiles else tokens[:-1]
    coupling_position_start = 1 if profile in full_sequence_profiles else 2
    if profile == "AMIDE":
        depro = max(0, int(getattr(inp, "deprotection_count", rules.get("amide_loading_depro", 2)) or 0)); wash = int(rules.get("amide_loading_dmf_wash", 6)); rxn = int(rules.get("amide_loading_synthesis", 1)); post = int(rules.get("amide_loading_post_dmf_wash", 2)); dmf_swell = int(rules.get("amide_loading_dmf_swell", 1))
        dmf = vol * (dmf_swell + depro * dmf_ratio + wash + rxn + post); pip = vol * (depro * pip_ratio); dcm = 0.0
        note = "Amide loading: DMF swell 1 -> depro 2 -> DMF wash 6 -> synthesis 1 -> DMF wash 2"
        if plan_warnings:
            note += " | WARNING: " + " ; ".join(plan_warnings)
        steps.append(_make_step(step_no, cterm_unit, "Loading", "Amide loading", depro, wash, rxn, post, 0, 1.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, 1, n))
        step_no += 1
    elif direct_loading_enabled(inp):
        swell = int(rules.get("ctc_loading_dcm_swell", 1)); rxn = int(rules.get("ctc_loading_synthesis", 1))
        load_solvent1, dmf_frac, load_solvent2, dcm_frac = _loading_solvent_pair(inp)
        dmf = vol * (rxn * dmf_frac); dcm = vol * (swell + rxn * dcm_frac)
        loading_mix_text = str(getattr(inp, "loading_dissolve_solvent", "90% DCM / 10% DMF") or "90% DCM / 10% DMF")
        note = f"2-CTC direct loading: MC/DCM swell 1 -> synthesis 1 with {loading_mix_text}"
        if plan_warnings:
            note += " | WARNING: " + " ; ".join(plan_warnings)
        steps.append(_make_step(step_no, cterm_unit, "Loading", "CTC/Trityl loading", 0, 0, rxn, 0, swell, dmf_frac, dcm_frac, dmf, 0.0, dcm, note, inp, overrides, lookup, 1, n))
        step_no += 1
    else:
        # Preloaded profiles do not create a separate loading row.  For
        # CTC(합성기)/CTC(합성용), every residue written in Sequence is still
        # coupled below; the externally attached residue is intentionally not
        # entered by the operator.
        pass
    for idx, aa in enumerate(reversed(coupling_tokens), start=coupling_position_start):
        depro = max(0, int(getattr(inp, "deprotection_count", rules.get("regular_depro", 2)) or 0)); wash = int(rules.get("regular_dmf_wash_after_depro", 2)); rxn = int(rules.get("regular_coupling", 1)); post = max(0, int(getattr(inp, "wash_solvent1_count", rules.get("regular_post_dmf_wash", 6)) or 0))
        dmf = vol * (depro * dmf_ratio + wash + rxn + post); pip = vol * (depro * pip_ratio)
        note = "Regular: depro 2 -> DMF wash 2 -> coupling 1 or user-defined repeat -> DMF wash 6"
        pos_cterm = idx; pos_nterm = n - idx + 1
        steps.append(_make_step(step_no, aa, "Regular AA coupling", _profile_for(aa, lookup), depro, wash, rxn, post, 0, 1.0, 0.0, dmf, pip, 0.0, note, inp, overrides, lookup, pos_cterm, pos_nterm))
        step_no += 1
    # Branch arm support: keep K(GGEP)-style notation from being silently lost.
    # These rows are a conservative orthogonal branch section. Exact branch
    # deprotection chemistry depends on the selected handle (K(Mtt), K(ivDde),
    # K(Fmoc), etc.) and can be refined through manual overrides.
    for br_i, br in enumerate(getattr(parsed, "branch_sites", []) or [], start=1):
        branch_tokens = list(br.get("branch_tokens", []) or [])
        if not branch_tokens:
            continue
        anchor = str(br.get("anchor_token", "branch point") or "branch point")
        depro = 0; wash = 0; rxn = 0; post = 2; dcmx = 0
        dmf = vol * post; pip = 0.0; dcm = 0.0
        note = f"Branch handle preparation at {anchor}: deprotect side-chain handle per selected PG/SOP, then DMF wash. Branch text={br.get('branch_text','')}."
        steps.append(_make_step(step_no, f"Branch@{anchor}", "Branch handle deprotection", "Orthogonal branch preparation", depro, wash, rxn, post, dcmx, 1.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, n, 0))
        step_no += 1
        for j, btok in enumerate(branch_tokens, start=1):
            depro = int(rules.get("regular_depro", 2)) if j > 1 else 0
            wash = int(rules.get("regular_dmf_wash_after_depro", 2)) if j > 1 else 0
            rxn = int(rules.get("regular_coupling", 1))
            post = int(rules.get("regular_post_dmf_wash", 6))
            dmf = vol * (depro * dmf_ratio + wash + rxn + post)
            pip = vol * (depro * pip_ratio)
            note = f"Branch arm coupling {j}/{len(branch_tokens)} from {anchor}({br.get('branch_text','')}). Verify orthogonal protecting group/order before bench use."
            steps.append(_make_step(step_no, btok, "Branch AA coupling", _profile_for(btok, lookup), depro, wash, rxn, post, 0, 1.0, 0.0, dmf, pip, 0.0, note, inp, overrides, lookup, n + j, 0))
            step_no += 1

    # v3.0.0 hotfix: the editable Plan table must show synthesis units from the
    # user-entered peptide notation only.  Fmoc removal is an operation/checklist
    # not an extra "Fmoc removal" row.
    if parsed.nterm:
        token = parsed.nterm
        rxn = int(rules.get("last_reaction", 1))
        # v3.0.0 label/linker generalization:
        # Any explicit N-terminal chemical, label, cap, or tag is treated as
        # the final coupling/capping unit, similar to an amino-acid coupling row.
        # The editable Plan shows only the real sequence unit. The practical
        # Operation/Checklist flow is:
        #   final Fmoc removal -> DMF wash x6 -> terminal unit reaction
        #   -> last wash: DMF x3 first, then DCM x3.
        # Linkers are kept in the core sequence as AA-like units.
        depro = max(0, int(getattr(inp, "deprotection_count", rules.get("last_depro", 2)) or 0))
        wash = int(rules.get("pre_modifier_dmf_wash_after_depro", 6))
        post = int(rules.get("last_post_dmf_wash", 3))
        dcmx = max(0, int(getattr(inp, "wash_solvent2_count", rules.get("last_dcm_wash", 3)) or 0))
        dmf = vol * (depro * dmf_ratio + wash + rxn + post)
        pip = vol * (depro * pip_ratio)
        dcm = vol * dcmx
        chem = _profile_for(token, lookup)
        if token in {"Ac", "Acetic acid", "Acetyl"}:
            chem = "Ac/capping"
        note = "Final N-terminal chemical/label/tag/cap unit. Linkers are not handled here; linkers remain core AA-like coupling units. Flow: final Fmoc removal -> DMF wash x6 -> terminal chemical reaction -> last wash DMF x3 then DCM x3."
        steps.append(_make_step(step_no, token, "Last / N-term cap", chem, depro, wash, rxn, post, dcmx, 1.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, n+1, 0))
    else:
        # Free N-terminus product: final Fmoc removal and final washes must still
        # be counted.  No reagent row is generated because coupling_repeat=0.
        depro = int(rules.get("last_depro", 2))
        wash = 0
        rxn = 0
        post = int(rules.get("last_post_depro_final_dmf_wash", rules.get("last_post_dmf_wash", 3)))
        dcmx = int(rules.get("last_dcm_wash", 3))
        dmf = vol * (depro * dmf_ratio + post)
        pip = vol * (depro * pip_ratio)
        dcm = vol * dcmx
        note = "Final free N-terminus Fmoc removal -> final DMF wash x3 -> DCM wash x3. No coupling reagent/material amount is counted for this row."
        steps.append(_make_step(step_no, "Fmoc removal", "Final free N-term deprotection", "Final deprotection/wash", depro, wash, rxn, post, dcmx, 0.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, n+1, 0))
    return pd.DataFrame([asdict(s) for s in steps])


def generate_excel_like_synthesis_table(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    m = generate_step_matrix(inp, compounds, rules)
    cols = [
        "step", "synthesis_direction", "sequence_position_from_cterm", "sequence_position_from_nterm", "unit", "phase", "chemistry",
        "protected_reagent", "reagent_class", "reagent_mw", "resin_g", "reagent_eq", "coupling_repeat", "total_reagent_eq",
        "planned_reagent_mmol", "planned_reagent_g", "planned_reagent_mg", "coupling_reagent", "catalyst", "additive", "base", "reaction_solvent",
        "depro_x", "dmf_wash_x", "reaction_x", "post_dmf_wash_x", "dcm_wash_x", "dmf_mL", "piperidine_mL", "dcm_mL", "override_source", "note"
    ]
    return m[[c for c in cols if c in m.columns]].copy()


def generate_detailed_operations(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    matrix = generate_step_matrix(inp, compounds, rules)
    vol = working_volume_mL(inp)
    family = resin_family(inp.resin)
    rules = rules or load_rules()
    solvent_frac, base_frac = deprotection_fractions(inp, rules)
    depro_base = str(getattr(inp, "deprotection_base", "Piperidine") or "Piperidine")
    wash1 = str(getattr(inp, "wash_solvent1", "DMF") or "DMF")
    wash2 = _operator_solvent_name(getattr(inp, "wash_solvent2", "DCM") or "DCM")
    ratio_text = str(getattr(inp, "deprotection_ratio", "20% in DMF") or "20% in DMF")
    rows = []; line = 1
    for matrix_index, (_, s) in enumerate(matrix.iterrows()):
        def add(group, detail, repeat_no, solvent1=0.0, depro_base_ml=0.0, solvent2=0.0, solution="", reagent_g="", solvent1_name="", solvent2_name=""):
            nonlocal line
            rows.append({
                "line": line, "step": int(s.step), "unit": s.unit, "phase": s.phase, "chemistry": s.chemistry,
                "protected_reagent": s.protected_reagent, "reagent_mw": s.reagent_mw,
                "coupling_reagent": s.coupling_reagent, "coupling_reagent_eq": s.coupling_reagent_eq, "coupling_reagent_count": s.coupling_reagent_count,
                "catalyst": s.catalyst, "catalyst_eq": s.catalyst_eq, "catalyst_count": s.catalyst_count, "additive": s.additive,
                "base": s.base, "base_eq": s.base_eq, "base_count": s.base_count,
                "reaction_solvent": s.reaction_solvent, "reagent_eq": s.reagent_eq, "coupling_repeat": s.coupling_repeat,
                "total_reagent_eq": s.total_reagent_eq, "planned_reagent_g": s.planned_reagent_g, "planned_reagent_mg": s.planned_reagent_mg,
                "reagent_eq_source": s.reagent_eq_source, "override_source": s.override_source, "ml_feature_source": s.ml_feature_source,
                "operation_group": group, "operation_detail": detail, "repeat_no": repeat_no, "solution_note": solution, "planned_reagent_g_operation": reagent_g,
                "solvent1_name": solvent1_name or wash1, "solvent1_mL": solvent1, "deprotection_base_name": depro_base, "deprotection_base_mL": depro_base_ml,
                "solvent2_name": solvent2_name or wash2, "solvent2_mL": solvent2,
                # Legacy columns retained for old exports/tests; names come from the connected columns above.
                "dmf_mL": solvent1, "piperidine_mL": depro_base_ml, "dcm_mL": solvent2,
                "status": "To do", "actual_amount": "", "actual_eq": "", "operator_time": "", "note": ""
            }); line += 1
        if str(s.unit).lower() != "fmoc removal":
            add("Reagent/resin", "Prepare resin or reagent", 1, reagent_g=s.planned_reagent_g)
        if s.phase == "Loading" and family == "Amide":
            add("Swell", f"{wash1} swell 1", 1, solvent1=vol, solution=f"{wash1} 100%", solvent1_name=wash1)
        if s.phase == "Loading" and family == "CTC/Trityl":
            add("Swell", f"{wash2} swell 1", 1, solvent2=vol, solution=f"{wash2} 100%", solvent2_name=wash2)
        for i in range(1, int(s.depro_x) + 1):
            add("Deprotection", f"Deprotection {i}", i, solvent1=vol*solvent_frac, depro_base_ml=vol*base_frac, solution=f"{ratio_text}: {depro_base} + {wash1}", solvent1_name=wash1)
        for i in range(1, int(s.dmf_wash_x) + 1):
            add(f"{wash1} wash", f"{wash1} wash after deprotection {i}", i, solvent1=vol, solution=f"{wash1} 100%", solvent1_name=wash1)
        for i in range(1, int(s.reaction_x) + 1):
            sol = f"{s.reaction_solvent}; reagent={s.coupling_reagent} ({s.coupling_reagent_eq} eq x{s.coupling_reagent_count}); catalyst={s.catalyst} ({s.catalyst_eq} eq x{s.catalyst_count}); additive={s.additive}; base={s.base} ({s.base_eq} eq x{s.base_count}); unit_eq={s.reagent_eq}; repeat={s.coupling_repeat}; total_unit_eq={s.total_reagent_eq}"
            if float(s.rxn_dcm_frac) > 0:
                if s.phase == "Loading" and family == "CTC/Trityl":
                    mix1, frac1, mix2, frac2 = _loading_solvent_pair(inp)
                    add("Synthesis/reaction", f"Synthesis / coupling / modifier reaction {i}", i, solvent1=vol*frac1, solvent2=vol*frac2, solution=sol, reagent_g=s.planned_reagent_g/float(s.coupling_repeat or 1), solvent1_name=mix1, solvent2_name=mix2 or wash2)
                else:
                    add("Synthesis/reaction", f"Synthesis / coupling / modifier reaction {i}", i, solvent1=vol*float(s.rxn_dmf_frac), solvent2=vol*float(s.rxn_dcm_frac), solution=sol, reagent_g=s.planned_reagent_g/float(s.coupling_repeat or 1), solvent1_name=str(s.reaction_solvent or wash1), solvent2_name=wash2)
            else:
                add("Synthesis/reaction", f"Synthesis / coupling / modifier reaction {i}", i, solvent1=vol, solution=sol, reagent_g=s.planned_reagent_g/float(s.coupling_repeat or 1), solvent1_name=str(s.reaction_solvent or wash1))
        for i in range(1, int(s.post_dmf_wash_x) + 1):
            add(f"Post {wash1} wash", f"Post/final {wash1} wash {i}", i, solvent1=vol, solution=f"{wash1} 100%", solvent1_name=wash1)
        for i in range(1, int(s.dcm_wash_x) + 1):
            if s.phase != "Loading":
                add(f"{wash2} wash", f"{wash2} wash {i}", i, solvent2=vol, solution=f"{wash2} 100%", solvent2_name=wash2)
        if matrix_index == len(matrix) - 1:
            for i in range(1, max(0, int(getattr(inp, "final_meoh_count", 0) or 0)) + 1):
                add("Final MeOH wash", f"Final MeOH wash {i}", i, solvent1=vol, solution="MeOH 100%", solvent1_name="MeOH")
    return pd.DataFrame(rows)


def generate_step_reagent_plan(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    matrix = generate_step_matrix(inp, compounds, rules)
    cols = ["step", "unit", "phase", "chemistry", "protected_reagent", "reagent_class", "reagent_mw", "coupling_reagent", "coupling_reagent_eq", "coupling_reagent_count", "catalyst", "catalyst_eq", "catalyst_count", "additive", "base", "base_eq", "base_count", "reaction_solvent", "reagent_eq", "coupling_repeat", "total_reagent_eq", "planned_reagent_mmol", "planned_reagent_g", "planned_reagent_mg", "reagent_eq_source", "coupling_repeat_source", "override_source", "ml_feature_source", "deprotection_base_name", "wash_solvent1_name", "wash_solvent2_name", "note"]
    return matrix[[c for c in cols if c in matrix.columns]].copy()


def _generate_materials_core(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    """Generate total raw-material usage for the plan.

    v2.0.2 normalizes this table as real totals instead of silent per-step
    fragments. Step-level details remain available in generate_step_reagent_plan.
    Auxiliary reagents (DIC/HOBt/DIEA/etc.) are calculated from the reagent
    library when MW/density are available; otherwise an explicit warning note is
    emitted in the source column.
    """
    compounds = compounds if compounds is not None else load_compounds()
    lookup = compound_lookup(compounds)
    lib_lookup = reagent_lookup(load_reagent_library())
    rows: list[dict[str, Any]] = []
    family = resin_family(inp.resin)
    resin_g = float(inp.scale_mmol) / float(inp.resin_loading_mmol_g) if inp.resin_loading_mmol_g else 0.0

    agg: dict[tuple, dict[str, Any]] = {}

    def add_agg(material: str, cls: str, reagent: str, planned_mmol: float = 0.0, planned_g: float = 0.0,
                planned_mL: float = 0.0, unit: str = "", source: str = "", mw: float = 0.0,
                density: float = 0.0, warning: str = ""):
        material = _norm_material_name(material)
        if not material:
            return
        cls = str(cls or "").strip()
        reagent = str(reagent or material).strip()
        key = (material.upper(), cls.lower(), reagent.upper())
        if key not in agg:
            agg[key] = {
                "material": material, "class": cls, "reagent": reagent,
                "planned_mmol": 0.0, "planned_g": 0.0, "planned_mg": 0.0, "planned_mL": 0.0,
                "unit": unit or "", "MW": mw or "", "density_g_mL": density or "",
                "source": "", "warning": ""
            }
        rec = agg[key]
        rec["planned_mmol"] += float(planned_mmol or 0.0)
        rec["planned_g"] += float(planned_g or 0.0)
        rec["planned_mg"] = rec["planned_g"] * 1000.0
        rec["planned_mL"] += float(planned_mL or 0.0)
        if unit and not rec.get("unit"):
            rec["unit"] = unit
        if mw and not rec.get("MW"):
            rec["MW"] = mw
        if density and not rec.get("density_g_mL"):
            rec["density_g_mL"] = density
        if source:
            prev = str(rec.get("source", ""))
            rec["source"] = (prev + " | " + source).strip(" |") if prev else source
        if warning:
            prev = str(rec.get("warning", ""))
            rec["warning"] = (prev + " | " + warning).strip(" |") if prev else warning

    add_agg("Resin", resin_family(inp.resin), inp.resin, inp.scale_mmol, resin_g, 0.0, "g", "scale/loading", 0.0, 0.0)

    step_plan = generate_step_reagent_plan(inp, compounds, rules)
    for _, s in step_plan.iterrows():
        unit_token = str(s.get("unit", "")).strip()
        rep = int(float(s.get("coupling_repeat") or 0))
        if unit_token.lower() == "fmoc removal" or rep == 0:
            continue
        total_eq = float(s.get("total_reagent_eq") or s.get("reagent_eq") or inp.coupling_eq or 0.0)
        req_mmol = float(inp.scale_mmol) * total_eq

        row = _row_for(unit_token, lookup)
        unit_mw = _float_row(row, "Reagent MW (g/mol)")
        planned_g = req_mmol * unit_mw / 1000.0 if unit_mw else 0.0
        unit_warning = ""
        unit_density = 0.0
        unit_planned_mL = 0.0
        if unit_token in {"Ac", "Ac2O", "Acetic anhydride", "Acetyl"}:
            unit_density = 1.08
            unit_planned_mL = planned_g / unit_density if planned_g else 0.0
        if not unit_mw and str(row.get("Counts as coupling unit?", "")).strip().lower() != "no":
            unit_warning = f"No reagent MW for {unit_token}; gram amount requires exact reagent/form."
        add_agg(
            unit_token,
            str(row.get("Class", "AA/chemical/linker/tag")),
            str(row.get("Reagent/protected form", unit_token)),
            req_mmol,
            planned_g,
            unit_planned_mL,
            "mL" if unit_planned_mL else "g" if planned_g else "manual" if unit_warning else "g",
            f"step {int(s.step)} unit total_eq={total_eq:g} source={s.get('reagent_eq_source','')}",
            unit_mw,
            unit_density,
            unit_warning,
        )

        aux_items = [
            (s.get("coupling_reagent", ""), "coupling reagent", float(s.get("coupling_reagent_eq") or 0.0), int(float(s.get("coupling_reagent_count") or 0))),
            (s.get("catalyst", ""), "catalyst/additive", float(s.get("catalyst_eq") or 0.0), int(float(s.get("catalyst_count") or 0))),
            (s.get("additive", ""), "additive", total_eq, 1),
            (s.get("base", ""), "base", float(s.get("base_eq") or 0.0), int(float(s.get("base_count") or 0))),
        ]
        protected_name = str(s.get("protected_reagent", "") or "").strip().lower()
        unit_name = str(s.get("unit", "") or "").strip().lower()
        for material, cls, aux_eq, aux_count in aux_items:
            material = _norm_material_name(material)
            material_l = str(material or "").strip().lower()
            if not material or "MANUAL" in material.upper() or "VERIFY" in material.upper():
                continue
            # N-terminal labels/caps often store the actual form in protected_reagent;
            # the unit row already counts that material, so do not duplicate it as an
            # auxiliary coupling reagent.
            if material_l == protected_name or material_l == unit_name:
                continue
            mat_mmol = float(inp.scale_mmol) * float(aux_eq) * max(0, int(aux_count)) * max(1, rep)
            mat_source = f"step {int(s.step)} {s.get('override_source','')} aux_eq={aux_eq:g} count={aux_count} repeat={rep}"
            if family == "CTC/Trityl" and str(s.get("phase", "")).lower() == "loading" and material.upper() in {"DIEA", "DIPEA"}:
                load_base_eq = float(getattr(inp, "loading_diea_eq", 4.0) or 4.0)
                mat_mmol = float(inp.scale_mmol) * load_base_eq
                mat_source = f"step {int(s.step)} trityl loading base eq={load_base_eq:g} resin:AA:DIEA=1:{float(getattr(inp, 'loading_aa_eq', 2.0) or 2.0):g}:{load_base_eq:g}"
            g, mL, mw, density, warn = _mass_volume_from_library(material, mat_mmol, lib_lookup)
            unit = "g/mL" if g and mL else "g" if g else "manual"
            add_agg(material, cls, material, mat_mmol, g, mL, unit, mat_source, mw, density, warn)

    rows.extend(agg.values())
    ops = generate_detailed_operations(inp, compounds, rules)
    solvent_rows = []
    if not ops.empty:
        for name_col, vol_col, cls in [("solvent1_name", "solvent1_mL", "solvent"), ("deprotection_base_name", "deprotection_base_mL", "deprotection base"), ("solvent2_name", "solvent2_mL", "solvent")]:
            if name_col not in ops.columns or vol_col not in ops.columns:
                continue
            grouped = ops.groupby(ops[name_col].fillna('').astype(str).str.strip(), dropna=False)[vol_col].sum()
            for material, amount in grouped.items():
                if not material or float(amount or 0.0) <= 0:
                    continue
                # The stepwise checklist keeps the established operator label
                # MC/DCM, while the total-material table retains the historical
                # DCM row used by old exports and inventory matching.
                total_material = "DCM" if str(material).strip().upper() == "MC/DCM" else str(material).strip()
                info = lib_lookup.get(total_material.lower(), lib_lookup.get(str(material).strip().lower(), {}))
                solvent_rows.append({"material": total_material, "class": cls, "reagent": total_material, "planned_mmol": 0.0, "planned_g": 0.0, "planned_mg": 0.0, "planned_mL": float(amount), "unit": "mL", "MW": info.get("MW", ""), "density_g_mL": info.get("Density", ""), "physical_state": "solution" if cls == "deprotection base" else "liquid", "source": "operation total from connected setup conditions", "warning": ""})
    rows.extend(solvent_rows)
    # Add cleavage cocktail components directly to raw material use.  This removes
    # the old conflicting standalone TFA reserve/suggestion row.
    try:
        cocktail = generate_cleavage_cocktail(inp)
        for _, cr in cocktail.iterrows():
            if str(cr.get("include", "")).upper() != "YES" or str(cr.get("component", "")) == "Total cocktail":
                continue
            comp = str(cr.get("component", "")).strip()
            state = str(cr.get("physical_state", "")).strip()
            vol = _float_any(cr.get("volume_mL", 0.0))
            grams = _float_any(cr.get("approx_g", 0.0))
            density = _float_any(cr.get("density_g_mL", 0.0))
            is_liquid = state in {"liquid", "solution"} or comp in {"TFA", "TIS", "EDT", "DW / water", "Thioanisole", "Anisole", "DMS", "DMSO", "Triethylsilane"}
            rows.append({
                "material": f"{comp} - cleavage cocktail component",
                "class": "cleavage cocktail component",
                "reagent": comp,
                "planned_mmol": 0.0,
                "planned_g": 0.0 if is_liquid else grams,
                "planned_mg": 0.0 if is_liquid else grams * 1000.0,
                "planned_mL": vol if is_liquid else 0.0,
                "unit": "mL" if is_liquid else "g",
                "MW": "",
                "density_g_mL": density or "",
                "physical_state": state,
                "source": f"cleavage cocktail preset={cr.get('selected_preset','')}; eq={cr.get('recommended_eq','')}",
                "warning": "Cocktail component from dedicated cleavage calculator; prepare fresh and verify SOP.",
            })
    except Exception as e:
        rows.append({"material": "Cleavage cocktail", "class": "cleavage", "reagent": "manual", "planned_mmol": 0.0, "planned_g": 0.0, "planned_mg": 0.0, "planned_mL": 0.0, "unit": "manual", "MW": "", "density_g_mL": "", "physical_state": "", "source": "cleavage cocktail generation failed", "warning": str(e)})
    df = pd.DataFrame(rows)
    df = _liquid_display_policy(df)
    preferred = ["material", "class", "reagent", "planned_mmol", "planned_g", "planned_mg", "planned_mL", "unit", "MW", "density_g_mL", "physical_state", "source", "warning"]
    return df[[c for c in preferred if c in df.columns]].copy()

def generate_ml_ready_log(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    matrix = generate_step_matrix(inp, compounds, rules); parsed = parse_sequence(inp.sequence); rows = []
    for _, s in matrix.iterrows():
        rows.append({
            "sequence": inp.sequence, "core_sequence": parsed.core, "core_tokens": "|".join(parsed.core_tokens), "nterm_modifier": parsed.nterm, "cterm_text": parsed.cterm_text,
            "resin": inp.resin, "resin_family": resin_family(inp.resin), "scale_mmol": inp.scale_mmol, "resin_loading_mmol_g": inp.resin_loading_mmol_g, "resin_g": s.resin_g,
            "step": int(s.step), "unit": s.unit, "phase": s.phase, "chemistry": s.chemistry, "protected_reagent": s.protected_reagent, "reagent_class": s.reagent_class,
            "coupling_reagent": s.coupling_reagent, "catalyst": s.catalyst, "additive": s.additive, "base": s.base, "reaction_solvent": s.reaction_solvent,
            "planned_reagent_eq": s.reagent_eq, "coupling_repeat": s.coupling_repeat, "total_reagent_eq": s.total_reagent_eq, "planned_reagent_mmol": s.planned_reagent_mmol, "planned_reagent_g": s.planned_reagent_g,
            "reagent_eq_source": s.reagent_eq_source, "override_source": s.override_source, "actual_reagent_eq": "", "actual_coupling_repeat": "", "actual_yield": "", "purity": "", "lcms_result": "", "hplc_method": "", "operator_note": "",
        })
    return pd.DataFrame(rows)



def generate_printable_checklist(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    """Generate a concise printable checklist for bench use.

    The checklist is intentionally simple: amino acid/modifier name, eq, amount, coupling system,
    repeat, date, checked, and note fields. It is suitable for printing and filling in during synthesis.
    """
    plan = generate_step_reagent_plan(inp, compounds, rules)
    rows = []
    for _, s in plan.iterrows():
        rows.append({
            "No": int(s.get("step", 0)),
            "AA/Chemical/label/tag/linker": s.get("unit", ""),
            "Protected reagent / form": s.get("protected_reagent", ""),
            "eq": s.get("reagent_eq", ""),
            "total eq": s.get("total_reagent_eq", ""),
            "amount(g)": s.get("planned_reagent_g", ""),
            "Coupling system": _format_coupling_system(s.get('coupling_reagent',''), s.get('catalyst',''), s.get('base','')),
            "Repeat": s.get("coupling_repeat", ""),
            "Date": "",
            "Checked": "No",
            "Note": "",
        })
    return pd.DataFrame(rows)

def _plan_summary_initial(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> dict:
    matrix = generate_step_matrix(inp, compounds, rules); parsed = parse_sequence(inp.sequence); materials = generate_materials(inp, compounds, rules)
    product_mw = 0.0; lookup = compound_lookup(compounds if compounds is not None else load_compounds())
    for token in (parsed.core_tokens or list(parsed.core)) + list(getattr(parsed, "branch_tokens", []) or []) + ([parsed.nterm] if parsed.nterm else []):
        product_mw += _float_row(_row_for(token, lookup), "Product MW contribution (g/mol)")
    product_mw += 17.03 if cterm_output(inp.resin).startswith("CONH2") else 18.02
    effective_eq, effective_eq_source = _resolve_coupling_eq(inp, len(parsed.core_tokens or list(parsed.core)) + len(getattr(parsed, "branch_tokens", []) or []))
    warnings = list(getattr(parsed, "warnings", []) or []) + _cterm_resin_warnings(parsed, inp.resin)
    cleavage = cleavage_eq_suggestion(inp)
    cocktail = generate_cleavage_cocktail(inp)
    try:
        cocktail_total_mL = float(cocktail[cocktail["component"].eq("Total cocktail")]["volume_mL"].iloc[0])
    except Exception:
        cocktail_total_mL = 0.0
    return {"sequence": inp.sequence, "nterm": parsed.nterm, "core": parsed.core, "core_tokens": "|".join(parsed.core_tokens), "branch_tokens": "|".join(getattr(parsed, "branch_tokens", []) or []), "branch_count": len(getattr(parsed, "branch_sites", []) or []), "warnings": " ; ".join(warnings), "cterm_text": parsed.cterm_text, "resin_family": resin_family(inp.resin), "cterm_output": cterm_output(inp.resin), "resin_g": inp.scale_mmol / inp.resin_loading_mmol_g if inp.resin_loading_mmol_g else 0.0, "operation_volume_mL": working_volume_mL(inp), "default_aa_coupling_eq": effective_eq, "aa_coupling_eq_source": effective_eq_source, "default_modifier_eq": inp.ac_eq, "default_coupling_repeats": inp.default_coupling_repeats, "default_modifier_repeats": inp.default_modifier_repeats, "default_coupling_system": _normalized_default_coupling_system(inp), "default_reagent_eq": inp.default_reagent_eq, "default_reagent_count": inp.default_reagent_count, "default_catalyst_eq": inp.default_catalyst_eq, "default_catalyst_count": inp.default_catalyst_count, "default_base_eq": inp.default_base_eq, "default_base_count": inp.default_base_count, "reagent_eq_follows_coupling_eq": inp.reagent_eq_follows_coupling_eq, "solvent_volume_mode": inp.solvent_volume_mode, "amide_ml_per_mmol": inp.amide_ml_per_mmol, "ctc_ml_per_mmol": inp.ctc_ml_per_mmol, "solvent_molarity_m": inp.solvent_molarity_m, "deprotection_condition": f"{inp.deprotection_base} / {inp.deprotection_ratio} x{inp.deprotection_count}", "cleavage_eq_suggestion": cleavage.get("cleavage_eq"), "cleavage_eq_source": cleavage.get("source"), "cleavage_auto_recommended_preset": recommend_cleavage_preset(inp).get("preset"), "cleavage_auto_reason": recommend_cleavage_preset(inp).get("reason"), "cleavage_tfa_mL_neat_equiv": cleavage.get("tfa_mL_neat_equiv"), "cleavage_cocktail_total_mL": cocktail_total_mL, "dmf_mL": float(matrix["dmf_mL"].sum()), "piperidine_mL": float(matrix["piperidine_mL"].sum()), "dcm_mL": float(matrix["dcm_mL"].sum()), "manual_override_count": int((matrix.get("override_source", "") != "default").sum()) if "override_source" in matrix.columns else 0, "product_mw": product_mw, "mh": product_mw + 1.0073, "mna": product_mw + 22.9898, "materials_count": int(len(materials))}


# ======================= V2.1.7 BENCH-ACCURATE CLEAVAGE + STEP MATERIALS =======================
# User-confirmed correction: cleavage cocktail "eq" is used as a bench volume
# planning rule, not as a neat-TFA molar equivalent.  For 2-CTC/Trityl plans the
# lab rule uses scale/2 * eq mL total cocktail; for amide/Rink plans it uses
# scale * eq mL total cocktail.  Example checks:
#   GHK, 1000 mmol, 2-CTC, 18 eq -> 9000 mL total = 8550 mL TFA + 450 mL water for 95/5

_CLEAVAGE_COMPONENT_INFO.update({
    "AcOH": {"role": "mild acid", "density": 1.049, "state": "liquid"},
    "TFE": {"role": "mild cleavage co-solvent", "density": 1.39, "state": "liquid"},
    "TEE": {"role": "mild cleavage co-solvent", "density": 1.39, "state": "liquid", "canonical": "TFE"},
    "MC/DCM": {"role": "methylene chloride solvent", "density": 1.325, "state": "liquid"},
    "DCM": {"role": "methylene chloride solvent", "density": 1.325, "state": "liquid", "canonical": "MC/DCM"},
    "MC": {"role": "methylene chloride solvent", "density": 1.325, "state": "liquid", "canonical": "MC/DCM"},
})


def _canonical_cleavage_component(name: str) -> str:
    raw = str(name or "").strip()
    key = re.sub(r"[^A-Za-z0-9]+", "", raw).upper()
    aliases = {
        "H2O": "DW / water", "WATER": "DW / water", "DW": "DW / water", "DIWATER": "DW / water",
        "TIPS": "TIS", "TRIISOPROPYLSILANE": "TIS", "TIS": "TIS",
        "TES": "Triethylsilane", "TRIETHYLSILANE": "Triethylsilane",
        "TEE": "TFE", "TFE": "TFE", "TRIFLUOROETHANOL": "TFE", "222TRIFLUOROETHANOL": "TFE",
        "MC": "MC/DCM", "DCM": "MC/DCM", "METHYLENECHLORIDE": "MC/DCM", "DICHLOROMETHANE": "MC/DCM",
        "ACOH": "AcOH", "ACETICACID": "AcOH",
        "ETHANEDITHIOL": "EDT", "12ETHANEDITHIOL": "EDT", "EDT": "EDT",
        "THIOANISOL": "Thioanisole", "THIOANISOLE": "Thioanisole",
        "DIMETHYLSULFIDE": "DMS", "DMS": "DMS", "DIMETHYLSULFOXIDE": "DMSO", "DMSO": "DMSO",
        "PHENOL": "Phenol", "DTT": "DTT", "AMMONIUMIODIDE": "Ammonium iodide", "NH4I": "Ammonium iodide",
        "ANISOLE": "Anisole", "DMB": "DMB", "DIMETHOXYBENZENE": "DMB", "PCRESOL": "p-Cresol",
        "TFA": "TFA",
    }
    return aliases.get(key, raw)


def cleavage_cocktail_presets() -> pd.DataFrame:
    rows = [
        {"preset": "AUTO", "components": "<sequence recommendation>", "recommended_for": "Automatically choose a preset from residue composition", "source_note": "Planner rule: Cys/Met/Trp/Tyr and resin family drive recommendation"},
        {"preset": "DEFAULT_TFA_WATER", "components": "TFA=95;Water=5", "recommended_for": "Simple short peptides and GHK-style basic cleavage planning", "source_note": "User-confirmed 95/5 TFA/water option"},
        {"preset": "DEFAULT_TFA_TIS_WATER", "components": "TFA=95;TIS=2.5;Water=2.5", "recommended_for": "Standard non-sensitive Fmoc/Rink Amide cases", "source_note": "Common 95:2.5:2.5 TFA/TIS/water"},
        {"preset": "TFA_TIS_WATER_96_2_2", "components": "TFA=96;TIS=2;Water=2", "recommended_for": "Simple standard peptides; compact 96/2/2 option", "source_note": "Common TFA/TIS/H2O 96/2/2 variant"},
        {"preset": "TFA_MC_1_1", "components": "TFA=50;MC=50", "recommended_for": "TFA/MC 1:1 cleavage option", "source_note": "User-requested MC:TFA=1:1 option"},
        {"preset": "ACOH_TFE_MC_1_1_8", "components": "AcOH=10;TFE=10;MC=80", "recommended_for": "Mild 2-CTC cleavage/check cleavage; AcOH/TFE/MC 1:1:8", "source_note": "User-requested AcOH/TFE(or TEE)/MC option"},
        {"preset": "ACOH_TFE_MC_2_2_6", "components": "AcOH=20;TFE=20;MC=60", "recommended_for": "Stronger mild-acid 2-CTC cleavage variant", "source_note": "AcOH/TFE/MC 2:2:6 variant"},
        {"preset": "REDUCING_TFA_TIS_WATER_EDT", "components": "TFA=94;TIS=1;Water=2.5;EDT=2.5", "recommended_for": "Most peptides containing Trp, Cys, or Met", "source_note": "Reducing mix 94/1/2.5/2.5"},
        {"preset": "CYS_EDT", "components": "TFA=92.5;TIS=2.5;Water=2.5;EDT=2.5", "recommended_for": "Cys/thiol-sensitive peptides; EDT-containing option", "source_note": "TFA/TIS/water + EDT variant"},
        {"preset": "REAGENT_B", "components": "TFA=88;Phenol=5.8;TIS=2;Water=4.2", "recommended_for": "Trityl/scavenging-heavy but lower-odor option; not sufficient alone for some Cys/Met cases", "source_note": "Reagent B: TFA/phenol/TIS/water"},
        {"preset": "REAGENT_K", "components": "TFA=82.5;Phenol=5;Water=5;Thioanisole=5;EDT=2.5", "recommended_for": "Sensitive residues such as Cys/Met/Trp/Tyr; broad general cleavage reagent", "source_note": "Reagent K"},
        {"preset": "REAGENT_L", "components": "TFA=88;TIS=2;DTT=5;Water=5", "recommended_for": "Low-odor/reducing option; Met oxidation-sensitive cases", "source_note": "Reagent L"},
        {"preset": "REAGENT_R", "components": "TFA=90;Thioanisole=5;Anisole=3;EDT=2", "recommended_for": "Arg(Pmc/Mtr)-type or strong scavenger cases", "source_note": "Reagent R"},
        {"preset": "REAGENT_H", "components": "TFA=81;Phenol=5;Thioanisole=5;EDT=2.5;Water=3;DMS=2;Ammonium iodide=1.5", "recommended_for": "Methionine oxidation suppression", "source_note": "Reagent H"},
        {"preset": "REAGENT_I", "components": "TFA=92.5;TIS=2.5;DMB=5", "recommended_for": "Rink amide linker decomposition mitigation", "source_note": "Reagent I"},
        {"preset": "TFA_WATER_TIS_EDT", "components": "TFA=90;Water=5;TIS=2.5;EDT=2.5", "recommended_for": "Cys-containing alternatives when extra water scavenging is desired", "source_note": "Practical EDT/water/TIS variant"},
        {"preset": "TFA_THIOANISOLE_EDT_ANISOLE", "components": "TFA=90;Thioanisole=5;EDT=3;Anisole=2", "recommended_for": "Strong cation scavenging; aromatic/thioether-rich sequences", "source_note": "Practical strong-scavenger variant"},
        {"preset": "TFA_TIS_P_CRESOL_WATER", "components": "TFA=90;TIS=2.5;p-Cresol=5;Water=2.5", "recommended_for": "Tyr/Trp-rich sequences where phenolic scavenger is desired", "source_note": "p-cresol/phenolic scavenger variant"},
        {"preset": "LOW_TFA_2CTC_TEST", "components": "TFA=1;MC=99", "recommended_for": "2-CTC mild acid test cleavage only; not full global deprotection", "source_note": "2-CTC mild acid test cleavage only; not for full global deprotection. Verify resin/protecting groups."},
    ]
    return pd.DataFrame(rows)


def _preset_components(name: str) -> dict[str, float]:
    key = re.sub(r"[^A-Za-z0-9]+", "_", str(name or "").strip().upper()).strip("_")
    if not key or key == "AUTO":
        key = "DEFAULT_TFA_TIS_WATER"
    presets = cleavage_cocktail_presets()
    for _, row in presets.iterrows():
        if re.sub(r"[^A-Za-z0-9]+", "_", str(row.get("preset", "")).upper()).strip("_") == key:
            return _parse_cleavage_components_text(str(row.get("components", "")))
    return _parse_cleavage_components_text(str(name or "")) or _parse_cleavage_components_text("TFA=95;TIS=2.5;Water=2.5")


def _cleavage_volume_factor(inp: PlanInput) -> float:
    return 0.5 if resin_family(getattr(inp, "resin", "")) == "CTC/Trityl" else 1.0


def generate_cleavage_cocktail(inp: PlanInput) -> pd.DataFrame:
    sug = cleavage_eq_suggestion(inp)
    comps = _selected_cleavage_components(inp)
    if not comps:
        comps = _parse_cleavage_components_text("TFA=95;TIS=2.5;Water=2.5")
    pct_sum = sum(max(0.0, float(v or 0.0)) for v in comps.values())
    if pct_sum <= 0:
        comps = _parse_cleavage_components_text("TFA=95;TIS=2.5;Water=2.5")
        pct_sum = 100.0
    selected_preset = _selected_cleavage_preset_name(inp)
    rec = recommend_cleavage_preset(inp)
    eq = float(sug.get("cleavage_eq", 0.0) or 0.0)
    scale = float(getattr(inp, "scale_mmol", 0.0) or 0.0)
    factor = _cleavage_volume_factor(inp)
    total_mL = scale * eq * factor
    reserve = float(getattr(inp, "cleavage_reserve_mL", 0.0) or 0.0)
    if reserve > 0:
        total_mL = max(total_mL, reserve)
    rows = []
    for name, raw_pct in comps.items():
        name = _canonical_cleavage_component(name)
        pct_norm = max(0.0, float(raw_pct or 0.0)) / pct_sum * 100.0
        if pct_norm <= 0:
            continue
        info = dict(_CLEAVAGE_COMPONENT_INFO.get(name, {}))
        canon = info.get("canonical")
        if canon:
            name = str(canon)
            info = dict(_CLEAVAGE_COMPONENT_INFO.get(name, info))
        density = float(info.get("density") or 0.0)
        state = str(info.get("state") or "liquid")
        vol = total_mL * pct_norm / 100.0
        approx_g = ""
        vol_out: float | str = round(vol, 6)
        if density and state in {"liquid", "solution", "liquid_or_solid", "solid_or_melt"}:
            # Keep grams for cleavage cocktail reference only; operator materials
            # use mL-only for liquid/solution rows.
            approx_g = round(vol * density, 6)
        elif state == "solid_wv":
            approx_g = round(total_mL * pct_norm / 100.0, 6)
            vol_out = ""
        rows.append({
            "component": name,
            "role": info.get("role", "scavenger/solvent"),
            "recommended_eq": eq if name == "TFA" else "",
            "percent": round(pct_norm, 3),
            "percent_basis": "v/v" if state not in {"solid_wv"} else "approx w/v",
            "volume_mL": vol_out,
            "density_g_mL": density or "",
            "approx_g": approx_g,
            "physical_state": state,
            "selected_preset": selected_preset,
            "auto_recommended_preset": rec.get("preset", ""),
            "include": "YES",
            "note": (f"Bench volume basis: scale_mmol x eq x resin_factor={factor:g}; source={sug.get('source')}; length={sug.get('length_tokens')}; Cys={sug.get('cys_count')}." + (f" Cleavage time={float(getattr(inp, 'cleavage_time_h', 0.0) or 0.0):g} h." if float(getattr(inp, 'cleavage_time_h', 0.0) or 0.0) > 0 else "") if name == "TFA" else "Included by selected/custom cleavage cocktail preset."),
        })
    rows.append({
        "component": "Total cocktail", "role": "total", "recommended_eq": eq, "percent": 100.0,
        "percent_basis": f"scale_mmol x eq x resin_factor({factor:g})", "volume_mL": round(total_mL, 6), "density_g_mL": "", "approx_g": "", "physical_state": "mixture",
        "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "YES",
        "note": f"Preset={selected_preset}; requested={getattr(inp, 'cleavage_preset', 'AUTO') or 'AUTO'}; custom={bool(str(getattr(inp, 'cleavage_components_text', '') or '').strip())}." + (f" Cleavage time={float(getattr(inp, 'cleavage_time_h', 0.0) or 0.0):g} h." if float(getattr(inp, 'cleavage_time_h', 0.0) or 0.0) > 0 else "") + " Use SOP/protecting-group check before bench use.",
    })
    if int(float(sug.get("cys_count", 0) or 0)) > 0:
        rows.append({"component": "Cys warning", "role": "manual check", "recommended_eq": "", "percent": "", "percent_basis": "", "volume_mL": "", "density_g_mL": "", "approx_g": "", "physical_state": "", "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "INFO", "note": "Cys detected: planner adds +100 eq per Cys. EDT/thioanisole/TIS/water selection should be confirmed by lab SOP."})
    if resin_family(inp.resin) == "CTC/Trityl":
        rows.append({"component": "2-CTC/Trityl warning", "role": "manual check", "recommended_eq": "", "percent": "", "percent_basis": "", "volume_mL": "", "density_g_mL": "", "approx_g": "", "physical_state": "", "selected_preset": selected_preset, "auto_recommended_preset": rec.get("preset", ""), "include": "INFO", "note": "2-CTC/Trityl uses scale/2 x eq mL volume basis in this planner. Confirm cleavage cocktail/protecting groups by SOP."})
    return pd.DataFrame(rows)


def _as_display_number(v: Any, digits: int = 6) -> Any:
    try:
        f = float(v or 0.0)
        if abs(f) < 1e-12:
            return ""
        return round(f, digits)
    except Exception:
        return v if v is not None else ""


def _step_material_row(step: Any, material: str, cls: str, mw: Any = "", density: Any = "", mmol: float = 0.0, g: float = 0.0, mL: float = 0.0, use_count: Any = "", repeat: Any = "", phase: str = "", note: str = "", source: str = "", state: str = "") -> dict[str, Any]:
    liquid = str(state).lower() in {"liquid", "solution"} or str(material).strip().lower().split(" -")[0] in {"dic", "diea", "dipea", "dmf", "dcm", "mc/dcm", "mc", "tfa", "tis", "edt", "acoh", "tfe", "piperidine", "water", "dw / water"}
    return {
        "step": step,
        "material": material,
        "class": cls,
        "MW": mw if mw not in (0, 0.0, None) else "",
        "density_g_mL": density if density not in (0, 0.0, None) else "",
        "planned_mmol": _as_display_number(mmol),
        "planned_g": "" if liquid else _as_display_number(g),
        "planned_mL": _as_display_number(mL),
        "unit": "mL" if liquid else "g" if g else "manual" if not mL else "mL",
        "use_count": use_count,
        "repeat": repeat,
        "phase": phase,
        "note": note,
        "source": source,
    }


def _generate_step_materials_core(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    """Operator-facing, step-by-step material table.

    This is intentionally different from generate_materials(): Selected Materials
    should follow synthesis/checklist order by step, while Selected Total Materials
    is the aggregated preparation/purchasing total.
    """
    compounds = compounds if compounds is not None else load_compounds()
    lookup = compound_lookup(compounds)
    lib_lookup = reagent_lookup(load_reagent_library())
    rows: list[dict[str, Any]] = []
    family = resin_family(inp.resin)
    resin_g = float(inp.scale_mmol or 0.0) / float(inp.resin_loading_mmol_g or 1.0)
    rows.append(_step_material_row("resin", inp.resin, "Resin", mmol=inp.scale_mmol, g=resin_g, phase="resin", note=f"Resin loading {inp.resin_loading_mmol_g:g} mmol/g; scale {inp.scale_mmol:g} mmol", source="scale/loading"))
    step_plan = generate_step_reagent_plan(inp, compounds, rules)
    for _, s in step_plan.iterrows():
        step = int(float(s.get("step") or 0))
        unit_token = str(s.get("unit", "")).strip()
        phase = str(s.get("phase", "")).strip()
        rep = int(float(s.get("coupling_repeat") or 0))
        req_mmol = float(s.get("planned_reagent_mmol") or 0.0)
        # Unit material row
        if unit_token and unit_token.lower() != "fmoc removal" and rep > 0:
            rows.append(_step_material_row(
                step, str(s.get("protected_reagent") or unit_token), str(s.get("reagent_class") or "AA/Chemical"),
                mw=s.get("reagent_mw", ""), mmol=req_mmol, g=float(s.get("planned_reagent_g") or 0.0),
                use_count=1, repeat=rep, phase=phase, note=f"{unit_token} / {s.get('total_reagent_eq', '')} eq", source=f"step {step}; unit"
            ))
        # Auxiliary coupling reagents / base
        total_eq = float(s.get("total_reagent_eq") or 0.0)
        aux = [
            (s.get("coupling_reagent", ""), "Coupling reagent", float(s.get("coupling_reagent_eq") or 0.0), int(float(s.get("coupling_reagent_count") or 0))),
            (s.get("catalyst", ""), "Catalyst/additive", float(s.get("catalyst_eq") or 0.0), int(float(s.get("catalyst_count") or 0))),
            (s.get("additive", ""), "Additive", total_eq, 1),
            (s.get("base", ""), "Base", float(s.get("base_eq") or 0.0), int(float(s.get("base_count") or 0))),
        ]
        for material, cls, aux_eq, aux_count in aux:
            material = _norm_material_name(material)
            if not material or material.upper() in {"N/A", "MANUAL"} or "VERIFY" in material.upper():
                continue
            mat_mmol = float(inp.scale_mmol or 0.0) * float(aux_eq) * max(0, int(aux_count)) * max(1, rep)
            note = f"{material} from step {step}; {aux_eq:g} eq x count {aux_count} x repeat {rep}"
            if family == "CTC/Trityl" and phase.lower() == "loading" and material.upper() in {"DIEA", "DIPEA"}:
                mat_mmol = float(inp.scale_mmol or 0.0) * float(getattr(inp, "loading_diea_eq", 4.0) or 4.0)
                note = f"2-CTC loading base; DIEA {float(getattr(inp, 'loading_diea_eq', 4.0) or 4.0):g} eq"
            g, mL, mw, density, warn = _mass_volume_from_library(material, mat_mmol, lib_lookup)
            state = "liquid" if mL else "solid"
            rows.append(_step_material_row(step, material, cls, mw=mw, density=density, mmol=mat_mmol, g=g, mL=mL, use_count=1, repeat=rep, phase=phase, note=note + (("; " + warn) if warn else ""), source=f"step {step}; aux", state=state))
    # Operation solvents in true checklist order.
    ops = generate_detailed_operations(inp, compounds, rules)
    for _, op in ops.iterrows():
        step = int(float(op.get("step") or 0)) if str(op.get("step", "")).strip() else "operation"
        group = str(op.get("operation_group", ""))
        detail = str(op.get("operation_detail", ""))
        rep = op.get("repeat_no", "")
        if float(op.get("solvent1_mL", op.get("dmf_mL", 0.0)) or 0.0):
            rows.append(_step_material_row(step, str(op.get("solvent1_name") or getattr(inp, "wash_solvent1", "DMF")), "Reaction/wash solvent 1", mL=float(op.get("solvent1_mL", op.get("dmf_mL", 0.0)) or 0.0), use_count=1, repeat=rep, phase=group, note=detail, source="operation solvent", state="liquid"))
        if float(op.get("deprotection_base_mL", op.get("piperidine_mL", 0.0)) or 0.0):
            rows.append(_step_material_row(step, str(op.get("deprotection_base_name") or getattr(inp, "deprotection_base", "Piperidine")), "Deprotection base", mL=float(op.get("deprotection_base_mL", op.get("piperidine_mL", 0.0)) or 0.0), use_count=1, repeat=rep, phase=group, note=str(getattr(inp, "deprotection_ratio", "20% in DMF")), source="operation solvent", state="solution"))
        if float(op.get("solvent2_mL", op.get("dcm_mL", 0.0)) or 0.0):
            rows.append(_step_material_row(step, str(op.get("solvent2_name") or getattr(inp, "wash_solvent2", "DCM")), "Reaction/wash solvent 2", mL=float(op.get("solvent2_mL", op.get("dcm_mL", 0.0)) or 0.0), use_count=1, repeat=rep, phase=group, note=detail, source="operation solvent", state="liquid"))
    # Cleavage cocktail components at the end of the actual procedure.
    try:
        cocktail = generate_cleavage_cocktail(inp)
        for _, cr in cocktail.iterrows():
            if str(cr.get("include", "")).upper() != "YES" or str(cr.get("component", "")) == "Total cocktail":
                continue
            rows.append(_step_material_row("cleavage", str(cr.get("component", "")), "Cleavage cocktail component", density=cr.get("density_g_mL", ""), mL=float(cr.get("volume_mL") or 0.0), phase="cleavage", note=str(cr.get("note", "")), source=f"cocktail preset={cr.get('selected_preset','')}", state=str(cr.get("physical_state", ""))))
    except Exception as e:
        rows.append(_step_material_row("cleavage", "Cleavage cocktail", "manual check", phase="cleavage", note=str(e), source="cleavage generation failed"))
    cols = ["step", "material", "class", "MW", "density_g_mL", "planned_mmol", "planned_g", "planned_mL", "unit", "use_count", "repeat", "phase", "note", "source"]
    return pd.DataFrame(rows, columns=cols)
# ======================= END V2.1.7 BENCH-ACCURATE CLEAVAGE + STEP MATERIALS =======================

# ======================= V2.1.7 AUTO CLEAVAGE RECOMMENDATION REPAIR =======================
def recommend_cleavage_preset(inp: PlanInput | str) -> dict[str, Any]:
    seq = inp.sequence if hasattr(inp, "sequence") else str(inp or "")
    resin = inp.resin if hasattr(inp, "resin") else "Amide"
    parsed = parse_sequence(seq)
    tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
    key = _sequence_key_for_cleavage(seq)
    aas = [str(t).replace("d", "").upper() for t in tokens]
    counts = {aa: aas.count(aa) for aa in sorted(set(aas))}
    if key in {"GHK", "GHK-NH2", "GHK-CONH2"}:
        return {"preset": "DEFAULT_TFA_WATER", "reason": "Confirmed GHK contract: 18 eq with TFA/water 95/5."}
    if key in {"AC-EEMQRR-NH2", "AC-EEMQRR-CONH2"}:
        return {"preset": "DEFAULT_TFA_WATER", "reason": "Confirmed Ac-EEMQRR-NH2 contract: 30 eq with 95% TFA / 5% DW; no TIS."}
    if counts.get("C", 0) and any(counts.get(x, 0) for x in ("M", "W", "Y")):
        return {"preset": "REAGENT_K", "reason": "Cys plus Met/Trp/Tyr detected; broad sensitive-residue scavenger mix recommended."}
    if counts.get("C", 0):
        return {"preset": "CYS_EDT", "reason": "Cys detected; EDT/TIS/water-containing cocktail recommended for thiol-sensitive cases."}
    if counts.get("M", 0):
        return {"preset": "REAGENT_H", "reason": "Met detected; Reagent H is shown as the methionine-oxidation-suppression route and still requires SOP review."}
    if counts.get("W", 0):
        return {"preset": "REDUCING_TFA_TIS_WATER_EDT", "reason": "Trp detected; a reducing EDT-containing mixture is shown and requires SOP review."}
    if counts.get("Y", 0):
        return {"preset": "REAGENT_B", "reason": "Tyr detected; phenolic/scavenger-rich option suggested."}
    if resin_family(resin) == "CTC/Trityl":
        return {"preset": "ACOH_TFE_MC_1_1_8", "reason": "2-CTC/Trityl resin detected; mild AcOH/TFE/MC option shown, confirm full deprotection by SOP."}
    return {"preset": "DEFAULT_TFA_TIS_WATER", "reason": "No special sensitivity trigger detected; standard TFA/TIS/water preset selected."}
# ======================= END V2.1.7 AUTO CLEAVAGE RECOMMENDATION REPAIR =======================

# ======================= V2.1.7 SUMMARY CLEAVAGE LABEL REPAIR =======================
def plan_summary(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> dict:
    matrix = generate_step_matrix(inp, compounds, rules)
    parsed = parse_sequence(inp.sequence)
    materials = generate_materials(inp, compounds, rules)
    product_mw = 0.0
    lookup = compound_lookup(compounds if compounds is not None else load_compounds())
    for token in (parsed.core_tokens or list(parsed.core)) + list(getattr(parsed, "branch_tokens", []) or []) + ([parsed.nterm] if parsed.nterm else []):
        product_mw += _float_row(_row_for(token, lookup), "Product MW contribution (g/mol)")
    product_mw += 17.03 if cterm_output(inp.resin).startswith("CONH2") else 18.02
    effective_eq, effective_eq_source = _resolve_coupling_eq(inp, len(parsed.core_tokens or list(parsed.core)) + len(getattr(parsed, "branch_tokens", []) or []))
    warnings = list(getattr(parsed, "warnings", []) or []) + _cterm_resin_warnings(parsed, inp.resin)
    cleavage = cleavage_eq_suggestion(inp)
    cocktail = generate_cleavage_cocktail(inp)
    def _component_mL(name):
        try:
            row = cocktail[cocktail["component"].astype(str).str.upper().eq(name.upper())]
            return float(row["volume_mL"].iloc[0]) if len(row) else 0.0
        except Exception:
            return 0.0
    try:
        cocktail_total_mL = float(cocktail[cocktail["component"].eq("Total cocktail")]["volume_mL"].iloc[0])
    except Exception:
        cocktail_total_mL = 0.0
    return {
        "sequence": inp.sequence, "nterm": parsed.nterm, "core": parsed.core, "core_tokens": "|".join(parsed.core_tokens),
        "branch_tokens": "|".join(getattr(parsed, "branch_tokens", []) or []), "branch_count": len(getattr(parsed, "branch_sites", []) or []),
        "warnings": " ; ".join(warnings), "cterm_text": parsed.cterm_text, "resin_family": resin_family(inp.resin), "cterm_output": cterm_output(inp.resin),
        "resin_g": inp.scale_mmol / inp.resin_loading_mmol_g if inp.resin_loading_mmol_g else 0.0, "operation_volume_mL": working_volume_mL(inp),
        "default_aa_coupling_eq": effective_eq, "aa_coupling_eq_source": effective_eq_source, "default_modifier_eq": inp.ac_eq,
        "default_coupling_repeats": inp.default_coupling_repeats, "default_modifier_repeats": inp.default_modifier_repeats,
        "default_coupling_system": _normalized_default_coupling_system(inp), "default_reagent_eq": inp.default_reagent_eq, "default_reagent_count": inp.default_reagent_count, "default_catalyst_eq": inp.default_catalyst_eq, "default_catalyst_count": inp.default_catalyst_count, "default_base_eq": inp.default_base_eq, "default_base_count": inp.default_base_count, "solvent_volume_mode": inp.solvent_volume_mode, "amide_ml_per_mmol": inp.amide_ml_per_mmol, "ctc_ml_per_mmol": inp.ctc_ml_per_mmol, "solvent_molarity_m": inp.solvent_molarity_m, "deprotection_condition": f"{inp.deprotection_base} / {inp.deprotection_ratio} x{inp.deprotection_count}",
        "cleavage_eq_suggestion": cleavage.get("cleavage_eq"), "cleavage_eq_source": cleavage.get("source"),
        "cleavage_volume_basis": "scale_mmol x eq x resin_factor (CTC/Trityl=0.5, Amide=1.0)",
        "cleavage_auto_recommended_preset": recommend_cleavage_preset(inp).get("preset"),
        "cleavage_auto_reason": recommend_cleavage_preset(inp).get("reason"),
        "cleavage_tfa_component_mL": _component_mL("TFA"),
        "cleavage_cocktail_total_mL": cocktail_total_mL,
        "dmf_mL": float(matrix["dmf_mL"].sum()), "piperidine_mL": float(matrix["piperidine_mL"].sum()), "dcm_mL": float(matrix["dcm_mL"].sum()),
        "manual_override_count": int((matrix.get("override_source", "") != "default").sum()) if "override_source" in matrix.columns else 0,
        "product_mw": product_mw, "mh": product_mw + 1.0073, "mna": product_mw + 22.9898, "materials_count": int(len(materials)),
    }
# ======================= END V2.1.7 SUMMARY CLEAVAGE LABEL REPAIR =======================

# ======================= V2.1.9 STEP MATERIAL ORDER + LIQUID DISPLAY REPAIR =======================
# Keep original builders for compatibility while returning ordered/mL-only operator tables.
_V219_ORIG_GENERATE_STEP_MATERIALS = _generate_step_materials_core
_V219_ORIG_GENERATE_MATERIALS = _generate_materials_core

_V219_LIQUID_NAMES = {
    'dic','diea','dipea','dmf','dcm','mc','mc/dcm','nmp','tfa','tis','edt','acoh','acetic acid','tfe','tee',
    'piperidine','water','h2o','dw','dw / water','meoh','methanol','acetic anhydride','ac2o','tea','triethylamine',
    'pyridine','thioanisole','anisole','dms','dmso','triethylsilane'
}

def _v219_is_liquid_material(name: str, cls: str = '', state: str = '', unit: str = '') -> bool:
    s = str(name or '').strip().lower()
    base = s.split(' -')[0].strip()
    cls_l = str(cls or '').lower()
    state_l = str(state or '').lower()
    unit_l = str(unit or '').lower()
    if state_l in {'liquid','solution'} or unit_l == 'ml':
        return True
    if base in _V219_LIQUID_NAMES or s in _V219_LIQUID_NAMES:
        return True
    if 'solvent' in cls_l or 'solution' in cls_l:
        return True
    return False

def _v219_numeric(v, default=0.0) -> float:
    try:
        if v is None or str(v).strip() == '': return default
        return float(str(v).replace(',', '').strip())
    except Exception:
        return default

def _v219_apply_liquid_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    for idx, r in out.fillna('').iterrows():
        mat = r.get('material', r.get('component', ''))
        cls = r.get('class', r.get('role', ''))
        state = r.get('physical_state', '')
        unit = r.get('unit', '')
        reagent = r.get('reagent', '')
        is_liq = _v219_is_liquid_material(mat, cls, state, unit) or _v219_is_liquid_material(reagent, cls, state, unit)
        if not is_liq:
            continue
        density = _v219_numeric(r.get('density_g_mL', ''), 0.0)
        g = _v219_numeric(r.get('planned_g', ''), 0.0)
        ml = _v219_numeric(r.get('planned_mL', ''), 0.0)
        if ml <= 0 and g > 0 and density > 0 and 'planned_mL' in out.columns:
            out.at[idx, 'planned_mL'] = g / density
        for col in ('planned_g','planned_mg','approx_g'):
            if col in out.columns:
                out.at[idx, col] = 0.0
        if 'unit' in out.columns:
            out.at[idx, 'unit'] = 'mL'
    return out

def _v219_order_step_materials(df: pd.DataFrame, resin_text: str = '') -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = _v219_apply_liquid_display(df).copy()
    out = out.astype(object).where(pd.notna(out), '')
    if resin_text and 'step' in out.columns and 'material' in out.columns:
        mask = out['step'].astype(str).str.lower().eq('resin')
        out.loc[mask, 'material'] = resin_text
        if 'reagent' in out.columns:
            out.loc[mask, 'reagent'] = resin_text
    def step_rank(v):
        s = str(v or '').strip().lower()
        if s == 'resin': return -1000
        if s == 'cleavage': return 100000
        try: return int(float(s)) * 100
        except Exception: return 90000
    def phase_rank(r):
        phase = str(r.get('phase','')).lower()
        src = str(r.get('source','')).lower()
        cls = str(r.get('class','')).lower()
        step = str(r.get('step','')).lower()
        if step == 'resin': return 0
        if phase == 'swell': return 1
        if 'deprotection' in phase: return 5
        if 'post' in phase: return 40
        if 'dmf wash' in phase: return 10
        if 'loading' in phase: return 15
        if 'regular aa' in phase or 'coupling' in phase:
            if 'unit' in src or 'aa' in cls: return 20
            if 'coupling reagent' in cls: return 21
            if 'catalyst' in cls: return 22
            if cls == 'additive': return 23
            if cls == 'base': return 24
            return 25
        if 'synthesis' in phase or 'reaction' in phase: return 30
        if 'dcm wash' in phase or 'mc/dcm' in phase: return 50
        if 'cleavage' in phase: return 1000
        return 100
    out['_sort_key'] = out.apply(lambda r: step_rank(r.get('step','')) + phase_rank(r), axis=1)
    out['_orig_order'] = range(len(out))
    out = out.sort_values(['_sort_key','_orig_order'], kind='mergesort').drop(columns=['_sort_key','_orig_order'])
    return out.reset_index(drop=True)

def _generate_step_materials_v219(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    return _v219_order_step_materials(_V219_ORIG_GENERATE_STEP_MATERIALS(inp, compounds, rules), str(getattr(inp, 'resin', '') or ''))

def _generate_materials_v219(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    return _v219_apply_liquid_display(_V219_ORIG_GENERATE_MATERIALS(inp, compounds, rules))
# ======================= END V2.1.9 STEP MATERIAL ORDER + LIQUID DISPLAY REPAIR =======================

# ======================= V2.2.1 USER-FACING MATERIAL DISPLAY FINAL REPAIR =======================
# Keep calculation internals intact, but guarantee operator-facing material tables use:
# - editor resin display: 2-CTC instead of internal CTC aliases;
# - protected bottle names instead of one-letter AA tokens in totals;
# - mL-only display fields for liquid/solution reagents such as DIEA and DIC.

_V221_ORIG_GENERATE_STEP_MATERIALS = _generate_step_materials_v219
_V221_ORIG_GENERATE_MATERIALS = _generate_materials_v219

_V221_AA_REAGENT_NAMES = {
    "A": "Fmoc-Ala-OH", "R": "Fmoc-Arg(Pbf)-OH", "N": "Fmoc-Asn(Trt)-OH", "D": "Fmoc-Asp(OtBu)-OH",
    "C": "Fmoc-Cys(Trt)-OH", "Q": "Fmoc-Gln(Trt)-OH", "E": "Fmoc-Glu(OtBu)-OH", "G": "Fmoc-Gly-OH",
    "H": "Fmoc-His(Trt)-OH", "I": "Fmoc-Ile-OH", "L": "Fmoc-Leu-OH", "K": "Fmoc-Lys(Boc)-OH",
    "M": "Fmoc-Met-OH", "F": "Fmoc-Phe-OH", "P": "Fmoc-Pro-OH", "S": "Fmoc-Ser(tBu)-OH",
    "T": "Fmoc-Thr(tBu)-OH", "W": "Fmoc-Trp(Boc)-OH", "Y": "Fmoc-Tyr(tBu)-OH", "V": "Fmoc-Val-OH",
}
_V221_LIQUID_NAMES = {
    "dic", "diea", "dipea", "dmf", "dcm", "mc", "mc/dcm", "nmp", "tfa", "tis", "edt",
    "acoh", "acetic acid", "tfe", "tee", "piperidine", "water", "h2o", "dw", "dw / water",
    "meoh", "methanol", "acetic anhydride", "ac2o", "tea", "triethylamine", "pyridine",
    "thioanisole", "anisole", "dms", "dmso", "triethylsilane", "cleavage reagent", "cleavage cocktail component",
}

def _v221_norm_display(x: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣/]+", "", str(x or "").strip().lower())

def _v221_resin_display(resin: Any) -> str:
    raw = str(resin or "").strip()
    n = _v221_norm_display(raw)
    if "ctc" in n or "trityl" in n or "합성기" in raw or "합성용" in raw:
        return "2-CTC"
    return raw or "Rink Amide AM"


def _v221_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or str(v).strip() == "":
            return default
        return float(str(v).replace(",", "").strip())
    except Exception:
        return default



def _v221_order_step_materials(df: pd.DataFrame, resin_text: str = "") -> pd.DataFrame:
    out = _v221_apply_display_rules(df, resin_text)
    if out is None or getattr(out, "empty", True):
        return out
    out = out.copy()
    out["_orig_order_v221"] = range(len(out))
    out["_sort_v221"] = out.apply(lambda r: _v221_step_sort_key(r)[0], axis=1)
    out = out.sort_values(["_sort_v221", "_orig_order_v221"], kind="mergesort").drop(columns=["_sort_v221", "_orig_order_v221"])
    return out.reset_index(drop=True)

def _generate_step_materials_v221(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    return _v221_order_step_materials(_V221_ORIG_GENERATE_STEP_MATERIALS(inp, compounds, rules), _v221_resin_display(getattr(inp, "resin", "")))

def _generate_materials_v221(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    return _v221_apply_display_rules(_V221_ORIG_GENERATE_MATERIALS(inp, compounds, rules), _v221_resin_display(getattr(inp, "resin", "")))
# ======================= END V2.2.1 USER-FACING MATERIAL DISPLAY FINAL REPAIR =======================

# V2.2.1b ordering correction: synthesis/reaction solvent belongs after coupling reagents, not before deprotection.
# ======================= END V2.2.1b ORDERING CORRECTION =======================

# V2.2.1c: Post DMF wash must stay after coupling/reaction, not inside generic DMF wash bucket.
def _v221_step_sort_key(row: pd.Series) -> tuple[float, int]:
    s = str(row.get("step", "")).strip().lower()
    if s == "resin": base = -1000
    elif s == "cleavage": base = 100000
    else:
        try: base = int(float(s)) * 100
        except Exception: base = 90000
    phase = str(row.get("phase", "")).strip().lower()
    src = str(row.get("source", "")).strip().lower()
    cls = str(row.get("class", "")).strip().lower()
    mat = str(row.get("material", "")).strip().lower()
    if s == "resin": rank = 0
    elif "swell" in phase: rank = 1
    elif "loading" in phase and ("aa" in cls or "unit" in src): rank = 10
    elif "loading" in phase and ("base" in cls or "aux" in src): rank = 11
    elif "deprotection" in phase and "piperidine" in mat: rank = 20
    elif "deprotection" in phase: rank = 21
    elif "post" in phase: rank = 50
    elif "final" in phase: rank = 60
    elif "dmf wash" in phase: rank = 30
    elif "regular aa" in phase or "coupling" in phase:
        if "aa" in cls or "unit" in src: rank = 40
        elif "coupling reagent" in cls: rank = 41
        elif "catalyst" in cls: rank = 42
        elif "base" in cls: rank = 43
        elif "solvent" in cls: rank = 44
        else: rank = 45
    elif "synthesis" in phase or "reaction" in phase: rank = 46
    elif "cleavage" in phase: rank = 1000
    else: rank = 100
    return (base + rank, 0)
# ======================= END V2.2.1c ORDERING CORRECTION =======================

# V2.2.1d: keep internal numeric planned_g=0.0 for regression/backward compatibility.
def _v221_apply_display_rules(df: pd.DataFrame, resin_text: str = "") -> pd.DataFrame:
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy().astype(object).where(pd.notna(df), "")
    resin_disp = _v221_resin_display(resin_text or getattr(df, "resin", ""))
    for idx, r in out.iterrows():
        mat = str(r.get("material", r.get("component", "")) or "").strip()
        cls = str(r.get("class", r.get("role", "")) or "").strip()
        state = str(r.get("physical_state", "") or "").strip()
        unit = str(r.get("unit", "") or "").strip()
        reagent = str(r.get("reagent", "") or "").strip()
        if str(r.get("step", "")).strip().lower() == "resin" or mat.lower() == "resin" or cls == "CTC/Trityl":
            if "material" in out.columns: out.at[idx, "material"] = resin_disp
            if "reagent" in out.columns: out.at[idx, "reagent"] = resin_disp
            if "class" in out.columns and cls == "CTC/Trityl": out.at[idx, "class"] = "Resin"
            continue
        if mat in _V221_AA_REAGENT_NAMES and str(cls).upper() == "AA":
            out.at[idx, "material"] = _V221_AA_REAGENT_NAMES[mat]
            mat = _V221_AA_REAGENT_NAMES[mat]
            if "class" in out.columns: out.at[idx, "class"] = "AA/Chemical"
        is_liq = _v221_is_liquid_display(mat, cls, state, unit) or _v221_is_liquid_display(reagent, cls, state, unit)
        if not is_liq: continue
        density = _v221_float(r.get("density_g_mL", r.get("Density(g/mL)", "")), 0.0)
        g = _v221_float(r.get("planned_g", ""), 0.0)
        ml = _v221_float(r.get("planned_mL", r.get("volume_mL", "")), 0.0)
        if ml <= 0 and g > 0 and density > 0:
            ml = g / density
            if "planned_mL" in out.columns: out.at[idx, "planned_mL"] = ml
            if "volume_mL" in out.columns: out.at[idx, "volume_mL"] = ml
        for col in ("planned_g", "planned_mg", "approx_g"):
            if col in out.columns: out.at[idx, col] = 0.0
        if "unit" in out.columns: out.at[idx, "unit"] = "mL"
    return out
# ======================= END V2.2.1d ENGINE NUMERIC COMPATIBILITY =======================

# V2.2.1e: cleavage solids such as phenol remain grams; only explicit liquid components are mL-only.
def _v221_is_liquid_display(material: Any, cls: Any = "", state: Any = "", unit: Any = "") -> bool:
    s = str(material or "").strip().lower()
    base = s.split(" -")[0].strip()
    cls_l = str(cls or "").strip().lower()
    state_l = str(state or "").strip().lower()
    unit_l = str(unit or "").strip().lower()
    if unit_l == "ml" or state_l in {"liquid", "solution", "mixture"}:
        return True
    if state_l in {"solid", "solid_wv", "powder"}:
        return False
    if base in _V221_LIQUID_NAMES or s in _V221_LIQUID_NAMES:
        return True
    if base in {"dic", "diea"}:
        return True
    if "solvent" in cls_l or "solution" in cls_l:
        return True
    return False
# ======================= END V2.2.1e CLEAVAGE SOLID DISPLAY FIX =======================

# ======================= V2.2.2 FINAL USER-FACING MATERIAL/RESIN REPAIR =======================
# Purpose: separate the user-selected resin label from the internal resin family/profile,
# make Selected Materials strictly step-by-step, and make liquid reagents mL-only in all
# user-facing material outputs.  This is intentionally appended last so older patch-stack
# helpers cannot override it.

_V222_ORIG_GENERATE_STEP_MATERIALS = _generate_step_materials_v221
_V222_ORIG_GENERATE_MATERIALS = _generate_materials_v221

_V222_LIQUID_NAMES = {
    "dic", "diea", "dipea", "dmf", "dcm", "mc", "mc/dcm", "nmp",
    "tfa", "tis", "edt", "acoh", "acetic acid", "tfe", "tee",
    "piperidine", "water", "h2o", "dw", "dw / water", "meoh", "methanol",
    "acetic anhydride", "ac2o", "tea", "triethylamine", "pyridine",
    "thioanisole", "anisole", "dms", "dmso", "triethylsilane",
}


def user_resin_label(resin: Any) -> str:
    """Return the exact user-facing resin label without collapsing CTC variants.

    2-CTC and CTC(합성용/합성기) may share an internal CTC/Trityl family, but they
    are separate user options and must not be substituted in GUI/export tables.
    """
    raw = str(resin or "").strip()
    if not raw:
        return "Rink Amide AM"
    # Repair internal/removed aliases while preserving the two active profiles.
    if raw.strip().lower() in {"ctc/trityl", "ctc_trityl"}:
        return "2-CTC"
    if raw in {"CTC 합성용", "CTC-synthesis", "CTC synthesis"}:
        return "CTC(합성용)"
    if raw == "CTC(합성용)":
        return raw
    return raw


def _v222_num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        s = str(v).replace(",", "").strip()
        if not s:
            return default
        return float(s)
    except Exception:
        return default


def _v222_norm_name(x: Any) -> str:
    return re.sub(r"\s+", " ", str(x or "").strip().lower())


def _v222_base_name(x: Any) -> str:
    return _v222_norm_name(x).split(" -")[0].strip()


def _v222_is_liquid(material: Any = "", cls: Any = "", state: Any = "", unit: Any = "", reagent: Any = "") -> bool:
    vals = [_v222_base_name(material), _v222_base_name(reagent), _v222_norm_name(material), _v222_norm_name(reagent)]
    state_l = _v222_norm_name(state)
    unit_l = _v222_norm_name(unit)
    cls_l = _v222_norm_name(cls)
    if unit_l == "ml" or state_l in {"liquid", "solution", "mixture"}:
        return True
    # Solid cleavage scavengers such as phenol must remain grams.
    if state_l in {"solid", "solid_wv", "powder"}:
        return False
    if any(v in _V222_LIQUID_NAMES for v in vals):
        return True
    # The user explicitly confirmed DIC is liquid/solvent-like for display.
    if any(v in {"dic", "diea", "dipea"} for v in vals):
        return True
    if "solvent" in cls_l or "solution" in cls_l:
        return True
    return False


def _v222_apply_material_display(df: pd.DataFrame, resin_label: str = "") -> pd.DataFrame:
    if df is None or getattr(df, "empty", True):
        return df
    out = df.copy().astype(object).where(pd.notna(df), "")
    label = user_resin_label(resin_label)
    for idx, row in out.iterrows():
        mat = str(row.get("material", row.get("component", "")) or "").strip()
        reagent = str(row.get("reagent", "") or "").strip()
        cls = str(row.get("class", row.get("role", "")) or "").strip()
        state = str(row.get("physical_state", "") or "").strip()
        unit = str(row.get("unit", "") or "").strip()
        step = str(row.get("step", "") or "").strip().lower()

        # Resin row: show the exact user-selected label.  Do not collapse
        # CTC(합성용/합성기) into 2-CTC or vice versa.
        if step == "resin" or mat.lower() == "resin" or ("resin" in cls.lower() and ("ctc" in mat.lower() or "trityl" in mat.lower() or not mat)):
            if "material" in out.columns:
                out.at[idx, "material"] = label
            if "reagent" in out.columns:
                out.at[idx, "reagent"] = label
            if "class" in out.columns and cls in {"CTC/Trityl", "Amide"}:
                out.at[idx, "class"] = "Resin"
            continue

        # Avoid one-letter AA tokens in total materials.
        if mat in _V221_AA_REAGENT_NAMES and str(cls).upper() == "AA":
            mat2 = _V221_AA_REAGENT_NAMES[mat]
            if "material" in out.columns:
                out.at[idx, "material"] = mat2
            if "class" in out.columns:
                out.at[idx, "class"] = "AA/Chemical"
            mat = mat2

        is_liq = _v222_is_liquid(mat, cls, state, unit, reagent)
        if not is_liq:
            continue
        dens = _v222_num(row.get("density_g_mL", row.get("Density(g/mL)", "")), 0.0)
        g = _v222_num(row.get("planned_g", row.get("total_g", row.get("approx_g", ""))), 0.0)
        ml = _v222_num(row.get("planned_mL", row.get("total_mL", row.get("volume_mL", ""))), 0.0)
        if ml <= 0 and g > 0 and dens > 0:
            ml = g / dens
        for col in ("planned_g", "planned_mg", "approx_g", "total_g"):
            if col in out.columns:
                out.at[idx, col] = ""
        for col in ("planned_mL", "total_mL", "volume_mL"):
            if col in out.columns and ml > 0:
                out.at[idx, col] = round(float(ml), 6)
        if "unit" in out.columns:
            out.at[idx, "unit"] = "mL"
    return out




def _v222_step_order(row: pd.Series) -> tuple[int, int]:
    s = str(row.get("step", "") or "").strip().lower()
    if s == "resin":
        base = -100000
    elif s == "cleavage":
        base = 100000
    else:
        try:
            base = int(float(s)) * 100
        except Exception:
            base = 90000
    return base + _v222_phase_rank(row), 0


def _v222_order_step_materials(df: pd.DataFrame, resin_label: str = "") -> pd.DataFrame:
    out = _v222_apply_material_display(df, resin_label)
    if out is None or getattr(out, "empty", True):
        return out
    out = out.copy()
    out["_v222_orig"] = range(len(out))
    out["_v222_sort"] = out.apply(lambda r: _v222_step_order(r)[0], axis=1)
    out = out.sort_values(["_v222_sort", "_v222_orig"], kind="mergesort").drop(columns=["_v222_sort", "_v222_orig"])
    return out.reset_index(drop=True)


def _v222_add_missing_cleavage_totals(inp: PlanInput, df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee that material totals contain cleavage cocktail components.

    Some older GUI/export paths built totals before the cleavage table was merged.
    This guard keeps Amide and 2-CTC totals consistent.
    """
    out = pd.DataFrame() if df is None else df.copy()
    existing = set(out.get("material", pd.Series(dtype=str)).astype(str).str.lower()) if not out.empty else set()
    rows = []
    try:
        cleav = generate_cleavage_cocktail(inp)
        for _, r in cleav.iterrows():
            comp = str(r.get("component", "") or "").strip()
            if not comp or comp.lower().startswith("total") or "warning" in comp.lower():
                continue
            key = f"{comp} - cleavage cocktail component".lower()
            if key in existing:
                continue
            vol = _v222_num(r.get("volume_mL", ""), 0.0)
            if vol <= 0:
                continue
            rows.append({
                "material": f"{comp} - cleavage cocktail component",
                "class": "cleavage cocktail component",
                "reagent": comp,
                "planned_mmol": 0.0,
                "planned_g": "",
                "planned_mg": "",
                "planned_mL": vol,
                "unit": "mL",
                "MW": "",
                "density_g_mL": r.get("density_g_mL", ""),
                "physical_state": r.get("physical_state", "liquid"),
                "source": f"cleavage cocktail preset={r.get('selected_preset','')}; eq={r.get('recommended_eq','')}",
                "warning": "Cocktail component from dedicated cleavage calculator; prepare fresh and verify SOP.",
            })
    except Exception:
        rows = []
    if rows:
        out = pd.concat([out, pd.DataFrame(rows)], ignore_index=True)
    return out


def _generate_step_materials_v222(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    raw = _V222_ORIG_GENERATE_STEP_MATERIALS(inp, compounds, rules)
    return _v222_order_step_materials(raw, user_resin_label(getattr(inp, "resin", "")))


def _generate_materials_v222(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    raw = _V222_ORIG_GENERATE_MATERIALS(inp, compounds, rules)
    raw = _v222_add_missing_cleavage_totals(inp, raw)
    return _v222_apply_material_display(raw, user_resin_label(getattr(inp, "resin", "")))
# ======================= END V2.2.2 FINAL USER-FACING MATERIAL/RESIN REPAIR =======================

# V2.2.2b: final ordering guard.  "Post DMF wash" must be after coupling,
# not caught by the generic "DMF wash" branch.
def _v222_phase_rank(row: pd.Series) -> int:
    s = str(row.get("step", "") or "").strip().lower()
    phase = str(row.get("phase", "") or "").strip().lower()
    src = str(row.get("source", "") or "").strip().lower()
    cls = str(row.get("class", "") or "").strip().lower()
    mat = str(row.get("material", "") or "").strip().lower()
    if s == "resin": return 0
    if "swell" in phase: return 1
    if "loading" in phase and ("aa" in cls or "unit" in src): return 10
    if "loading" in phase and ("base" in cls or "aux" in src): return 11
    if "deprotection" in phase and "piperidine" in mat: return 20
    if "deprotection" in phase: return 21
    if "post" in phase: return 50
    if "dmf wash" in phase: return 30
    if "regular aa" in phase or "coupling" in phase:
        if "aa" in cls or "unit" in src: return 40
        if "coupling reagent" in cls: return 41
        if "catalyst" in cls: return 42
        if "base" in cls: return 43
        if "solvent" in cls: return 44
        return 45
    if "synthesis" in phase or "reaction" in phase: return 46
    if "final" in phase: return 60
    if "cleavage" in phase: return 1000
    return 100
# ======================= END V2.2.2b FINAL ORDERING GUARD =======================

# Canonical material API. Historical transformations above use unique helper
# names; these public functions are defined once and are never rebound.
from .display import (
    normalize_operator_amounts as _normalize_operator_amounts,
    ordered_step_materials as _ordered_step_materials,
    resin_label as _resin_label,
)


def generate_step_materials(
    inp: PlanInput,
    compounds: pd.DataFrame | None = None,
    rules: dict | None = None,
) -> pd.DataFrame:
    raw = _generate_step_materials_v222(inp, compounds, rules)
    return _ordered_step_materials(raw, _resin_label(getattr(inp, "resin", "")))


def generate_materials(
    inp: PlanInput,
    compounds: pd.DataFrame | None = None,
    rules: dict | None = None,
) -> pd.DataFrame:
    raw = _generate_materials_v222(inp, compounds, rules)
    return _normalize_operator_amounts(raw, _resin_label(getattr(inp, "resin", "")))
