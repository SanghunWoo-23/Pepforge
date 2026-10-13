from __future__ import annotations

import json
from pathlib import Path

from peptiforg_core.haddock3_backend import prepare_haddock3_job, harvest_haddock3_poses, run_haddock3_job


def _pdb(path: Path, chain: str, residues=(1, 2)) -> Path:
    lines=[]
    atom=1
    for resi in residues:
        lines.append(f"ATOM  {atom:5d}  CA  ALA {chain}{resi:4d}    {resi*2.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C")
        atom+=1
    path.write_text("\n".join(lines)+"\nEND\n", encoding="utf-8")
    return path


def test_prepare_guided_haddock_job_writes_real_workflow_and_air(tmp_path: Path):
    rec=_pdb(tmp_path/'rec.pdb','A',(10,11,12))
    pep=_pdb(tmp_path/'pep.pdb','P',(1,2,3))
    m=prepare_haddock3_job(rec,pep,tmp_path/'job',binding_site_mode='manual',binding_site_residues=['A:10','12'],pose_limit=5,preset='fast')
    cfg=Path(m['prepared']['workflow_cfg']).read_text()
    air=Path(m['prepared']['restraint_tbl']).read_text()
    assert '[rigidbody]' in cfg and '[flexref]' in cfg and '[emref]' in cfg
    assert 'sampling = 200' in cfg and 'top_models = 5' in cfg
    assert 'resid 10 and segid A' in air and 'segid B' in air


def test_harvest_requires_real_score_table_and_pose(tmp_path: Path):
    run=tmp_path/'run'; stage=run/'05_caprieval'; stage.mkdir(parents=True)
    _pdb(stage/'model1.pdb','A',(1,2)); _pdb(stage/'model2.pdb','A',(1,2))
    (stage/'capri.tsv').write_text('structure\tscore\nmodel1.pdb\t-50.0\nmodel2.pdb\t-30.0\n',encoding='utf-8')
    result=harvest_haddock3_poses(run,tmp_path/'out',pose_limit=1)
    assert result['status']=='COMPLETED_SCORED_POSES'
    assert result['pose_count']==1 and result['poses'][0]['score']==-50.0
    assert Path(result['poses'][0]['pose_pdb']).exists()


def test_real_subprocess_contract_with_fake_haddock_executable(tmp_path: Path):
    rec=_pdb(tmp_path/'rec.pdb','A',(10,11,12)); pep=_pdb(tmp_path/'pep.pdb','P',(1,2,3))
    manifest=prepare_haddock3_job(rec,pep,tmp_path/'job',pose_limit=2,preset='fast')
    exe=tmp_path/'haddock3'
    exe.write_text(r'''#!/usr/bin/env python3
import pathlib,re,sys
if len(sys.argv)>1 and sys.argv[1] in ('--version','-h'):
 print('haddock3 2026.8.0'); raise SystemExit(0)
cfg=pathlib.Path(sys.argv[1]).read_text()
m=re.search(r'run_dir\s*=\s*"([^"]+)"',cfg); run=pathlib.Path(m.group(1)); stage=run/'05_caprieval'; stage.mkdir(parents=True,exist_ok=True)
for i,score in [(1,-77.5),(2,-66.0)]:
 p=stage/f'model{i}.pdb'; p.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nATOM      2  CA  ALA B   1       0.000   0.000   4.000  1.00  0.00           C\nEND\n')
(stage/'capri.tsv').write_text('structure\tscore\nmodel1.pdb\t-77.5\nmodel2.pdb\t-66.0\n')
''',encoding='utf-8')
    exe.chmod(0o755)
    result=run_haddock3_job(tmp_path/'job',executable=str(exe))
    assert result['status']=='COMPLETED_SCORED_POSES'
    assert len(result['poses'])==2
    assert Path(tmp_path/'job'/'haddock3_stdout.log').exists()
