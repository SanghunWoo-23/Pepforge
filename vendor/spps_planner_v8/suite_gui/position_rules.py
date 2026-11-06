"""C-terminal position rules shared by Generate and Apply Change.

Positions are counted across every real synthesis unit (AA, d-AA, linker,
chemical, label, and tag) in the visible C-to-N Plan order.
"""
from __future__ import annotations

import re
from typing import Any


def value(variable: Any, default: Any = "") -> Any:
    try:
        return variable.get()
    except Exception:
        return default


def number(raw: Any, default: float = 0.0) -> float:
    try:
        return float(str(raw).strip())
    except Exception:
        return default


def parse_ranges(text: str) -> list[tuple[int, int, float]]:
    """Parse ``7:2`` and ``4-7:2`` rules; blank means no override."""
    if not str(text or "").strip():
        return []
    rules: list[tuple[int, int, float]] = []
    for part in re.split(r"[,;]+", str(text)):
        match = re.fullmatch(
            r"\s*(\d+)(?:\s*-\s*(\d+))?\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*",
            part,
        )
        if not match:
            continue
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        rules.append((min(start, end), max(start, end), float(match.group(3))))
    return rules


def range_value(position: int, rules: list[tuple[int, int, float]], fallback: float) -> float:
    for start, end, result in rules:
        if start <= position <= end:
            return result
    return fallback


def sequence_unit_count(gui: Any) -> int:
    sequence = str(value(getattr(gui, "pm_sequence", None), "") or "").strip()
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(sequence)
        return len(list(parsed.core_tokens or [])) + (
            1 if str(parsed.nterm or "").strip() else 0
        )
    except Exception:
        return len(re.findall(r"[A-Za-z]", sequence))


def is_fmoc_removal(row: dict[str, Any]) -> bool:
    # A real terminal chemical row can legitimately mention the preceding
    # "final Fmoc removal" in its protocol note.  Classification must be based
    # on the unit/phase itself; searching the whole note deleted Ac, Pal and
    # label rows from the visible Project Manager Plan.
    unit_key = re.sub(
        r"[^a-z0-9]+", "", str(row.get("Unit name", "") or "").lower()
    )
    phase_key = re.sub(
        r"[^a-z0-9]+", "", str(row.get("Phase", "") or "").lower()
    )
    return unit_key in {"fmocremoval", "finalfmocremoval"} or (
        not unit_key and "deprotectiononly" in phase_key
    )


def is_position_unit(row: dict[str, Any]) -> bool:
    return bool(str(row.get("Unit name", "") or "").strip()) and not is_fmoc_removal(row)


def apply_generated(gui: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply eq/repeat ranges to generated rows without adding synthetic rows."""
    result = [dict(row) for row in rows if not is_fmoc_removal(row)]
    expected = sequence_unit_count(gui)
    indices = [index for index, row in enumerate(result) if is_position_unit(row)]
    if expected >= 0 and len(indices) > expected:
        remove = set(indices[: len(indices) - expected])
        result = [row for index, row in enumerate(result) if index not in remove]
        indices = [index for index, row in enumerate(result) if is_position_unit(row)]

    eq_enabled = bool(value(getattr(gui, "use_position_aa_eq", None), True))
    repeat_enabled = bool(value(getattr(gui, "use_position_doubling", None), True))
    eq_rules = parse_ranges(value(getattr(gui, "position_aa_eq_rules", None), ""))
    repeat_rules = parse_ranges(value(getattr(gui, "position_doubling_rules", None), ""))
    follows = bool(value(getattr(gui, "reagent_eq_follows_coupling_eq", None), True))
    offset = max(0, expected - len(indices))

    for ordinal, row_index in enumerate(indices, 1):
        position = offset + ordinal
        row = result[row_index]
        if eq_enabled:
            fallback = number(
                row.get("Unit eq"),
                number(value(getattr(gui, "coupling_eq", None), 5), 5),
            )
            eq = range_value(position, eq_rules, fallback)
            row["Unit eq"] = str(int(eq)) if float(eq).is_integer() else str(eq)
            if follows:
                for name_column, eq_column in (
                    ("Reagent 1", "R1 eq"),
                    ("Reagent 2 / catalyst", "R2 eq"),
                    ("Base", "Base eq"),
                ):
                    if str(row.get(name_column, "")).strip():
                        row[eq_column] = row["Unit eq"]
        if repeat_enabled:
            repeat = int(round(range_value(position, repeat_rules, 1.0)))
            row["Repeat"] = str(max(1, repeat))

    for number_, row in enumerate(result, 1):
        row["No"] = str(number_)
    return result


def desired_repeats(gui: Any, rows: list[dict[str, Any]]) -> dict[int, int]:
    """Return row-index to current repeat count for Apply Change."""
    indices = [index for index, row in enumerate(rows) if is_position_unit(row)]
    expected = sequence_unit_count(gui)
    offset = max(0, expected - len(indices))
    enabled = bool(value(getattr(gui, "use_position_doubling", None), True))
    rules = parse_ranges(value(getattr(gui, "position_doubling_rules", None), ""))
    result: dict[int, int] = {}
    for ordinal, row_index in enumerate(indices, 1):
        repeat = range_value(offset + ordinal, rules, 1.0) if enabled else 1.0
        result[row_index] = max(1, int(round(repeat)))
    return result


# Stable compatibility names for tests and downstream extensions.
_apply_generated_position_rules = apply_generated
_parse_ranges = lambda text, _default=None: parse_ranges(text)
_range_value = range_value
_sequence_unit_count = sequence_unit_count
_is_position_unit_row = is_position_unit


__all__ = [
    "apply_generated",
    "desired_repeats",
    "is_position_unit",
    "parse_ranges",
    "range_value",
    "sequence_unit_count",
]
