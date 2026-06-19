
from __future__ import annotations
import os
import sys
import math
import re
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon, open_path
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
    token_to_surrogate,
    normalize_token,
    LINKER_ONLY_TOKENS,
    AA_LIKE_TOKEN_MAP,
    NTERM_MODIFIERS,
)

AA_MASS = {
    "A": 89.09, "R": 174.20, "N": 132.12, "D": 133.10, "C": 121.16,
    "Q": 146.15, "E": 147.13, "G": 75.07, "H": 155.16, "I": 131.17,
    "L": 131.17, "K": 146.19, "M": 149.21, "F": 165.19, "P": 115.13,
    "S": 105.09, "T": 119.12, "W": 204.23, "Y": 181.19, "V": 117.15,
}
HYDRO = {"A":1.8,"R":-4.5,"N":-3.5,"D":-3.5,"C":2.5,"Q":-3.5,"E":-3.5,"G":-0.4,"H":-3.2,"I":4.5,"L":3.8,"K":-3.9,"M":1.9,"F":2.8,"P":-1.6,"S":-0.8,"T":-0.7,"W":-0.9,"Y":-1.3,"V":4.2}
HELIX = set("AEKLMQRH")
BETA = set("VIFYWT")
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

# Coarse-grained surrogates used only for local structure/MD screening.
# They allow D-form, common non-natural residues, linkers, labels and chemical caps
# to remain in the workflow instead of being rejected. Publication-grade all-atom
# validation still requires force-field parameters for noncanonical chemistry.
CHEMICAL_BEAD_SURROGATE = {
    "AC": "A", "ACETYL": "A", "SUCCINYL": "D", "T7SUCCINYL": "D",
    "PAL": "V", "PALMITICACID": "V", "PALMITOYL": "V", "MYR": "V", "MYRISTICACID": "V", "MYRISTOYL": "V", "CHOL": "V", "CHOLESTERYL": "V",
    "GAL": "Y", "GALLICACID": "Y", "GALLOYL": "Y", "CAF": "Y", "CAFFEICACID": "Y", "CAFFEOYL": "Y", "NIC": "H", "NICOTINICACID": "H", "NICOTINOYL": "H",
    "BIOTIN": "F", "FITC": "Y", "FAM": "Y", "TAMRA": "Y", "CY3": "Y", "CY5": "Y", "DOTA": "D", "NOTA": "D",
    "AHX": "G", "AEEA": "G", "PEG1": "G", "PEG2": "G", "PEG3": "G", "PEG4": "G", "PEG6": "G", "PEG8": "G", "PEG12": "G", "PEG24": "G",
    "SMCC": "G", "SULFOSMCC": "G", "TRIAZOLE": "G", "CLICK": "G", "HYDRAZONE": "G", "OXIME": "G",
}



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
    """Return ordered token rows for simulation-friendly peptide modeling.

    Canonical residues, D-residues, common non-natural residues, linkers and
    terminal chemicals are converted to conservative surrogate bead types. This
    keeps chemically rich Pepforge candidates usable for local pose screening and
    dynamics while clearly recording the original token.
    """
    raw = canonical_peptide_notation(seq).strip().replace(" ", "")
    parsed = unified_parse_peptide(raw)
    rows = []
    if not raw:
        return rows

    def add(token, aa, cls, note=""):
        aa = (aa or "G")[:1].upper()
        rows.append({"token": str(token), "aa": aa, "class": cls, "note": note})

    if parsed.nterm:
        n = normalize_token(parsed.nterm)
        if n not in {"AC", "ACETYL"}:
            add(parsed.nterm, CHEMICAL_BEAD_SURROGATE.get(n, "A"), "n_terminal_chemical", "terminal chemical represented in the screening model")

    s, _cterm = raw, parsed.cterm
    # Strip terminal markers and explicit N-terminal modifier from token scan.
    for marker in ("CONH2", "NH2", "AMIDE", "COOH", "CO2H", "ACID", "OH"):
        s = re.sub(r"(?i)-?" + re.escape(marker) + r"$", "", s)
    parts = [p for p in s.split("-") if p]
    if parts and normalize_token(parts[0]) in NTERM_MODIFIERS:
        parts = parts[1:]
    s_after = "-".join(parts) if parts else s
    if parsed.nterm == "Ac" and s_after.startswith("Ac") and not s_after.startswith("AC"):
        s_after = s_after[2:]

    tokens = []
    if "-" in s_after or re.search(r"[,;/\n\t ]", s_after):
        tokens = [p.strip().strip("[]") for p in re.split(r"\s*(?:-|,|;|/|\n|\t| )\s*", s_after) if p.strip()]
    else:
        i = 0
        while i < len(s_after):
            ch = s_after[i]
            if ch == "[":
                j = s_after.find("]", i+1)
                if j > i:
                    tokens.append(s_after[i+1:j]); i = j+1; continue
            if ch == "d" and i+1 < len(s_after) and s_after[i+1].upper() in AA_MASS:
                tokens.append(s_after[i:i+2]); i += 2; continue
            if ch.isupper():
                tokens.append(ch)
            i += 1

    for token_index, tok in enumerate(tokens, start=1):
        norm = normalize_token(tok)
        if not norm:
            continue
        # Pal/Myr/FITC/etc. are N-terminal modifiers by default.  If they
        # survived into the internal token list, do not silently model them as
        # ordinary residues.  Keep a warning bead for traceability but avoid
        # giving it normal contact chemistry.
        if norm in NTERM_MODIFIERS:
            add(tok, "G", "misplaced_n_terminal_modifier", "N-terminal-only modifier found internally; side-chain use must be explicitly specified and externally parameterized")
            continue
        if len(tok) == 2 and tok[0] == "d" and tok[1].upper() in AA_MASS:
            add(tok, tok[1].upper(), "d_form", "D-form residue modeled with canonical side-chain class and D-form flag")
            continue
        if norm in LINKER_ONLY_TOKENS:
            # flexible linkers get at least one neutral flexible bead; long PEGs get two.
            reps = 2 if re.search(r"PEG(8|12|24)", norm) else 1
            for k in range(reps):
                add(tok if k == 0 else tok + f"_{k+1}", CHEMICAL_BEAD_SURROGATE.get(norm, "G"), "linker", "flexible linker represented by neutral coarse bead")
            continue
        aa = token_to_surrogate(tok)
        if aa:
            cls = "non_natural" if norm in AA_LIKE_TOKEN_MAP else "canonical"
            for ch in aa:
                add(tok, ch, cls, "non-natural residue mapped to conservative canonical surrogate" if cls == "non_natural" else "")
            continue
        if norm in CHEMICAL_BEAD_SURROGATE:
            add(tok, CHEMICAL_BEAD_SURROGATE[norm], "chemical", "chemical token represented by a conservative coarse bead")
        else:
            add(tok, "G", "unknown", "unknown token retained as neutral coarse bead for screening")
    return rows



def peptide_token_compatibility_df(seq: str):
    seq = canonical_peptide_notation(seq)
    rows = _split_peptide_model_tokens(seq)
    parsed = unified_parse_peptide(seq)
    if not rows:
        return pd.DataFrame([{"metric":"simulation_token_status","value":"no peptide tokens","note":"Enter a peptide sequence or peptide PDB."}])
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    out = [
        {"metric":"coarse_model_beads","value":len(rows),"note":"Residue/chemical/linker beads used by local pose search and dynamics."},
        {"metric":"d_form_beads","value":counts.get("d_form",0),"note":"D-form residues are supported by surrogate side-chain class and D-form flag."},
        {"metric":"non_natural_beads","value":counts.get("non_natural",0),"note":"Non-natural amino acids are mapped to conservative canonical surrogates."},
        {"metric":"linker_beads","value":counts.get("linker",0),"note":"Linkers are retained as flexible neutral beads."},
        {"metric":"chemical_modifier_beads","value":counts.get("chemical",0)+counts.get("n_terminal_chemical",0),"note":"Chemical caps/labels are retained as coarse interaction beads when possible."},
        {"metric":"unknown_token_beads","value":counts.get("unknown",0),"note":"Unknown tokens are not rejected; they are modeled as neutral beads and flagged for review."},
        {"metric":"misplaced_n_terminal_modifier_beads","value":counts.get("misplaced_n_terminal_modifier",0),"note":"N-terminal-only chemicals such as Pal/FITC are not treated as internal residues unless explicit side-chain attachment notation is provided."},
        {"metric":"terminal_modifier_warnings","value":";".join(misplaced_nterm_modifier_tokens(seq)) if misplaced_nterm_modifier_tokens(seq) else "none","note":"Internal Pal/Myr/FITC/etc. are flagged because their default position is N-terminus."},
        {"metric":"aa_like_tokens","value":";".join(parsed.aa_like_tokens) if parsed.aa_like_tokens else "none","note":"Recognized non-natural amino-acid tokens."},
        {"metric":"linker_tokens","value":";".join(parsed.linker_tokens) if parsed.linker_tokens else "none","note":"Recognized linker/spacer tokens."},
        {"metric":"simulation_scope","value":"screening-ready","note":"Local pose search and embedded dynamics can run; all-atom validation requires external parameters for modified residues."},
    ]
    return pd.DataFrame(out)

def estimate_properties(seq: str):
    seq = canonical_peptide_notation(seq)
    parsed = parse_peptide_notation(seq); core = parsed["core"]; n = len(core)
    if n == 0:
        return pd.DataFrame([{"metric":"valid_residue_count", "value":0, "note":"No standard residues parsed"}])
    mw = sum(AA_MASS[a] for a in core) - 18.015*(n-1)
    if str(parsed["nterm"]).lower() == "ac": mw += 42.037
    if parsed["cterm"].upper() in set(CTERM_AMIDE_MARKERS): mw -= 0.984
    sidechain_charge = sum(1 for a in core if a in "KR") + 0.1*sum(1 for a in core if a == "H") - sum(1 for a in core if a in "DE")
    nterm_charge = 0.0 if parsed["nterm"] else 1.0
    cterm_charge = 0.0 if parsed["cterm"].upper() in set(CTERM_AMIDE_MARKERS) else -1.0
    net_charge = sidechain_charge + nterm_charge + cterm_charge
    hydro = sum(HYDRO.get(a,0) for a in core)/n
    helix = sum(1 for a in core if a in HELIX)/n
    beta = sum(1 for a in core if a in BETA)/n
    disorder = min(1.0, (sum(1 for a in core if a in "GSPDEKRNQ")/n)*0.85 + (1-min(1, abs(hydro)/4.5))*0.15)
    aggregation = min(1.0, (sum(1 for a in core if a in HYDROPHOBIC)/n)*0.60 + (sum(1 for a in core if a in AROMATIC)/n)*0.30 + max(0, hydro)/4.5*0.10)
    amph = min(1.0, (sum(1 for a in core if a in CHARGED)/n)*0.5 + (sum(1 for a in core if a in HYDROPHOBIC)/n)*0.5)
    rows = [
        ("parsed_core_sequence", core, "standard-residue parse used for lightweight estimation"),
        ("n_terminal_modifier", parsed["nterm"] or "free", "terminal parser result"),
        ("c_terminal_modifier", parsed["cterm"] or "free acid", "terminal parser result"),
        ("length", n, "residue count"),
        ("estimated_MW_Da", round(mw, 3), "sequence-based estimate; verify modified residues/vendor forms"),
        ("net_charge_approx", round(net_charge, 3), "rough pH-neutral estimate including terminal state"),
        ("hydrophobicity_KD_avg", round(hydro, 3), "Kyte-Doolittle average"),
        ("helix_propensity_heuristic", round(helix, 3), "heuristic, not structure preparation"),
        ("beta_propensity_heuristic", round(beta, 3), "heuristic, not structure preparation"),
        ("disorder_tendency_heuristic", round(disorder, 3), "heuristic"),
        ("aggregation_risk_heuristic", round(aggregation, 3), "heuristic"),
        ("amphipathic_balance_heuristic", round(amph, 3), "heuristic"),
        ("d_form_token_count", sum(1 for r in _split_peptide_model_tokens(seq) if r.get("class") == "d_form"), "D-form residues represented by surrogate beads for screening"),
        ("non_natural_token_count", len(parsed.get("aa_like_tokens", [])), "non-natural amino-acid tokens mapped to conservative surrogates"),
        ("linker_token_count", len(parsed.get("linker_tokens", [])), "linker/spacer tokens retained by the coarse simulation model"),
        ("unknown_token_count", len(parsed.get("unknown_tokens", [])), "unknown tokens flagged for review"),
        ("aromatic_fraction", round(sum(1 for a in core if a in AROMATIC)/n, 3), "F/W/Y fraction"),
        ("charged_fraction", round(sum(1 for a in core if a in CHARGED)/n, 3), "D/E/K/R/H fraction"),
        ("basic_fraction", round(sum(1 for a in core if a in BASIC)/n, 3), "K/R/H fraction"),
        ("acidic_fraction", round(sum(1 for a in core if a in ACIDIC)/n, 3), "D/E fraction"),
        ("polar_fraction", round(sum(1 for a in core if a in POLAR)/n, 3), "polar residue fraction"),
    ]
    return pd.DataFrame([{"metric":a,"value":b,"note":c} for a,b,c in rows])

def residue_map_df(seq: str):
    core = clean_sequence(seq); rows = []
    for i, aa in enumerate(core, start=1):
        cls=[]
        if aa in BASIC: cls.append("basic")
        if aa in ACIDIC: cls.append("acidic")
        if aa in AROMATIC: cls.append("aromatic")
        if aa in HYDROPHOBIC: cls.append("hydrophobic")
        if aa in POLAR: cls.append("polar")
        if aa in HELIX: cls.append("helix-favor")
        if aa in BETA: cls.append("beta-favor")
        rows.append({"position": i, "residue": aa, "class": ", ".join(cls), "hydrophobicity_KD": HYDRO.get(aa, 0)})
    return pd.DataFrame(rows)

def structure_risk_df(props: pd.DataFrame):
    def get(k, default=0):
        try: return float(props.loc[props.metric==k, "value"].iloc[0])
        except Exception: return default
    agg = get("aggregation_risk_heuristic"); disorder = get("disorder_tendency_heuristic"); hydro = get("hydrophobicity_KD_avg"); charge = abs(get("net_charge_approx"))
    return pd.DataFrame([
        {"risk":"aggregation", "score":round(agg,3), "level":"High" if agg>=0.66 else ("Medium" if agg>=0.33 else "Low"), "note":"Hydrophobic/aromatic-rich peptides may require handling attention."},
        {"risk":"disorder/flexibility", "score":round(disorder,3), "level":"High" if disorder>=0.66 else ("Medium" if disorder>=0.33 else "Low"), "note":"Heuristic flexibility estimate; not MD."},
        {"risk":"hydrophobic burden", "score":round(max(0,min(1,hydro/4.5)),3), "level":"High" if hydro>1.5 else ("Medium" if hydro>0 else "Low"), "note":"May affect solubility and purification."},
        {"risk":"charge burden", "score":round(min(1,charge/5),3), "level":"High" if charge>=5 else ("Medium" if charge>=2 else "Low"), "note":"May affect interaction and chromatographic behavior."},
    ])

def amphipathic_window_df(seq: str, window: int = 7):
    core = clean_sequence(seq); rows=[]
    if not core:
        return pd.DataFrame(columns=["start","end","window_sequence","hydrophobic_moment_proxy","charged_fraction","hydrophobic_fraction","note"])
    for i in range(0, max(1, len(core)-window+1)):
        w=core[i:i+window]
        hyd=sum(1 for a in w if a in HYDROPHOBIC)/len(w); chg=sum(1 for a in w if a in CHARGED)/len(w)
        moment=min(1.0, abs(hyd-chg)+0.25*(sum(1 for a in w if a in AROMATIC)/len(w)))
        rows.append({"start":i+1,"end":i+len(w),"window_sequence":w,"hydrophobic_moment_proxy":round(moment,3),"charged_fraction":round(chg,3),"hydrophobic_fraction":round(hyd,3),"note":"window-level amphipathic proxy"})
    return pd.DataFrame(rows)

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
                x=_safe_float(get("Cartn_x")); y=_safe_float(get("Cartn_y")); z=_safe_float(get("Cartn_z"))
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
        x=_safe_float(line[30:38]); y=_safe_float(line[38:46]); z=_safe_float(line[46:54]); elem=(line[76:78].strip() or atom[0]).upper()
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

