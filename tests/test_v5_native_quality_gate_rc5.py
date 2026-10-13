from pathlib import Path
import json

from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.native_quality_gate_v1 import audit_peptide_geometry, assess_native_docking_pose
from peptiforg_core.native_mechanics_v1 import NativeMechanicsConfig, run_native_mechanics


def test_native_builder_exports_quality_gate(tmp_path):
    r=export_native_backbone('AGK',tmp_path/'build')
    q=r['quality_gate']
    assert q['status'] in {'PASS','WARN'}
    assert q['fail_count']==0
    assert q['optional_rdkit_validation']['status'] in {'PASS','WARN_SANITIZE','WARN_PARSE_FAILED','WARN_VALIDATOR_ERROR','SKIPPED_NOT_INSTALLED'}


def test_quality_gate_rejects_duplicate_coordinates(tmp_path):
    p=tmp_path/'bad.pdb'
    p.write_text(
        'ATOM      1    N ALA P   1       0.000   0.000   0.000  1.00  0.00           N\n'
        'ATOM      2   CA ALA P   1       0.000   0.000   0.000  1.00  0.00           C\n'
        'ATOM      3    C ALA P   1       2.500   0.000   0.000  1.00  0.00           C\n'
        'ATOM      4    O ALA P   1       3.700   0.000   0.000  1.00  0.00           O\nEND\n',encoding='utf-8')
    q=audit_peptide_geometry(p,optional_rdkit=False)
    assert q['status']=='FAIL'
    assert q['near_duplicate_heavy_atom_pairs']>=1


def test_docking_quality_gate_distinguishes_good_and_bad():
    good=assess_native_docking_pose(clash_count=0,min_distance_A=2.7,contact_count=12)
    bad=assess_native_docking_pose(clash_count=20,min_distance_A=1.2,contact_count=3)
    assert good['status']=='PASS'
    assert bad['status']=='FAIL'


def test_native_mechanics_exports_quality_gate(tmp_path):
    b=export_native_backbone('AGK',tmp_path/'seed')
    r=run_native_mechanics(b['pdb'],tmp_path/'mech',config=NativeMechanicsConfig(steps=3,save_every=3,velocity_noise=0.0))
    assert 'quality_gate' in r
    assert 'final_geometry_quality' in r
    assert r['quality_gate']['status'] in {'PASS','WARN','FAIL'}

from peptiforg_core.quality_preserving_peptide_builder_v1 import build_quality_preserving_peptide

def test_quality_preserving_builder_always_has_native_and_optional_layer(tmp_path):
    r=build_quality_preserving_peptide('AGK',tmp_path/'hybrid')
    assert r['status']=='COMPLETED'
    assert Path(r['native']['pdb']).exists()
    assert r['preferred_structure']['source'] in {'native','rdkit_optional_quality_layer'}
    if r['optional_rdkit']['status']=='COMPLETED':
        assert Path(r['optional_rdkit']['pdb']).exists()
        assert r['optional_rdkit']['quality_gate']['status'] in {'PASS','WARN','FAIL'}
