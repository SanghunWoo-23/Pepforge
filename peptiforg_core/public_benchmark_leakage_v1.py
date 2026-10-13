from __future__ import annotations

"""Cross-split leakage audit for the public peptide-docking development registry.

The audit can establish exact duplicate/accession independence, but does not call a
split sequence-independent at an arbitrary identity threshold unless such an
alignment analysis has actually been supplied. This prevents overclaiming.
"""

from pathlib import Path
from typing import Any
import csv
import hashlib
import json

PUBLIC_BENCHMARK_LEAKAGE_VERSION = "0.1.0"

_AA3 = {
    "ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E","GLY":"G","HIS":"H","ILE":"I",
    "LEU":"L","LYS":"K","MET":"M","PHE":"F","PRO":"P","SER":"S","THR":"T","TRP":"W","TYR":"Y","VAL":"V",
    "MSE":"M","SEC":"U","PYL":"O"
}


def _rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _chain_sequence(path: Path, chain: str = "A") -> str:
    seen = set(); seq=[]
    if not path.exists(): return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("ATOM  ") or len(line) < 27 or line[21:22].strip() != chain: continue
        if line[12:16].strip() != "CA": continue
        key=(line[22:26].strip(), line[26:27].strip())
        if key in seen: continue
        seen.add(key); seq.append(_AA3.get(line[17:20].strip().upper(), "X"))
    return "".join(seq)


def _provenance(root: Path, tid: str) -> dict[str, Any]:
    p=root/tid/"provenance.json"
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}


def audit_public_benchmark_split(registry_csv: str|Path, prepared_root: str|Path, output_dir: str|Path) -> dict[str, Any]:
    rows=_rows(registry_csv); root=Path(prepared_root).expanduser().resolve(); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    entries=[]
    for r in rows:
        tid=(r.get("target_id") or "").upper(); split=(r.get("split") or "").lower()
        prov=_provenance(root,tid)
        rec_path=root/tid/"prepared"/"receptor_bound_A.pdb"
        seq=_chain_sequence(rec_path,"A")
        rec_acc=[]; pep_acc=[]
        for item in prov.get("uniprot_annotations") or []:
            if item.get("role")=="receptor" and item.get("accession"): rec_acc.append(item["accession"])
            if item.get("role")=="peptide" and item.get("accession"): pep_acc.append(item["accession"])
        # Backward-compatible provenance from early RC22 builds lacks role; keep unassigned accessions visible.
        all_acc=sorted({str(x.get("accession") or "") for x in (prov.get("uniprot_annotations") or []) if x.get("accession")})
        entries.append({"target_id":tid,"split":split,"receptor_accessions":sorted(set(rec_acc)),"peptide_accessions":sorted(set(pep_acc)),"all_accessions":all_acc,
                        "receptor_sequence":seq,"receptor_sequence_sha256":hashlib.sha256(seq.encode()).hexdigest() if seq else ""})
    train=[e for e in entries if e["split"]=="train"]; hold=[e for e in entries if e["split"]=="holdout"]
    def overlaps(field: str):
        ans=[]
        for a in train:
            av=set(a.get(field) or []) if isinstance(a.get(field),list) else ({a.get(field)} if a.get(field) else set())
            for b in hold:
                bv=set(b.get(field) or []) if isinstance(b.get(field),list) else ({b.get(field)} if b.get(field) else set())
                inter=sorted(x for x in av.intersection(bv) if x)
                if inter: ans.append({"train_target":a["target_id"],"holdout_target":b["target_id"],"shared":inter})
        return ans
    accession_overlap=overlaps("receptor_accessions")
    exact_seq=[]
    for a in train:
        if not a["receptor_sequence_sha256"]: continue
        for b in hold:
            if a["receptor_sequence_sha256"]==b["receptor_sequence_sha256"] and b["receptor_sequence_sha256"]:
                exact_seq.append({"train_target":a["target_id"],"holdout_target":b["target_id"],"sha256":a["receptor_sequence_sha256"]})
    prepared=sum(1 for e in entries if e["receptor_sequence"])
    status="FAIL" if accession_overlap or exact_seq else ("PASS_EXACT_DUPLICATE_GUARD" if prepared==len(entries) and train and hold else "INCOMPLETE")
    payload={"version":PUBLIC_BENCHMARK_LEAKAGE_VERSION,"status":status,"registry_rows":len(entries),"prepared_receptor_sequences":prepared,
             "train_count":len(train),"holdout_count":len(hold),"receptor_uniprot_cross_split_overlap":accession_overlap,"exact_receptor_sequence_cross_split_overlap":exact_seq,
             "sequence_identity_threshold_independence":"NOT_EVALUATED",
             "promotion_guard":"PASS_EXACT_DUPLICATE_GUARD only excludes identical receptor/accession leakage. It does not prove sequence-family independence at a chosen identity threshold.",
             "entries":entries}
    (out/"public_benchmark_split_audit.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return payload

__all__=["PUBLIC_BENCHMARK_LEAKAGE_VERSION","audit_public_benchmark_split"]
