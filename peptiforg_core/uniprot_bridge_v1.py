from __future__ import annotations

"""Minimal UniProtKB REST bridge used by Pepforge V5 public benchmark provenance.

UniProt annotations are metadata/provenance and sequence sanity evidence only.
They are never treated as docking ground truth or affinity measurements.
"""

from pathlib import Path
from typing import Any
import json
import re
import urllib.parse
import urllib.request

UNIPROT_BRIDGE_VERSION = "0.2.0"
UNIPROT_ENTRY_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
_ACC_RE = re.compile(r"^[A-Z0-9]{6,10}(?:-\d+)?$", re.I)


def normalize_uniprot_accession(value: str) -> str:
    s = str(value or "").strip().upper()
    return s if _ACC_RE.match(s) else ""


def _json_get(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Pepforge/5 UniProt provenance"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _entry_summary(data: dict[str, Any]) -> dict[str, Any]:
    pd = data.get("proteinDescription") or {}
    rn = (pd.get("recommendedName") or {}).get("fullName") or {}
    submitted = (pd.get("submissionNames") or [{}])[0].get("fullName") if pd.get("submissionNames") else {}
    name = rn.get("value") or (submitted or {}).get("value") or ""
    genes = data.get("genes") or []
    gene = ""
    if genes:
        gene = ((genes[0].get("geneName") or {}).get("value") or "")
    seq = ((data.get("sequence") or {}).get("value") or "").replace("\n", "")
    pdb_refs = []
    for ref in data.get("uniProtKBCrossReferences") or []:
        if str(ref.get("database") or "").upper() == "PDB":
            pdb_refs.append(str(ref.get("id") or "").upper())
    return {
        "accession": data.get("primaryAccession") or "",
        "entry_id": data.get("uniProtkbId") or "",
        "reviewed": str(data.get("entryType") or "").lower().startswith("uniprotkb reviewed"),
        "protein_name": name,
        "gene": gene,
        "organism": ((data.get("organism") or {}).get("scientificName") or ""),
        "sequence": seq,
        "sequence_length": len(seq),
        "pdb_cross_references": sorted(set(pdb_refs)),
        "source": "UniProtKB REST API",
        "claim_guard": "UniProt annotation/sequence is provenance and sanity-check evidence, not docking or affinity ground truth.",
    }



def summarize_uniprot_json(path: str | Path) -> dict[str, Any]:
    """Load a cached UniProtKB JSON response and return the normalized Pepforge summary."""
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    return _entry_summary(data)

def get_uniprot_entry(accession: str, *, timeout: int = 30, raw_output: str | Path | None = None) -> dict[str, Any]:
    acc = normalize_uniprot_accession(accession)
    if not acc:
        raise ValueError("Invalid UniProt accession")
    data = _json_get(UNIPROT_ENTRY_URL.format(accession=urllib.parse.quote(acc)), timeout=timeout)
    if raw_output:
        p = Path(raw_output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return _entry_summary(data)


def search_uniprot(query: str, *, rows: int = 10, reviewed_only: bool = False, timeout: int = 30) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    if reviewed_only:
        q = f"({q}) AND reviewed:true"
    params = urllib.parse.urlencode({"query": q, "format": "json", "size": max(1, min(int(rows), 100))})
    data = _json_get(f"{UNIPROT_SEARCH_URL}?{params}", timeout=timeout)
    return [_entry_summary(x) for x in (data.get("results") or [])]


__all__ = [
    "UNIPROT_BRIDGE_VERSION", "normalize_uniprot_accession", "summarize_uniprot_json", "get_uniprot_entry", "search_uniprot"
]
