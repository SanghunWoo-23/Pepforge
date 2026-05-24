#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External result parsers for Peptide Design Engine continual ML.

Purpose
-------
Convert AF3 output folders and PRODIGY txt/csv outputs into canonical CSV files
that can be appended into data/training_data.csv by data_manager.py.

Design principles
-----------------
- Standard-library only: EXE/PyInstaller friendly.
- Conservative parsing: never delete raw values; preserve unknown fields where useful.
- Candidate matching: infer candidate_id from file/folder names, or from a user-provided
  mapping CSV with candidate_id/sequence/target_id columns.
- Safe for heterogeneous AF3/PRODIGY exports; unsupported files are skipped, not fatal.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

AA = set("ACDEFGHIKLMNPQRSTVWY")


def clean_sequence(seq: str) -> str:
    return "".join(c for c in str(seq).upper() if c in AA)


def read_csv(path: str | Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: List[Dict[str, Any]]) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        # still write a useful empty template
        keys = ["candidate_id", "sequence", "clean_sequence", "target_id", "source_file", "source_type", "notes"]
    else:
        keys: List[str] = []
        preferred = [
            "candidate_id", "sequence", "clean_sequence", "target_id", "design_mode",
            "source_file", "source_type",
            "af3_confidence", "af3_iptm", "af3_ptm", "af3_ranking_score",
            "prodigy_delta_g", "prodigy_kd", "docking_score",
            "hplc_purity", "ms_confirmed", "experimental_binding", "activity_label", "notes",
        ]
        for k in preferred:
            if any(k in r for r in rows) and k not in keys:
                keys.append(k)
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    return str(path)


def _norm(s: Any) -> str:
    return str(s or "").strip()


def normalize_candidate_name(name: str) -> str:
    """Infer a candidate id from a filename/folder name.

    Examples:
    - PDE_0001_model_0.cif -> PDE_0001
    - candidate-12_rank_001.json -> candidate-12
    """
    base = Path(name).stem
    # strong PDE id
    m = re.search(r"(PDE[_-]?[A-Za-z0-9]+)", base, re.IGNORECASE)
    if m:
        return m.group(1).replace("-", "_")
    # remove common result suffixes
    base = re.sub(r"(_?model[_-]?\d+|_?rank[_-]?\d+|_?seed[_-]?\d+|_?scores?|_?summary|_?result)$", "", base, flags=re.I)
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_")
    return base or Path(name).stem


def load_mapping(mapping_csv: str | Path | None = None) -> Dict[str, Dict[str, str]]:
    """Load candidate mapping CSV.

    Supported columns:
    - candidate_id
    - sequence / clean_sequence / peptide / seq
    - target_id
    - source_name / file / folder / af3_folder / prodigy_file

    Returns a dict keyed by candidate_id and any source-name aliases.
    """
    if not mapping_csv:
        return {}
    path = Path(mapping_csv)
    if not path.exists():
        return {}
    rows = read_csv(path)
    mapping: Dict[str, Dict[str, str]] = {}
    for r in rows:
        cid = _norm(r.get("candidate_id") or r.get("id") or r.get("name"))
        seq = _norm(r.get("sequence") or r.get("clean_sequence") or r.get("peptide") or r.get("seq"))
        target = _norm(r.get("target_id") or r.get("target") or r.get("receptor") or r.get("binder_target"))
        aliases = [
            cid,
            _norm(r.get("source_name")),
            _norm(r.get("file")),
            _norm(r.get("filename")),
            _norm(r.get("folder")),
            _norm(r.get("af3_folder")),
            _norm(r.get("prodigy_file")),
        ]
        record = {
            "candidate_id": cid,
            "sequence": seq,
            "clean_sequence": _norm(r.get("clean_sequence") or clean_sequence(seq)),
            "target_id": target,
        }
        for a in aliases:
            if a:
                mapping[a] = record
                mapping[Path(a).stem] = record
                mapping[normalize_candidate_name(a)] = record
    return mapping


def apply_mapping(row: Dict[str, Any], mapping: Dict[str, Dict[str, str]], source_path: str | Path) -> Dict[str, Any]:
    candidates = [
        _norm(row.get("candidate_id")),
        normalize_candidate_name(Path(source_path).name),
        normalize_candidate_name(Path(source_path).parent.name),
        Path(source_path).stem,
        Path(source_path).parent.name,
    ]
    match = None
    for key in candidates:
        if key and key in mapping:
            match = mapping[key]
            break
    if match:
        for k in ["candidate_id", "sequence", "clean_sequence", "target_id"]:
            if not _norm(row.get(k)) and _norm(match.get(k)):
                row[k] = match[k]
    if not _norm(row.get("candidate_id")):
        row["candidate_id"] = candidates[1] or candidates[2]
    if not _norm(row.get("clean_sequence")):
        row["clean_sequence"] = clean_sequence(_norm(row.get("sequence")))
    return row


