from pathlib import Path
from peptiforg_core.native_geometry_dynamics_v1 import NativeGeometryDynamicsConfig, run_native_geometry_dynamics


def _pdb(path:Path):
    lines=[
      "ATOM      1    N ALA P   1       0.000   0.000   0.000  1.00  0.00           N",
      "ATOM      2   CA ALA P   1       1.450   0.000   0.000  1.00  0.00           C",
      "ATOM      3    C ALA P   1       2.400   1.000   0.000  1.00  0.00           C",
      "ATOM      4    O ALA P   1       2.200   2.200   0.000  1.00  0.00           O",
      "ATOM      5    N GLY P   2       3.500   0.600   0.000  1.00  0.00           N",
      "ATOM      6   CA GLY P   2       4.600   1.400   0.000  1.00  0.00           C",
      # deliberately overlapping nonbonded oxygen to exercise repulsion
      "ATOM      7    O GLY P   2       1.600   0.100   0.000  1.00  0.00           O",
      "END",
    ]
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def test_native_geometry_dynamics_outputs_real_trace_and_restart(tmp_path):
    src=tmp_path/'x.pdb'; _pdb(src)
    cfg=NativeGeometryDynamicsConfig(steps=20,save_every=5,step_size=0.002,noise_scale=0.0)
    r=run_native_geometry_dynamics(src,tmp_path/'run',config=cfg)
    assert r['status']=='COMPLETED'
    assert r['evidence_grade']=='EXPERIMENTAL_GEOMETRY_DYNAMICS'
    assert Path(r['final_pdb']).exists() and Path(r['trace_csv']).exists() and Path(r['restart_state']).exists()
    assert len(r['frames'])>=5
    assert 'not production molecular dynamics' in r['claim_guard'].lower()


def test_native_geometry_dynamics_restart(tmp_path):
    src=tmp_path/'x.pdb'; _pdb(src)
    cfg=NativeGeometryDynamicsConfig(steps=5,save_every=5)
    a=run_native_geometry_dynamics(src,tmp_path/'a',config=cfg)
    b=run_native_geometry_dynamics(src,tmp_path/'b',config=cfg,restart_state=a['restart_state'])
    assert Path(b['restart_state']).exists()
    import json
    state=json.loads(Path(b['restart_state']).read_text())
    assert state['step']==10
