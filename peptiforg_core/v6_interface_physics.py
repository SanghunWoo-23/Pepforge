"""Conservative receptor-conditioned flexible pose refinement.

Uses RDKit MMFF94s intramolecular energy and a differentiable heavy-atom
steric/contact *heuristic*. This is not a parameterized binding free energy.
Does not change molecular bonds or stereochemistry; rejects unsupported MMFF.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def _receptor_heavy_xyz(path):
    import numpy as np
    xyz = []
    for line in Path(path).read_text(errors='replace').splitlines():
        if not line.startswith(('ATOM  ', 'HETATM')) or len(line) < 54:
            continue
        alt = line[16:17]
        if alt not in (' ', 'A'):
            continue
        element = line[76:78].strip().upper() if len(line) >= 78 else ''
        if not element:
            element = ''.join(c for c in line[12:16].strip() if c.isalpha())[:1].upper()
        if element in ('H', 'D'):
            continue
        coords = [float(line[i:i + 8]) for i in (30, 38, 46)]
        if not all(math.isfinite(v) for v in coords):
            raise ValueError('Nonfinite receptor atom coordinates')
        xyz.append(coords)
    if not xyz:
        raise ValueError('Receptor contains no usable heavy atoms')
    return np.asarray(xyz, dtype=float)


def refine_interface_pose(receptor_pdb, peptide_sdf, output_sdf, *, max_iterations=1000,
                          clash_distance=2.8, contact_distance=4.0,
                          steric_weight=14.0, contact_weight=0.10):
    """Optimize full ligand coordinates in receptor frame; no invented ΔG.

    Only use for physically plausible starting docked poses. A soft interfacial
    heuristic complements (never replaces) MMFF94s ligand intramolecular FF.
    """
    import numpy as np
    from scipy.optimize import minimize
    from scipy.spatial import cKDTree
    from rdkit import Chem
    from rdkit.Chem import AllChem
    for name, val in [('clash_distance', clash_distance), ('contact_distance', contact_distance),
                      ('steric_weight', steric_weight), ('contact_weight', contact_weight)]:
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
            raise ValueError(f'{name} must be positive and finite')
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10000:
        raise ValueError('max_iterations must be integer in 1..10000')
    if contact_distance <= clash_distance:
        raise ValueError('Contact distance must exceed clash distance')
    out = Path(output_sdf)
    if out.exists() or out.is_symlink():
        raise FileExistsError('Refusing to overwrite pose')
    if out.suffix.lower() != '.sdf':
        raise ValueError('Output must be an SDF file')
    supplier = Chem.SDMolSupplier(str(peptide_sdf), removeHs=False)
    valid = [m for m in supplier if m is not None]
    if len(valid) != 1 or not valid[0].GetNumConformers():
        raise ValueError('Exactly one valid 3D ligand molecule is required')
    mol = Chem.AddHs(valid[0], addCoords=True)
    params = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant='MMFF94s')
    if params is None:
        raise ValueError('MMFF94s does not parameterize this chemistry')
    rec = _receptor_heavy_xyz(receptor_pdb)
    tree = cKDTree(rec)
    ligand_elements = np.asarray([a.GetAtomicNum() > 1 for a in mol.GetAtoms()])
    initial = np.asarray(mol.GetConformer().GetPositions(), dtype=float)
    if not np.isfinite(initial).all():
        raise ValueError('Nonfinite ligand coordinates')
    original_smiles = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
    # Cache receptor neighbors once around starting ligand with generous reach;
    # a translated-away ligand gains no interface reward, preventing false affinity.
    def evaluate(vector):
        xyz = vector.reshape((-1, 3))
        ff = AllChem.MMFFGetMoleculeForceField(mol, params, ignoreInterfragInteractions=False)
        flat = tuple(float(v) for v in vector)
        e_internal = ff.CalcEnergy(flat)
        grad = np.asarray(ff.CalcGrad(flat), dtype=float).reshape((-1, 3))
        for i in np.flatnonzero(ligand_elements):
            close = tree.query_ball_point(xyz[i], r=contact_distance + 1.0)
            if not close:
                continue
            delta = xyz[i] - rec[close]
            ds = np.maximum(np.linalg.norm(delta, axis=1), 1e-8)
            # soft steric repulsion + shallow short-range geometric contact.
            overlap = np.maximum(clash_distance - ds, 0.0)
            e_internal += steric_weight * float(np.dot(overlap, overlap))
            slope = -2.0 * steric_weight * overlap
            # Smooth attraction centered at contact_distance; purely heuristic.
            t = (ds - contact_distance) / 0.7
            gaussian = np.exp(-0.5 * t * t)
            e_internal -= contact_weight * float(gaussian.sum())
            slope += contact_weight * gaussian * t / 0.7
            grad[i] += np.sum((slope / ds)[:, None] * delta, axis=0)
        return float(e_internal), grad.flatten().astype(float)
    result = minimize(evaluate, initial.flatten(), jac=True, method='L-BFGS-B',
                      options={'maxiter': max_iterations, 'ftol': 1e-9})
    if not np.isfinite(result.x).all() or not math.isfinite(result.fun):
        raise RuntimeError('Nonfinite interface refinement outcome')
    if not result.success:
        raise RuntimeError(f'Interface refinement did not converge: {result.message}')
    new = np.asarray(result.x).reshape((-1, 3))
    for idx, pos in enumerate(new):
        mol.GetConformer().SetAtomPosition(idx, tuple(float(x) for x in pos))
    if Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True) != original_smiles:
        raise RuntimeError('Chemical identity changed during refinement')
    # Validate the final geometrical pose against the requested input chirality.
    # The molecular graph alone cannot detect an inverted 3D stereocentre.
    check = Chem.Mol(mol)
    Chem.AssignStereochemistryFrom3D(check)
    starting = Chem.Mol(Chem.AddHs(valid[0], addCoords=True))
    Chem.AssignStereochemistryFrom3D(starting)
    def centres(m):
        return {i: tag for i, tag in Chem.FindMolChiralCenters(m, includeUnassigned=True)}
    if centres(check) != centres(starting):
        raise RuntimeError('3D stereochemistry changed during interface refinement')
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {'method': 'MMFF94s + empirical steric/contact geometry',
              'is_binding_free_energy': False,
              'notes': 'Receptor fixed; ligand Cartesian relaxation, not validated molecular docking affinity',
              'converged': bool(result.success), 'iterations': int(result.nit),
              'initial_objective': float(evaluate(initial.flatten())[0]),
              'final_objective': float(result.fun),
              'initial_smiles': original_smiles,
              'sdf_sha256': None}
    # Write both products to temporary files, and publish the report last.
    # Failed computation must never look like a successful completed run.
    tmpname = None
    try:
        with tempfile.NamedTemporaryFile(dir=out.parent, suffix='.sdf', delete=False) as tmp:
            tmpname = tmp.name
        writer = Chem.SDWriter(tmpname)
        try:
            mol.SetProp('Pepforge_Interface_Score_Not_DeltaG', str(float(result.fun)))
            writer.write(mol)
        finally:
            writer.close()
        check_supplier = Chem.SDMolSupplier(tmpname, removeHs=False)
        if len(check_supplier) != 1 or check_supplier[0] is None:
            raise RuntimeError('Generated SDF could not be read back')
        report['sdf_sha256'] = hashlib.sha256(Path(tmpname).read_bytes()).hexdigest()
        report_path = out.with_suffix('.json')
        if report_path.exists() or report_path.is_symlink():
            raise FileExistsError('Refusing to overwrite existing report')
        os.replace(tmpname, out)
        tmpname = None
        tmp_report = None
        try:
            with tempfile.NamedTemporaryFile(dir=out.parent, suffix='.json', mode='w', encoding='utf8', delete=False) as tmp:
                tmp_report = tmp.name
                json.dump(report, tmp, indent=2)
                tmp.write('\n')
            os.replace(tmp_report, report_path)
        except BaseException:
            out.unlink(missing_ok=True)
            raise
        finally:
            if tmp_report is not None:
                Path(tmp_report).unlink(missing_ok=True)
        return report
    finally:
        if tmpname is not None:
            Path(tmpname).unlink(missing_ok=True)
