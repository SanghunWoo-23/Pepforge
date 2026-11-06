from __future__ import annotations
"""Auditable RDKit MMFF94s evaluation of an explicit modified-peptide graph.

This is molecular-mechanics intramolecular conformer energy, NEVER binding
free energy, a protein-peptide docking score, or OpenMM production MD.
"""
import hashlib
import json
import math
from pathlib import Path


def evaluate_sdf(sdf_path: str | Path, report_path: str | Path, *, max_iterations: int = 200, optimize: bool = False) -> dict:
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem
    source = Path(sdf_path)
    if max_iterations < 1 or max_iterations > 100000:
        raise ValueError('max_iterations must be in 1..100000')
    input_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    supplier = Chem.SDMolSupplier(str(source), removeHs=False, sanitize=True)
    mols = [m for m in supplier if m is not None]
    if not mols:
        raise ValueError('SDF contains no readable sanitized molecule')
    results=[]
    for i,mol in enumerate(mols):
        row={'index':i, 'atoms':mol.GetNumAtoms(), 'conformers':mol.GetNumConformers(),
             'isomeric_smiles':Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)}
        # Stereochemistry is an explicit part of the molecular input contract.
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        row['chiral_centers'] = [{'atom_index': int(idx), 'cip': str(label)}
                                 for idx, label in Chem.FindMolChiralCenters(mol, includeUnassigned=True)]
        row['stereochemistry_provenance'] = 'Assigned from SDF stereotags/3D coordinates; original sequence D/L specification not independently validated'
        row['unassigned_chiral_centers'] = sum(center['cip'] == '?' for center in row['chiral_centers'])
        if row['unassigned_chiral_centers']:
            row.update(status='AMBIGUOUS_STEREOCHEMISTRY',
                       reason='At least one stereocenter is unspecified; parameter evaluation suppressed')
            results.append(row); continue
        if mol.GetNumConformers()==0:
            row.update(status='NO_COORDINATES'); results.append(row);continue
        model = Chem.AddHs(Chem.Mol(mol), addCoords=True)
        if not AllChem.MMFFHasAllMoleculeParams(model):
            row.update(status='UNPARAMETERIZED', reason='MMFF94s lacks parameters for one or more atoms; no fabricated substitute')
            results.append(row);continue
        props=AllChem.MMFFGetMoleculeProperties(model, mmffVariant='MMFF94s')
        if props is None:
            row.update(status='UNPARAMETERIZED');results.append(row);continue
        energies=[]
        for conformer in model.GetConformers():
            ff=AllChem.MMFFGetMoleculeForceField(model,props,confId=conformer.GetId())
            initial=ff.CalcEnergy()
            if not math.isfinite(initial):
                raise ValueError(f'Non-finite initial MMFF94s energy for molecule {i}')
            record={'conformer_id':conformer.GetId(),'initial_energy_kcal_mol':initial}
            if optimize:
                code=ff.Minimize(maxIts=max_iterations)
                final_energy = ff.CalcEnergy()
                if not math.isfinite(final_energy):
                    raise ValueError(f'Non-finite optimized MMFF94s energy for molecule {i}')
                record.update(minimizer_status=int(code),final_energy_kcal_mol=final_energy,
                              converged=(int(code) == 0))
            energies.append(record)
        row.update(status='EVALUATED', forcefield='MMFF94s', energy_unit='kcal/mol', energies=energies)
        results.append(row)
    output={'schema':'pepforge-v6-modified-ff-1', 'purpose':'INTRAMOLECULAR_CONFORMER_ENERGY_ONLY',
            'disclaimer':'NOT docking affinity, binding free energy, or validated OpenMM protein-peptide MD.',
            'input_sdf':str(source),'input_sha256':input_hash, 'rdkit_version':rdBase.rdkitVersion,
            'optimization_requested':bool(optimize),
            'parameterization_policy':'No invented atom types; reject unresolved stereocenters after SDF import and unsupported MMFF94s chemistry',
            'results':results}
    target=Path(report_path); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return output
