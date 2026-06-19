import re
from dataclasses import dataclass, field

PROTECTING_GROUP_RE = re.compile(r"\([^)]*\)")

@dataclass
class ParsedSequence:
    raw: str
    nterm: str
    core: str
    cterm_text: str
    core_tokens: list[str] = field(default_factory=list)


NTERM_MODIFIERS = [
    "Ac", "FITC", "Biotin", "BIOTIN", "Biotin-NHS", "Biotin acid",
    "FAM", "5-FAM", "6-FAM", "FAM-NHS", "TAMRA", "CY3", "CY5", "CY7",
    "Pal", "Palmitic acid", "Palmitoyl", "Myr", "Myristic acid", "Myristoyl",
    "Gal", "Gallic acid", "Galloyl", "Nic", "Nicotinic acid", "Nicotinoyl",
    "Caf", "Caffeic acid", "Caffeoyl", "DOTA", "NOTA", "Dabcyl", "BHQ",
    "His6", "His8", "His10", "FLAG", "HA", "Myc", "StrepII", "TwinStrep", "V5", "T7", "ALFA", "AviTag", "SpyTag"
]

NTERM_MODIFIER_ALIASES = {
    "AC": "Ac", "ACETYL": "Ac", "ACETICACID": "Ac",
    "BIOTIN": "Biotin", "BIOTINNHS": "Biotin-NHS", "BIOTINACID": "Biotin acid",
    "FITC": "FITC", "FAM": "FAM", "5FAM": "5-FAM", "6FAM": "6-FAM", "FAMNHS": "FAM-NHS",
    "TAMRA": "TAMRA", "CY3": "CY3", "CY5": "CY5", "CY7": "CY7",
    "PAL": "Pal", "PALMITICACID": "Pal", "PALMITOYL": "Pal",
    "MYR": "Myr", "MYRISTICACID": "Myr", "MYRISTOYL": "Myr",
    "GAL": "Gal", "GALLICACID": "Gal", "GALLOYL": "Gal",
    "CAF": "Caf", "CAFFEICACID": "Caf", "CAFFEOYL": "Caf",
    "NIC": "Nic", "NICOTINICACID": "Nic", "NICOTINOYL": "Nic",
    "DOTA": "DOTA", "NOTA": "NOTA", "DABCYL": "Dabcyl", "BHQ": "BHQ",
    "HIS6": "His6", "HIS8": "His8", "HIS10": "His10", "FLAG": "FLAG", "HA": "HA",
    "MYC": "Myc", "STREPII": "StrepII", "TWINSTREP": "TwinStrep", "V5": "V5",
    "T7": "T7", "ALFA": "ALFA", "AVITAG": "AviTag", "SPYTAG": "SpyTag",
}

def _norm_key(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(token or "")).upper()
CTERM_MARKERS = {"NH2", "CONH2", "AMIDE", "COOH", "CO2H", "OH", "ACID"}


def strip_protecting_groups(text: str) -> str:
    return PROTECTING_GROUP_RE.sub("", text or "").replace(" ", "")



def _normalise_nterm_modifier(token: str) -> str:
    t = str(token or "").strip()
    key = _norm_key(t)
    if key in NTERM_MODIFIER_ALIASES:
        return NTERM_MODIFIER_ALIASES[key]
    for m in NTERM_MODIFIERS:
        if _norm_key(m) == key:
            return NTERM_MODIFIER_ALIASES.get(_norm_key(m), m)
    return ""


def _consume_leading_nterm_modifier(parts: list[str]) -> tuple[str, list[str]]:
    """Return (modifier, remaining_parts), supporting hyphenated modifiers.

    Examples: 5-FAM-Ahx-EEMQRR-NH2 -> modifier 5-FAM; Biotin-NHS-PEPTIDE
    -> modifier Biotin-NHS.  Plain FAM-PEPTIDE still works.
    """
    if not parts:
        return "", parts
    # Try longest practical modifier first because some names contain hyphens.
    max_len = min(3, len(parts))
    for n in range(max_len, 0, -1):
        cand = "-".join(parts[:n])
        mod = _normalise_nterm_modifier(cand)
        if mod:
            return mod, parts[n:]
    return "", parts

def _is_cterm_marker(s: str) -> bool:
    return str(s or "").strip().upper() in CTERM_MARKERS


def _split_attached_nterm(core_text: str) -> tuple[str, str]:
    """Detect only safe compact N-terminal modifier notation.

    Compact modifier notation is intentionally conservative.  In older builds,
    case-insensitive detection treated natural all-caps sequences such as
    ACDE... as Ac + DE..., and could similarly misread PAL... as Pal.  For SPPS
    planning this is dangerous because it changes the actual core sequence.

    Supported compact form:
    - AcEEMQRR -> Ac + EEMQRR

    Other modifiers should be written explicitly with a dash:
    - FITC-EEMQRR
    - Biotin-EEMQRR
    - Pal-EEMQRR
    """
    s = str(core_text or "").strip()
    if s.startswith("Ac") and not s.startswith("AC") and len(s) > 2:
        nxt = s[2:3]
        if nxt and nxt.isupper():
            return "Ac", s[2:]
    return "", s


