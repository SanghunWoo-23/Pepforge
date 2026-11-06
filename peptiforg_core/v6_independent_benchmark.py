"""Independent, explicitly paired pose coordinates RMSD assessment.
Never claim independent validity when reference data overlaps training data.
"""
from pathlib import Path
import csv,json,math
import numpy as np

def read_heavy_atoms(pdb):
    atoms={}
    for line in Path(pdb).read_text(errors='replace').splitlines():
        if not line.startswith(('ATOM  ','HETATM')): continue
        element=line[76:78].strip().upper()
        if element in ('H','D'): continue
        if line[16:17] not in (' ', 'A'):
            raise ValueError('Alternate atom locations require explicit conformer selection')
        k=(line[21:22],line[22:27].strip(),line[12:16].strip())
        if k in atoms: raise ValueError(f'Duplicate atom ID {k}')
        try: xyz=np.array([float(line[30+i:38+i]) for i in (0,8,16)])
        except ValueError as e: raise ValueError('Bad PDB coordinates') from e
        if not np.isfinite(xyz).all(): raise ValueError('Nonfinite PDB coordinates')
        atoms[k]=xyz
    if not atoms: raise ValueError('No heavy atoms')
    return atoms

def aligned_rmsd(reference,prediction):
    a,b=read_heavy_atoms(reference),read_heavy_atoms(prediction)
    if set(a)!=set(b): raise ValueError('Different atom keys; RMSD undefined without explicit mapping')
    keys=sorted(a)
    x=np.stack([a[k] for k in keys]);y=np.stack([b[k] for k in keys])
    x=x-x.mean(axis=0);y=y-y.mean(axis=0)
    u,_,vt=np.linalg.svd(y.T@x);d=np.eye(3);d[2,2]=np.linalg.det(u@vt)
    rotation=u@d@vt
    return float(np.sqrt(np.mean(np.sum((y@rotation-x)**2,axis=1))))

def receptor_aligned_ligand_rmsd(reference_receptor, predicted_receptor,
                                 reference_peptide, predicted_peptide):
    """Receptor-superposed peptide RMSD, preserving the binding-site position.

    All corresponding heavy atoms must have matching PDB chain/residue/atom IDs.
    This is not a symmetry-corrected ligand RMSD.
    """
    rr, pr = read_heavy_atoms(reference_receptor), read_heavy_atoms(predicted_receptor)
    rl, pl = read_heavy_atoms(reference_peptide), read_heavy_atoms(predicted_peptide)
    if set(rr) != set(pr) or len(rr) < 3:
        raise ValueError('Receptor mapping requires at least 3 corresponding heavy atoms')
    if set(rl) != set(pl):
        raise ValueError('Peptide heavy atom correspondence is inconsistent')
    keys=sorted(rr)
    reference=np.stack([rr[k] for k in keys])
    predicted=np.stack([pr[k] for k in keys])
    cr,cp=reference.mean(axis=0), predicted.mean(axis=0)
    u,_,vt=np.linalg.svd((predicted-cp).T@(reference-cr))
    correction=np.eye(3); correction[2,2]=np.linalg.det(u@vt)
    rotation=u@correction@vt
    ligand_keys=sorted(rl)
    ligand_reference=np.stack([rl[k] for k in ligand_keys])
    ligand_predicted=np.stack([pl[k] for k in ligand_keys])
    aligned=(ligand_predicted-cp)@rotation+cr
    value=float(np.sqrt(np.mean(np.sum((aligned-ligand_reference)**2,axis=1))))
    if not math.isfinite(value):
        raise ValueError('Nonfinite receptor-aligned RMSD')
    return value

def benchmark(manifest_csv,output_json):
    rows=list(csv.DictReader(Path(manifest_csv).open(newline='',encoding='utf-8-sig')))
    if not rows: raise ValueError('No benchmarks')
    cases=[];seen=set()
    for row in rows:
        case=row['case_id']; family=row['family']; split=row['split']
        if not case or not family or split!='test': raise ValueError('Explicit independent test cases and protein families required')
        if case in seen: raise ValueError('Duplicate benchmark case')
        seen.add(case)
        rmsd=aligned_rmsd(row['reference_peptide_pdb'],row['predicted_peptide_pdb'])
        item={'case_id':case,'family':family,'aligned_heavy_atom_rmsd_angstrom':rmsd,'under_2A':rmsd<2.0}
        ref_rec=row.get('reference_receptor_pdb','').strip()
        pred_rec=row.get('predicted_receptor_pdb','').strip()
        if bool(ref_rec) != bool(pred_rec):
            raise ValueError('Both receptor PDBs must be supplied for interface RMSD')
        if ref_rec:
            site_rmsd=receptor_aligned_ligand_rmsd(ref_rec,pred_rec,row['reference_peptide_pdb'],row['predicted_peptide_pdb'])
            item['receptor_aligned_peptide_rmsd_angstrom']=site_rmsd
            item['receptor_aligned_under_2A']=site_rmsd<2.0
        cases.append(item)
    report={'status':'MEASURED_NOT_INDEPENDENCE_CERTIFIED','case_count':len(cases),'fraction_under_2A':sum(c['under_2A'] for c in cases)/len(cases),'cases':cases,'limitations':['Manifest split labels cannot prove no model training leakage','Receptor-aligned placement is reported only when both receptor structures are provided','Atom names and residue IDs must match']}
    Path(output_json).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report
