from __future__ import annotations

from pathlib import Path
import numpy as np

from peptiforg_core.openmm_md_backend import residue_parameterization_gate
from peptiforg_core.trajectory_analysis_v5 import analyze_trajectory


def test_modified_residue_is_hard_blocked_for_openmm_standard_gate(tmp_path: Path):
    p=tmp_path/'mod.pdb'
    p.write_text('HETATM    1  C1  AEE P   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n')
    gate=residue_parameterization_gate(p)
    assert gate['status']=='PARAMETERIZATION_REQUIRED'
    assert 'AEE' in gate['unsupported_residue_names']


def test_real_mdtraj_analysis_outputs_metrics_and_clusters(tmp_path: Path):
    import mdtraj as md
    pdb=tmp_path/'complex.pdb'
    pdb.write_text(
        'ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n'
        'ATOM      2  CA  ALA A   2       3.800   0.000   0.000  1.00  0.00           C\n'
        'TER\n'
        'ATOM      3  CA  GLY B   1       0.000   0.000   4.000  1.00  0.00           C\n'
        'ATOM      4  CA  GLY B   2       3.800   0.000   4.000  1.00  0.00           C\nEND\n', encoding='utf-8')
    top=md.load(str(pdb))
    xyz=np.repeat(top.xyz,6,axis=0)
    for i in range(6): xyz[i,:,2]+=i*0.01
    traj=md.Trajectory(xyz,top.topology)
    dcd=tmp_path/'traj.dcd'; traj.save_dcd(str(dcd))
    result=analyze_trajectory(pdb,dcd,tmp_path/'analysis',clusters=2)
    assert result['status']=='COMPLETED' and result['frames']==6
    assert Path(result['files']['frame_metrics']).exists()
    assert Path(result['files']['hbond_persistence']).exists()
    assert Path(result['files']['secondary_structure']).exists()
    assert 'autocorrelation_diagnostics' in result
    assert result['autocorrelation_diagnostics']['rmsd']['sample_count'] == 6
    assert len(result['files']['medoids'])==2
