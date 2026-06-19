"""Unified peptide token registry and notation parser for Pepforge V4.

This module centralizes terminal modifiers, linker-only tokens, amino-acid-like
tokens, and C-terminal markers so Hot Spot Finder, Peptide Design Engine,
Structure Assist, and SPPS Planner can share one interpretation layer.

The parser is conservative by design:
- Ac-EEMQRR-NH2 -> nterm=Ac, core=EEMQRR, cterm=NH2
- AcEEMQRR-NH2  -> nterm=Ac, core=EEMQRR, cterm=NH2
- ACDE-NH2      -> nterm="", core=ACDE, cterm=NH2
- PALE-NH2      -> nterm="", core=PALE, cterm=NH2
- PEG4-EEMQRR-NH2 -> PEG4 is a linker-only prefix, not P/E/G residues
- bAla-EEMQRR-NH2 -> bAla is mapped to A as an amino-acid-like surrogate
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import List, Dict

AA = set("ACDEFGHIKLMNPQRSTVWY")

NTERM_MODIFIERS = {
    "AC": "Ac", "BIOTIN": "Biotin", "FITC": "FITC", "FAM": "FAM",
    "TAMRA": "TAMRA", "CY3": "CY3", "CY5": "CY5", "CY7": "CY7",
    "PAL": "Pal", "PALMITICACID": "Pal", "PALMITOYL": "Pal",
    "MYR": "Myr", "MYRISTICACID": "Myr", "MYRISTOYL": "Myr",
    "GAL": "Gal", "GALLICACID": "Gal", "GALLOYL": "Gal",
    "CAF": "Caf", "CAFFEICACID": "Caf", "CAFFEOYL": "Caf",
    "NIC": "Nic", "NICOTINICACID": "Nic", "NICOTINOYL": "Nic",
    "DOTA": "DOTA", "NOTA": "NOTA",
    "ROX": "ROX", "NBD": "NBD", "DANSYL": "Dansyl", "BODIPY": "BODIPY",
}

CTERM_MARKERS = {
    "NH2": "NH2", "CONH2": "CONH2", "AMIDE": "NH2",
    "COOH": "COOH", "CO2H": "COOH", "OH": "OH", "ACID": "COOH",
}

AA_LIKE_TOKEN_MAP = {
    "BALA": "A", "BALA": "A", "GALA": "G", "GALA": "G",
    "SAR": "G", "ORN": "K", "DAB": "K", "DAP": "K", "CIT": "R",
    "HYL": "K", "HYP": "P", "NLE": "L", "NVA": "V", "ABU": "A",
    "AIB": "A", "CHA": "L", "CHG": "V", "TIC": "F", "NAL": "F",
    "BIP": "F", "PHE4F": "F", "PHE4CL": "F", "PHE4ME": "F",
    "TYRME": "Y", "HARG": "R", "HLYS": "K", "MEALA": "A",
    "MEGLY": "G", "MELEU": "L", "MEPHE": "F", "MEVAL": "V",
    "SEC": "C", "PEN": "C", "PRA": "K",
}

LINKER_ONLY_TOKENS = {
    "PEG1", "PEG2", "PEG3", "PEG4", "PEG6", "PEG8", "PEG12", "PEG24",
    "AEEA", "AHX", "G4S", "G4SX2", "SMCC", "SULFOSMCC", "DSS",
    "TRIAZOLE", "CLICK", "HYDRAZONE", "OXIME", "EDC",
}

AA_LINKER_EXPANSIONS = {"GG": "GG", "GGG": "GGG", "GS": "GS", "GSG": "GSG", "G4S": "GGGGS"}

@dataclass
class PeptideTokenParse:
    raw: str
    nterm: str = ""
    cterm: str = ""
    core_sequence: str = ""
    core_tokens: List[str] = field(default_factory=list)
    linker_tokens: List[str] = field(default_factory=list)
    modifier_tokens: List[str] = field(default_factory=list)
    aa_like_tokens: List[str] = field(default_factory=list)
    unknown_tokens: List[str] = field(default_factory=list)

def normalize_token(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(token or "")).upper()

def split_notation(seq: str) -> List[str]:
    s = str(seq or "").strip().replace(" ", "")
    if not s:
        return []
    if re.search(r"[,;/\n\t ]", s):
        return [p.strip().strip("[]") for p in re.split(r"\s*(?:,|;|/|\n|\t| )\s*", s) if p.strip()]
    # Keep dash-separated modifier notation.
    return [p for p in s.split("-") if p]

def _strip_cterm(raw: str) -> tuple[str, str]:
    s = raw
    # CONH2 before NH2.
    for marker in ("CONH2", "NH2", "AMIDE", "COOH", "CO2H", "ACID", "OH"):
        pat = re.compile(r"(?i)-?" + re.escape(marker) + r"$")
        if pat.search(s):
            return pat.sub("", s), CTERM_MARKERS.get(marker.upper(), marker.upper())
    return s, ""

def token_to_surrogate(token: str) -> str:
    t = str(token or "").strip()
    if not t:
        return ""
    norm = normalize_token(t)
    if len(t) == 2 and t[0] == "d" and t[1].upper() in AA:
        return t[1].upper()
    if norm in AA_LINKER_EXPANSIONS:
        return AA_LINKER_EXPANSIONS[norm]
    if norm in AA_LIKE_TOKEN_MAP:
        return AA_LIKE_TOKEN_MAP[norm]
    if norm in LINKER_ONLY_TOKENS or norm in NTERM_MODIFIERS or norm in CTERM_MARKERS:
        return ""
    if len(norm) == 1 and norm in AA:
        return norm
    if norm and all(ch in AA for ch in norm):
        return norm
    return ""

def parse_peptide_notation(seq: str) -> PeptideTokenParse:
    raw = str(seq or "").strip().replace(" ", "")
    parse = PeptideTokenParse(raw=raw)
    if not raw:
        return parse

    s, cterm = _strip_cterm(raw)
    parse.cterm = cterm

    parts = [p for p in s.split("-") if p]
    # explicit N-terminal modifier
    if parts:
        first_norm = normalize_token(parts[0])
        if first_norm in NTERM_MODIFIERS:
            parse.nterm = NTERM_MODIFIERS[first_norm]
            parse.modifier_tokens.append(parse.nterm)
            parts = parts[1:]

    s_after = "-".join(parts) if parts else s
    # Safe compact Ac: AcEEMQRR, but not ACDE.
    if not parse.nterm and s_after.startswith("Ac") and not s_after.startswith("AC") and len(s_after) > 2 and s_after[2:3].isupper():
        parse.nterm = "Ac"
        parse.modifier_tokens.append("Ac")
        s_after = s_after[2:]

    # Bracketed tokens are supported for non-natural units: E[Hyp]MQ[Ahx]RR.
    tokens: List[str] = []
    if "-" in s_after or re.search(r"[,;/\n\t ]", s_after):
        tokens = split_notation(s_after)
    else:
        # scan bracketed tokens plus natural letters/dAA compactly
        i = 0
        while i < len(s_after):
            ch = s_after[i]
            if ch == "[":
                j = s_after.find("]", i+1)
                if j > i:
                    tokens.append(s_after[i+1:j])
                    i = j+1
                    continue
            if ch == "d" and i+1 < len(s_after) and s_after[i+1].isupper():
                tokens.append(s_after[i:i+2])
                i += 2
                continue
            if ch.isupper():
                tokens.append(ch)
            # lowercase not in token context ignored to avoid terminal-word false residues
            i += 1

    core_parts: List[str] = []
    for tok in tokens:
        norm = normalize_token(tok)
        if not norm:
            continue
        if norm in LINKER_ONLY_TOKENS:
            parse.linker_tokens.append(tok)
            continue
        if norm in AA_LIKE_TOKEN_MAP:
            parse.aa_like_tokens.append(tok)
        frag = token_to_surrogate(tok)
        if frag:
            parse.core_tokens.extend(list(frag))
            core_parts.append(frag)
        elif norm not in NTERM_MODIFIERS and norm not in CTERM_MARKERS:
            parse.unknown_tokens.append(tok)

    parse.core_sequence = "".join(core_parts)
    return parse

def core_sequence(seq: str) -> str:
    return parse_peptide_notation(seq).core_sequence

def is_cterm_amide(seq: str) -> bool:
    return parse_peptide_notation(seq).cterm in {"NH2", "CONH2"}

def is_nterm_acetyl(seq: str) -> bool:
    return parse_peptide_notation(seq).nterm == "Ac"

def token_table() -> List[Dict[str, str]]:
    rows = []
    for k,v in sorted(NTERM_MODIFIERS.items()):
        rows.append({"token": v, "type": "NTERM_MODIFIER", "surrogate": ""})
    for k,v in sorted(AA_LIKE_TOKEN_MAP.items()):
        rows.append({"token": k, "type": "AA_LIKE", "surrogate": v})
    for k in sorted(LINKER_ONLY_TOKENS):
        rows.append({"token": k, "type": "LINKER_ONLY", "surrogate": ""})
    for k,v in sorted(CTERM_MARKERS.items()):
        rows.append({"token": k, "type": "CTERM", "surrogate": v})
    return rows
