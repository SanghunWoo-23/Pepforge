from __future__ import annotations

"""Quality-preserving peptide builder.

Pepforge-native backbone generation is always attempted first.  If RDKit is
available locally, it may generate an additional full-atom canonical peptide
candidate for chemistry/geometry quality enhancement.  Pepforge records both
artifacts and provenance and never makes RDKit a hard dependency.
"""

from pathlib import Path
from typing import Any
import json

from .native_peptide_builder_v1 import export_native_backbone
from .native_quality_gate_v1 import audit_peptide_geometry
from .quality_arbitration_v1 import arbitrate_candidates

QUALITY_PRESERVING_BUILDER_VERSION="0.2.0"


def _rdkit_full_atom(sequence:str, out:Path, *, seed:int=20260929)->dict[str,Any]:
    out.mkdir(parents=True, exist_ok=True)
    try:
        from rdkit import Chem  # type: ignore
        from rdkit.Chem import AllChem  # type: ignore
    except Exception as exc:
        return {"status":"UNAVAILABLE","reason":str(exc),"backend":"RDKit optional quality layer"}
    seq=str(sequence or '').strip().upper()
    if not seq or any(c not in 'ACDEFGHIKLMNPQRSTVWY' for c in seq):
        return {"status":"UNSUPPORTED_SEQUENCE","reason":"RDKit enhancement is limited to canonical one-letter peptide sequence in v1.","backend":"RDKit optional quality layer"}
    try:
        mol=Chem.MolFromSequence(seq)
        if mol is None:
            return {"status":"FAILED","reason":"MolFromSequence returned None","backend":"RDKit optional quality layer"}
        mol=Chem.AddHs(mol)
        params=AllChem.ETKDGv3(); params.randomSeed=int(seed); params.useRandomCoords=False
        code=AllChem.EmbedMolecule(mol,params)
        if int(code)!=0:
            return {"status":"FAILED","reason":f"EmbedMolecule returned {code}","backend":"RDKit optional quality layer"}
        optimize="NONE"
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol,maxIters=1000); optimize="MMFF"
        else:
            try:
                AllChem.UFFOptimizeMolecule(mol,maxIters=1000); optimize="UFF"
            except Exception:
                optimize="EMBED_ONLY"
        p=out/'rdkit_quality_full_atom.pdb'; Chem.MolToPDBFile(mol,str(p))
        quality=audit_peptide_geometry(p,optional_rdkit=True)
        return {"status":"COMPLETED","backend":"RDKit optional quality layer","optimization":optimize,"pdb":str(p.resolve()),"atom_count":int(mol.GetNumAtoms()),"quality_gate":quality,
                "provenance":"Optional locally installed general-purpose chemistry toolkit; used for quality enhancement/validation, not as Pepforge's required scientific engine."}
    except Exception as exc:
        return {"status":"FAILED","reason":str(exc),"backend":"RDKit optional quality layer"}


def build_quality_preserving_peptide(sequence:str, output_dir:str|Path, *, phi_deg=None, psi_deg=None, omega_deg=None, chain:str='P', enable_rdkit:bool=True)->dict[str,Any]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    native=export_native_backbone(sequence,out/'native',phi_deg=phi_deg,psi_deg=psi_deg,omega_deg=omega_deg,chain=chain)
    rdkit=_rdkit_full_atom(sequence,out/'rdkit') if enable_rdkit else {"status":"SKIPPED_BY_POLICY","backend":"RDKit optional quality layer"}
    candidates=[{
        "name":"native","source":"native","native":True,"usable":True,"pdb":native['pdb'],
        "atom_count":int(native.get('atom_count',0)),"richness":int(native.get('atom_count',0)),
        "quality_gate":dict(native.get('quality_gate') or {}),
    }]
    if rdkit.get('status')=='COMPLETED':
        candidates.append({
            "name":"rdkit_optional_quality_layer","source":"rdkit_optional_quality_layer","native":False,"usable":True,
            "pdb":rdkit['pdb'],"atom_count":int(rdkit.get('atom_count',0)),"richness":int(rdkit.get('atom_count',0)),
            "quality_gate":dict(rdkit.get('quality_gate') or {}),
        })
    arbitration=arbitrate_candidates(candidates,prefer_native_on_tie=True)
    chosen=arbitration.get('selected_candidate') or candidates[0]
    preferred={
        "source":chosen.get('source','native'),"pdb":chosen.get('pdb',native['pdb']),
        "reason":"selected by Pepforge quality arbitration using quality-gate status first, structural richness second, and native preference only as a tie-breaker",
    }
    payload={
        "version":QUALITY_PRESERVING_BUILDER_VERSION,"status":"COMPLETED","sequence":str(sequence).strip().upper(),
        "native":native,"optional_rdkit":rdkit,"quality_arbitration":arbitration,"preferred_structure":preferred,
        "quality_policy":"Native path always remains available. Optional RDKit may improve canonical full-atom geometry/chemistry but is not required and never rewrites native provenance.",
        "claim_guard":"Preferred means preferred for downstream structural initialization under current quality policy, not experimentally validated native conformation.",
    }
    (out/'quality_preserving_builder_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

__all__=["QUALITY_PRESERVING_BUILDER_VERSION","build_quality_preserving_peptide"]
