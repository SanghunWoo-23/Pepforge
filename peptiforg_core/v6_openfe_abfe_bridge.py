"""Prepare a real OpenFE ABFE transformation; never fabricate computed energies.

API follows the official OpenFE ABFE tutorial (accessed 2026-10-20).
Requires a separately installed, supported OpenFE environment for preparation.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

class ABFEInputError(ValueError):
    pass

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_inputs(receptor, peptide):
    from rdkit import Chem
    receptor, peptide = Path(receptor), Path(peptide)
    if not receptor.is_file() or receptor.suffix.lower() != '.pdb':
        raise ABFEInputError('Receptor must be an existing prepared PDB file')
    if not peptide.is_file() or peptide.suffix.lower() != '.sdf':
        raise ABFEInputError('Modified peptide must be an existing SDF file')
    supplier = Chem.SDMolSupplier(str(peptide), removeHs=False)
    if len(supplier) != 1 or supplier[0] is None:
        raise ABFEInputError('SDF must contain exactly one valid molecule')
    mol = supplier[0]
    if mol.GetNumConformers() != 1 or not mol.GetConformer().Is3D():
        raise ABFEInputError('ABFE requires one explicit 3D conformer')
    if not any(a.GetSymbol() == 'C' for a in mol.GetAtoms()):
        raise ABFEInputError('Peptide chemistry invalid: no carbon atoms')
    if mol.GetNumAtoms() > 600:
        raise ABFEInputError('Unusually large ligand: manual chemistry review required (>600 atoms)')
    lines = receptor.read_text(errors='replace').splitlines()
    if not any(l.startswith(('ATOM  ','HETATM')) for l in lines):
        raise ABFEInputError('Receptor PDB has no atomic coordinates')
    return receptor, peptide, mol

def prepare(receptor, peptide, output, *, platform='CPU', repeats=3):
    """Create official OpenFE Transformation JSON, not run the simulation.

    Platform is explicitly selected; avoid assuming CUDA on laboratory PCs.
    """
    if platform not in ('CPU', 'CUDA', 'OpenCL'):
        raise ABFEInputError('platform must be CPU/CUDA/OpenCL')
    if not isinstance(repeats, int) or repeats < 3:
        raise ABFEInputError('at least three protocol repeats required for production setup')
    receptor, peptide, mol = validate_inputs(receptor, peptide)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    try:
        import openfe
        from openfe.protocols.openmm_afe import AbsoluteBindingProtocol
    except ImportError as exc:
        raise RuntimeError('OpenFE is not installed: use an OpenFE-supported conda/WSL2 environment') from exc
    ligand = openfe.SmallMoleculeComponent.from_rdkit(mol)
    protein = openfe.ProteinComponent.from_pdb_file(str(receptor))
    solvent = openfe.SolventComponent()
    state_a = openfe.ChemicalSystem({'ligand': ligand, 'protein':protein, 'solvent':solvent}, name='pepforge_abfe')
    state_b = openfe.ChemicalSystem({'protein':protein, 'solvent':solvent})
    settings = AbsoluteBindingProtocol.default_settings()
    settings.protocol_repeats = repeats
    settings.engine_settings.compute_platform = platform
    protocol = AbsoluteBindingProtocol(settings=settings)
    transformation = openfe.Transformation(stateA=state_a, stateB=state_b, mapping=None, protocol=protocol, name='pepforge_abfe')
    # Serialize completely before writing final output; a failure must not create partial artifacts.
    import tempfile, os
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.json', delete=False) as tmp:
        temporary = Path(tmp.name)
    try:
        transformation.dump(temporary)
        payload = json.loads(temporary.read_text())
        if not isinstance(payload, dict):
            raise RuntimeError('Invalid OpenFE serialization')
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    manifest = {
        'status':'PREPARED_NOT_EXECUTED',
        'receptor_sha256':sha256(receptor), 'peptide_sha256':sha256(peptide),
        'transformation_sha256':sha256(output),
        'platform':platform, 'protocol_repeats':repeats,
        'method':'OpenFE AbsoluteBindingProtocol with built-in orientational restraint and cycle corrections',
        'warning':'Do not add independent Boresch correction to OpenFE final ABFE estimate.',
        'command':f'openfe quickrun "{output.name}" -o results.json -d abfe_workdir',
    }
    audit_path = output.with_suffix('.manifest.json')
    audit_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    return manifest
