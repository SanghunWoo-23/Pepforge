"""Read-only analytics and data-health reporting for SPPS Planner V6.

The experimental DB module owns persistence/import.  This module owns derived
operator/developer reports so read-heavy reporting can evolve independently of
record writes and schema migration.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def v6_analytics(db_path: str | Path | None = None) -> dict[str, Any]:
    from suite_gui import experimental_data as data
    from suite_gui.decision_support import analytics_snapshot
    return analytics_snapshot(
        loading_rows=data.list_records("loading", db_path),
        outcome_rows=data.list_records("outcome", db_path),
        issue_rows=data.list_records("issue", db_path),
        cleavage_rows=data.list_records("cleavage", db_path),
    )


def quality_findings(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    from suite_gui import experimental_data as data
    from suite_gui.decision_support import record_quality_issues
    return record_quality_issues(
        loading_rows=data.list_records("loading", db_path),
        outcome_rows=data.list_records("outcome", db_path),
        issue_rows=data.list_records("issue", db_path),
    )


def data_health(db_path: str | Path | None = None) -> dict[str, Any]:
    """Return auditable quality/consistency metrics, never a fabricated success rate."""
    from suite_gui import experimental_data as data

    data.initialize(db_path)
    with data._connect(db_path) as con:
        def status_counts(table: str) -> dict[str, int]:
            rows = con.execute(f"SELECT status,COUNT(*) AS n FROM {table} GROUP BY status").fetchall()
            return {str(row["status"]): int(row["n"]) for row in rows}

        loading_total = int(con.execute("SELECT COUNT(*) FROM loading_records").fetchone()[0])
        cleavage_total = int(con.execute("SELECT COUNT(*) FROM cleavage_records").fetchone()[0])
        sequence_total = int(con.execute("SELECT COUNT(*) FROM synthesis_sequence_records").fetchone()[0])
        usage_total = int(con.execute("SELECT COUNT(*) FROM cleavage_usage_records").fetchone()[0])
        outcome_total = int(con.execute("SELECT COUNT(*) FROM experimental_outcomes").fetchone()[0])
        issue_total = int(con.execute("SELECT COUNT(*) FROM synthesis_issue_records").fetchone()[0])
        usage_unit_review = int(con.execute("SELECT COUNT(*) FROM cleavage_usage_records WHERE unit_review_required=1").fetchone()[0])
        usage_normalized = int(con.execute("SELECT COUNT(*) FROM cleavage_usage_records WHERE cocktail_ml_per_mmol IS NOT NULL").fetchone()[0])
        missing_keys = {
            "loading": int(con.execute("SELECT COUNT(*) FROM loading_records WHERE resin_key='' OR amino_acid_key='' ").fetchone()[0]),
            "cleavage": int(con.execute("SELECT COUNT(*) FROM cleavage_records WHERE product<>'' AND product_key='' ").fetchone()[0]),
            "sequence": int(con.execute("SELECT COUNT(*) FROM synthesis_sequence_records WHERE product_key='' OR sequence_key='' ").fetchone()[0]),
        }
        sequence_products = int(con.execute("SELECT COUNT(DISTINCT product_key) FROM synthesis_sequence_records WHERE product_key<>''").fetchone()[0])
        linked_cleavage = int(con.execute("""
            SELECT COUNT(*) FROM cleavage_records c
            WHERE c.product_key<>'' AND EXISTS (
                SELECT 1 FROM synthesis_sequence_records s WHERE s.product_key=c.product_key
            )
        """).fetchone()[0])
        repeated_loading_groups = int(con.execute("""
            SELECT COUNT(*) FROM (
                SELECT resin_key,amino_acid_key FROM loading_records
                WHERE resin_key<>'' AND amino_acid_key<>''
                GROUP BY resin_key,amino_acid_key HAVING COUNT(*)>=2
            )
        """).fetchone()[0])
        loading_rows = [dict(row) for row in con.execute("""
            SELECT resin_key,amino_acid_key,loading_rate_mmol_g FROM loading_records
            WHERE loading_rate_mmol_g IS NOT NULL AND resin_key<>'' AND amino_acid_key<>''
        """).fetchall()]
        cleavage_rows = [dict(row) for row in con.execute("""
            SELECT product_key,cleavage_eq,cleavage_time_h FROM cleavage_records
            WHERE product_key<>'' AND cleavage_eq IS NOT NULL AND cleavage_time_h IS NOT NULL
        """).fetchall()]
        explicit_edt = 0
        for row in con.execute("SELECT other_scavengers_json FROM cleavage_records").fetchall():
            try:
                parsed = json.loads(str(row[0] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = {}
            if isinstance(parsed, dict) and any(
                str(k).strip().casefold() == "edt" and data._float(v) not in (None, 0)
                for k, v in parsed.items()
            ):
                explicit_edt += 1

        groups: dict[tuple[str, str], list[float]] = {}
        for row in loading_rows:
            groups.setdefault((row["resin_key"], row["amino_acid_key"]), []).append(float(row["loading_rate_mmol_g"]))
        errors: list[float] = []
        for values in groups.values():
            if len(values) < 2:
                continue
            for index, observed in enumerate(values):
                peers = values[:index] + values[index + 1:]
                prediction = sorted(peers)[len(peers) // 2]
                errors.append(abs(observed - prediction))
        loading_mae = (sum(errors) / len(errors)) if errors else None

        cgroups: dict[str, list[tuple[float, float]]] = {}
        for row in cleavage_rows:
            cgroups.setdefault(str(row["product_key"]), []).append((float(row["cleavage_eq"]), float(row["cleavage_time_h"])))
        agree = 0
        evaluated = 0
        for values in cgroups.values():
            if len(values) < 2:
                continue
            counts: dict[tuple[float, float], int] = {}
            for value in values:
                counts[value] = counts.get(value, 0) + 1
            mode = max(counts, key=counts.get)
            agree += sum(value == mode for value in values)
            evaluated += len(values)
        cleavage_agreement = (100.0 * agree / evaluated) if evaluated else None

        def lifecycle_counts(table: str) -> dict[str, int]:
            rows = con.execute(f"SELECT record_state,COUNT(*) AS n FROM {table} GROUP BY record_state").fetchall()
            return {str(row["record_state"] or "draft"): int(row["n"]) for row in rows}

        lifecycle = {
            "loading": lifecycle_counts("loading_records"),
            "cleavage": lifecycle_counts("cleavage_records"),
            "outcome": lifecycle_counts("experimental_outcomes"),
            "issue": lifecycle_counts("synthesis_issue_records"),
        }
        status = {
            "loading": status_counts("loading_records"),
            "cleavage": status_counts("cleavage_records"),
            "sequence": status_counts("synthesis_sequence_records"),
            "cleavage_usage": status_counts("cleavage_usage_records"),
            "outcome": status_counts("experimental_outcomes"),
            "issue": status_counts("synthesis_issue_records"),
        }

    quality = quality_findings(db_path)
    return {
        "counts": {"loading": loading_total, "cleavage": cleavage_total, "sequence": sequence_total, "cleavage_usage": usage_total, "outcome": outcome_total, "issue": issue_total},
        "cleavage_usage_unit_review_required": usage_unit_review,
        "cleavage_usage_normalized_records": usage_normalized,
        "status_counts": status,
        "missing_canonical_keys": missing_keys,
        "sequence_products": sequence_products,
        "cleavage_records_linked_to_sequence_product": linked_cleavage,
        "repeated_loading_groups": repeated_loading_groups,
        "explicit_edt_records": explicit_edt,
        "loading_leave_one_out_mae_mmol_g": loading_mae,
        "loading_leave_one_out_evaluated": len(errors),
        "cleavage_eq_time_replay_agreement_pct": cleavage_agreement,
        "cleavage_eq_time_replay_evaluated": evaluated,
        "record_state_counts": lifecycle,
        "quality_findings_count": len(quality),
        "quality_findings": quality[:100],
    }


__all__ = ["v6_analytics", "quality_findings", "data_health"]