KNOWN_CORE_TOKENS = {
    "AEEA", "AHX", "CHA", "AIB", "NLE", "ORN", "CIT", "HYP", "DAB", "NAL",
    "BALA", "B-ALA", "GABA", "PEG1", "PEG2", "PEG3", "PEG4", "PEG6", "PEG8", "PEG12", "PEG24",
    "G4S", "G4SX2", "SMCC", "SULFOSMCC", "DSS"
}


def _tokenize_compact_segment(segment: str) -> list[str]:
    """Tokenize one delimiter-free segment.

    Multi-letter laboratory tokens are preserved only when written as a full
    segment (Ahx, AEEA, Cha, PEG4, etc.) or in bracket notation.  Plain FASTA
    chunks such as EEMQRR are still split into amino-acid residues.
    """
    seg = str(segment or "").strip().strip("[]")
    if not seg:
        return []
    if seg.upper() in KNOWN_CORE_TOKENS:
        canonical = {"AHX": "Ahx", "CHA": "Cha", "AIB": "Aib", "NLE": "Nle", "ORN": "Orn", "CIT": "Cit", "HYP": "Hyp", "DAB": "Dab", "NAL": "Nal", "BALA": "bAla", "B-ALA": "bAla"}.get(seg.upper())
        return [canonical or seg]
    tokens = []
    i = 0
    while i < len(seg):
        ch = seg[i]
        if ch == "[":
            j = seg.find("]", i + 1)
            if j > i:
                tokens.append(seg[i+1:j].strip())
                i = j + 1
                continue
        if ch == "d" and i + 1 < len(seg) and seg[i+1].isalpha() and seg[i+1].isupper():
            tokens.append(seg[i:i+2])
            i += 2
            continue
        if ch.isalpha() and ch.isupper():
            tokens.append(ch)
        i += 1
    return [t for t in tokens if t]


def tokenize_core_sequence(core: str) -> list[str]:
    """Tokenize core sequence for SPPS planning.

    Supported examples:
    - EEMQRR -> E, E, M, Q, R, R
    - EEMQRR-NH2 -> E, E, M, Q, R, R after parsing
    - AcEEMQRR-NH2 -> Ac as N-terminal modifier, EEMQRR as core
    - dA,dR,Hyp,Ahx -> dA, dR, Hyp, Ahx
    - dA/dR/Hyp/Ahx -> dA, dR, Hyp, Ahx
    - Biotin-Ahx-EEMQRR-NH2 -> Biotin as N-term, Ahx preserved as linker, then E/E/M/Q/R/R
    - FAM-AEEA-EEMQRR-NH2 -> FAM as N-term, AEEA preserved as linker, then E/E/M/Q/R/R
    - E[Hyp]MQ[Ahx]RR -> E, Hyp, M, Q, Ahx, R, R

    Hyphen inside the parsed core is treated as a residue/linker separator. This
    prevents Ahx/AEEA from being silently degraded into A/H/X or A/E/E/A.
    """
    s = strip_protecting_groups(core or "")
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"\s*(?:-|,|;|/|\n|\t| )\s*", s) if p.strip()]
    tokens: list[str] = []
    if len(parts) > 1:
        for part in parts:
            tokens.extend(_tokenize_compact_segment(part))
        return [t for t in tokens if t]
    return _tokenize_compact_segment(s)


def parse_sequence(seq: str) -> ParsedSequence:
    """Parse peptide notation robustly for SPPS planning.

    Correctly handles terminal modifiers, hyphenated labels, internal linker
    tokens, D-amino-acid tokens, and C-terminal markers.  The first dash token
    is treated as an N-terminal modifier only when it matches the supported
    modifier list (including hyphenated names such as 5-FAM or Biotin-NHS).
    """
    raw = (seq or "").strip()
    s = raw.replace(" ", "")
    if not s:
        return ParsedSequence(raw=raw, nterm="", core="", cterm_text="", core_tokens=[])

    parts = [p.strip() for p in s.split("-") if p.strip()]
    nterm = ""
    cterm = ""

    # Remove C-terminal marker first.
    if parts and _is_cterm_marker(parts[-1]):
        cterm = parts[-1]
        parts = parts[:-1]

    # Then consume a known N-terminal modifier, supporting hyphenated modifiers.
    nterm, remaining = _consume_leading_nterm_modifier(parts)
    if nterm:
        core = "-".join(remaining)
    else:
        core_candidate = "-".join(parts) if parts else s
        # Safe compact notation: AcEEMQRR -> Ac + EEMQRR.
        detected, remainder = _split_attached_nterm(core_candidate)
        nterm, core = detected, remainder

    core_clean = strip_protecting_groups(core)
    return ParsedSequence(raw=raw, nterm=nterm, core=core_clean, cterm_text=cterm, core_tokens=tokenize_core_sequence(core_clean))
