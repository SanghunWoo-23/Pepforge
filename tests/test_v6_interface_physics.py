import pytest
from pathlib import Path
from peptiforg_core.v6_interface_physics import refine_interface_pose


def _fixtures(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles('CCO'))
    assert AllChem.EmbedMolecule(mol, randomSeed=17) == 0
    AllChem.MMFFOptimizeMolecule(mol)
    ligand = tmp_path / 'ligand.sdf'
    writer = Chem.SDWriter(str(ligand)); writer.write(mol); writer.close()
    receptor = tmp_path / 'receptor.pdb'
    receptor.write_text('ATOM      1  C   ALA A   1       3.500   0.000   0.000  1.00 20.00           C\nEND\n')
    return receptor, ligand


def test_interface_real_calculation_and_provenance(tmp_path):
    rec, lig = _fixtures(tmp_path)
    output = tmp_path / 'relaxed.sdf'
    result = refine_interface_pose(rec, lig, output)
    assert result['converged'] and output.stat().st_size > 0
    assert result['is_binding_free_energy'] is False
    assert output.with_suffix('.json').is_file()
    from rdkit import Chem
    initial = Chem.SDMolSupplier(str(lig), removeHs=False)[0]
    actual = Chem.SDMolSupplier(str(output), removeHs=False)[0]
    assert Chem.MolToSmiles(Chem.RemoveHs(initial), isomericSmiles=True) == Chem.MolToSmiles(Chem.RemoveHs(actual), isomericSmiles=True)
    with pytest.raises(FileExistsError):
        refine_interface_pose(rec, lig, output)


def test_invalid_receptor_and_config(tmp_path):
    rec, lig = _fixtures(tmp_path)
    with pytest.raises(ValueError):
        refine_interface_pose(rec, lig, tmp_path/'x.sdf', contact_distance=2.0)
    rec.write_text('END\n')
    with pytest.raises(ValueError):
        refine_interface_pose(rec, lig, tmp_path/'y.sdf')


def test_report_collision_keeps_existing_data(tmp_path):
    rec, lig = _fixtures(tmp_path)
    out = tmp_path / 'refined.sdf'
    report = out.with_suffix('.json')
    report.write_text('original report')
    with pytest.raises(FileExistsError):
        refine_interface_pose(rec, lig, out)
    assert report.read_text() == 'original report'
    assert not out.exists()


def test_output_extension_must_be_sdf(tmp_path):
    rec, lig = _fixtures(tmp_path)
    with pytest.raises(ValueError, match='SDF'):
        refine_interface_pose(rec, lig, tmp_path / 'wrong.pdb')
