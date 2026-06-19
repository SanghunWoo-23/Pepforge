from pathlib import Path
import json

from peptiforg_core.low_spec_validation_bridge import export_low_spec_validation_bridge


def test_v2_1_low_spec_validation_bridge_exports(tmp_path: Path):
    paths = export_low_spec_validation_bridge("FITC-Cha-AEEA-dK-NH2", tmp_path, "fitc_cha_aeea_dk", num_confs=3)
    required = [
        "sdf_multi_conformer",
        "pdb",
        "json_metadata",
        "conformer_metrics_csv",
        "parameter_requirements_csv",
        "evidence_report_json",
        "evidence_report_txt",
        "manifest",
        "template_vina_config_template",
        "template_openmm_validation_template",
    ]
    for key in required:
        assert key in paths
        assert Path(paths[key]).exists()
    evidence = json.loads(Path(paths["evidence_report_json"]).read_text(encoding="utf-8"))
    assert evidence["bridge_version"] == "2.1.0"
    assert evidence["evidence_grade"] in {"A", "B", "C", "D"}
    assert "not final Kd" in evidence["predicted_binding_claim_allowed"]


def test_v2_1_parameter_requirements_include_modified_tokens(tmp_path: Path):
    paths = export_low_spec_validation_bridge("Ac-K(Ahx-Biotin)-LVFF-NH2", tmp_path, "k_biotin", num_confs=2)
    txt = Path(paths["parameter_requirements_csv"]).read_text(encoding="utf-8-sig")
    assert "side-chain modified residue" in txt or "sidechain_label_aa" in txt
    assert "parameter" in txt.lower()
