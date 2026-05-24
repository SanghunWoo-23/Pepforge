#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Continual-learning data manager for Peptide Design Engine.

This module intentionally uses only the Python standard library so it remains
friendly to PyInstaller/EXE packaging. It appends AF3, PRODIGY, docking, and
experimental CSV exports into one canonical training_data.csv without deleting
unknown columns.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Any

CANONICAL_COLUMNS = [
    "candidate_id", "sequence", "clean_sequence", "target_id", "design_mode",
    "source_file", "source_type",
    "af3_confidence", "af3_iptm", "af3_ptm", "af3_ranking_score",
    "prodigy_delta_g", "prodigy_kd", "docking_score",
    "hplc_purity", "ms_confirmed", "experimental_binding", "activity_label",
    "notes",
]

ALIASES = {
    "seq": "sequence", "peptide": "sequence", "peptide_sequence": "sequence", "candidate_sequence": "sequence",
    "clean_peptide_sequence": "clean_sequence", "surrogate_sequence": "clean_sequence",
    "id": "candidate_id", "name": "candidate_id", "rank_id": "candidate_id",
    "iptm": "af3_iptm", "ipTM": "af3_iptm", "ptm": "af3_ptm", "pTM": "af3_ptm",
    "ranking_score": "af3_ranking_score", "confidence": "af3_confidence",
    "delta_g": "prodigy_delta_g", "dg": "prodigy_delta_g", "binding_energy": "prodigy_delta_g",
    "kd": "prodigy_kd", "Kd": "prodigy_kd",
    "score": "docking_score", "vina_score": "docking_score", "rosetta_score": "docking_score",
    "purity": "hplc_purity", "hplc": "hplc_purity",
    "ms": "ms_confirmed", "lcms_confirmed": "ms_confirmed", "maldi_confirmed": "ms_confirmed",
    "binding": "experimental_binding", "activity": "experimental_binding", "label": "activity_label",
}


def normalize_key(k: str) -> str:
    kk = str(k).strip().replace(" ", "_").replace("-", "_")
    return ALIASES.get(kk, ALIASES.get(kk.lower(), kk))


def infer_source_type(path: str, row: Dict[str, Any]) -> str:
    name = Path(path).name.lower()
    keys = {normalize_key(k) for k in row.keys()}
    if "af3" in name or {"af3_iptm", "af3_ptm", "af3_ranking_score"} & keys:
        return "AF3"
    if "prodigy" in name or {"prodigy_delta_g", "prodigy_kd"} & keys:
        return "PRODIGY"
    if "dock" in name or "docking_score" in keys:
        return "DOCKING"
    if "experiment" in name or {"experimental_binding", "hplc_purity", "ms_confirmed"} & keys:
        return "EXPERIMENT"
    return "MIXED"


def clean_sequence(seq: str) -> str:
    aa = set("ACDEFGHIKLMNPQRSTVWY")
    return "".join(c for c in str(seq).upper() if c in aa)


def stable_candidate_id(row: Dict[str, Any]) -> str:
    base = "|".join(str(row.get(k, "")) for k in ["sequence", "clean_sequence", "target_id", "source_type"])
    return "PDE_" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:12].upper()


def read_csv(path: str | Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: List[Dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(CANONICAL_COLUMNS)
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def normalize_row(row: Dict[str, Any], source_path: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        out[normalize_key(k)] = v
    out.setdefault("source_file", Path(source_path).name)
    out.setdefault("source_type", infer_source_type(source_path, row))
    seq = str(out.get("sequence", "")).strip()
    if not seq and out.get("clean_sequence"):
        seq = str(out.get("clean_sequence"))
    out["sequence"] = seq
    out.setdefault("clean_sequence", clean_sequence(seq))
    if not out.get("candidate_id"):
        out["candidate_id"] = stable_candidate_id(out)
    return out


def append_training_csvs(input_paths: Iterable[str], training_db: str = "data/training_data.csv") -> Dict[str, Any]:
    db = Path(training_db)
    existing = read_csv(db) if db.exists() else []
    all_rows = [dict(r) for r in existing]
    seen = {(r.get("candidate_id", ""), r.get("source_file", "")) for r in all_rows}
    added = 0
    for path in input_paths:
        for raw in read_csv(path):
            row = normalize_row(raw, path)
            key = (row.get("candidate_id", ""), row.get("source_file", ""))
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)
            added += 1
    write_csv(db, all_rows)
    return {"training_db": str(db), "added": added, "total": len(all_rows)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--training-db", default="data/training_data.csv")
    args = ap.parse_args()
    print(append_training_csvs(args.inputs, args.training_db))
