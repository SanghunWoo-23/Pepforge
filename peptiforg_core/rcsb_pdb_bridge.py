from __future__ import annotations

"""RCSB PDB search and download bridge for Pepforge v2.6.0.

This module uses public RCSB PDB programmatic services:
- Search API for text and sequence-based lookup
- Data API for basic entry metadata
- File download service for PDB/mmCIF coordinate files

It uses only the Python standard library so the public release remains lightweight.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import json
import re
import urllib.error
import urllib.parse
import urllib.request

RCSB_BRIDGE_VERSION = "2.6.0"
RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_DATA_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download/{pdb_id}.{fmt}"

_PDB_ID_RE = re.compile(r"^[0-9][A-Za-z0-9]{3}$")
_AA_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYBXZJUO\\s\\n\\r\\t>]+$", re.I)


def _json_post(url: str, payload: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Pepforge/2.6.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _json_get(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Pepforge/2.6.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _text_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"Accept": "text/plain,*/*", "User-Agent": "Pepforge/2.6.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_pdb_id(value: str) -> str:
    s = str(value or "").strip().upper()
    return s if _PDB_ID_RE.match(s) else ""


def clean_sequence_query(value: str) -> str:
    lines = []
    for line in str(value or "").splitlines():
        if line.strip().startswith(">"):
            continue
        lines.append(re.sub(r"[^A-Za-z]", "", line).upper())
    seq = "".join(lines)
    return seq


def infer_query_mode(query: str) -> str:
    """Return pdb_id, sequence, or text."""
    q = str(query or "").strip()
    if normalize_pdb_id(q):
        return "pdb_id"
    seq = clean_sequence_query(q)
    if len(seq) >= 15 and _AA_RE.match(q):
        return "sequence"
    return "text"


def _entry_metadata(pdb_id: str) -> dict[str, Any]:
    pdb_id = normalize_pdb_id(pdb_id)
    if not pdb_id:
        return {}
    try:
        data = _json_get(RCSB_DATA_ENTRY_URL.format(pdb_id=pdb_id))
    except Exception:
        return {}
    info = data.get("struct", {}) or {}
    exptl = data.get("exptl", []) or []
    return {
        "pdb_id": pdb_id,
        "title": info.get("title", ""),
        "experimental_method": "; ".join(str(x.get("method", "")) for x in exptl if isinstance(x, dict)) or "",
        "resolution_A": ((data.get("rcsb_entry_info", {}) or {}).get("resolution_combined") or [""])[0],
        "deposition_date": data.get("rcsb_accession_info", {}).get("deposit_date", ""),
        "release_date": data.get("rcsb_accession_info", {}).get("initial_release_date", ""),
    }


def search_by_pdb_id(pdb_id: str) -> list[dict[str, Any]]:
    pdb_id = normalize_pdb_id(pdb_id)
    if not pdb_id:
        return []
    meta = _entry_metadata(pdb_id)
    if not meta:
        meta = {"pdb_id": pdb_id, "title": "", "experimental_method": "", "resolution_A": "", "deposition_date": "", "release_date": ""}
    meta.update({"match_type": "pdb_id", "score": 1.0, "source": "RCSB Data API"})
    return [meta]


def search_text(query: str, rows: int = 10) -> list[dict[str, Any]]:
    payload = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "struct.title",
                "operator": "contains_words",
                "value": str(query or "").strip(),
            },
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": int(rows)},
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }
    data = _json_post(RCSB_SEARCH_URL, payload)
    out = []
    for item in data.get("result_set", []) or []:
        identifier = str(item.get("identifier", "")).split("_")[0].upper()
        if not normalize_pdb_id(identifier):
            continue
        meta = _entry_metadata(identifier)
        meta.update({"match_type": "text", "score": item.get("score", ""), "source": "RCSB Search API"})
        out.append(meta)
    return out


def search_sequence(sequence: str, rows: int = 10, identity_cutoff: float = 0.3, evalue_cutoff: float = 1.0) -> list[dict[str, Any]]:
    seq = clean_sequence_query(sequence)
    if len(seq) < 15:
        return []
    payload = {
        "query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": float(evalue_cutoff),
                "identity_cutoff": float(identity_cutoff),
                "target": "pdb_protein_sequence",
                "value": seq,
            },
        },
        "return_type": "polymer_entity",
        "request_options": {
            "paginate": {"start": 0, "rows": int(rows)},
            "results_content_type": ["experimental"],
            "scoring_strategy": "sequence",
        },
    }
    data = _json_post(RCSB_SEARCH_URL, payload)
    out = []
    seen = set()
    for item in data.get("result_set", []) or []:
        identifier = str(item.get("identifier", "")).upper()
        pdb_id = identifier.split("_")[0]
        if not normalize_pdb_id(pdb_id) or pdb_id in seen:
            continue
        seen.add(pdb_id)
        meta = _entry_metadata(pdb_id)
        meta.update({
            "match_type": "sequence",
            "score": item.get("score", ""),
            "source": "RCSB Search API",
            "polymer_entity": identifier,
        })
        out.append(meta)
    return out


def search_rcsb(query: str, mode: str = "auto", rows: int = 10) -> list[dict[str, Any]]:
    """Search RCSB by PDB ID, sequence, or text keyword."""
    mode = (mode or "auto").lower().strip()
    if mode == "auto":
        mode = infer_query_mode(query)
    if mode in {"pdb", "pdb_id", "code"}:
        return search_by_pdb_id(query)
    if mode in {"seq", "sequence"}:
        return search_sequence(query, rows=rows)
    return search_text(query, rows=rows)


def download_rcsb_structure(pdb_id: str, output_dir: str | Path, fmt: str = "pdb") -> str:
    """Download a PDB or mmCIF file from RCSB file download service."""
    pdb_id = normalize_pdb_id(pdb_id)
    if not pdb_id:
        raise ValueError("Invalid PDB ID. Expected four-character ID such as 1CRN.")
    fmt = str(fmt or "pdb").strip().lower()
    if fmt in {"cif", "mmcif"}:
        fmt = "cif"
    elif fmt != "pdb":
        raise ValueError("fmt must be 'pdb' or 'cif'.")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{pdb_id}.{fmt}"
    url = RCSB_DOWNLOAD_URL.format(pdb_id=pdb_id, fmt=fmt)
    text = _text_get(url)
    if not text.strip():
        raise RuntimeError(f"Downloaded empty structure file for {pdb_id}.")
    path.write_text(text, encoding="utf-8")
    return str(path)


def _normalize_result_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "pdb_id": str(r.get("pdb_id", "") or "").upper(),
        "title": r.get("title", "") or "",
        "method": r.get("experimental_method", "") or r.get("method", "") or "",
        "resolution_A": r.get("resolution_A", "") or "",
        "match_type": r.get("match_type", "") or "",
        "score": r.get("score", "") or "",
        "source": r.get("source", "") or "",
        "polymer_entity": r.get("polymer_entity", "") or "",
    }


def results_to_rows(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_result_row(r) for r in results]


__all__ = [
    "RCSB_BRIDGE_VERSION",
    "search_rcsb",
    "search_by_pdb_id",
    "search_text",
    "search_sequence",
    "download_rcsb_structure",
    "results_to_rows",
    "infer_query_mode",
    "normalize_pdb_id",
]
