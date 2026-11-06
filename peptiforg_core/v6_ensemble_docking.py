"""Audited CPU-compatible ensemble docking; no claim of binding free energy.

Each independently refined 3D chemical conformer runs through the existing
native docking implementation.  Failures are recorded, never silently ranked.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import math


def _hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_ensemble_docking(receptor, peptide_sdf, output, *, conformers=12,
                         max_structures=8, seed=2026, poses=3, max_candidates=250,
                         mode='blind', binding_residues=None):
    from rdkit import Chem
    from .v6_ff_ensemble import refine_sdf_ensemble
    from .v6_docking_inputs import prepare_structure_file, write_pymol_review
    from .v6_compute_pipeline import run_pipeline
    from .native_docking_v1 import NativeDockingConfig

    if type(conformers) is not int or not 1 <= conformers <= 100:
        raise ValueError('conformers must be 1..100')
    if type(max_structures) is not int or not 1 <= max_structures <= 40:
        raise ValueError('max_structures must be 1..40')
    if type(poses) is not int or not 1 <= poses <= 20:
        raise ValueError('poses must be 1..20')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 200000:
        raise ValueError('max_candidates must be 1..200000')
    if type(seed) is not int or not 1 <= seed < 2**31-1:
        raise ValueError('seed must be an integer between 1 and 2^31-1')
    if mode not in {'blind','manual','hotspot'}:
        raise ValueError('unsupported docking mode')
    if mode != 'blind' and not binding_residues:
        raise ValueError('manual/hotspot mode requires binding residues')
    raw_out = Path(output).expanduser()
    if raw_out.is_symlink() or any(p.is_symlink() for p in raw_out.parents):
        raise ValueError('Symlink output or parent prohibited')
    out = raw_out.resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise FileExistsError('Output must be a fresh/empty directory')
    # Reject invalid inputs before creating the work area.
    if not Path(receptor).is_file() or not Path(peptide_sdf).is_file():
        raise FileNotFoundError('Both receptor structure and peptide SDF must exist')
    if Path(receptor).resolve() == Path(peptide_sdf).resolve():
        raise ValueError('Receptor and peptide must be separate inputs')
    if Path(peptide_sdf).suffix.lower() != '.sdf':
        raise ValueError('Modified-peptide input must be an explicit SDF molecular graph')
    from shutil import copyfile
    out.mkdir(parents=True, exist_ok=True)
    input_dir = out / 'input_snapshots'
    input_dir.mkdir()
    rec_snapshot = input_dir / ('receptor' + Path(receptor).suffix.lower())
    pep_snapshot = input_dir / 'modified_peptide.sdf'
    before_rec, before_pep = _hash(receptor), _hash(peptide_sdf)
    copyfile(receptor, rec_snapshot)
    copyfile(peptide_sdf, pep_snapshot)
    if _hash(rec_snapshot) != before_rec or _hash(pep_snapshot) != before_pep or _hash(receptor) != before_rec or _hash(peptide_sdf) != before_pep:
        raise RuntimeError('Input files changed during snapshot creation')
    report={'schema':'pepforge.v6.ensemble_docking.v1', 'status':'RUNNING',
            'method':'RDKit MMFF94s conformer refinement + native rigid-body geometry search',
            'limitations':['Not an AF3/ESMFold structure predictor',
                           'Native score is not binding free energy or kcal/mol',
                           'PDB docking adapter cannot encode SDF bond orders or torsional flexibility'],
            'inputs':{'receptor_sha256':before_rec, 'peptide_sdf_sha256':before_pep,
                      'receptor_snapshot':str(rec_snapshot), 'peptide_snapshot':str(pep_snapshot)},
            'runs':[]}
    manifest=out/'ensemble_docking_report.json'
    def save():
        temp=manifest.with_suffix('.json.tmp')
        temp.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
        temp.replace(manifest)
    save()
    try:
        rec=prepare_structure_file(rec_snapshot,out/'prepared_receptor','receptor')
        ff=refine_sdf_ensemble(pep_snapshot,out/'conformer_refinement',conformers=conformers,seed=seed)
        report['force_field']={'report_path':str(out/'conformer_refinement'/'mmff94s_ensemble_report.json'),
                               'report_sha256':_hash(out/'conformer_refinement'/'mmff94s_ensemble_report.json')}
        source=out/'conformer_refinement'/'mmff94s_diverse_converged.sdf'
        valid=[m for m in Chem.SDMolSupplier(str(source),removeHs=False) if m is not None]
        if not valid:
            report['status']='NO_CONVERGED_CONFORMER';save();return report
        for i,mol in enumerate(valid[:max_structures],1):
            work=out/f'conformer_{i:03d}'
            work.mkdir()
            sdf=work/'peptide.sdf'
            writer=Chem.SDWriter(str(sdf));writer.write(mol);writer.close()
            original_smiles = mol.GetProp('Pepforge_Input_Isomeric_SMILES') if mol.HasProp('Pepforge_Input_Isomeric_SMILES') else Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
            actual_smiles = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
            if actual_smiles != original_smiles:
                raise ValueError(f'Conformer {i}: identity/stereochemistry mismatch')
            row={'index':i,'sdf_sha256':_hash(sdf),'isomeric_smiles':original_smiles,
                 'mmff94s_intramolecular_kcal_mol':float(mol.GetProp('Pepforge_MMFF94s_kcal_mol')),
                 'status':'RUNNING'}
            report['runs'].append(row);save()
            try:
                pdb=prepare_structure_file(sdf,work/'prepared','peptide')
                config=NativeDockingConfig(mode=mode,poses=poses,max_candidates=max_candidates,seed=seed+i)
                result=run_pipeline(rec,pdb,work/'docking',config=config,binding_residues=binding_residues)
                row['status']='COMPLETED' if result['status']=='DOCKING_COMPLETED_MD_NOT_REQUESTED' else result['status']
                row['manifest']=str(work/'docking'/'v6_compute_pipeline.json')
                row['manifest_sha256']=_hash(row['manifest'])
                stage=result.get('stages',{}).get('native_docking',{})
                row['verified_pose_count']=stage.get('verified_pose_count',0)
                if row['status']=='COMPLETED' and not row['verified_pose_count']:
                    row['status']='FAILED_ZERO_VERIFIED_POSES'
                if row['status']=='COMPLETED':
                    pose_paths=[entry['pose_pdb'] for entry in stage.get('pose_artifacts',[])]
                    review=write_pymol_review(rec,pdb,pose_paths,work/'review_in_pymol.pml')
                    row['pymol_script']=review
                    row['pymol_script_sha256']=_hash(review)
            except Exception as exc:
                row['status']='FAILED'
                row['error']=f'{type(exc).__name__}: {exc}'
            save()
        report['successful_conformers']=sum(r['status']=='COMPLETED' for r in report['runs'])
        report['failed_conformers']=len(report['runs'])-report['successful_conformers']
        report['status']='COMPLETED' if report['runs'] and all(r['status']=='COMPLETED' for r in report['runs']) else 'PARTIAL_OR_FAILED'
    except Exception as exc:
        report['status']='FAILED'
        report['error']=f'{type(exc).__name__}: {exc}'
        save()
        raise
    save()
    return report
