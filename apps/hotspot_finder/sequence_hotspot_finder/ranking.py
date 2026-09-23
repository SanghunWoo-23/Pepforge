from __future__ import annotations

"""Region-level hotspot prioritization.

The residue scorer and this region ranker are intentionally separate.  The
ranker turns residue-level evidence into non-overlapping local regions that are
easier to inspect and hand off to the Peptide Design Engine.  The returned
priority score is a heuristic ranking descriptor, not a binding probability,
affinity, or experimentally validated hotspot call.
"""

from typing import Any

import numpy as np
import pandas as pd

_CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
_NUMERIC_DEFAULTS = (
    "hotspot_score",
    "rule_score",
    "conservation_score",
    "structure_score",
    "supervised_score",
    "esm_embedding_score",
    "aromatic_flag",
    "positive_flag",
    "negative_flag",
    "polar_flag",
    "special_flag",
    "abs_charge",
    "hydrophobicity_norm",
)


def _position_column(df: pd.DataFrame) -> str | None:
    for name in ("original_position", "display_position", "model_position", "position"):
        if name in df.columns:
            return name
    return None


def _aa_column(df: pd.DataFrame) -> str | None:
    for name in ("input_token", "base_token", "model_token", "amino_acid", "residue"):
        if name in df.columns:
            return name
    return None


def _canonical_residue(row: pd.Series, aa_col: str) -> str:
    for name in ("model_token", "base_token", aa_col):
        raw = str(row.get(name, "") or "").strip().upper()
        if len(raw) == 1 and raw in _CANONICAL_AA:
            return raw
    return "X"


def _reason(region: pd.DataFrame, center_row: pd.Series, aa_col: str) -> str:
    charge = float(region["_charge_density"].mean()) if "_charge_density" in region else 0.0
    arom = float(region["_arom_density"].mean()) if "_arom_density" in region else 0.0
    local = float(region["_local_density"].mean()) if "_local_density" in region else 0.0
    bal = float(region["_local_balanced"].mean()) if "_local_balanced" in region else 0.0
    aa = _canonical_residue(center_row, aa_col)
    reasons: list[str] = []
    if charge >= 0.35:
        reasons.append("charged cluster")
    if arom >= 0.22:
        reasons.append("aromatic enrichment")
    if local >= 0.35:
        reasons.append("contact-like residue density")
    if bal >= 0.22:
        reasons.append("balanced local context")
    if aa in {"K", "R", "D", "E", "H"}:
        reasons.append("charged center")
    elif aa in {"F", "W", "Y"}:
        reasons.append("aromatic center")
    elif aa == "C":
        reasons.append("special Cys context")
    return "; ".join(dict.fromkeys(reasons)) or "local window/context evidence"


