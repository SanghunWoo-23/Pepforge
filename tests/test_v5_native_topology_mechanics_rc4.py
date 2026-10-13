from pathlib import Path
import json
import numpy as np

from peptiforg_core.native_topology_v1 import build_native_topology, export_native_topology
from peptiforg_core.native_mechanics_v1 import NativeMechanicsConfig, evaluate_native_mechanics, run_native_mechanics


def _pdb(path: Path):
    lines=[
      "ATOM      1    N ALA P   1       0.000   0.000   0.000  1.00  0.00           N",
      "ATOM      2   CA ALA P   1       1.450   0.000   0.000  1.00  0.00           C",
      "ATOM      3    C ALA P   1       2.400   1.000   0.000  1.00  0.00           C",
      "ATOM      4    O ALA P   1       2.200   2.200   0.000  1.00  0.00           O",
      "ATOM      5    N GLY P   2       3.500   0.600   0.000  1.00  0.00           N",
      "ATOM      6   CA GLY P   2       4.600   1.400   0.000  1.00  0.00           C",
      "ATOM      7    C GLY P   2       5.700   0.700   0.000  1.00  0.00           C",
      "ATOM      8    O GLY P   2       6.700   1.300   0.000  1.00  0.00           O",
      "END",
    ]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def test_native_topology_builds_explicit_graph(tmp_path):
    src=tmp_path/'x.pdb'; _pdb(src)
    top=build_native_topology(src)
    assert top.summary()['atom_count']==8
    assert top.summary()['bond_count']>=7
    assert top.summary()['angle_count']>0
    assert top.summary()['dihedral_count']>0
    assert any(srcname=='peptide_backbone' for *_,srcname in top.bonds)
    out=export_native_topology(top,tmp_path/'topology.json')
    payload=json.loads(Path(out).read_text())
    assert payload['provenance']['charge_model']=='coarse formal-group proxy'
    assert 'validated arbitrary-chemistry' in payload['provenance']['claim_guard']


def test_native_mechanics_force_and_restart(tmp_path):
    src=tmp_path/'x.pdb'; _pdb(src)
    top=build_native_topology(src)
    cfg=NativeMechanicsConfig(steps=12,save_every=4,dt_reduced=0.001,damping=0.05)
    f,terms=evaluate_native_mechanics(top,top.coordinates_A.copy(),cfg)
    assert f.shape==(8,3)
    assert set(['bond','angle','steric_repulsion','electrostatic_proxy','total_reduced_score']).issubset(terms)
    a=run_native_mechanics(src,tmp_path/'a',config=cfg)
    assert a['status']=='COMPLETED'
    assert a['evidence_grade']=='EXPERIMENTAL_NATIVE_MECHANICS_NOT_MD'
    assert Path(a['topology_json']).exists() and Path(a['trace_csv']).exists()
    assert 'not production molecular dynamics' in a['claim_guard'].lower()
    b=run_native_mechanics(src,tmp_path/'b',config=NativeMechanicsConfig(steps=3,save_every=3),restart_state=a['restart_state'])
    st=json.loads(Path(b['restart_state']).read_text())
    assert st['step']==15


def test_modified_residue_is_not_silently_canonicalized(tmp_path):
    src=tmp_path/'m.pdb'
    src.write_text("HETATM    1   C1 MSE P   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n",encoding='utf-8')
    top=build_native_topology(src)
    assert 'MSE' in top.provenance['unsupported_residue_names']
