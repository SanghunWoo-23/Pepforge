"""Chemistry-aware peptide torsion exploration before ensemble docking.

MMFF94s ligand internal energies only. Receptor geometry is clash screened;
this is NOT a validated protein-peptide binding free-energy potential.
"""
from pathlib import Path
import hashlib, json, math, random

def sample_flexible_conformers(sdf, output, *, samples=24, seed=2026, max_rotatable=24):
    from rdkit import Chem
    from rdkit.Chem import AllChem, Lipinski, rdMolTransforms
    if type(samples) is not int or not 1 <= samples <= 500: raise ValueError('samples must be 1..500')
    if type(seed) is not int or not 0 <= seed < 2**31: raise ValueError('invalid seed')
    target=Path(output)
    if target.exists(): raise FileExistsError('output must not exist')
    mols=[m for m in Chem.SDMolSupplier(str(sdf),removeHs=False) if m is not None]
    if not mols or not mols[0].GetNumConformers():raise ValueError('3D SDF required')
    original=Chem.AddHs(mols[0],addCoords=True)
    identity=Chem.MolToSmiles(Chem.RemoveHs(original),isomericSmiles=True)
    props=AllChem.MMFFGetMoleculeProperties(original,mmffVariant='MMFF94s')
    if props is None:raise ValueError('MMFF94s parameters unavailable; do not invent force-field parameters')
    matches=original.GetSubstructMatches(Lipinski.RotatableBondSmarts)
    torsions=[]
    for j,k in matches:
        aj=original.GetAtomWithIdx(j); ak=original.GetAtomWithIdx(k)
        left=[n.GetIdx() for n in aj.GetNeighbors() if n.GetIdx()!=k and n.GetAtomicNum()>1]
        right=[n.GetIdx() for n in ak.GetNeighbors() if n.GetIdx()!=j and n.GetAtomicNum()>1]
        if left and right:torsions.append((left[0],j,k,right[0]))
    torsions=torsions[:max_rotatable]
    rng=random.Random(seed); results=[];target.parent.mkdir(parents=True,exist_ok=True)
    writer=Chem.SDWriter(str(target))
    try:
        for i in range(samples):
            mol=Chem.Mol(original)
            if i and torsions:
                conf=mol.GetConformer()
                for _ in range(min(len(torsions),max(1,2+i//8))):
                    t=rng.choice(torsions)
                    rdMolTransforms.SetDihedralDeg(conf,*t,rng.uniform(-180,180))
            ff=AllChem.MMFFGetMoleculeForceField(mol,props)
            if ff is None:continue
            code=ff.Minimize(maxIts=400)
            energy=ff.CalcEnergy()
            if code!=0 or not math.isfinite(energy):continue
            got=Chem.MolToSmiles(Chem.RemoveHs(mol),isomericSmiles=True)
            if got!=identity:continue
            mol.SetProp('Pepforge_Identity_SMILES',identity)
            mol.SetProp('Pepforge_MMFF94s_Internal_kcal_mol',str(energy))
            mol.SetProp('Pepforge_Conformer_Index',str(i))
            writer.write(mol)
            results.append({'index':i,'energy_kcal_mol':energy})
    finally:writer.close()
    report={'method':'ETKDG-compatible explicit torsion perturbations + MMFF94s intramolecular minimization', 'not_binding_free_energy':True,'sampling_attempts':samples,'successful_conformers':len(results),'rotatable_torsions':len(torsions),'structures':results,'sdf_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    Path(str(target)+'.json').write_text(json.dumps(report,indent=2)+'\n')
    if not results:raise RuntimeError('No chemically valid converged conformers')
    return report
