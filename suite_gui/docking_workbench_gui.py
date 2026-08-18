
from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)
import os
import sys
import math
import re
import shutil
import traceback
import json
import tempfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon, open_path
from peptiforg_core.ui_theme import apply_pepforge_theme
from peptiforg_core.sandbox_runtime import configured_output
from peptiforg_core.rcsb_pdb_bridge import search_rcsb, download_rcsb_structure, results_to_rows, RCSB_BRIDGE_VERSION
from peptiforg_core.target_structure_preparation import export_target_preparation_package, TARGET_PREP_VERSION
from peptiforg_core.binding_site_selector import export_binding_site_selection_package, BINDING_SITE_SELECTOR_VERSION
from peptiforg_core.external_docking_result_parser import export_external_docking_import_package, EXTERNAL_DOCKING_PARSER_VERSION
from peptiforg_core.calibration_dataset_mode import export_calibration_dataset_template, export_calibration_report, CALIBRATION_MODE_VERSION
from peptiforg_core.calibration_visualization import export_calibration_visualization_package, CALIBRATION_VISUALIZATION_VERSION
from peptiforg_core.evidence_engine import export_evidence_engine_report, export_evidence_engine_report_from_project, EVIDENCE_ENGINE_VERSION
from peptiforg_core.project_session_manager import create_project_session_package, load_project_session, export_session_summary, PROJECT_SESSION_VERSION
from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard, CANDIDATE_DASHBOARD_VERSION
from peptiforg_core.experimental_data_importer import make_experimental_template, export_experimental_import_package, EXPERIMENTAL_IMPORT_VERSION
from peptiforg_core.workflow_automation_runner import default_workflow_config, save_workflow_config, run_workflow, WORKFLOW_AUTOMATION_VERSION
from peptiforg_core.run_comparison import export_run_comparison_package, RUN_COMPARISON_VERSION
from peptiforg_core.peptide_target_complex_builder import export_complex_builder_package, COMPLEX_BUILDER_VERSION

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from peptiforg_core.peptide_tokens import (
    parse_peptide_notation as unified_parse_peptide,
    normalize_token,
    NTERM_MODIFIERS,
)

AA_MASS = {
    "A": 89.09, "R": 174.20, "N": 132.12, "D": 133.10, "C": 121.16,
    "Q": 146.15, "E": 147.13, "G": 75.07, "H": 155.16, "I": 131.17,
    "L": 131.17, "K": 146.19, "M": 149.21, "F": 165.19, "P": 115.13,
    "S": 105.09, "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
}
HYDRO = {"A":1.8,"R":-4.5,"N":-3.5,"D":-3.5,"C":2.5,"Q":-3.5,"E":-3.5,"G":-0.4,"H":-3.2,"I":4.5,"L":3.8,"K":-3.9,"M":1.9,"F":2.8,"P":-1.6,"S":-0.8,"T":-0.7,"W":-0.9,"Y":-1.3,"V":4.2}
CHARGED = set("DEKRH")
BASIC = set("KRH")
ACIDIC = set("DE")
AROMATIC = set("FWY")
POLAR = set("STNQCY")
HYDROPHOBIC = set("AILMFWVYP")
CTERM_AMIDE_MARKERS = ("CONH2", "NH2", "AMIDE")

# Interaction distance criteria used by the Docking Workbench.
# These are reported in the UI/export so users can interpret the contact table.
# Hydrogen bonds are treated as donor-acceptor heavy-atom distance proxies because
# many PDB/mmCIF files do not contain explicit hydrogens.
HYDROGEN_BOND_DA_CUTOFF_A = 3.9
HYDROGEN_BOND_STRONG_DA_CUTOFF_A = 3.5
HYDROPHOBIC_CONTACT_CUTOFF_A = 5.0
CONTACT_CUTOFF_A = 5.0
CLASH_CUTOFF_A = 2.0
CHARGE_PROXIMITY_CUTOFF_A = 5.0
POLAR_PROXIMITY_CUTOFF_A = 5.0
HBOND_CAPABLE = POLAR | BASIC | ACIDIC | set("YWHC")

def _residue_can_hbond(aa: str) -> bool:
    return str(aa or "").upper() in HBOND_CAPABLE

def _is_atom_hbond_donor(atom_row) -> bool:
    elem = str(atom_row.get("element", "")).upper()
    atom = str(atom_row.get("atom", "")).upper()
    aa = str(atom_row.get("aa", "")).upper()
    return elem in {"N", "O", "S"} and (aa in HBOND_CAPABLE or atom.startswith(("N", "O", "S")))

def _is_atom_hbond_acceptor(atom_row) -> bool:
    elem = str(atom_row.get("element", "")).upper()
    atom = str(atom_row.get("atom", "")).upper()
    aa = str(atom_row.get("aa", "")).upper()
    return elem in {"O", "N", "S"} and (aa in HBOND_CAPABLE or atom.startswith(("O", "N", "S")))

def _is_atom_hydrophobic(atom_row) -> bool:
    elem = str(atom_row.get("element", "")).upper()
    atom = str(atom_row.get("atom", "")).upper()
    aa = str(atom_row.get("aa", "")).upper()
    # Carbon-rich side chains and aromatic atoms are treated as hydrophobic
    # contact candidates. Backbone carbonyl carbon is excluded where possible.
    return aa in HYDROPHOBIC and elem in {"C", "S"} and atom not in {"C"}

def interaction_distance_criteria_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"metric":"hydrogen_bond_DA_cutoff", "value":HYDROGEN_BOND_DA_CUTOFF_A, "unit":"Angstrom", "interpretation":"donor-acceptor heavy-atom distance proxy", "method_note":"Used when explicit hydrogens/angles are unavailable; stronger contacts are typically <= 3.5 A."},
        {"metric":"hydrophobic_contact_cutoff", "value":HYDROPHOBIC_CONTACT_CUTOFF_A, "unit":"Angstrom", "interpretation":"hydrophobic residue/atom contact distance", "method_note":"Used for residue-level hydrophobic contact counting and atom-level hydrophobic contact labels."},
        {"metric":"generic_interface_contact_cutoff", "value":CONTACT_CUTOFF_A, "unit":"Angstrom", "interpretation":"generic residue-level target-peptide contact cutoff", "method_note":"Used for interface contact counting in the screening model."},
        {"metric":"steric_clash_cutoff", "value":CLASH_CUTOFF_A, "unit":"Angstrom", "interpretation":"distance below this is treated as a clash/covalent-range warning", "method_note":"Lower clash counts are better."},
    ], columns=["metric","value","unit","interpretation","method_note"])

def _residue_label(chain, resi, aa) -> str:
    """Human-readable residue label such as A:134D or 4Q."""
    chain = str(chain or "").strip()
    try:
        resi_txt = str(int(float(resi)))
    except Exception:
        resi_txt = str(resi or "?").strip()
    aa = str(aa or "X").strip().upper()[:1] or "X"
    return f"{chain}:{resi_txt}{aa}" if chain else f"{resi_txt}{aa}"

def _contact_columns() -> list[str]:
    # Readability-first contact table.  The visible table intentionally starts
    # with what users ask for: protein residue, peptide residue, distance, and
    # interaction class.  Window columns summarize the local interaction block.
    return [
        "protein_residue", "peptide_residue", "distance_A", "interaction",
        "protein_window", "peptide_window", "orientation", "pose_id",
        "target_residue", "pep_pos", "pep_aa", "target_chain", "target_resi", "target_aa",
        "cutoff_A", "note"
    ]

def _atom_contact_columns() -> list[str]:
    return [
        "target_residue", "target_chain", "target_resi", "target_resn", "target_atom",
        "peptide_residue", "peptide_chain", "peptide_resi", "peptide_resn", "peptide_atom",
        "distance_A", "cutoff_A", "contact_class", "note"
    ]


def _pose_columns() -> list[str]:
    return [
        "pose_rank", "pose_id", "conformation", "orientation",
        "contact_count", "centroid_overlap_warnings",
        "hydrophobic_proximities", "opposite_charge_proximities",
        "aromatic_proximities", "polar_residue_proximities", "min_centroid_distance_A",
        "rotation_z_deg", "translation_x_A", "translation_y_A", "translation_z_A",
        "center_x_A", "center_y_A", "center_z_A", "note"
    ]

# Common project aliases.  The canonical notation is used for metadata so
# N-terminal Ac and C-terminal NH2 are not lost when a user types an alias.
PEPTIDE_ALIASES = {
    "AHP8": "Ac-EEMQRR-NH2",
    "AHP-8": "Ac-EEMQRR-NH2",
    "AC-EEMQRR-NH2": "Ac-EEMQRR-NH2",
}

