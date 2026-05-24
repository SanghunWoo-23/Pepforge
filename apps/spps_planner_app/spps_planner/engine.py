from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import csv
import io
import re
import pandas as pd
from .parser import parse_sequence
from .database import load_compounds, load_rules, compound_lookup

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

@dataclass
class PlanInput:
    sequence: str = "Ac-EEMQRR-NH2"
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
    tfa_factor: float = 10.0
    step_overrides_text: str = ""


def resin_family(resin: str) -> str:
    r = (resin or "").lower()
    if "ctc" in r or "trityl" in r:
        return "CTC/Trityl"
    return "Amide"


def operation_volume_mL(resin: str, scale_mmol: float) -> float:
    return scale_mmol * (4.0 if resin_family(resin) == "CTC/Trityl" else 10.0)


def cterm_output(resin: str) -> str:
    return "COOH / OH" if resin_family(resin) == "CTC/Trityl" else "CONH2 / NH2"


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
                    keys = ["step", "coupling_reagent", "catalyst", "additive", "base", "reaction_solvent", "reagent_eq", "coupling_repeat", "note"]
                else:
                    keys = ["unit", "coupling_reagent", "catalyst", "additive", "base", "reaction_solvent", "reagent_eq", "coupling_repeat", "note"]
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
    if "NHS" in profile or t.endswith("-NHS") or "NHS" in t:
        return {"coupling_reagent": reagent_name, "catalyst": "", "additive": "activated ester; verify reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_nhs", "note_add": "NHS/activated ester default; no DIC/HOBt unless actual reagent form requires it."}
    if "FITC" in t or "ISOTHIOCYANATE" in profile:
        return {"coupling_reagent": reagent_name if reagent_name else "FITC / isothiocyanate dye", "catalyst": "", "additive": "protect from light; verify reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_fitc", "note_add": "FITC default assumes amine-labeling/isothiocyanate chemistry; verify SOP."}
    if "BIOTIN" in t:
        return {"coupling_reagent": reagent_name if reagent_name else "Biotin reagent (acid/NHS; verify form)", "catalyst": "", "additive": "VERIFY acid vs NHS/sulfo-NHS", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_biotin", "note_add": "Biotin chemistry depends on reagent form; override reagent/catalyst/base/eq."}
    if any(x in t for x in ["CY5", "CY3", "FAM", "TAMRA", "DABCYL", "BHQ", "DOTA", "NOTA"]):
        return {"coupling_reagent": reagent_name or "Activated label / chelator reagent", "catalyst": "", "additive": "protect from light; verify label reagent form", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_label", "note_add": "Label/chelator default is conservative; exact chemistry depends on reagent form."}
    if token in {"Pal", "Myr", "Nic", "Caf", "Gal", "Stear", "Ole"} or "ACID" in profile or "CARBOXYLIC" in profile:
        return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_acid", "note_add": "Acid-like modifier/label/linker default follows selected coupling system; override as needed."}
    if cls in {"label", "base chem", "chemical", "modifier", "n-term modifier", "linker"} or "SPECIAL" in profile:
        return {"coupling_reagent": reagent_name or "Selected modifier reagent; verify form", "catalyst": "", "additive": "VERIFY chemistry", "base": "DIEA", "reaction_solvent": "DMF", "reagent_eq": inp.ac_eq, "coupling_repeat": inp.default_modifier_repeats, "reagent_eq_source": "modifier_default_verify", "note_add": "Generic modifier default; override based on actual reagent/SOP."}
    return None


def _default_step_reagents(phase: str, unit: str, inp: PlanInput, lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    lookup = lookup or {}
    if phase == "Loading" and resin_family(inp.resin) == "CTC/Trityl":
        # 2-CTC/trityl loading is performed under DCM conditions.
        # DIEA/DIPEA is a base, not a coupling reagent, so do not duplicate it
        # as both reagent and base.
        return {"coupling_reagent": "", "catalyst": "", "additive": "", "base": inp.default_base or "DIEA", "reaction_solvent": "DCM", "reagent_eq": inp.coupling_eq, "coupling_repeat": 1, "coupling_repeat_source": "loading_default", "reagent_eq_source": "global_loading"}
    if phase == "Loading":
        return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.coupling_eq, "coupling_repeat": 1, "coupling_repeat_source": "loading_default", "reagent_eq_source": "global_loading"}
    if phase == "Last / N-term cap":
        md = _modifier_defaults(unit, lookup, inp)
        if md:
            note_add = md.pop("note_add", "")
            return md | {"default_note_add": note_add}
    return {"coupling_reagent": inp.default_coupling_reagent or "DIC", "catalyst": inp.default_catalyst or "HOBt", "additive": "", "base": inp.default_base or "", "reaction_solvent": inp.default_reaction_solvent or "DMF", "reagent_eq": inp.coupling_eq, "coupling_repeat": inp.default_coupling_repeats, "reagent_eq_source": "global_aa"}


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
    old_rxn = max(1, int(rxn or 1))
    rep = _parse_repeat(defaults.get("coupling_repeat", rxn)) or old_rxn
    if rep != old_rxn:
        # Reaction solvent volume scales with the number of coupling/reaction repeats.
        # Deprotection and wash volumes are unchanged.
        dmf += max(0, rep - old_rxn) * operation_volume_mL(inp.resin, inp.scale_mmol) * float(dmf_frac)
        dcm += max(0, rep - old_rxn) * operation_volume_mL(inp.resin, inp.scale_mmol) * float(dcm_frac)
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
    eq = float(defaults.get("reagent_eq", 1.0) or 1.0)
    total_eq = eq * rep
    mmol = float(inp.scale_mmol) * total_eq
    g = mmol * mw / 1000.0 if mw else 0.0
    resin_g = float(inp.scale_mmol) / float(inp.resin_loading_mmol_g) if inp.resin_loading_mmol_g else 0.0
    return Step(
        step_no, "C-term to N-term", pos_cterm, pos_nterm, unit, phase, chemistry, depro, wash, rxn, post, dcmx, dmf_frac, dcm_frac, dmf, pip, dcm, note,
        protected, reagent_class, mw, prod,
        str(defaults.get("coupling_reagent", "")), str(defaults.get("catalyst", "")), str(defaults.get("additive", "")),
        str(defaults.get("base", "")), str(defaults.get("reaction_solvent", "")), eq,
        str(defaults.get("reagent_eq_source", "global_default")), rep, str(defaults.get("coupling_repeat_source", defaults.get("reagent_eq_source", "global_default"))), total_eq, mmol, g, g*1000.0, resin_g,
        source, "spps_ml_ready"
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
    family = resin_family(inp.resin)
    vol = operation_volume_mL(inp.resin, inp.scale_mmol)
    dmf_ratio = float(rules.get("depro_dmf_ratio", 0.8))
    pip_ratio = float(rules.get("depro_piperidine_ratio", 0.2))
    steps: list[Step] = []
    step_no = 1
    cterm_unit = tokens[-1]
    n = len(tokens)
    if family == "Amide":
        depro = int(rules.get("amide_loading_depro", 2)); wash = int(rules.get("amide_loading_dmf_wash", 6)); rxn = int(rules.get("amide_loading_synthesis", 1)); post = int(rules.get("amide_loading_post_dmf_wash", 2)); dmf_swell = int(rules.get("amide_loading_dmf_swell", 1))
        dmf = vol * (dmf_swell + depro * dmf_ratio + wash + rxn + post); pip = vol * (depro * pip_ratio); dcm = 0.0
        note = "Amide loading: DMF swell 1 → depro 2 → DMF wash 6 → synthesis 1 → DMF wash 2"
        steps.append(_make_step(step_no, cterm_unit, "Loading", "Amide loading", depro, wash, rxn, post, 0, 1.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, 1, n))
    else:
        swell = int(rules.get("ctc_loading_dcm_swell", 1)); rxn = int(rules.get("ctc_loading_synthesis", 1)); dmf_frac = float(rules.get("ctc_loading_synthesis_dmf_fraction", 0.1)); dcm_frac = float(rules.get("ctc_loading_synthesis_dcm_fraction", 0.9))
        dmf = vol * (rxn * dmf_frac); dcm = vol * (swell + rxn * dcm_frac)
        note = "CTC/Trityl loading: DCM swell 1 → synthesis 1 with 90% DCM + 10% DMF"
        steps.append(_make_step(step_no, cterm_unit, "Loading", "CTC/Trityl loading", 0, 0, rxn, 0, swell, dmf_frac, dcm_frac, dmf, 0.0, dcm, note, inp, overrides, lookup, 1, n))
    step_no += 1
    for idx, aa in enumerate(reversed(tokens[:-1]), start=2):
        depro = int(rules.get("regular_depro", 2)); wash = int(rules.get("regular_dmf_wash_after_depro", 2)); rxn = int(rules.get("regular_coupling", 1)); post = int(rules.get("regular_post_dmf_wash", 6))
        dmf = vol * (depro * dmf_ratio + wash + rxn + post); pip = vol * (depro * pip_ratio)
        note = "Regular: depro 2 → DMF wash 2 → coupling 1 or user-defined repeat → DMF wash 6"
        pos_cterm = idx; pos_nterm = n - idx + 1
        steps.append(_make_step(step_no, aa, "Regular AA coupling", _profile_for(aa, lookup), depro, wash, rxn, post, 0, 1.0, 0.0, dmf, pip, 0.0, note, inp, overrides, lookup, pos_cterm, pos_nterm))
        step_no += 1
    if parsed.nterm:
        token = parsed.nterm
        depro = int(rules.get("last_depro", 2)); wash = int(rules.get("last_dmf_wash_after_depro", 6)); rxn = int(rules.get("last_reaction", 1)); post = int(rules.get("last_post_dmf_wash", 3)); dcmx = int(rules.get("last_dcm_wash", 3))
        dmf = vol * (depro * dmf_ratio + wash + rxn + post); pip = vol * (depro * pip_ratio); dcm = vol * dcmx
        chem = _profile_for(token, lookup)
        if token in {"Ac", "Acetic acid", "Acetyl"}: chem = "Ac/capping"
        note = "Last/cap/modifier: depro 2 → DMF wash 6 → modifier/label reaction → DMF wash 3 → DCM wash 3"
        steps.append(_make_step(step_no, token, "Last / N-term cap", chem, depro, wash, rxn, post, dcmx, 1.0, 0.0, dmf, pip, dcm, note, inp, overrides, lookup, n+1, 0))
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
    vol = operation_volume_mL(inp.resin, inp.scale_mmol)
    family = resin_family(inp.resin)
    rules = rules or load_rules()
    dmf_ratio = float(rules.get("depro_dmf_ratio", 0.8)); pip_ratio = float(rules.get("depro_piperidine_ratio", 0.2))
    rows = []; line = 1
    for _, s in matrix.iterrows():
        def add(group, detail, repeat_no, dmf=0.0, pip=0.0, dcm=0.0, solution="", reagent_g=""):
            nonlocal line
            rows.append({
                "line": line, "step": int(s.step), "unit": s.unit, "phase": s.phase, "chemistry": s.chemistry,
                "protected_reagent": s.protected_reagent, "reagent_mw": s.reagent_mw,
                "coupling_reagent": s.coupling_reagent, "catalyst": s.catalyst, "additive": s.additive, "base": s.base,
                "reaction_solvent": s.reaction_solvent, "reagent_eq": s.reagent_eq, "coupling_repeat": s.coupling_repeat,
                "total_reagent_eq": s.total_reagent_eq, "planned_reagent_g": s.planned_reagent_g, "planned_reagent_mg": s.planned_reagent_mg,
                "reagent_eq_source": s.reagent_eq_source, "override_source": s.override_source, "ml_feature_source": s.ml_feature_source,
                "operation_group": group, "operation_detail": detail, "repeat_no": repeat_no, "solution_note": solution, "planned_reagent_g_operation": reagent_g,
                "dmf_mL": dmf, "piperidine_mL": pip, "dcm_mL": dcm, "status": "To do", "actual_amount": "", "actual_eq": "", "operator_time": "", "note": ""
            }); line += 1
        add("Reagent/resin", "Prepare resin or reagent", 1, reagent_g=s.planned_reagent_g)
        if s.phase == "Loading" and family == "Amide": add("Swell", "DMF swell 1", 1, dmf=vol, solution="DMF 100%")
        if s.phase == "Loading" and family == "CTC/Trityl": add("Swell", "DCM swell 1", 1, dcm=vol, solution="DCM 100%")
        for i in range(1, int(s.depro_x) + 1): add("Deprotection", f"Deprotection {i}", i, dmf=vol*dmf_ratio, pip=vol*pip_ratio, solution="20% piperidine + 80% DMF")
        for i in range(1, int(s.dmf_wash_x) + 1): add("DMF wash", f"DMF wash after deprotection {i}", i, dmf=vol, solution="DMF 100%")
        for i in range(1, int(s.reaction_x) + 1):
            sol = f"{s.reaction_solvent}; reagent={s.coupling_reagent}; catalyst={s.catalyst}; additive={s.additive}; base={s.base}; eq_each={s.reagent_eq}; repeat={s.coupling_repeat}; total_eq={s.total_reagent_eq}"
            add("Synthesis/reaction", f"Synthesis / coupling / modifier reaction {i}", i, dmf=vol*float(s.rxn_dmf_frac), dcm=vol*float(s.rxn_dcm_frac), solution=sol, reagent_g=s.planned_reagent_g/float(s.coupling_repeat or 1))
        for i in range(1, int(s.post_dmf_wash_x) + 1): add("Post DMF wash", f"Post/final DMF wash {i}", i, dmf=vol, solution="DMF 100%")
        for i in range(1, int(s.dcm_wash_x) + 1):
            if s.phase != "Loading": add("DCM wash", f"DCM wash {i}", i, dcm=vol, solution="DCM 100%")
    return pd.DataFrame(rows)


def generate_step_reagent_plan(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    matrix = generate_step_matrix(inp, compounds, rules)
    cols = ["step", "unit", "phase", "chemistry", "protected_reagent", "reagent_class", "reagent_mw", "coupling_reagent", "catalyst", "additive", "base", "reaction_solvent", "reagent_eq", "coupling_repeat", "total_reagent_eq", "planned_reagent_mmol", "planned_reagent_g", "planned_reagent_mg", "reagent_eq_source", "coupling_repeat_source", "override_source", "ml_feature_source", "note"]
    return matrix[[c for c in cols if c in matrix.columns]].copy()


def generate_materials(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> pd.DataFrame:
    compounds = compounds if compounds is not None else load_compounds(); lookup = compound_lookup(compounds); rows = []
    resin_g = inp.scale_mmol / inp.resin_loading_mmol_g if inp.resin_loading_mmol_g else 0.0
    rows.append({"material": "Resin", "class": resin_family(inp.resin), "reagent": inp.resin, "planned_mmol": inp.scale_mmol, "planned_g": resin_g, "planned_mg": resin_g*1000, "planned_mL": 0.0, "unit": "g", "source": "scale/loading"})
    step_plan = generate_step_reagent_plan(inp, compounds, rules)
    agg: dict[tuple, dict] = {}
    def add_agg(material: str, cls: str, reagent: str, planned_mmol: float, planned_g: float, unit: str, source: str):
        material = str(material or "").strip()
        if not material: return
        key = (material, cls, unit, source if str(source).startswith("step") else "")
        if key not in agg: agg[key] = {"material": material, "class": cls, "reagent": reagent or material, "planned_mmol": 0.0, "planned_g": 0.0, "planned_mg": 0.0, "planned_mL": 0.0, "unit": unit, "source": source}
        agg[key]["planned_mmol"] += planned_mmol; agg[key]["planned_g"] += planned_g; agg[key]["planned_mg"] += planned_g*1000
    for _, s in step_plan.iterrows():
        unit_token = str(s.get("unit", "")).strip(); total_eq = float(s.get("total_reagent_eq") or s.get("reagent_eq") or inp.coupling_eq); req_mmol = inp.scale_mmol * total_eq
        row = lookup.get(unit_token, {}); mw = float(row.get("Reagent MW (g/mol)") or 0); planned_g = req_mmol * mw / 1000 if mw else 0.0
        add_agg(unit_token, str(row.get("Class", "coupling unit")), str(row.get("Reagent/protected form", unit_token)), req_mmol, planned_g, "g", f"step {int(s.step)} unit total_eq={total_eq} source={s.get('reagent_eq_source','')}")
        for material, cls in [(s.get("coupling_reagent", ""), "coupling/modifier reagent"), (s.get("catalyst", ""), "catalyst/additive"), (s.get("additive", ""), "additive"), (s.get("base", ""), "base")]:
            material = str(material or "").strip()
            if material: add_agg(material, cls, material, req_mmol, 0.0, "see SOP", f"step {int(s.step)} {s.get('override_source','')} total_eq={total_eq}")
    rows.extend(agg.values())
    ops = generate_detailed_operations(inp, compounds, rules)
    rows += [
        {"material": "DMF", "class": "solvent", "reagent": "DMF", "planned_mmol": 0, "planned_g": 0, "planned_mg": 0, "planned_mL": ops["dmf_mL"].sum(), "unit": "mL", "source": "operation total"},
        {"material": "Piperidine", "class": "solvent", "reagent": "Piperidine", "planned_mmol": 0, "planned_g": 0, "planned_mg": 0, "planned_mL": ops["piperidine_mL"].sum(), "unit": "mL", "source": "operation total"},
        {"material": "DCM", "class": "solvent", "reagent": "DCM", "planned_mmol": 0, "planned_g": 0, "planned_mg": 0, "planned_mL": ops["dcm_mL"].sum(), "unit": "mL", "source": "operation total"},
        {"material": "TFA", "class": "cleavage", "reagent": "TFA", "planned_mmol": 0, "planned_g": 0, "planned_mg": 0, "planned_mL": inp.scale_mmol/2 if resin_family(inp.resin)=="CTC/Trityl" else inp.scale_mmol*inp.tfa_factor, "unit": "mL", "source": "suggestion"},
    ]
    return pd.DataFrame(rows)


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
            "Coupling system": f"{s.get('coupling_reagent','')} / {s.get('catalyst','')} / {s.get('base','')}",
            "Repeat": s.get("coupling_repeat", ""),
            "Date": "",
            "Checked": "□",
            "Note": "",
        })
    return pd.DataFrame(rows)

def plan_summary(inp: PlanInput, compounds: pd.DataFrame | None = None, rules: dict | None = None) -> dict:
    matrix = generate_step_matrix(inp, compounds, rules); parsed = parse_sequence(inp.sequence); materials = generate_materials(inp, compounds, rules)
    product_mw = 0.0; lookup = compound_lookup(compounds if compounds is not None else load_compounds())
    for token in (parsed.core_tokens or list(parsed.core)) + ([parsed.nterm] if parsed.nterm else []):
        product_mw += _float_row(_row_for(token, lookup), "Product MW contribution (g/mol)")
    product_mw += 17.03 if cterm_output(inp.resin).startswith("CONH2") else 18.02
    return {"sequence": inp.sequence, "nterm": parsed.nterm, "core": parsed.core, "core_tokens": "|".join(parsed.core_tokens), "cterm_text": parsed.cterm_text, "resin_family": resin_family(inp.resin), "cterm_output": cterm_output(inp.resin), "resin_g": inp.scale_mmol / inp.resin_loading_mmol_g if inp.resin_loading_mmol_g else 0.0, "operation_volume_mL": operation_volume_mL(inp.resin, inp.scale_mmol), "default_aa_coupling_eq": inp.coupling_eq, "default_modifier_eq": inp.ac_eq, "default_coupling_repeats": inp.default_coupling_repeats, "default_modifier_repeats": inp.default_modifier_repeats, "default_coupling_system": f"{inp.default_coupling_reagent}/{inp.default_catalyst}/{inp.default_base}", "dmf_mL": float(matrix["dmf_mL"].sum()), "piperidine_mL": float(matrix["piperidine_mL"].sum()), "dcm_mL": float(matrix["dcm_mL"].sum()), "manual_override_count": int((matrix.get("override_source", "") != "default").sum()) if "override_source" in matrix.columns else 0, "product_mw": product_mw, "mh": product_mw + 1.0073, "mna": product_mw + 22.9898, "materials_count": int(len(materials))}
