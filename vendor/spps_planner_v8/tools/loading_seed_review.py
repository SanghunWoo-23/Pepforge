"""Review-gated tooling for loading-history seed transcription.

The tool is intentionally generic and contains no bundled experimental data. It helps
transcribe image/log sources into a staging CSV, compare candidates against the current
canonical seed, and promote only explicitly APPROVED, unambiguous, non-duplicate rows
into a *new* seed file for human review.

It never OCRs, guesses, or silently corrects source values.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suite_gui import experimental_data

CANONICAL_FIELDS = [
    "status", "date", "resin_type", "amino_acid_raw", "amino_acid_normalized",
    "aa_eq", "base", "base_eq", "coupling_reagent", "coupling_reagent_eq",
    "additive", "additive_eq", "loading_time_h", "loading_solvent",
    "capping_performed", "capping_method", "resin_sample_weight_mg", "absorbance",
    "loading_rate_mmol_g", "source_locator", "raw_note",
]
STAGING_FIELDS = [
    "review_state", "ambiguity_reason", "source_file", "source_locator",
    *[field for field in CANONICAL_FIELDS if field != "source_locator"],
]
REQUIRED_APPROVAL_FIELDS = (
    "date", "resin_type", "aa_eq", "base_eq", "loading_rate_mmol_g",
)
APPROVED = "APPROVED"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def _read_csv(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _amino_acid(row: Mapping[str, Any]) -> str:
    raw = _text(row.get("amino_acid_normalized")) or _text(row.get("amino_acid_raw"))
    return experimental_data.normalize_amino_acid(raw)


def source_locator(row: Mapping[str, Any], fallback: str = "") -> str:
    source_file = _text(row.get("source_file"))
    locator = _text(row.get("source_locator"))
    if source_file and locator and source_file.casefold() not in locator.casefold():
        return f"{source_file} | {locator}"
    return locator or source_file or fallback


def semantic_signature(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Mirror the loading seed semantic identity without changing values."""
    resin = _text(row.get("resin_type"))
    amino = _amino_acid(row)
    return (
        _text(row.get("date")),
        experimental_data.canonical_resin_key(resin),
        experimental_data.canonical_amino_acid_key(amino),
        _number(row.get("aa_eq")),
        _number(row.get("base_eq")),
        _number(row.get("absorbance")),
        _number(row.get("loading_rate_mmol_g")),
    )


