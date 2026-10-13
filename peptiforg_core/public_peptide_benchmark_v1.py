from __future__ import annotations

"""Public protein-peptide benchmark registry and RCSB/UniProt synchronization.

The registry is derived from the 57-case global peptide-docking benchmark table
reported by Tao et al. (JCIM 2020). Coordinate files are NOT redistributed by
Pepforge. When syncing, Pepforge downloads the current PDB entry from RCSB and
optionally enriches chain provenance with UniProtKB records referenced by DBREF.

Scientific scope:
- RCSB PDB supplies experimental coordinates / entry provenance.
- UniProt supplies protein accession/sequence annotation.
- Neither source is treated as evidence that a Pepforge prediction is correct.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import csv, hashlib, json, re, shutil, urllib.request

from .uniprot_bridge_v1 import get_uniprot_entry, summarize_uniprot_json

PUBLIC_PEPTIDE_BENCHMARK_VERSION = "0.2.0"
RCSB_PDB_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"
UNIPROT_JSON_URL = "https://rest.uniprot.org/uniprotkb/{accession}.json"

@dataclass(frozen=True)
class PublicBenchmarkCase:
    peptide_length_reported: int
    bound_pdb: str
    receptor_chain: str
    peptide_chain: str
    unbound_pdb: str
    unbound_chain: str

# 57 bound/unbound cases from the published global peptide docking benchmark.
# Length is the value reported by the benchmark table; sync computes observed
# chain length independently and records any mismatch rather than hiding it.
PUBLIC_57_CASES: tuple[PublicBenchmarkCase, ...] = (
    PublicBenchmarkCase(5,"1JWG","B","D","1JWF","A"), PublicBenchmarkCase(5,"1NVR","A","B","2QHN","A"),
    PublicBenchmarkCase(5,"2H9M","C","D","2H14","A"), PublicBenchmarkCase(5,"2HPL","A","B","2HPJ","A"),
    PublicBenchmarkCase(6,"1AWR","C","I","2ALF","A"), PublicBenchmarkCase(6,"1DDV","A","B","1I2H","A"),
    PublicBenchmarkCase(6,"1KL3","C","G","2RTM","A"), PublicBenchmarkCase(6,"1TP5","A","B","1TQ3","A"),
    PublicBenchmarkCase(6,"1TW6","B","D","2I3I","A"), PublicBenchmarkCase(6,"1VZQ","H","I","1JWT","A"),
    PublicBenchmarkCase(6,"3D1E","A","P","3D1G","A"), PublicBenchmarkCase(6,"3D9T","B","D","1QBH","A"),
    PublicBenchmarkCase(7,"1CZY","C","E","1CZZ","C"), PublicBenchmarkCase(7,"1LVM","A","E","1LVB","B"),
    PublicBenchmarkCase(7,"1SE0","A","B","3SIQ","A"), PublicBenchmarkCase(7,"2FOJ","A","B","2F1W","A"),
    PublicBenchmarkCase(8,"1ER8","E","I","1OEW","A"), PublicBenchmarkCase(8,"1N7F","B","D","1N7E","A"),
    PublicBenchmarkCase(8,"1OU8","B","D","1OU9","A"), PublicBenchmarkCase(8,"2C3I","B","A","2J2I","B"),
    PublicBenchmarkCase(8,"2FGR","A","B","2FGQ","X"), PublicBenchmarkCase(8,"2J6F","A","C","2J6K","A"),
    PublicBenchmarkCase(8,"2VJ0","A","P","1B9K","A"), PublicBenchmarkCase(9,"1CKA","A","B","2DVJ","A"),
    PublicBenchmarkCase(9,"1MFG","A","B","2H3L","A"), PublicBenchmarkCase(9,"1OAI","A","B","1GO5","A"),
    PublicBenchmarkCase(9,"1T4F","M","P","1Z1M","A"), PublicBenchmarkCase(9,"1UJ0","A","B","1X2Q","A"),
    PublicBenchmarkCase(9,"1X2R","A","B","1X2J","A"), PublicBenchmarkCase(9,"1Z9O","A","G","1Z9L","A"),
    PublicBenchmarkCase(9,"2B1Z","B","D","2IOG","A"), PublicBenchmarkCase(10,"1T7R","A","B","2AM9","A"),
    PublicBenchmarkCase(10,"1YWO","A","P","1Y0M","A"), PublicBenchmarkCase(10,"2FVJ","A","B","2HWQ","A"),
    PublicBenchmarkCase(10,"2HO2","A","B","2E45","A"), PublicBenchmarkCase(10,"2O9V","A","B","2O9S","A"),
    PublicBenchmarkCase(10,"2P1T","A","B","3NSQ","A"), PublicBenchmarkCase(10,"2R7G","C","D","3POM","A"),
    PublicBenchmarkCase(10,"2ZJD","A","B","1V49","A"), PublicBenchmarkCase(11,"1D4T","A","B","1D1Z","C"),
    PublicBenchmarkCase(11,"1NX1","A","C","1ALV","A"), PublicBenchmarkCase(11,"1RXZ","A","B","1RWZ","A"),
    PublicBenchmarkCase(11,"1SSH","A","B","1OOT","A"), PublicBenchmarkCase(11,"2QOS","C","A","1LF7","A"),
    PublicBenchmarkCase(12,"2A3I","A","B","2AA2","A"), PublicBenchmarkCase(12,"2B9H","A","C","2B9F","A"),
    PublicBenchmarkCase(12,"2CCH","D","F","1H1R","B"), PublicBenchmarkCase(12,"2O4J","A","C","1IE9","A"),
    PublicBenchmarkCase(12,"2P54","A","B","1I7G","A"), PublicBenchmarkCase(13,"1EG4","A","P","1EG3","A"),
    PublicBenchmarkCase(13,"1HC9","A","C","2ABX","A"), PublicBenchmarkCase(13,"2FMF","A","B","1JBE","A"),
    PublicBenchmarkCase(14,"1SFI","A","I","1UTN","A"), PublicBenchmarkCase(14,"1YUC","A","C","3TX7","B"),
    PublicBenchmarkCase(14,"2O02","A","P","3RDH","A"), PublicBenchmarkCase(14,"3BU3","A","B","3EKK","A"),
    PublicBenchmarkCase(15,"1JBU","H","X","2BZ6","H"),
)

def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def write_public_registry(output_csv: str|Path) -> str:
    out=Path(output_csv); out.parent.mkdir(parents=True,exist_ok=True)
    fields=["target_id","reported_peptide_length","bound_pdb","receptor_chain","peptide_chain","unbound_pdb","unbound_chain","split","source","source_doi","coordinate_provider","annotation_provider"]
    with out.open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader()
        for i,c in enumerate(PUBLIC_57_CASES):
            # deterministic dev split; NOT sequence-independent. Kept explicit.
            split = "holdout" if (i % 5 == 0) else "train"
            w.writerow({"target_id":c.bound_pdb,"reported_peptide_length":c.peptide_length_reported,
                "bound_pdb":c.bound_pdb,"receptor_chain":c.receptor_chain,"peptide_chain":c.peptide_chain,
                "unbound_pdb":c.unbound_pdb,"unbound_chain":c.unbound_chain,"split":split,
                "source":"Tao2020_global_peptide_docking_benchmark","source_doi":"10.1021/acs.jcim.0c00372","coordinate_provider":"RCSB PDB","annotation_provider":"UniProtKB"})
    return str(out.resolve())

def _download(url: str, path: Path, timeout: int=45) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url, headers={"User-Agent":"Pepforge/5 public benchmark sync"})
    with urllib.request.urlopen(req, timeout=timeout) as r, path.open('wb') as f:
        f.write(r.read())


def _find_cached_file(cache_root: str|Path|None, names: Iterable[str]) -> Path|None:
    if not cache_root:
        return None
    root=Path(cache_root).expanduser().resolve()
    if not root.exists():
        return None
    candidates=[]
    for name in names:
        candidates.extend([root/name, root/name.lower(), root/'raw'/name, root/'raw'/name.lower()])
    for p in candidates:
        if p.is_file():
            return p
    # A user-maintained mirror can be nested by PDB ID. Avoid broad recursive scans.
    for sub in root.iterdir() if root.is_dir() else []:
        if not sub.is_dir():
            continue
        for name in names:
            p=sub/name
            if p.is_file():
                return p
    return None

def _materialize_pdb(pdb_id: str, path: Path, *, cache_root: str|Path|None=None, allow_network: bool=True, timeout: int=45) -> str:
    if path.is_file():
        return "existing"
    cached=_find_cached_file(cache_root,[f"{pdb_id.upper()}.pdb",f"{pdb_id.lower()}.pdb"])
    if cached:
        path.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(cached,path); return "local_cache"
    if not allow_network:
        raise FileNotFoundError(f"{pdb_id}: coordinate file not found in local cache and network access is disabled")
    _download(RCSB_PDB_URL.format(pdb_id=pdb_id),path,timeout); return "RCSB_PDB_HTTPS"

def _atom_chain(line: str) -> str:
    return line[21:22].strip() if len(line) > 21 else ""

def _res_key(line: str) -> tuple[str,str]:
    return (line[22:26].strip(), line[26:27].strip() if len(line)>26 else "")

def _renumber_chain_lines(lines: Iterable[str], source_chain: str, target_chain: str) -> list[str]:
    out=[]
    for line in lines:
        if not line.startswith(("ATOM  ","HETATM")): continue
        if _atom_chain(line) != source_chain: continue
        # keep only amino-acid ATOM records; benchmark is canonical peptide/protein oriented
        if not line.startswith("ATOM  "): continue
        line=(line[:21] + (target_chain or " ")[:1] + line[22:]) if len(line)>=22 else line
        out.append(line.rstrip())
    return out

def _chain_residue_count(lines: Iterable[str], chain: str) -> int:
    return len({_res_key(x) for x in lines if x.startswith("ATOM  ") and _atom_chain(x)==chain and x[12:16].strip()=="CA"})

def _dbref_accessions(lines: Iterable[str], chain: str) -> list[str]:
    acc=[]
    for line in lines:
        if not line.startswith("DBREF"): continue
        # Legacy DBREF has chain near col 13; accession often columns 34-41.
        if len(line)>12 and line[12:13].strip()==chain:
            token=(line[33:41].strip() if len(line)>=41 else "")
            if token and re.match(r"^[A-Z0-9]{6,10}$", token): acc.append(token)
    return sorted(set(acc))

def _fetch_uniprot(accession: str, out: Path, timeout: int=30, *, role: str="") -> dict[str,Any]:
    summary=get_uniprot_entry(accession, timeout=timeout, raw_output=out)
    summary["role"]=role
    summary["sha256"]=_sha256(out)
    return summary

def sync_public_case(case: PublicBenchmarkCase, output_dir: str|Path, *, include_unbound: bool=True, include_uniprot: bool=True, timeout: int=45, local_cache: str|Path|None=None, allow_network: bool=True) -> dict[str,Any]:
    root=Path(output_dir).expanduser().resolve()/case.bound_pdb
    raw=root/'raw'; prepared=root/'prepared'; raw.mkdir(parents=True,exist_ok=True); prepared.mkdir(parents=True,exist_ok=True)
    bound_raw=raw/f"{case.bound_pdb}.pdb"
    bound_source=_materialize_pdb(case.bound_pdb,bound_raw,cache_root=local_cache,allow_network=allow_network,timeout=timeout)
    lines=bound_raw.read_text(encoding='utf-8',errors='replace').splitlines()
    rec=_renumber_chain_lines(lines,case.receptor_chain,'A'); pep=_renumber_chain_lines(lines,case.peptide_chain,'P')
    if not rec: raise ValueError(f"{case.bound_pdb}: receptor chain {case.receptor_chain} not found")
    if not pep: raise ValueError(f"{case.bound_pdb}: peptide chain {case.peptide_chain} not found")
    reference=prepared/'reference_complex_A_P.pdb'; receptor=prepared/'receptor_bound_A.pdb'; peptide=prepared/'peptide_bound_P.pdb'
    reference.write_text('\n'.join(rec+['TER']+pep+['TER','END'])+'\n',encoding='utf-8')
    receptor.write_text('\n'.join(rec+['TER','END'])+'\n',encoding='utf-8')
    peptide.write_text('\n'.join(pep+['TER','END'])+'\n',encoding='utf-8')
    obs=_chain_residue_count(lines,case.peptide_chain)
    unbound_path=None; unbound_source="not_requested"
    if include_unbound:
        ub=raw/f"{case.unbound_pdb}.pdb"
        unbound_source=_materialize_pdb(case.unbound_pdb,ub,cache_root=local_cache,allow_network=allow_network,timeout=timeout)
        ulines=ub.read_text(encoding='utf-8',errors='replace').splitlines()
        urec=_renumber_chain_lines(ulines,case.unbound_chain,'A')
        if urec:
            unbound_path=prepared/'receptor_unbound_A.pdb'; unbound_path.write_text('\n'.join(urec+['TER','END'])+'\n',encoding='utf-8')
    uni=[]
    if include_uniprot:
        role_accessions=[]
        role_accessions.extend((a,"receptor") for a in _dbref_accessions(lines,case.receptor_chain))
        role_accessions.extend((a,"peptide") for a in _dbref_accessions(lines,case.peptide_chain))
        seen=set()
        for a,role in role_accessions:
            key=(a,role)
            if key in seen: continue
            seen.add(key)
            try:
                uni_out=raw/f"uniprot_{a}.json"
                cached_uni=_find_cached_file(local_cache,[f"uniprot_{a}.json",f"{a}.json"])
                if cached_uni:
                    shutil.copy2(cached_uni,uni_out)
                    item=summarize_uniprot_json(uni_out); item.update({"role":role,"sha256":_sha256(uni_out),"retrieval":"local_cache"}); uni.append(item)
                elif allow_network:
                    item=_fetch_uniprot(a, uni_out, timeout=min(timeout,30), role=role); item["retrieval"]="UniProtKB_REST"; uni.append(item)
                else:
                    uni.append({"accession":a,"role":role,"status":"CACHE_MISS_NETWORK_DISABLED"})
            except Exception as exc: uni.append({"accession":a,"role":role,"status":"FETCH_FAILED","error":str(exc)})
    payload={"version":PUBLIC_PEPTIDE_BENCHMARK_VERSION,"target_id":case.bound_pdb,"source":"RCSB PDB + published 57-case benchmark",
        "bound_pdb":case.bound_pdb,"unbound_pdb":case.unbound_pdb,"original_chains":{"receptor":case.receptor_chain,"peptide":case.peptide_chain,"unbound_receptor":case.unbound_chain},
        "normalized_chains":{"receptor":"A","peptide":"P"},"reported_peptide_length":case.peptide_length_reported,"observed_peptide_length":obs,
        "length_mismatch":bool(obs and obs!=case.peptide_length_reported),"reference_pdb":str(reference),"receptor_bound_pdb":str(receptor),"peptide_bound_pdb":str(peptide),
        "receptor_unbound_pdb":str(unbound_path) if unbound_path else "","coordinate_retrieval":{"bound":bound_source,"unbound":unbound_source},"rcsb_urls":{"bound":RCSB_PDB_URL.format(pdb_id=case.bound_pdb),"unbound":RCSB_PDB_URL.format(pdb_id=case.unbound_pdb)},
        "uniprot_annotations":uni,"sha256":{"bound_raw":_sha256(bound_raw),"reference":_sha256(reference),"receptor_bound":_sha256(receptor),"peptide_bound":_sha256(peptide)},
        "claim_guard":"Public experimental coordinates and UniProt annotations are provenance/reference data only; they do not validate Pepforge predictions or affinity."}
    (root/'provenance.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

def sync_public_registry(output_dir: str|Path, *, target_ids: Iterable[str]|None=None, include_unbound: bool=True, include_uniprot: bool=True, continue_on_error: bool=True, local_cache: str|Path|None=None, allow_network: bool=True) -> dict[str,Any]:
    selected={x.upper() for x in (target_ids or [])}
    cases=[c for c in PUBLIC_57_CASES if not selected or c.bound_pdb in selected]
    root=Path(output_dir).expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    results=[]; errors=[]
    for c in cases:
        try: results.append(sync_public_case(c,root,include_unbound=include_unbound,include_uniprot=include_uniprot,local_cache=local_cache,allow_network=allow_network))
        except Exception as exc:
            errors.append({"target_id":c.bound_pdb,"error":str(exc)})
            if not continue_on_error: raise
    payload={"version":PUBLIC_PEPTIDE_BENCHMARK_VERSION,"status":"PASS" if results and not errors else ("PARTIAL" if results else "FAIL"),"targets_requested":len(cases),"targets_synced":len(results),"errors":errors,"targets":results,"local_cache":str(Path(local_cache).expanduser().resolve()) if local_cache else "","network_allowed":bool(allow_network),
        "claim_guard":"Sync success means files were retrieved/prepared, not that docking accuracy has been validated."}
    (root/'public_benchmark_sync_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

__all__=['PUBLIC_PEPTIDE_BENCHMARK_VERSION','PublicBenchmarkCase','PUBLIC_57_CASES','write_public_registry','sync_public_case','sync_public_registry']
