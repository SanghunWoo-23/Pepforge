from pathlib import Path
import pytest
from peptiforg_core.v6_docking_inputs import prepare_structure_file,validate_protein_sequence


def test_pdb_file_retains_exact_input(tmp_path):
    p=tmp_path/'peptide.pdb'
    p.write_text('ATOM      1  CA  GLY P   1       1.000   2.000   3.000  1.00 20.00           C\n')
    assert prepare_structure_file(p,tmp_path/'out','peptide')==str(p.resolve())


def test_sdf_keeps_real_3d_atoms(tmp_path):
    rdkit=pytest.importorskip('rdkit')
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m=Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)NCC(=O)O'))
    assert AllChem.EmbedMolecule(m,randomSeed=123)==0
    f=tmp_path/'peptide.sdf'; Chem.MolToMolFile(m,str(f))
    pdb=prepare_structure_file(f,tmp_path/'out','peptide')
    assert Path(pdb).is_file() and 'HETATM' in Path(pdb).read_text()


def test_reject_unsupported_or_non3d(tmp_path):
    f=tmp_path/'pep.txt'; f.write_text('ACDEFG')
    with pytest.raises(ValueError,match='unsupported'):prepare_structure_file(f,tmp_path/'out','peptide')


def test_sequence_is_not_silently_rewritten():
    assert validate_protein_sequence('ACD\nEFG')=='ACDEFG'
    with pytest.raises(ValueError): validate_protein_sequence('ACDX')


def test_gui_offers_direct_peptide_file():
    text=(Path(__file__).parents[1]/'suite_gui'/'pymol_structure_builder_gui.py').read_text()
    assert 'def _start_v6_file_docking' in text
    assert 'self.v6_peptide_path' in text
    assert 'prepare_structure_file(kwargs["receptor_path"]' in text
