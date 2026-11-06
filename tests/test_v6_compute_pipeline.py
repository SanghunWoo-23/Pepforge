import json
from pathlib import Path
import pytest
from peptiforg_core.v6_compute_pipeline import preflight,run_pipeline,validate_native_config
from peptiforg_core.native_docking_v1 import NativeDockingConfig
from peptiforg_core.openmm_md_backend import OpenMMProtocol, validate_protocol

def test_invalid_docking_parameters():
    with pytest.raises(ValueError): validate_native_config(NativeDockingConfig(max_candidates=0))
    with pytest.raises(ValueError): validate_native_config(NativeDockingConfig(shell_distance_A=float('nan')))
    with pytest.raises(ValueError): validate_native_config(NativeDockingConfig(poses=-1))

def test_invalid_md_protocol():
    with pytest.raises(ValueError): validate_protocol(OpenMMProtocol(temperature_k=float('nan')))
    with pytest.raises(ValueError): validate_protocol(OpenMMProtocol(ionic_strength_molar=float('inf')))

def test_preflight_and_no_fake_success(tmp_path):
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    r.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n')
    p.write_text('ATOM      1  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C\n')
    info=preflight(r,p)
    assert info['status']=='PREFLIGHT_ONLY' and len(info['inputs']['receptor']['sha256'])==64
    with pytest.raises(ValueError): preflight(r,r)
    with pytest.raises(FileExistsError):
        output=tmp_path/'occupied'; output.mkdir(); (output/'existing').write_text('x')
        run_pipeline(r,p,output)

def test_reject_nonfolder_output_and_invalid_parameters(tmp_path):
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    r.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n')
    p.write_text('ATOM      1  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C\n')
    outfile=tmp_path/'out'; outfile.write_text('do not overwrite')
    with pytest.raises(NotADirectoryError): run_pipeline(r,p,outfile)
    assert outfile.read_text()=='do not overwrite'
    with pytest.raises(ValueError): validate_native_config(NativeDockingConfig(local_refine_steps=True))
    with pytest.raises(ValueError): validate_native_config(NativeDockingConfig(seed=-1))


def test_end_to_end_real_docking_md_not_requested(tmp_path):
    from tests.test_v5_native_docking_v1 import _write_pdb
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    _write_pdb(r,'A'); _write_pdb(p,'P',offset=(20,20,20))
    cfg=NativeDockingConfig(poses=2,anchor_count=3,rotations_per_anchor=3,max_candidates=9,local_refine_steps=1)
    result=run_pipeline(r,p,tmp_path/'run',config=cfg)
    assert result['status']=='DOCKING_COMPLETED_MD_NOT_REQUESTED'
    assert result['stages']['production_md']['status']=='NOT_REQUESTED'
    for pose in result['stages']['native_docking']['pose_artifacts']:
        assert Path(pose['pose_pdb']).is_file() and len(pose['sha256'])==64
    assert json.loads((tmp_path/'run'/'v6_compute_pipeline.json').read_text())['status']==result['status']

def test_md_blocked_on_failed_pose_quality(tmp_path, monkeypatch):
    from tests.test_v5_native_docking_v1 import _write_pdb
    import peptiforg_core.native_docking_v1 as native
    import peptiforg_core.openmm_md_backend as backend
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    _write_pdb(r,'A'); _write_pdb(p,'P',offset=(20,20,20))
    real_run=native.run_native_docking
    def run_failed_gate(*args, **kwargs):
        result=real_run(*args, **kwargs)
        for row in result['poses']:
            row['quality_gate']={'status':'FAIL'}
        return result
    monkeypatch.setattr(native, 'run_native_docking', run_failed_gate)
    def no_md(*args, **kwargs):
        raise AssertionError('MD must not be called on failed pose')
    monkeypatch.setattr(backend, 'run_openmm_replicates', no_md)
    cfg=NativeDockingConfig(poses=1,anchor_count=2,rotations_per_anchor=2,max_candidates=4)
    result=run_pipeline(r,p,tmp_path/'run',config=cfg,run_md=True)
    assert result['status']=='MD_BLOCKED_QUALITY_GATE'
    assert result['stages']['native_docking']['status']=='COMPLETED'


def test_preflight_rejects_nonstructure_and_nonfinite_coordinates(tmp_path):
    receptor=tmp_path/'receptor.pdb'; peptide=tmp_path/'peptide.pdb'
    peptide.write_text('ATOM      1  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C\n')
    receptor.write_text('this is not an actual PDB atom table\n')
    with pytest.raises(ValueError): preflight(receptor,peptide)
    receptor.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n')
    assert preflight(receptor,peptide)['inputs']['receptor']['parsed_atom_count']==1