def canonical_peptide_notation(seq: str) -> str:
    raw = str(seq or "").strip()
    # Be permissive with laboratory notation such as "-Cha-", "-AEEA-",
    # "-dK-", "FITC -", or "Pal-".  The parser keeps chemical meaning while
    # removing cosmetic spaces and repeated dash separators.
    raw = re.sub(r"\s*[-–—]\s*", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    key = re.sub(r"[^A-Za-z0-9-]", "", raw).upper()
    return PEPTIDE_ALIASES.get(key, raw)

def peptide_notation_parts(seq: str) -> list[str]:
    """Return dash-separated peptide notation parts after alias/space cleanup.

    This keeps laboratory input such as ``FITC -Cha-AEEA-dK-NH2`` equivalent to
    ``FITC-Cha-AEEA-dK-NH2``.  It is intentionally notation-level, not a FASTA
    parser.
    """
    raw = canonical_peptide_notation(seq)
    raw = re.sub(r"\s*[-–—]\s*", "-", str(raw or "").strip())
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return [p.strip().strip("[]") for p in raw.split("-") if p.strip()]


def misplaced_nterm_modifier_tokens(seq: str) -> list[str]:
    """Return N-terminal-only modifier tokens that appear internally.

    Pal/Myr/FITC/FAM/TAMRA/Biotin/etc. are terminal chemicals by default in
    Pepforge notation.  If they appear after the first token, they are not treated
    as amino-acid-like residues.  Side-chain use should be written explicitly in a
    future notation such as K(Pal), Lys(Pal), or another side-chain attachment form.
    """
    parts = peptide_notation_parts(seq)
    if not parts:
        return []
    out = []
    # Ignore the first token because N-terminal modifiers are valid there.
    # Ignore the final token if it is a C-terminal marker.
    for idx, tok in enumerate(parts):
        norm = normalize_token(tok)
        if idx == 0:
            continue
        if norm in set(CTERM_AMIDE_MARKERS) or norm in {"COOH", "CO2H", "ACID", "OH", "CONH2", "AMIDE"}:
            continue
        if norm in NTERM_MODIFIERS:
            out.append(tok)
    return out


def terminal_modifier_policy_df(seq: str) -> pd.DataFrame:
    """Human-readable terminal chemistry policy rows for the UI/export."""
    misplaced = misplaced_nterm_modifier_tokens(seq)
    rows = []
    if misplaced:
        for tok in misplaced:
            rows.append({
                "metric": "misplaced_n_terminal_modifier",
                "value": tok,
                "note": f"{tok} is treated as an N-terminal modifier by default. Internal/side-chain use must be explicitly specified; it is not modeled as a normal residue.",
            })
    else:
        rows.append({"metric": "terminal_modifier_policy", "value": "ok", "note": "No N-terminal-only chemical modifier was detected in an internal peptide position."})
    return pd.DataFrame(rows, columns=["metric", "value", "note"])


CHEMICAL_DISPLAY_NAMES = {
    "PAL": "Palmitic acid", "MYR": "Myristic acid", "GAL": "Gallic acid",
    "CAF": "Caffeic acid", "NIC": "Nicotinic acid", "STEAR": "Stearic acid",
    "PALMITICACID": "Palmitic acid", "MYRISTICACID": "Myristic acid",
    "GALLICACID": "Gallic acid", "CAFFEICACID": "Caffeic acid", "NICOTINICACID": "Nicotinic acid",
}

def _display_token_name(token: str) -> str:
    key = normalize_token(token)
    return CHEMICAL_DISPLAY_NAMES.get(key, str(token or ""))

def has_terminal_notation(seq: str) -> bool:
    raw = str(seq or "").strip()
    if not raw:
        return False
    parsed = unified_parse_peptide(canonical_peptide_notation(raw))
    return bool(parsed.nterm or parsed.cterm)

def terminal_status_df(seq: str) -> pd.DataFrame:
    canonical = canonical_peptide_notation(seq)
    parsed = unified_parse_peptide(canonical)
    nterm = _display_token_name(parsed.nterm) if parsed.nterm else "free amine"
    cterm = parsed.cterm or "free acid"
    if parsed.nterm:
        n_note = "N-terminus is occupied by a terminal modifier/cap; do not treat it as a free N-terminal amine."
    else:
        n_note = "No N-terminal cap detected; treated as free amine."
    c_note = "C-terminus is amidated." if str(cterm).upper() in set(CTERM_AMIDE_MARKERS) else "No C-terminal amide detected; treated as free acid."
    rows = [
        {"field": "input_notation", "value": str(seq or "").strip() or "empty", "note": "User-entered peptide notation or alias."},
        {"field": "canonical_notation", "value": canonical or "empty", "note": "Alias-expanded notation used for terminal-state metadata."},
        {"field": "n_terminal", "value": nterm, "note": n_note},
        {"field": "c_terminal", "value": cterm, "note": c_note},
        {"field": "core_sequence", "value": parsed.core_sequence or "none", "note": "Residue sequence used for property estimates and docking screening."},
    ]
    misplaced = misplaced_nterm_modifier_tokens(canonical)
    if misplaced:
        rows.append({"field": "terminal_modifier_warning", "value": ";".join(misplaced), "note": "These tokens are N-terminal-only modifiers by default. Internal use requires explicit side-chain notation and external parameter review."})
    return pd.DataFrame(rows, columns=["field", "value", "note"])

THREE_TO_ONE = {
    "ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E","GLY":"G","HIS":"H","ILE":"I",
    "LEU":"L","LYS":"K","MET":"M","PHE":"F","PRO":"P","SER":"S","THR":"T","TRP":"W","TYR":"Y","VAL":"V",
    "MSE":"M","SEC":"C","PYL":"K","HYP":"P","ORN":"K","DAB":"K","DAP":"K","CIT":"R",
}
ONE_TO_THREE = {
    "A":"ALA", "R":"ARG", "N":"ASN", "D":"ASP", "C":"CYS",
    "Q":"GLN", "E":"GLU", "G":"GLY", "H":"HIS", "I":"ILE",
    "L":"LEU", "K":"LYS", "M":"MET", "F":"PHE", "P":"PRO",
    "S":"SER", "T":"THR", "W":"TRP", "Y":"TYR", "V":"VAL",
}

def parse_peptide_notation(seq: str) -> dict:
    p = unified_parse_peptide(canonical_peptide_notation(seq))
    return {"raw": p.raw, "nterm": p.nterm, "core": p.core_sequence, "cterm": p.cterm,
            "linker_tokens": p.linker_tokens, "aa_like_tokens": p.aa_like_tokens, "unknown_tokens": p.unknown_tokens}

def clean_sequence(seq: str) -> str:
    return parse_peptide_notation(seq).get("core", "")

def _split_peptide_model_tokens(seq: str):
    """Return ordered chemistry tokens without canonical-surrogate substitution.

    This table is descriptive metadata only.  Non-natural amino acids, linkers,
    labels and terminal chemicals retain their own token identity.  3D geometry
    is obtained from Structure Builder or an explicit PDB; unsupported chemistry
    is never silently replaced by Gly/Ala/Lys/etc.
    """
    sequence = canonical_peptide_notation(seq)
    if not sequence:
        return []
    from peptiforg_core.pymol_structure_builder import classify_tokens
    rows = []
    for item in classify_tokens(sequence):
        token = str(item.token or item.raw or "")
        cls = str(item.cls or "unknown")
        aa = ""
        if cls == "std_aa" and len(token) == 1 and token.upper() in AA_MASS:
            aa = token.upper()
        elif cls == "d_std_aa":
            raw = str(item.raw or token)
            if raw and raw[-1].upper() in AA_MASS:
                aa = raw[-1].upper()
        if cls in {"unknown", "unsupported"}:
            cls = "unsupported"
        rows.append({
            "token": token,
            "aa": aa or "X",
            "class": cls,
            "note": str(item.note or ""),
            "warning": str(item.warning or ""),
        })
    return rows


def peptide_token_compatibility_df(seq: str):
    seq = canonical_peptide_notation(seq)
    rows = _split_peptide_model_tokens(seq)
    parsed = unified_parse_peptide(seq)
    if not rows:
        return pd.DataFrame([{"metric":"token_status","value":"no peptide tokens","note":"Enter a peptide sequence or peptide PDB."}])
    counts = {}
    warnings = []
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
        if r.get("warning"):
            warnings.append(f"{r.get('token')}: {r.get('warning')}")
    supported_for_builder = counts.get("unsupported", 0) == 0
    out = [
        {"metric":"token_count","value":len(rows),"note":"Chemistry tokens parsed from the peptide notation."},
        {"metric":"d_amino_acid_count","value":counts.get("d_std_aa",0),"note":"D-residues retain stereochemistry in Structure Builder; no L-residue substitution is applied."},
        {"metric":"non_natural_count","value":counts.get("non_natural_aa",0),"note":"Non-natural residues retain their own Structure Builder templates when supported."},
        {"metric":"linker_count","value":counts.get("linker",0),"note":"Linkers retain their own connected chemistry when supported."},
        {"metric":"terminal_or_label_count","value":sum(counts.get(k,0) for k in ("n_terminal_modifier","c_terminal_modifier","n_terminal","c_terminal","label","chemical")),"note":"Terminal chemicals/labels are not counted as canonical amino acids."},
        {"metric":"unsupported_token_count","value":counts.get("unsupported",0),"note":"Unsupported tokens block sequence-derived 3D generation instead of being converted to canonical residues."},
        {"metric":"notation_warnings","value":"; ".join(warnings) if warnings else "none","note":"Warnings emitted by the chemistry-aware parser."},
        {"metric":"aa_like_tokens","value":";".join(parsed.aa_like_tokens) if parsed.aa_like_tokens else "none","note":"Recognized non-natural amino-acid tokens."},
        {"metric":"linker_tokens","value":";".join(parsed.linker_tokens) if parsed.linker_tokens else "none","note":"Recognized linker/spacer tokens."},
        {"metric":"structure_builder_status","value":"supported" if supported_for_builder else "review required","note":"Sequence-derived 3D screening uses Structure Builder coordinates; unsupported chemistry requires an explicit validated structure/template."},
    ]
    return pd.DataFrame(out)


def estimate_properties(seq: str):
    """Return transparent sequence descriptors without structural/binding claims.

    Values derived only from canonical residues are labelled as such. Modified
    chemistry is preserved in the token table/Structure Builder and is not folded
    into a fabricated total-MW, affinity, aggregation, disorder, or secondary-
    structure score.
    """
    seq = canonical_peptide_notation(seq)
    parsed = parse_peptide_notation(seq)
    core = parsed["core"]
    n = len(core)
    if n == 0:
        return pd.DataFrame([{"metric":"canonical_residue_count", "value":0, "note":"No canonical residues were parsed; inspect token compatibility/Structure Builder output."}])
    core_mw = sum(AA_MASS[a] for a in core) - 18.015*(n-1)
    if str(parsed["nterm"]).lower() == "ac":
        core_mw += 42.037
    if str(parsed["cterm"]).upper() in set(CTERM_AMIDE_MARKERS):
        core_mw -= 0.984
    basic_n = sum(1 for a in core if a in BASIC)
    acidic_n = sum(1 for a in core if a in ACIDIC)
    aromatic_n = sum(1 for a in core if a in AROMATIC)
    hydrophobic_n = sum(1 for a in core if a in HYDROPHOBIC)
    polar_n = sum(1 for a in core if a in POLAR)
    pro_gly_n = sum(1 for a in core if a in "PG")
    rows = [
        ("parsed_core_sequence", core, "Canonical residue core parsed from the notation."),
        ("n_terminal_modifier", parsed["nterm"] or "free", "Parsed terminal state; chemistry is handled separately from the canonical residue core."),
        ("c_terminal_modifier", parsed["cterm"] or "free acid", "Parsed terminal state."),
        ("canonical_residue_count", n, "Canonical residues only."),
        ("canonical_core_MW_Da", round(core_mw, 3), "Canonical core plus simple Ac/NH2 terminal correction only; not a total MW for other modifications/linkers/non-natural residues."),
        ("hydrophobicity_KD_avg", round(sum(HYDRO.get(a,0) for a in core)/n, 3), "Kyte-Doolittle average over canonical residues only."),
        ("basic_residue_count", basic_n, "K/R/H count in canonical core."),
        ("acidic_residue_count", acidic_n, "D/E count in canonical core."),
        ("aromatic_fraction", round(aromatic_n/n, 3), "F/W/Y fraction in canonical core."),
        ("hydrophobic_fraction", round(hydrophobic_n/n, 3), "A/I/L/M/F/W/V/Y/P fraction in canonical core."),
        ("charged_fraction", round((basic_n+acidic_n)/n, 3), "D/E/K/R/H fraction in canonical core."),
        ("polar_fraction", round(polar_n/n, 3), "S/T/N/Q/C/Y fraction in canonical core."),
        ("pro_gly_fraction", round(pro_gly_n/n, 3), "P/G fraction; raw composition descriptor, not a disorder prediction."),
        ("d_amino_acid_count", sum(1 for r in _split_peptide_model_tokens(seq) if r.get("class") == "d_std_aa"), "Count from chemistry-aware token parsing."),
        ("non_natural_token_count", sum(1 for r in _split_peptide_model_tokens(seq) if r.get("class") == "non_natural_aa"), "Count only; no canonical surrogate score is assigned."),
        ("linker_token_count", sum(1 for r in _split_peptide_model_tokens(seq) if r.get("class") == "linker"), "Count only; linker geometry is handled by Structure Builder."),
        ("unsupported_token_count", sum(1 for r in _split_peptide_model_tokens(seq) if r.get("class") == "unsupported"), "Unsupported chemistry requires review; it is not silently substituted."),
    ]
    return pd.DataFrame([{"metric":a,"value":b,"note":c} for a,b,c in rows])


def residue_map_df(seq: str):
    """Residue-level canonical chemistry descriptors only."""
    core = clean_sequence(seq)
    rows = []
    for i, aa in enumerate(core, start=1):
        cls=[]
        if aa in BASIC: cls.append("basic")
        if aa in ACIDIC: cls.append("acidic")
        if aa in AROMATIC: cls.append("aromatic")
        if aa in HYDROPHOBIC: cls.append("hydrophobic")
        if aa in POLAR: cls.append("polar")
        rows.append({"position": i, "residue": aa, "class": ", ".join(cls), "hydrophobicity_KD": HYDRO.get(aa, 0)})
    return pd.DataFrame(rows)


def structure_risk_df(props: pd.DataFrame):
    """Expose raw composition descriptors instead of fabricated risk classes."""
    def get(k, default=0.0):
        try:
            return float(props.loc[props.metric==k, "value"].iloc[0])
        except Exception:
            return default
    rows = [
        {"risk":"hydrophobic_fraction", "score":get("hydrophobic_fraction"), "level":"descriptor", "note":"Raw canonical-core composition; not an aggregation prediction."},
        {"risk":"aromatic_fraction", "score":get("aromatic_fraction"), "level":"descriptor", "note":"Raw canonical-core composition."},
        {"risk":"charged_fraction", "score":get("charged_fraction"), "level":"descriptor", "note":"Raw canonical-core composition; not a binding prediction."},
        {"risk":"pro_gly_fraction", "score":get("pro_gly_fraction"), "level":"descriptor", "note":"Raw P/G composition; not a disorder/flexibility probability."},
    ]
    return pd.DataFrame(rows)


def amphipathic_window_df(seq: str, window: int = 7):
    """Return sliding-window composition descriptors without a fake hydrophobic moment."""
    core = clean_sequence(seq)
    cols=["start","end","window_sequence","charged_fraction","hydrophobic_fraction","aromatic_fraction","note"]
    if not core:
        return pd.DataFrame(columns=cols)
    rows=[]
    for i in range(0, max(1, len(core)-window+1)):
        w=core[i:i+window]
        rows.append({
            "start":i+1,
            "end":i+len(w),
            "window_sequence":w,
            "charged_fraction":round(sum(1 for a in w if a in CHARGED)/len(w),3),
            "hydrophobic_fraction":round(sum(1 for a in w if a in HYDROPHOBIC)/len(w),3),
            "aromatic_fraction":round(sum(1 for a in w if a in AROMATIC)/len(w),3),
            "note":"Observed composition only; no amphipathic moment is inferred without a defined conformation.",
        })
    return pd.DataFrame(rows, columns=cols)


def _safe_float(text: str, default=0.0):
    try: return float(text)
    except Exception: return default

def parse_mmcif_atoms(path: str | Path):
    """Minimal mmCIF atom_site parser for complex structure preparation/structure preparation-style structures.

    It extracts the same columns as parse_pdb_atoms. This is intentionally
    lightweight: it supports common whitespace-separated atom_site loops and
    quoted values, then falls back safely if the file is not an atom_site mmCIF.
    """
    import shlex
    p = Path(path) if path else None
    cols = ["record","atom","resn","chain","resi","x","y","z","element","aa"]
    if not p or not p.exists():
        return pd.DataFrame(columns=cols)
    lines = p.read_text(errors="ignore").splitlines()
    rows=[]; i=0
    while i < len(lines):
        if lines[i].strip() != "loop_":
            i += 1; continue
        i += 1; headers=[]
        while i < len(lines) and lines[i].startswith("_atom_site."):
            headers.append(lines[i].strip()); i += 1
        if not headers:
            continue
        hmap={h.split('.',1)[1]: idx for idx,h in enumerate(headers)}
        needed = ["Cartn_x","Cartn_y","Cartn_z"]
        if not all(k in hmap for k in needed):
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") and lines[i].strip() != "loop_": i += 1
            continue
        while i < len(lines):
            s=lines[i].strip()
            if not s or s.startswith("#") or s == "loop_" or s.startswith("_"):
                break
            try:
                parts=shlex.split(s)
            except Exception:
                parts=s.split()
            if len(parts) >= len(headers):
                def get(*names, default=""):
                    for name in names:
                        if name in hmap and hmap[name] < len(parts):
                            val=parts[hmap[name]]
                            if val not in (".", "?"):
                                return val
                    return default
                group=get("group_PDB", default="ATOM")
                atom=get("auth_atom_id","label_atom_id")
                resn=get("auth_comp_id","label_comp_id").upper()
                chain=get("auth_asym_id","label_asym_id", default="?")
                resi=get("auth_seq_id","label_seq_id", default="")
                try:
                    x=float(get("Cartn_x")); y=float(get("Cartn_y")); z=float(get("Cartn_z"))
                except (TypeError, ValueError):
                    i += 1
                    continue
                elem=get("type_symbol", default=(atom[:1] or "")).upper()
                rows.append({"record":group,"atom":atom,"resn":resn,"chain":chain,"resi":resi,"x":x,"y":y,"z":z,"element":elem,"aa":THREE_TO_ONE.get(resn,"X")})
            i += 1
        if rows:
            break
    return pd.DataFrame(rows, columns=cols)

def parse_pdb_atoms(path: str | Path):
    p = Path(path) if path else None
    cols=["record","atom","resn","chain","resi","x","y","z","element","aa"]
    if not p or not p.exists():
        return pd.DataFrame(columns=cols)
    # complex structure preparation commonly exports mmCIF. Accept it directly.
    if p.suffix.lower() in {".cif", ".mmcif"}:
        return parse_mmcif_atoms(p)
    rows=[]
    for line in p.read_text(errors="ignore").splitlines():
        if not line.startswith(("ATOM", "HETATM")): continue
        atom=line[12:16].strip(); resn=line[17:20].strip().upper(); chain=line[21].strip() or "?"; resi=line[22:26].strip()
        try:
            x=float(line[30:38]); y=float(line[38:46]); z=float(line[46:54])
        except (TypeError, ValueError):
            continue
        elem=(line[76:78].strip() or atom[0]).upper()
        rows.append({"record":line[:6].strip(),"atom":atom,"resn":resn,"chain":chain,"resi":resi,"x":x,"y":y,"z":z,"element":elem,"aa":THREE_TO_ONE.get(resn,"X")})
    df=pd.DataFrame(rows, columns=cols)
    if df.empty:
        # Some AF/affinity scoring-adjacent files are named .txt/.pdb but contain mmCIF text.
        return parse_mmcif_atoms(p)
    return df

def pdb_summary_df(path: str | Path | None):
    p = Path(path) if path else None
    try:
        atoms=parse_pdb_atoms(p) if p else pd.DataFrame()
    except Exception as exc:
        return pd.DataFrame([
            {"field":"file","value":str(p) if p else "","note":"target path received by Docking Workbench"},
            {"field":"status","value":"parse error","note":str(exc)},
            {"field":"action","value":"check file format/path","note":"PDB, CIF, and mmCIF are supported; non-ASCII paths are normalized internally when possible."},
        ])
    if atoms.empty:
        return pd.DataFrame([
            {"field":"file","value":p.name if p else "","note":"target path received"},
            {"field":"status","value":"no ATOM/HETATM parsed","note":"The file was missing, empty, or no structure atoms were parsed."},
            {"field":"path","value":str(p) if p else "","note":"Use Prepare Target or select a valid PDB/CIF/mmCIF file."},
        ])
    residues=atoms.drop_duplicates(["chain","resi"]); chains=sorted(atoms["chain"].dropna().unique().tolist())
    center=(atoms[["x","y","z"]].mean()).to_dict(); radius=float((((atoms[["x","y","z"]]-pd.Series(center))**2).sum(axis=1)**0.5).max())
    records=atoms["record"].astype(str).value_counts().to_dict() if "record" in atoms.columns else {}
    return pd.DataFrame([
        {"field":"file","value":Path(path).name,"note":"imported target structure file"},
        {"field":"format","value":Path(path).suffix.lower().lstrip('.') or "pdb/text","note":"PDB/CIF/mmCIF parser path"},
        {"field":"atom_count","value":int(len(atoms)),"note":"parsed ATOM/HETATM records; record mix="+str(records)},
        {"field":"residue_count","value":int(len(residues)),"note":"unique chain/residue identifiers"},
        {"field":"chain_count","value":len(chains),"note":"chains: "+",".join(chains[:12])},
        {"field":"center_xyz","value":f"{center['x']:.2f}, {center['y']:.2f}, {center['z']:.2f}","note":"geometric center"},
        {"field":"approx_radius_A","value":round(radius,2),"note":"max atom distance from center"},
    ])

def receptor_residue_points(atoms: pd.DataFrame):
    if atoms.empty:
        return pd.DataFrame(columns=["chain","resi","resn","aa","x","y","z","class"])
    preferred=atoms[atoms["atom"].isin(["CA","CB","P"])]
    if preferred.empty: preferred=atoms.copy()
    grouped=preferred.groupby(["chain","resi","resn","aa"], dropna=False)[["x","y","z"]].mean().reset_index()
    def cls(aa):
        out=[]
        if aa in BASIC: out.append("basic")
        if aa in ACIDIC: out.append("acidic")
        if aa in HYDROPHOBIC: out.append("hydrophobic")
        if aa in AROMATIC: out.append("aromatic")
        if aa in POLAR: out.append("polar")
        return ",".join(out) or "other"
    grouped["class"]=grouped["aa"].map(cls)
    return grouped

def _points_from_structure_builder_metadata(pdb_path: str | Path, metadata_path: str | Path | None = None) -> pd.DataFrame:
    """Convert a Structure Builder all-atom model into token-level 3D points.

    RDKit PDB export may label the connected molecule as a single ``UNL``
    residue.  Pepforge's Structure Builder writes ``atom_ranges`` metadata that
    preserves the original peptide/modification units.  This helper uses those
    real generated coordinates instead of inventing canonical surrogate residues.
    """
    atoms = parse_pdb_atoms(pdb_path)
    cols = ["pep_pos", "aa", "token", "token_class", "x", "y", "z"]
    if atoms.empty:
        return pd.DataFrame(columns=cols)
    heavy = atoms[atoms["element"].astype(str).str.upper() != "H"].reset_index(drop=True)
    meta_path = Path(metadata_path) if metadata_path else Path(pdb_path).with_suffix(".json")
    if not meta_path.exists():
        return pd.DataFrame(columns=cols)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame(columns=cols)
    ranges = meta.get("atom_ranges") or []
    rows = []
    unit_index = 0
    for item in ranges:
        try:
            start = int(item.get("heavy_start_1based")) - 1
            stop = int(item.get("heavy_end_1based"))
        except (TypeError, ValueError):
            continue
        if start < 0 or stop <= start or start >= len(heavy):
            continue
        block = heavy.iloc[start:min(stop, len(heavy))]
        if block.empty:
            continue
        token = str(item.get("token") or "")
        kind = str(item.get("kind") or "unknown")
        # C-terminal atoms are part of the preceding residue and should not
        # become an extra peptide residue/contact position.
        if kind in {"c_terminal", "c_terminal_atom", "c_terminal_modifier"}:
            continue
        unit_index += 1
        up = token.upper()
        aa = ""
        if kind == "std_aa" and len(token) == 1 and up in AA_MASS:
            aa = up
        elif kind == "d_std_aa" and len(token) >= 2 and token[-1].upper() in AA_MASS:
            aa = token[-1].upper()
        rows.append({
            "pep_pos": unit_index,
            "aa": aa or "X",
            "token": token,
            "token_class": kind,
            "x": float(block["x"].mean()),
            "y": float(block["y"].mean()),
            "z": float(block["z"].mean()),
        })
    return pd.DataFrame(rows, columns=cols)


def build_peptide_structure_bundle(
    seq: str,
    output_dir: str | Path,
    name: str = "docking_peptide",
    *,
    num_confs: int = 1,
    max_iters: int = 20,
    num_threads: int = 2,
):
    """Build a persistent Structure Builder model and token-centroid table.

    Docking only needs a chemically faithful coordinate seed for rigid-body
    geometry screening, so this internal bridge requests one lightly optimized
    conformer. A visible, family-diverse Top 5 ensemble remains the separate PSB
    workflow and should not be regenerated for every docking preview.
    """
    sequence = canonical_peptide_notation(seq)
    if not sequence:
        raise ValueError("Peptide sequence is empty.")
    from peptiforg_core.pymol_structure_builder import (
        export_modified_peptide_coordinate_seed,
        export_modified_peptide_structure,
    )
    if int(num_confs) <= 1:
        paths = export_modified_peptide_coordinate_seed(
            sequence, output_dir, name=name,
            max_iters=max_iters, num_threads=num_threads,
        )
    else:
        paths = export_modified_peptide_structure(
            sequence, output_dir, name=name,
            num_confs=num_confs, max_iters=max_iters, num_threads=num_threads,
        )
    points = _points_from_structure_builder_metadata(paths["pdb"], paths.get("json"))
    if points.empty:
        raise ValueError("Structure Builder produced no token-level peptide coordinates.")
    return points.copy(), dict(paths)


def apply_pose_transform_to_pdb(source_pdb: str | Path, output_pdb: str | Path, pose_row) -> Path:
    """Apply the recorded rigid-body Z rotation/translation to atomic PDB coordinates."""
    src=Path(source_pdb); dst=Path(output_pdb)
    if not src.exists():
        raise FileNotFoundError(src)
    def f(key, default=0.0):
        try: return float(pose_row.get(key, default) or default)
        except Exception: return float(default)
    cx,cy,cz=f("center_x_A"),f("center_y_A"),f("center_z_A")
    tx,ty,tz=f("translation_x_A"),f("translation_y_A"),f("translation_z_A")
    angle=math.radians(f("rotation_z_deg")); ca,sa=math.cos(angle),math.sin(angle)
    out=[]
    for line in src.read_text(encoding="utf-8",errors="ignore").splitlines():
        if line.startswith(("ATOM","HETATM")) and len(line)>=54:
            try:
                x=float(line[30:38])-cx; y=float(line[38:46])-cy; z=float(line[46:54])-cz
            except ValueError:
                continue
            xr=x*ca-y*sa+tx; yr=x*sa+y*ca+ty; zr=z+tz
            line=f"{line[:30]}{xr:8.3f}{yr:8.3f}{zr:8.3f}{line[54:]}"
        out.append(line)
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text("\n".join(out)+"\n",encoding="utf-8")
    return dst


def apply_pose_transform_to_atoms(atoms: pd.DataFrame, pose_row) -> pd.DataFrame:
    """Apply a recorded rigid-body candidate transform to parsed atomic coordinates."""
    if atoms is None or atoms.empty:
        return pd.DataFrame(columns=getattr(atoms,"columns",[]))
    out=atoms.copy()
    def f(key, default=0.0):
        try: return float(pose_row.get(key,default) or default)
        except Exception: return float(default)
    cx,cy,cz=f("center_x_A"),f("center_y_A"),f("center_z_A")
    tx,ty,tz=f("translation_x_A"),f("translation_y_A"),f("translation_z_A")
    a=math.radians(f("rotation_z_deg")); ca,sa=math.cos(a),math.sin(a)
    x=out["x"].astype(float)-cx; y=out["y"].astype(float)-cy; z=out["z"].astype(float)-cz
    out["x"]=x*ca-y*sa+tx; out["y"]=x*sa+y*ca+ty; out["z"]=z+tz
    return out


def atomic_structure_pdb(atoms: pd.DataFrame, title: str, forced_chain: str | None = None) -> str:
    """Serialize actual parsed atomic coordinates to PDB text."""
    lines=[f"REMARK {title}", "REMARK Coordinates are atomic coordinates; Pepforge ranking is not an energy/affinity calculation."]
    serial=1
    if atoms is not None and not atoms.empty:
        for _,a in atoms.iterrows():
            atom=str(a.get("atom","C"))[:4]; resn=str(a.get("resn","UNK") or "UNK")[:3]
            chain=(forced_chain or str(a.get("chain","A") or "A"))[:1]
            try: resi=int(float(a.get("resi",serial)))
            except Exception: resi=serial
            elem=str(a.get("element",atom[:1] or "C") or "C")[:2].rjust(2)
            lines.append(f"ATOM  {serial:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {float(a['x']):8.3f}{float(a['y']):8.3f}{float(a['z']):8.3f}  1.00  0.00          {elem}")
            serial+=1
    lines.append("END")
    return "\n".join(lines)+"\n"


def atomic_complex_pdb(target_atoms: pd.DataFrame, peptide_atoms: pd.DataFrame, contacts: pd.DataFrame | None = None) -> str:
    """Create a PDB from actual parsed atomic coordinates; no centroid pseudo-atoms are inserted."""
    lines=[
        "REMARK Pepforge coordinate complex candidate",
        "REMARK Target and peptide entries below are actual parsed/generated atomic coordinates.",
        "REMARK Pepforge local geometry ranking is not a docking energy or affinity calculation.",
    ]
    if contacts is not None and isinstance(contacts,pd.DataFrame) and not contacts.empty:
        for _,r in contacts.head(40).iterrows():
            lines.append(f"REMARK CENTROID_CONTACT {r.get('peptide_residue','')} -> {r.get('target_residue','')} dist={r.get('distance_A','')}A {r.get('interaction','')}")
    serial=1
    def emit(df, forced_chain=None):
        nonlocal serial
        if df is None or df.empty: return
        for _,a in df.iterrows():
            atom=str(a.get("atom","C"))[:4]; resn=str(a.get("resn","UNK") or "UNK")[:3]
            chain=(forced_chain or str(a.get("chain","A") or "A"))[:1]
            try: resi=int(float(a.get("resi",serial)))
            except Exception: resi=serial
            elem=str(a.get("element",atom[:1] or "C") or "C")[:2].rjust(2)
            lines.append(f"ATOM  {serial:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {float(a['x']):8.3f}{float(a['y']):8.3f}{float(a['z']):8.3f}  1.00  0.00          {elem}")
            serial+=1
    emit(target_atoms)
    lines.append("TER")
    emit(peptide_atoms, forced_chain="P")
    lines.append("END")
    return "\n".join(lines)+"\n"


def generate_peptide_structure_points(seq: str) -> pd.DataFrame:
    """Generate Structure Builder token-centroid coordinates for local screening."""
    with tempfile.TemporaryDirectory(prefix="pepforge_docking_structure_") as td:
        points, _paths = build_peptide_structure_bundle(seq, td, name="docking_peptide")
        return points.copy()


def pdb_to_peptide_points(path: str | Path):
    p = Path(path)
    sidecar = p.with_suffix(".json")
    if sidecar.exists():
        mapped = _points_from_structure_builder_metadata(p, sidecar)
        if not mapped.empty:
            return mapped
    atoms = parse_pdb_atoms(p)
    pts = receptor_residue_points(atoms)
    if pts.empty:
        return pd.DataFrame(columns=["pep_pos","aa","token","token_class","x","y","z"])
    pts = pts.reset_index(drop=True)
    return pd.DataFrame({
        "pep_pos": range(1,len(pts)+1),
        "aa": pts["aa"].tolist(),
        "token": pts["aa"].tolist(),
        "token_class": ["pdb_residue"] * len(pts),
        "x": pts["x"].tolist(), "y": pts["y"].tolist(), "z": pts["z"].tolist()
    })


def _directions():
    base=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(1,-1,0),(-1,1,0),(-1,-1,0),(1,0,1),(1,0,-1),(-1,0,1),(-1,0,-1),(0,1,1),(0,1,-1),(0,-1,1),(0,-1,-1)]
    out=[]
    for x,y,z in base:
        n=math.sqrt(x*x+y*y+z*z); out.append((x/n,y/n,z/n))
    return out

def _score_contacts(receptor: pd.DataFrame, pep: pd.DataFrame, pose_id: str):
    """Measure transparent residue/token-centroid proximities for one candidate pose.

    No thermodynamic, hydrogen-bond, or electrostatic energy is inferred here.
    The peptide side is represented by Structure Builder token centroids; the
    receptor side is represented by residue points.  Atom-level geometry is
    reported separately when both structures contain atomic coordinates.
    """
    contacts = overlaps = hyd = charge = aromatic = polar = 0
    min_d = float("inf")
    contact_rows = []
    if receptor is None or receptor.empty or pep is None or pep.empty:
        return contacts, overlaps, hyd, charge, aromatic, polar, min_d, contact_rows
    for _, pr in pep.iterrows():
        dx = receptor["x"] - pr["x"]
        dy = receptor["y"] - pr["y"]
        dz = receptor["z"] - pr["z"]
        dist = (dx*dx + dy*dy + dz*dz) ** 0.5
        if dist.empty:
            continue
        min_d = min(min_d, float(dist.min()))
        close = receptor[dist <= CONTACT_CUTOFF_A].copy()
        close["_distance"] = dist[dist <= CONTACT_CUTOFF_A]
        close = close.sort_values("_distance").head(12)
        for _, rr in close.iterrows():
            d = float(rr["_distance"])
            paa = str(pr.get("aa", "X")).upper()[:1] or "X"
            raa = str(rr.get("aa", "X")).upper()[:1] or "X"
            labels = ["centroid_contact"]
            cutoff_used = CONTACT_CUTOFF_A
            contacts += 1
            if paa in HYDROPHOBIC and raa in HYDROPHOBIC and d <= HYDROPHOBIC_CONTACT_CUTOFF_A:
                hyd += 1; labels.append("hydrophobic_proximity")
            if paa in AROMATIC and raa in AROMATIC and d <= HYDROPHOBIC_CONTACT_CUTOFF_A:
                aromatic += 1; labels.append("aromatic_proximity")
            if ((paa in BASIC and raa in ACIDIC) or (paa in ACIDIC and raa in BASIC)) and d <= CHARGE_PROXIMITY_CUTOFF_A:
                charge += 1; labels.append("opposite_charge_proximity"); cutoff_used = CHARGE_PROXIMITY_CUTOFF_A
            if _residue_can_hbond(paa) and _residue_can_hbond(raa) and d <= POLAR_PROXIMITY_CUTOFF_A:
                polar += 1; labels.append("polar_residue_proximity"); cutoff_used = POLAR_PROXIMITY_CUTOFF_A
            if d <= CLASH_CUTOFF_A:
                overlaps += 1; labels.append("centroid_overlap_warning"); cutoff_used = CLASH_CUTOFF_A
            pep_label = _residue_label("", pr.get("pep_pos", "?"), paa)
            target_label = _residue_label(rr.get("chain", ""), rr.get("resi", "?"), raa)
            orientation = "reverse_C_to_N" if "reverse_C_to_N" in str(pose_id) else ("forward_N_to_C" if "forward_N_to_C" in str(pose_id) else "imported_or_direct")
            contact_rows.append({
                "protein_residue": target_label, "peptide_residue": pep_label,
                "distance_A": round(d, 2), "interaction": ";".join(dict.fromkeys(labels)),
                "pose_id": pose_id, "orientation": orientation, "protein_window": "", "peptide_window": "",
                "target_residue": target_label, "pep_pos": int(pr.get("pep_pos", 0) or 0),
                "pep_aa": paa, "target_chain": rr.get("chain", ""), "target_resi": rr.get("resi", ""),
                "target_aa": raa, "cutoff_A": cutoff_used,
                "note": "Residue/token-centroid geometry only; inspect atom-level contacts separately when available.",
            })
    return contacts, overlaps, hyd, charge, aromatic, polar, min_d, contact_rows




def analyze_atom_level_contact_frames(t: pd.DataFrame, p: pd.DataFrame, cutoff_A: float = HYDROPHOBIC_CONTACT_CUTOFF_A):
    """Analyze actual atom-coordinate proximities between target and peptide frames."""
    cols=_atom_contact_columns()
    if t is None or p is None or t.empty or p.empty:
        return pd.DataFrame(columns=cols)
    rows=[]
    for _,pa in p.iterrows():
        dx=t["x"]-pa["x"]; dy=t["y"]-pa["y"]; dz=t["z"]-pa["z"]
        dist=(dx*dx+dy*dy+dz*dz)**0.5
        close=t[dist<=cutoff_A].copy(); close["_distance"]=dist[dist<=cutoff_A]
        for _,ta in close.sort_values("_distance").head(80).iterrows():
            d=float(ta["_distance"]); cls=[]; cutoff_used=CONTACT_CUTOFF_A
            if d<=CLASH_CUTOFF_A:
                cls.append("atom_overlap_or_covalent_range_warning"); cutoff_used=CLASH_CUTOFF_A
            hb_pair=(_is_atom_hbond_donor(pa) and _is_atom_hbond_acceptor(ta)) or (_is_atom_hbond_acceptor(pa) and _is_atom_hbond_donor(ta))
            if hb_pair and d<=HYDROGEN_BOND_DA_CUTOFF_A:
                cls.append("hbond_distance_candidate"); cutoff_used=HYDROGEN_BOND_DA_CUTOFF_A
            if ((str(pa.get("aa","")).upper() in BASIC and str(ta.get("aa","")).upper() in ACIDIC) or (str(pa.get("aa","")).upper() in ACIDIC and str(ta.get("aa","")).upper() in BASIC)) and d<=CHARGE_PROXIMITY_CUTOFF_A:
                cls.append("opposite_charge_residue_atom_proximity"); cutoff_used=CHARGE_PROXIMITY_CUTOFF_A
            if _is_atom_hydrophobic(pa) and _is_atom_hydrophobic(ta) and d<=HYDROPHOBIC_CONTACT_CUTOFF_A:
                cls.append("hydrophobic_atom_proximity"); cutoff_used=HYDROPHOBIC_CONTACT_CUTOFF_A
            if not cls:
                cls.append("atom_proximity")
            target_label=_residue_label(ta.get("chain",""),ta.get("resi","?"),ta.get("aa",ta.get("resn","X")))
            pep_label=_residue_label(pa.get("chain",""),pa.get("resi","?"),pa.get("aa",pa.get("resn","X")))
            rows.append({
                "target_residue":target_label,"target_chain":ta["chain"],"target_resi":ta["resi"],"target_resn":ta["resn"],"target_atom":ta["atom"],
                "peptide_residue":pep_label,"peptide_chain":pa["chain"],"peptide_resi":pa["resi"],"peptide_resn":pa["resn"],"peptide_atom":pa["atom"],
                "distance_A":round(d,2),"cutoff_A":cutoff_used,"contact_class":";".join(dict.fromkeys(cls)),
                "note":"Coordinate-derived atom proximity. H-bond labels are distance candidates only; donor-H-acceptor angle is not asserted."
            })
    return pd.DataFrame(rows,columns=cols)


def analyze_atom_level_contacts(target_pdb: str | Path | None, peptide_pdb: str | Path | None, cutoff_A: float = HYDROPHOBIC_CONTACT_CUTOFF_A):
    return analyze_atom_level_contact_frames(parse_pdb_atoms(target_pdb), parse_pdb_atoms(peptide_pdb), cutoff_A=cutoff_A)


def analyze_pdb_pdb_contacts(target_pdb: str | Path | None, peptide_pdb: str | Path | None):
    receptor = receptor_residue_points(parse_pdb_atoms(target_pdb))
    pep = pdb_to_peptide_points(peptide_pdb)
    if receptor.empty or pep.empty:
        return pd.DataFrame(columns=_pose_columns()), pd.DataFrame(columns=_contact_columns())
    contacts, overlaps, hyd, charge, aromatic, polar, min_d, rows = _score_contacts(receptor, pep, "imported_pdb")
    poses = pd.DataFrame([{
        "pose_rank": 1, "pose_id":"imported_pdb", "conformation":"imported", "orientation":"imported_or_direct",
        "contact_count":contacts, "centroid_overlap_warnings":overlaps,
        "hydrophobic_proximities":hyd, "opposite_charge_proximities":charge,
        "aromatic_proximities":aromatic, "polar_residue_proximities":polar,
        "min_centroid_distance_A":round(min_d,2) if math.isfinite(min_d) else "",
        "rotation_z_deg":0.0, "translation_x_A":0.0, "translation_y_A":0.0, "translation_z_A":0.0,
        "center_x_A":0.0, "center_y_A":0.0, "center_z_A":0.0,
        "note":"Direct geometry analysis of the supplied target/peptide structures; no pose search or affinity inference."
    }], columns=_pose_columns())
    return poses, pd.DataFrame(rows, columns=_contact_columns())



