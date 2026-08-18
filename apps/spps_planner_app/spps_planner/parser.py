import re
from dataclasses import dataclass, field

PROTECTING_GROUP_RE = re.compile(r"\(([^)]*)\)")
KNOWN_PROTECTING_GROUPS = {
    "OTBU", "TBU", "TRT", "PBF", "BOC", "FMOC", "DDE", "IVDDE", "MTT",
    "ALLOC", "ACM", "STBU", "TBUT", "BZH", "BOM", "TOS", "Z", "CBZ",
    "BNS", "MTS", "MTR", "PMC", "BZI", "BZI2", "2CLTRT", "CLTRT",
    "PO(NME2)2", "PO(OME)2", "PO(OBZL)OH", "OTCE", "OPNB",
}

@dataclass
class ParsedSequence:
    raw: str
    nterm: str
    core: str
    cterm_text: str
    core_tokens: list[str] = field(default_factory=list)
    branch_tokens: list[str] = field(default_factory=list)
    branch_sites: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


NTERM_MODIFIERS = [
    "Ac", "Fmoc", "Boc", "FITC", "Biotin", "BIOTIN", "Biotin-NHS", "Biotin acid",
    "FAM", "5-FAM", "6-FAM", "FAM-NHS", "TAMRA", "5-TAMRA", "6-TAMRA", "TAMRA-NHS", "CY3", "CY5", "CY5-NHS", "Sulfo-Cy5-NHS", "Sulfo-Cy5-NHS-K", "Sulfo-Cy5-NHS-TEA", "CY7",
    "Desthiobiotin", "Desthiobiotin-NHS", "Biotin-PEG4-acid", "Biotin-PEG4-NHS", "Chol-Suc", "CHEMS",
    "DOTA-tris(tBu)", "DOTA-NHS", "DOTA-NHS-tris(tBu)", "NOTA-NHS", "DBCO acid", "DBCO-PEG4-acid",
    "Pal", "Palmitic acid", "Palmitoyl", "Myr", "Myristic acid", "Myristoyl",
    "Gal", "Gallic acid", "Galloyl", "Nic", "Nicotinic acid", "Nicotinoyl",
    "Caf", "Caffeic acid", "Caffeoyl", "DOTA", "NOTA", "Dabcyl", "BHQ",
    "His6", "His8", "His10", "FLAG", "HA", "Myc", "StrepII", "TwinStrep", "V5", "T7", "ALFA", "AviTag", "SpyTag"
]

ACETYLATED_AMINO_ACIDS = [
    "Ac-Ala-OH", "Ac-Arg(Pbf)-OH", "Ac-Asn(Trt)-OH", "Ac-Asp(OtBu)-OH",
    "Ac-Cys(Trt)-OH", "Ac-Gln(Trt)-OH", "Ac-Glu(OtBu)-OH", "Ac-Gly-OH",
    "Ac-His(Trt)-OH", "Ac-Ile-OH", "Ac-Leu-OH", "Ac-Lys(Boc)-OH",
    "Ac-Met-OH", "Ac-Phe-OH", "Ac-Pro-OH", "Ac-Ser(tBu)-OH",
    "Ac-Thr(tBu)-OH", "Ac-Trp(Boc)-OH", "Ac-Tyr(tBu)-OH", "Ac-Val-OH",
]
NTERM_MODIFIERS.extend(ACETYLATED_AMINO_ACIDS)

