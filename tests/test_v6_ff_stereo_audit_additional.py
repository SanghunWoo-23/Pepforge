import json
from pathlib import Path
import pytest


def _write_sdf(path, smiles):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(mol, randomSeed=53) == 0
    writer = Chem.SDWriter(str(path))
    writer.write(mol)
    writer.close()


def test_mmff_reports_defined_stereochemistry(tmp_path):
    from peptiforg_core.v6_modified_forcefield import evaluate_sdf
    sdf = tmp_path / 'chiral.sdf'
    _write_sdf(sdf, 'N[C@@H](C)C(=O)O')
    report = evaluate_sdf(sdf, tmp_path/'audit.json', optimize=True)
    row = report['results'][0]
    assert row['status'] == 'EVALUATED'
    assert row['chiral_centers'] and row['unassigned_chiral_centers'] == 0
    assert 'converged' in row['energies'][0]


def test_mmff_marks_sdf_stereochemistry_provenance(tmp_path):
    from peptiforg_core.v6_modified_forcefield import evaluate_sdf
    sdf = tmp_path / 'unknown.sdf'
    _write_sdf(sdf, 'NC(C)C(=O)O')
    report = evaluate_sdf(sdf, tmp_path/'audit.json')
    assert 'not independently validated' in report['results'][0]['stereochemistry_provenance']
    # 3D SDF files can carry geometry-derived stereochemistry even if input SMILES was unspecified.
    assert report['results'][0]['status'] == 'EVALUATED'


def test_pymol_script_sequence_labels(tmp_path):
    from pepforge_structure_tool.pymol_script import make_pymol_pml
    (tmp_path/'peptide.pdb').write_text('END\n')
    meta = {'pdb_path':str(tmp_path/'peptide.pdb'), 'atom_ranges':[
        {'token':'dK','kind':'d_std_aa','heavy_start_1based':1,'heavy_end_1based':4},
        {'token':'PEG4','kind':'linker','heavy_start_1based':5,'heavy_end_1based':9},
    ]}
    mp=tmp_path/'peptide.json'; mp.write_text(json.dumps(meta))
    pml=make_pymol_pml(mp,prefer='pdb')
    text=pml.read_text()
    assert 'set seq_view_label_mode, 1' in text
    assert 'sort' in text and 'rebuild' in text
    table=(tmp_path/'peptide_sequence_token_map.tsv').read_text()
    assert 'PEG4' in table and 'dK' in table