def pdb_points_from_atoms(atoms: pd.DataFrame):
    pts = receptor_residue_points(atoms)
    if pts.empty:
        return pd.DataFrame(columns=["pep_pos","aa","x","y","z"])
    pts = pts.reset_index(drop=True)
    return pd.DataFrame({"pep_pos": range(1, len(pts)+1), "aa": pts["aa"].tolist(), "x": pts["x"].tolist(), "y": pts["y"].tolist(), "z": pts["z"].tolist()})


def complex_chain_split(path: str | Path | None):
    atoms = parse_pdb_atoms(path)
    if atoms.empty or "chain" not in atoms:
        return atoms, pd.DataFrame(), "", "no atoms/chains parsed"
    counts = atoms.groupby("chain")["resi"].nunique().sort_values()
    if len(counts) < 2:
        return atoms, pd.DataFrame(), "", "single-chain structure; provide peptide sequence or peptide PDB for contact analysis"
    peptide_chain = str(counts.index[0])
    peptide_atoms = atoms[atoms["chain"].astype(str) == peptide_chain].copy()
    target_atoms = atoms[atoms["chain"].astype(str) != peptide_chain].copy()
    note = f"auto complex split: shortest chain '{peptide_chain}' treated as peptide; remaining chains treated as target"
    return target_atoms, peptide_atoms, peptide_chain, note


def structure_has_multiple_chains(path: str | Path | None) -> bool:
    try:
        atoms = parse_pdb_atoms(path)
        return (not atoms.empty) and atoms["chain"].nunique() >= 2
    except Exception:
        return False


def analyze_complex_structure_contacts(path: str | Path | None):
    target_atoms, peptide_atoms, pep_chain, note = complex_chain_split(path)
    receptor = receptor_residue_points(target_atoms)
    pep = pdb_points_from_atoms(peptide_atoms)
    if receptor.empty or pep.empty:
        poses = pd.DataFrame([{
            "pose_rank":"", "pose_id":"complex_import", "conformation":"imported_complex", "orientation":"imported_or_direct",
            "contact_count":"", "centroid_overlap_warnings":"", "hydrophobic_proximities":"",
            "opposite_charge_proximities":"", "aromatic_proximities":"", "polar_residue_proximities":"",
            "min_centroid_distance_A":"", "rotation_z_deg":0.0, "translation_x_A":0.0, "translation_y_A":0.0,
            "translation_z_A":0.0, "center_x_A":0.0, "center_y_A":0.0, "center_z_A":0.0, "note":note
        }], columns=_pose_columns())
        return poses, pd.DataFrame(columns=_contact_columns()), pd.DataFrame(columns=_atom_contact_columns()), pep
    contacts, overlaps, hyd, charge, aromatic, polar, min_d, rows = _score_contacts(receptor, pep, "complex_import")
    poses = pd.DataFrame([{
        "pose_rank":1, "pose_id":"complex_import", "conformation":"imported_complex", "orientation":"imported_or_direct",
        "contact_count":contacts, "centroid_overlap_warnings":overlaps, "hydrophobic_proximities":hyd,
        "opposite_charge_proximities":charge, "aromatic_proximities":aromatic, "polar_residue_proximities":polar,
        "min_centroid_distance_A":round(min_d,2) if math.isfinite(min_d) else "", "rotation_z_deg":0.0,
        "translation_x_A":0.0, "translation_y_A":0.0, "translation_z_A":0.0,
        "center_x_A":0.0, "center_y_A":0.0, "center_z_A":0.0, "note":note
    }], columns=_pose_columns())
    atom_rows=[]
    for _, pa in peptide_atoms.iterrows():
        dx=target_atoms["x"]-pa["x"]; dy=target_atoms["y"]-pa["y"]; dz=target_atoms["z"]-pa["z"]
        dist=(dx*dx+dy*dy+dz*dz)**0.5
        close=target_atoms[dist<=CONTACT_CUTOFF_A].copy(); close["_distance"]=dist[dist<=CONTACT_CUTOFF_A]
        for _, ta in close.iterrows():
            atom_rows.append({
                "target_residue":_residue_label(ta.get("chain",""),ta.get("resi",""),ta.get("aa",ta.get("resn","X"))),
                "target_chain":ta["chain"],"target_resi":ta["resi"],"target_resn":ta["resn"],"target_atom":ta["atom"],
                "peptide_residue":_residue_label(pa.get("chain",""),pa.get("resi",""),pa.get("aa",pa.get("resn","X"))),
                "peptide_chain":pa["chain"],"peptide_resi":pa["resi"],"peptide_resn":pa["resn"],"peptide_atom":pa["atom"],
                "distance_A":round(float(ta["_distance"]),2),"cutoff_A":CONTACT_CUTOFF_A,"contact_class":"atom_proximity",
                "note":"Atomic-coordinate proximity in the supplied complex; no bond or affinity is inferred."
            })
    return poses, pd.DataFrame(rows, columns=_contact_columns()), pd.DataFrame(atom_rows, columns=_atom_contact_columns()), pep


def simulation_summary_df(poses: pd.DataFrame, contacts: pd.DataFrame, risk: pd.DataFrame):
    """Summarize geometry/contact screening without inventing energies or MD metrics."""
    if poses is None or poses.empty:
        return pd.DataFrame([{
            "metric":"3D screening status","value":"not available","unit":"-",
            "interpretation":"Provide target coordinates and run screening. Molecular dynamics is external-only."
        }], columns=["metric","value","unit","interpretation"])
    best = poses.iloc[0].to_dict()
    def _int(name):
        try: return int(float(best.get(name,0) or 0))
        except Exception: return 0
    return pd.DataFrame([
        {"metric":"best_pose","value":best.get("pose_id", ""),"unit":"-","interpretation":"First candidate after deterministic multi-key geometry ranking."},
        {"metric":"pose_rank","value":best.get("pose_rank", ""),"unit":"ordinal","interpretation":"Rank is based on observed geometry descriptors, not energy or affinity."},
        {"metric":"centroid_contacts","value":_int("contact_count"),"unit":"count","interpretation":"Residue/token-centroid proximities within the configured cutoff."},
        {"metric":"centroid_overlap_warnings","value":_int("centroid_overlap_warnings"),"unit":"count","interpretation":"Very short centroid distances requiring geometry review."},
        {"metric":"molecular_dynamics","value":"not run internally","unit":"-","interpretation":"Export structures for a validated external MD engine."},
    ], columns=["metric","value","unit","interpretation"])


def sequence_sequence_interaction_df(target_seq: str, peptide_seq: str):
    """Return composition descriptors for sequence-only triage.

    No interaction/affinity score is synthesized because sequence composition
    alone does not define a 3D binding interface.
    """
    t="".join([c for c in str(target_seq or "").upper() if c in AA_MASS])
    p=clean_sequence(peptide_seq)
    if not t or not p:
        return pd.DataFrame([{"metric":"status","value":"insufficient sequence input","note":"Enter target and peptide sequences."}])
    def frac(s, group):
        return round(sum(1 for a in s if a in group)/len(s), 4)
    return pd.DataFrame([
        {"metric":"mode","value":"sequence_descriptor_only","note":"No 3D target model or binding score is generated from sequence alone."},
        {"metric":"target_length","value":len(t),"note":"Canonical target residues parsed."},
        {"metric":"peptide_length","value":len(p),"note":"Canonical peptide residues parsed."},
        {"metric":"target_basic_fraction","value":frac(t,BASIC),"note":"Observed sequence composition."},
        {"metric":"target_acidic_fraction","value":frac(t,ACIDIC),"note":"Observed sequence composition."},
        {"metric":"target_hydrophobic_fraction","value":frac(t,HYDROPHOBIC),"note":"Observed sequence composition."},
        {"metric":"peptide_basic_fraction","value":frac(p,BASIC),"note":"Observed sequence composition."},
        {"metric":"peptide_acidic_fraction","value":frac(p,ACIDIC),"note":"Observed sequence composition."},
        {"metric":"peptide_hydrophobic_fraction","value":frac(p,HYDROPHOBIC),"note":"Observed sequence composition."},
        {"metric":"next_step","value":"provide target PDB/mmCIF","note":"Required before Pepforge can evaluate 3D contacts/poses."},
    ])



# -----------------------------------------------------------------------------
 # External molecular-dynamics handling only
# -----------------------------------------------------------------------------










def docking_readiness_df(seq: str):
    """Report input readiness requirements, not an arbitrary 0-1 docking score."""
    canonical = canonical_peptide_notation(seq)
    tokens = _split_peptide_model_tokens(canonical)
    if not tokens:
        return pd.DataFrame([{"metric":"input_readiness","value":"missing peptide","note":"Enter a peptide sequence or load a peptide PDB."}])
    unsupported=[r.get("token","") for r in tokens if r.get("class") == "unsupported"]
    return pd.DataFrame([
        {"metric":"input_readiness","value":"review required" if unsupported else "parsed","note":"Readiness indicates parse/structure availability only; it is not binding likelihood."},
        {"metric":"token_count","value":len(tokens),"note":"Chemistry tokens recognized by the Structure Builder parser."},
        {"metric":"unsupported_tokens","value":";".join(unsupported) if unsupported else "none","note":"Unsupported tokens are not replaced by canonical residues."},
        {"metric":"3d_requirement","value":"target coordinates required","note":"3D contact/pose screening requires a target PDB/mmCIF. Sequence-only targets receive descriptor analysis only."},
        {"metric":"external_validation","value":"recommended","note":"Use Vina/GROMACS/other external tools for quantitative or publication-grade claims."},
    ])



# -----------------------------------------------------------------------------
# Structure-preparation and external-validation helpers
# -----------------------------------------------------------------------------
def _clean_protein_sequence(seq: str) -> str:
    """Robust protein-sequence cleaner for pasted FASTA, spaced sequences, and labels.

    This is intentionally separate from the peptide notation parser because target
    proteins are often pasted as FASTA blocks. Header lines, residue numbers,
    whitespace, and punctuation are ignored.
    """
    lines = []
    for line in str(seq or "").replace("\r", "\n").split("\n"):
        s = line.strip()
        if not s or s.startswith(">"):
            continue
        # Drop common numbering formats such as "12 ACD..." or "ACD 120".
        s = re.sub(r"\b\d+\b", "", s)
        lines.append(s)
    return "".join([c for c in "".join(lines).upper() if c in AA_MASS])

def pdb_to_sequence(path: str | Path | None) -> str:
    atoms = parse_pdb_atoms(path) if path else pd.DataFrame()
    if atoms.empty:
        return ""
    residues = atoms.drop_duplicates(["chain", "resi"]).copy()
    return "".join(residues.get("aa", pd.Series(dtype=str)).astype(str).tolist()).replace("X", "")


# -----------------------------------------------------------------------------
# Local rigid-body geometry screening helpers
# -----------------------------------------------------------------------------



def _center_points(points: pd.DataFrame) -> pd.Series:
    if points is None or points.empty:
        return pd.Series({"x":0.0,"y":0.0,"z":0.0})
    return points[["x","y","z"]].mean()


def _reverse_peptide_orientation(points: pd.DataFrame) -> pd.DataFrame:
    """Rotate a centered peptide 180 degrees about Z without reflecting chirality."""
    if points is None or points.empty:
        return points
    rev = points.copy().reset_index(drop=True)
    center = _center_points(rev)
    rev[["x", "y", "z"]] = rev[["x", "y", "z"]] - center
    rev["x"] = -rev["x"]
    rev["y"] = -rev["y"]
    return rev


def _format_contact_window(values, chain_prefix=False):
    """Format a compact residue window such as A:126D-A:132Y or 1E-6R."""
    cleaned = []
    for v in values:
        txt = str(v or "").strip()
        if txt and txt not in cleaned:
            cleaned.append(txt)
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) <= 4:
        return ", ".join(cleaned)
    return f"{cleaned[0]} ... {cleaned[-1]} ({len(cleaned)} contacts)"


def top_contact_report(contacts: pd.DataFrame, poses: pd.DataFrame | None = None, top_n: int = 50) -> pd.DataFrame:
    """Return a readable top interaction table for the UI.

    The raw search may create hundreds or thousands of pairwise contacts because
    every peptide residue can contact multiple receptor residues.  The public UI
    shows the best interactions first in one readable box, while full details are
    still exported as CSV.
    """
    cols = _contact_columns()
    if contacts is None or contacts.empty:
        return pd.DataFrame(columns=cols)
    df = contacts.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    if poses is not None and not poses.empty and "pose_id" in poses.columns:
        rank = {pid: i for i, pid in enumerate(poses["pose_id"].astype(str).tolist())}
        df["_pose_rank"] = df["pose_id"].astype(str).map(rank).fillna(9999).astype(int)
    else:
        df["_pose_rank"] = 0
    df["_distance"] = pd.to_numeric(df.get("distance_A", 9999), errors="coerce").fillna(9999.0)
    df["_target_resi_num"] = pd.to_numeric(df.get("target_resi", ""), errors="coerce")
    df["_pep_pos_num"] = pd.to_numeric(df.get("pep_pos", ""), errors="coerce")

    # Build local context windows per pose, so a row can be read as part of an
    # interaction block rather than as an isolated pair.
    for pid, g in df.groupby("pose_id", dropna=False):
        gg = g.sort_values(["_target_resi_num", "_pep_pos_num", "_distance"])
        protein_window = _format_contact_window(gg.get("protein_residue", pd.Series(dtype=str)).tolist())
        pep_window = _format_contact_window(gg.sort_values("_pep_pos_num").get("peptide_residue", pd.Series(dtype=str)).tolist())
        idx = g.index
        df.loc[idx, "protein_window"] = protein_window
        df.loc[idx, "peptide_window"] = pep_window

    # Remove exact duplicates from nearly identical neighboring poses while keeping
    # multiple different protein residues for the same peptide residue.
    df = df.sort_values(["_pose_rank", "_distance"]).drop_duplicates(
        subset=["protein_residue", "peptide_residue", "interaction"], keep="first"
    )
    return df.sort_values(["_pose_rank", "_distance"]).head(top_n)[cols].reset_index(drop=True)


def run_pose_search(target_atoms: pd.DataFrame, peptide_points: pd.DataFrame | None = None,
                    peptide_seq: str = "", pose_limit: int = 50):
    """Generate local rigid-body geometry candidates around receptor residue anchors.

    Peptide coordinates come from Structure Builder or an explicit structure.
    Candidate ordering is a deterministic multi-key geometry ranking; no
    thermodynamic energy, docking affinity, or Kd is calculated.
    """
    receptor = receptor_residue_points(target_atoms)
    if peptide_points is None or peptide_points.empty:
        if not str(peptide_seq or "").strip():
            raise ValueError("No peptide structure or peptide sequence was provided for pose screening.")
        peptide_points = generate_peptide_structure_points(peptide_seq)
    if receptor.empty or peptide_points.empty:
        return pd.DataFrame(columns=_pose_columns()), pd.DataFrame(columns=_contact_columns()), peptide_points

    anchors = receptor.copy().reset_index(drop=True)
    if len(anchors) > 260:
        anchors = anchors.iloc[[round(i*(len(anchors)-1)/259) for i in range(260)]].copy()

    original = peptide_points.copy().reset_index(drop=True)
    center = _center_points(original)
    base = original.copy()
    base[["x","y","z"]] = base[["x","y","z"]] - center
    orientations = [("forward_N_to_C", base, 0.0), ("reverse_C_to_N", _reverse_peptide_orientation(base), math.pi)]

    poses=[]; all_contacts=[]; models={}
    directions = _directions()[:6]
    offset = 4.2
    rotations = [0, math.pi/2, math.pi, 3*math.pi/2]
    for orientation_name, oriented_base, orientation_rot in orientations:
        for _, anchor in anchors.iterrows():
            for di, d in enumerate(directions):
                rot = rotations[di % len(rotations)]
                total_rot = (orientation_rot + rot) % (2*math.pi)
                m = oriented_base.copy()
                x = m["x"].copy(); y = m["y"].copy()
                m["x"] = x*math.cos(rot) - y*math.sin(rot)
                m["y"] = x*math.sin(rot) + y*math.cos(rot)
                tx = float(anchor["x"] + d[0]*offset); ty = float(anchor["y"] + d[1]*offset); tz = float(anchor["z"] + d[2]*offset)
                m["x"] += tx; m["y"] += ty; m["z"] += tz
                pose_id = f"{orientation_name}_pose_{anchor['chain']}{anchor['resi']}_{di+1}"
                contacts, overlaps, hyd, charge, aromatic, polar, min_d, rows = _score_contacts(receptor, m, pose_id)
                poses.append({
                    "pose_rank":0, "pose_id":pose_id, "conformation":"structure_builder_rigid_body", "orientation":orientation_name,
                    "contact_count":contacts, "centroid_overlap_warnings":overlaps,
                    "hydrophobic_proximities":hyd, "opposite_charge_proximities":charge,
                    "aromatic_proximities":aromatic, "polar_residue_proximities":polar,
                    "min_centroid_distance_A":round(min_d,2) if math.isfinite(min_d) else "",
                    "rotation_z_deg":round(math.degrees(total_rot),6),
                    "translation_x_A":round(tx,6), "translation_y_A":round(ty,6), "translation_z_A":round(tz,6),
                    "center_x_A":round(float(center.get("x",0.0)),6), "center_y_A":round(float(center.get("y",0.0)),6), "center_z_A":round(float(center.get("z",0.0)),6),
                    "note":"Rigid-body candidate from Structure Builder geometry; rank uses measured centroid/contact descriptors only."
                })
                all_contacts.extend(rows)
                models[pose_id] = m.copy()
    poses_df = pd.DataFrame(poses, columns=_pose_columns())
    if poses_df.empty:
        return poses_df, pd.DataFrame(columns=_contact_columns()), original
    poses_df = poses_df.sort_values(
        ["centroid_overlap_warnings","contact_count","opposite_charge_proximities","hydrophobic_proximities","aromatic_proximities","polar_residue_proximities","min_centroid_distance_A","pose_id"],
        ascending=[True,False,False,False,False,False,True,True], kind="mergesort"
    ).head(max(1,int(pose_limit))).reset_index(drop=True)
    poses_df["pose_rank"] = range(1, len(poses_df)+1)
    keep = set(poses_df["pose_id"])
    all_contacts = [r for r in all_contacts if r.get("pose_id") in keep]
    best_model = models.get(str(poses_df.iloc[0]["pose_id"]), original).copy()
    return poses_df, pd.DataFrame(all_contacts, columns=_contact_columns()), best_model







def screening_evidence_df(poses: pd.DataFrame, contacts: pd.DataFrame) -> pd.DataFrame:
    """Return transparent geometry/contact evidence without affinity inference."""
    source = "Pepforge geometry/contact screening"
    columns = ["source", "metric", "value", "unit", "interpretation", "method_note"]
    if poses is None or poses.empty:
        return pd.DataFrame([{
            "source":source, "metric":"status", "value":"no 3D pose", "unit":"-",
            "interpretation":"Provide target coordinates and run screening.",
            "method_note":"Pepforge does not infer thermodynamic affinity from sequence or contact counts."
        }], columns=columns)
    best = poses.iloc[0].to_dict()
    def val(name, default=""):
        v=best.get(name,default); return v
    rows=[
        ("best_pose", val("pose_id"), "-", "Top candidate after deterministic multi-key geometry ranking.", "Not a thermodynamic ranking."),
        ("pose_rank", val("pose_rank"), "ordinal", "Rank derived from explicit geometry descriptors.", "No weighted energy or affinity score is generated."),
        ("centroid_contacts", val("contact_count"), "count", "Residue/token-centroid proximities within cutoff.", "Coordinate-derived centroid geometry."),
        ("centroid_overlap_warnings", val("centroid_overlap_warnings"), "count", "Very short centroid distances requiring review.", "Not an atom-level clash count."),
        ("hydrophobic_proximities", val("hydrophobic_proximities"), "count", "Hydrophobic residue/token centroid proximities.", "Proximity descriptor only; not an interaction energy."),
        ("opposite_charge_proximities", val("opposite_charge_proximities"), "count", "Oppositely charged residue centroid proximities.", "Not a salt-bridge energy."),
        ("aromatic_proximities", val("aromatic_proximities"), "count", "Aromatic centroid proximities.", "Not a pi-stacking assignment."),
        ("polar_residue_proximities", val("polar_residue_proximities"), "count", "Polar residue centroid proximities.", "Not a hydrogen-bond assignment."),
        ("minimum_centroid_distance", val("min_centroid_distance_A"), "Angstrom", "Closest centroid distance in the candidate.", "Atom-level distances are reported separately when both atomic structures exist."),
        ("internal_delta_G", "not calculated", "-", "Pepforge does not convert these descriptors into ΔG.", "Import a validated external result if needed."),
        ("internal_Kd", "not calculated", "-", "Pepforge does not infer Kd from geometry ranking.", "Use experiment or validated external computation."),
    ]
    return pd.DataFrame([{
        "source":source,"metric":m,"value":v,"unit":u,"interpretation":i,"method_note":n
    } for m,v,u,i,n in rows], columns=columns)


def dynamics_summary_label(summary: pd.DataFrame) -> pd.DataFrame:
    """Compatibility label for imported/external dynamics only."""
    if summary is None or summary.empty:
        return pd.DataFrame([{"metric":"engine_mode","value":"external MD only","note":"Pepforge does not run or label a toy dynamics model as molecular dynamics."}])
    out=summary.copy()
    out.loc[len(out)]={"metric":"engine_mode","value":"external/imported dynamics","note":"Interpret only according to the external engine/method that generated the data."}
    return out