NTERM_MODIFIER_ALIASES = {
    "AC": "Ac", "ACETYL": "Ac", "ACETICACID": "Ac",
    "FMOC": "Fmoc", "FMOCCL": "Fmoc", "BOC": "Boc", "BOC2O": "Boc",
    "BIOTIN": "Biotin", "BIOTINNHS": "Biotin-NHS", "BIOTINACID": "Biotin acid",
    "DESTHIOBIOTIN": "Desthiobiotin", "DESTHIOBIOTINNHS": "Desthiobiotin-NHS", "BIOTINPEG4ACID": "Biotin-PEG4-acid", "BIOTINPEG4NHS": "Biotin-PEG4-NHS",
    "FITC": "FITC", "FAM": "FAM", "5FAM": "5-FAM", "6FAM": "6-FAM", "FAMNHS": "FAM-NHS",
    "TAMRA": "TAMRA", "5TAMRA": "5-TAMRA", "6TAMRA": "6-TAMRA", "TAMRANHS": "TAMRA-NHS", "CY3": "CY3", "CY5": "CY5", "CY5NHS": "CY5-NHS", "SULFOCY5NHS": "Sulfo-Cy5-NHS", "SULFOCY5NHSK": "Sulfo-Cy5-NHS-K", "SULFOCY5NHSTEA": "Sulfo-Cy5-NHS-TEA", "CY7": "CY7",
    "PAL": "Pal", "PALMITICACID": "Pal", "PALMITOYL": "Pal",
    "CHOLSUC": "Chol-Suc", "CHEMS": "CHEMS", "CHS": "Chol-Suc",
    "MYR": "Myr", "MYRISTICACID": "Myr", "MYRISTOYL": "Myr",
    "GAL": "Gal", "GALLICACID": "Gal", "GALLOYL": "Gal",
    "CAF": "Caf", "CAFFEICACID": "Caf", "CAFFEOYL": "Caf",
    "NIC": "Nic", "NICOTINICACID": "Nic", "NICOTINOYL": "Nic",
    "DOTA": "DOTA", "DOTATRISTBU": "DOTA-tris(tBu)", "DOTANHS": "DOTA-NHS", "DOTANHSTRISTBU": "DOTA-NHS-tris(tBu)",
    "NOTA": "NOTA", "NOTANHS": "NOTA-NHS", "DBCOACID": "DBCO acid", "DBCOPEG4ACID": "DBCO-PEG4-acid", "DABCYL": "Dabcyl", "BHQ": "BHQ",
    "HIS6": "His6", "HIS8": "His8", "HIS10": "His10", "FLAG": "FLAG", "HA": "HA",
    "MYC": "Myc", "STREPII": "StrepII", "TWINSTREP": "TwinStrep", "V5": "V5",
    "T7": "T7", "ALFA": "ALFA", "AVITAG": "AviTag", "SPYTAG": "SpyTag",
}
NTERM_MODIFIER_ALIASES.update({
    re.sub(r"[^A-Za-z0-9]", "", name).upper(): name
    for name in ACETYLATED_AMINO_ACIDS
})

def _norm_key(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(token or "")).upper()


def _uppercase_plain_natural_segment(seg: str) -> str:
    """Allow lowercase FASTA input without changing explicit D-form syntax.

    g-h-k and ghk are treated as G-H-K.  Explicit dG remains dG; bracketed
    vendor/linker tokens and mixed-case aliases such as gAla are handled by
    the normal alias table instead of this helper.
    """
    s = str(seg or "").strip()
    letters = [ch for ch in s if ch.isalpha()]
    if letters and all(ch.islower() for ch in letters) and set(ch.upper() for ch in letters).issubset(NATURAL_AA_LETTERS):
        return "".join(ch.upper() if ch.isalpha() else ch for ch in s)
    return s
CTERM_MARKERS = {"NH2", "CONH2", "AMIDE", "COOH", "CO2H", "OH", "ACID"}
NATURAL_AA_LETTERS = set("ARNDCQEGHILKMFPSTWYV")


def _pg_norm(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9()]+", "", str(text or "")).upper()


def _is_known_protecting_group(text: str) -> bool:
    key = _pg_norm(text)
    return key in KNOWN_PROTECTING_GROUPS


def strip_protecting_groups(text: str) -> str:
    """Remove known protecting groups but keep branch notation.

    Older builds removed every parenthesized group. That silently deleted
    branch arms such as K(GGEP). This function now removes only known
    protecting groups such as E(OtBu), R(Pbf), Q(Trt), K(Mtt), etc.; unknown
    sequence-like parentheses remain available to the branch parser.
    """
    def repl(m: re.Match) -> str:
        inner = m.group(1)
        return "" if _is_known_protecting_group(inner) else f"({inner})"
    return PROTECTING_GROUP_RE.sub(repl, text or "").replace(" ", "")



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
    max_len = min(8, len(parts))
    for n in range(max_len, 0, -1):
        candidate_parts = parts[:n]
        if n > 1 and all(
            len(part) == 1 and part.isupper() and part in NATURAL_AA_LETTERS
            for part in candidate_parts
        ):
            # Dashed peptide input such as A-C-D or F-A-M is a residue
            # sequence, not the aliases Ac or FAM.
            continue
        cand = "-".join(candidate_parts)
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
    "BALA", "B-ALA", "BETAALA", "GALA", "G-ALA", "GAMMAALA", "GABA", "PEG1", "PEG2", "PEG3", "PEG4", "PEG6", "PEG8", "PEG12", "PEG24",
    "G4S", "G4SX2", "SMCC", "SULFOSMCC", "DSS",
    "K(FMOC)", "K(IVDDE)", "K(DDE)", "K(MTT)", "DPR", "ORN", "DAB"
}

