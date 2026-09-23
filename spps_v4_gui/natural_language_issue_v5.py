"""Lightweight Korean/English natural-language parser for synthesis issue notes.

The parser is intentionally deterministic and local.  It never invents chemistry
conditions.  It maps common operator language into the existing Issue Log schema
and returns a confidence score so low-confidence notes can be kept out of ML/risk
features until reviewed.
"""
from __future__ import annotations

import re
from typing import Any

PARSER_VERSION = "v5-light-bilingual-2"


def _has(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


ISSUES = (
    # label, stage, confidence, patterns
    ("Abnormal Kaiser / chloranil", "Coupling", 0.88, (
        r"\bkaiser\b.*(?:positive|\+|blue|양성|파란|블루)", r"(?:positive|\+|blue|양성|파란|블루).*\bkaiser\b",
        r"\bchloranil\b.*(?:positive|\+|양성)", r"카이저.*(?:양성|파란|블루|\+)", r"클로라닐.*(?:양성|\+)",
    )),
    ("Precipitation failure / partial precipitation", "Precipitation / Workup", 0.86, (
        r"precipitat(?:ion|e).*?(?:fail|poor|partial|not|no |hard|problem)", r"(?:ether|hexane).*?(?:no|poor|partial).*precip",
        r"침전.*(?:안|못|적|부분|불량|문제|잘 안)", r"(?:에테르|ether|헥산|hexane).*침전.*(?:안|못|적|부분)",
    )),
    ("Aggregation / resin clumping", "Coupling", 0.86, (
        r"resin.*(?:clump|aggregate|stick|stuck|cake)", r"(?:clump|aggregate).*resin",
        r"레진.*(?:뭉|응집|붙|굳|덩어리)", r"(?:뭉|응집).*레진",
    )),
    ("Oxidation", "Cleavage", 0.86, (
        r"\boxid(?:ation|ized|ised)\b", r"산화", r"met\s*\(?o\)?", r"methionine.*oxid",
    )),
    ("Incomplete deprotection", "Deprotection", 0.82, (
        r"(?:fmoc|deprotect).*?(?:incomplete|fail|not complete|problem|positive)",
        r"(?:incomplete|fail).*?(?:fmoc|deprotect)", r"탈보호.*(?:안|못|불완전|문제)", r"fmoc.*(?:안|못|불완전|문제)",
    )),
    ("Incomplete coupling", "Coupling", 0.80, (
        r"coupl(?:ing|ed).*?(?:incomplete|fail|poor|not|again|repeat|problem)",
        r"(?:incomplete|failed|poor).*coupl", r"(?:안\s*붙|못\s*붙|결합.*(?:안|못|불완전)|커플링.*(?:안|못|불완전|문제))",
        r"(?:재커플링|re-?coupl|repeat\s+coupl)",
    )),
    ("Poor swelling", "Swelling", 0.82, (
        r"(?:poor|bad|insufficient).*swell", r"resin.*(?:not|poor).*swell", r"팽윤.*(?:안|못|불량|부족|문제)",
    )),
    ("Filtration difficulty", "Precipitation / Workup", 0.80, (
        r"filter(?:ing|ation)?.*?(?:slow|hard|difficult|clog|problem)", r"(?:slow|hard|difficult|clog).*filter",
        r"여과.*(?:느|안|막|어렵|문제)", r"필터.*(?:막|안|느|문제)",
    )),
    ("Reagent solubility", "Coupling", 0.80, (
        r"(?:reagent|amino acid|aa).*?(?:insoluble|not dissolv|poor solubility)", r"(?:insoluble|not dissolv).*?(?:reagent|amino acid)",
        r"(?:시약|아미노산).*?(?:안 녹|못 녹|용해.*안|불용|용해도)",
    )),
    ("Side product", "Purification", 0.78, (
        r"side\s*product", r"by-?product", r"impurity peak", r"부산물", r"불순물.*피크",
    )),
    ("Low crude recovery", "Precipitation / Workup", 0.78, (
        r"(?:low|poor).*crude.*(?:recovery|yield)", r"crude.*(?:low|poor)", r"크루드.*(?:적|낮|회수.*안)", r"조펩타이드.*(?:적|낮)",
    )),
    ("Cleavage problem", "Cleavage", 0.72, (
        r"cleavage.*(?:problem|fail|incomplete|poor|issue)", r"(?:problem|fail|incomplete).*cleavage", r"클리비지.*(?:문제|안|못|불완전)", r"절단.*(?:문제|안|못|불완전)",
    )),
    ("Equipment / process problem", "Equipment / Process", 0.76, (
        r"(?:equipment|machine|pump|rotor|shaker|stirrer).*?(?:fail|stop|problem|error|broken)",
        r"(?:장비|펌프|로터|교반기|쉐이커).*?(?:고장|멈|문제|에러)",
    )),
)

ACTIONS = (
    ("NH4I reduction", (r"\bnh4i\b", r"ammonium\s+iodide", r"암모늄\s*아이오다이드", r"요오드화\s*암모늄")),
    ("Repeat coupling", (r"repeat(?:ed)?\s+(?:the\s+)?coupl", r"re-?coupl", r"coupl(?:ing)?\s+(?:again|once more)", r"재커플링", r"커플링.*(?:한 번 더|다시)", r"한 번 더.*(?:붙|coupl)")),
    ("Repeat deprotection", (r"repeat(?:ed)?\s+(?:the\s+)?deprotect", r"deprotect.*(?:again|once more)", r"탈보호.*(?:다시|한 번 더)", r"fmoc.*(?:다시|한 번 더)")),
    ("Longer reaction", (r"(?:extend|longer|increased).*?(?:time|reaction)", r"시간.*(?:늘|연장)", r"반응.*(?:더 오래|연장)")),
    ("Solvent change", (r"chang(?:e|ed).*solvent", r"solvent.*chang", r"용매.*(?:교체|변경|바꿈|바꿨)")),
    ("Reagent change", (r"chang(?:e|ed).*reagent", r"reagent.*chang", r"시약.*(?:교체|변경|바꿈|바꿨)")),
    ("Additional wash", (r"additional\s+wash", r"extra\s+wash", r"wash(?:ed)?\s+(?:again|more)", r"세척.*(?:추가|더|다시)", r"워시.*(?:추가|더|다시)")),
    ("Re-cleavage / extended cleavage", (r"re-?cleavage", r"repeat.*cleavage", r"extend.*cleavage", r"클리비지.*(?:다시|연장|더 오래)")),
    ("Re-precipitation / additional wash", (r"re-?precip", r"precipitat.*again", r"재침전", r"침전.*(?:다시|한 번 더)")),
    ("Manual intervention", (r"manual(?:ly)?", r"shake(?:d)? by hand", r"stirr(?:ed)? by hand", r"손으로", r"수동", r"직접.*(?:흔들|섞)")),
)

RESOLUTIONS = (
    ("Not Resolved", (r"not\s+resolved", r"still\s+(?:positive|failed|bad|problem)", r"did(?:n'?t| not)\s+(?:work|resolve|improve)", r"여전히", r"해결.*안", r"안\s*됐", r"안\s*됨", r"계속.*(?:양성|문제)")),
    ("Improved", (r"improv(?:ed|ement)", r"better", r"나아", r"개선", r"호전")),
    ("Resolved", (r"resolved", r"fixed", r"worked", r"fine\b", r"okay\b", r"ok\b", r"negative\b", r"returned?\s+to\s+normal", r"back\s+to\s+normal", r"괜찮", r"해결", r"정상", r"음성", r"문제없", r"잘 됐", r"잘됨")),
)

RESIDUES = {
    "ALA":"A", "ARG":"R", "ASN":"N", "ASP":"D", "CYS":"C", "GLN":"Q", "GLU":"E", "GLY":"G", "HIS":"H", "ILE":"I",
    "LEU":"L", "LYS":"K", "MET":"M", "PHE":"F", "PRO":"P", "SER":"S", "THR":"T", "TRP":"W", "TYR":"Y", "VAL":"V",
    "알라닌":"A", "아르기닌":"R", "아스파라긴":"N", "아스파트산":"D", "시스테인":"C", "글루타민":"Q", "글루탐산":"E", "글라이신":"G", "글리신":"G",
    "히스티딘":"H", "아이소류신":"I", "류신":"L", "라이신":"K", "메티오닌":"M", "페닐알라닌":"F", "프롤린":"P", "세린":"S", "트레오닌":"T",
    "트립토판":"W", "타이로신":"Y", "발린":"V",
}


def _position(text: str) -> int | None:
    patterns = (
        r"(?:position|pos\.?|site|residue)\s*#?\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:번|번째)(?:\s*(?:자리|위치|residue))?",
    )
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                n = int(m.group(1))
                return n if n > 0 else None
            except Exception:
                pass
    return None


def _residue(text: str) -> str:
    # Prefer explicit D-/Fmoc forms, then standard 3-letter names.
    m = re.search(r"\b(?:Fmoc[- ]?)?(D[- ]?)?(Ala|Arg|Asn|Asp|Cys|Gln|Glu|Gly|His|Ile|Leu|Lys|Met|Phe|Pro|Ser|Thr|Trp|Tyr|Val)\b", text, re.IGNORECASE)
    if m:
        aa = RESIDUES[m.group(2).upper()]
        return ("D-" + aa) if m.group(1) else aa
    for name, aa in RESIDUES.items():
        if re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", text, re.IGNORECASE):
            return aa
    return ""


def _language(text: str) -> str:
    ko = bool(re.search(r"[가-힣]", text))
    en = bool(re.search(r"[A-Za-z]", text))
    return "mixed" if ko and en else "ko" if ko else "en" if en else "unknown"


def parse_issue_note(note: str) -> dict[str, Any]:
    raw = str(note or "").strip()
    compact = re.sub(r"\s+", " ", raw)
    if not compact:
        return {
            "stage": "Other", "issue_type": "Other", "action_taken": "", "resolution": "Unknown",
            "severity": "Low", "position": None, "residue": "", "confidence": 0.0,
            "parse_status": "needs_review", "parser_version": PARSER_VERSION, "detected_language": "unknown",
            "matched_fields": [],
        }

    issue_type, stage, base = "Other", "Other", 0.20
    matched = []
    for label, issue_stage, confidence, patterns in ISSUES:
        if _has(compact, patterns):
            issue_type, stage, base = label, issue_stage, confidence
            matched.append("issue")
            break

    action = ""
    for label, patterns in ACTIONS:
        if _has(compact, patterns):
            action = label; matched.append("action"); break

    resolution = "Unknown"
    for label, patterns in RESOLUTIONS:
        if _has(compact, patterns):
            resolution = label; matched.append("resolution"); break

    pos = _position(compact)
    if pos is not None: matched.append("position")
    residue = _residue(compact)
    if residue: matched.append("residue")

    # Stage-only hints are useful when the issue wording is generic.
    if stage == "Other":
        stage_hints = (
            ("Precipitation / Workup", (r"precip", r"ether", r"hexane", r"침전", r"에테르", r"헥산")),
            ("Cleavage", (r"cleavage", r"tfa", r"클리비지", r"절단")),
            ("Deprotection", (r"deprotect", r"fmoc", r"탈보호")),
            ("Loading", (r"loading", r"로딩")),
            ("Swelling", (r"swelling", r"swell", r"팽윤")),
            ("Coupling", (r"coupling", r"coupl", r"kaiser", r"chloranil", r"커플링", r"카이저", r"클로라닐")),
        )
        for label, patterns in stage_hints:
            if _has(compact, patterns):
                stage = label; base = max(base, 0.35); matched.append("stage"); break

    confidence = base
    if action: confidence += 0.06
    if resolution != "Unknown": confidence += 0.05
    if pos is not None: confidence += 0.025
    if residue: confidence += 0.025
    confidence = round(min(confidence, 0.99), 3)

    # Distinctive issue language can be ML-safe without forcing extra user input.
    # Generic or ambiguous notes are preserved but excluded from ML/risk until review.
    parse_status = "auto_verified" if issue_type != "Other" and confidence >= 0.75 else "needs_review"

    severity = "Medium" if issue_type != "Other" else "Low"
    if _has(compact, (r"critical", r"severe", r"serious", r"major", r"심각", r"치명", r"매우\s*큰")):
        severity = "High"
    elif _has(compact, (r"minor", r"slight(?: issue| problem)?", r"small issue", r"경미", r"가벼운 문제")):
        severity = "Low"

    return {
        "stage": stage,
        "issue_type": issue_type,
        "action_taken": action,
        "resolution": resolution,
        "severity": severity,
        "position": pos,
        "residue": residue,
        "confidence": confidence,
        "parse_status": parse_status,
        "parser_version": PARSER_VERSION,
        "detected_language": _language(compact),
        "matched_fields": matched,
    }


__all__ = ["PARSER_VERSION", "parse_issue_note"]