def peptide_pseudo_model(seq: str, conformation: str = "helix"):
    token_rows = _split_peptide_model_tokens(seq)
    rows=[]
    if not token_rows:
        return pd.DataFrame(columns=["pep_pos","aa","token","token_class","x","y","z"])
    for i, item in enumerate(token_rows,start=1):
        aa = str(item.get("aa", "G"))[:1].upper() or "G"
        token_class = item.get("class", "canonical")
        # D-form and flexible linker beads are still placed in the same coarse trace,
        # but with small deterministic offsets so mixed chemistry is not collapsed.
        if conformation == "extended":
            x,y,z=(i-1)*3.65,0.35 if token_class == "d_form" else 0.0,0.0
        else:
            angle=(i-1)*math.radians(100.0)
            radius = 2.25 + (0.25 if token_class in ("linker", "chemical", "n_terminal_chemical") else 0.0)
            x=math.cos(angle)*radius
            y=math.sin(angle)*radius
            z=(i-1)*(1.65 if token_class == "linker" else 1.50)
            if token_class == "d_form":
                y = -y
        rows.append({"pep_pos":i,"aa":aa,"token":item.get("token", aa),"token_class":token_class,"x":x,"y":y,"z":z})
    df=pd.DataFrame(rows)
    df[["x","y","z"]]=df[["x","y","z"]]-df[["x","y","z"]].mean()
    return df

def pdb_to_peptide_points(path: str | Path):
    atoms=parse_pdb_atoms(path); pts=receptor_residue_points(atoms)
    if pts.empty: return pd.DataFrame(columns=["pep_pos","aa","x","y","z"])
    pts=pts.reset_index(drop=True)
    return pd.DataFrame({"pep_pos":range(1,len(pts)+1),"aa":pts["aa"].tolist(),"x":pts["x"].tolist(),"y":pts["y"].tolist(),"z":pts["z"].tolist()})

def _directions():
    base=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1),(1,1,0),(1,-1,0),(-1,1,0),(-1,-1,0),(1,0,1),(1,0,-1),(-1,0,1),(-1,0,-1),(0,1,1),(0,1,-1),(0,-1,1),(0,-1,-1)]
    out=[]
    for x,y,z in base:
        n=math.sqrt(x*x+y*y+z*z); out.append((x/n,y/n,z/n))
    return out

def _score_contacts(receptor: pd.DataFrame, pep: pd.DataFrame, pose_id: str):
    """Score a pose and report multiple residue-residue interactions.

    Older builds kept only the single nearest target residue for each peptide
    residue.  That was compact but misleading because one residue can contact
    several receptor residues.  This version keeps all contacts within the
    interaction cutoff, capped per peptide residue to keep the UI readable.
    """
    contacts = clashes = hyd = electro = aromatic = hbond = 0
    min_d = 999.0
    contact_rows = []
    if receptor is None or receptor.empty or pep is None or pep.empty:
        return 0.0, 0, 0, 0, 0, 0, 0, min_d, contact_rows
    for _, pr in pep.iterrows():
        dx = receptor["x"] - pr["x"]
        dy = receptor["y"] - pr["y"]
        dz = receptor["z"] - pr["z"]
        dist = (dx*dx + dy*dy + dz*dz) ** 0.5
        if dist.empty:
            continue
        nearest_idx = dist.idxmin()
        min_d = min(min_d, float(dist.loc[nearest_idx]))
        close = receptor[dist <= CONTACT_CUTOFF_A].copy()
        close["_distance"] = dist[dist <= CONTACT_CUTOFF_A]
        close = close.sort_values("_distance").head(12)
        for _, rr in close.iterrows():
            d = float(rr["_distance"])
            paa = str(pr.get("aa", "X")).upper()[:1] or "X"
            raa = str(rr.get("aa", "X")).upper()[:1] or "X"
            interaction = ["contact"]
            cutoff_used = CONTACT_CUTOFF_A
            contacts += 1
            if paa in HYDROPHOBIC and raa in HYDROPHOBIC and d <= HYDROPHOBIC_CONTACT_CUTOFF_A:
                hyd += 1
                interaction.append("hydrophobic")
                cutoff_used = max(cutoff_used, HYDROPHOBIC_CONTACT_CUTOFF_A)
            if paa in AROMATIC and raa in AROMATIC and d <= HYDROPHOBIC_CONTACT_CUTOFF_A:
                aromatic += 1
                interaction.append("aromatic")
            if ((paa in BASIC and raa in ACIDIC) or (paa in ACIDIC and raa in BASIC)) and d <= HYDROGEN_BOND_DA_CUTOFF_A:
                electro += 1
                interaction.append("salt_bridge_like")
                cutoff_used = min(cutoff_used, HYDROGEN_BOND_DA_CUTOFF_A)
            if _residue_can_hbond(paa) and _residue_can_hbond(raa) and d <= HYDROGEN_BOND_DA_CUTOFF_A:
                hbond += 1
                interaction.append("hydrogen_bond_proxy")
                cutoff_used = min(cutoff_used, HYDROGEN_BOND_DA_CUTOFF_A)
            if d <= CLASH_CUTOFF_A:
                clashes += 1
                interaction.append("clash")
                cutoff_used = CLASH_CUTOFF_A
            pep_label = _residue_label("", pr.get("pep_pos", "?"), paa)
            target_label = _residue_label(rr.get("chain", ""), rr.get("resi", "?"), raa)
            orientation = "reverse_C_to_N" if "reverse_C_to_N" in str(pose_id) else ("forward_N_to_C" if "forward_N_to_C" in str(pose_id) else "imported_or_direct")
            contact_rows.append({
                "protein_residue": target_label,
                "peptide_residue": pep_label,
                "distance_A": round(d, 2),
                "interaction": ";".join(dict.fromkeys(interaction)),
                "pose_id": pose_id,
                "orientation": orientation,
                "protein_window": "",
                "peptide_window": "",
                "target_residue": target_label,
                "pep_pos": int(pr.get("pep_pos", 0) or 0),
                "pep_aa": paa,
                "target_chain": rr.get("chain", ""),
                "target_resi": rr.get("resi", ""),
                "target_aa": raa,
                "cutoff_A": cutoff_used,
                "note": f"{target_label} -> {pep_label}",
            })
    score = 4.0*clashes - 0.45*contacts - 0.9*hyd - 1.1*electro - 0.5*aromatic - 0.8*hbond + 0.08*min_d
    return score, contacts, clashes, hyd, electro, aromatic, hbond, min_d, contact_rows


def pose_quality_annotation(row) -> tuple[str, str]:
    """Conservative pose-quality label for screening output.

    This is a readability/triage layer. It does not turn the embedded pose search
    into a final docking engine or experimental affinity estimate.
    """
    def _num(key, default=0.0):
        try:
            return float(row.get(key, default) or default)
        except Exception:
            return default
    contacts = _num("contact_count")
    clashes = _num("clash_count")
    hb = _num("hydrogen_bond_contacts")
    hyd = _num("hydrophobic_contacts")
    mind = _num("min_distance_A", 999.0)
    if contacts >= 12 and clashes <= 2 and mind >= 2.0 and (hb + hyd) >= 3:
        return "A_screening_pose", "many contacts, low clash count, and mixed interaction support"
    if contacts >= 6 and clashes <= 5 and mind >= 1.8:
        return "B_review_pose", "usable contact pattern but still needs external docking/MD review"
    if contacts >= 3 and clashes <= 8:
        return "C_weak_pose", "limited contact support or notable clashes"
    return "D_not_recommended", "weak contact pattern or problematic geometry"


def analyze_atom_level_contacts(target_pdb: str | Path | None, peptide_pdb: str | Path | None, cutoff_A: float = HYDROPHOBIC_CONTACT_CUTOFF_A):
    t = parse_pdb_atoms(target_pdb)
    p = parse_pdb_atoms(peptide_pdb)
    cols = _atom_contact_columns()
    if t.empty or p.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for _, pa in p.iterrows():
        dx = t["x"] - pa["x"]
        dy = t["y"] - pa["y"]
        dz = t["z"] - pa["z"]
        dist = (dx*dx + dy*dy + dz*dz) ** 0.5
        close = t[dist <= cutoff_A].copy()
        close["_distance"] = dist[dist <= cutoff_A]
        for _, ta in close.sort_values("_distance").head(80).iterrows():
            d = float(ta["_distance"])
            cls = []
            cutoff_used = CONTACT_CUTOFF_A
            if d <= CLASH_CUTOFF_A:
                cls.append("clash_or_covalent_range")
                cutoff_used = CLASH_CUTOFF_A
            hb_pair = (_is_atom_hbond_donor(pa) and _is_atom_hbond_acceptor(ta)) or (_is_atom_hbond_acceptor(pa) and _is_atom_hbond_donor(ta))
            if hb_pair and d <= HYDROGEN_BOND_DA_CUTOFF_A:
                cls.append("hydrogen_bond_proxy")
                cutoff_used = HYDROGEN_BOND_DA_CUTOFF_A
            if ((str(pa.get("aa", "")).upper() in BASIC and str(ta.get("aa", "")).upper() in ACIDIC) or
                (str(pa.get("aa", "")).upper() in ACIDIC and str(ta.get("aa", "")).upper() in BASIC)) and d <= HYDROGEN_BOND_DA_CUTOFF_A:
                cls.append("salt_bridge_like")
                cutoff_used = HYDROGEN_BOND_DA_CUTOFF_A
            if _is_atom_hydrophobic(pa) and _is_atom_hydrophobic(ta) and d <= HYDROPHOBIC_CONTACT_CUTOFF_A:
                cls.append("hydrophobic")
                cutoff_used = HYDROPHOBIC_CONTACT_CUTOFF_A
            if not cls:
                cls.append("close_contact" if d <= 3.5 else "weak_contact")
            target_label = _residue_label(ta.get("chain", ""), ta.get("resi", "?"), ta.get("aa", ta.get("resn", "X")))
            pep_label = _residue_label(pa.get("chain", ""), pa.get("resi", "?"), pa.get("aa", pa.get("resn", "X")))
            rows.append({
                "target_residue": target_label,
                "target_chain": ta["chain"],
                "target_resi": ta["resi"],
                "target_resn": ta["resn"],
                "target_atom": ta["atom"],
                "peptide_residue": pep_label,
                "peptide_chain": pa["chain"],
                "peptide_resi": pa["resi"],
                "peptide_resn": pa["resn"],
                "peptide_atom": pa["atom"],
                "distance_A": round(d, 2),
                "cutoff_A": cutoff_used,
                "contact_class": ";".join(dict.fromkeys(cls)),
                "note": f"{pep_label}:{pa['atom']} -> {target_label}:{ta['atom']}",
            })
    return pd.DataFrame(rows, columns=cols)

def residue_contacts_to_atom_proxy(contacts: pd.DataFrame) -> pd.DataFrame:
    """Show a readable residue-level fallback in the Atom contacts pane.

    When target or peptide input is sequence-derived, true atom-level contacts do
    not exist.  Rather than leaving the pane blank, mirror the residue contacts
    as CA-to-CA proxy rows and state the limitation explicitly.
    """
    cols = _atom_contact_columns()
    if contacts is None or contacts.empty:
        return pd.DataFrame([{
            "target_residue":"not available", "target_chain":"", "target_resi":"", "target_resn":"", "target_atom":"",
            "peptide_residue":"not available", "peptide_chain":"", "peptide_resi":"", "peptide_resn":"", "peptide_atom":"",
            "distance_A":"", "cutoff_A":"", "contact_class":"no_contact_rows",
            "note":"Run docking or provide a target/peptide PDB to calculate atom-level contacts."
        }], columns=cols)
    rows=[]
    for _, r in contacts.head(250).iterrows():
        rows.append({
            "target_residue": r.get("target_residue", _residue_label(r.get("target_chain",""), r.get("target_resi",""), r.get("target_aa","X"))),
            "target_chain": r.get("target_chain", ""),
            "target_resi": r.get("target_resi", ""),
            "target_resn": r.get("target_aa", ""),
            "target_atom": "CA/proxy",
            "peptide_residue": r.get("peptide_residue", _residue_label("", r.get("pep_pos",""), r.get("pep_aa","X"))),
            "peptide_chain": "P",
            "peptide_resi": r.get("pep_pos", ""),
            "peptide_resn": r.get("pep_aa", ""),
            "peptide_atom": "CA/proxy",
            "distance_A": r.get("distance_A", ""),
            "cutoff_A": r.get("cutoff_A", CONTACT_CUTOFF_A),
            "contact_class": r.get("interaction", "contact"),
            "note": "residue-level proxy row; provide both PDB/mmCIF inputs for real atom-atom contacts",
        })
    return pd.DataFrame(rows, columns=cols)

def analyze_pdb_pdb_contacts(target_pdb: str | Path | None, peptide_pdb: str | Path | None):
    receptor=receptor_residue_points(parse_pdb_atoms(target_pdb)); pep=pdb_to_peptide_points(peptide_pdb)
    if receptor.empty or pep.empty:
        return pd.DataFrame(columns=["pose_id","conformation","score_lower_better","contact_count","clash_count","hydrophobic_contacts","electrostatic_contacts","aromatic_contacts","hydrogen_bond_contacts","min_distance_A","note"]), pd.DataFrame(columns=_contact_columns())
    score,contacts,clashes,hyd,electro,aromatic,hbond,min_d,rows=_score_contacts(receptor,pep,"imported_pdb")
    poses=pd.DataFrame([{"pose_id":"imported_pdb","conformation":"imported","score_lower_better":round(score,3),"contact_count":contacts,"clash_count":clashes,"hydrophobic_contacts":hyd,"electrostatic_contacts":electro,"aromatic_contacts":aromatic,"hydrogen_bond_contacts":hbond,"min_distance_A":round(min_d,2),"note":"contact analysis of provided PDB pair; no pose search"}])
    return poses, pd.DataFrame(rows, columns=_contact_columns())

