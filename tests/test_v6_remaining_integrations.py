from pathlib import Path
import pytest
from peptiforg_core.v6_execution_devices import inspect_compute_devices
from peptiforg_core.v6_docking_inputs import write_pymol_review


def test_device_detection_does_not_promise_native_cuda():
    info = inspect_compute_devices()
    assert 'CPU' in info['native_docking']
    assert isinstance(info['openmm']['platforms'], list)
    assert isinstance(info['torch']['cuda_available'], bool)


def test_pymol_script_sequence_and_chemistry(tmp_path):
    inputs = tmp_path / 'inputs'; inputs.mkdir()
    for filename in ('receptor.pdb','peptide.pdb'):
        (inputs / filename).write_text('ATOM\n')
    (inputs / 'peptide_chemistry.sdf').write_text('MOLECULE\n')
    target = tmp_path / 'review.pml'
    write_pymol_review(inputs/'receptor.pdb', inputs/'peptide.pdb', [], target)
    contents = target.read_text()
    assert 'set seq_view, 1' in contents
    assert 'Peptide_chemistry' in contents


def test_manual_requires_residues_before_output(tmp_path):
    from peptiforg_core.v6_compute_pipeline import run_pipeline
    from peptiforg_core.native_docking_v1 import NativeDockingConfig
    with pytest.raises(ValueError, match='requires receptor binding residues'):
        run_pipeline('missing_r.pdb','missing_p.pdb',tmp_path/'out',config=NativeDockingConfig(mode='manual'))
    assert not (tmp_path/'out').exists()


def test_chemistry_sdf_kept_for_rdkit_adapter(tmp_path):
    pytest.importorskip('rdkit')
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol,randomSeed=3)==0
    input_sdf=tmp_path/'input.sdf'
    w=Chem.SDWriter(str(input_sdf));w.write(mol);w.close()
    from peptiforg_core.v6_docking_inputs import prepare_structure_file
    dest=tmp_path/'working'
    result=prepare_structure_file(input_sdf,dest,'peptide')
    assert Path(result).is_file()
    preserved=Chem.SDMolSupplier(str(dest/'peptide_chemistry.sdf'),removeHs=False)[0]
    assert preserved is not None
    assert Chem.MolToSmiles(Chem.RemoveHs(preserved),isomericSmiles=True)==Chem.MolToSmiles(Chem.RemoveHs(mol),isomericSmiles=True)