def _row_issues(row: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    aa = _amino_acid(row)
    if not aa:
        issues.append("missing amino_acid")
    for field in REQUIRED_APPROVAL_FIELDS:
        if not _text(row.get(field)):
            issues.append(f"missing {field}")
    for field in ("aa_eq", "base_eq", "loading_rate_mmol_g"):
        if _text(row.get(field)) and _number(row.get(field)) is None:
            issues.append(f"invalid numeric {field}")
    for field in ("loading_time_h", "resin_sample_weight_mg", "absorbance"):
        if _text(row.get(field)) and _number(row.get(field)) is None:
            issues.append(f"invalid numeric {field}")
    if not source_locator(row):
        issues.append("missing source provenance")
    if _text(row.get("ambiguity_reason")):
        issues.append("source value marked ambiguous")
    return issues


def review_rows(staging_rows: Iterable[Mapping[str, Any]], canonical_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    canonical_index: dict[tuple[Any, ...], int] = {}
    for number, row in enumerate(canonical_rows, 2):
        canonical_index.setdefault(semantic_signature(row), number)

    report: list[dict[str, Any]] = []
    seen_stage: dict[tuple[Any, ...], int] = {}
    for number, raw in enumerate(staging_rows, 2):
        row = dict(raw)
        signature = semantic_signature(row)
        issues = _row_issues(row)
        duplicate_of = ""
        if signature in canonical_index:
            duplicate_of = f"canonical row {canonical_index[signature]}"
        elif signature in seen_stage:
            duplicate_of = f"staging row {seen_stage[signature]}"
        else:
            seen_stage[signature] = number

        state = _text(row.get("review_state")).upper()
        if issues:
            result = "AMBIGUOUS" if "source value marked ambiguous" in issues else "INVALID"
        elif duplicate_of:
            result = "DUPLICATE"
        elif state == APPROVED:
            result = "READY"
        else:
            result = "REVIEW"

        report.append({
            "staging_row": number,
            "review_result": result,
            "review_state": state or "PENDING",
            "issues": "; ".join(issues),
            "duplicate_of": duplicate_of,
            "source_locator": source_locator(row),
            "date": _text(row.get("date")),
            "resin_type": _text(row.get("resin_type")),
            "amino_acid": _amino_acid(row),
            "aa_eq": _text(row.get("aa_eq")),
            "base_eq": _text(row.get("base_eq")),
            "loading_rate_mmol_g": _text(row.get("loading_rate_mmol_g")),
        })
    return report


def review_staging(staging_path: str | Path, canonical_path: str | Path) -> list[dict[str, Any]]:
    _, staging = _read_csv(staging_path)
    _, canonical = _read_csv(canonical_path)
    return review_rows(staging, canonical)


def write_review_report(rows: Iterable[Mapping[str, Any]], output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "staging_row", "review_result", "review_state", "issues", "duplicate_of",
        "source_locator", "date", "resin_type", "amino_acid", "aa_eq", "base_eq",
        "loading_rate_mmol_g",
    ]
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return target


def write_template(output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=STAGING_FIELDS).writeheader()
    return target


def promote_staging(staging_path: str | Path, canonical_path: str | Path, output_seed: str | Path) -> dict[str, Any]:
    staging_fields, staging = _read_csv(staging_path)
    canonical_fields, canonical = _read_csv(canonical_path)
    report = review_rows(staging, canonical)
    ready_rows = {int(item["staging_row"]): item for item in report if item["review_result"] == "READY"}

    target = Path(output_seed)
    if target.resolve() == Path(canonical_path).resolve():
        raise ValueError("Refusing in-place seed overwrite. Promote to a new reviewable output path.")
    target.parent.mkdir(parents=True, exist_ok=True)

    output_fields = list(canonical_fields)
    if "source_locator" not in output_fields:
        insert_at = output_fields.index("raw_note") if "raw_note" in output_fields else len(output_fields)
        output_fields.insert(insert_at, "source_locator")
    for field in CANONICAL_FIELDS:
        if field not in output_fields:
            output_fields.append(field)

    # Work on copies so an exact duplicate can enrich a legacy canonical row with
    # newly recovered source provenance without creating another experiment row.
    canonical_out = [dict(row) for row in canonical]
    canonical_index: dict[tuple[Any, ...], int] = {}
    for idx, row in enumerate(canonical_out):
        canonical_index.setdefault(semantic_signature(row), idx)

    enriched_duplicates = 0
    for row_number, row in enumerate(staging, 2):
        item = report[row_number - 2]
        if item["review_result"] != "DUPLICATE":
            continue
        sig = semantic_signature(row)
        idx = canonical_index.get(sig)
        if idx is None:
            continue
        incoming = source_locator(row)
        current = _text(canonical_out[idx].get("source_locator"))
        if incoming and not current:
            canonical_out[idx]["source_locator"] = incoming
            enriched_duplicates += 1

    promoted = 0
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        for row in canonical_out:
            writer.writerow({field: row.get(field, "") for field in output_fields})
        for row_number, row in enumerate(staging, 2):
            if row_number not in ready_rows:
                continue
            clean = {field: row.get(field, "") for field in output_fields}
            clean["status"] = _text(clean.get("status")) or "parsed"
            clean["amino_acid_normalized"] = _amino_acid(row)
            if not _text(clean.get("amino_acid_raw")):
                clean["amino_acid_raw"] = clean["amino_acid_normalized"]
            clean["source_locator"] = source_locator(row)
            writer.writerow(clean)
            promoted += 1

    return {
        "canonical_rows": len(canonical),
        "staging_rows": len(staging),
        "promoted_rows": promoted,
        "enriched_duplicates": enriched_duplicates,
        "output_rows": len(canonical) + promoted,
        "output": str(target),
        "report": report,
        "staging_fields": staging_fields,
    }


def _print_summary(report: Iterable[Mapping[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for row in report:
        key = _text(row.get("review_result")) or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    ordered = " | ".join(f"{key}={counts[key]}" for key in sorted(counts))
    print(ordered or "No staging rows")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review-gated loading seed staging tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_template = sub.add_parser("template", help="Create an empty transcription staging CSV")
    p_template.add_argument("output")

    p_review = sub.add_parser("review", help="Diff/validate staging rows against the canonical seed")
    p_review.add_argument("staging")
    p_review.add_argument("canonical")
    p_review.add_argument("--report", required=True)

    p_promote = sub.add_parser("promote", help="Write a new seed containing READY staging rows")
    p_promote.add_argument("staging")
    p_promote.add_argument("canonical")
    p_promote.add_argument("--output", required=True)
    p_promote.add_argument("--report")

    args = parser.parse_args(argv)
    if args.command == "template":
        print(write_template(args.output))
        return 0
    if args.command == "review":
        report = review_staging(args.staging, args.canonical)
        write_review_report(report, args.report)
        _print_summary(report)
        return 0 if all(row["review_result"] not in {"INVALID", "AMBIGUOUS"} for row in report) else 2
    if args.command == "promote":
        result = promote_staging(args.staging, args.canonical, args.output)
        if args.report:
            write_review_report(result["report"], args.report)
        _print_summary(result["report"])
        print(f"promoted={result['promoted_rows']} output={result['output']}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