def rank_hotspot_regions(
    scored_df: pd.DataFrame,
    *,
    top_n: int = 30,
    window_size: int = 15,
    min_score: float = 0.0,
    overlap: int = 5,
) -> pd.DataFrame:
    """Rank non-overlapping hotspot regions from residue-level scored output.

    ``priority_score`` is designed for within-run prioritization only.  It is
    not calibrated across proteins and must not be interpreted as a binding
    probability, affinity, or experimental confidence.
    """

    columns = [
        "rank",
        "record_name",
        "region_start",
        "region_end",
        "region_sequence",
        "center_position",
        "center_residue",
        "hotspot_residues",
        "priority_score",
        "why_hotspot",
        "basis",
        "claim_guard",
    ]
    if scored_df is None or len(scored_df) == 0:
        return pd.DataFrame(columns=columns)

    work = scored_df.copy()
    pos_col = _position_column(work)
    aa_col = _aa_column(work)
    if not pos_col or not aa_col:
        return pd.DataFrame(columns=columns)

    work[pos_col] = pd.to_numeric(work[pos_col], errors="coerce")
    work = work.dropna(subset=[pos_col]).copy()
    if work.empty:
        return pd.DataFrame(columns=columns)
    work[pos_col] = work[pos_col].astype(int)

    for col in _NUMERIC_DEFAULTS:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0.0)
        else:
            work[col] = 0.0

    aa = work[aa_col].astype(str).str.upper()
    work["_is_yc"] = aa.isin(["Y", "C"]).astype(float)
    work["_is_strong_contact_like"] = aa.isin(["K", "R", "D", "E", "W", "F", "Y", "H", "C", "P"]).astype(float)

    work["_balanced_residue"] = (
        0.20 * work["positive_flag"]
        + 0.20 * work["negative_flag"]
        + 0.18 * work["aromatic_flag"]
        + 0.13 * work["polar_flag"]
        + 0.10 * work["abs_charge"].clip(0, 1)
        + 0.08 * work["_is_strong_contact_like"]
        + 0.06 * work["special_flag"]
        + 0.05 * (1.0 - (work["hydrophobicity_norm"] - 0.55).abs().clip(0, 1))
    )
    work["_balanced_residue"] = (work["_balanced_residue"] - 0.10 * work["_is_yc"]).clip(lower=0.0)

    top_n = max(1, int(top_n))
    window_size = max(5, int(window_size))
    half = max(2, min(8, window_size // 2))
    overlap = max(0, min(int(overlap), window_size - 1))
    min_distance = max(1, window_size - overlap)
    min_score = float(min_score)

    selected: list[dict[str, Any]] = []
    group_key = "record_name" if "record_name" in work.columns else None
    grouped = work.groupby(group_key, sort=False) if group_key else [("input", work)]

    for record, raw_group in grouped:
        g = raw_group.sort_values(pos_col).reset_index(drop=True).copy()
        raw = g["hotspot_score"].astype(float)
        if float(raw.max()) > float(raw.min()):
            g["_raw_norm"] = (raw - raw.min()) / (raw.max() - raw.min())
        else:
            g["_raw_norm"] = raw.clip(0, 1)
        g["_local_balanced"] = g["_balanced_residue"].rolling(2 * half + 1, center=True, min_periods=1).mean()
        g["_local_density"] = g["_is_strong_contact_like"].rolling(2 * half + 1, center=True, min_periods=1).mean()
        g["_charge_density"] = (g["positive_flag"] + g["negative_flag"]).rolling(2 * half + 1, center=True, min_periods=1).mean()
        g["_arom_density"] = g["aromatic_flag"].rolling(2 * half + 1, center=True, min_periods=1).mean()
        g["_composite"] = (
            0.30 * g["_raw_norm"]
            + 0.34 * g["_local_balanced"]
            + 0.16 * g["_local_density"]
            + 0.12 * g["_charge_density"]
            + 0.08 * g["_arom_density"]
        )
        isolated_yc = (g["_is_yc"] > 0) & (g["_local_density"] < 0.30) & (g["_charge_density"] < 0.15)
        g.loc[isolated_yc, "_composite"] *= 0.62

        centers = g if min_score <= 0 else g[g["_composite"] >= min_score]
        used: list[int] = []
        for _, center in centers.sort_values("_composite", ascending=False).iterrows():
            center_pos = int(center[pos_col])
            if any(abs(center_pos - prior) < min_distance for prior in used):
                continue
            region = g[(g[pos_col] >= center_pos - half) & (g[pos_col] <= center_pos + half)].copy()
            if region.empty:
                continue
            region["_token_score"] = (
                0.55 * region["_balanced_residue"]
                + 0.30 * region["_raw_norm"]
                + 0.15 * region["_is_strong_contact_like"]
            )
            reps = region.sort_values("_token_score", ascending=False).head(5).sort_values(pos_col)
            tokens = [f"({int(rr[pos_col])}{_canonical_residue(rr, aa_col)})" for _, rr in reps.iterrows()]
            if not tokens:
                continue

            region_start = int(region[pos_col].min())
            region_end = int(region[pos_col].max())
            region_sequence = "".join(_canonical_residue(rr, aa_col) for _, rr in region.sort_values(pos_col).iterrows())
            center_residue = _canonical_residue(center, aa_col)
            selected.append(
                {
                    "record_name": str(record),
                    "region_start": region_start,
                    "region_end": region_end,
                    "region_sequence": region_sequence,
                    "center_position": center_pos,
                    "center_residue": center_residue,
                    "hotspot_residues": ", ".join(tokens),
                    "priority_score": float(center["_composite"]),
                    "why_hotspot": _reason(region, center, aa_col),
                    "basis": "residue evidence + non-overlapping local window/context ranking",
                    "claim_guard": "Priority score is a within-run heuristic ranking descriptor, not a binding probability, affinity, or experimental hotspot validation.",
                }
            )
            used.append(center_pos)

    if not selected:
        return pd.DataFrame(columns=columns)

    selected.sort(key=lambda row: (-float(row["priority_score"]), str(row["record_name"]), int(row["center_position"])))
    selected = selected[:top_n]
    for idx, row in enumerate(selected, start=1):
        row["rank"] = idx
        row["priority_score"] = round(float(row["priority_score"]), 6)
    return pd.DataFrame(selected, columns=columns)


__all__ = ["rank_hotspot_regions"]