def test_md_error_does_not_erase_docking_success(tmp_path,monkeypatch):
    from tests.test_v5_native_docking_v1 import _write_pdb
    import peptiforg_core.openmm_md_backend as backend
    rec=tmp_path/'rec.pdb'; pep=tmp_path/'pep.pdb'
    _write_pdb(rec,'A'); _write_pdb(pep,'P',offset=(20,20,20))
    def throw(*args,**kwargs):
        raise RuntimeError('intentional MD backend error')
    monkeypatch.setattr(backend,'run_openmm_replicates',throw)
    import peptiforg_core.native_docking_v1 as native
    original=native.run_native_docking
    def docking_with_pass(*args,**kwargs):
        result=original(*args,**kwargs)
        for row in result['poses']:
            row['quality_gate']={'status':'PASS'}
        return result
    monkeypatch.setattr(native,'run_native_docking',docking_with_pass)
    cfg=NativeDockingConfig(poses=1,anchor_count=2,rotations_per_anchor=2,max_candidates=4)
    report=run_pipeline(rec,pep,tmp_path/'run',config=cfg,run_md=True)
    assert report['status']=='MD_FAILED_DOCKING_COMPLETED'
    assert report['stages']['native_docking']['status']=='COMPLETED'
    assert report['stages']['production_md']['status']=='FAILED'
    assert json.loads((tmp_path/'run'/'v6_compute_pipeline.json').read_text())['status']==report['status']


def test_output_symlink_rejected(tmp_path):
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    r.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n')
    p.write_text('ATOM      1  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C\n')
    target=tmp_path/'target'; target.mkdir()
    link=tmp_path/'link'
    try: link.symlink_to(target,target_is_directory=True)
    except (OSError,NotImplementedError): pytest.skip('symlinks unavailable')
    with pytest.raises(ValueError,match='symbolic link'):
        run_pipeline(r,p,link)

def test_invalid_mode_type_and_protected_output(tmp_path):
    from dataclasses import replace
    with pytest.raises(ValueError, match='mode'):
        validate_native_config(replace(NativeDockingConfig(), mode=None))
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    r.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n')
    p.write_text('ATOM      1  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C\n')
    with pytest.raises(ValueError, match='root'):
        run_pipeline(r,p,Path.cwd())


def test_reject_docking_pose_count_mismatch(tmp_path,monkeypatch):
    from tests.test_v5_native_docking_v1 import _write_pdb
    import peptiforg_core.native_docking_v1 as native
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    _write_pdb(r,'A'); _write_pdb(p,'P',offset=(20,20,20))
    original=native.run_native_docking
    def wrong_count(*args,**kwargs):
        result=original(*args,**kwargs)
        result['selected_pose_count']=9999
        return result
    monkeypatch.setattr(native,'run_native_docking',wrong_count)
    cfg=NativeDockingConfig(poses=1,anchor_count=2,rotations_per_anchor=2,max_candidates=4)
    result=run_pipeline(r,p,tmp_path/'run',config=cfg)
    assert result['status']=='NO_VERIFIED_POSE'
    assert result['stages']['native_docking']['reported_pose_count']==9999

def test_engine_uses_verified_input_snapshots(tmp_path,monkeypatch):
    from tests.test_v5_native_docking_v1 import _write_pdb
    import peptiforg_core.native_docking_v1 as native
    from peptiforg_core.v6_compute_pipeline import sha256
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb'
    _write_pdb(r,'A'); _write_pdb(p,'P',offset=(20,20,20))
    original=native.run_native_docking
    observed=[]
    def verify_paths(receptor,peptide,*args,**kwargs):
        observed.extend([Path(receptor),Path(peptide)])
        assert all(path.parent.name=='input_snapshots' for path in observed)
        return original(receptor,peptide,*args,**kwargs)
    monkeypatch.setattr(native,'run_native_docking',verify_paths)
    cfg=NativeDockingConfig(poses=1,anchor_count=2,rotations_per_anchor=2,max_candidates=4)
    result=run_pipeline(r,p,tmp_path/'run',config=cfg)
    assert result['status']=='DOCKING_COMPLETED_MD_NOT_REQUESTED'
    assert result['input_snapshots']['receptor']['sha256']==sha256(r)
    assert result['input_snapshots']['peptide']['sha256']==sha256(p)
    assert len(observed)==2