def _first_number(obj: Any, keys: Iterable[str]) -> Optional[float]:
    """Recursively find first numeric value for possible key names."""
    keyset = {k.lower() for k in keys}

    def rec(x: Any) -> Optional[float]:
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower() in keyset:
                    val = to_float(v)
                    if val is not None:
                        return val
            for v in x.values():
                out = rec(v)
                if out is not None:
                    return out
        elif isinstance(x, list):
            for v in x:
                out = rec(v)
                if out is not None:
                    return out
        return None

    return rec(obj)


def to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        if math.isfinite(float(x)):
            return float(x)
        return None
    s = str(x).strip()
    if not s:
        return None
    # handle 1.2e-6, -8.4, "Kd=1.2e-6"
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def parse_af3_json(path: str | Path, mapping: Optional[Dict[str, Dict[str, str]]] = None) -> Optional[Dict[str, Any]]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    row: Dict[str, Any] = {
        "candidate_id": normalize_candidate_name(path.parent.name if path.parent.name else path.stem),
        "source_file": str(path),
        "source_type": "AF3",
        "notes": "parsed from AF3 JSON",
    }

    # Common AlphaFold/AF3 score variants.
    candidates = {
        "af3_iptm": ["iptm", "ipTM", "interface_ptm", "interface_pTM"],
        "af3_ptm": ["ptm", "pTM"],
        "af3_ranking_score": ["ranking_score", "ranking_confidence", "rank_score"],
        "af3_confidence": ["confidence", "mean_plddt", "plddt", "mean_confidence_score"],
    }
    for out_key, possible in candidates.items():
        val = _first_number(data, possible)
        if val is not None:
            row[out_key] = val

    # Some AF3 outputs use fraction scale for ipTM/pTM; leave unchanged.
    row = apply_mapping(row, mapping or {}, path)
    # If no useful score was found, still keep the row only if mapping exists.
    if not any(k in row for k in ["af3_iptm", "af3_ptm", "af3_ranking_score", "af3_confidence"]) and not mapping:
        return None
    return row