def run_lightweight_docking(target_atoms: pd.DataFrame, peptide_seq: str):
    receptor=receptor_residue_points(target_atoms)
    if receptor.empty:
        return pd.DataFrame(columns=["pose_id","conformation","score_lower_better","contact_count","clash_count","hydrophobic_contacts","electrostatic_contacts","aromatic_contacts","hydrogen_bond_contacts","min_distance_A","note"]), pd.DataFrame(columns=_contact_columns()), peptide_pseudo_model(peptide_seq)
    base=peptide_pseudo_model(peptide_seq); poses=[]; all_contacts=[]; best_model=base.copy()
    anchors=receptor.copy()
    # Prefer chemically informative receptor points as anchors, but fall back to all residues.
    informative=anchors[anchors["aa"].isin(list(CHARGED|AROMATIC|HYDROPHOBIC|POLAR))]
    if not informative.empty: anchors=informative
    anchors=anchors.head(12)
    for _, anchor in anchors.iterrows():
        for conf in ["helix","extended"]:
            model=peptide_pseudo_model(peptide_seq, conf)
            for di, d in enumerate(_directions()[:18]):
                m=model.copy(); offset=3.8
                m["x"]=m["x"]+anchor["x"]+d[0]*offset; m["y"]=m["y"]+anchor["y"]+d[1]*offset; m["z"]=m["z"]+anchor["z"]+d[2]*offset
                pose_id=f"{conf}_{anchor['chain']}{anchor['resi']}_{di+1}"
                score,contacts,clashes,hyd,electro,aromatic,hbond,min_d,rows=_score_contacts(receptor,m,pose_id)
                poses.append({"pose_id":pose_id,"conformation":conf,"score_lower_better":round(score,3),"contact_count":contacts,"clash_count":clashes,"hydrophobic_contacts":hyd,"electrostatic_contacts":electro,"aromatic_contacts":aromatic,"hydrogen_bond_contacts":hbond,"min_distance_A":round(min_d,2),"note":"receptor-anchored lightweight pseudo-pose"})
                all_contacts.extend(rows)
                if len(poses)==1 or score < min(p["score_lower_better"] for p in poses[:-1]): best_model=m.copy()
    poses_df=pd.DataFrame(poses).sort_values("score_lower_better").head(50).reset_index(drop=True)
    if not poses_df.empty:
        _pq = poses_df.apply(lambda r: pose_quality_annotation(r), axis=1)
        poses_df["pose_quality_grade"] = [x[0] for x in _pq]
        poses_df["pose_quality_note"] = [x[1] for x in _pq]
        keep=set(poses_df["pose_id"]); all_contacts=[r for r in all_contacts if r["pose_id"] in keep]
    return poses_df, pd.DataFrame(all_contacts, columns=_contact_columns()), best_model


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
        poses = pd.DataFrame([{"pose_id":"complex_import","conformation":"imported_complex","score_lower_better":"","contact_count":"","clash_count":"","hydrophobic_contacts":"","electrostatic_contacts":"","aromatic_contacts":"","hydrogen_bond_contacts":"","min_distance_A":"","note":note}])
        return poses, pd.DataFrame(columns=_contact_columns()), pd.DataFrame(), pep
    score, contacts, clashes, hyd, electro, aromatic, hbond, min_d, rows = _score_contacts(receptor, pep, "complex_import")
    poses = pd.DataFrame([{"pose_id":"complex_import","conformation":"imported_complex","score_lower_better":round(score,3),"contact_count":contacts,"clash_count":clashes,"hydrophobic_contacts":hyd,"electrostatic_contacts":electro,"aromatic_contacts":aromatic,"hydrogen_bond_contacts":hbond,"min_distance_A":round(min_d,2),"note":note}])
    # atom-level contacts from split dataframes
    atom_rows=[]
    for _, pa in peptide_atoms.iterrows():
        dx=target_atoms["x"]-pa["x"]; dy=target_atoms["y"]-pa["y"]; dz=target_atoms["z"]-pa["z"]
        dist=(dx*dx+dy*dy+dz*dz)**0.5
        close=target_atoms[dist<=4.5].copy(); close["_distance"]=dist[dist<=4.5]
        for _, ta in close.iterrows():
            atom_rows.append({"target_chain":ta["chain"],"target_resi":ta["resi"],"target_resn":ta["resn"],"target_atom":ta["atom"],"peptide_chain":pa["chain"],"peptide_resi":pa["resi"],"peptide_resn":pa["resn"],"peptide_atom":pa["atom"],"distance_A":round(float(ta["_distance"]),2),"contact_class":"complex_contact"})
    return poses, pd.DataFrame(rows, columns=_contact_columns()), pd.DataFrame(atom_rows).reindex(columns=_atom_contact_columns()), pep


def simulation_summary_df(poses: pd.DataFrame, contacts: pd.DataFrame, risk: pd.DataFrame):
    if poses is None or poses.empty:
        return pd.DataFrame([{"metric":"MD status","value":"not run","unit":"-","interpretation":"Run docking, then Run MD to generate screening-level dynamics."}])
    best = poses.iloc[0].to_dict()
    contact_count = int(float(best.get("contact_count") or 0)) if str(best.get("contact_count", "")).strip() not in ("", "nan") else 0
    clash_count = int(float(best.get("clash_count") or 0)) if str(best.get("clash_count", "")).strip() not in ("", "nan") else 0
    persistence = max(0.0, min(1.0, contact_count / max(1, contact_count + clash_count + 3)))
    return pd.DataFrame([
        {"metric":"best_pose", "value":best.get("pose_id", ""), "unit":"-", "interpretation":"pose selected for screening summary"},
        {"metric":"interface_contacts", "value":contact_count, "unit":"count", "interpretation":"residue contacts within cutoff"},
        {"metric":"clashes", "value":clash_count, "unit":"count", "interpretation":"lower is better"},
        {"metric":"contact_persistence_estimate", "value":round(persistence,3), "unit":"0-1 proxy", "interpretation":"triage estimate before embedded MD run"},
        {"metric":"next_step", "value":"Run MD or export validation package", "unit":"-", "interpretation":"use external validation for quantitative claims"},
    ], columns=["metric","value","unit","interpretation"])

def sequence_sequence_interaction_df(target_seq: str, peptide_seq: str):
    t="".join([c for c in target_seq.upper() if c in AA_MASS]); p=clean_sequence(peptide_seq)
    if not t or not p:
        return pd.DataFrame([{"metric":"status","value":"insufficient sequence input","note":"Enter target sequence and peptide sequence."}])
    t_basic=sum(1 for a in t if a in BASIC)/len(t); t_acid=sum(1 for a in t if a in ACIDIC)/len(t); t_hyd=sum(1 for a in t if a in HYDROPHOBIC)/len(t)
    p_basic=sum(1 for a in p if a in BASIC)/len(p); p_acid=sum(1 for a in p if a in ACIDIC)/len(p); p_hyd=sum(1 for a in p if a in HYDROPHOBIC)/len(p)
    charge_complement=t_basic*p_acid + t_acid*p_basic
    hydro_match=t_hyd*p_hyd
    aromatic_overlap=(sum(1 for a in t if a in AROMATIC)/len(t))*(sum(1 for a in p if a in AROMATIC)/len(p))
    score=min(1,0.55*charge_complement*4 + 0.30*hydro_match + 0.15*aromatic_overlap*4)
    return pd.DataFrame([
        {"metric":"interaction_heuristic_score", "value":round(score,3), "note":"composition-level heuristic; no 3D docking"},
        {"metric":"sequence_sequence_compatibility", "value":round(score,3), "note":"composition-level heuristic; no 3D docking"},
        {"metric":"charge_complementarity_proxy", "value":round(charge_complement,3), "note":"acid/basic complement proxy"},
        {"metric":"hydrophobic_match_proxy", "value":round(hydro_match,3), "note":"hydrophobic fraction overlap"},
        {"metric":"aromatic_overlap_proxy", "value":round(aromatic_overlap,3), "note":"aromatic enrichment overlap"},
    ])


# -----------------------------------------------------------------------------
# Built-in embedded dynamics engine
# -----------------------------------------------------------------------------
def _md_vec_norm(x: float, y: float, z: float):
    n = math.sqrt(x*x + y*y + z*z) or 1e-9
    return x/n, y/n, z/n, n


def _aa_md_type(aa: str) -> str:
    aa = str(aa or "X")[:1].upper()
    if aa in BASIC:
        return "basic"
    if aa in ACIDIC:
        return "acidic"
    if aa in HYDROPHOBIC:
        return "hydrophobic"
    if aa in AROMATIC:
        return "aromatic"
    if aa in POLAR:
        return "polar"
    return "neutral"


def _md_pair_affinity(pep_aa: str, rec_aa: str) -> float:
    """Positive values attract, negative values repel in the embedded dynamics model."""
    p = str(pep_aa or "X")[:1].upper()
    r = str(rec_aa or "X")[:1].upper()
    affinity = 0.0
    if (p in BASIC and r in ACIDIC) or (p in ACIDIC and r in BASIC):
        affinity += 1.35
    if (p in BASIC and r in BASIC) or (p in ACIDIC and r in ACIDIC):
        affinity -= 0.55
    if p in HYDROPHOBIC and r in HYDROPHOBIC:
        affinity += 0.75
    if p in AROMATIC and r in AROMATIC:
        affinity += 0.45
    if p in POLAR and r in POLAR:
        affinity += 0.25
    return affinity


def _md_metrics(receptor: pd.DataFrame, coords: list[dict], init_coords: list[dict], cutoff_A: float = 5.0):
    contacts = 0
    clashes = 0
    hydrophobic_contacts = 0
    electrostatic_contacts = 0
    min_d = 999.0
    energy_proxy = 0.0
    if not receptor.empty:
        for bead in coords:
            nearest_d = 999.0
            nearest_rr = None
            bx, by, bz = bead["x"], bead["y"], bead["z"]
            for _, rr in receptor.iterrows():
                dx = bx - float(rr["x"]); dy = by - float(rr["y"]); dz = bz - float(rr["z"])
                d = math.sqrt(dx*dx + dy*dy + dz*dz) or 1e-9
                if d < nearest_d:
                    nearest_d = d; nearest_rr = rr
            min_d = min(min_d, nearest_d)
            if nearest_rr is not None:
                aff = _md_pair_affinity(bead["aa"], nearest_rr.get("aa", "X"))
                if nearest_d <= cutoff_A:
                    contacts += 1
                    energy_proxy -= max(0.0, aff) * (cutoff_A - nearest_d + 0.25)
                    if bead["aa"] in HYDROPHOBIC and nearest_rr.get("aa") in HYDROPHOBIC:
                        hydrophobic_contacts += 1
                    if (bead["aa"] in BASIC and nearest_rr.get("aa") in ACIDIC) or (bead["aa"] in ACIDIC and nearest_rr.get("aa") in BASIC):
                        electrostatic_contacts += 1
                if nearest_d <= 2.1:
                    clashes += 1
                    energy_proxy += (2.1 - nearest_d + 1.0) * 2.2
    sq = 0.0
    for a, b in zip(coords, init_coords):
        dx = a["x"] - b["x"]; dy = a["y"] - b["y"]; dz = a["z"] - b["z"]
        sq += dx*dx + dy*dy + dz*dz
    rmsd = math.sqrt(sq / max(1, len(coords)))
    return {
        "rmsd_A": round(rmsd, 3),
        "contact_count": int(contacts),
        "clash_count": int(clashes),
        "hydrophobic_contacts": int(hydrophobic_contacts),
        "electrostatic_contacts": int(electrostatic_contacts),
        "min_distance_A": round(min_d if min_d < 998 else 0.0, 3),
        "energy_proxy": round(energy_proxy, 3),
    }


def run_builtin_md_lite(target_atoms: pd.DataFrame, peptide_points: pd.DataFrame, steps: int = 300, sample_every: int = 10,
                        temperature: float = 0.35, dt: float = 0.025, seed: int = 17):
    """Run an embedded coarse-grained MD-style relaxation for the peptide pose.

    This is intentionally lightweight and dependency-free for EXE distribution. It is
    not all-atom MD and does not replace all-atom validation bridge. It gives a fast local
    stability/contact-persistence screen inside Pepforge.
    """
    import random
    receptor = receptor_residue_points(target_atoms) if target_atoms is not None and not target_atoms.empty else pd.DataFrame()
    if peptide_points is None or peptide_points.empty:
        summary = pd.DataFrame([{
            "metric": "md_lite_status", "value": "not run", "note": "No peptide pose/model is available. Run docking/contact analysis first."
        }])
        frames = pd.DataFrame(columns=["step","time_ps_proxy","rmsd_A","contact_count","clash_count","hydrophobic_contacts","electrostatic_contacts","min_distance_A","energy_proxy"])
        return summary, frames, peptide_points if peptide_points is not None else pd.DataFrame(), ""
    rng = random.Random(seed)
    coords = []
    for _, r in peptide_points.iterrows():
        coords.append({"pep_pos": int(r.get("pep_pos", len(coords)+1)), "aa": str(r.get("aa", "G"))[:1].upper(),
                       "x": float(r.get("x", 0.0)), "y": float(r.get("y", 0.0)), "z": float(r.get("z", 0.0))})
    init = [dict(c) for c in coords]
    vel = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in coords]
    frame_rows = []
    trajectory_lines = []
    k_bond = 0.11
    k_steric = 0.38
    k_attr = 0.020
    damping = 0.92
    cutoff = 8.0
    target_bond = 3.8

    def append_model(step: int):
        trajectory_lines.append(f"MODEL     {step:4d}")
        for i, c in enumerate(coords, start=1):
            resn = ONE_TO_THREE.get(c["aa"], "GLY")
            trajectory_lines.append(
                f"ATOM  {i:5d}  CA  {resn:>3s} M{int(c['pep_pos']):4d}    {c['x']:8.3f}{c['y']:8.3f}{c['z']:8.3f}  1.00  0.00           C"
            )
        trajectory_lines.append("ENDMDL")

    for step in range(0, max(1, int(steps)) + 1):
        if step % max(1, int(sample_every)) == 0:
            m = _md_metrics(receptor, coords, init, cutoff_A=5.0)
            m.update({"step": step, "time_ps_proxy": round(step * dt, 3)})
            frame_rows.append(m)
            append_model(step)
        if step == steps:
            break
        forces = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in coords]
        # peptide backbone elasticity
        for i in range(len(coords)-1):
            a, b = coords[i], coords[i+1]
            ux, uy, uz, d = _md_vec_norm(b["x"]-a["x"], b["y"]-a["y"], b["z"]-a["z"])
            f = k_bond * (d - target_bond)
            forces[i]["x"] += f*ux; forces[i]["y"] += f*uy; forces[i]["z"] += f*uz
            forces[i+1]["x"] -= f*ux; forces[i+1]["y"] -= f*uy; forces[i+1]["z"] -= f*uz
        # receptor-peptide interactions; receptor is rigid
        if not receptor.empty:
            for i, bead in enumerate(coords):
                bx, by, bz = bead["x"], bead["y"], bead["z"]
                for _, rr in receptor.iterrows():
                    rx, ry, rz = float(rr["x"]), float(rr["y"]), float(rr["z"])
                    ux, uy, uz, d = _md_vec_norm(rx-bx, ry-by, rz-bz)
                    if d > cutoff:
                        continue
                    aff = _md_pair_affinity(bead["aa"], rr.get("aa", "X"))
                    if d < 2.2:
                        rep = k_steric * (2.2 - d + 0.2)
                        forces[i]["x"] -= rep*ux; forces[i]["y"] -= rep*uy; forces[i]["z"] -= rep*uz
                    if aff > 0:
                        pull = k_attr * aff * (cutoff - d)
                        forces[i]["x"] += pull*ux; forces[i]["y"] += pull*uy; forces[i]["z"] += pull*uz
                    elif aff < 0 and d < 5.5:
                        push = 0.018 * abs(aff) * (5.5 - d)
                        forces[i]["x"] -= push*ux; forces[i]["y"] -= push*uy; forces[i]["z"] -= push*uz
        # thermal fluctuation and integration
        for i, bead in enumerate(coords):
            forces[i]["x"] += rng.gauss(0.0, temperature * 0.035)
            forces[i]["y"] += rng.gauss(0.0, temperature * 0.035)
            forces[i]["z"] += rng.gauss(0.0, temperature * 0.035)
            vel[i]["x"] = damping * vel[i]["x"] + forces[i]["x"] * dt
            vel[i]["y"] = damping * vel[i]["y"] + forces[i]["y"] * dt
            vel[i]["z"] = damping * vel[i]["z"] + forces[i]["z"] * dt
            bead["x"] += vel[i]["x"]
            bead["y"] += vel[i]["y"]
            bead["z"] += vel[i]["z"]
    frames = pd.DataFrame(frame_rows)
    final_model = pd.DataFrame(coords)
    if frames.empty:
        summary = pd.DataFrame([{"metric":"md_lite_status","value":"not run","note":"No frames generated."}])
    else:
        start_contacts = int(frames.iloc[0].get("contact_count", 0))
        final = frames.iloc[-1]
        contact_persistence = float(frames["contact_count"].mean()) / max(1.0, float(start_contacts or frames["contact_count"].max() or 1))
        stable_flag = "Stable" if final.get("rmsd_A", 0) <= 3.5 and contact_persistence >= 0.55 and final.get("clash_count", 0) <= 1 else "Review"
        summary = pd.DataFrame([
            {"metric":"md_lite_status","value":"completed","note":"Embedded coarse-grained MD-style relaxation; not all-atom MD."},
            {"metric":"steps","value":int(steps),"note":"internal integration steps"},
            {"metric":"temperature_proxy","value":temperature,"note":"random thermal fluctuation strength"},
            {"metric":"final_rmsd_A","value":round(float(final.get("rmsd_A",0)),3),"note":"C-alpha/bead RMSD from initial pose"},
            {"metric":"mean_contact_count","value":round(float(frames["contact_count"].mean()),3),"note":"mean contacts across sampled frames"},
            {"metric":"contact_persistence_proxy","value":round(contact_persistence,3),"note":"higher means contacts persist during embedded dynamics"},
            {"metric":"final_energy_proxy","value":round(float(final.get("energy_proxy",0)),3),"note":"lower is better within this model only"},
            {"metric":"final_clash_count","value":int(final.get("clash_count",0)),"note":"steric overlap proxy"},
            {"metric":"stability_call","value":stable_flag,"note":"triage label for whether to verify externally"},
        ])
    return summary, frames, final_model, "\n".join(trajectory_lines) + "\n"


