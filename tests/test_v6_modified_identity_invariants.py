"""Identity invariants for the chemical ensemble handed to docking."""
from pathlib import Path
import pytest

rdkit = pytest.importorskip('rdkit')
from rdkit import Chem
from rdkit.Chem import AllChem
from peptiforg_core.v6_ff_ensemble import refine_sdf_ensemble


def test_explicit_chiral_identity_survives_ensemble_export(tmp_path):
    starting = Chem.MolFromSmiles('N[C@@H](C)C(=O)N[C@H](CO)C(=O)O')
    original_smiles = Chem.MolToSmiles(starting, isomericSmiles=True)
    m = Chem.AddHs(starting)
    assert AllChem.EmbedMolecule(m, randomSeed=23) == 0
    inp = tmp_path / 'input.sdf'
    writer = Chem.SDWriter(str(inp)); writer.write(m); writer.close()
    out = tmp_path / 'out'
    result = refine_sdf_ensemble(inp, out, conformers=4, seed=23)
    structures = [x for x in Chem.SDMolSupplier(str(out/'mmff94s_diverse_converged.sdf'), removeHs=False) if x]
    assert structures
    for structure in structures:
        assert structure.GetProp('Pepforge_Input_Isomeric_SMILES') == original_smiles
        assert Chem.MolToSmiles(Chem.RemoveHs(structure), isomericSmiles=True) == original_smiles