def normalize_result_report_df(df: pd.DataFrame | None, poses: pd.DataFrame | None = None, contacts: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a GUI-safe screening/external-result table.

    Older import paths produced source/field/value/note tables while the Results
    pane expects source/metric/value/unit/interpretation/method_note.  This helper
    keeps the Screening evidence / external result pane populated after Analyze, Load, or external-result import.
    """
    columns = ["source", "metric", "value", "unit", "interpretation", "method_note"]
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        if poses is not None and isinstance(poses, pd.DataFrame) and not poses.empty:
            return screening_evidence_df(poses, contacts if isinstance(contacts, pd.DataFrame) else pd.DataFrame())
        return pd.DataFrame([{
            "source": "Pepforge screening report",
            "metric": "status",
            "value": "not generated",
            "unit": "-",
            "interpretation": "Click Run Screening, or load an output folder containing screening_evidence_summary.csv.",
            "method_note": "The report is generated after a pose/contact table exists."
        }], columns=columns)
    out = df.copy()
    rename = {}
    if "field" in out.columns and "metric" not in out.columns:
        rename["field"] = "metric"
    if "note" in out.columns and "interpretation" not in out.columns:
        rename["note"] = "interpretation"
    out = out.rename(columns=rename)
    for c in columns:
        if c not in out.columns:
            out[c] = "-" if c == "unit" else ""
    # If an imported text/parser table had only generic rows, make the scope explicit.
    blank_method = out["method_note"].astype(str).str.strip().eq("")
    out.loc[blank_method, "method_note"] = "Imported or Pepforge-generated screening report; not final experimental affinity proof."
    return out[columns]


def screening_report_markdown(df: pd.DataFrame | None) -> str:
    """Create a readable Markdown report for geometry/contact screening evidence."""
    rep = normalize_result_report_df(df)
    lines = [
        "# Pepforge Docking Workbench Screening Evidence Report",
        "",
        "This report contains geometry/contact screening descriptors. It does not calculate ΔG, Kd, docking energy, or molecular-dynamics stability.",
        "",
        "| Source | Metric | Value | Unit | Interpretation | Method note |",
        "|---|---|---:|---|---|---|",
    ]
    for _, r in rep.iterrows():
        vals = []
        for c in ["source", "metric", "value", "unit", "interpretation", "method_note"]:
            vals.append(str(r.get(c, "")).replace("|", "/").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    lines += [
        "",
        "## 사용법",
        "",
        "1. Docking Workbench에서 Target/Peptide를 입력한다.",
        "2. Run을 누르면 Docking results, Contacts, Screening evidence가 같이 갱신된다.",
        "3. Export를 누르면 screening_evidence_summary.csv와 screening_evidence_report.md가 output 폴더에 저장된다.",
        "4. 기존 output을 다시 볼 때는 Load로 해당 docking_* 폴더를 선택한다.",
    ]
    return "\n".join(lines) + "\n"
molecular_dynamics_summary_label = dynamics_summary_label


def structure_pipeline_df(target_mode: str, peptide_mode: str, target_seq: str, peptide_seq: str,
                          target_pdb: str | Path | None, peptide_pdb: str | Path | None):
    """Describe what Pepforge can do with the supplied coordinate availability."""
    target_mode = str(target_mode or "PDB")
    peptide_mode = str(peptide_mode or "Sequence")
    target_exists = bool(target_pdb and Path(target_pdb).exists() and not parse_pdb_atoms(target_pdb).empty)
    peptide_exists = bool(peptide_pdb and Path(peptide_pdb).exists() and not parse_pdb_atoms(peptide_pdb).empty)
    rows=[]
    def add(stage,status,function,input_used,output,note):
        rows.append({"stage":stage,"status":status,"function":function,"input_used":input_used,"output":output,"note":note,"engine":"Pepforge"})
    if not target_exists:
        add("1_target_coordinates","REQUIRED","target structure input","target sequence or missing target file","target PDB/mmCIF","Pepforge does not fabricate target 3D coordinates from sequence. Obtain measured or externally predicted target coordinates first.")
        add("2_sequence_descriptors","AVAILABLE_NOW","sequence descriptor analysis","target/peptide sequence","composition and chemistry tables","Descriptor analysis is not docking or binding prediction.")
        add("3_3d_screening","BLOCKED","rigid-body geometry/contact screening","target coordinates required","none","3D screening remains disabled until target coordinates are supplied.")
    elif peptide_mode == "PDB" and peptide_exists:
        add("1_coordinate_check","AVAILABLE_NOW","direct coordinate contact analysis","target PDB/mmCIF + peptide PDB","residue and atom proximity tables","Supplied structures are analyzed directly; no affinity is inferred.")
        add("2_local_pose_search","AVAILABLE_IF_NEEDED","rigid-body local candidate generation","same coordinate inputs","ranked geometry candidates","Used only when a local pose search is requested/needed; ranking is geometric and ordinal.")
    else:
        add("1_peptide_structure","AVAILABLE_NOW","Peptide Structure Builder","peptide sequence","chemistry-aware peptide starting conformer","The generated conformer is a starting candidate, not a native-state prediction.")
        add("2_local_pose_search","AVAILABLE_NOW","rigid-body local candidate generation","target coordinates + Structure Builder peptide coordinates","ranked geometry candidates","No Vina/PRODIGY/thermodynamic energy is calculated internally.")
    add("4_external_validation","READY","external validation handoff","exported structures/tables","Vina/PRODIGY/GROMACS/OpenMM/etc. inputs or imported results","Quantitative docking, affinity, or MD claims require an appropriate external engine or experiment.")
    return pd.DataFrame(rows, columns=["stage","status","function","input_used","output","note","engine"])


def structure_preparation_files(target_seq: str, peptide_seq: str, peptide_pdb: str | Path | None = None):
    """Create generic structure-preparation payloads for export."""
    t = _clean_protein_sequence(target_seq)
    p = clean_sequence(peptide_seq)
    pep_note = "peptide sequence entered by user"
    if not p and peptide_pdb and Path(peptide_pdb).exists():
        atoms = parse_pdb_atoms(peptide_pdb)
        if not atoms.empty:
            p = "".join(atoms.drop_duplicates(["chain", "resi"])["aa"].astype(str).tolist()).replace("X", "")
            pep_note = "peptide sequence extracted from peptide structure residues; verify noncanonical/modified residues manually"
    complex_fasta = f">target_A\n{t}\n>peptide_B\n{p}\n"
    target_fasta = f">target_structure_input\n{t}\n"
    complex_json = (
        '{\n'
        '  "name": "Pepforge_complex_structure_input",\n'
        '  "modelSeeds": [1],\n'
        '  "sequences": [\n'
        '    {"protein": {"id": "A", "sequence": "' + t + '"}},\n'
        '    {"protein": {"id": "B", "sequence": "' + p + '"}}\n'
        '  ]\n'
        '}\n'
    )
    notes = (
        "Pepforge structure-preparation bridge\n"
        "- Use the target sequence to obtain or import a target structure when only sequence is available.\n"
        "- Use the target + peptide payload for complex-structure preparation or other external structure preparation.\n"
        f"- Peptide source: {pep_note}.\n"
        "- Modified residues/noncanonical caps may need manual compatible representation in external tools.\n"
    )
    return complex_fasta, target_fasta, complex_json, notes

# Backward-compatible function name for older tests/scripts. The UI and primary exports use generic names.
def af3_ready_files(target_seq: str, peptide_seq: str, peptide_pdb: str | Path | None = None):
    complex_fasta, target_fasta, complex_json, notes = structure_preparation_files(target_seq, peptide_seq, peptide_pdb)
    legacy_json = complex_json.replace("Pepforge_complex_structure_input", "Pepforge_AF3_ready_complex")
    legacy_notes = notes + "- ESMFold-compatible target FASTA alias retained for older automated tests/scripts.\n"
    return complex_fasta, target_fasta, legacy_json, legacy_notes

def parse_affinity_text(path: str | Path):
    p = Path(path)
    rows=[]
    txt = p.read_text(errors="ignore") if p.exists() else ""
    for line in txt.splitlines():
        s=line.strip()
        low=s.lower()
        if not s:
            continue
        if "binding affinity" in low or "predicted binding affinity" in low or "dg" in low or "kcal" in low:
            rows.append({"source":p.name,"field":"affinity_line","value":s,"note":"contact/affinity parsed line"})
        elif "dissociation constant" in low or "kd" in low:
            rows.append({"source":p.name,"field":"kd_line","value":s,"note":"contact/affinity parsed line"})
        elif "interfacial contacts" in low or "charged-charged" in low or "apolar-apolar" in low:
            rows.append({"source":p.name,"field":"interface_contact_line","value":s,"note":"contact/affinity parsed line"})
    if not rows:
        rows.append({"source":p.name,"field":"status","value":"text imported","note":"No specific affinity markers detected; file retained in imported results."})
    return pd.DataFrame(rows, columns=["source","field","value","note"])



def parse_md_xvg(path: str | Path):
    p=Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["source","series","points","last_value","mean_value","note"])
    xs=[]; ys=[]; title="xvg_series"
    for line in p.read_text(errors="ignore").splitlines():
        s=line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("@"):
            if "title" in s:
                m=re.search(r'"([^"]+)"', s)
                if m: title=m.group(1)
            continue
        parts=s.split()
        if len(parts)>=2:
            try:
                xs.append(float(parts[0])); ys.append(float(parts[1]))
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
    if not ys:
        return pd.DataFrame([{"source":p.name,"series":title,"points":0,"last_value":"","mean_value":"","note":"No numeric XVG data parsed."}])
    return pd.DataFrame([{"source":p.name,"series":title,"points":len(ys),"last_value":round(float(ys[-1]),4),"mean_value":round(sum(ys)/len(ys),4),"note":"MD result XVG summary imported"}])





def all_atom_parameter_requirements_df(seq: str):
    """Describe external all-atom parameter requirements without inventing mappings.

    Unsupported notation is reported explicitly instead of being converted to a
    canonical residue.  This is a requirements/status table only; it does not
    claim that an external force field contains parameters for a token.
    """
    raw = canonical_peptide_notation(seq or "")
    if not raw:
        return pd.DataFrame([{
            "token":"none", "type":"empty peptide", "pepforge_screening":"not ready",
            "all_atom_requirement":"Enter a peptide sequence or provide an explicit peptide structure.",
            "status":"not ready",
        }], columns=["token","type","pepforge_screening","all_atom_requirement","status"])

    # Prefer the full chemistry-aware parser.  If one token is unsupported, fall
    # back only to per-dash token classification so that the unsupported literal
    # token can be reported; no surrogate residue or geometry is generated.
    try:
        token_rows = _split_peptide_model_tokens(raw)
    except Exception:
        from peptiforg_core.pymol_structure_builder import classify_tokens
        token_rows = []
        parts = [part.strip() for part in str(raw).split("-") if part.strip()]
        if not parts:
            parts = [str(raw).strip()]
        for part in parts:
            try:
                classified = classify_tokens(part)
            except Exception as exc:
                token_rows.append({
                    "token": part, "aa":"X", "class":"unsupported",
                    "note":"Token is not supported by the current Structure Builder parser.",
                    "warning": str(exc),
                })
                continue
            for item in classified:
                token_rows.append({
                    "token": str(item.token or item.raw or part),
                    "aa":"X", "class": str(item.cls or "unsupported"),
                    "note": str(item.note or ""), "warning": str(item.warning or ""),
                })

    rows=[]
    for item in token_rows:
        tok=str(item.get("token", ""))
        cls=str(item.get("class", "unsupported"))
        norm=normalize_token(tok)

        if cls == "std_aa":
            req="Standard residue parameters in the selected external force field."
            status="verify selected force field"
            screening="Structure Builder supported"
        elif cls == "d_std_aa":
            req="D-residue topology/parameters with chirality verified in the selected external workflow."
            status="parameter check required"
            screening="Structure Builder supported"
        elif cls == "non_natural_aa":
            req="Explicit non-natural residue topology, charges, and bonded/nonbonded parameters."
            status="parameter required"
            screening="Structure Builder supported when a template exists"
        elif cls == "linker":
            req="Explicit linker topology, charges, linkage definition, and bonded/nonbonded parameters."
            status="parameter required"
            screening="Structure Builder supported when a template exists"
        elif cls in {"label", "chemical"}:
            req="Explicit modification parameters, charges, and attachment/linkage definition."
            status="parameter required"
            screening="Structure Builder supported when a template exists"
        elif cls in {"n_terminal_modifier", "n_terminal"}:
            if norm in {"AC", "ACETYL"}:
                req="Verify an acetylated N-terminus patch/residue definition in the selected external force field."
                status="parameter check required"
            else:
                req="Explicit N-terminal modification topology, charges, and linkage definition."
                status="parameter required"
            screening="Structure Builder supported when a template exists"
        elif cls in {"c_terminal_modifier", "c_terminal"}:
            if norm in {"NH2", "CONH2", "AMIDE"}:
                req="Verify an amidated C-terminus patch/residue definition in the selected external force field."
                status="parameter check required"
            else:
                req="Explicit C-terminal modification topology, charges, and linkage definition."
                status="parameter required"
            screening="Structure Builder supported when a template exists"
        else:
            req="Provide an explicit validated structure/template and external force-field parameters; no canonical surrogate is used."
            status="unsupported / review required"
            screening="blocked for sequence-derived 3D"

        rows.append({
            "token":tok or "unknown", "type":cls or "unsupported",
            "pepforge_screening":screening,
            "all_atom_requirement":req,
            "status":status,
        })

    return pd.DataFrame(rows, columns=["token","type","pepforge_screening","all_atom_requirement","status"])

def parse_external_validation_file(path: str | Path):
    """Parse external MD/structure/affinity files without generating derived affinity claims."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame([{"source":str(p), "field":"status", "value":"missing file", "note":"File was not found."}])
    suf = p.suffix.lower()
    if suf == ".xvg":
        md = parse_md_xvg(p)
        if md is None or md.empty:
            return pd.DataFrame([{"source":p.name, "field":"xvg_status", "value":"no numeric data", "note":"No numeric XVG series was parsed."}])
        # Normalize the XVG summary to the same external-result schema used by
        # the other import formats.  Values are copied from the external file;
        # no affinity or thermodynamic quantity is inferred.
        rows=[]
        for _, r in md.iterrows():
            for field in ("series", "points", "last_value", "mean_value"):
                if field in r:
                    rows.append({"source":p.name, "field":field, "value":r.get(field, ""), "note":"External XVG summary value."})
        return pd.DataFrame(rows, columns=["source","field","value","note"])
    if suf in {".csv", ".tsv"}:
        sep = "\t" if suf == ".tsv" else ","
        try:
            df = pd.read_csv(p, sep=sep)
        except Exception as exc:
            return pd.DataFrame([{"source":p.name, "field":"table_import_error", "value":str(exc), "note":"Could not parse the external table."}])
        rows=[{"source":p.name, "field":"table_rows", "value":len(df), "note":"External validation table imported."}]
        for col in df.columns[:8]:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals):
                rows.append({"source":p.name, "field":f"{col}_last", "value":round(float(vals.iloc[-1]),4), "note":"Last numeric value copied from the external series."})
                rows.append({"source":p.name, "field":f"{col}_mean", "value":round(float(vals.mean()),4), "note":"Arithmetic mean of the imported numeric series."})
        return pd.DataFrame(rows, columns=["source","field","value","note"])
    if suf in {".xlsx", ".xls"}:
        try:
            xl = pd.ExcelFile(p)
            return pd.DataFrame([{"source":p.name, "field":"excel_sheets", "value":";".join(xl.sheet_names), "note":"Workbook detected for external-result review."}])
        except Exception as exc:
            return pd.DataFrame([{"source":p.name, "field":"excel_import_error", "value":str(exc), "note":"Could not parse the workbook."}])
    if suf in {".pdb", ".cif", ".mmcif"}:
        atoms = parse_pdb_atoms(p)
        if atoms.empty:
            return pd.DataFrame([{"source":p.name, "field":"structure_atoms", "value":0, "note":"No valid ATOM/HETATM coordinates were parsed."}])
        return pd.DataFrame([
            {"source":p.name, "field":"structure_atoms", "value":len(atoms), "note":"Parsed coordinate atoms."},
            {"source":p.name, "field":"structure_chains", "value":atoms["chain"].nunique(), "note":"Parsed chain count."},
            {"source":p.name, "field":"structure_residues", "value":atoms.drop_duplicates(["chain","resi"]).shape[0], "note":"Parsed residue count."},
        ])
    return parse_affinity_text(p)


def all_atom_validation_template_files():
    """Return portable validation bridge templates for external all-atom MD workflows."""
    gmx = external_md_template_files()
    amber_min = """# Pepforge AMBER minimization skeleton\n# Fill topology/coordinate names after preparing parameters.\nMinimization\n &cntrl\n  imin=1, maxcyc=5000, ncyc=2500, cut=10.0,\n /\n"""
    namd_conf = """# Pepforge NAMD short validation skeleton\n# Replace structure/coordinates/parameters with prepared files.\ntimestep 2.0\nexclude scaled1-4\n1-4scaling 1.0\nswitching on\nswitchdist 10.0\ncutoff 12.0\nPME yes\nminimize 5000\nrun 50000\n"""
    readme = """Pepforge all-atom validation package\n\nPurpose\n- This package is for external validation of Pepforge docking/MD screening outputs.\n- Pepforge does not hide the limitation: D-form residues, non-natural amino acids, labels, linkers, and terminal chemicals may require force-field parameters before all-atom MD.\n\nRecommended workflow\n1. Inspect token_parameter_requirements.csv.\n2. Use target_input.pdb, peptide_input.pdb, and complex_candidate.pdb as starting structures.\n3. Clean protonation, termini, missing atoms, chain IDs, and modified residues.\n4. Generate topology with a force field suitable for the chosen chemistry.\n5. Run minimization/equilibration/production externally.\n6. Import RMSD/RMSF/energy/contact CSV/XVG/LOG/PDB outputs back through Pepforge.\n\nInterpretation\n- Embedded Pepforge MD is for screening and prioritization.\n- External all-atom MD should be used for publication-grade claims or expensive experimental decisions.\n"""
    files={}
    for k,v in gmx.items():
        files[f"gromacs/{k}"]=v
    files["amber/min.in"]=amber_min
    files["namd/short_validation.conf"]=namd_conf
    files["README_ALL_ATOM_VALIDATION.txt"]=readme
    return files

def external_md_template_files():
    mdp_minim = """; Pepforge basic energy minimization template
integrator = steep
emtol = 1000.0
emstep = 0.01
nsteps = 50000
cutoff-scheme = Verlet
coulombtype = PME
rcoulomb = 1.0
rvdw = 1.0
pbc = xyz
"""
    mdp_nvt = """; Pepforge basic temperature-equilibration template
integrator = md
nsteps = 50000
dt = 0.002
tcoupl = V-rescale
tc-grps = Protein Non-Protein
tau_t = 0.1 0.1
ref_t = 300 300
pcoupl = no
constraints = h-bonds
coulombtype = PME
rvdw = 1.0
pbc = xyz
"""
    mdp_md = """; Pepforge short production-MD template
integrator = md
nsteps = 500000
dt = 0.002
tcoupl = V-rescale
tc-grps = Protein Non-Protein
tau_t = 0.1 0.1
ref_t = 300 300
pcoupl = Parrinello-Rahman
ref_p = 1.0
tau_p = 2.0
compressibility = 4.5e-5
constraints = h-bonds
coulombtype = PME
rvdw = 1.0
pbc = xyz
"""
    readme = """Pepforge external MD bridge

This folder contains minimal all-atom MD input templates only. Pepforge does not bundle an all-atom validation bridge engine.
Recommended flow:
1. Prepare a protein-peptide complex PDB/mmCIF from predicted, modelled, or imported structure data.
2. Clean chain IDs, protonation, missing atoms, termini, and modified residues manually.
3. Generate topology with a suitable force field. Noncanonical residues/caps require parameters.
4. Run minimization, equilibration, and production MD externally.
5. Import RMSD/RMSF/energy .xvg or CSV back into Docking Workbench.
"""
    return {"em.mdp": mdp_minim, "nvt.mdp": mdp_nvt, "md_short.mdp": mdp_md, "EXTERNAL_MD_README.txt": readme}



def has_modified_peptide_tokens(seq: str) -> bool:
    rows = _split_peptide_model_tokens(seq or "")
    return any(str(r.get("class", "")) not in {"canonical", ""} for r in rows)




def combined_complex_pdb(target_atoms: pd.DataFrame, peptide_points: pd.DataFrame, contacts: pd.DataFrame | None = None) -> str:
    """Export a readable PDB containing target and current peptide pose.

    For sequence-derived targets this is a coarse CA model.  For PDB/mmCIF
    targets, parsed atoms are retained.  Contacts are also written as REMARK
    lines using residue labels such as 4Q -> A:134D.
    """
    lines=["REMARK Pepforge target-peptide complex candidate", "REMARK Use as screening/export model; validate externally before quantitative claims."]
    if contacts is not None and not contacts.empty:
        for _, r in contacts.head(80).iterrows():
            lines.append(f"REMARK CONTACT {r.get('peptide_residue','')} -> {r.get('target_residue','')} dist={r.get('distance_A','')}A interaction={r.get('interaction','')}")
    serial=1
    if target_atoms is not None and not target_atoms.empty:
        for _, a in target_atoms.iterrows():
            atom=str(a.get('atom','CA'))[:4]
            resn=str(a.get('resn', ONE_TO_THREE.get(str(a.get('aa','G'))[:1], 'GLY')))[:3]
            chain=str(a.get('chain','A') or 'A')[:1]
            try: resi=int(float(a.get('resi', serial)))
            except Exception: resi=serial
            elem=str(a.get('element','C') or 'C')[:2].rjust(2)
            lines.append(f"ATOM  {serial:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {float(a.get('x',0)):8.3f}{float(a.get('y',0)):8.3f}{float(a.get('z',0)):8.3f}  1.00  0.00          {elem}")
            serial+=1
    lines.append("TER")
    if peptide_points is not None and not peptide_points.empty:
        for _, r in peptide_points.iterrows():
            aa=str(r.get('aa','G'))[:1] or 'G'
            resn=ONE_TO_THREE.get(aa, 'GLY')
            try: resi=int(float(r.get('pep_pos', serial)))
            except Exception: resi=serial
            lines.append(f"ATOM  {serial:5d}  CA  {resn:>3s} P{resi:4d}    {float(r.get('x',0)):8.3f}{float(r.get('y',0)):8.3f}{float(r.get('z',0)):8.3f}  1.00  0.00           C")
            serial+=1
    lines.append("END")
    return "\n".join(lines)+"\n"


