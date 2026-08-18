from __future__ import annotations

"""Peptide-Target Complex Builder for Pepforge v2.8.0.

This module generates a conservative initial target-peptide complex candidate for
Docking Workbench screening. It can combine a prepared target PDB with either a
peptide PDB or a simple pseudo-backbone generated from peptide notation/sequence.

It is not a replacement for AutoDock Vina, Rosetta, AlphaFold, full docking, or
all-atom relaxation. The output is an initial candidate for contact preview,
clash review, and validation-bridge preparation.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv, json, math, re

COMPLEX_BUILDER_VERSION = "2.8.0"
AA1 = set("ACDEFGHIKLMNPQRSTVWY")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["note"]
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    return str(path)

def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return str(path)

def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8'); return str(path)

def parse_pdb_atoms(path: str | Path) -> list[dict[str, Any]]:
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f'PDB file not found: {p}')
    out=[]
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        rec=line[0:6].strip()
        if rec not in {'ATOM','HETATM'}: continue
        atom=line[12:16].strip(); resn=line[17:20].strip(); chain=line[21:22].strip() or '_'; resi=line[22:26].strip()
        try: x=float(line[30:38]); y=float(line[38:46]); z=float(line[46:54])
        except Exception: continue
        elem=(line[76:78].strip() if len(line)>=78 else re.sub(r'[^A-Za-z]','',atom)[:1]).upper()
        out.append({'record':rec,'atom':atom,'resn':resn,'chain':chain,'resi':resi,'x':x,'y':y,'z':z,'element':elem,'line':line})
    return out

def _centroid(atoms: list[dict[str, Any]]) -> tuple[float,float,float]:
    if not atoms: return (0.0,0.0,0.0)
    return (sum(a['x'] for a in atoms)/len(atoms), sum(a['y'] for a in atoms)/len(atoms), sum(a['z'] for a in atoms)/len(atoms))

def _clean_sequence(seq: str) -> str:
    s=str(seq or '')
    # keep one-letter amino acids; remove common caps/modifiers as pseudo-builder cannot model them atomically.
    s=re.sub(r'Ac|NH2|FITC|FAM|TAMRA|Biotin|Ahx|AEEA|Pal|Myr|Cha','',s,flags=re.I)
    letters=''.join(ch.upper() for ch in s if ch.upper() in AA1)
    if not letters:
        raise ValueError('No supported canonical peptide residues were parsed. Provide an explicit peptide PDB for modified/non-canonical chemistry.')
    return letters

def build_pseudo_peptide_pdb(sequence: str, center: tuple[float,float,float], offset_A: float = 8.0, chain_id: str = 'P') -> str:
    seq=_clean_sequence(sequence)
    cx,cy,cz=center
    # simple extended CA trace placed along X axis, offset from target centroid.
    lines=[]; serial=1; start_x=cx+offset_A-(len(seq)-1)*1.9
    aa3={'A':'ALA','C':'CYS','D':'ASP','E':'GLU','F':'PHE','G':'GLY','H':'HIS','I':'ILE','K':'LYS','L':'LEU','M':'MET','N':'ASN','P':'PRO','Q':'GLN','R':'ARG','S':'SER','T':'THR','V':'VAL','W':'TRP','Y':'TYR'}
    for i,aa in enumerate(seq, start=1):
        resn=aa3.get(aa,'GLY'); x=start_x+(i-1)*3.8; y=cy+offset_A; z=cz
        lines.append(f"ATOM  {serial:5d}  CA  {resn:>3s} {chain_id:1s}{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C")
        serial+=1
    lines.append('TER'); lines.append('END')
    return '\n'.join(lines)+'\n'

def _renumber_as_chain(pdb_text: str, chain_id: str, start_serial: int) -> tuple[list[str], int]:
    lines=[]; serial=start_serial
    for line in pdb_text.splitlines():
        rec=line[0:6].strip()
        if rec not in {'ATOM','HETATM'}: continue
        if len(line)<80: line=line.ljust(80)
        newline=f"{line[0:6]}{serial:5d}{line[11:21]}{chain_id:1s}{line[22:]}"
        lines.append(newline[:80])
        serial+=1
    return lines, serial

def _format_existing_target_lines(target_path: str | Path, chain_filter: Optional[Iterable[str]] = None) -> list[str]:
    selected={str(c).strip() for c in chain_filter or [] if str(c).strip()}
    lines=[]
    for line in Path(target_path).read_text(encoding='utf-8', errors='ignore').splitlines():
        rec=line[0:6].strip()
        if rec not in {'ATOM','HETATM'}: continue
        chain=line[21:22].strip() or '_'
        if selected and chain not in selected: continue
        lines.append(line[:80].ljust(80))
    return lines

def min_distance_between_atoms(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> float:
    best=9999.0
    for x in a:
        for y in b:
            d=((x['x']-y['x'])**2+(x['y']-y['y'])**2+(x['z']-y['z'])**2)**0.5
            if d<best: best=d
    return best

def contact_preview(target_atoms: list[dict[str, Any]], peptide_atoms: list[dict[str, Any]], cutoff_A: float = 5.0, clash_A: float = 2.0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    contacts=[]; clashes=[]
    for pa in peptide_atoms:
        near=[]
        for ta in target_atoms:
            d=((pa['x']-ta['x'])**2+(pa['y']-ta['y'])**2+(pa['z']-ta['z'])**2)**0.5
            if d<=cutoff_A:
                row={'peptide_chain':pa['chain'],'peptide_resi':pa['resi'],'peptide_resn':pa['resn'],'target_chain':ta['chain'],'target_resi':ta['resi'],'target_resn':ta['resn'],'distance_A':round(d,3),'class':'clash' if d<clash_A else 'contact'}
                near.append(row)
                if d<clash_A: clashes.append(row)
        contacts.extend(sorted(near, key=lambda r:r['distance_A'])[:10])
    return contacts[:500], clashes[:500]

def export_complex_builder_package(
    target_pdb: str | Path,
    output_dir: str | Path,
    peptide_pdb: str | Path | None = None,
    peptide_sequence: str = 'Ac-EEMQRR-NH2',
    target_chains: Optional[Iterable[str]] = None,
    peptide_chain_id: str = 'P',
    placement_offset_A: float = 8.0,
) -> Dict[str,str]:
    out=Path(output_dir); pkg=out/'peptide_target_complex_builder'; pkg.mkdir(parents=True, exist_ok=True)
    target_atoms=parse_pdb_atoms(target_pdb)
    if not target_atoms: raise ValueError('No target atoms parsed from target PDB.')
    center=_centroid(target_atoms)
    target_lines=_format_existing_target_lines(target_pdb, target_chains)
    serial=1+len(target_lines)
    if peptide_pdb and Path(peptide_pdb).exists():
        pep_text=Path(peptide_pdb).read_text(encoding='utf-8', errors='ignore')
    else:
        pep_text=build_pseudo_peptide_pdb(peptide_sequence, center, placement_offset_A, peptide_chain_id)
    pep_lines, next_serial=_renumber_as_chain(pep_text, peptide_chain_id, serial)
    complex_pdb=pkg/'initial_complex_candidate.pdb'
    complex_pdb.write_text('\n'.join(target_lines+pep_lines+['TER','END'])+'\n', encoding='utf-8')
    complex_atoms=parse_pdb_atoms(complex_pdb)
    peptide_atoms=[a for a in complex_atoms if a['chain']==peptide_chain_id]
    target_atoms2=[a for a in complex_atoms if a['chain']!=peptide_chain_id]
    contacts, clashes=contact_preview(target_atoms2, peptide_atoms)
    contact_csv=pkg/'complex_contact_preview.csv'; clash_csv=pkg/'complex_clash_report.csv'
    _write_csv(contact_csv, contacts, fieldnames=['peptide_chain','peptide_resi','peptide_resn','target_chain','target_resi','target_resn','distance_A','class'])
    _write_csv(clash_csv, clashes, fieldnames=['peptide_chain','peptide_resi','peptide_resn','target_chain','target_resi','target_resn','distance_A','class'])
    summary={'pepforge_version':COMPLEX_BUILDER_VERSION,'target_pdb':str(target_pdb),'peptide_pdb':str(peptide_pdb) if peptide_pdb else None,'peptide_sequence':peptide_sequence,'target_chains':list(target_chains or []),'peptide_chain_id':peptide_chain_id,'target_atom_count':len(target_atoms2),'peptide_atom_count':len(peptide_atoms),'contact_count':len(contacts),'clash_count':len(clashes),'min_distance_A':min_distance_between_atoms(target_atoms2, peptide_atoms) if peptide_atoms and target_atoms2 else None,'claim_boundary':'Initial complex candidate for screening/contact preview only; not final docking or validated binding pose.'}
    manifest=pkg/'complex_builder_manifest.json'; _write_json(manifest, summary)
    readme=pkg/'README_COMPLEX_BUILDER.txt'
    _write_text(readme, 'Pepforge Peptide-Target Complex Builder\n=====================================\n\nThis folder contains an initial complex candidate and contact/clash preview.\nUse it for screening and validation bridge preparation only. It is not a final\ndocking pose or proof of binding.\n')
    return {'initial_complex_candidate_pdb':str(complex_pdb),'complex_contact_preview':str(contact_csv),'complex_clash_report':str(clash_csv),'complex_builder_manifest':str(manifest),'complex_builder_readme':str(readme)}

__all__=['COMPLEX_BUILDER_VERSION','build_pseudo_peptide_pdb','export_complex_builder_package','contact_preview','parse_pdb_atoms']
