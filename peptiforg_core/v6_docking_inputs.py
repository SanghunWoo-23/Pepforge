"""Strict GUI input adapters: preserve atom coordinates and refuse silent chemistry substitution."""
from pathlib import Path
import re


def prepare_structure_file(source, output_dir, kind):
    """Return real PDB coordinates for docking; never fabricate a molecular structure."""
    path = Path(source).expanduser().resolve()
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(f'{kind}: choose an existing, nonempty structure file: {path}')
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == '.pdb':
        return str(path)
    dest = out / f'{kind}_converted.pdb'
    if suffix in {'.cif', '.mmcif'}:
        from peptiforg_core.structure_predictor_backends import convert_mmcif_to_pdb
        convert_mmcif_to_pdb(path, dest)
    elif suffix in {'.sdf', '.mol'}:
        try:
            from rdkit import Chem
        except ImportError as exc:
            raise RuntimeError(f'{kind}: RDKit is necessary to read {suffix} chemistry') from exc
        if suffix == '.sdf':
            supplier = Chem.SDMolSupplier(str(path), removeHs=False, sanitize=True)
            molecules = [m for m in supplier if m is not None]
            if len(molecules) != 1:
                raise ValueError(f'{kind}: SDF must contain exactly one valid molecule; found {len(molecules)}')
            mol = molecules[0]
        else:
            mol = Chem.MolFromMolFile(str(path), removeHs=False, sanitize=True)
        if mol is None or not mol.GetNumConformers():
            raise ValueError(f'{kind}: a chemically valid 3D conformer is required')
        # Preserve the authoritative bond orders, atom-level stereochemistry and
        # chemical identity in a companion SDF. PDB is a *coordinate adapter* only.
        from shutil import copyfile
        chemistry = out / f'{kind}_chemistry.sdf'
        writer = Chem.SDWriter(str(chemistry))
        writer.write(mol)
        writer.close()
        if not chemistry.is_file() or not chemistry.stat().st_size:
            raise ValueError(f'{kind}: could not export authoritative chemistry SDF')
        Chem.MolToPDBFile(mol, str(dest))
    else:
        raise ValueError(f'{kind}: unsupported format {suffix}; use PDB, mmCIF, SDF or MOL with 3D coordinates')
    from peptiforg_core.interface_quality import parse_pdb_atoms
    atoms = parse_pdb_atoms(dest)
    if len(atoms) == 0:
        raise ValueError(f'{kind}: conversion contained no readable atomic coordinates')
    return str(dest)


def validate_protein_sequence(sequence):
    seq = re.sub(r'\s+', '', str(sequence or '').replace('>', ''))
    if not seq or not re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', seq.upper()):
        raise ValueError('Receptor sequence must contain canonical one-letter amino acids; provide an experimental structure for modified targets.')
    return seq.upper()


def write_pymol_review(receptor_pdb, peptide_pdb, pose_pdbs, destination):
    """Create a PyMOL script with sequence panel and real atomic coordinates."""
    import json
    dest=Path(destination); dest.parent.mkdir(parents=True,exist_ok=True)
    def path(p):
        # PyMOL accepts slash-separated absolute paths; quoting escapes spaces/Korean names.
        return '"' + str(Path(p).resolve()).replace('\\','/').replace('"','\\"') + '"'
    commands=[
        'reinitialize',
        f'load {path(receptor_pdb)}, Receptor',
        f'load {path(peptide_pdb)}, Peptide_input',
        'hide everything',
        'show cartoon, Receptor',
        'show sticks, Peptide_input',
        'set seq_view, 1',
        'set seq_view_format, 1',  # PyMOL three-letter residue labels when available
        'set seq_view_label_spacing, 5',
    ]
    for i,pose in enumerate(pose_pdbs,1):
        commands += [f'load {path(pose)}, Docked_pose_{i}', f'show sticks, Docked_pose_{i}']
    # PyMOL sequence panel is the actual polymer sequence; ligand/nonstandard
    # fragments are displayed with chemically identified object labels instead.
    chemistry = Path(peptide_pdb).parent / 'peptide_chemistry.sdf'
    if chemistry.exists():
        commands += [f'load {path(chemistry)}, Peptide_chemistry',
                     'show sticks, Peptide_chemistry',
                     'set label_size, 12',
                     'label (Peptide_chemistry and name C1), resn']
    commands += ['orient Receptor', 'zoom all']
    dest.write_text('\n'.join(commands)+'\n',encoding='utf-8')
    return str(dest)
