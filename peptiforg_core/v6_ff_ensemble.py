"""Deterministic, auditable MMFF94s conformer refinement for explicit modified-peptide SDFs.

Does not assert validated protein-peptide energetics or parameterize unsupported chemistries.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import shutil
import tempfile
from pathlib import Path


def _diverse_conformers(mol, rows, *, rmsd_cutoff, energy_window):
    """Greedy heavy-atom RMSD diversity screen of converged MMFF conformers."""
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign
    if mol.GetNumHeavyAtoms() == 0:
        raise ValueError("empty heavy-atom graph")
    ranked = sorted((r for r in rows if r["converged"]), key=lambda r: (r["final_kcal_mol"], r["conformer_id"]))
    if not ranked:
        return []
    floor = ranked[0]["final_kcal_mol"]
    selected = []
    heavy = Chem.RemoveHs(mol)
    for row in ranked:
        if row["final_kcal_mol"] - floor > energy_window:
            continue
        # BestRMS uses symmetry-aware atom correspondence and does not overwrite the
        # unaligned conformer coordinates when using temporary single-conformer copies.
        trial = Chem.Mol(heavy)
        trial.RemoveAllConformers()
        trial.AddConformer(Chem.Conformer(heavy.GetConformer(row["conformer_id"])), assignId=True)
        distinct = True
        for earlier in selected:
            reference = Chem.Mol(heavy)
            reference.RemoveAllConformers()
            reference.AddConformer(Chem.Conformer(heavy.GetConformer(earlier["conformer_id"])), assignId=True)
            if rdMolAlign.GetBestRMS(trial, reference) < rmsd_cutoff:
                distinct = False
                break
        if distinct:
            selected.append(row)
    return selected


def refine_sdf_ensemble(sdf_path, output_dir, *, conformers=12, seed=2026, max_iterations=500, prune_rms=0.5, diversity_rmsd=1.0, energy_window_kcal_mol=15.0):
    from rdkit import Chem, rdBase
    from rdkit.Chem import AllChem
    source = Path(sdf_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not 1 <= conformers <= 1000 or not 1 <= max_iterations <= 100000:
        raise ValueError('conformers/max_iterations out of safe range')
    if not isinstance(seed, int) or not 1 <= seed < 2**31:
        raise ValueError('seed must be an integer between 1 and 2^31-1')
    if not math.isfinite(prune_rms) or not 0 <= prune_rms <= 10:
        raise ValueError('prune_rms must be finite within 0..10')
    if not math.isfinite(diversity_rmsd) or not 0 < diversity_rmsd <= 20:
        raise ValueError("diversity_rmsd must be finite within (0,20]")
    if not math.isfinite(energy_window_kcal_mol) or not 0 <= energy_window_kcal_mol <= 1000:
        raise ValueError("energy_window_kcal_mol must be finite within [0,1000]")
    out = Path(output_dir)
    if out.is_symlink() or (out.exists() and (not out.is_dir() or any(out.iterdir()))):
        raise ValueError('output directory must be empty, a directory, and not a symlink')
    if not source.resolve().is_file():
        raise ValueError('SDF source is not a regular file')
    input_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    molecules = list(Chem.SDMolSupplier(str(source), sanitize=True, removeHs=False))
    if not molecules or any(m is None for m in molecules):
        raise ValueError('SDF contains invalid molecules; no partial result written')
    # Compute before writing, to avoid claiming partial success.
    records = []
    models = []
    best_models = []
    diverse_models = []
    for index, original in enumerate(molecules):
        original_identity = Chem.MolToSmiles(Chem.RemoveHs(original), isomericSmiles=True)
        mol = Chem.AddHs(Chem.Mol(original), addCoords=True)
        Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
        ambiguous = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
        if any(code == '?' for _, code in ambiguous):
            raise ValueError(f'molecule {index}: unresolved stereocenter; explicit stereo required')
        if not AllChem.MMFFHasAllMoleculeParams(mol):
            raise ValueError(f'molecule {index}: MMFF94s does not cover full molecule')
        props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant='MMFF94s')
        if props is None:
            raise ValueError(f'molecule {index}: parameter assignment failed')
        expected_stereo = {a.GetIdx(): a.GetProp("_CIPCode") for a in mol.GetAtoms() if a.HasProp("_CIPCode")}
        mol.RemoveAllConformers()
        params = AllChem.ETKDGv3()
        params.randomSeed = seed
        params.numThreads = 1
        params.pruneRmsThresh = float(prune_rms)
        params.enforceChirality = True
        ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=conformers, params=params))
        if not ids:
            raise RuntimeError(f'molecule {index}: ETKDG embedding yielded no conformers')
        per_conf = []
        for cid in ids:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
            if ff is None:
                raise RuntimeError('MMFF could not construct a force field')
            initial = float(ff.CalcEnergy())
            status = int(ff.Minimize(maxIts=max_iterations))
            energy = float(ff.CalcEnergy())
            if not all(map(math.isfinite, [initial, energy])):
                raise ValueError('non-finite energy')
            # Apply minimized force field coordinate values to the owned conformer.
            coordinates = ff.Positions()
            conf = mol.GetConformer(cid)
            for a in range(mol.GetNumAtoms()):
                from rdkit.Geometry import Point3D
                conf.SetAtomPosition(a, Point3D(*coordinates[3*a:3*a+3]))
            # Verify assigned tetrahedral stereochemistry after moving optimized coordinates.
            stereo_mol = Chem.Mol(mol)
            stereo_mol.RemoveAllConformers()
            stereo_mol.AddConformer(Chem.Conformer(conf), assignId=True)
            Chem.AssignStereochemistryFrom3D(stereo_mol)
            observed = {a.GetIdx(): a.GetProp('_CIPCode') for a in stereo_mol.GetAtoms() if a.HasProp('_CIPCode')}
            stereo_ok = all(observed.get(i) == cip for i, cip in expected_stereo.items())
            per_conf.append({'stereochemistry_preserved':stereo_ok,'conformer_id':int(cid),'initial_kcal_mol':initial,'final_kcal_mol':energy,
                             'converged':status == 0 and stereo_ok,'minimizer_status':status})
        selected = _diverse_conformers(mol, per_conf, rmsd_cutoff=diversity_rmsd, energy_window=energy_window_kcal_mol)
        for entry in selected:
            selected_mol = Chem.Mol(mol)
            selected_mol.RemoveAllConformers()
            selected_mol.AddConformer(Chem.Conformer(mol.GetConformer(entry["conformer_id"])), assignId=True)
            selected_mol.SetProp("Pepforge_Molecule_Index", str(index))
            selected_mol.SetProp("Pepforge_Conformer_ID", str(entry["conformer_id"]))
            selected_mol.SetProp("Pepforge_MMFF94s_kcal_mol", str(entry["final_kcal_mol"]))
            if Chem.MolToSmiles(Chem.RemoveHs(selected_mol), isomericSmiles=True) != original_identity:
                raise ValueError(f'molecule {index}: selected conformer changed molecular connectivity or stereochemistry')
            selected_mol.SetProp('Pepforge_Input_Isomeric_SMILES', original_identity)
            diverse_models.append(selected_mol)
        # Exclude non-converged conformers from best-conformer selection.
        valid = [r for r in per_conf if r['converged']]
        records.append({'molecule_index':index, 'input_isomeric_smiles':Chem.MolToSmiles(Chem.RemoveHs(original), isomericSmiles=True),
                        'chiral_centers': [{'atom_index':i,'cip':v} for i,v in ambiguous],
                        'generated_count':len(ids),'conformers':per_conf,
                        'diverse_conformer_ids':[r['conformer_id'] for r in selected],
                        'best_converged_conformer_id':min(valid,key=lambda r:r['final_kcal_mol'])['conformer_id'] if valid else None,
                        'status':'EVALUATED' if valid else 'NO_CONVERGED_CONFORMER'})
        models.append(mol)
        if valid:
            selected_id = min(valid, key=lambda r:r['final_kcal_mol'])['conformer_id']
            best = Chem.Mol(mol)
            best.RemoveAllConformers()
            best.AddConformer(Chem.Conformer(mol.GetConformer(selected_id)), assignId=True)
            best.SetProp('Pepforge_Molecule_Index', str(index))
            best.SetProp('Pepforge_Conformer_ID', str(selected_id))
            best.SetProp('Pepforge_MMFF94s_kcal_mol', str(min(valid,key=lambda r:r['final_kcal_mol'])['final_kcal_mol']))
            if Chem.MolToSmiles(Chem.RemoveHs(best), isomericSmiles=True) != original_identity:
                raise ValueError(f'molecule {index}: best conformer changed molecular identity')
            best.SetProp('Pepforge_Input_Isomeric_SMILES', original_identity)
            best_models.append(best)
    # Commit only after all computations pass; clean up partial writes on error.
    out.mkdir(parents=True, exist_ok=True)
    dest = out/'mmff94s_conformers.sdf'
    writer = Chem.SDWriter(str(dest))
    try:
        for index, model in enumerate(models):
            for conf in model.GetConformers():
                m = Chem.Mol(model)
                rec = next(r for r in records[index]['conformers'] if r['conformer_id'] == conf.GetId())
                m.SetProp('Pepforge_Molecule_Index',str(index))
                m.SetProp('Pepforge_Conformer_ID',str(conf.GetId()))
                m.SetProp('Pepforge_MMFF94s_kcal_mol',str(rec['final_kcal_mol']))
                m.SetProp('Pepforge_Converged',str(rec['converged']))
                writer.write(m,confId=conf.GetId())
    finally:
        writer.close()
    best_dest = out/'mmff94s_best_converged.sdf'
    best_writer = Chem.SDWriter(str(best_dest))
    try:
        for best in best_models:
            best_writer.write(best)
    finally:
        best_writer.close()
    diverse_dest = out/'mmff94s_diverse_converged.sdf'
    diverse_writer = Chem.SDWriter(str(diverse_dest))
    try:
        for model in diverse_models:
            diverse_writer.write(model)
    finally:
        diverse_writer.close()
    report = {'schema':'pepforge-mmff94s-ensemble-v3','purpose':'INTRAMOLECULAR_CONFORMER_REFINEMENT_ONLY',
              'not_validated_for':['binding_affinity','protein_peptide_complex_forcefield','MD'],
              'input_sha256':input_hash,'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
              'best_converged_sha256':hashlib.sha256(best_dest.read_bytes()).hexdigest(),
              'best_converged_count':len(best_models),
              'diverse_converged_count':len(diverse_models),
              'diverse_converged_sha256':hashlib.sha256(diverse_dest.read_bytes()).hexdigest(),
              'diversity_rmsd_angstrom':diversity_rmsd, 'energy_window_kcal_mol':energy_window_kcal_mol,
              'rdkit_version':rdBase.rdkitVersion, 'seed':seed, 'requested_conformers':conformers,
              'max_iterations':max_iterations,'prune_rms_angstrom':prune_rms,'results':records}
    (out/'mmff94s_ensemble_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return report
