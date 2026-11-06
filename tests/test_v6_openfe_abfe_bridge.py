from pathlib import Path
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem
from peptiforg_core.v6_openfe_abfe_bridge import validate_inputs, prepare, ABFEInputError

def example(tmp_path):
    p=tmp_path/'pep.sdf'; r=tmp_path/'rec.pdb'
    m=Chem.AddHs(Chem.MolFromSmiles('NCC(=O)O'))
    assert AllChem.EmbedMolecule(m,randomSeed=31)==0
    w=Chem.SDWriter(str(p));w.write(m);w.close()
    r.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n')
    return r,p

def test_valid(tmp_path):
    r,p=example(tmp_path)
    assert validate_inputs(r,p)[2].GetNumAtoms()>0

def test_refuses_existing_output(tmp_path):
    r,p=example(tmp_path); output=tmp_path/'x.json';output.write_text('{}')
    with pytest.raises(FileExistsError): prepare(r,p,output)

def test_repeats_and_platform(tmp_path):
    r,p=example(tmp_path)
    with pytest.raises(ABFEInputError):prepare(r,p,tmp_path/'x.json',repeats=1)
    with pytest.raises(ABFEInputError):prepare(r,p,tmp_path/'x.json',platform='GPU')

def test_missing_receptor(tmp_path):
    _,p=example(tmp_path)
    with pytest.raises(ABFEInputError):validate_inputs(tmp_path/'missing.pdb',p)

def test_invalid_sdf(tmp_path):
    r,p=example(tmp_path);p.write_text('bad input')
    with pytest.raises(ABFEInputError):validate_inputs(r,p)
