"""V6 online target import. Public source data only; no invented scientific scores."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
from typing import Any
from peptiforg_core.uniprot_bridge_v1 import normalize_uniprot_accession, get_uniprot_entry
from peptiforg_core.rcsb_pdb_bridge import normalize_pdb_id

MAX_STRUCTURE_BYTES = 30 * 1024 * 1024

def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        temp = Path(tmp.name)
    os.replace(temp, path)

def _structure_bytes(pdb_id: str, fmt: str, timeout: int) -> bytes:
    if fmt not in ('cif', 'pdb') or not normalize_pdb_id(pdb_id):
        raise ValueError('Invalid structure request')
    url = f'https://files.rcsb.org/download/{pdb_id}.{fmt}'
    req = urllib.request.Request(url, headers={'User-Agent':'Pepforge-V6/OnlineTargetImport', 'Accept':'text/plain'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # Defend against excessive downloads while retaining format-specific records.
        content = resp.read(MAX_STRUCTURE_BYTES + 1)
    if len(content) > MAX_STRUCTURE_BYTES:
        raise ValueError('Structure exceeds the 30 MiB size limit')
    if not content or (fmt == 'cif' and b'data_' not in content[:4096]) or (fmt == 'pdb' and b'ATOM ' not in content and b'HETATM' not in content):
        raise ValueError('Unexpected or empty coordinate format')
    return content

def import_uniprot_target(accession: str, output_dir: str | Path, *, pdb_limit: int = 3,
                          fmt: str = 'cif', timeout: int = 20, download_structures: bool = True,
                          offline_json: str | Path | None = None) -> dict[str, Any]:
    acc = normalize_uniprot_accession(accession)
    if not acc: raise ValueError('Invalid UniProt accession')
    if fmt not in ('cif', 'pdb'): raise ValueError('Invalid structure format')
    if not (0 <= pdb_limit <= 20): raise ValueError('pdb_limit must be 0..20')
    if not (1 <= timeout <= 120): raise ValueError('timeout must be 1..120 seconds')
    out = Path(output_dir).expanduser().resolve()
    if offline_json:
        from peptiforg_core.uniprot_bridge_v1 import summarize_uniprot_json
        summary = summarize_uniprot_json(offline_json)
    else:
        summary = get_uniprot_entry(acc, timeout=timeout)
    if summary.get('accession', '').upper() != acc.split('-')[0] and summary.get('accession', '').upper() != acc:
        raise ValueError('UniProt accession mismatch')
    seq = summary.get('sequence', '')
    if not seq or not seq.isalpha(): raise ValueError('Missing/invalid sequence')
    ids = [x for x in summary.get('pdb_cross_references', []) if normalize_pdb_id(x)][:pdb_limit]
    manifest: dict[str, Any] = {
        'schema': 'pepforge.v6.online_target_import.v1', 'uniprot_accession': acc,
        'protein_name': summary.get('protein_name', ''), 'organism': summary.get('organism', ''),
        'sequence_length': len(seq), 'sources': {'sequence': 'UniProtKB REST API', 'structures': 'RCSB PDB File Download'},
        'interpretation': 'Public annotations/coordinates only; NOT docking predictions, affinity, or validated force-field parameters.',
        'files': [], 'errors': [], 'offline_source': bool(offline_json),
    }
    fasta = f'>{acc} {summary.get("protein_name", "").replace(chr(10), " ")}\n' + '\n'.join(seq[i:i+80] for i in range(0,len(seq),80)) + '\n'
    files = [('target.fasta',fasta.encode('utf-8')),
             ('uniprot_summary.json',(json.dumps(summary,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))]
    for pid in ids if download_structures else []:
        try: files.append((f'structures/{pid}.{fmt}',_structure_bytes(pid,fmt,timeout)))
        except Exception as exc: manifest['errors'].append({'pdb_id':pid,'error':f'{type(exc).__name__}: {exc}'})
    for name, data in files:
        _atomic_write(out/name, data)
        manifest['files'].append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    _atomic_write(out/'import_manifest.json', (json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    return manifest
