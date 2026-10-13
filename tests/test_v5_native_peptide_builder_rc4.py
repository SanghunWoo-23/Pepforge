from pathlib import Path
import numpy as np
from peptiforg_core.native_peptide_builder_v1 import build_native_backbone, export_native_backbone
from peptiforg_core.native_topology_v1 import build_native_topology


def test_native_builder_generates_canonical_backbone_without_rdkit(tmp_path):
    r=build_native_backbone('AGK')
    assert r['status']=='COMPLETED'
    assert r['evidence_grade']=='EXPERIMENTAL_BACKBONE_ONLY'
    # 3 residues x backbone 4 + CB for A/K, no CB for G
    assert len(r['atoms'])==14
    out=export_native_backbone('AGK',tmp_path)
    assert Path(out['pdb']).exists()
    top=build_native_topology(out['pdb'])
    assert top.summary()['atom_count']==14
    assert sum(1 for *_,src in top.bonds if src=='peptide_backbone')==2


def test_native_builder_respects_user_torsion_arrays(tmp_path):
    r=build_native_backbone('AAA',phi_deg=[-80,-70,-60],psi_deg=[120,130,140],omega_deg=[180,175])
    assert r['phi_deg']==[-80.0,-70.0,-60.0]
    assert r['psi_deg']==[120.0,130.0,140.0]
    assert r['omega_deg']==[180.0,175.0]
    coords=np.array([[a['x'],a['y'],a['z']] for a in r['atoms']],float)
    assert np.isfinite(coords).all()


def test_native_builder_rejects_modified_notation_instead_of_canonicalizing():
    import pytest
    with pytest.raises(ValueError):
        build_native_backbone('Ac-AAA')