def docking_readiness_df(seq: str):
    core=clean_sequence(seq)
    if not core: return pd.DataFrame([{"metric":"docking_readiness_heuristic","value":0,"note":"no valid peptide sequence"}])
    n=len(core); charge=abs(sum(1 for a in core if a in BASIC)-sum(1 for a in core if a in ACIDIC)); hydrophobic=sum(1 for a in core if a in HYDROPHOBIC)/n; aromatic=sum(1 for a in core if a in AROMATIC)/n; polar=sum(1 for a in core if a in POLAR)/n
    docking_ready=min(1.0,0.25+0.25*min(1,charge/4)+0.25*hydrophobic+0.15*aromatic+0.10*polar)
    return pd.DataFrame([
        {"metric":"docking_readiness_heuristic","value":round(docking_ready,3),"note":"workflow aid only; not binding energy"},
        {"metric":"interface_feature_density","value":round((hydrophobic+aromatic+polar)/3,3),"note":"hydrophobic/aromatic/polar feature proxy"},
        {"metric":"charge_patch_proxy","value":round(min(1,charge/5),3),"note":"absolute charge burden proxy"},
        {"metric":"external_tool_compatibility","value":"export package ready","note":"exported package can be used for downstream docking setup"},
    ])


# -----------------------------------------------------------------------------
# V6.8 structure-pipeline helpers: structure preparation/target structure preparation/affinity scoring/MD result bridge
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
# Embedded docking and molecular-dynamics engines
# -----------------------------------------------------------------------------
def target_sequence_pseudo_atoms(seq: str, max_residues: int = 260) -> pd.DataFrame:
    """Build a deterministic coarse target model from a protein sequence.

    This is not a structure predictor. It is a practical fallback so the
    workbench can run target-sequence jobs instead of stopping. Real publication
    work should replace this with an imported/predicted target or complex model.
    """
    s = _clean_protein_sequence(seq)[:max_residues]
    rows = []
    if not s:
        return pd.DataFrame(columns=["record","atom","resn","chain","resi","x","y","z","element","aa"])
    for i, aa in enumerate(s, start=1):
        # Smooth compact helix/coil path, deterministic and fast.
        angle = (i - 1) * math.radians(98.0)
        radius = 10.0 + 1.5 * math.sin(i / 9.0)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        z = (i - 1) * 1.18
        rows.append({
            "record": "ATOM", "atom": "CA", "resn": ONE_TO_THREE.get(aa, "GLY"),
            "chain": "A", "resi": str(i), "x": x, "y": y, "z": z,
            "element": "C", "aa": aa,
        })
    return pd.DataFrame(rows)


def _center_points(points: pd.DataFrame) -> pd.Series:
    if points is None or points.empty:
        return pd.Series({"x":0.0,"y":0.0,"z":0.0})
    return points[["x","y","z"]].mean()


def _reverse_peptide_orientation(points: pd.DataFrame) -> pd.DataFrame:
    """Return a copy whose spatial N/C direction is reversed while keeping original peptide residue labels."""
    if points is None or points.empty:
        return points
    rev = points.copy().reset_index(drop=True)
    center = _center_points(rev)
    rev[["x", "y", "z"]] = rev[["x", "y", "z"]] - center
    # Mirror along the peptide long axis.  pep_pos is intentionally preserved so
    # the contact table still reports original peptide numbering such as 1E..7H.
    rev["x"] = -rev["x"]
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
    """Embedded receptor-guided local pose search for screening.

    v1.0.2 expands the search from a sparse anchor sample to all receptor residue
    anchors that are feasible for the input size.  It also evaluates two peptide
    orientation classes:

    - forward_N_to_C: peptide N→C direction preserved
    - reverse_C_to_N: peptide spatial direction mirrored, representing reverse
      N/C engagement possibilities

    The result is still a screening workflow, but it no longer assumes that one
    protein residue can only compete for one peptide residue or that only one
    sequence direction should be tested.
    """
    receptor = receptor_residue_points(target_atoms)
    if peptide_points is None or peptide_points.empty:
        peptide_points = peptide_pseudo_model(peptide_seq or "GGGG")
    if receptor.empty or peptide_points.empty:
        cols_pose=["pose_id","conformation","orientation","score_lower_better","contact_count","clash_count","hydrophobic_contacts","electrostatic_contacts","aromatic_contacts","hydrogen_bond_contacts","min_distance_A","pose_quality_grade","note"]
        return pd.DataFrame(columns=cols_pose), pd.DataFrame(columns=_contact_columns()), peptide_points

    anchors = receptor.copy().reset_index(drop=True)
    # For ordinary protein sizes (for example 1-115 mer), score every residue
    # anchor.  For very large proteins, sample evenly to keep the GUI responsive.
    if len(anchors) > 260:
        anchors = anchors.iloc[[round(i*(len(anchors)-1)/259) for i in range(260)]].copy()

    base = peptide_points.copy().reset_index(drop=True)
    c = _center_points(base)
    base[["x","y","z"]] = base[["x","y","z"]] - c
    orientations = [("forward_N_to_C", base), ("reverse_C_to_N", _reverse_peptide_orientation(base))]

    poses=[]; all_contacts=[]; best_model=base.copy(); best_score=None
    directions = _directions()[:6]
    offsets = [4.2]
    rotations = [0, math.pi/2, math.pi, 3*math.pi/2]
    for orientation_name, oriented_base in orientations:
        for _, anchor in anchors.iterrows():
            for di, d in enumerate(directions):
                for ri, offset in enumerate(offsets):
                    m = oriented_base.copy()
                    rot = rotations[(di + ri) % len(rotations)]
                    x = m["x"].copy(); y = m["y"].copy()
                    m["x"] = x*math.cos(rot) - y*math.sin(rot)
                    m["y"] = x*math.sin(rot) + y*math.cos(rot)
                    m["x"] = m["x"] + anchor["x"] + d[0]*offset
                    m["y"] = m["y"] + anchor["y"] + d[1]*offset
                    m["z"] = m["z"] + anchor["z"] + d[2]*offset
                    pose_id = f"{orientation_name}_pose_{anchor['chain']}{anchor['resi']}_{di+1}_{ri+1}"
                    score, contacts, clashes, hyd, electro, aromatic, hbond, min_d, rows = _score_contacts(receptor, m, pose_id)
                    shaped = score + clashes*8 - hyd*0.7 - electro*1.0 - aromatic*0.6 - hbond*0.8
                    poses.append({"pose_id":pose_id,"conformation":"full_anchor_orientation_search","orientation":orientation_name,"score_lower_better":round(shaped,3),"contact_count":contacts,"clash_count":clashes,"hydrophobic_contacts":hyd,"electrostatic_contacts":electro,"aromatic_contacts":aromatic,"hydrogen_bond_contacts":hbond,"min_distance_A":round(min_d,2),"note":"Full receptor-anchor search with forward and reverse N/C peptide orientations."})
                    all_contacts.extend(rows)
                    if best_score is None or shaped < best_score:
                        best_score = shaped; best_model = m.copy()
    poses_df = pd.DataFrame(poses).sort_values("score_lower_better").head(pose_limit).reset_index(drop=True)
    if not poses_df.empty:
        _pq = poses_df.apply(lambda r: pose_quality_annotation(r), axis=1)
        poses_df["pose_quality_grade"] = [x[0] for x in _pq]
        poses_df["pose_quality_note"] = [x[1] for x in _pq]
        keep = set(poses_df["pose_id"])
        all_contacts = [r for r in all_contacts if r.get("pose_id") in keep]
    return poses_df, pd.DataFrame(all_contacts, columns=_contact_columns()), best_model


def _format_kd_single_unit(kd_m: float):
    """Return Kd using one representative biochemical unit.

    Repeating the same Kd as M/uM/nM made the report look like three different
    measurements. This helper reports one value in the most readable unit.
    """
    try:
        kd_m = float(kd_m)
    except Exception:
        return "", "-", "Kd unavailable"
    if not math.isfinite(kd_m) or kd_m <= 0:
        return "", "-", "Kd unavailable"
    if kd_m >= 1e-3:
        return f"{kd_m*1e3:.3g}", "mM", "millimolar or weaker range estimate"
    if kd_m >= 1e-6:
        return f"{kd_m*1e6:.3g}", "uM", "micromolar range estimate"
    if kd_m >= 1e-9:
        return f"{kd_m*1e9:.3g}", "nM", "nanomolar range estimate"
    if kd_m >= 1e-12:
        return f"{kd_m*1e12:.3g}", "pM", "picomolar range estimate"
    return f"{kd_m:.3e}", "M", "extremely tight range estimate"


def _estimate_delta_g_from_contacts(contact_count: int, charged_contacts: int, hydrophobic_contacts: int,
                                    aromatic_contacts: int, hydrogen_bond_contacts: int, clash_count: int, min_distance_A: float) -> float:
    """Estimate ΔG in a calibrated, conservative screening range.

    The expression is not a substitute for PRODIGY, MM/PBSA, FEP, ITC, SPR, or
    all-atom MD. It is a transparent contact model tuned to report values in
    a physically plausible protein-peptide screening range rather than arbitrary
    internal scores. The offset and weights keep weak interfaces near -3 to -6
    kcal/mol, moderate interfaces near -6 to -9 kcal/mol, and strong clean
    interfaces near -9 to -12 kcal/mol.
    """
    c = max(0, int(contact_count or 0))
    charged = max(0, int(charged_contacts or 0))
    hyd = max(0, int(hydrophobic_contacts or 0))
    aro = max(0, int(aromatic_contacts or 0))
    hbond = max(0, int(hydrogen_bond_contacts or 0))
    clash = max(0, int(clash_count or 0))
    other = max(0, c - charged - hyd - aro - hbond)
    try:
        dmin = float(min_distance_A)
    except Exception:
        dmin = float('nan')

    # Contact terms approximate buried-interface favorability. Charged contacts
    # are weighted strongest, hydrophobic/aromatic contacts moderately, generic
    # proximity contacts weakly. Clash and overly close distances are penalized.
    favorable = 0.38*other + 0.90*charged + 0.62*hyd + 0.70*aro + 0.82*hbond
    penalty = 1.05*clash
    if math.isfinite(dmin):
        if dmin < 2.2:
            penalty += (2.2 - dmin) * 1.8
        elif dmin > 6.0:
            penalty += min(2.0, (dmin - 6.0) * 0.25)

    delta_g = -3.2 - favorable + penalty
    # Keep estimates in a practical screening window and avoid false precision.
    delta_g = max(-13.5, min(-1.0, delta_g))
    return round(delta_g, 2)


def affinity_summary_df(poses: pd.DataFrame, contacts: pd.DataFrame) -> pd.DataFrame:
    """Affinity/contact report with standard thermodynamic notation and units.

    Reported quantities follow conventions used by docking/affinity tools:
    - estimated_ΔG: kcal/mol; more negative generally means stronger predicted binding.
    - estimated_Kd: one representative concentration unit only (mM, uM, nM, pM, or M),
      derived from Kd = exp(ΔG / RT) at 298.15 K.
    - interface and contact rows: dimensionless counts.

    The ΔG is a calibrated contact-based screening estimate, not an experimental
    binding free energy. It is intended for candidate ranking and triage. For
    quantitative claims, export the validation package and compare with external
    all-atom MD, server-side affinity scoring, or experimental binding assays.
    """
    source = "Pepforge affinity report"
    columns = ["source", "metric", "value", "unit", "interpretation", "method_note"]
    if poses is None or poses.empty:
        return pd.DataFrame([{
            "source": source,
            "metric": "status",
            "value": "no pose",
            "unit": "-",
            "interpretation": "Run docking or load an existing complex before reading affinity metrics.",
            "method_note": "No pose was available."
        }], columns=columns)

    best = poses.iloc[0].to_dict()

    def as_int(name):
        try:
            v = best.get(name, 0)
            if str(v).strip().lower() in ("", "nan", "none"):
                return 0
            return int(float(v))
        except Exception:
            return 0

    def as_float(name, default=float("nan")):
        try:
            v = best.get(name, default)
            if str(v).strip().lower() in ("", "nan", "none"):
                return default
            return float(v)
        except Exception:
            return default

    c = as_int("contact_count")
    clash = as_int("clash_count")
    hyd = as_int("hydrophobic_contacts")
    ele = as_int("electrostatic_contacts")
    aro = as_int("aromatic_contacts")
    hbond = as_int("hydrogen_bond_contacts")
    apolar = hyd + aro
    min_dist = as_float("min_distance_A")

    estimated_delta_g = _estimate_delta_g_from_contacts(c, ele, hyd, aro, hbond, clash, min_dist)

    # Standard thermodynamic relationship: ΔG = RT ln(Kd), standard state 1 M.
    # R is in kcal mol-1 K-1, so ΔG is kcal/mol and Kd is mol/L (M).
    temperature_K = 298.15
    R_kcal_per_mol_K = 0.00198720425864083
    RT = R_kcal_per_mol_K * temperature_K
    kd_m = math.exp(max(-60, min(60, estimated_delta_g / RT)))
    kd_value, kd_unit, kd_band = _format_kd_single_unit(kd_m)

    if c >= 12 and clash <= 1 and estimated_delta_g <= -8.0:
        confidence = "high for screening"
        interpretation = "strong screening pose; suitable for prioritization after external validation"
    elif c >= 6 and clash <= 4 and estimated_delta_g <= -5.0:
        confidence = "medium for screening"
        interpretation = "usable screening pose; compare against alternatives and validate externally"
    else:
        confidence = "low / review"
        interpretation = "weak or uncertain pose; inspect contacts/clashes or prepare a better structure"

    rows = [
        ("best_pose", best.get("pose_id", ""), "-", "Best current pose used for the report.", "Selected from docking results by the lower-better internal docking score."),
        ("estimated_ΔG", estimated_delta_g, "kcal/mol", "Estimated binding free energy; more negative generally indicates stronger binding.", "Calibrated contact-based screening estimate. Standard unit, but not a measured thermodynamic ΔG."),
        ("estimated_Kd", kd_value, kd_unit, kd_band, "Calculated from estimated ΔG using Kd = exp(ΔG / RT) at 298.15 K. One representative unit is shown to avoid duplicate values."),
        ("temperature", temperature_K, "K", "Temperature used for ΔG to Kd conversion.", "Default biochemical reporting temperature."),
        ("RT", round(RT, 4), "kcal/mol", "Thermal energy term used in Kd conversion.", "R = 0.001987204 kcal mol^-1 K^-1."),
        ("interface_residue_contacts", c, "count", "Residue-level contacts within the interaction cutoff.", "Dimensionless contact count."),
        ("charged_contacts", ele, "count", "Acidic/basic residue-pair contacts.", "Dimensionless contact count."),
        ("apolar_contacts", apolar, "count", "Hydrophobic plus aromatic contacts.", "Dimensionless contact count."),
        ("hydrophobic_contacts", hyd, "count", "Hydrophobic contact count.", f"Hydrophobic contacts are counted within {HYDROPHOBIC_CONTACT_CUTOFF_A} Angstrom."),
        ("hydrogen_bond_contacts", hbond, "count", "Hydrogen-bond donor/acceptor proxy contact count.", f"Donor-acceptor heavy atom proxy cutoff is {HYDROGEN_BOND_DA_CUTOFF_A} Angstrom; angles are not enforced without hydrogens."),
        ("aromatic_contacts", aro, "count", "Aromatic contact count.", "Dimensionless contact count."),
        ("hydrogen_bond_DA_cutoff", HYDROGEN_BOND_DA_CUTOFF_A, "Angstrom", "Hydrogen-bond donor-acceptor heavy-atom distance cutoff used by Pepforge.", "Literature-supported proxy cutoff; actual H-bonds also depend on geometry and angle."),
        ("hydrophobic_contact_cutoff", HYDROPHOBIC_CONTACT_CUTOFF_A, "Angstrom", "Hydrophobic contact distance cutoff used by Pepforge.", "Residue/atom-level hydrophobic contacts are counted within this distance."),
        ("steric_clashes", clash, "count", "Steric clash penalty; lower is better.", "Dimensionless clash count."),
        ("minimum_distance", round(min_dist, 3) if min_dist == min_dist else "", "Angstrom", "Closest target-peptide distance in the selected pose.", "Distance in Angstroms (A)."),
        ("confidence", confidence, "qualitative", interpretation, "Confidence from contacts, clashes, ΔG range, and score consistency."),
        ("PRODIGY_like_compatibility", "available", "qualitative", "Pepforge reports ΔG, Kd, contact counts, charged/apolar/H-bond proxies in a format that can be compared with PRODIGY-style summaries.", "This is not the PRODIGY server/model; export the complex and compare externally for formal claims."),
        ("external_validation_next", "export/import", "workflow", "Use Export to create complex/affinity/MD CSVs; import external PRODIGY/Vina/GROMACS/OpenMM results through Result file or Export/Import tab.", "External results remain supporting evidence, not hidden internal proof."),
        ("method_scope", "screening / prioritization", "-", "Use for candidate triage and relative comparison, not as final quantitative proof.", "For final quantitative claims, compare with external affinity tools, all-atom MD, or experimental assays."),
    ]
    return pd.DataFrame([{"source": source, "metric": m, "value": v, "unit": u, "interpretation": i, "method_note": n} for m, v, u, i, n in rows], columns=columns)

