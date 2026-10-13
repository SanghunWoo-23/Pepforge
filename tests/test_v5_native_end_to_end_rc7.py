from pathlib import Path
from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.native_end_to_end_v1 import NativeE2EConfig, run_native_end_to_end


def test_native_e2e_offline_path(tmp_path):
    receptor=export_native_backbone("AAAAAAAAAA",tmp_path/"receptor",chain="A")["pdb"]
    cfg=NativeE2EConfig(enable_rdkit_quality_layer=False,docking_poses=2,docking_anchors=3,docking_rotations=4,docking_candidates=20,mechanics_steps=4,mechanics_save_every=2)
    result=run_native_end_to_end("EEMQRR",receptor,tmp_path/"run",config=cfg)
    assert result["network_policy"]=="NO_NETWORK_CALLS_IN_NATIVE_E2E_MODULE"
    assert result["peptide_builder"]["status"]=="COMPLETED"
    assert result["native_docking"]["status"] in {"COMPLETED","NO_USABLE_POSES"}
    assert Path(tmp_path/"run"/"native_end_to_end_summary.json").exists()
    if result["selected_docking_pose"] is not None:
        assert result["native_mechanics"]["evidence_grade"]=="EXPERIMENTAL_NATIVE_MECHANICS_NOT_PRODUCTION_MD"