def parse_af3_csv(path: str | Path, mapping: Optional[Dict[str, Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        src_rows = read_csv(path)
    except Exception:
        return rows
    aliases = {
        "iptm": "af3_iptm", "ipTM": "af3_iptm", "interface_ptm": "af3_iptm",
        "ptm": "af3_ptm", "pTM": "af3_ptm",
        "ranking_score": "af3_ranking_score", "ranking_confidence": "af3_ranking_score",
        "confidence": "af3_confidence", "mean_plddt": "af3_confidence", "plddt": "af3_confidence",
        "seq": "sequence", "peptide": "sequence", "target": "target_id", "id": "candidate_id", "name": "candidate_id",
    }
    for r in src_rows:
        out: Dict[str, Any] = {"source_file": str(path), "source_type": "AF3", "notes": "parsed from AF3 CSV"}
        for k, v in r.items():
            kk = aliases.get(str(k).strip(), aliases.get(str(k).strip().lower(), str(k).strip()))
            out[kk] = v
        out = apply_mapping(out, mapping or {}, path)
        rows.append(out)
    return rows


def parse_af3_folder(folder: str | Path, output_csv: str | Path, mapping_csv: str | Path | None = None) -> Dict[str, Any]:
    """Parse an AF3 output folder into a canonical CSV."""
    folder = Path(folder)
    mapping = load_mapping(mapping_csv)
    rows: List[Dict[str, Any]] = []

    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        low = p.name.lower()
        if p.suffix.lower() == ".json" and any(token in low for token in ["score", "summary", "ranking", "confidence", "result"]):
            row = parse_af3_json(p, mapping)
            if row:
                rows.append(row)
        elif p.suffix.lower() == ".csv":
            # Accept CSVs inside AF3 folder if they look score-ish
            parsed = parse_af3_csv(p, mapping)
            rows.extend(parsed)

    # Deduplicate weakly by candidate + source file
    dedup: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        key = (_norm(r.get("candidate_id")), _norm(r.get("source_file")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    write_csv(output_csv, dedup)
    return {"output_csv": str(output_csv), "rows": len(dedup), "source": str(folder), "type": "AF3"}


PRODIGY_PATTERNS = {
    "prodigy_delta_g": [
        r"Predicted\s+binding\s+affinity\s*\(.*?kcal.*?\)\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        r"binding\s+affinity\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        r"delta\s*g\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        r"ΔG\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        r"\bDG\b\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
    ],
    "prodigy_kd": [
        r"Predicted\s+dissociation\s+constant.*?[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        r"\bKd\b\s*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
        r"dissociation\s+constant\s*[:=]\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
    ],
}


def parse_prodigy_txt(path: str | Path, mapping: Optional[Dict[str, Dict[str, str]]] = None) -> Optional[Dict[str, Any]]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    row: Dict[str, Any] = {
        "candidate_id": normalize_candidate_name(path.name),
        "source_file": str(path),
        "source_type": "PRODIGY",
        "notes": "parsed from PRODIGY text",
    }
    for out_key, patterns in PRODIGY_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, text, flags=re.I)
            if m:
                val = to_float(m.group(1))
                if val is not None:
                    row[out_key] = val
                    break
    row = apply_mapping(row, mapping or {}, path)
    if not any(k in row for k in ["prodigy_delta_g", "prodigy_kd"]):
        return None
    return row


def parse_prodigy_csv(path: str | Path, mapping: Optional[Dict[str, Dict[str, str]]] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        src_rows = read_csv(path)
    except Exception:
        return rows
    aliases = {
        "delta_g": "prodigy_delta_g", "dg": "prodigy_delta_g", "binding_affinity": "prodigy_delta_g",
        "predicted_binding_affinity": "prodigy_delta_g",
        "kd": "prodigy_kd", "dissociation_constant": "prodigy_kd",
        "seq": "sequence", "peptide": "sequence", "target": "target_id", "id": "candidate_id", "name": "candidate_id",
    }
    for r in src_rows:
        out: Dict[str, Any] = {"source_file": str(path), "source_type": "PRODIGY", "notes": "parsed from PRODIGY CSV"}
        for k, v in r.items():
            kk = aliases.get(str(k).strip(), aliases.get(str(k).strip().lower(), str(k).strip()))
            out[kk] = v
        out = apply_mapping(out, mapping or {}, path)
        rows.append(out)
    return rows


def parse_prodigy_path(input_path: str | Path, output_csv: str | Path, mapping_csv: str | Path | None = None) -> Dict[str, Any]:
    """Parse a PRODIGY txt/csv file or folder into a canonical CSV."""
    p = Path(input_path)
    mapping = load_mapping(mapping_csv)
    rows: List[Dict[str, Any]] = []
    files = [p] if p.is_file() else sorted([x for x in p.rglob("*") if x.is_file()])
    for f in files:
        suffix = f.suffix.lower()
        if suffix == ".csv":
            rows.extend(parse_prodigy_csv(f, mapping))
        elif suffix in {".txt", ".out", ".log"} or "prodigy" in f.name.lower():
            row = parse_prodigy_txt(f, mapping)
            if row:
                rows.append(row)

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        key = (_norm(r.get("candidate_id")), _norm(r.get("source_file")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    write_csv(output_csv, dedup)
    return {"output_csv": str(output_csv), "rows": len(dedup), "source": str(input_path), "type": "PRODIGY"}


def parse_and_import_af3(folder: str | Path, training_db: str | Path, parsed_csv: str | Path | None = None, mapping_csv: str | Path | None = None) -> Dict[str, Any]:
    """Parse AF3 folder then append to training DB."""
    if parsed_csv is None:
        parsed_csv = Path(training_db).parent / "parsed_af3_latest.csv"
    parse_result = parse_af3_folder(folder, parsed_csv, mapping_csv=mapping_csv)
    import data_manager
    append_result = data_manager.append_training_csvs([str(parsed_csv)], str(training_db))
    return {"parse": parse_result, "append": append_result}


def parse_and_import_prodigy(input_path: str | Path, training_db: str | Path, parsed_csv: str | Path | None = None, mapping_csv: str | Path | None = None) -> Dict[str, Any]:
    """Parse PRODIGY txt/csv/folder then append to training DB."""
    if parsed_csv is None:
        parsed_csv = Path(training_db).parent / "parsed_prodigy_latest.csv"
    parse_result = parse_prodigy_path(input_path, parsed_csv, mapping_csv=mapping_csv)
    import data_manager
    append_result = data_manager.append_training_csvs([str(parsed_csv)], str(training_db))
    return {"parse": parse_result, "append": append_result}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Parse AF3/PRODIGY outputs into Peptide Design Engine training CSV.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_af3 = sub.add_parser("af3")
    ap_af3.add_argument("folder")
    ap_af3.add_argument("--output-csv", required=True)
    ap_af3.add_argument("--mapping-csv", default=None)

    ap_prod = sub.add_parser("prodigy")
    ap_prod.add_argument("input")
    ap_prod.add_argument("--output-csv", required=True)
    ap_prod.add_argument("--mapping-csv", default=None)

    args = ap.parse_args()
    if args.cmd == "af3":
        print(parse_af3_folder(args.folder, args.output_csv, args.mapping_csv))
    elif args.cmd == "prodigy":
        print(parse_prodigy_path(args.input, args.output_csv, args.mapping_csv))