TOKEN_CANONICAL = {
    "AHX": "Ahx", "CHA": "Cha", "AIB": "Aib", "NLE": "Nle", "ORN": "Orn",
    "CIT": "Cit", "HYP": "Hyp", "DAB": "Dab", "NAL": "Nal",
    "BALA": "bAla", "B-ALA": "bAla", "BETAALA": "bAla", "ΒALA": "bAla",
    "GALA": "gAla", "G-ALA": "gAla", "GAMMAALA": "gAla", "ΓALA": "gAla", "GABA": "gAla",
    "K(FMOC)": "K(Fmoc)",
    "K(IVDDE)": "K(ivDde)", "K(DDE)": "K(ivDde)", "K(MTT)": "K(Mtt)",
}


def _normalize_core_aliases(text: str) -> str:
    """Normalize common lab linker spellings before top-level splitting.

    This prevents inputs such as b-Ala/g-Ala/gamma-Ala from being split into
    artificial residues by the dash parser. Bracket notation still wins for any
    unusual vendor token.
    """
    s = str(text or "")
    replacements = [
        (r"(?i)β[-_ ]?ala", "bAla"),
        (r"(?i)beta[-_ ]?ala", "bAla"),
        (r"(?i)b[-_ ]?ala", "bAla"),
        (r"(?i)γ[-_ ]?ala", "gAla"),
        (r"(?i)gamma[-_ ]?ala", "gAla"),
        (r"(?i)g[-_ ]?ala", "gAla"),
        (r"(?i)gaba", "gAla"),
    ]
    # Exact bottle names are entered in brackets and must remain byte-for-byte
    # intact.  Alias normalization applies only to ordinary sequence segments.
    parts = re.split(r"(\[[^\]]*\])", s)
    for index in range(0, len(parts), 2):
        for pat, repl in replacements:
            parts[index] = re.sub(pat, repl, parts[index])
    return "".join(parts)


def _tokenize_compact_segment(segment: str) -> list[str]:
    """Tokenize one delimiter-free segment.

    Multi-letter laboratory tokens are preserved only when written as a full
    segment (Ahx, AEEA, Cha, PEG4, etc.) or in bracket notation.  Plain FASTA
    chunks such as EEMQRR are still split into amino-acid residues.
    """
    raw_segment = str(segment or "").strip()
    if raw_segment.startswith("[") and raw_segment.endswith("]"):
        token = raw_segment[1:-1].strip()
        return [TOKEN_CANONICAL.get(token.upper(), token)] if token else []
    seg = _uppercase_plain_natural_segment(raw_segment)
    if not seg:
        return []
    if seg.upper() in KNOWN_CORE_TOKENS:
        canonical = TOKEN_CANONICAL.get(seg.upper())
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


