import json
import pytest
from peptiforg_core.v6_ensemble_docking import run_ensemble_docking


def _inputs(tmp_path):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from tests.test_v5_native_docking_v1 import _write_pdb
    receptor = tmp_path/'receptor.pdb'
    _write_pdb(receptor,'A')
    mol=Chem.AddHs(Chem.MolFromSmiles('N[C@@H](C)C(=O)N[C@H](C)C(=O)O'))
    assert AllChem.EmbedMolecule(mol,randomSeed=12)==0
    peptide=tmp_path/'peptide.sdf'
    with Chem.SDWriter(str(peptide)) as w: w.write(mol)
    return receptor,peptide


def test_real_multi_conformer_docking(tmp_path):
    receptor,peptide=_inputs(tmp_path)
    report=run_ensemble_docking(receptor,peptide,tmp_path/'out',conformers=3,max_structures=2,poses=1,max_candidates=6)
    assert report['status']=='COMPLETED', report
    assert report['runs'] and all(r['verified_pose_count']>=1 for r in report['runs'])
    assert (tmp_path/'out/ensemble_docking_report.json').is_file()
    assert json.loads((tmp_path/'out/ensemble_docking_report.json').read_text())['status']=='COMPLETED'


def test_rejects_unsafe_parameters_and_existing_output(tmp_path):
    receptor,peptide=_inputs(tmp_path)
    with pytest.raises(ValueError):run_ensemble_docking(receptor,peptide,tmp_path/'out',max_structures=0)
    with pytest.raises(ValueError):run_ensemble_docking(receptor,peptide,tmp_path/'out',mode='manual')
    occupied=tmp_path/'occupied';occupied.mkdir();(occupied/'old').write_text('keep')
    with pytest.raises(FileExistsError):run_ensemble_docking(receptor,peptide,occupied)
    assert (occupied/'old').read_text()=='keep'


def test_snapshot_inputs_and_hashes(tmp_path):
    import hashlib
    receptor, peptide = _inputs(tmp_path)
    report = run_ensemble_docking(receptor, peptide, tmp_path/'snapshot_out',
                                  conformers=2, max_structures=1, poses=1, max_candidates=6)
    assert report['status'] == 'COMPLETED'
    for label, key in [('receptor_snapshot','receptor_sha256'),('peptide_snapshot','peptide_sdf_sha256')]:
        path = __import__('pathlib').Path(report['inputs'][label])
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == report['inputs'][key]
    assert (tmp_path/'snapshot_out/input_snapshots/modified_peptide.sdf').is_file()


def test_reject_invalid_seed_before_output(tmp_path):
    receptor, peptide = _inputs(tmp_path)
    with pytest.raises(ValueError, match='seed'):
        run_ensemble_docking(receptor, peptide, tmp_path/'bad_seed', seed=0)
    assert not (tmp_path/'bad_seed').exists()
