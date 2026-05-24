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
    "Ac", "FITC", "Biotin", "BIOTIN", "FAM", "TAMRA", "CY3", "CY5", "CY7",
    "Pal", "Myr", "Gal", "Nic", "Caf", "DOTA", "NOTA"
]
CTERM_MARKERS = {"NH2", "CONH2", "AMIDE", "COOH", "CO2H", "OH", "ACID"}


def strip_protecting_groups(text: str) -> str:
    return PROTECTING_GROUP_RE.sub("", text or "").replace(" ", "")


def _is_cterm_marker(s: str) -> bool:
    return str(s or "").strip().upper() in CTERM_MARKERS


def _split_attached_nterm(core_text: str) -> tuple[str, str]:
    """Detect compact N-terminal modifier notation such as AcEEMQRR.

    This keeps normal peptide strings such as EEMQRR untouched, but allows
    AcEEMQRR-NH2 or AcEEMQRR to be interpreted as Ac + EEMQRR.
    """
    s = str(core_text or "").strip()
    for mod in sorted(NTERM_MODIFIERS, key=len, reverse=True):
        if s.upper().startswith(mod.upper()) and len(s) > len(mod):
            nxt = s[len(mod):len(mod)+1]
            # treat as attached modifier only when the remaining string starts
            # like a peptide sequence token.
            if nxt and nxt.isalpha():
                return mod if mod != "BIOTIN" else "Biotin", s[len(mod):]
    return "", s


def tokenize_core_sequence(core: str) -> list[str]:
    """Tokenize core sequence for SPPS planning.

    Supported examples:
    - EEMQRR -> E, E, M, Q, R, R
    - EEMQRR-NH2 -> E, E, M, Q, R, R after parsing
    - AcEEMQRR-NH2 -> Ac as N-terminal modifier, EEMQRR as core
    - dA,dR,Hyp,Ahx -> dA, dR, Hyp, Ahx
    - dA/dR/Hyp/Ahx -> dA, dR, Hyp, Ahx
    - E[Hyp]MQ[Ahx]RR -> E, Hyp, M, Q, Ahx, R, R

    For multi-letter non-natural residues, comma/slash/semicolon/newline or [token]
    notation is recommended.
    """
    s = strip_protecting_groups(core or "")
    if not s:
        return []
    if re.search(r"[,;/\n\t ]", s):
        return [p.strip().strip("[]") for p in re.split(r"\s*(?:,|;|/|\n|\t| )\s*", s) if p.strip()]
    tokens = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "[":
            j = s.find("]", i + 1)
            if j > i:
                tokens.append(s[i+1:j].strip())
                i = j + 1
                continue
        if ch == "d" and i + 1 < len(s) and s[i+1].isalpha() and s[i+1].isupper():
            tokens.append(s[i:i+2])
            i += 2
            continue
        if ch.isalpha() and ch.isupper():
            tokens.append(ch)
        elif ch.isalpha() and ch.islower():
            # lower-case characters that are not part of dAA or bracketed tokens are ignored
            # to avoid turning terminal words into false amino acids.
            pass
        i += 1
    return [t for t in tokens if t]


def parse_sequence(seq: str) -> ParsedSequence:
    """Parse peptide notation robustly for SPPS planning.

    Correctly handles:
    - Ac-EEMQRR-NH2
    - EEMQRR-NH2
    - EEMQRR
    - AcEEMQRR-NH2
    - AcEEMQRR

    The previous behavior incorrectly treated EEMQRR-NH2 as Nterm=EEMQRR and core=NH2.
    That made the planner parse N/H instead of the actual peptide sequence. This parser
    first checks whether the last dash-separated token is a known C-terminal marker.
    """
    raw = (seq or "").strip()
    s = raw.replace(" ", "")
    if not s:
        return ParsedSequence(raw=raw, nterm="", core="", cterm_text="", core_tokens=[])

    parts = [p.strip() for p in s.split("-") if p.strip()]
    nterm = ""
    cterm = ""
    core = s

    if len(parts) >= 3 and _is_cterm_marker(parts[-1]):
        cterm = parts[-1]
        maybe_nterm = parts[0]
        middle = "-".join(parts[1:-1])
        # If first token is known modifier, use it as nterm; otherwise treat all before Cterm as core.
        if any(maybe_nterm.upper() == m.upper() for m in NTERM_MODIFIERS):
            nterm = maybe_nterm if maybe_nterm.upper() != "BIOTIN" else "Biotin"
            core = middle
        else:
            core = "-".join(parts[:-1])
    elif len(parts) >= 2 and _is_cterm_marker(parts[-1]):
        cterm = parts[-1]
        core_candidate = "-".join(parts[:-1])
        detected, remainder = _split_attached_nterm(core_candidate)
        nterm, core = detected, remainder
    elif len(parts) >= 2:
        maybe_nterm = parts[0]
        if any(maybe_nterm.upper() == m.upper() for m in NTERM_MODIFIERS):
            nterm = maybe_nterm if maybe_nterm.upper() != "BIOTIN" else "Biotin"
            core = "-".join(parts[1:])
        else:
            detected, remainder = _split_attached_nterm("-".join(parts))
            nterm, core = detected, remainder
    else:
        detected, remainder = _split_attached_nterm(s)
        nterm, core = detected, remainder

    core_clean = strip_protecting_groups(core)
    return ParsedSequence(raw=raw, nterm=nterm, core=core_clean, cterm_text=cterm, core_tokens=tokenize_core_sequence(core_clean))