def _split_top_level(text: str) -> list[str]:
    """Split on delimiters but not inside () or []."""
    s = str(text or "")
    parts: list[str] = []
    buf: list[str] = []
    depth_par = 0
    depth_br = 0
    for ch in s:
        if ch == "(":
            depth_par += 1; buf.append(ch); continue
        if ch == ")":
            depth_par = max(0, depth_par - 1); buf.append(ch); continue
        if ch == "[":
            depth_br += 1; buf.append(ch); continue
        if ch == "]":
            depth_br = max(0, depth_br - 1); buf.append(ch); continue
        if depth_par == 0 and depth_br == 0 and ch in "-,;/\n\t ":
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def _tokenize_segment_with_branches(segment: str) -> tuple[list[str], list[dict], list[str]]:
    """Tokenize one segment and preserve sequence-like branch arms.

    K(GGEP) becomes main token K plus branch site {anchor_token: K,
    branch_tokens: [G,G,E,P]}. Known protecting groups such as E(OtBu) are
    removed rather than treated as branches. Whole-token branch handles such as
    K(Mtt) stay as K(Mtt).
    """
    raw_segment = str(segment or "").strip()
    if raw_segment.startswith("[") and raw_segment.endswith("]"):
        token = raw_segment[1:-1].strip()
        canonical = TOKEN_CANONICAL.get(token.upper(), token)
        return ([canonical] if canonical else []), [], []
    seg = _uppercase_plain_natural_segment(raw_segment)
    warnings: list[str] = []
    if not seg:
        return [], [], warnings
    if seg.upper() in KNOWN_CORE_TOKENS:
        canonical = TOKEN_CANONICAL.get(seg.upper())
        return [canonical or seg], [], warnings
    tokens: list[str] = []
    branches: list[dict] = []
    i = 0
    while i < len(seg):
        ch = seg[i]
        if ch == "[":
            j = seg.find("]", i + 1)
            if j > i:
                tok = seg[i+1:j].strip()
                if tok:
                    tokens.append(TOKEN_CANONICAL.get(tok.upper(), tok))
                i = j + 1
                continue
        if ch == "(":
            j = seg.find(")", i + 1)
            if j > i:
                inner = seg[i+1:j].strip()
                if _is_known_protecting_group(inner):
                    i = j + 1
                    continue
                branch_tokens = tokenize_core_sequence(inner)
                if branch_tokens and tokens:
                    branches.append({
                        "anchor_index": len(tokens) - 1,
                        "anchor_token": tokens[-1],
                        "branch_text": inner,
                        "branch_tokens": branch_tokens,
                    })
                    warnings.append(f"Branch arm detected at {tokens[-1]}({inner}); branch steps are planned as a separate orthogonal section.")
                elif inner:
                    warnings.append(f"Unsupported parenthesized branch/group ignored: ({inner})")
                i = j + 1
                continue
        if ch == "d" and i + 1 < len(seg) and seg[i+1].isalpha() and seg[i+1].isupper():
            tokens.append(seg[i:i+2])
            i += 2
            continue
        if ch.isalpha() and ch.isupper():
            tokens.append(ch)
        i += 1
    return [t for t in tokens if t], branches, warnings


def tokenize_core_sequence_with_branches(core: str) -> tuple[list[str], list[dict], list[str]]:
    # Do not pre-strip protecting groups here: whole-token branch handles such
    # as K(Mtt) / K(ivDde) must remain detectable. Segment tokenization itself
    # skips ordinary protecting groups such as E(OtBu), R(Pbf), Q(Trt).
    s = _normalize_core_aliases(str(core or "")).replace(" ", "")
    if not s:
        return [], [], []
    parts = _split_top_level(s)
    tokens: list[str] = []
    branches: list[dict] = []
    warnings: list[str] = []
    for part in parts:
        local_tokens, local_branches, local_warnings = _tokenize_segment_with_branches(part)
        offset = len(tokens)
        for br in local_branches:
            br = dict(br)
            br["anchor_index"] = int(br.get("anchor_index", 0)) + offset
            branches.append(br)
        tokens.extend(local_tokens)
        warnings.extend(local_warnings)
    return [t for t in tokens if t], branches, warnings


def tokenize_core_sequence(core: str) -> list[str]:
    """Tokenize core sequence for SPPS planning while not deleting branches.

    Branch arms are returned through parse_sequence(...).branch_sites; this
    compatibility function returns only the main-chain tokens.
    """
    tokens, _, _ = tokenize_core_sequence_with_branches(core)
    return tokens


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

    # Preserve hyphens inside bracketed exact reagent names such as
    # [Fmoc-NH-PEG4-CH2COOH].
    parts = [p.strip() for p in _split_top_level(s) if p.strip()]
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
    core_tokens, branch_sites, warnings = tokenize_core_sequence_with_branches(core)
    branch_tokens: list[str] = []
    for br in branch_sites:
        branch_tokens.extend(list(br.get("branch_tokens", [])))
    return ParsedSequence(raw=raw, nterm=nterm, core=core_clean, cterm_text=cterm, core_tokens=core_tokens, branch_tokens=branch_tokens, branch_sites=branch_sites, warnings=warnings)