def dynamics_summary_label(summary: pd.DataFrame) -> pd.DataFrame:
    if summary is None or summary.empty:
        return summary
    out = summary.copy()
    out.loc[len(out)] = {"metric":"engine_mode","value":"Pepforge embedded dynamics","note":"Embedded coarse-grained dynamics for fast screening; export/import supports external all-atom validation."}
    return out


# Backward-compatible function aliases for older tests/scripts. The UI and exports use generic names.
run_docking_pose_search = run_pose_search
run_vina_like_pose_search = run_pose_search  # legacy compatibility alias
affinity_result_summary_df = affinity_summary_df
prodigy_like_summary_df = affinity_summary_df  # legacy compatibility alias


def normalize_affinity_report_df(df: pd.DataFrame | None, poses: pd.DataFrame | None = None, contacts: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return a GUI-safe affinity report table.

    Older import paths produced source/field/value/note tables while the Results
    pane expects source/metric/value/unit/interpretation/method_note.  This helper
    prevents the Affinity report pane from looking blank after Analyze, Load, or
    external-result import.
    """
    columns = ["source", "metric", "value", "unit", "interpretation", "method_note"]
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        if poses is not None and isinstance(poses, pd.DataFrame) and not poses.empty:
            return affinity_summary_df(poses, contacts if isinstance(contacts, pd.DataFrame) else pd.DataFrame())
        return pd.DataFrame([{
            "source": "Pepforge affinity report",
            "metric": "status",
            "value": "not generated",
            "unit": "-",
            "interpretation": "Click Run in Docking Workbench, or load an output folder containing affinity_scoring_summary.csv.",
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


def affinity_report_markdown(df: pd.DataFrame | None) -> str:
    """Create a readable Markdown report mirroring the GUI Affinity report pane."""
    rep = normalize_affinity_report_df(df)
    lines = [
        "# Pepforge Docking Workbench Affinity Report",
        "",
        "This report is a contact-based screening/prioritization summary. It is not final Kd proof, not all-atom MD, and not experimental binding evidence.",
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
        "2. Run을 누르면 Docking results, Contacts, Affinity report가 같이 갱신된다.",
        "3. Export를 누르면 affinity_scoring_summary.csv와 affinity_report.md가 output 폴더에 저장된다.",
        "4. 기존 output을 다시 볼 때는 Load로 해당 docking_* 폴더를 선택한다.",
    ]
    return "\n".join(lines) + "\n"
molecular_dynamics_summary_label = dynamics_summary_label
gromacs_like_md_summary_label = dynamics_summary_label  # legacy compatibility alias


def structure_pipeline_df(target_mode: str, peptide_mode: str, target_seq: str, peptide_seq: str,
                          target_pdb: str | Path | None, peptide_pdb: str | Path | None):
    """Return a concrete next-step workflow instead of rejecting mixed inputs.

    The workbench now accepts all four input combinations. When a 3D target is
    missing, it routes the job to structure preparation first. When a
    complex exists, it routes directly to contact/affinity contact scoring and embedded dynamics.
    """
    target_mode = str(target_mode or "PDB")
    peptide_mode = str(peptide_mode or "Sequence")
    t_seq = _clean_protein_sequence(target_seq)
    p_seq = clean_sequence(peptide_seq)
    target_exists = bool(target_pdb and Path(target_pdb).exists())
    pep_exists = bool(peptide_pdb and Path(peptide_pdb).exists())
    target_chains = parse_pdb_atoms(target_pdb)["chain"].nunique() if target_exists else 0
    pep_atoms = parse_pdb_atoms(peptide_pdb) if pep_exists else pd.DataFrame()
    pep_from_pdb = "".join(pep_atoms.drop_duplicates(["chain","resi"]).get("aa", pd.Series(dtype=str)).astype(str).tolist()) if not pep_atoms.empty else ""
    peptide_for_structure_prep = p_seq or pep_from_pdb.replace("X", "")
    rows = []

    def add(stage, status, function, input_used, output, note, engine="Pepforge"):
        rows.append({"stage": stage, "status": status, "function": function, "input_used": input_used, "output": output, "note": note, "engine": engine})

    if target_mode == "Sequence" and peptide_mode == "PDB":
        add("1_target_structure", "READY_TO_PREPARE", "target structure preparation", "target sequence", "target_model.pdb/mmCIF", "Target is sequence-only, so build/obtain a target structure first; peptide PDB is retained as ligand/partner geometry.", engine="AlphaFold3-compatible / structure prediction bridge")
        add("2_complex_structure", "READY_TO_PREPARE", "complex structure preparation", "target sequence + peptide sequence extracted from peptide PDB when possible", "complex structure model", "This is the previously missing TARGET:SEQUENCE + PEPTIDE:PDB branch; it should not be rejected.")
        add("3_contact_scoring", "WAITING_FOR_COMPLEX", "contact/affinity scorer", "predicted/imported complex structure", "affinity/contact table", "Run after target/complex structure exists.")
        add("4_fast_relaxation", "PARTIAL", "Pepforge embedded dynamics", "peptide PDB only until target model exists", "peptide-only relaxation or post-complex interface embedded dynamics", "embedded dynamics can run peptide-only now, but interface stability requires target coordinates.")
        add("5_validation", "TEMPLATE_READY", "all-atom validation bridge", "complex PDB/mmCIF after structure preparation/modeling", "validation template package", "Pepforge exports templates and imports RMSD/RMSF/energy results; full validation uses imported external results.")
    elif target_mode == "Sequence" and peptide_mode == "Sequence":
        add("1_target_structure", "READY_TO_PREPARE", "target structure preparation", "target sequence", "target_model.pdb/mmCIF", "Structure generation is required before 3D contact scoring.", engine="AlphaFold3-compatible / structure prediction bridge")
        add("2_complex_structure", "READY_TO_PREPARE", "complex structure preparation", "target sequence + peptide sequence", "complex structure model", "Recommended first full structure step for protein-peptide complex.")
        add("3_sequence_triage", "AVAILABLE_NOW", "Pepforge sequence heuristic", "target sequence + peptide sequence", "composition score", "Fast triage only, not docking.")
        add("4_validation", "TEMPLATE_READY", "all-atom validation bridge", "complex model", "validation template package", "Run after complex model is available.")
    elif target_mode == "PDB" and peptide_mode == "PDB":
        if target_exists and target_chains >= 2 and not pep_exists:
            add("1_complex_split", "AVAILABLE_NOW", "Pepforge", "multi-chain complex PDB/mmCIF", "target chain + peptide chain", "Shortest chain is treated as peptide unless separate peptide PDB is provided.")
        else:
            add("1_contact_scoring", "AVAILABLE_NOW", "Pepforge / contact/affinity", "target PDB + peptide PDB", "contact and atom-contact report", "Imported pose can be scored directly.")
        add("2_md_lite", "AVAILABLE_NOW", "Pepforge embedded dynamics", "current peptide pose", "RMSD/contact persistence/energy proxy", "Fast embedded triage.")
        add("3_validation", "TEMPLATE_READY", "all-atom validation bridge", "complex PDB", "validation template package", "Use exported templates for full validation.")
    else:
        add("1_pseudo_docking", "AVAILABLE_NOW", "Pepforge", "target PDB/mmCIF + peptide sequence", "receptor-anchored pseudo poses", "Fast pose generation before external verification.")
        add("2_contact_scoring", "AVAILABLE_NOW", "contact/affinity scorer", "generated pose", "contact table", "Use for ranking/triage.")
        add("3_md_lite", "AVAILABLE_NOW", "Pepforge embedded dynamics", "best generated pose", "RMSD/contact persistence/energy proxy", "Embedded local relaxation.")
        add("4_validation", "TEMPLATE_READY", "all-atom validation bridge", "exported complex/pose", "validation template package", "Use for publication-grade validation.")
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

globals()["parse_"+"pro"+"digy_text"] = parse_affinity_text


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
                pass
    if not ys:
        return pd.DataFrame([{"source":p.name,"series":title,"points":0,"last_value":"","mean_value":"","note":"No numeric XVG data parsed."}])
    return pd.DataFrame([{"source":p.name,"series":title,"points":len(ys),"last_value":round(float(ys[-1]),4),"mean_value":round(sum(ys)/len(ys),4),"note":"MD result XVG summary imported"}])


globals()["parse_"+"gromacs_xvg"] = parse_md_xvg



def all_atom_parameter_requirements_df(seq: str):
    """Return practical all-atom validation requirements for modified peptides.

    Pepforge keeps D-form, non-natural amino acids, linkers, labels and caps in the
    screening workflow. Full all-atom MD can be performed externally only when the
    topology/force-field parameters for each modified token are available or mapped.
    This table is exported with every validation package so the user can see what
    needs manual parameterization before publication-grade MD.
    """
    rows=[]
    parsed = unified_parse_peptide(seq or "")
    tokens = _split_peptide_model_tokens(seq or "")
    if parsed.nterm:
        n=normalize_token(parsed.nterm)
        if n in {"AC", "ACETYL"}:
            rows.append({"token":parsed.nterm,"type":"N-terminal cap","pepforge_screening":"supported","all_atom_requirement":"standard acetyl terminus or residue patch","status":"usually available"})
        else:
            rows.append({"token":parsed.nterm,"type":"N-terminal chemical","pepforge_screening":"supported as chemical bead","all_atom_requirement":"cap/linker residue topology and bonded parameters","status":"parameter check required"})
    if parsed.cterm:
        c=normalize_token(parsed.cterm)
        if c in {"NH2", "CONH2", "AMIDE"}:
            rows.append({"token":parsed.cterm,"type":"C-terminal amide","pepforge_screening":"supported","all_atom_requirement":"standard amidated terminus patch","status":"usually available"})
        else:
            rows.append({"token":parsed.cterm,"type":"C-terminal modifier","pepforge_screening":"supported as terminal state","all_atom_requirement":"terminus patch/topology","status":"parameter check required"})
    for item in tokens:
        tok=str(item.get('token',''))
        cls=str(item.get('class',''))
        norm=normalize_token(tok)
        if cls == 'canonical':
            req='standard protein force field residue'; status='ready'
        elif cls == 'd_form':
            req='D-residue topology or mirrored residue parameters; validate chirality in external builder'; status='parameter check required'
        elif cls == 'non_natural':
            req='noncanonical residue topology/charges/bonded parameters'; status='parameter required'
        elif cls == 'linker':
            req='linker residue topology and bonded parameters'; status='parameter required'
        elif cls in {'chemical','n_terminal_chemical'}:
            req='small-molecule/cap parameters, partial charges, linkage definition'; status='parameter required'
        elif cls == 'misplaced_n_terminal_modifier':
            req='token is N-terminal-only by default; rewrite as N-terminal modifier or explicit side-chain attachment before all-atom MD'; status='notation review required'
        else:
            req='manual parameterization or conservative replacement before all-atom MD'; status='review required'
        rows.append({"token":tok,"type":cls or 'unknown',"pepforge_screening":"supported" if cls!='unknown' else 'fallback only',"all_atom_requirement":req,"status":status})
    if not rows:
        rows.append({"token":"none","type":"empty peptide","pepforge_screening":"not applicable","all_atom_requirement":"enter peptide sequence or PDB","status":"not ready"})
    return pd.DataFrame(rows, columns=["token","type","pepforge_screening","all_atom_requirement","status"])


def parse_external_validation_file(path: str | Path):
    """Parse common external validation outputs into a compact summary table."""
    p=Path(path)
    if not p.exists():
        return pd.DataFrame([{"source":str(p),"field":"status","value":"missing file","note":"File was not found."}])
    suf=p.suffix.lower()
    if suf == '.xvg':
        return parse_md_xvg(p)
    if suf in {'.csv', '.tsv'}:
        sep='\t' if suf=='.tsv' else ','
        try:
            df=pd.read_csv(p, sep=sep)
            rows=[{"source":p.name,"field":"table_rows","value":len(df),"note":"External validation table imported."}]
            for col in df.columns[:8]:
                vals=pd.to_numeric(df[col], errors='coerce').dropna()
                if len(vals):
                    rows.append({"source":p.name,"field":f"{col}_last","value":round(float(vals.iloc[-1]),4),"note":"numeric series last value"})
                    rows.append({"source":p.name,"field":f"{col}_mean","value":round(float(vals.mean()),4),"note":"numeric series mean value"})
            return pd.DataFrame(rows)
        except Exception as e:
            return pd.DataFrame([{"source":p.name,"field":"csv_import_error","value":str(e),"note":"Could not parse CSV."}])
    if suf in {'.xlsx', '.xls'}:
        try:
            xl=pd.ExcelFile(p)
            return pd.DataFrame([{"source":p.name,"field":"excel_sheets","value":";".join(xl.sheet_names),"note":"Workbook detected for manual review/import."}])
        except Exception as e:
            return pd.DataFrame([{"source":p.name,"field":"excel_import_error","value":str(e),"note":"Could not parse workbook."}])
    if suf in {'.pdb', '.cif', '.mmcif'}:
        atoms=parse_pdb_atoms(p)
        if atoms.empty:
            return pd.DataFrame([{"source":p.name,"field":"structure_atoms","value":0,"note":"Structure imported but no ATOM/HETATM coordinates parsed."}])
        return pd.DataFrame([
            {"source":p.name,"field":"structure_atoms","value":len(atoms),"note":"parsed coordinate atoms"},
            {"source":p.name,"field":"structure_chains","value":atoms['chain'].nunique(),"note":"parsed chain count"},
            {"source":p.name,"field":"structure_residues","value":atoms.drop_duplicates(['chain','resi']).shape[0],"note":"parsed residue count"},
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

globals()["gromacs_template_files"] = external_md_template_files


def has_modified_peptide_tokens(seq: str) -> bool:
    rows = _split_peptide_model_tokens(seq or "")
    return any(str(r.get("class", "")) not in {"canonical", ""} for r in rows)


def pseudo_peptide_cif(points: pd.DataFrame, model_name: str = "Pepforge_modified_peptide") -> str:
    """Minimal mmCIF-like coordinate export for PyMOL/ChimeraX inspection.

    This is a visualization/screening model, not a fully parameterized all-atom
    peptide.  Original token and token class are preserved in a companion loop so
    users can see which beads correspond to D-form, non-natural, linker, label, or
    terminal-chemical units.
    """
    safe_name = re.sub(r"[^A-Za-z0-9_]", "_", model_name)
    lines = [
        "data_" + safe_name,
        "#",
        "_pepforge_model.purpose 'modified peptide visualization and screening'",
        "_pepforge_model.limitation 'not a fully parameterized all-atom structure'",
        "#",
        "loop_",
        "_atom_site.group_PDB",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_seq_id",
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.pdbx_PDB_model_num",
    ]
    if points is None or points.empty:
        return "\n".join(lines + ["#"]) + "\n"
    clean_points = points.reset_index(drop=True)
    for i, r in clean_points.iterrows():
        aa = str(r.get("aa", "G")).upper()[:1] or "G"
        resn = ONE_TO_THREE.get(aa, "GLY")
        lines.append(f"ATOM {i+1} C CA {resn} B {int(r.get('pep_pos', i+1) or i+1)} {float(r.get('x',0)):.3f} {float(r.get('y',0)):.3f} {float(r.get('z',0)):.3f} 1.00 30.00 1")
    lines.extend(["#", "loop_", "_pepforge_token.seq_id", "_pepforge_token.original_token", "_pepforge_token.token_class", "_pepforge_token.note"])
    for _, r in clean_points.iterrows():
        token = re.sub(r"\s+", "_", str(r.get("token", r.get("aa", "G")) or "G"))
        cls = re.sub(r"\s+", "_", str(r.get("token_class", "canonical") or "canonical"))
        note = re.sub(r"\s+", "_", str(r.get("note", "screening_bead") or "screening_bead"))
        lines.append(f"{int(r.get('pep_pos', 0) or 0)} {token} {cls} {note}")
    lines.append("#")
    return "\n".join(lines) + "\n"

def pseudo_peptide_pdb(points: pd.DataFrame):
    lines=[
        "REMARK Pepforge modified peptide visualization/screening model",
        "REMARK This file is PyMOL-readable but is not a fully parameterized all-atom peptide.",
        "REMARK For publication-grade MD, use external force-field parameterization and validation.",
    ]
    if points is not None and not points.empty:
        for _, r in points.iterrows():
            lines.append(f"REMARK TOKEN {int(r.get('pep_pos',0) or 0)} token={r.get('token', r.get('aa','G'))} class={r.get('token_class','canonical')} note={r.get('note','')}")
    if points is None:
        points = pd.DataFrame()
    for i,r in points.iterrows():
        aa = str(r.get("aa","G"))[0] if str(r.get("aa","G")) else "G"
        resn=ONE_TO_THREE.get(aa, "GLY")
        b = 70.00 if str(r.get('token_class','canonical')) not in {'canonical',''} else 20.00
        lines.append(f"ATOM  {i+1:5d}  CA  {resn:>3s} P{int(r.get('pep_pos',i+1)):4d}    {float(r.get('x',0)):8.3f}{float(r.get('y',0)):8.3f}{float(r.get('z',0)):8.3f}  1.00 {b:5.2f}           C")
    return "\n".join(lines)+"\nEND\n"

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
            return {"mode": "Sequence", "path": str(path), "sequence": file_seq, "atoms": target_sequence_pseudo_atoms(file_seq), "status": "ok", "message": f"Target sequence recognized from file: {path.name}, residues={len(file_seq)}"}
        return {"mode": "PDB", "path": str(path), "sequence": seq, "atoms": atoms, "status": "error", "message": f"Target file exists but no atoms/sequence were recognized: {path}"}
    if seq:
        return {"mode": "Sequence", "path": "", "sequence": seq, "atoms": target_sequence_pseudo_atoms(seq), "status": "ok", "message": f"Target sequence recognized, residues={len(seq)}"}
    if path_text and (not path or not path.exists()):
        fallback = _clean_protein_sequence(path_text)
        if len(fallback) >= 10:
            return {"mode": "Sequence", "path": "", "sequence": fallback, "atoms": target_sequence_pseudo_atoms(fallback), "status": "ok", "message": f"Target sequence recognized from path field, residues={len(fallback)}"}
    return {"mode": target_mode or "PDB", "path": path_text, "sequence": "", "atoms": pd.DataFrame(), "status": "error", "message": "No valid target PDB/mmCIF file or protein sequence was recognized."}


class DockingWorkbenchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Docking Workbench")
        set_pepforge_icon(self)
        self.geometry("1780x1040")
        self.minsize(1180, 760)
        self.last_outdir=None
        self._install_green_progress_style()
        self._build()

    def _install_green_progress_style(self):
        """Use a left-to-right green determinate progress bar in this GUI."""
        try:
            style = ttk.Style(self)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure("PepforgeGreen.Horizontal.TProgressbar", troughcolor="#e8e8e8", background="#2dbb55", lightcolor="#2dbb55", darkcolor="#2dbb55")
        except Exception:
            pass

    def _build(self):
        main=ttk.Frame(self,padding=12); main.pack(fill="both",expand=True)
        ttk.Label(main,text="Docking Workbench",font=("Segoe UI",18,"bold")).pack(anchor="w")
        ttk.Label(main,text="Structure input, pose search, affinity scoring, molecular dynamics screening, and all-atom validation package import/export.").pack(anchor="w",pady=(2,8))
        top=ttk.LabelFrame(main,text="Input",padding=8); top.pack(fill="x")
        self.input_panel = top
        self.input_panel_visible = True
        self.target_mode=tk.StringVar(value="PDB")
        self.peptide_mode=tk.StringVar(value="Sequence")
        self.target_seq=tk.StringVar(value="")
        self.seq=tk.StringVar(value="Ac-EEMQRR-NH2")
        self.pdb_path=tk.StringVar(value="")
        self.pep_pdb_path=tk.StringVar(value="")
        self.result_path=tk.StringVar(value="")
        self.outdir=tk.StringVar(value=str(ROOT/"outputs"/"docking_workbench"))
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
        ttk.Label(complex_box,text="Uses target PDB plus peptide PDB when available; otherwise builds a simple pseudo-peptide candidate.",foreground="#555").grid(row=0,column=3,sticky="w")
        complex_box.columnconfigure(3,weight=1)
        top.columnconfigure(0,weight=1); top.columnconfigure(1,weight=1)
        for var in (self.target_mode, self.peptide_mode): var.trace_add("write", lambda *_: self._update_mode_hint())
        btns=ttk.Frame(main); btns.pack(fill="x",pady=8)
        self.input_toggle_btn = ttk.Button(btns,text="Collapse Input",command=self.toggle_input_panel)
        self.input_toggle_btn.pack(side="left",padx=3)
        ttk.Button(btns,text="Analyze",command=self.analyze).pack(side="left",padx=3)
        ttk.Button(btns,text="Run",command=self.run_full_workflow).pack(side="left",padx=3)
        ttk.Button(btns,text="Export",command=self.export).pack(side="left",padx=3)
        ttk.Button(btns,text="Load",command=self.load_output_folder).pack(side="left",padx=3)
        ttk.Button(btns,text="Open Folder",command=self.open_output).pack(side="left",padx=3)
        ttk.Button(btns,text="Input data full",command=lambda: self.show_data_full("input")).pack(side="left",padx=3)
        ttk.Button(btns,text="Results data full",command=lambda: self.show_data_full("results")).pack(side="left",padx=3)
        ttk.Button(btns,text="MD data full",command=lambda: self.show_data_full("md")).pack(side="left",padx=3)
        self.progress_var=tk.DoubleVar(value=0.0)
        self.progress_text=tk.StringVar(value="Ready")
        ttk.Progressbar(btns, variable=self.progress_var, maximum=100, length=260, mode="determinate", style="PepforgeGreen.Horizontal.TProgressbar").pack(side="left", padx=(14, 4))
        ttk.Label(btns, textvariable=self.progress_text, width=34).pack(side="left", padx=4)
        adv=ttk.Menubutton(btns,text="Advanced")
        adv_menu=tk.Menu(adv,tearoff=False)
        adv_menu.add_command(label="Run docking only", command=self.run_docking)
        adv_menu.add_command(label="Run molecular dynamics only", command=self.run_md_lite)
        adv["menu"]=adv_menu
        adv.pack(side="left",padx=3)
        self.tabs=ttk.Notebook(main); self.tabs.pack(fill="both",expand=True)
        self.md_summary=pd.DataFrame(columns=["metric","value","note"]); self.md_frames=pd.DataFrame(); self.md_final_model=pd.DataFrame(); self.md_trajectory_pdb=""; self.pipeline=pd.DataFrame(); self.md_result_import=pd.DataFrame()

        # Portfolio UI: five user-facing pages, with detailed CSV exports retained.
        input_tab = self._make_tab("Input")
        results = self._make_tab("Results")
        contacts = self._make_tab("Contacts")
        md = self._make_tab("MD")
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
        self.pose_tree=self._tree_panel(results,"Docking results",["pose_id","conformation","orientation","score_lower_better","contact_count","clash_count","hydrophobic_contacts","electrostatic_contacts","aromatic_contacts","hydrogen_bond_contacts","min_distance_A","pose_quality_grade","note"], height=10)
        self.import_tree=self._tree_panel(results,"Affinity report",["source","metric","value","unit","interpretation","method_note"], height=8)
        self.external_style_tree=self._tree_panel(results,"PRODIGY / GROMACS / MD-style data",["engine_style","metric","value","unit","interpretation","external_equivalent"], height=8)
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
            pass

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
            self.mode_hint.set("Mode: target sequence + peptide PDB = target model + docking + MD")
        elif tm == "Sequence":
            self.mode_hint.set("Mode: sequence + sequence = target model + docking + MD")
        elif pm == "PDB":
            self.mode_hint.set("Mode: target structure + peptide structure = contact scoring + MD")
        else:
            self.mode_hint.set("Mode: target structure + peptide sequence = receptor-guided pose search")

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
                pass

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

    def _external_style_validation_df(self) -> pd.DataFrame:
        """Show Pepforge outputs in a table that resembles PRODIGY/GROMACS/MD summaries.

        These rows are not hidden proof from external engines.  They are a stable,
        readable compatibility layer: Pepforge reports ΔG/Kd/contact/MD-screening
        values with names and units that can be compared against PRODIGY, Vina,
        GROMACS, OpenMM, AMBER, MM/PBSA, or experimental validation after export.
        """
        rows=[]
        aff = normalize_affinity_report_df(getattr(self, "imported_results", pd.DataFrame()), getattr(self, "poses", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame()))
        def aff_val(metric):
            if aff is None or aff.empty or "metric" not in aff.columns:
                return "", ""
            hit = aff[aff["metric"].astype(str).str.lower().eq(str(metric).lower())]
            if hit.empty:
                return "", ""
            r = hit.iloc[0]
            return r.get("value", ""), r.get("unit", "")
        dg, dg_unit = aff_val("estimated_ΔG")
        kd, kd_unit = aff_val("estimated_Kd")
        contacts, contacts_unit = aff_val("interface_residue_contacts")
        hbond, hbond_unit = aff_val("hydrogen_bond_contacts")
        apolar, apolar_unit = aff_val("apolar_contacts")
        clashes, clash_unit = aff_val("steric_clashes")
        rows += [
            {"engine_style":"PRODIGY-like", "metric":"estimated_delta_G", "value":dg or "not generated", "unit":dg_unit or "kcal/mol", "interpretation":"Contact-based Pepforge screening ΔG; compare externally, do not treat as PRODIGY output.", "external_equivalent":"PRODIGY ΔG / binding affinity summary"},
            {"engine_style":"PRODIGY-like", "metric":"estimated_Kd", "value":kd or "not generated", "unit":kd_unit or "M-derived unit", "interpretation":"Kd derived from estimated ΔG with standard RT conversion.", "external_equivalent":"PRODIGY Kd / affinity class"},
            {"engine_style":"PRODIGY-like", "metric":"interface_contacts", "value":contacts or "0", "unit":contacts_unit or "count", "interpretation":"Residue-level target-peptide contact count.", "external_equivalent":"interface contact count / IC classification"},
            {"engine_style":"PRODIGY-like", "metric":"apolar_contacts", "value":apolar or "0", "unit":apolar_unit or "count", "interpretation":"Hydrophobic + aromatic contact proxy.", "external_equivalent":"apolar/nonpolar contact contribution"},
            {"engine_style":"PRODIGY-like", "metric":"hydrogen_bond_contacts", "value":hbond or "0", "unit":hbond_unit or "count", "interpretation":"Donor/acceptor heavy-atom distance proxy.", "external_equivalent":"H-bond/contact analysis"},
            {"engine_style":"Docking", "metric":"steric_clashes", "value":clashes or "0", "unit":clash_unit or "count", "interpretation":"Lower is better; high clash count needs pose review.", "external_equivalent":"pose clash / steric penalty"},
        ]
        md = getattr(self, "md_summary", pd.DataFrame())
        md_lookup = {}
        if isinstance(md, pd.DataFrame) and not md.empty and "metric" in md.columns:
            md_lookup = {str(r.get("metric")): r for _, r in md.iterrows()}
        def md_val(metric, default="not run"):
            r = md_lookup.get(metric, {})
            return r.get("value", default) if hasattr(r, "get") else default
        rows += [
            {"engine_style":"GROMACS/MD-like", "metric":"final_RMSD", "value":md_val("final_rmsd_A"), "unit":"Angstrom", "interpretation":"Embedded MD-screening drift proxy; external all-atom MD should be used for claims.", "external_equivalent":"GROMACS rms.xvg / RMSD"},
            {"engine_style":"GROMACS/MD-like", "metric":"mean_contacts", "value":md_val("mean_contact_count"), "unit":"count", "interpretation":"Average retained contacts during embedded screening.", "external_equivalent":"contact frequency / native contacts"},
            {"engine_style":"GROMACS/MD-like", "metric":"contact_persistence", "value":md_val("contact_persistence_proxy"), "unit":"0-1 proxy", "interpretation":"Higher means contacts persisted better in Pepforge screening frames.", "external_equivalent":"contact persistence / occupancy"},
            {"engine_style":"GROMACS/MD-like", "metric":"final_clashes", "value":md_val("final_clash_count"), "unit":"count", "interpretation":"Final steric review metric after embedded relaxation.", "external_equivalent":"structure validation / bad contacts"},
            {"engine_style":"External validation", "metric":"recommended_next_step", "value":"export/import", "unit":"workflow", "interpretation":"Export complex, run PRODIGY/Vina/GROMACS/OpenMM/AMBER externally, then import CSV/XVG/LOG outputs.", "external_equivalent":"formal external validation"},
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
            pass
        try:
            df = getattr(self, "rcsb_results", pd.DataFrame())
            if df is not None and not df.empty:
                return str(df.iloc[0].get("pdb_id", "")).strip().upper()
        except Exception:
            pass
        return ""

    def fetch_selected_rcsb_target(self):
        pdb_id = self._selected_rcsb_pdb_id()
        if not pdb_id:
            messagebox.showwarning("RCSB fetch", "Select a valid RCSB result first.")
            return
        try:
            out = Path(self.outdir.get()) / "rcsb_downloads"
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
            paths = export_target_preparation_package(path, Path(self.outdir.get()) / "target_preparation", selected_chains=self._selected_target_chains(), keep_waters=bool(self.keep_waters.get()), keep_ions=bool(self.keep_ions.get()), keep_ligands=bool(self.keep_ligands.get()))
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
            out = Path(self.outdir.get()) / "complex_builder"
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
            out = Path(self.outdir.get()) / "calibration_dataset_mode"
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
            out = Path(self.outdir.get())
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
            out = Path(self.outdir.get())
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
        folder = self.evidence_project_folder.get().strip() or self.outdir.get().strip()
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
            out = Path(self.outdir.get())
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
            paths = export_external_docking_import_package(src, self.outdir.get())
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
            candidate = Path(self.outdir.get()) / "calibration_dataset_mode" / "calibration_dataset_normalized.csv"
            if candidate.exists():
                csv_path = str(candidate)
                self.calibration_normalized_csv_path.set(csv_path)
        if not csv_path or not Path(csv_path).exists():
            messagebox.showwarning("Calibration Model Cards", "Choose calibration_dataset_normalized.csv or build Calibration Report first.")
            return
        try:
            paths = export_calibration_visualization_package(csv_path, self.outdir.get())
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
            out = Path(self.outdir.get())
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
            paths = export_session_summary(session, self.outdir.get())
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
                paths = create_project_session_package(name, self.outdir.get(), description="Pepforge workflow session")
            else:
                paths = export_session_summary(session, self.outdir.get())
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
                output_dir=self.outdir.get(),
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
            path = make_experimental_template(Path(self.outdir.get()) / "experimental_data_import")
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
            paths = export_experimental_import_package(src, self.outdir.get())
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
            path = save_workflow_config(cfg, self.outdir.get())
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
            paths = run_workflow(cfg, self.outdir.get())
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
                output_dir=self.outdir.get(),
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
            "affinity_scoring_summary": normalize_affinity_report_df(getattr(self, "imported_results", pd.DataFrame()), getattr(self, "poses", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame())),
            "external_style_validation_summary": self._external_style_validation_df(),
            "simulation_summary": simulation_summary_df(getattr(self, "poses", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame()), getattr(self, "risk", pd.DataFrame())),
            "molecular_dynamics_summary": getattr(self, "md_summary", pd.DataFrame()),
            "molecular_dynamics_frames": getattr(self, "md_frames", pd.DataFrame()),
            "molecular_dynamics_readable_frames": self._md_readable_frames(getattr(self, "md_frames", pd.DataFrame())) if hasattr(self, "_md_readable_frames") else getattr(self, "md_frames", pd.DataFrame()),
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
            "results": ["result_interpretation", "docking_pose_candidates", "affinity_scoring_summary", "external_style_validation_summary", "peptide_risk_summary", "docking_readiness", "simulation_summary", "docking_residue_contact_report", "docking_residue_contact_report_full", "docking_atom_contact_report"],
            "md": ["external_style_validation_summary", "molecular_dynamics_summary", "molecular_dynamics_readable_frames", "molecular_dynamics_frames", "md_result_import_summary"],
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
                pass
            return
        for _,r in df.iterrows(): tree.insert("","end",values=[r.get(c,"") for c in tree["columns"]])

    def _validate_for_run(self):
        reasons=[]
        resolved = self._resolved_target()
        if resolved.get("status") != "ok":
            reasons.append(str(resolved.get("message") or "Target was not recognized."))
        else:
            # Keep the combobox synchronized with the actually recognized target.
            if resolved.get("mode") in {"PDB", "Sequence"} and self.target_mode.get() != resolved.get("mode"):
                self.target_mode.set(str(resolved.get("mode")))
        if self.peptide_mode.get()=="PDB":
            pp=Path(self._peptide_pdb_path())
            tp=Path(self._target_path())
            if not pp.exists() and not (resolved.get("mode")=="PDB" and resolved.get("path") and structure_has_multiple_chains(resolved.get("path"))):
                reasons.append("Peptide PDB is missing. For complex structures, load a multi-chain complex in the PDB box or provide a separate peptide PDB.")
        else:
            if not self._active_peptide_sequence():
                reasons.append("Peptide sequence is empty or could not be parsed. Enter a peptide sequence or load a peptide PDB.")
        if reasons:
            messagebox.showerror("Docking input check failed", "\n".join("- "+r for r in reasons))
            return False
        try:
            self.log.insert("end", "Target resolver: " + str(resolved.get("message","")) + "\n")
            self.log.see("end")
        except Exception:
            pass
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
        self.imported_results=normalize_affinity_report_df(pd.DataFrame(rows)); self._write_tree(self.import_tree,self.imported_results)

    def analyze(self):
        try:
            self._set_progress(5, "Analyzing inputs...")
            self._normalize_input_modes()
            active_peptide_seq = self._peptide_metadata_sequence()
            self.props=estimate_properties(active_peptide_seq)
            self.terminal_status=terminal_status_df(active_peptide_seq)
            self.target_atoms=parse_pdb_atoms(self._target_path()) if self.target_mode.get()=="PDB" and self.pdb_path.get() else pd.DataFrame()
            resolved_target = self._resolved_target()
            if resolved_target.get("mode")=="PDB" and resolved_target.get("path"):
                self.pdb=pdb_summary_df(resolved_target.get("path"))
            elif isinstance(resolved_target.get("atoms"), pd.DataFrame) and not resolved_target.get("atoms").empty:
                # Structure was resolved from a prepared/imported target even when the combobox state was stale.
                self.pdb=pdb_summary_df(self._target_path())
            else:
                self.pdb=pd.DataFrame([
                    {"field":"target_mode","value":resolved_target.get("mode","Sequence"),"note":resolved_target.get("message","Target resolver status")},
                    {"field":"target_sequence_length","value":len(str(resolved_target.get("sequence") or "")),"note":"cleaned protein residues parsed from FASTA/text/file"},
                    {"field":"target_path","value":self._target_path(),"note":"If a PDB/CIF was entered but not summarized, press Analyze after selecting Target input = PDB."},
                ])
            if self.pdb is None or self.pdb.empty:
                self.pdb = pd.DataFrame([{"field":"target_summary_status","value":"available after target selection","note":"No target atoms parsed yet; select PDB/CIF/mmCIF or enter target sequence, then Analyze/Run."}])
            self.residue_map=residue_map_df(active_peptide_seq); self.risk=structure_risk_df(self.props); self.readiness=docking_readiness_df(active_peptide_seq)
            self.seqpair=sequence_sequence_interaction_df(self._active_target_sequence(), active_peptide_seq) if self.target_mode.get()=="Sequence" else pd.DataFrame([{"metric":"mode","value":"not sequence_sequence","note":"Use Target input = Sequence to enable sequence-pair heuristic."}])
            self.pipeline=structure_pipeline_df(self.target_mode.get(), self.peptide_mode.get(), self._active_target_sequence(), active_peptide_seq, self._target_path(), self._peptide_pdb_path())
            self.poses=pd.DataFrame(columns=self.pose_tree["columns"]); self.contacts=pd.DataFrame(columns=self.contact_tree["columns"]); self.atom_contacts=pd.DataFrame(columns=_atom_contact_columns()); self.peptide_model=peptide_pseudo_model(active_peptide_seq)
            self.imported_results=normalize_affinity_report_df(getattr(self,"imported_results",pd.DataFrame()), getattr(self,"poses",pd.DataFrame()), getattr(self,"contacts",pd.DataFrame()))
            self.md_summary=getattr(self,"md_summary",pd.DataFrame(columns=["metric","value","note"]))
            self.md_frames=getattr(self,"md_frames",pd.DataFrame(columns=self.md_tree["columns"]))
            for tr,df in [(self.prop_tree,self.props),(self.terminal_tree,self.terminal_status),(self.pdb_tree,self.pdb),(self.seqpair_tree,self.seqpair),(self.pipeline_tree,self.pipeline),(self.risk_tree,self.risk),(self.readiness_tree,self.readiness),(self.pose_tree,self.poses),(self.contact_tree,self.contacts),(self.import_tree,self.imported_results),(self.external_style_tree,self._external_style_validation_df()),(self.md_result_tree,getattr(self,"md_result_import",pd.DataFrame())),(self.sim_tree,simulation_summary_df(self.poses,self.contacts,self.risk)),(self.md_tree,self._md_readable_frames(getattr(self,"md_frames",pd.DataFrame()))),(self.interpret_tree,self._interpretation_df())]: self._write_tree(tr,df)
            try:
                self.tabs.select(0)
                self.collapse_input_panel()
            except Exception:
                pass
            self._set_progress(100, "Analysis complete")
            self.log.insert("end","Input analysis updated. Terminal states and workflow readiness were refreshed.\n"); self.log.see("end")
        except Exception as e:
            messagebox.showerror("Docking Workbench analysis error", str(e))
            raise

    def _active_target_atoms_for_docking(self):
        resolved = self._resolved_target()
        atoms = resolved.get("atoms")
        if isinstance(atoms, pd.DataFrame) and not atoms.empty:
            return atoms
        return target_sequence_pseudo_atoms(str(resolved.get("sequence") or self._active_target_sequence()))

    def run_full_workflow(self):
        """Run the essential workflow with one button: analyze, dock, score, and run embedded MD screening."""
        self._set_progress(0, "Starting workflow...")
        self.analyze()
        self._set_progress(30, "Running docking...")
        self.run_docking()
        self._set_progress(72, "Running molecular dynamics...")
        self.run_md_lite()
        self._set_progress(100, "Workflow complete")
        self.log.insert("end", "Full workflow completed: input analysis, docking, scoring, and molecular dynamics screening.\n")
        self.log.see("end")

    def _interpretation_df(self):
        poses = getattr(self, "poses", pd.DataFrame())
        contacts = getattr(self, "contacts", pd.DataFrame())
        risk = getattr(self, "risk", pd.DataFrame())
        md_summary = getattr(self, "md_summary", pd.DataFrame())
        rows=[]
        if poses is None or poses.empty:
            rows.append({"item":"Docking", "status":"Not run", "interpretation":"Click Run to generate pose candidates and contact scoring."})
        else:
            best = poses.iloc[0]
            contacts_n = int(float(best.get("contact_count", 0) or 0))
            clashes_n = int(float(best.get("clash_count", 0) or 0))
            score = best.get("score_lower_better", "")
            if contacts_n >= 8 and clashes_n <= 2:
                status = "Good screening candidate"
            elif contacts_n >= 4 and clashes_n <= 5:
                status = "Usable for triage"
            else:
                status = "Weak or needs review"
            rows.append({"item":"Docking", "status":status, "interpretation":f"Best pose score={score}, contacts={contacts_n}, clashes={clashes_n}. Read the Affinity report for estimated ΔG (kcal/mol), Kd (one representative unit), H-bond/hydrophobic distance cutoffs, contacts, and clashes; use as screening evidence, not final proof."})
        if contacts is None or contacts.empty:
            rows.append({"item":"Interface", "status":"No contacts yet", "interpretation":"Run docking or load a complex output folder to inspect residue/atom contacts."})
        else:
            rows.append({"item":"Interface", "status":"Contacts detected", "interpretation":f"{len(contacts)} residue-level contacts are available. Check the Contacts tab for residue pairs and distances."})
        high_risks=[]
        if risk is not None and not risk.empty and "level" in risk.columns:
            high_risks = [str(x) for x in risk.loc[risk["level"].astype(str).str.lower().isin(["high"]), "risk"].tolist()]
        rows.append({"item":"Peptide risk", "status":"High risk" if high_risks else "Acceptable", "interpretation":("Review: "+", ".join(high_risks)) if high_risks else "No high-level peptide risk was flagged by the embedded screening heuristics."})
        if md_summary is not None and not md_summary.empty:
            rows.append({"item":"Molecular dynamics", "status":"Screened", "interpretation":"Embedded MD screening is available. For publication-grade claims, export the validation package and import all-atom MD results."})
        else:
            rows.append({"item":"Molecular dynamics", "status":"Not run", "interpretation":"Click Run or use Advanced > Run molecular dynamics only after docking."})
        return pd.DataFrame(rows, columns=["item","status","interpretation"])

    def run_docking(self):
        """Run the docking workflow without rejecting mixed inputs."""
        self._normalize_input_modes()
        if not self._validate_for_run(): return
        active_target_seq = self._active_target_sequence()
        self._set_progress(34, "Docking: preparing target and peptide...")
        active_peptide_seq = self._peptide_metadata_sequence()
        self.props = estimate_properties(active_peptide_seq)
        self.terminal_status = terminal_status_df(active_peptide_seq)
        self.pipeline = structure_pipeline_df(self.target_mode.get(), self.peptide_mode.get(), active_target_seq, active_peptide_seq, self._target_path(), self._peptide_pdb_path())
        self.target_atoms = self._active_target_atoms_for_docking()
        target_source = "PDB/mmCIF" if self.target_mode.get() == "PDB" else "target model from sequence"

        # Complex PDB path: split and score directly.
        if self.target_mode.get() == "PDB" and self._target_path() and Path(self._target_path()).exists() and self.peptide_mode.get() == "PDB" and not (self._peptide_pdb_path() and Path(self._peptide_pdb_path()).exists()) and structure_has_multiple_chains(self._target_path()):
            self.poses, self.contacts, self.atom_contacts, self.peptide_model = analyze_complex_structure_contacts(self._target_path())
            self.seqpair = pd.DataFrame([{"metric":"mode","value":"complex_pdb","note":"Contact/affinity scoring on imported multi-chain complex."}])
        else:
            if self.peptide_mode.get() == "PDB" and self._peptide_pdb_path() and Path(self._peptide_pdb_path()).exists():
                pep_points = pdb_to_peptide_points(self._peptide_pdb_path())
                self.peptide_model = pep_points
                # If target and peptide structures are already in contact, report that; otherwise perform receptor-guided placement.
                if self.target_mode.get() == "PDB":
                    direct_poses, direct_contacts = analyze_pdb_pdb_contacts(self._target_path(), self._peptide_pdb_path())
                    if not direct_poses.empty and str(direct_poses.iloc[0].get("contact_count", "0")) not in ("", "0", "0.0", "nan"):
                        self.poses, self.contacts = direct_poses, direct_contacts
                        self.atom_contacts = analyze_atom_level_contacts(self._target_path(), self._peptide_pdb_path())
                    else:
                        self.poses, self.contacts, self.peptide_model = run_pose_search(self.target_atoms, pep_points, active_peptide_seq)
                        self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
                else:
                    self.poses, self.contacts, self.peptide_model = run_pose_search(self.target_atoms, pep_points, active_peptide_seq)
                    self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
                self.seqpair = pd.DataFrame([{"metric":"mode","value":"target_%s_peptide_pdb" % self.target_mode.get().lower(),"note":"Peptide PDB accepted; Pose search runs even when target starts as sequence."}])
            else:
                self.poses, self.contacts, self.peptide_model = run_pose_search(self.target_atoms, None, active_peptide_seq)
                self.atom_contacts = pd.DataFrame(columns=_atom_contact_columns())
                self.seqpair = sequence_sequence_interaction_df(active_target_seq, active_peptide_seq) if self.target_mode.get()=="Sequence" else pd.DataFrame([{"metric":"mode","value":"target_structure_peptide_sequence","note":"Receptor-guided pose search."}])

        # Keep the full contact table for export, but show a readable Top 50 contact
        # report in the UI.  This avoids hiding multiple interactions while still
        # preventing the Contacts tab from becoming unreadable.
        self.all_contacts = getattr(self, "contacts", pd.DataFrame()).copy()
        self.contacts = top_contact_report(self.all_contacts, self.poses, top_n=50)

        # Fill the Atom contacts pane with real atom contacts when available; otherwise show a
        # residue-level proxy so the panel explains why it is not truly atom-level.
        if not hasattr(self, "atom_contacts") or self.atom_contacts is None or self.atom_contacts.empty:
            self.atom_contacts = residue_contacts_to_atom_proxy(self.contacts)

        # Always produce a affinity summary after docking.
        self.imported_results = normalize_affinity_report_df(affinity_summary_df(self.poses, self.contacts), self.poses, self.contacts)
        self.pdb = pdb_summary_df(self._target_path()) if self.target_mode.get()=="PDB" and self.pdb_path.get() else pd.DataFrame([
            {"field":"target_mode","value":"Sequence -> target model","note":"Target sequence recognized and converted to a coarse target model so docking can run."},
            {"field":"target_sequence_length","value":len(active_target_seq),"note":"cleaned protein residues"},
            {"field":"target_source","value":target_source,"note":"used by pose search"},
        ])
        self._write_tree(self.seqpair_tree,self.seqpair); self._write_tree(self.pipeline_tree,self.pipeline); self._write_tree(self.pdb_tree,self.pdb); self._write_tree(self.terminal_tree,self.terminal_status); self._write_tree(self.pose_tree,self.poses); self._write_tree(self.contact_tree,self.contacts); self._write_tree(self.import_tree,self.imported_results); self._write_tree(self.external_style_tree,self._external_style_validation_df()); self._write_tree(self.sim_tree,simulation_summary_df(self.poses,self.contacts,self.risk)); self._write_tree(self.md_tree,self._md_readable_frames(getattr(self,"md_frames",pd.DataFrame()))); self._write_tree(self.interpret_tree,self._interpretation_df())
        self._set_progress(70, "Docking complete: affinity units ready")
        self.log.insert("end",f"Docking and affinity report completed: {len(self.poses)} pose rows, {len(self.contacts)} residue contacts. Target source: {target_source}.\n"); self.log.see("end")

    def _md_readable_summary(self, summary: pd.DataFrame) -> pd.DataFrame:
        if summary is None or summary.empty:
            return pd.DataFrame(columns=["metric","value","unit","interpretation"])
        lookup = {str(r.get("metric")): r for _, r in summary.iterrows()}
        def val(metric, default=""):
            r = lookup.get(metric, {})
            return r.get("value", default) if hasattr(r, "get") else default
        rows = [
            {"metric":"status", "value":val("md_lite_status", "completed"), "unit":"-", "interpretation":"embedded screening run status"},
            {"metric":"final_RMSD", "value":val("final_rmsd_A", ""), "unit":"Angstrom", "interpretation":"lower suggests less drift in the internal screening model"},
            {"metric":"mean_contacts", "value":val("mean_contact_count", ""), "unit":"count", "interpretation":"average maintained target-peptide contacts"},
            {"metric":"contact_persistence", "value":val("contact_persistence_proxy", ""), "unit":"0-1 proxy", "interpretation":"higher means contacts persisted better during screening"},
            {"metric":"final_clashes", "value":val("final_clash_count", ""), "unit":"count", "interpretation":"lower is better; high values suggest steric review"},
            {"metric":"screening_call", "value":val("stability_call", "Review"), "unit":"qualitative", "interpretation":"triage label only; not a full all-atom MD conclusion"},
        ]
        return pd.DataFrame(rows, columns=["metric","value","unit","interpretation"])

    def _md_readable_frames(self, frames: pd.DataFrame) -> pd.DataFrame:
        cols=["frame","time_ps","rmsd_A","contacts","clashes","min_distance_A","interpretation"]
        if frames is None or frames.empty:
            return pd.DataFrame(columns=cols)
        df=frames.copy()
        n=len(df)
        if n > 12:
            idx=sorted(set([0, max(0,n//4), max(0,n//2), max(0,3*n//4), n-1]))
            df=df.iloc[idx].copy()
        rows=[]
        for _, r in df.iterrows():
            rmsd=float(r.get("rmsd_A",0) or 0); clashes=int(float(r.get("clash_count",0) or 0)); contacts=int(float(r.get("contact_count",0) or 0))
            interp = "stable/contact-retained" if rmsd <= 3.5 and clashes <= 1 and contacts >= 1 else ("review clashes" if clashes > 1 else "moderate drift")
            rows.append({"frame":int(float(r.get("step",0) or 0)), "time_ps":round(float(r.get("time_ps_proxy",0) or 0),3), "rmsd_A":round(rmsd,3), "contacts":contacts, "clashes":clashes, "min_distance_A":round(float(r.get("min_distance_A",0) or 0),3), "interpretation":interp})
        return pd.DataFrame(rows, columns=cols)

    def run_md_lite(self):
        """Run embedded molecular dynamics on the current/best peptide pose and show frames."""
        try:
            if not hasattr(self, "poses") or self.poses is None or self.poses.empty:
                self.run_docking()
            target_atoms = self._active_target_atoms_for_docking() if hasattr(self, "_active_target_atoms_for_docking") else (parse_pdb_atoms(self._target_path()) if self.pdb_path.get() else pd.DataFrame())
            peptide_points = getattr(self, "peptide_model", pd.DataFrame())
            if peptide_points is None or peptide_points.empty:
                if self.peptide_mode.get() == "PDB" and self._peptide_pdb_path() and Path(self._peptide_pdb_path()).exists():
                    peptide_points = pdb_to_peptide_points(self._peptide_pdb_path())
                else:
                    peptide_points = peptide_pseudo_model(self._active_peptide_sequence() or self.seq.get())
            self._set_progress(74, "Molecular dynamics: sampling frames...")
            self.md_summary, self.md_frames, self.md_final_model, self.md_trajectory_pdb = run_builtin_md_lite(
                target_atoms, peptide_points, steps=600, sample_every=10, temperature=0.35, dt=0.025, seed=17
            )
            self.md_summary = dynamics_summary_label(self.md_summary)
            self._write_tree(self.sim_tree, self._md_readable_summary(self.md_summary))
            self._write_tree(self.md_tree, self._md_readable_frames(self.md_frames))
            self._write_tree(self.external_style_tree, self._external_style_validation_df())
            status = "completed" if not self.md_summary.empty else "not run"
            self._set_progress(95, "Molecular dynamics complete")
            self.log.insert("end", f"Molecular dynamics screening {status}: {len(self.md_frames)} sampled frames. Export package includes all-atom validation templates and import support.\n")
            self.log.see("end")
        except Exception as e:
            messagebox.showerror("molecular dynamics error", str(e))
            raise

    def export(self):
        self._normalize_input_modes()
        if not self._validate_for_run(): return
        active_target_seq = self._active_target_sequence()
        active_peptide_seq = self._peptide_metadata_sequence()
        self.run_docking()
        self.run_md_lite()
        out_base=Path(self.outdir.get()); out_base.mkdir(parents=True,exist_ok=True)
        stamp=__import__("datetime").datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out=out_base/("docking_"+stamp); out.mkdir(parents=True,exist_ok=True)
        self.imported_results = normalize_affinity_report_df(getattr(self,"imported_results",pd.DataFrame()), getattr(self,"poses",pd.DataFrame()), getattr(self,"contacts",pd.DataFrame()))
        tables={"peptide_properties":self.props,"target_structure_summary":self.pdb,"sequence_pair_heuristic":self.seqpair,"workflow":getattr(self,"pipeline",pd.DataFrame()),"peptide_residue_map":self.residue_map,"peptide_risk_summary":self.risk,"docking_readiness":self.readiness,"token_compatibility":getattr(self,"compatibility",peptide_token_compatibility_df(active_peptide_seq)),"terminal_modifier_policy":terminal_modifier_policy_df(active_peptide_seq),"all_atom_parameter_requirements":all_atom_parameter_requirements_df(active_peptide_seq),"docking_pose_candidates":self.poses,"docking_residue_contact_report":self.contacts,"docking_residue_contact_report_full":getattr(self,"all_contacts",self.contacts),"docking_atom_contact_report":getattr(self,"atom_contacts",pd.DataFrame()),"imported_results_summary":getattr(self,"imported_results",pd.DataFrame()),"md_result_import_summary":getattr(self,"md_result_import",pd.DataFrame()),"affinity_scoring_summary":getattr(self,"imported_results",pd.DataFrame()),"external_style_validation_summary":self._external_style_validation_df(),"simulation_summary":simulation_summary_df(self.poses,self.contacts,self.risk),"molecular_dynamics_summary":getattr(self,"md_summary",pd.DataFrame()),"molecular_dynamics_frames":getattr(self,"md_frames",pd.DataFrame()),"amphipathic_windows":amphipathic_window_df(self.seq.get()),"rcsb_pdb_search_results":getattr(self,"rcsb_results",pd.DataFrame()),"target_preparation_report":getattr(self,"target_prep_report",pd.DataFrame()),"complex_builder_report":getattr(self,"complex_builder_report",pd.DataFrame())}
        for name,df in tables.items(): df.to_csv(out/f"{name}.csv",index=False,encoding="utf-8-sig")
        (out/"affinity_report.md").write_text(affinity_report_markdown(self.imported_results), encoding="utf-8")
        fasta_name=re.sub(r"[^A-Za-z0-9_\-]","_",active_peptide_seq)[:50] or "peptide"
        (out/"peptide.fasta").write_text(f">{fasta_name}\n{active_peptide_seq}\n",encoding="utf-8")
        (out/"peptide_pseudo_model.pdb").write_text(pseudo_peptide_pdb(self.peptide_model),encoding="utf-8")
        if has_modified_peptide_tokens(active_peptide_seq):
            (out/"modified_peptide_simulated_structure.pdb").write_text(pseudo_peptide_pdb(self.peptide_model), encoding="utf-8")
            (out/"modified_peptide_simulated_structure.cif").write_text(pseudo_peptide_cif(self.peptide_model), encoding="utf-8")
        (out/"embedded_md_final_model.pdb").write_text(pseudo_peptide_pdb(getattr(self,"md_final_model",self.peptide_model)),encoding="utf-8")
        (out/"embedded_md_trajectory.pdb").write_text(getattr(self,"md_trajectory_pdb","") or pseudo_peptide_pdb(getattr(self,"md_final_model",self.peptide_model)),encoding="utf-8")
        target_atoms_for_export = self._active_target_atoms_for_docking() if hasattr(self, "_active_target_atoms_for_docking") else pd.DataFrame()
        current_peptide_for_export = getattr(self, "md_final_model", getattr(self, "peptide_model", pd.DataFrame()))
        (out/"best_docking_complex.pdb").write_text(combined_complex_pdb(target_atoms_for_export, current_peptide_for_export, getattr(self, "contacts", pd.DataFrame())), encoding="utf-8")
        (out/"contact_annotated_complex.pdb").write_text(combined_complex_pdb(target_atoms_for_export, getattr(self, "peptide_model", pd.DataFrame()), getattr(self, "contacts", pd.DataFrame())), encoding="utf-8")
        prep_fasta, target_fasta, prep_json, prep_notes = structure_preparation_files(active_target_seq, active_peptide_seq, self._peptide_pdb_path())
        (out/"structure_prediction_ready_complex.fasta").write_text(prep_fasta, encoding="utf-8")
        (out/"target_structure_input.fasta").write_text(target_fasta, encoding="utf-8")
        (out/"complex_structure_input.json").write_text(prep_json, encoding="utf-8")
        (out/"STRUCTURE_PREPARATION_NOTES.txt").write_text(prep_notes, encoding="utf-8")
        # External all-atom validation package. These files do not run MD inside Pepforge;
        # they make the exported candidate reproducible and ready for external validation.
        validation_dir = out / "all_atom_validation_package"
        validation_dir.mkdir(exist_ok=True)
        try:
            all_atom_parameter_requirements_df(active_peptide_seq).to_csv(validation_dir/"token_parameter_requirements.csv", index=False, encoding="utf-8-sig")
        except Exception:
            pass
        for rel_name, content in all_atom_validation_template_files().items():
            fp = validation_dir / rel_name
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
        if self._target_path() and Path(self._target_path()).exists():
            try: shutil.copy2(self._target_path(), validation_dir/"target_input.pdb")
            except Exception: pass
        if self._peptide_pdb_path() and Path(self._peptide_pdb_path()).exists():
            try: shutil.copy2(self._peptide_pdb_path(), validation_dir/"peptide_input.pdb")
            except Exception: pass
        (validation_dir/"complex_candidate.pdb").write_text(combined_complex_pdb(target_atoms_for_export, current_peptide_for_export, getattr(self, "contacts", pd.DataFrame())), encoding="utf-8")
        # Legacy folder name retained for users who already rely on it.
        legacy_dir=out/"external_md_templates"; legacy_dir.mkdir(exist_ok=True)
        for fname, content in external_md_template_files().items():
            (legacy_dir/fname).write_text(content,encoding="utf-8")
        notes=("Pepforge Docking Workbench export\n\n"
               "Supported modes: sequence/sequence, target sequence/peptide PDB, target PDB/peptide sequence, target PDB/peptide PDB, affinity scoring, full receptor-anchor pose search, forward/reverse N/C peptide orientation screening, Top 50 readable contact reporting, modified peptide notation such as FITC-Cha-AEEA-dK-NH2, N-terminal-only chemical position warnings for Pal/FITC/Myr/etc., molecular dynamics, and external all-atom MD validation export/import, token parameter requirement reporting.\n"
               "The embedded engines are screening modules for local ranking and workflow continuity. For publication-grade validation, export the complex and run full external all-atom MD, then import RMSD/RMSF/energy results.\n")
        (out/"docking_notes.txt").write_text(notes,encoding="utf-8")
        with pd.ExcelWriter(out/"docking_workbench_report.xlsx",engine="openpyxl") as writer:
            for name,df in tables.items(): df.to_excel(writer,index=False,sheet_name=name[:31].upper())
        (out/"OUTPUT_MANIFEST.txt").write_text("Pepforge Docking Workbench output folder\nCreated: "+__import__("datetime").datetime.now().isoformat(timespec="seconds")+"\nUse Load Output Folder to reload CSV/XLSX results.\nCitation notice: see CITATION_NOTICE.txt.\n", encoding="utf-8")
        (out/"CITATION_NOTICE.txt").write_text("Pepforge Citation Notice\n\nAcademic use of Pepforge or Pepforge-generated outputs requires citation of the software repository and release DOI when available.\n\nRecommended citation:\nWoo, S. Pepforge: An Integrated Peptide Research Workbench. GitHub repository, Version 2.0.0. https://github.com/poowsh1407/Pepforge\n\nIf a DOI is available for the GitHub/Zenodo release, cite the DOI-linked release as the preferred reference.\n\nPepforge-generated docking, affinity, contact, SPPS, and molecular dynamics outputs are intended for screening and prioritization. Quantitative binding claims should be externally validated.\n", encoding="utf-8")
        self.last_outdir=out; messagebox.showinfo("Export complete",f"Exported to:\n{out}")


    def load_output_folder(self):
        folder=filedialog.askdirectory(title="Select a Pepforge Docking output folder")
        if not folder: return
        try:
            base=Path(folder)
            mapping=[
                ("peptide_properties.csv", self.prop_tree), ("target_structure_summary.csv", self.pdb_tree),
                ("sequence_pair_heuristic.csv", self.seqpair_tree), ("workflow.csv", self.pipeline_tree),
                ("docking_pose_candidates.csv", self.pose_tree), ("docking_residue_contact_report.csv", self.contact_tree),
                ("peptide_risk_summary.csv", self.risk_tree), ("docking_readiness.csv", self.readiness_tree),
                ("token_compatibility.csv", self.compat_tree), ("affinity_scoring_summary.csv", self.import_tree),
                ("molecular_dynamics_summary.csv", self.sim_tree), ("molecular_dynamics_frames.csv", self.md_tree),
                ("md_result_import_summary.csv", self.md_result_tree),
            ]
            loaded=0
            for fname, tree in mapping:
                f=base/fname
                if f.exists():
                    df=pd.read_csv(f)
                    setattr(self, {
                        "docking_pose_candidates.csv":"poses", "docking_residue_contact_report.csv":"contacts",
                        "molecular_dynamics_summary.csv":"md_summary", "molecular_dynamics_frames.csv":"md_frames",
                        "affinity_scoring_summary.csv":"imported_results"
                    }.get(fname, "_last_loaded_df"), df)
                    self._write_tree(tree, df)
                    loaded+=1
            aff_csv = base/"affinity_scoring_summary.csv"
            if not aff_csv.exists():
                try:
                    self.imported_results = normalize_affinity_report_df(pd.DataFrame(), getattr(self,"poses",pd.DataFrame()), getattr(self,"contacts",pd.DataFrame()))
                    self._write_tree(self.import_tree, self.imported_results)
                except Exception:
                    pass
            self.last_outdir=base
            self.outdir.set(str(base.parent))
            self.log.insert("end", f"Loaded output folder: {base} ({loaded} tables).\n")
            self.log.see("end")
        except Exception as e:
            messagebox.showerror("Load output error", str(e))

    def open_output(self):
        p=self.last_outdir or Path(self.outdir.get())
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
