from __future__ import annotations

import json
from pathlib import Path

from peptiforg_core.psb_v5_full_pipeline import run_psb_v5_pipeline


def _pdb(path: Path, chain='A'):
    path.write_text(f'ATOM      1  CA  ALA {chain}   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n',encoding='utf-8'); return path


def test_full_pipeline_prepares_without_fabricating_when_not_run(tmp_path: Path):
    models=[]; top=[]
    for rank in range(1,3):
        p=_pdb(tmp_path/f'p{rank}.pdb','P'); models.append(str(p)); top.append({'rank':rank,'conf_id':rank,'family':'coil','energy':float(rank)})
    meta=tmp_path/'psb.json'; meta.write_text(json.dumps({'input':'AA','top5_conformer_pdb_paths':models,'conformation_analysis':{'top_conformers':top}}))
    rec=_pdb(tmp_path/'rec.pdb','A')
    result=run_psb_v5_pipeline(meta,rec,tmp_path/'run',model_limit=2,run_docking=False)
    assert result['status']=='PREPARED_NOT_RUN'
    assert result['verified_pose_count']==0
    assert result['pymol']['status']=='NO_VERIFIED_POSES'
    assert not list((tmp_path/'run').rglob('pose_*.pdb'))


def test_full_pipeline_executes_fake_backend_then_dockbench_and_pymol(tmp_path: Path):
    models=[]; top=[]
    for rank in range(1,3):
        p=_pdb(tmp_path/f'p_exec{rank}.pdb','P'); models.append(str(p)); top.append({'rank':rank,'conf_id':rank,'family':'coil','energy':float(rank)})
    meta=tmp_path/'psb_exec.json'; meta.write_text(json.dumps({'input':'AA','top5_conformer_pdb_paths':models,'conformation_analysis':{'top_conformers':top}}))
    rec=tmp_path/'rec_exec.pdb'
    rec.write_text('ATOM      1  CA  ALA A  10       0.000   0.000   0.000  1.00  0.00           C\nATOM      2  CA  ALA A  11       4.000   0.000   0.000  1.00  0.00           C\nEND\n')
    exe=tmp_path/'haddock3'
    exe.write_text(r'''#!/usr/bin/env python3
import pathlib,re,sys
if len(sys.argv)>1 and sys.argv[1] in ('--version','-h'):
 print('haddock3 2026.8.0'); raise SystemExit(0)
cfg=pathlib.Path(sys.argv[1]).read_text(); run=pathlib.Path(re.search(r'run_dir\s*=\s*"([^"]+)"',cfg).group(1)); st=run/'05_caprieval'; st.mkdir(parents=True,exist_ok=True)
for i,score in [(1,-80.0),(2,-70.0)]:
 (st/f'm{i}.pdb').write_text('ATOM      1  CA  ALA A  10       0.000   0.000   0.000  1.00  0.00           C\nATOM      2  CA  ALA A  11       4.000   0.000   0.000  1.00  0.00           C\nTER\nATOM      3  CA  GLY B   1       0.000   0.000   4.000  1.00  0.00           C\nEND\n')
(st/'capri.tsv').write_text('structure\tscore\nm1.pdb\t-80.0\nm2.pdb\t-70.0\n')
''')
    exe.chmod(0o755)
    result=run_psb_v5_pipeline(meta,rec,tmp_path/'run_exec',model_limit=2,pose_limit_per_model=2,run_docking=True,haddock_executable=str(exe))
    assert result['status']=='DOCKING_COMPLETED'
    assert result['verified_pose_count']==4
    assert Path(result['pymol']['pml']).exists()
    assert result['dockbench']['pose_count']==4