def resolve_target_input(target_mode: str, target_path: str | Path | None, target_sequence: str | None = "") -> dict:
    """Resolve target input robustly for GUI and tests.

    Returns a dict with mode, path, sequence, atoms, status, and message.
    This keeps target recognition consistent across Analyze/Run/Export.
    """
    path_text = str(target_path or "").strip().strip('"').strip("'")
    path = Path(path_text).expanduser() if path_text else None
    seq = _clean_protein_sequence(target_sequence or "")
    if path and path.exists():
        atoms = parse_pdb_atoms(path)
        if not atoms.empty:
            return {"mode": "PDB", "path": str(path), "sequence": seq, "atoms": atoms, "status": "ok", "message": f"Target structure recognized: {path.name}, atoms={len(atoms)}"}
        # Some users put FASTA/text in a file or use a structure-like extension with sequence content.
        try:
            file_seq = _clean_protein_sequence(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            file_seq = ""
        if len(file_seq) >= 10:
            return {"mode": "Sequence", "path": str(path), "sequence": file_seq, "atoms": pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"]), "status": "ok", "message": f"Target sequence recognized from file: {path.name}, residues={len(file_seq)}"}
        return {"mode": "PDB", "path": str(path), "sequence": seq, "atoms": atoms, "status": "error", "message": f"Target file exists but no atoms/sequence were recognized: {path}"}
    if seq:
        return {"mode": "Sequence", "path": "", "sequence": seq, "atoms": pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"]), "status": "ok", "message": f"Target sequence recognized, residues={len(seq)}"}
    if path_text and (not path or not path.exists()):
        fallback = _clean_protein_sequence(path_text)
        if len(fallback) >= 10:
            return {"mode": "Sequence", "path": "", "sequence": fallback, "atoms": pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"]), "status": "ok", "message": f"Target sequence recognized from path field, residues={len(fallback)}"}
    return {"mode": target_mode or "PDB", "path": path_text, "sequence": "", "atoms": pd.DataFrame(), "status": "error", "message": "No valid target PDB/mmCIF file or protein sequence was recognized."}


class DockingWorkbenchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Docking Workbench")
        set_pepforge_icon(self)
        self.geometry("1780x1040")
        self.minsize(1180, 760)
        apply_pepforge_theme(self)
        self.last_outdir=None
        self._install_green_progress_style()
        self._build()

    def _default_outdir(self) -> Path:
        return configured_output(ROOT/"outputs"/"docking_workbench", "docking")

    def _effective_outdir(self) -> Path:
        raw = str(self.outdir.get() or "").strip()
        if raw:
            return Path(raw).expanduser()
        outdir = self._default_outdir()
        self.outdir.set(str(outdir))
        return outdir

    @staticmethod
    def _path_fingerprint(path_text: str) -> tuple:
        path_text = str(path_text or "").strip()
        if not path_text:
            return ("", None, None)
        path = Path(path_text).expanduser()
        try:
            stat = path.stat()
            return (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
        except OSError:
            return (str(path), None, None)

    def _screening_input_signature(self) -> tuple:
        """Return a stable signature for the inputs that determine screening results.

        Export uses this to avoid re-running an expensive Structure Builder/screening
        pass when the already-displayed results were produced from the same inputs,
        while still preventing stale results from being exported after an input change.
        """
        return (
            str(self.target_mode.get() or ""),
            self._path_fingerprint(self._target_path()),
            str(self.target_seq.get() or "").strip(),
            str(self.peptide_mode.get() or ""),
            self._path_fingerprint(self._peptide_pdb_path()),
            str(self.seq.get() or "").strip(),
        )

    def _screening_results_are_current(self) -> bool:
        return (
            getattr(self, "_last_screening_signature", None) == self._screening_input_signature()
            and hasattr(self, "screening_evidence")
        )

    def _install_green_progress_style(self):
        """Use a left-to-right green determinate progress bar in this GUI."""
        try:
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
            style.configure("PepforgeGreen.Horizontal.TProgressbar", troughcolor="#e8e8e8", background="#2dbb55", lightcolor="#2dbb55", darkcolor="#2dbb55")
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _build(self):
        main=ttk.Frame(self,padding=12); main.pack(fill="both",expand=True)
        ttk.Label(main,text="Docking Workbench",style="Title.TLabel").pack(anchor="w")
        ttk.Label(main,text="Structure input, local rigid-body geometry/contact screening, and external docking/affinity/MD validation import/export.",style="Sub.TLabel").pack(anchor="w",pady=(2,8))
        top=ttk.LabelFrame(main,text="Input",padding=8); top.pack(fill="x")
        self.input_panel = top
        self.input_panel_visible = True
        self.target_mode=tk.StringVar(value="PDB")
        self.peptide_mode=tk.StringVar(value="Sequence")
        self.target_seq=tk.StringVar(value="")
        self.seq=tk.StringVar(value="")
        self.pdb_path=tk.StringVar(value="")
        self.pep_pdb_path=tk.StringVar(value="")
        self.result_path=tk.StringVar(value="")
        self.outdir=tk.StringVar(value="")
        self.rcsb_query=tk.StringVar(value="")
        self.rcsb_mode=tk.StringVar(value="auto")
        self.rcsb_format=tk.StringVar(value="pdb")
        self.target_selected_chains=tk.StringVar(value="")
        self.keep_waters=tk.BooleanVar(value=False)
        self.keep_ions=tk.BooleanVar(value=True)
        self.keep_ligands=tk.BooleanVar(value=True)
        self.calibration_dataset_path=tk.StringVar(value="")
        self.calibration_candidate_score=tk.StringVar(value="")
        self.evidence_project_folder=tk.StringVar(value="")
        self.project_session_name=tk.StringVar(value="Pepforge_Project")
        self.project_session_file=tk.StringVar(value="")
        self.dashboard_design_csv=tk.StringVar(value="")
        self.dashboard_docking_csv=tk.StringVar(value="")
        self.dashboard_external_csv=tk.StringVar(value="")
        self.dashboard_calibration_csv=tk.StringVar(value="")
        self.experimental_import_csv=tk.StringVar(value="")
        self.workflow_config_path=tk.StringVar(value="")
        self.workflow_project_name=tk.StringVar(value="Pepforge_Project")
        self.compare_old_project=tk.StringVar(value="")
        self.compare_new_project=tk.StringVar(value="")
        self.compare_old_dashboard=tk.StringVar(value="")
        self.compare_new_dashboard=tk.StringVar(value="")
        self.dashboard_experimental_csv=tk.StringVar(value="")
        self.binding_site_seed_residues=tk.StringVar(value="")
        self.binding_site_ligand_cutoff=tk.StringVar(value="6.0")
        self.binding_site_seed_cutoff=tk.StringVar(value="8.0")
        self.external_docking_result_path=tk.StringVar(value="")
        self.calibration_normalized_csv_path=tk.StringVar(value="")
        self.complex_chain_id=tk.StringVar(value="P")
        self.mode_hint=tk.StringVar(value="Mode: target structure + peptide sequence = receptor-guided pose screening")
        mode_row=ttk.Frame(top); mode_row.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,6))
        ttk.Label(mode_row,text="Target input",width=14).pack(side="left")
        cb1=ttk.Combobox(mode_row,textvariable=self.target_mode,values=["PDB","Sequence"],width=12,state="readonly"); cb1.pack(side="left",padx=4)
        ttk.Label(mode_row,text="Peptide input",width=14).pack(side="left",padx=(16,0))
        cb2=ttk.Combobox(mode_row,textvariable=self.peptide_mode,values=["Sequence","PDB"],width=12,state="readonly"); cb2.pack(side="left",padx=4)
        ttk.Label(mode_row,textvariable=self.mode_hint,foreground="#444").pack(side="left",padx=12)
        pdb_box=ttk.LabelFrame(top,text="PDB",padding=8); pdb_box.grid(row=1,column=0,sticky="nsew",padx=(0,6))
        seq_box=ttk.LabelFrame(top,text="SEQUENCE",padding=8); seq_box.grid(row=1,column=1,sticky="nsew",padx=(6,0))
        ttk.Label(pdb_box,text="Protein / complex PDB or mmCIF",width=28).grid(row=0,column=0,sticky="w")
        ttk.Entry(pdb_box,textvariable=self.pdb_path).grid(row=0,column=1,sticky="ew",padx=4); ttk.Button(pdb_box,text="Browse",command=self.browse_pdb).grid(row=0,column=2,padx=4,sticky="e")
        ttk.Label(pdb_box,text="Peptide PDB or peptide chain file",width=28).grid(row=1,column=0,sticky="w")
        ttk.Entry(pdb_box,textvariable=self.pep_pdb_path).grid(row=1,column=1,sticky="ew",padx=4); ttk.Button(pdb_box,text="Browse",command=self.browse_peptide_pdb).grid(row=1,column=2,padx=4,sticky="e")
        ttk.Label(pdb_box,text="Result file",width=28).grid(row=2,column=0,sticky="w")
        ttk.Entry(pdb_box,textvariable=self.result_path).grid(row=2,column=1,sticky="ew",padx=4); ttk.Button(pdb_box,text="Import",command=self.browse_result).grid(row=2,column=2,padx=4,sticky="e")
        pdb_box.columnconfigure(1,weight=1)
        ttk.Label(seq_box,text="Protein sequence",width=22).grid(row=0,column=0,sticky="w")
        ttk.Entry(seq_box,textvariable=self.target_seq).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Label(seq_box,text="Peptide sequence",width=22).grid(row=1,column=0,sticky="w")
        ttk.Entry(seq_box,textvariable=self.seq).grid(row=1,column=1,sticky="ew",padx=4)
        ttk.Label(seq_box,text="Output folder",width=22).grid(row=2,column=0,sticky="w")
        ttk.Entry(seq_box,textvariable=self.outdir).grid(row=2,column=1,sticky="ew",padx=4); ttk.Button(seq_box,text="Browse",command=self.browse_outdir).grid(row=2,column=2,padx=4,sticky="e")
        seq_box.columnconfigure(1,weight=1)
        rcsb_box=ttk.LabelFrame(top,text="RCSB PDB Search / Fetch",padding=8); rcsb_box.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(8,0))
        ttk.Label(rcsb_box,text="PDB code / protein name / sequence",width=30).grid(row=0,column=0,sticky="w")
        ttk.Entry(rcsb_box,textvariable=self.rcsb_query).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Label(rcsb_box,text="Mode").grid(row=0,column=2,sticky="e")
        ttk.Combobox(rcsb_box,textvariable=self.rcsb_mode,values=["auto","pdb_id","text","sequence"],width=10,state="readonly").grid(row=0,column=3,padx=4)
        ttk.Label(rcsb_box,text="Format").grid(row=0,column=4,sticky="e")
        ttk.Combobox(rcsb_box,textvariable=self.rcsb_format,values=["pdb","cif"],width=6,state="readonly").grid(row=0,column=5,padx=4)
        ttk.Button(rcsb_box,text="Search RCSB",command=self.search_rcsb_target).grid(row=0,column=6,padx=4)
        ttk.Button(rcsb_box,text="Fetch selected to Target",command=self.fetch_selected_rcsb_target).grid(row=0,column=7,padx=4)
        ttk.Button(rcsb_box,text="Open RCSB page",command=self.open_selected_rcsb_page).grid(row=0,column=8,padx=4)
        rcsb_box.columnconfigure(1,weight=1)
        prep_box=ttk.LabelFrame(top,text="Target Preparation",padding=8); prep_box.grid(row=3,column=0,columnspan=2,sticky="ew",pady=(8,0))
        ttk.Label(prep_box,text="Selected chains",width=18).grid(row=0,column=0,sticky="w")
        ttk.Entry(prep_box,textvariable=self.target_selected_chains,width=18).grid(row=0,column=1,sticky="w",padx=4)
        ttk.Checkbutton(prep_box,text="keep waters",variable=self.keep_waters).grid(row=0,column=2,sticky="w",padx=4)
        ttk.Checkbutton(prep_box,text="keep ions",variable=self.keep_ions).grid(row=0,column=3,sticky="w",padx=4)
        ttk.Checkbutton(prep_box,text="keep ligands/cofactors",variable=self.keep_ligands).grid(row=0,column=4,sticky="w",padx=4)
        ttk.Button(prep_box,text="Prepare Target",command=self.prepare_target_structure).grid(row=0,column=5,padx=8)
        ttk.Label(prep_box,text="Example: A or A,B. Blank = all chains.",foreground="#555").grid(row=0,column=6,sticky="w")
        prep_box.columnconfigure(6,weight=1)
        complex_box=ttk.LabelFrame(top,text="Complex Builder",padding=8); complex_box.grid(row=4,column=0,columnspan=2,sticky="ew",pady=(8,0))
        ttk.Label(complex_box,text="Peptide chain ID",width=18).grid(row=0,column=0,sticky="w")
        ttk.Entry(complex_box,textvariable=self.complex_chain_id,width=6).grid(row=0,column=1,sticky="w",padx=4)
        ttk.Button(complex_box,text="Build Initial Complex",command=self.build_initial_complex).grid(row=0,column=2,padx=8)
        ttk.Label(complex_box,text="Uses target PDB plus peptide coordinates. Sequence peptides are built by Peptide Structure Builder; no surrogate residue model is used.",foreground="#555").grid(row=0,column=3,sticky="w")
        complex_box.columnconfigure(3,weight=1)
        top.columnconfigure(0,weight=1); top.columnconfigure(1,weight=1)
        for var in (self.target_mode, self.peptide_mode): var.trace_add("write", lambda *_: self._update_mode_hint())
        btns=ttk.Frame(main); btns.pack(fill="x",pady=8)
        self.input_toggle_btn = ttk.Button(btns,text="Collapse Input",command=self.toggle_input_panel)
        self.input_toggle_btn.pack(side="left",padx=3)
        ttk.Button(btns,text="Analyze",command=self.analyze).pack(side="left",padx=3)
        self.run_screening_btn = ttk.Button(btns,text="Run Screening",command=self.run_docking)
        self.run_screening_btn.pack(side="left",padx=3)
        ttk.Button(btns,text="Export",command=self.export).pack(side="left",padx=3)
        ttk.Button(btns,text="Load",command=self.load_output_folder).pack(side="left",padx=3)
        ttk.Button(btns,text="Open Folder",command=self.open_output).pack(side="left",padx=3)
        ttk.Button(btns,text="Input data full",command=lambda: self.show_data_full("input")).pack(side="left",padx=3)
        ttk.Button(btns,text="Results data full",command=lambda: self.show_data_full("results")).pack(side="left",padx=3)
        
        self.progress_var=tk.DoubleVar(value=0.0)
        self.progress_text=tk.StringVar(value="Ready")
        ttk.Progressbar(btns, variable=self.progress_var, maximum=100, length=260, mode="determinate", style="PepforgeGreen.Horizontal.TProgressbar").pack(side="left", padx=(14, 4))
        ttk.Label(btns, textvariable=self.progress_text, width=34).pack(side="left", padx=4)
        adv=ttk.Menubutton(btns,text="Advanced")
        adv_menu=tk.Menu(adv,tearoff=False)
        adv_menu.add_command(label="Run docking only", command=self.run_docking)
        adv["menu"]=adv_menu
        adv.pack(side="left",padx=3)
        self.tabs=ttk.Notebook(main); self.tabs.pack(fill="both",expand=True)
        self.md_summary=pd.DataFrame(columns=["metric","value","note"]); self.md_frames=pd.DataFrame(); self.md_final_model=pd.DataFrame(); self.md_trajectory_pdb=""; self.pipeline=pd.DataFrame(); self.md_result_import=pd.DataFrame()

        # Portfolio UI: five user-facing pages, with detailed CSV exports retained.
        input_tab = self._make_tab("Input")
        results = self._make_tab("Results")
        contacts = self._make_tab("Contacts")
        md = self._make_tab("External validation")
        imports = self._make_tab("Export / Import")

        self.prop_tree=self._tree_panel(input_tab,"Peptide summary",["metric","value","note"], height=5)
        self.terminal_tree=self._tree_panel(input_tab,"Terminal state",["field","value","note"], height=5)
        self.pdb_tree=self._tree_panel(input_tab,"Target summary",["field","value","note"], height=5)
        self.target_prep_tree=self._tree_panel(input_tab,"Target preparation report",["item","value","note"], height=6)
        self.binding_site_tree=self._tree_panel(input_tab,"Binding site selector report",["item","value","note"], height=6)
        self.rcsb_tree=self._tree_panel(input_tab,"RCSB PDB search results",["pdb_id","title","method","resolution_A","match_type","score","source","polymer_entity"], height=7)
        self.seqpair_tree=self._tree_panel(input_tab,"Sequence-pair summary",["metric","value","note"], height=4)
        self.compat_tree=self._tree_panel(input_tab,"Modified residues and chemicals",["metric","value","note"], height=5)
        self.pipeline_tree=self._tree_panel(input_tab,"Workflow",["stage","status","function","input_used","output","note"], height=6)

        self.interpret_tree=self._tree_panel(results,"Result interpretation",["item","status","interpretation"], height=5)
        self.pose_tree=self._tree_panel(results,"Geometry candidates",_pose_columns(), height=10)
        self.import_tree=self._tree_panel(results,"Screening evidence / external result",["source","metric","value","unit","interpretation","method_note"], height=8)
        self.external_style_tree=self._tree_panel(results,"External validation status",["engine_style","metric","value","unit","interpretation","external_equivalent"], height=8)
        self.risk_tree=self._tree_panel(results,"Risk summary",["risk","score","level","note"], height=5)
        self.readiness_tree=self._tree_panel(results,"Readiness",["metric","value","note"], height=4)

        self.contact_tree=self._tree_panel(contacts,"Top interaction contacts",_contact_columns(), height=22)
        self.complex_tree=self._tree_panel(contacts,"Initial complex builder",["item","value","note"], height=6)
        # Technical atom/proxy contacts and peptide residue maps are still exported,
        # but are no longer shown as separate panes in the public UI because they
        # made the Contacts tab hard to read.
        self.atom_contact_tree = None
        self.residue_tree = None

        self.sim_tree=self._tree_panel(md,"MD screening summary",["metric","value","unit","interpretation"], height=8)
        self.md_tree=self._tree_panel(md,"MD readable trend",["frame","time_ps","rmsd_A","contacts","clashes","min_distance_A","interpretation"], height=12)
        self.md_result_tree=self._tree_panel(imports,"Imported external validation results",["source","series","points","last_value","mean_value","note"], height=8)
        ed_box=ttk.LabelFrame(imports,text="External Docking Result Import",padding=6); ed_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(ed_box,text="File or folder",width=14).grid(row=0,column=0,sticky="w")
        ttk.Entry(ed_box,textvariable=self.external_docking_result_path).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(ed_box,text="Browse File",command=self.browse_external_docking_file).grid(row=0,column=2,padx=4)
        ttk.Button(ed_box,text="Browse Folder",command=self.browse_external_docking_folder).grid(row=0,column=3,padx=4)
        ttk.Button(ed_box,text="Import Docking Results",command=self.import_external_docking_results).grid(row=0,column=4,padx=4)
        ed_box.columnconfigure(1,weight=1)
        self.external_docking_tree=self._tree_panel(imports,"External docking import summary",["item","value","note"], height=6)
        ps_box=ttk.LabelFrame(imports,text="Project Session / Resume",padding=6); ps_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(ps_box,text="Session name",width=14).grid(row=0,column=0,sticky="w")
        ttk.Entry(ps_box,textvariable=self.project_session_name).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(ps_box,text="New Session",command=self.create_project_session).grid(row=0,column=2,padx=4)
        ttk.Button(ps_box,text="Load Session",command=self.load_project_session_file).grid(row=0,column=3,padx=4)
        ttk.Button(ps_box,text="Save Summary",command=self.save_project_session_summary).grid(row=0,column=4,padx=4)
        ps_box.columnconfigure(1,weight=1)
        self.project_session_tree=self._tree_panel(imports,"Project session summary",["item","value","note"], height=6)
        dash_box=ttk.LabelFrame(imports,text="Candidate Comparison Dashboard",padding=6); dash_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(dash_box,text="Design CSV",width=12).grid(row=0,column=0,sticky="w")
        ttk.Entry(dash_box,textvariable=self.dashboard_design_csv).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(dash_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.dashboard_design_csv)).grid(row=0,column=2,padx=3)
        ttk.Label(dash_box,text="Docking CSV",width=12).grid(row=1,column=0,sticky="w")
        ttk.Entry(dash_box,textvariable=self.dashboard_docking_csv).grid(row=1,column=1,sticky="ew",padx=4)
        ttk.Button(dash_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.dashboard_docking_csv)).grid(row=1,column=2,padx=3)
        ttk.Label(dash_box,text="External CSV",width=12).grid(row=2,column=0,sticky="w")
        ttk.Entry(dash_box,textvariable=self.dashboard_external_csv).grid(row=2,column=1,sticky="ew",padx=4)
        ttk.Button(dash_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.dashboard_external_csv)).grid(row=2,column=2,padx=3)
        ttk.Label(dash_box,text="Calibration CSV",width=12).grid(row=3,column=0,sticky="w")
        ttk.Entry(dash_box,textvariable=self.dashboard_calibration_csv).grid(row=3,column=1,sticky="ew",padx=4)
        ttk.Button(dash_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.dashboard_calibration_csv)).grid(row=3,column=2,padx=3)
        ttk.Label(dash_box,text="Experimental CSV",width=12).grid(row=4,column=0,sticky="w")
        ttk.Entry(dash_box,textvariable=self.dashboard_experimental_csv).grid(row=4,column=1,sticky="ew",padx=4)
        ttk.Button(dash_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.dashboard_experimental_csv)).grid(row=4,column=2,padx=3)
        ttk.Button(dash_box,text="Build Dashboard",command=self.build_candidate_dashboard).grid(row=5,column=1,sticky="w",pady=4)
        dash_box.columnconfigure(1,weight=1)
        self.candidate_dashboard_tree=self._tree_panel(imports,"Candidate dashboard summary",["item","value","note"], height=6)
        exp_box=ttk.LabelFrame(imports,text="Experimental Data Import",padding=6); exp_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(exp_box,text="Assay CSV",width=12).grid(row=0,column=0,sticky="w")
        ttk.Entry(exp_box,textvariable=self.experimental_import_csv).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(exp_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.experimental_import_csv)).grid(row=0,column=2,padx=3)
        ttk.Button(exp_box,text="Template",command=self.create_experimental_template).grid(row=0,column=3,padx=3)
        ttk.Button(exp_box,text="Import Experimental",command=self.import_experimental_data).grid(row=0,column=4,padx=3)
        exp_box.columnconfigure(1,weight=1)
        self.experimental_import_tree=self._tree_panel(imports,"Experimental import summary",["item","value","note"], height=6)
        wf_box=ttk.LabelFrame(imports,text="Workflow Automation Runner",padding=6); wf_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(wf_box,text="Project name",width=14).grid(row=0,column=0,sticky="w")
        ttk.Entry(wf_box,textvariable=self.workflow_project_name).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(wf_box,text="Create Config",command=self.create_workflow_config).grid(row=0,column=2,padx=3)
        ttk.Button(wf_box,text="Run Workflow",command=self.run_workflow_automation).grid(row=0,column=3,padx=3)
        wf_box.columnconfigure(1,weight=1)
        self.workflow_tree=self._tree_panel(imports,"Workflow automation summary",["item","value","note"], height=6)
        cmp_box=ttk.LabelFrame(imports,text="Run Comparison / Evidence Diff",padding=6); cmp_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(cmp_box,text="Old project",width=12).grid(row=0,column=0,sticky="w")
        ttk.Entry(cmp_box,textvariable=self.compare_old_project).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(cmp_box,text="Browse",command=lambda:self._browse_folder_var(self.compare_old_project)).grid(row=0,column=2,padx=3)
        ttk.Label(cmp_box,text="New project",width=12).grid(row=1,column=0,sticky="w")
        ttk.Entry(cmp_box,textvariable=self.compare_new_project).grid(row=1,column=1,sticky="ew",padx=4)
        ttk.Button(cmp_box,text="Browse",command=lambda:self._browse_folder_var(self.compare_new_project)).grid(row=1,column=2,padx=3)
        ttk.Label(cmp_box,text="Old dashboard",width=12).grid(row=2,column=0,sticky="w")
        ttk.Entry(cmp_box,textvariable=self.compare_old_dashboard).grid(row=2,column=1,sticky="ew",padx=4)
        ttk.Button(cmp_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.compare_old_dashboard)).grid(row=2,column=2,padx=3)
        ttk.Label(cmp_box,text="New dashboard",width=12).grid(row=3,column=0,sticky="w")
        ttk.Entry(cmp_box,textvariable=self.compare_new_dashboard).grid(row=3,column=1,sticky="ew",padx=4)
        ttk.Button(cmp_box,text="Browse",command=lambda:self._browse_dashboard_csv(self.compare_new_dashboard)).grid(row=3,column=2,padx=3)
        ttk.Button(cmp_box,text="Compare Runs",command=self.compare_runs).grid(row=4,column=1,sticky="w",pady=4)
        cmp_box.columnconfigure(1,weight=1)
        self.run_comparison_tree=self._tree_panel(imports,"Run comparison summary",["item","value","note"], height=6)
        cal_box=ttk.LabelFrame(imports,text="Calibration Dataset Mode",padding=6); cal_box.pack(fill="x",expand=False,pady=3)
        ttk.Label(cal_box,text="Dataset CSV",width=14).grid(row=0,column=0,sticky="w")
        ttk.Entry(cal_box,textvariable=self.calibration_dataset_path).grid(row=0,column=1,sticky="ew",padx=4)
        ttk.Button(cal_box,text="Browse",command=self.browse_calibration_dataset).grid(row=0,column=2,padx=4)
        ttk.Button(cal_box,text="Template",command=self.create_calibration_template).grid(row=0,column=3,padx=4)
        ttk.Label(cal_box,text="Candidate score",width=16).grid(row=1,column=0,sticky="w")
        ttk.Entry(cal_box,textvariable=self.calibration_candidate_score,width=18).grid(row=1,column=1,sticky="w",padx=4)
        ttk.Button(cal_box,text="Build Calibration Report",command=self.build_calibration_report).grid(row=1,column=2,columnspan=2,padx=4,sticky="w")
        ttk.Label(cal_box,text="Normalized CSV",width=14).grid(row=3,column=0,sticky="w")
        ttk.Entry(cal_box,textvariable=self.calibration_normalized_csv_path).grid(row=3,column=1,sticky="ew",padx=4)
        ttk.Button(cal_box,text="Browse Normalized",command=self.browse_calibration_normalized_csv).grid(row=3,column=2,padx=4)
        ttk.Button(cal_box,text="Build Model Cards",command=self.build_calibration_model_cards).grid(row=3,column=3,columnspan=2,padx=4,sticky="w")
        ttk.Button(cal_box,text="Build Evidence Report",command=self.build_evidence_engine_report).grid(row=1,column=4,padx=4,sticky="w")
        ttk.Label(cal_box,text="Project folder",width=14).grid(row=2,column=0,sticky="w")
        ttk.Entry(cal_box,textvariable=self.evidence_project_folder).grid(row=2,column=1,sticky="ew",padx=4)
        ttk.Button(cal_box,text="Browse Project",command=self.browse_evidence_project_folder).grid(row=2,column=2,padx=4)
        ttk.Button(cal_box,text="Auto-scan Project",command=self.autoscan_evidence_project).grid(row=2,column=3,columnspan=2,padx=4,sticky="w")
        cal_box.columnconfigure(1,weight=1)
        self.calibration_tree=self._tree_panel(imports,"Calibration summary",["item","value","note"], height=6)
        self.log=self._text_panel(imports,"Log", height=10)
        self._update_mode_hint(); self.analyze()

    def _set_progress(self, value: float, text: str):
        try:
            self.progress_var.set(max(0, min(100, float(value))))
            self.progress_text.set(str(text))
            self.update_idletasks()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    def _peptide_metadata_sequence(self):
        typed = canonical_peptide_notation(self.seq.get())
        # Preserve terminal notation from the text field even when a peptide PDB is loaded.
        # PDB files commonly lose Ac/NH2 caps, but the user-entered notation is still the
        # authoritative peptide chemistry for reporting and compatibility checks.
        if typed and (has_terminal_notation(typed) or typed.upper() in PEPTIDE_ALIASES):
            return typed
        return canonical_peptide_notation(self._active_peptide_sequence() or typed)

    def _update_mode_hint(self):
        tm, pm = self.target_mode.get(), self.peptide_mode.get()
        if tm == "Sequence" and pm == "PDB":
            self.mode_hint.set("Mode: target sequence + peptide PDB = descriptors only until target coordinates are supplied")
        elif tm == "Sequence":
            self.mode_hint.set("Mode: sequence + sequence = descriptors only; target coordinates required for 3D screening")
        elif pm == "PDB":
            self.mode_hint.set("Mode: target structure + peptide structure = direct contact analysis / local geometry screening")
        else:
            self.mode_hint.set("Mode: target structure + peptide sequence = Structure Builder + local rigid-body geometry screening")

    def _clean_path_value(self, value):
        """Normalize a path pasted from Windows dialogs, quoted strings, or drag/drop."""
        v = str(value or "").strip().strip('"').strip("'")
        # Windows drag/drop sometimes wraps a single path in braces.
        if v.startswith("{") and v.endswith("}") and "}" not in v[1:-1]:
            v = v[1:-1].strip()
        return v

    def _path_exists(self, value):
        try:
            v = self._clean_path_value(value)
            return bool(v and Path(v).exists())
        except Exception:
            return False

    def _target_path(self):
        return self._clean_path_value(self.pdb_path.get())

    def _resolved_target(self):
        return resolve_target_input(self.target_mode.get(), self._target_path(), self.target_seq.get())

    def _target_status_message(self):
        return str(self._resolved_target().get("message", ""))

    def _peptide_pdb_path(self):
        return self._clean_path_value(self.pep_pdb_path.get())

    def _active_target_sequence(self):
        resolved = self._resolved_target()
        return str(resolved.get("sequence") or "")

    def _active_peptide_sequence(self):
        # When peptide input is explicitly a PDB, prefer the sequence parsed from that file.
        # This prevents the default example peptide text from overriding the loaded peptide PDB.
        if self.peptide_mode.get() == "PDB" and self._path_exists(self.pep_pdb_path.get()):
            pdb_seq = pdb_to_sequence(self._peptide_pdb_path())
            if pdb_seq:
                return pdb_seq
        seq = clean_sequence(self.seq.get())
        if seq:
            return seq
        if self._path_exists(self.pep_pdb_path.get()):
            return pdb_to_sequence(self._peptide_pdb_path())
        return ""

    def _normalize_input_modes(self):
        """Smooth workflow: infer the selected input mode from filled fields when mismatched.

        This prevents valid jobs such as TARGET: sequence + PEPTIDE: PDB from
        being rejected just because the combobox state was left on the previous
        mode. Manual combobox choices are still respected when the corresponding
        field is present.
        """
        changed = []
        resolved_target = self._resolved_target()
        target_has_pdb = bool(resolved_target.get("mode") == "PDB" and resolved_target.get("status") == "ok")
        target_has_seq = bool(resolved_target.get("mode") == "Sequence" and resolved_target.get("sequence"))
        pep_has_pdb = self._path_exists(self.pep_pdb_path.get())
        pep_has_seq_text = bool(clean_sequence(self.seq.get()))

        # Prefer actual structure files when a file was loaded. If no target file is
        # present but a protein sequence/FASTA is present, switch to Sequence.
        if target_has_pdb and self.target_mode.get() != "PDB":
            self.target_mode.set("PDB"); changed.append("Target auto-set to PDB")
        elif (not target_has_pdb) and target_has_seq and self.target_mode.get() != "Sequence":
            self.target_mode.set("Sequence"); changed.append("Target auto-set to Sequence")

        # Peptide PDB must win over the default peptide sequence text. Otherwise the
        # Workbench appears to ignore PEPTIDE:PDB and runs the wrong branch.
        if pep_has_pdb and self.peptide_mode.get() != "PDB":
            self.peptide_mode.set("PDB"); changed.append("Peptide auto-set to PDB")
        elif (not pep_has_pdb) and pep_has_seq_text and self.peptide_mode.get() != "Sequence":
            self.peptide_mode.set("Sequence"); changed.append("Peptide auto-set to Sequence")
        if changed:
            try:
                self.log.insert("end", "Workflow auto-normalized: " + "; ".join(changed) + ".\n")
                self.log.see("end")
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
    def _make_tab(self, name):
        fr = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(fr, text=name)
        fr.columnconfigure(0, weight=1)
        return fr

    def _tree_panel(self, parent, title, cols, height=8):
        box = ttk.LabelFrame(parent, text=title, padding=4)
        box.pack(fill="both", expand=True, pady=3)
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        tr = ttk.Treeview(box, columns=cols, show="headings", height=height)
        for c in cols:
            tr.heading(c, text=c)
            width = 380 if c in ("note", "method_note", "interpretation") else 150
            if c in ("protein_window", "peptide_window"):
                width = 260
            if c in ("protein_residue", "peptide_residue", "target_residue"):
                width = 130
            if c in ("interaction", "contact_class"):
                width = 260
            if c in ("function", "input_used", "output"):
                width = 260
            tr.column(c, width=width, minwidth=80, stretch=True, anchor="w")
        y = ttk.Scrollbar(box, orient="vertical", command=tr.yview)
        x = ttk.Scrollbar(box, orient="horizontal", command=tr.xview)
        tr.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tr.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        return tr

    def _text_panel(self, parent, title, height=8):
        box = ttk.LabelFrame(parent, text=title, padding=4)
        box.pack(fill="both", expand=True, pady=3)
        txt = tk.Text(box, wrap="word", height=height)
        txt.pack(fill="both", expand=True)
        return txt

    def _tree_tab(self,name,cols):
        fr=ttk.Frame(self.tabs); self.tabs.add(fr,text=name); fr.rowconfigure(0,weight=1); fr.columnconfigure(0,weight=1)
        tr=ttk.Treeview(fr,columns=cols,show="headings")
        for c in cols:
            tr.heading(c,text=c); tr.column(c,width=190 if c!="note" else 420,minwidth=70,stretch=True,anchor="w")
        y=ttk.Scrollbar(fr,orient="vertical",command=tr.yview); x=ttk.Scrollbar(fr,orient="horizontal",command=tr.xview)
        tr.configure(yscrollcommand=y.set,xscrollcommand=x.set); tr.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); x.grid(row=1,column=0,sticky="ew")
        return tr
    def _text_tab(self,name):
        fr=ttk.Frame(self.tabs); self.tabs.add(fr,text=name); txt=tk.Text(fr,wrap="word"); txt.pack(fill="both",expand=True); return txt

    def toggle_input_panel(self):
        """Collapse/expand the large Input block so Target summary and result panes remain visible."""
        try:
            if getattr(self, "input_panel_visible", True):
                self.input_panel.pack_forget()
                self.input_panel_visible = False
                self.input_toggle_btn.configure(text="Expand Input")
                self.progress_text.set("Input collapsed: results area expanded")
            else:
                # Reinsert input panel directly above the command button row.
                self.input_panel.pack(fill="x", before=self.input_toggle_btn.master)
                self.input_panel_visible = True
                self.input_toggle_btn.configure(text="Collapse Input")
                self.progress_text.set("Input expanded")
        except Exception as exc:
            messagebox.showerror("Input panel toggle error", str(exc))

    def collapse_input_panel(self):
        """Programmatic helper used after Analyze/Run to maximize Target summary visibility."""
        if getattr(self, "input_panel_visible", True):
            self.toggle_input_panel()

    def _combined_result_report(self) -> pd.DataFrame:
        frames=[]
        screening=getattr(self,"screening_evidence",pd.DataFrame())
        external=getattr(self,"imported_results",pd.DataFrame())
        if isinstance(screening,pd.DataFrame) and not screening.empty:
            frames.append(normalize_result_report_df(screening))
        if isinstance(external,pd.DataFrame) and not external.empty:
            frames.append(normalize_result_report_df(external))
        if not frames:
            return normalize_result_report_df(pd.DataFrame(), getattr(self,"poses",pd.DataFrame()), getattr(self,"contacts",pd.DataFrame()))
        return pd.concat(frames, ignore_index=True)

    def _external_style_validation_df(self) -> pd.DataFrame:
        """Report what was measured internally and what still requires an external engine."""
        poses=getattr(self,"poses",pd.DataFrame())
        contacts=getattr(self,"contacts",pd.DataFrame())
        ext=getattr(self,"imported_results",pd.DataFrame())
        md_ext=getattr(self,"md_result_import",pd.DataFrame())
        rows=[
            {"engine_style":"Pepforge","metric":"local_geometry_candidates","value":len(poses) if isinstance(poses,pd.DataFrame) else 0,"unit":"count","interpretation":"Rigid-body geometry candidates generated from supplied target coordinates and peptide coordinates.","external_equivalent":"Not equivalent to Vina/Glide/HADDOCK scoring."},
            {"engine_style":"Pepforge","metric":"displayed_centroid_contacts","value":len(contacts) if isinstance(contacts,pd.DataFrame) else 0,"unit":"rows","interpretation":"Residue/token-centroid proximity rows.","external_equivalent":"Inspect atom-level/external docking contacts for quantitative interpretation."},
            {"engine_style":"External docking/affinity","metric":"import_status","value":"loaded" if isinstance(ext,pd.DataFrame) and not ext.empty else "not loaded","unit":"-","interpretation":"External ΔG/Kd/docking scores are shown only when imported from a user-supplied result.","external_equivalent":"Vina/PRODIGY/MM-PBSA/experiment as supplied by the user."},
            {"engine_style":"External molecular dynamics","metric":"import_status","value":"loaded" if isinstance(md_ext,pd.DataFrame) and not md_ext.empty else "not loaded","unit":"-","interpretation":"Pepforge does not generate MD trajectories internally.","external_equivalent":"GROMACS/OpenMM/NAMD/AMBER output import."},
            {"engine_style":"External validation","metric":"recommended_next_step","value":"export/import","unit":"workflow","interpretation":"Export coordinates and run the appropriate validated external tool before quantitative binding or stability claims.","external_equivalent":"Method chosen by the user/research protocol."},
        ]
        return pd.DataFrame(rows, columns=["engine_style","metric","value","unit","interpretation","external_equivalent"])

    def search_rcsb_target(self):
        query = self.rcsb_query.get().strip()
        if not query:
            # Use active protein sequence as fallback when user leaves the RCSB box empty.
            query = self._active_target_sequence()
            if query:
                self.rcsb_query.set(query)
        if not query:
            messagebox.showwarning("RCSB search", "Enter a PDB code, protein name, or protein sequence.")
            return
        try:
            self._set_progress(15, "Searching RCSB PDB...")
            results = search_rcsb(query, mode=self.rcsb_mode.get(), rows=20)
            self.rcsb_results = pd.DataFrame(results_to_rows(results))
            if self.rcsb_results.empty:
                self.rcsb_results = pd.DataFrame([{
                    "pdb_id":"", "title":"No RCSB result found", "method":"", "resolution_A":"",
                    "match_type":self.rcsb_mode.get(), "score":"", "source":"RCSB Search API", "polymer_entity":""
                }])
            self._write_tree(self.rcsb_tree, self.rcsb_results)
            self._set_progress(100, f"RCSB results: {len(results)}")
            self.log.insert("end", f"RCSB search complete: {len(results)} result(s). Query mode={self.rcsb_mode.get()}.\n")
            self.log.see("end")
        except Exception as exc:
            self._set_progress(0, "RCSB search failed")
            messagebox.showerror("RCSB search failed", str(exc))

    def _selected_rcsb_pdb_id(self):
        try:
            sel = self.rcsb_tree.selection()
            if sel:
                vals = self.rcsb_tree.item(sel[0], "values")
                if vals:
                    return str(vals[0]).strip().upper()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        try:
            df = getattr(self, "rcsb_results", pd.DataFrame())
            if df is not None and not df.empty:
                return str(df.iloc[0].get("pdb_id", "")).strip().upper()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
        return ""

    def fetch_selected_rcsb_target(self):
        pdb_id = self._selected_rcsb_pdb_id()
        if not pdb_id:
            messagebox.showwarning("RCSB fetch", "Select a valid RCSB result first.")
            return
        try:
            out = self._effective_outdir() / "rcsb_downloads"
            fmt = self.rcsb_format.get()
            self._set_progress(20, f"Downloading {pdb_id} from RCSB...")
            path = download_rcsb_structure(pdb_id, out, fmt=fmt)
            self.pdb_path.set(path)
            self.target_mode.set("PDB")
            self._set_progress(100, f"Fetched {pdb_id}")
            self.log.insert("end", f"RCSB structure fetched and set as target: {path}\n")
            self.log.see("end")
            self.analyze()
        except Exception as exc:
            self._set_progress(0, "RCSB fetch failed")
            messagebox.showerror("RCSB fetch failed", str(exc))

    def open_selected_rcsb_page(self):
        pdb_id = self._selected_rcsb_pdb_id()
        if not pdb_id:
            messagebox.showwarning("RCSB page", "Select a valid RCSB result first.")
            return
        import webbrowser
        webbrowser.open(f"https://www.rcsb.org/structure/{pdb_id}")



    def _selected_target_chains(self):
        raw = self.target_selected_chains.get().strip()
        if not raw:
            return []
        return [x.strip() for x in re.split(r"[,;\s]+", raw) if x.strip()]

    def prepare_target_structure(self):
        path = self._target_path()
        if not path or not Path(path).exists():
            messagebox.showwarning("Target preparation", "Load or fetch a target PDB/mmCIF first.")
            return
        try:
            self._set_progress(15, "Preparing target structure...")
            paths = export_target_preparation_package(path, self._effective_outdir() / "target_preparation", selected_chains=self._selected_target_chains(), keep_waters=bool(self.keep_waters.get()), keep_ions=bool(self.keep_ions.get()), keep_ligands=bool(self.keep_ligands.get()))
            cleaned = paths.get("target_cleaned_pdb", "")
            if cleaned:
                self.pdb_path.set(cleaned)
                self.target_mode.set("PDB")
            self.target_prep_report = pd.DataFrame([
                {"item":"cleaned_pdb", "value":cleaned, "note":"Set as current target path."},
                {"item":"chain_summary", "value":paths.get("target_chain_summary", ""), "note":"Review chain roles before docking."},
                {"item":"quality_warnings", "value":paths.get("target_quality_warnings", ""), "note":"Check before interpreting contacts."},
            ])
            self._write_tree(self.target_prep_tree, self.target_prep_report)
            self._set_progress(100, "Target prepared")
            self.log.insert("end", f"Target preparation complete. Cleaned target set: {cleaned}\n")
            self.log.see("end")
            self.analyze()
        except Exception as exc:
            self._set_progress(0, "Target preparation failed")
            messagebox.showerror("Target preparation failed", str(exc))



    def build_initial_complex(self):
        self._normalize_input_modes()
        target = self._target_path()
        if not target or not Path(target).exists():
            messagebox.showwarning("Complex builder", "Load, fetch, or prepare a target PDB/mmCIF first.")
            return
        try:
            self._set_progress(15, "Building initial complex...")
            out = self._effective_outdir() / "complex_builder"
            pep_pdb = self._peptide_pdb_path() if self._path_exists(self.pep_pdb_path.get()) else None
            chain_id = (self.complex_chain_id.get().strip() or "P")[:1]
            paths = export_complex_builder_package(
                target_pdb=target,
                output_dir=out,
                peptide_pdb=pep_pdb,
                peptide_sequence=self._peptide_metadata_sequence(),
                target_chains=self._selected_target_chains() if hasattr(self, "_selected_target_chains") else [],
                peptide_chain_id=chain_id,
            )
            self.complex_builder_report = pd.DataFrame([
                {"item":"initial_complex_candidate_pdb", "value":paths.get("initial_complex_candidate_pdb",""), "note":"Initial screening complex; not final docking proof."},
                {"item":"complex_contact_preview", "value":paths.get("complex_contact_preview",""), "note":"Distance-based contact preview."},
                {"item":"complex_clash_report", "value":paths.get("complex_clash_report",""), "note":"Review before interpretation."},
            ])
            self._write_tree(self.complex_tree, self.complex_builder_report)
            self._set_progress(100, "Initial complex built")
            self.log.insert("end", f"Initial complex builder package exported: {paths.get('initial_complex_candidate_pdb','')}\n")
            self.log.see("end")
        except Exception as exc:
            self._set_progress(0, "Complex builder failed")
            messagebox.showerror("Complex builder failed", str(exc))



    def browse_calibration_dataset(self):
        p = filedialog.askopenfilename(filetypes=[("Calibration CSV","*.csv"),("All files","*.*")])
        if p:
            self.calibration_dataset_path.set(p)

    def create_calibration_template(self):
        try:
            out = self._effective_outdir() / "calibration_dataset_mode"
            path = export_calibration_dataset_template(out)
            self.calibration_dataset_path.set(path)
            self.log.insert("end", f"Calibration dataset template created: {path}\n")
            self.log.see("end")
            messagebox.showinfo("Calibration template", "Calibration dataset template created.")
        except Exception as exc:
            messagebox.showerror("Calibration template failed", str(exc))

    def build_calibration_report(self):
        dataset = self.calibration_dataset_path.get().strip()
        if not dataset or not Path(dataset).exists():
            messagebox.showwarning("Calibration Dataset Mode", "Choose or create a calibration dataset CSV first.")
            return
        cand = self.calibration_candidate_score.get().strip()
        try:
            self._set_progress(20, "Building calibration report...")
            out = self._effective_outdir()
            paths = export_calibration_report(dataset, out, candidate_score=(cand if cand else None))
            rows = [
                {"item":"normalized_dataset", "value":paths.get("calibration_dataset_normalized",""), "note":"normalized affinity and score table"},
                {"item":"class_statistics", "value":paths.get("calibration_class_statistics",""), "note":"score distributions by potency class"},
                {"item":"candidate_prediction", "value":paths.get("candidate_calibration_prediction",""), "note":"claim-bounded candidate class prediction"},
                {"item":"claim_guard", "value":paths.get("calibration_claim_guard_table",""), "note":"blocks final Kd / true binder overclaims"},
            ]
            self.calibration_summary = pd.DataFrame(rows)
            self._write_tree(self.calibration_tree, self.calibration_summary)
            self._set_progress(100, "Calibration report built")
            self.log.insert("end", "Calibration Dataset Mode report exported.\n")
            self.log.see("end")
        except Exception as exc:
            self._set_progress(0, "Calibration failed")
            messagebox.showerror("Calibration Dataset Mode failed", str(exc))



    def build_evidence_engine_report(self):
        try:
            out = self._effective_outdir()
            # Evidence Engine can run even when some evidence files are absent.
            # It reports missing evidence instead of failing.
            paths = export_evidence_engine_report(output_dir=out)
            rows = [
                {"item":"evidence_report", "value":paths.get("evidence_report_md",""), "note":"overall evidence grade and claim wording"},
                {"item":"claim_guard", "value":paths.get("evidence_claim_guard_table",""), "note":"allowed/blocked wording"},
                {"item":"missing_validation", "value":paths.get("missing_validation_checklist",""), "note":"recommended next validation steps"},
            ]
            self.evidence_summary = pd.DataFrame(rows)
            if hasattr(self, "calibration_tree"):
                self._write_tree(self.calibration_tree, self.evidence_summary)
            self.log.insert("end", "Pepforge Evidence Engine report exported.\n")
            self.log.see("end")
            messagebox.showinfo("Evidence Engine", "Evidence Engine report exported.")
        except Exception as exc:
            messagebox.showerror("Evidence Engine failed", str(exc))



    def browse_evidence_project_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.evidence_project_folder.set(p)

    def autoscan_evidence_project(self):
        folder = self.evidence_project_folder.get().strip() or str(self._effective_outdir())
        if not folder or not Path(folder).exists():
            messagebox.showwarning("Evidence Engine Auto-scan", "Choose an existing project/output folder.")
            return
        try:
            paths = export_evidence_engine_report_from_project(folder, output_dir=folder)
            rows = [
                {"item":"readable_report", "value":paths.get("evidence_report_readable_md",""), "note":"human-readable evidence summary"},
                {"item":"autoscan_trace", "value":paths.get("project_autoscan_trace",""), "note":"which files were auto-detected"},
                {"item":"evidence_summary", "value":paths.get("evidence_summary_json",""), "note":"machine-readable evidence grade"},
                {"item":"missing_validation", "value":paths.get("missing_validation_checklist",""), "note":"next validation steps"},
            ]
            self.evidence_summary = pd.DataFrame(rows)
            if hasattr(self, "calibration_tree"):
                self._write_tree(self.calibration_tree, self.evidence_summary)
            self.log.insert("end", f"Evidence Engine auto-scan complete: {folder}\n")
            self.log.see("end")
            messagebox.showinfo("Evidence Engine Auto-scan", "Project folder auto-scan report exported.")
        except Exception as exc:
            messagebox.showerror("Evidence Engine Auto-scan failed", str(exc))



    def select_binding_site(self):
        path = self._target_path()
        if not path or not Path(path).exists():
            messagebox.showwarning("Binding Site Selector", "Load, fetch, or prepare a target PDB first.")
            return
        try:
            ligand_cutoff = float(self.binding_site_ligand_cutoff.get() or 6.0)
            seed_cutoff = float(self.binding_site_seed_cutoff.get() or 8.0)
            out = self._effective_outdir()
            paths = export_binding_site_selection_package(
                pdb_path=path,
                output_dir=out,
                selected_chains=self._selected_target_chains() if hasattr(self, "_selected_target_chains") else [],
                seed_residues=self.binding_site_seed_residues.get(),
                ligand_cutoff_A=ligand_cutoff,
                seed_cutoff_A=seed_cutoff,
            )
            rows = [
                {"item":"selected_residues", "value":paths.get("selected_binding_site_residues",""), "note":"candidate binding-site residue list"},
                {"item":"ligands", "value":paths.get("ligand_cofactor_summary",""), "note":"detected ligands/cofactors"},
                {"item":"pymol_selection", "value":paths.get("binding_site_selection_pml",""), "note":"PyMOL selection helper"},
                {"item":"summary", "value":paths.get("binding_site_summary",""), "note":"machine-readable site summary"},
            ]
            self.binding_site_summary = pd.DataFrame(rows)
            self._write_tree(self.binding_site_tree, self.binding_site_summary)
            self.log.insert("end", "Binding Site Selector package exported.\n")
            self.log.see("end")
            messagebox.showinfo("Binding Site Selector", "Binding-site selection package exported.")
        except Exception as exc:
            messagebox.showerror("Binding Site Selector failed", str(exc))



    def browse_external_docking_file(self):
        p = filedialog.askopenfilename(filetypes=[("Docking result files","*.txt *.log *.out *.csv *.tsv"),("All files","*.*")])
        if p:
            self.external_docking_result_path.set(p)

    def browse_external_docking_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.external_docking_result_path.set(p)

    def import_external_docking_results(self):
        src = self.external_docking_result_path.get().strip()
        if not src or not Path(src).exists():
            messagebox.showwarning("External Docking Result Import", "Choose an external docking result file or folder.")
            return
        try:
            paths = export_external_docking_import_package(src, str(self._effective_outdir()))
            rows = [
                {"item":"normalized_scores", "value":paths.get("external_docking_scores_normalized",""), "note":"tool-aware normalized score table"},
                {"item":"summary", "value":paths.get("external_docking_import_summary",""), "note":"detected tool/record summary"},
                {"item":"best_by_group", "value":paths.get("external_docking_best_by_group",""), "note":"best rows per tool/score-type group"},
                {"item":"claim_guard", "value":paths.get("external_docking_claim_guard_table",""), "note":"blocks score overclaims"},
            ]
            self.external_docking_summary = pd.DataFrame(rows)
            if hasattr(self, "external_docking_tree"):
                self._write_tree(self.external_docking_tree, self.external_docking_summary)
            self.log.insert("end", "External docking results imported and normalized.\n")
            self.log.see("end")
            messagebox.showinfo("External Docking Result Import", "External docking results imported.")
        except Exception as exc:
            messagebox.showerror("External Docking Import failed", str(exc))



    def browse_calibration_normalized_csv(self):
        p = filedialog.askopenfilename(filetypes=[("Calibration normalized CSV","*.csv"),("All files","*.*")])
        if p:
            self.calibration_normalized_csv_path.set(p)

    def build_calibration_model_cards(self):
        csv_path = self.calibration_normalized_csv_path.get().strip()
        if not csv_path:
            candidate = self._effective_outdir() / "calibration_dataset_mode" / "calibration_dataset_normalized.csv"
            if candidate.exists():
                csv_path = str(candidate)
                self.calibration_normalized_csv_path.set(csv_path)
        if not csv_path or not Path(csv_path).exists():
            messagebox.showwarning("Calibration Model Cards", "Choose calibration_dataset_normalized.csv or build Calibration Report first.")
            return
        try:
            paths = export_calibration_visualization_package(csv_path, str(self._effective_outdir()))
            rows = [
                {"item":"model_card_index_csv", "value":paths.get("target_model_card_index_csv",""), "note":"target-wise model-card index"},
                {"item":"model_card_index_md", "value":paths.get("target_model_card_index_md",""), "note":"readable model-card index"},
                {"item":"manifest", "value":paths.get("calibration_visualization_manifest",""), "note":"generated card manifest"},
            ]
            self.calibration_visualization_summary = pd.DataFrame(rows)
            if hasattr(self, "calibration_tree"):
                self._write_tree(self.calibration_tree, self.calibration_visualization_summary)
            self.log.insert("end", "Calibration visualization/model cards exported.\n")
            self.log.see("end")
            messagebox.showinfo("Calibration Model Cards", "Target-specific model cards exported.")
        except Exception as exc:
            messagebox.showerror("Calibration Model Cards failed", str(exc))



    def create_project_session(self):
        try:
            name = self.project_session_name.get().strip() or "Pepforge_Project"
            out = self._effective_outdir()
            paths = create_project_session_package(name, out, description="Pepforge workflow session")
            self.project_session_file.set(paths.get("session_json",""))
            rows = [
                {"item":"session_json", "value":paths.get("session_json",""), "note":"portable project state file"},
                {"item":"stage_progress", "value":paths.get("project_stage_progress",""), "note":"stage status table"},
                {"item":"next_actions", "value":paths.get("project_next_actions",""), "note":"recommended next steps"},
                {"item":"summary", "value":paths.get("project_session_summary",""), "note":"readable resume summary"},
            ]
            self.project_session_summary = pd.DataFrame(rows)
            if hasattr(self, "project_session_tree"):
                self._write_tree(self.project_session_tree, self.project_session_summary)
            self.log.insert("end", "Project session package created.\n")
            self.log.see("end")
            messagebox.showinfo("Project Session", "Project session package created.")
        except Exception as exc:
            messagebox.showerror("Project Session failed", str(exc))

    def load_project_session_file(self):
        p = filedialog.askopenfilename(filetypes=[("Pepforge session","pepforge_project_session.json"),("JSON","*.json"),("All files","*.*")])
        if not p:
            return
        try:
            session = load_project_session(p)
            self.project_session_file.set(p)
            self.project_session_name.set(session.get("project_name","Pepforge_Project"))
            paths = export_session_summary(session, str(self._effective_outdir()))
            rows = [
                {"item":"loaded_session", "value":p, "note":"loaded project session"},
                {"item":"current_stage", "value":session.get("current_stage",""), "note":"resume point"},
                {"item":"summary", "value":paths.get("project_session_summary",""), "note":"updated session summary"},
            ]
            self.project_session_summary = pd.DataFrame(rows)
            if hasattr(self, "project_session_tree"):
                self._write_tree(self.project_session_tree, self.project_session_summary)
            self.log.insert("end", "Project session loaded.\n")
            self.log.see("end")
        except Exception as exc:
            messagebox.showerror("Load Project Session failed", str(exc))

    def save_project_session_summary(self):
        try:
            if self.project_session_file.get().strip() and Path(self.project_session_file.get().strip()).exists():
                session = load_project_session(self.project_session_file.get().strip())
            else:
                session = None
            if session is None:
                name = self.project_session_name.get().strip() or "Pepforge_Project"
                paths = create_project_session_package(name, str(self._effective_outdir()), description="Pepforge workflow session")
            else:
                paths = export_session_summary(session, str(self._effective_outdir()))
            rows = [
                {"item":"session_json", "value":paths.get("session_json",""), "note":"portable project state file"},
                {"item":"summary", "value":paths.get("project_session_summary",""), "note":"readable resume summary"},
            ]
            self.project_session_summary = pd.DataFrame(rows)
            if hasattr(self, "project_session_tree"):
                self._write_tree(self.project_session_tree, self.project_session_summary)
            messagebox.showinfo("Project Session", "Project session summary saved.")
        except Exception as exc:
            messagebox.showerror("Save Project Session failed", str(exc))



    def _browse_dashboard_csv(self, var):
        p = filedialog.askopenfilename(filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if p:
            var.set(p)

    def build_candidate_dashboard(self):
        try:
            paths = export_candidate_dashboard(
                output_dir=str(self._effective_outdir()),
                design_candidates_csv=self.dashboard_design_csv.get().strip() or None,
                docking_contacts_csv=self.dashboard_docking_csv.get().strip() or None,
                external_docking_scores_csv=self.dashboard_external_csv.get().strip() or None,
                calibration_predictions_csv=self.dashboard_calibration_csv.get().strip() or None,
                experimental_candidate_summary_csv=self.dashboard_experimental_csv.get().strip() or None,
            )
            rows = [
                {"item":"dashboard_csv", "value":paths.get("candidate_comparison_dashboard_csv",""), "note":"ranked candidate table"},
                {"item":"dashboard_md", "value":paths.get("candidate_comparison_dashboard_md",""), "note":"readable dashboard report"},
                {"item":"dashboard_chart", "value":paths.get("candidate_dashboard_top_svg",""), "note":"top candidate SVG chart"},
                {"item":"summary", "value":paths.get("candidate_dashboard_summary",""), "note":"machine-readable summary"},
            ]
            self.candidate_dashboard_summary = pd.DataFrame(rows)
            if hasattr(self, "candidate_dashboard_tree"):
                self._write_tree(self.candidate_dashboard_tree, self.candidate_dashboard_summary)
            self.log.insert("end", "Candidate Comparison Dashboard exported.\n")
            self.log.see("end")
            messagebox.showinfo("Candidate Dashboard", "Candidate Comparison Dashboard exported.")
        except Exception as exc:
            messagebox.showerror("Candidate Dashboard failed", str(exc))



    def create_experimental_template(self):
        try:
            path = make_experimental_template(self._effective_outdir() / "experimental_data_import")
            self.experimental_import_csv.set(path)
            self.log.insert("end", f"Experimental data template created: {path}\n")
            self.log.see("end")
            messagebox.showinfo("Experimental Data Import", "Experimental template created.")
        except Exception as exc:
            messagebox.showerror("Experimental template failed", str(exc))

    def import_experimental_data(self):
        src = self.experimental_import_csv.get().strip()
        if not src or not Path(src).exists():
            messagebox.showwarning("Experimental Data Import", "Choose an experimental assay CSV first.")
            return
        try:
            paths = export_experimental_import_package(src, str(self._effective_outdir()))
            self.dashboard_experimental_csv.set(paths.get("experimental_candidate_summary", ""))
            rows = [
                {"item":"normalized", "value":paths.get("experimental_data_normalized", ""), "note":"normalized assay data"},
                {"item":"candidate_summary", "value":paths.get("experimental_candidate_summary", ""), "note":"median nM and class per candidate"},
                {"item":"claim_guard", "value":paths.get("experimental_claim_guard_table", ""), "note":"assay claim boundary"},
                {"item":"report", "value":paths.get("experimental_import_report", ""), "note":"readable experimental report"},
            ]
            self.experimental_import_summary = pd.DataFrame(rows)
            if hasattr(self, "experimental_import_tree"):
                self._write_tree(self.experimental_import_tree, self.experimental_import_summary)
            self.log.insert("end", "Experimental data imported.\n")
            self.log.see("end")
            messagebox.showinfo("Experimental Data Import", "Experimental data imported.")
        except Exception as exc:
            messagebox.showerror("Experimental import failed", str(exc))



    def create_workflow_config(self):
        try:
            cfg = default_workflow_config(self.workflow_project_name.get().strip() or "Pepforge_Project")
            path = save_workflow_config(cfg, str(self._effective_outdir()))
            self.workflow_config_path.set(path)
            rows = [{"item":"workflow_config", "value":path, "note":"editable workflow configuration"}]
            self.workflow_summary = pd.DataFrame(rows)
            if hasattr(self, "workflow_tree"):
                self._write_tree(self.workflow_tree, self.workflow_summary)
            self.log.insert("end", f"Workflow config created: {path}\n")
            self.log.see("end")
            messagebox.showinfo("Workflow Automation", "Workflow config created.")
        except Exception as exc:
            messagebox.showerror("Workflow config failed", str(exc))

    def run_workflow_automation(self):
        try:
            cfg_path = self.workflow_config_path.get().strip()
            if cfg_path and Path(cfg_path).exists():
                from peptiforg_core.workflow_automation_runner import load_workflow_config
                cfg = load_workflow_config(cfg_path)
            else:
                cfg = default_workflow_config(self.workflow_project_name.get().strip() or "Pepforge_Project")
            paths = run_workflow(cfg, str(self._effective_outdir()))
            rows = [
                {"item":"stage_results", "value":paths.get("workflow_stage_results",""), "note":"stage status table"},
                {"item":"manifest", "value":paths.get("workflow_run_manifest",""), "note":"workflow artifact manifest"},
                {"item":"report", "value":paths.get("workflow_run_report",""), "note":"readable run report"},
                {"item":"claim_guard", "value":paths.get("workflow_claim_guard_table",""), "note":"automation claim boundary"},
            ]
            self.workflow_summary = pd.DataFrame(rows)
            if hasattr(self, "workflow_tree"):
                self._write_tree(self.workflow_tree, self.workflow_summary)
            self.log.insert("end", "Workflow automation completed.\n")
            self.log.see("end")
            messagebox.showinfo("Workflow Automation", "Workflow automation completed.")
        except Exception as exc:
            messagebox.showerror("Workflow automation failed", str(exc))



    def _browse_folder_var(self, var):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    def compare_runs(self):
        oldp = self.compare_old_project.get().strip()
        newp = self.compare_new_project.get().strip()
        if not oldp or not Path(oldp).exists() or not newp or not Path(newp).exists():
            messagebox.showwarning("Run Comparison", "Choose existing old and new project folders.")
            return
        try:
            paths = export_run_comparison_package(
                old_project_dir=oldp,
                new_project_dir=newp,
                output_dir=str(self._effective_outdir()),
                old_dashboard_csv=self.compare_old_dashboard.get().strip() or None,
                new_dashboard_csv=self.compare_new_dashboard.get().strip() or None,
            )
            rows = [
                {"item":"candidate_delta", "value":paths.get("candidate_rank_delta",""), "note":"candidate rank/score delta"},
                {"item":"changed_files", "value":paths.get("changed_files_inventory",""), "note":"added/removed/modified files"},
                {"item":"evidence_delta", "value":paths.get("evidence_delta_summary",""), "note":"evidence summary delta"},
                {"item":"report", "value":paths.get("run_comparison_report",""), "note":"readable comparison report"},
            ]
            self.run_comparison_summary = pd.DataFrame(rows)
            if hasattr(self, "run_comparison_tree"):
                self._write_tree(self.run_comparison_tree, self.run_comparison_summary)
            self.log.insert("end", "Run comparison package exported.\n")
            self.log.see("end")
            messagebox.showinfo("Run Comparison", "Run comparison package exported.")
        except Exception as exc:
            messagebox.showerror("Run Comparison failed", str(exc))


    def browse_pdb(self):
        p=filedialog.askopenfilename(filetypes=[("Structure files","*.pdb *.ent *.cif *.mmcif *.txt"),("All files","*.*")])
        if p: self.pdb_path.set(p); self.analyze()
    def browse_peptide_pdb(self):
        p=filedialog.askopenfilename(filetypes=[("Structure files","*.pdb *.ent *.cif *.mmcif *.txt"),("All files","*.*")])
        if p: self.pep_pdb_path.set(p); self.analyze()
    def browse_result(self):
        p=filedialog.askopenfilename(filetypes=[("Docking/MD result files","*.csv *.xlsx *.pdb *.cif *.mmcif *.txt *.log *.out *.xvg"),("All files","*.*")])
        if p: self.result_path.set(p); self.import_external_result()
    def browse_outdir(self):
        p=filedialog.askdirectory()
        if p: self.outdir.set(p)

    def _all_docking_data_tables(self):
        """Return complete Docking Workbench tables for full-data popups/export review.

        These popups are intentionally separate from the compact public panes. They
        prevent regressions where data still exists internally/export-wise but is
        hard to see because the Input panel or notebook page is too crowded.
        """
        active_peptide_seq = self._active_peptide_sequence() if hasattr(self, "_active_peptide_sequence") else str(self.seq.get())
        tables = {
            "peptide_properties": getattr(self, "props", pd.DataFrame()),
            "terminal_state": getattr(self, "terminal_status", pd.DataFrame()),
            "target_structure_summary": getattr(self, "pdb", pd.DataFrame()),
            "target_preparation_report": getattr(self, "target_prep_report", pd.DataFrame()),
            "binding_site_selector_report": getattr(self, "binding_site_report", pd.DataFrame()),
            "rcsb_pdb_search_results": getattr(self, "rcsb_results", pd.DataFrame()),
            "sequence_pair_heuristic": getattr(self, "seqpair", pd.DataFrame()),
            "workflow": getattr(self, "pipeline", pd.DataFrame()),
            "modified_residue_compatibility": getattr(self, "compatibility", pd.DataFrame()),
            "terminal_modifier_policy": terminal_modifier_policy_df(active_peptide_seq),
            "all_atom_parameter_requirements": all_atom_parameter_requirements_df(active_peptide_seq),
            "docking_pose_candidates": getattr(self, "poses", pd.DataFrame()),
            "docking_residue_contact_report": getattr(self, "contacts", pd.DataFrame()),
            "docking_residue_contact_report_full": getattr(self, "all_contacts", getattr(self, "contacts", pd.DataFrame())),
            "docking_atom_contact_report": getattr(self, "atom_contacts", pd.DataFrame()),
            "screening_evidence_summary": getattr(self, "screening_evidence", screening_evidence_df(getattr(self, "poses", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame()))),
            "external_result_import_summary": getattr(self, "imported_results", pd.DataFrame()),
            "external_style_validation_summary": self._external_style_validation_df(),
            "simulation_summary": simulation_summary_df(getattr(self, "poses", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame()), getattr(self, "risk", pd.DataFrame())),
            "molecular_dynamics_status": getattr(self, "md_summary", pd.DataFrame()),
            "md_result_import_summary": getattr(self, "md_result_import", pd.DataFrame()),
            "peptide_risk_summary": getattr(self, "risk", pd.DataFrame()),
            "docking_readiness": getattr(self, "readiness", pd.DataFrame()),
            "result_interpretation": self._interpretation_df() if hasattr(self, "_interpretation_df") else pd.DataFrame(),
            "initial_complex_builder": getattr(self, "complex_builder_report", pd.DataFrame()),
        }
        return tables

    def show_data_full(self, group="results"):
        """Open a resizable full-data window, similar to SPPS Planner *full buttons."""
        group = str(group or "results").lower()
        groups = {
            "input": ["peptide_properties", "terminal_state", "target_structure_summary", "target_preparation_report", "binding_site_selector_report", "rcsb_pdb_search_results", "sequence_pair_heuristic", "workflow", "modified_residue_compatibility", "terminal_modifier_policy", "all_atom_parameter_requirements"],
            "results": ["result_interpretation", "docking_pose_candidates", "screening_evidence_summary", "external_result_import_summary", "external_style_validation_summary", "peptide_risk_summary", "docking_readiness", "simulation_summary", "docking_residue_contact_report", "docking_residue_contact_report_full", "docking_atom_contact_report"],
            "md": ["external_style_validation_summary", "molecular_dynamics_status", "md_result_import_summary"],
        }
        tables = self._all_docking_data_tables()
        names = groups.get(group, groups["results"])
        win = tk.Toplevel(self)
        win.title(f"Docking Workbench - {group.title()} data full")
        win.geometry("1180x760")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
        nb = ttk.Notebook(win)
        nb.grid(row=0, column=0, sticky="nsew")
        for name in names:
            df = tables.get(name, pd.DataFrame())
            fr = ttk.Frame(nb)
            nb.add(fr, text=name[:28])
            fr.rowconfigure(0, weight=1)
            fr.columnconfigure(0, weight=1)
            if not isinstance(df, pd.DataFrame) or df.empty:
                df = pd.DataFrame([{"status": "no data", "note": "Run Analyze/Run, load an output folder, or import external results."}])
            cols = [str(c) for c in df.columns]
            tr = ttk.Treeview(fr, columns=cols, show="headings")
            for c in cols:
                width = 180
                if "note" in c.lower() or "interpretation" in c.lower() or "external" in c.lower():
                    width = 420
                if "path" in c.lower() or "file" in c.lower():
                    width = 360
                tr.heading(c, text=c)
                tr.column(c, width=width, minwidth=80, stretch=True, anchor="w")
            y = ttk.Scrollbar(fr, orient="vertical", command=tr.yview)
            x = ttk.Scrollbar(fr, orient="horizontal", command=tr.xview)
            tr.configure(yscrollcommand=y.set, xscrollcommand=x.set)
            tr.grid(row=0, column=0, sticky="nsew")
            y.grid(row=0, column=1, sticky="ns")
            x.grid(row=1, column=0, sticky="ew")
            for _, r in df.iterrows():
                tr.insert("", "end", values=[r.get(c, "") for c in cols])
        self.progress_text.set(f"{group.title()} data full opened")

    def _write_tree(self,tree,df):
        tree.delete(*tree.get_children())
        if df is None or df.empty:
            try:
                cols=list(tree["columns"])
                if cols:
                    tree.insert("", "end", values=["no data", "", "Run Analyze/Run or load a valid file; this pane is intentionally not hidden."][:len(cols)])
            except Exception:
                LOGGER.debug("Optional operation skipped", exc_info=True)
            return
        for _,r in df.iterrows(): tree.insert("","end",values=[r.get(c,"") for c in tree["columns"]])

    def _screening_validation_reasons(self):
        """Return user-facing validation reasons without opening a dialog.

        Keeping validation computation separate makes the Run Screening callback
        testable and prevents silent pre-dialog failures in the windowed EXE.
        """
        reasons=[]
        resolved = self._resolved_target()
        if resolved.get("status") != "ok":
            reasons.append(str(resolved.get("message") or "Target was not recognized."))
        else:
            if resolved.get("mode") in {"PDB", "Sequence"} and self.target_mode.get() != resolved.get("mode"):
                self.target_mode.set(str(resolved.get("mode")))
        if self.peptide_mode.get()=="PDB":
            pp=Path(self._peptide_pdb_path())
            if not pp.exists() and not (resolved.get("mode")=="PDB" and resolved.get("path") and structure_has_multiple_chains(resolved.get("path"))):
                reasons.append("Peptide PDB is missing. For complex structures, load a multi-chain complex in the PDB box or provide a separate peptide PDB.")
        else:
            raw_peptide = canonical_peptide_notation(self.seq.get())
            if not raw_peptide:
                reasons.append("Peptide sequence is empty. Enter a peptide sequence or load a peptide PDB.")
            else:
                try:
                    token_rows = _split_peptide_model_tokens(raw_peptide)
                    unsupported = [r.get("token","") for r in token_rows if r.get("class") == "unsupported"]
                    if unsupported:
                        reasons.append("Unsupported peptide token(s): " + ", ".join(map(str,unsupported)) + ". No canonical-residue surrogate will be substituted.")
                    misplaced = misplaced_nterm_modifier_tokens(raw_peptide)
                    if misplaced:
                        reasons.append("N-terminal-only modifier appears internally: " + ", ".join(misplaced) + ". Use explicit supported attachment notation.")
                    if not token_rows:
                        reasons.append("Peptide sequence did not produce any supported structure tokens.")
                except Exception as exc:
                    reasons.append("Peptide sequence/structure parsing failed: " + str(exc))
        return reasons, resolved

    def _validate_for_run(self):
        reasons, resolved = self._screening_validation_reasons()
        if reasons:
            try:
                self.log.insert("end", "Input validation failed:\n" + "\n".join("- "+r for r in reasons) + "\n")
                self.log.see("end")
            except Exception as exc:
                LOGGER.debug("Could not write validation failure to UI log: %s", exc)
            messagebox.showerror("Docking input check failed", "\n".join("- "+r for r in reasons))
            return False
        try:
            self.log.insert("end", "Target resolver: " + str(resolved.get("message","")) + "\n")
            self.log.see("end")
        except Exception as exc:
            LOGGER.debug("Could not write target resolver message: %s", exc)
        return True

    def import_external_result(self):
        p=Path(self.result_path.get()); rows=[]
        if not p.exists(): rows.append({"source":"external","field":"status","value":"not found","note":str(p)})
        elif p.suffix.lower()==".csv":
            df=pd.read_csv(p); rows.append({"source":p.name,"field":"rows","value":len(df),"note":"CSV docking/result table imported"}); rows.append({"source":p.name,"field":"columns","value":", ".join(map(str,df.columns[:12])),"note":"first columns"})
        elif p.suffix.lower() in (".xlsx",".xls"):
            xl=pd.ExcelFile(p); rows.append({"source":p.name,"field":"sheets","value":", ".join(xl.sheet_names),"note":"Excel docking/result workbook imported"})
        elif p.suffix.lower() in (".pdb",".ent",".cif",".mmcif"):
            rows.extend(pdb_summary_df(p).assign(source=p.name).rename(columns={"field":"field","value":"value","note":"note"}).to_dict("records"))
            for r in rows: r.setdefault("source",p.name)
        elif p.suffix.lower()==".xvg":
            self.md_result_import=parse_external_validation_file(p)
            self._write_tree(self.md_result_tree,self.md_result_import)
            rows.append({"source":p.name,"field":"validation_import","value":len(self.md_result_import),"note":"External validation result imported"})
        elif p.suffix.lower() in (".txt", ".log", ".out"):
            prod=parse_affinity_text(p)
            rows.extend(prod.to_dict("records"))
        else: rows.append({"source":p.name,"field":"size_bytes","value":p.stat().st_size,"note":"generic result file"})
        self.imported_results=normalize_result_report_df(pd.DataFrame(rows)); self._write_tree(self.import_tree,self._combined_result_report())

    def analyze(self):
        try:
            self._set_progress(5, "Analyzing inputs...")
            self._normalize_input_modes()
            active_peptide_seq = self._peptide_metadata_sequence()
            self.props = estimate_properties(active_peptide_seq)
            self.terminal_status = terminal_status_df(active_peptide_seq)
            resolved_target = self._resolved_target()
            if resolved_target.get("mode") == "PDB" and resolved_target.get("path"):
                self.target_atoms = parse_pdb_atoms(resolved_target.get("path"))
                self.pdb = pdb_summary_df(resolved_target.get("path"))
            else:
                self.target_atoms = pd.DataFrame()
                self.pdb = pd.DataFrame([
                    {"field":"target_mode","value":"Sequence descriptor only","note":resolved_target.get("message","Target resolver status")},
                    {"field":"target_sequence_length","value":len(str(resolved_target.get("sequence") or "")),"note":"No 3D coordinates are fabricated from target sequence."},
                    {"field":"3d_screening_requirement","value":"target PDB/mmCIF required","note":"Provide measured/predicted target coordinates before pose/contact screening."},
                ])
            self.residue_map = residue_map_df(active_peptide_seq)
            self.risk = structure_risk_df(self.props)
            self.readiness = docking_readiness_df(active_peptide_seq)
            self.compatibility = peptide_token_compatibility_df(active_peptide_seq)
            self.seqpair = sequence_sequence_interaction_df(self._active_target_sequence(), active_peptide_seq) if resolved_target.get("mode") == "Sequence" else pd.DataFrame([{"metric":"mode","value":"3D target input","note":"Sequence-only descriptors are not needed when target coordinates are supplied."}])
            self.pipeline = structure_pipeline_df(self.target_mode.get(), self.peptide_mode.get(), self._active_target_sequence(), active_peptide_seq, self._target_path(), self._peptide_pdb_path())
            self.poses = pd.DataFrame(columns=self.pose_tree["columns"])
            self.contacts = pd.DataFrame(columns=self.contact_tree["columns"])
            self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
            # Analyze is intentionally lightweight: sequence-derived 3D peptide
            # geometry is generated only when Run Screening is requested.
            self.peptide_model = pd.DataFrame(columns=["pep_pos","aa","token","token_class","x","y","z"])
            self.screening_evidence = screening_evidence_df(self.poses, self.contacts)
            if not hasattr(self, "imported_results"):
                self.imported_results = pd.DataFrame(columns=["source","metric","value","unit","interpretation","method_note"])
            self.md_summary = pd.DataFrame([{"metric":"molecular_dynamics","value":"external only","note":"Pepforge does not run molecular dynamics internally."}])
            self.md_frames = pd.DataFrame(columns=self.md_tree["columns"])
            for tr,df in [
                (self.prop_tree,self.props),(self.terminal_tree,self.terminal_status),(self.pdb_tree,self.pdb),
                (self.seqpair_tree,self.seqpair),(self.pipeline_tree,self.pipeline),(self.risk_tree,self.risk),
                (self.readiness_tree,self.readiness),(self.pose_tree,self.poses),(self.contact_tree,self.contacts),
                (self.import_tree,self._combined_result_report()),(self.external_style_tree,self._external_style_validation_df()),
                (self.md_result_tree,getattr(self,"md_result_import",pd.DataFrame())),
                (self.sim_tree,simulation_summary_df(self.poses,self.contacts,self.risk)),
                (self.md_tree,self._md_readable_frames(self.md_frames)),(self.interpret_tree,self._interpretation_df())
            ]:
                self._write_tree(tr,df)
            try:
                self.tabs.select(0)
                self.collapse_input_panel()
            except Exception:
                LOGGER.debug("Could not adjust analysis view", exc_info=True)
            self._set_progress(100, "Analysis complete")
            self.log.insert("end","Input analysis updated. No target/peptide 3D coordinates were fabricated during Analyze.\n")
            self.log.see("end")
        except Exception as exc:
            messagebox.showerror("Docking Workbench analysis error", str(exc))
            raise


    def _active_target_atoms_for_docking(self):
        """Return only coordinate-derived target atoms; sequence-only targets return empty."""
        resolved = self._resolved_target()
        atoms = resolved.get("atoms")
        if resolved.get("mode") == "PDB" and isinstance(atoms, pd.DataFrame) and not atoms.empty:
            return atoms
        return pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"])


    def run_full_workflow(self):
        """Analyze and start 3D/contact screening; MD remains external-only."""
        self._set_progress(0, "Starting workflow...")
        self.analyze()
        self._set_progress(20, "Starting screening...")
        self.run_docking()
        self.log.insert("end", "Workflow started: input analysis + geometry/contact screening. Molecular dynamics is external-only.\n")
        self.log.see("end")


    def _interpretation_df(self):
        poses=getattr(self,"poses",pd.DataFrame()); contacts=getattr(self,"contacts",pd.DataFrame())
        rows=[]
        if poses is None or poses.empty:
            rows.append({"item":"3D screening","status":"No pose result","interpretation":"Sequence-only targets provide descriptors only. Supply target coordinates for local 3D screening."})
        else:
            best=poses.iloc[0]
            rows.append({"item":"3D screening","status":"Geometry candidates available","interpretation":f"Top candidate rank={best.get('pose_rank','')}; centroid contacts={best.get('contact_count','')}; overlap warnings={best.get('centroid_overlap_warnings','')}. No ΔG/Kd is inferred."})
        rows.append({"item":"Interface","status":"Centroid contacts available" if isinstance(contacts,pd.DataFrame) and not contacts.empty else "No centroid contacts","interpretation":"Residue/token-centroid proximity is a geometric screening descriptor, not a bond or affinity measurement."})
        rows.append({"item":"Atom-level contacts","status":"Available when both atomic structures are supplied","interpretation":"Hydrogen-bond distance candidates and other atom-level proximity labels require actual atomic coordinates."})
        rows.append({"item":"Molecular dynamics","status":"External only","interpretation":"Run a validated external MD engine and import its results if dynamics are needed."})
        return pd.DataFrame(rows, columns=["item","status","interpretation"])


    def _screening_failure_log(self, stage: str, exc: BaseException) -> Path:
        """Persist a visible screening failure report in the docking sandbox."""
        try:
            out = self._effective_outdir() if hasattr(self, "_effective_outdir") else configured_output(ROOT / "outputs" / "docking_workbench", "docking")
        except Exception:
            out = configured_output(ROOT / "outputs" / "docking_workbench", "docking")
        log_dir = Path(out) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"screening_failure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path.write_text(
            "Pepforge Docking Workbench screening failure\n"
            "============================================\n"
            f"Stage: {stage}\n"
            f"Error: {type(exc).__name__}: {exc}\n\n"
            + traceback.format_exc(),
            encoding="utf-8",
        )
        return path

    def _set_screening_busy(self, busy: bool) -> None:
        try:
            self.run_screening_btn.configure(state="disabled" if busy else "normal")
        except Exception as exc:
            LOGGER.debug("Could not update Run Screening state: %s", exc)

    def run_docking(self):
        """Start screening with immediate UI feedback and guarded validation.

        The previous callback could fail before validation/progress feedback and,
        in a windowed EXE, look like a dead button.  This entry point always
        updates the progress bar first, then runs the actual workflow on the next
        Tk event-loop turn so the user sees that the click was received.
        """
        if getattr(self, "_screening_in_progress", False):
            return
        self._screening_in_progress = True
        self._set_screening_busy(True)
        self._set_progress(2, "Screening requested...")
        try:
            self.log.insert("end", "Run Screening requested.\n")
            self.log.see("end")
        except Exception as exc:
            LOGGER.debug("Could not write screening start log: %s", exc)
        self.after(25, self._run_docking_guarded)

    def _run_docking_guarded(self):
        stage = "input mode normalization"
        try:
            self._set_progress(5, "Resolving inputs...")
            self._normalize_input_modes()

            stage = "input validation"
            self._set_progress(10, "Validating inputs...")
            if not self._validate_for_run():
                self._set_progress(0, "Input validation failed")
                return False

            stage = "descriptor analysis"
            self.peptide_source_pdb = ""
            self.peptide_structure_paths = {}
            self._set_progress(18, "Analyzing chemistry and input modes...")
            resolved = self._resolved_target()
            active_target_seq = self._active_target_sequence()
            active_peptide_seq = self._peptide_metadata_sequence()
            self.props = estimate_properties(active_peptide_seq)
            self.terminal_status = terminal_status_df(active_peptide_seq)
            self.compatibility = peptide_token_compatibility_df(active_peptide_seq)
            self.risk = structure_risk_df(self.props)
            self.readiness = docking_readiness_df(active_peptide_seq)
            self.residue_map = residue_map_df(active_peptide_seq)
            self.pipeline = structure_pipeline_df(
                self.target_mode.get(), self.peptide_mode.get(), active_target_seq,
                active_peptide_seq, self._target_path(), self._peptide_pdb_path()
            )

            # Sequence-only target: descriptors only. No invented protein geometry.
            if resolved.get("mode") != "PDB":
                stage = "sequence-only descriptor analysis"
                self._set_progress(45, "Sequence-only mode: no 3D target fabricated")
                self.target_atoms = pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"])
                self.peptide_model = pd.DataFrame(columns=["pep_pos","aa","token","token_class","x","y","z"])
                self.poses = pd.DataFrame(columns=self.pose_tree["columns"])
                self.contacts = pd.DataFrame(columns=self.contact_tree["columns"])
                self.all_contacts = self.contacts.copy()
                self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
                self.seqpair = sequence_sequence_interaction_df(active_target_seq, active_peptide_seq)
                self.screening_evidence = screening_evidence_df(self.poses, self.contacts)
                self.pdb = pd.DataFrame([
                    {"field":"target_mode","value":"Sequence descriptor only","note":"No 3D target coordinates were generated."},
                    {"field":"target_sequence_length","value":len(active_target_seq),"note":"Canonical target residues parsed."},
                    {"field":"3d_screening_requirement","value":"target PDB/mmCIF required","note":"Load experimentally determined or externally predicted target coordinates before pose/contact screening."},
                ])
                completion_text = "Sequence descriptor analysis complete; target coordinates required for 3D screening"
            else:
                stage = "target coordinate preparation"
                self._set_progress(28, "Loading target coordinates...")
                self.target_atoms = self._active_target_atoms_for_docking()
                if self.target_atoms is None or self.target_atoms.empty:
                    raise ValueError("Target PDB/mmCIF contained no valid coordinate atoms. Invalid coordinate rows are not replaced with (0,0,0).")
                self.pdb = pdb_summary_df(resolved.get("path") or self._target_path())
                self.seqpair = pd.DataFrame([{"metric":"mode","value":"coordinate_target","note":"3D screening uses supplied target coordinates."}])

                stage = "peptide coordinate preparation"
                self._set_progress(40, "Preparing peptide coordinates...")
                complex_mode = (
                    self.peptide_mode.get() == "PDB"
                    and not (self._peptide_pdb_path() and Path(self._peptide_pdb_path()).exists())
                    and resolved.get("path")
                    and structure_has_multiple_chains(resolved.get("path"))
                )
                if complex_mode:
                    self.poses, self.contacts, self.atom_contacts, self.peptide_model = analyze_complex_structure_contacts(resolved.get("path"))
                else:
                    if self.peptide_mode.get() == "PDB":
                        pp = Path(self._peptide_pdb_path())
                        if not pp.exists():
                            raise ValueError("Peptide PDB is missing.")
                        pep_points = pdb_to_peptide_points(pp)
                        if pep_points.empty:
                            raise ValueError("No peptide coordinate points could be recovered from the peptide PDB/Structure Builder metadata.")
                        self.peptide_model = pep_points
                        self.peptide_source_pdb = str(pp)
                        self.peptide_structure_paths = {"pdb": str(pp)}
                    else:
                        cache_root = self._default_outdir() / "_screening_cache"
                        cache_root.mkdir(parents=True, exist_ok=True)
                        cache_dir = Path(tempfile.mkdtemp(prefix="peptide_", dir=str(cache_root)))
                        self.peptide_model, self.peptide_structure_paths = build_peptide_structure_bundle(
                            active_peptide_seq, cache_dir, name="screening_peptide"
                        )
                        self.peptide_source_pdb = str(self.peptide_structure_paths["pdb"])
                        pep_points = self.peptide_model

                    stage = "geometry/contact screening"
                    self._set_progress(55, "Screening rigid-body geometry/contact candidates...")
                    if self.peptide_mode.get() == "PDB":
                        direct_poses, direct_contacts = analyze_pdb_pdb_contacts(self._target_path(), self._peptide_pdb_path())
                        if not direct_poses.empty and int(float(direct_poses.iloc[0].get("contact_count",0) or 0)) > 0:
                            self.poses, self.contacts = direct_poses, direct_contacts
                            self.atom_contacts = analyze_atom_level_contacts(self._target_path(), self._peptide_pdb_path())
                        else:
                            self.poses, self.contacts, self.peptide_model = run_pose_search(self.target_atoms, pep_points, active_peptide_seq)
                            self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
                    else:
                        self.poses, self.contacts, self.peptide_model = run_pose_search(self.target_atoms, pep_points, active_peptide_seq)
                        self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())

                    # When local pose search was used, apply the exact recorded rigid-body
                    # transform to the actual peptide atomic coordinates and analyze those.
                    if (self.atom_contacts is None or self.atom_contacts.empty) and isinstance(self.poses,pd.DataFrame) and not self.poses.empty and getattr(self,"peptide_source_pdb",""):
                        source_atoms=parse_pdb_atoms(self.peptide_source_pdb)
                        if not source_atoms.empty:
                            self.peptide_posed_atoms=apply_pose_transform_to_atoms(source_atoms,self.poses.iloc[0])
                            self.atom_contacts=analyze_atom_level_contact_frames(self.target_atoms,self.peptide_posed_atoms)

                stage = "contact summary"
                self._set_progress(75, "Summarizing coordinate contacts...")
                self.all_contacts = getattr(self, "contacts", pd.DataFrame()).copy()
                self.contacts = top_contact_report(self.all_contacts, self.poses, top_n=50)
                self.screening_evidence = screening_evidence_df(self.poses, self.contacts)
                completion_text = f"3D geometry/contact screening complete: {len(self.poses)} pose rows, {len(self.contacts)} displayed contact rows"

            stage = "results rendering"
            self._set_progress(90, "Updating results...")
            for tree, df in [
                (self.prop_tree,self.props),(self.terminal_tree,self.terminal_status),(self.pdb_tree,self.pdb),
                (self.seqpair_tree,self.seqpair),(self.pipeline_tree,self.pipeline),(self.risk_tree,self.risk),
                (self.readiness_tree,self.readiness),(self.pose_tree,self.poses),(self.contact_tree,self.contacts),
                (self.import_tree,self._combined_result_report()),(self.external_style_tree,self._external_style_validation_df()),
                (self.sim_tree,simulation_summary_df(self.poses,self.contacts,self.risk)),
                (self.md_tree,self._md_readable_frames(getattr(self,"md_frames",pd.DataFrame()))),
                (self.interpret_tree,self._interpretation_df()),
            ]:
                self._write_tree(tree, df)
            try:
                for tab_id in self.tabs.tabs():
                    if self.tabs.tab(tab_id, "text") == "Results":
                        self.tabs.select(tab_id)
                        break
            except Exception:
                LOGGER.debug("Could not switch to Results tab", exc_info=True)
            self._set_progress(100, completion_text)
            self.log.insert("end", completion_text + ".\n")
            self.log.see("end")
            self._last_screening_signature = self._screening_input_signature()
            return True
        except Exception as exc:
            try:
                log_path = self._screening_failure_log(stage, exc)
            except Exception:
                log_path = None
            self._set_progress(0, f"Screening failed: {stage}")
            LOGGER.exception("Docking screening failed at stage %s", stage)
            detail = f"Screening failed during: {stage}\n\n{type(exc).__name__}: {exc}"
            if log_path:
                detail += f"\n\nDiagnostic log:\n{log_path}"
            messagebox.showerror("Docking screening failed", detail)
            return False
        finally:
            self._screening_in_progress = False
            self._set_screening_busy(False)


    def _md_readable_summary(self, summary: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame([{"metric":"molecular_dynamics","value":"external only","unit":"-","interpretation":"Pepforge does not generate internal MD trajectories or stability metrics."}])


    def _md_readable_frames(self, frames: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(columns=["frame","time_ps","rmsd_A","contacts","clashes","min_distance_A","interpretation"])


    def run_md_lite(self):
        """Compatibility action directing the user to external molecular dynamics."""
        self.md_summary = pd.DataFrame([{
            "metric":"molecular_dynamics", "value":"not run internally",
            "note":"Pepforge exports starting structures/templates only. Run GROMACS/OpenMM/NAMD externally and import the resulting RMSD/RMSF/energy/contact data."
        }])
        self.md_frames = pd.DataFrame(columns=self.md_tree["columns"])
        self._write_tree(self.sim_tree, self._md_readable_summary(self.md_summary))
        self._write_tree(self.md_tree, self._md_readable_frames(self.md_frames))
        self._set_progress(100, "External MD preparation only")
        try:
            self.log.insert("end", "Pepforge does not run internal molecular dynamics. Use Export for external MD preparation/import.\n")
            self.log.see("end")
        except Exception:
            LOGGER.debug("Could not update MD guidance log", exc_info=True)
        return self.md_summary


    def export(self):
        """Export results for the current inputs without silently reusing stale screening data.

        If the displayed results were generated from the unchanged current inputs, export
        writes them directly. If the inputs changed, one synchronous guarded screening pass
        is performed first. This avoids the previous duplicate Structure Builder/screening
        run on every export while preserving correctness.
        """
        self._normalize_input_modes()
        if not self._screening_results_are_current():
            self._screening_in_progress = True
            self._set_screening_busy(True)
            self._set_progress(2, "Preparing export screening...")
            if not self._run_docking_guarded():
                return None
        else:
            self._set_progress(96, "Writing current screening results...")

        active_target_seq=self._active_target_sequence()
        active_peptide_seq=self._peptide_metadata_sequence()
        out_base=self._effective_outdir(); out_base.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out=out_base/("docking_"+stamp); out.mkdir(parents=True,exist_ok=True)

        self.screening_evidence=screening_evidence_df(getattr(self,"poses",pd.DataFrame()), getattr(self,"contacts",pd.DataFrame()))
        external_results=getattr(self,"imported_results",pd.DataFrame())
        md_import=getattr(self,"md_result_import",pd.DataFrame())
        md_status=pd.DataFrame([{
            "metric":"molecular_dynamics","value":"not run internally",
            "note":"Pepforge exports structures/templates and imports results from validated external MD engines."
        }])
        tables={
            "peptide_properties":getattr(self,"props",pd.DataFrame()),
            "target_structure_summary":getattr(self,"pdb",pd.DataFrame()),
            "sequence_pair_descriptors":getattr(self,"seqpair",pd.DataFrame()),
            "workflow":getattr(self,"pipeline",pd.DataFrame()),
            "peptide_residue_map":getattr(self,"residue_map",pd.DataFrame()),
            "peptide_risk_summary":getattr(self,"risk",pd.DataFrame()),
            "docking_readiness":getattr(self,"readiness",pd.DataFrame()),
            "token_compatibility":getattr(self,"compatibility",peptide_token_compatibility_df(active_peptide_seq)),
            "terminal_modifier_policy":terminal_modifier_policy_df(active_peptide_seq),
            "all_atom_parameter_requirements":all_atom_parameter_requirements_df(active_peptide_seq),
            "docking_pose_candidates":getattr(self,"poses",pd.DataFrame()),
            "docking_residue_contact_report":getattr(self,"contacts",pd.DataFrame()),
            "docking_residue_contact_report_full":getattr(self,"all_contacts",getattr(self,"contacts",pd.DataFrame())),
            "docking_atom_contact_report":getattr(self,"atom_contacts",pd.DataFrame()),
            "screening_evidence_summary":self.screening_evidence,
            "external_result_import_summary":external_results,
            "external_md_result_import_summary":md_import,
            "external_validation_status":self._external_style_validation_df(),
            "screening_summary":simulation_summary_df(getattr(self,"poses",pd.DataFrame()),getattr(self,"contacts",pd.DataFrame()),getattr(self,"risk",pd.DataFrame())),
            "molecular_dynamics_status":md_status,
            "amphipathic_windows":amphipathic_window_df(self.seq.get()),
            "rcsb_pdb_search_results":getattr(self,"rcsb_results",pd.DataFrame()),
            "target_preparation_report":getattr(self,"target_prep_report",pd.DataFrame()),
            "complex_builder_report":getattr(self,"complex_builder_report",pd.DataFrame()),
        }
        for name,df in tables.items():
            if not isinstance(df,pd.DataFrame): df=pd.DataFrame(df)
            df.to_csv(out/f"{name}.csv",index=False,encoding="utf-8-sig")
        (out/"screening_evidence_report.md").write_text(screening_report_markdown(self.screening_evidence),encoding="utf-8")

        if active_peptide_seq:
            fasta_name=re.sub(r"[^A-Za-z0-9_\-]","_",active_peptide_seq)[:50] or "peptide"
            (out/"peptide.fasta").write_text(f">{fasta_name}\n{active_peptide_seq}\n",encoding="utf-8")
        if active_target_seq:
            (out/"target_sequence.fasta").write_text(f">target\n{active_target_seq}\n",encoding="utf-8")

        target_path=Path(self._target_path()) if self._target_path() else None
        if target_path and target_path.exists():
            shutil.copy2(target_path,out/("target_input"+target_path.suffix.lower()))

        structure_dir=out/"peptide_structure_builder"
        structure_dir.mkdir(exist_ok=True)
        source_pdb=Path(getattr(self,"peptide_source_pdb","")) if getattr(self,"peptide_source_pdb","") else None
        source_paths=getattr(self,"peptide_structure_paths",{}) or {}
        copied_source_pdb=None
        if source_paths:
            for key,value in source_paths.items():
                src=Path(value)
                if src.exists() and src.is_file():
                    dst=structure_dir/src.name
                    shutil.copy2(src,dst)
                    if key=="pdb": copied_source_pdb=dst
        elif source_pdb and source_pdb.exists():
            copied_source_pdb=structure_dir/("peptide_input"+source_pdb.suffix.lower())
            shutil.copy2(source_pdb,copied_source_pdb)

        if isinstance(getattr(self,"peptide_model",None),pd.DataFrame) and not self.peptide_model.empty:
            self.peptide_model.to_csv(out/"peptide_screening_token_centroids.csv",index=False,encoding="utf-8-sig")

        posed_peptide_path=None; atomic_complex_path=None
        poses=getattr(self,"poses",pd.DataFrame())
        if isinstance(poses,pd.DataFrame) and not poses.empty and source_pdb and source_pdb.exists():
            source_atoms=parse_pdb_atoms(source_pdb)
            if not source_atoms.empty:
                best=poses.iloc[0]
                posed_atoms=apply_pose_transform_to_atoms(source_atoms,best)
                posed_peptide_path=out/"peptide_screened_pose_atomic.pdb"
                posed_peptide_path.write_text(atomic_structure_pdb(posed_atoms,"Pepforge screened peptide pose; rigid-body transform only",forced_chain="P"),encoding="utf-8")
                target_atoms=getattr(self,"target_atoms",pd.DataFrame())
                if isinstance(target_atoms,pd.DataFrame) and not target_atoms.empty:
                    atomic_complex_path=out/"target_peptide_screened_pose_atomic.pdb"
                    atomic_complex_path.write_text(atomic_complex_pdb(target_atoms,posed_atoms,getattr(self,"contacts",pd.DataFrame())),encoding="utf-8")
                transform={k:(best.get(k).item() if hasattr(best.get(k),"item") else best.get(k)) for k in [
                    "pose_rank","pose_id","orientation","rotation_z_deg","translation_x_A","translation_y_A","translation_z_A",
                    "center_x_A","center_y_A","center_z_A","contact_count","centroid_overlap_warnings"
                ] if k in best.index}
                transform["scope"]="Rigid-body transform applied to the actual peptide atomic coordinates used to derive screening centroids. No docking energy is implied."
                (out/"best_pose_rigid_transform.json").write_text(json.dumps(transform,indent=2,ensure_ascii=False),encoding="utf-8")

        prep_fasta,target_fasta,prep_json,prep_notes=structure_preparation_files(active_target_seq,active_peptide_seq,self._peptide_pdb_path())
        (out/"external_structure_preparation_complex.fasta").write_text(prep_fasta,encoding="utf-8")
        (out/"external_target_structure_input.fasta").write_text(target_fasta,encoding="utf-8")
        (out/"external_complex_structure_input.json").write_text(prep_json,encoding="utf-8")
        (out/"EXTERNAL_STRUCTURE_PREPARATION_NOTES.txt").write_text(prep_notes,encoding="utf-8")

        validation_dir=out/"external_validation_package"
        validation_dir.mkdir(exist_ok=True)
        all_atom_parameter_requirements_df(active_peptide_seq).to_csv(validation_dir/"token_parameter_requirements.csv",index=False,encoding="utf-8-sig")
        for rel_name,content in all_atom_validation_template_files().items():
            fp=validation_dir/rel_name; fp.parent.mkdir(parents=True,exist_ok=True); fp.write_text(content,encoding="utf-8")
        if target_path and target_path.exists():
            shutil.copy2(target_path,validation_dir/("target_input"+target_path.suffix.lower()))
        if posed_peptide_path and posed_peptide_path.exists():
            shutil.copy2(posed_peptide_path,validation_dir/posed_peptide_path.name)
        elif copied_source_pdb and copied_source_pdb.exists():
            shutil.copy2(copied_source_pdb,validation_dir/"peptide_starting_structure.pdb")
        if atomic_complex_path and atomic_complex_path.exists():
            shutil.copy2(atomic_complex_path,validation_dir/atomic_complex_path.name)

        notes=(
            "Pepforge Docking Workbench export\n\n"
            "Pepforge performs local rigid-body geometry/contact screening only when target coordinates are supplied.\n"
            "Peptide sequence inputs are converted to a chemistry-aware Structure Builder starting conformer; unsupported chemistry is not replaced by canonical residues.\n"
            "Pose ordering uses explicit geometry descriptors and does not calculate docking energy, ΔG, Kd, or molecular-dynamics stability.\n"
            "For quantitative docking/affinity/MD claims, use an appropriate validated external method and import/report those results separately.\n"
        )
        (out/"docking_notes.txt").write_text(notes,encoding="utf-8")
        with pd.ExcelWriter(out/"docking_workbench_report.xlsx",engine="openpyxl") as writer:
            for name,df in tables.items():
                if not isinstance(df,pd.DataFrame): df=pd.DataFrame(df)
                df.to_excel(writer,index=False,sheet_name=name[:31].upper())
        (out/"OUTPUT_MANIFEST.txt").write_text(
            "Pepforge Docking Workbench output folder\nCreated: "+datetime.now().isoformat(timespec="seconds")+
            "\nInternal scope: geometry/contact screening only.\nExternal quantitative results remain separately imported evidence.\n",
            encoding="utf-8"
        )
        (out/"CITATION_NOTICE.txt").write_text(
            "Pepforge Citation Notice\n\nRecommended citation:\nWoo, S. Pepforge: An Integrated Peptide Research Workbench. GitHub repository, Version 3.0.0.\n\n"
            "Pepforge internal Docking Workbench output is geometry/contact screening evidence, not an experimental or thermodynamic affinity result.\n",
            encoding="utf-8"
        )
        self.last_outdir=out
        messagebox.showinfo("Export complete",f"Exported to:\n{out}")
        return out


    def load_output_folder(self):
        folder=filedialog.askdirectory(title="Select a Pepforge Docking output folder")
        if not folder:
            return
        try:
            base=Path(folder)
            mapping=[
                ("peptide_properties.csv", self.prop_tree, "props"),
                ("target_structure_summary.csv", self.pdb_tree, "pdb"),
                ("sequence_pair_descriptors.csv", self.seqpair_tree, "seqpair"),
                ("workflow.csv", self.pipeline_tree, "pipeline"),
                ("docking_pose_candidates.csv", self.pose_tree, "poses"),
                ("docking_residue_contact_report.csv", self.contact_tree, "contacts"),
                ("peptide_risk_summary.csv", self.risk_tree, "risk"),
                ("docking_readiness.csv", self.readiness_tree, "readiness"),
                ("token_compatibility.csv", self.compat_tree, "compatibility"),
                ("screening_evidence_summary.csv", self.import_tree, "screening_evidence"),
                ("external_md_result_import_summary.csv", self.md_result_tree, "md_result_import"),
            ]
            # Backward-compatible read-only support for older output folder names.
            legacy=[
                ("sequence_pair_heuristic.csv", self.seqpair_tree, "seqpair"),
                ("affinity_scoring_summary.csv", self.import_tree, "screening_evidence"),
                ("md_result_import_summary.csv", self.md_result_tree, "md_result_import"),
            ]
            loaded=0; seen=set()
            for fname,tree,attr in mapping+legacy:
                if attr in seen:
                    continue
                f=base/fname
                if f.exists():
                    df=pd.read_csv(f)
                    setattr(self,attr,df)
                    self._write_tree(tree,df)
                    loaded+=1; seen.add(attr)
            ext=base/"external_result_import_summary.csv"
            self.imported_results=pd.read_csv(ext) if ext.exists() else pd.DataFrame(columns=["source","metric","value","unit","interpretation","method_note"])
            if not hasattr(self,"screening_evidence"):
                self.screening_evidence=screening_evidence_df(getattr(self,"poses",pd.DataFrame()),getattr(self,"contacts",pd.DataFrame()))
                self._write_tree(self.import_tree,self._combined_result_report())
            self.last_outdir=base
            self.outdir.set(str(base.parent))
            self.log.insert("end",f"Loaded output folder: {base} ({loaded} tables).\n")
            self.log.see("end")
        except Exception as exc:
            messagebox.showerror("Load output error",str(exc))

    def open_output(self):
        p=self.last_outdir or self._effective_outdir()
        if p.exists():
            if os.name=="nt": os.startfile(str(p))
            elif sys.platform=="darwin": os.system(f'open "{p}"')
            else: os.system(f'xdg-open "{p}"')
        else: messagebox.showinfo("Not found",str(p))

def main():
    app=DockingWorkbenchGUI(); app.mainloop()

StructureAssistGUI = DockingWorkbenchGUI

if __name__ == "__main__":
    main()
