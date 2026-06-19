from pathlib import Path
import importlib.util

from peptiforg_core.logic_audit_v301 import v301_logic_analysis, export_v301_logic_audit


def _load_peptide_engine():
    root = Path(__file__).resolve().parents[1]
    path = root / "apps" / "peptide_design_engine" / "Python" / "peptide_engine.py"
    spec = importlib.util.spec_from_file_location("peptide_engine_v301_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v301_logic_audit_exports(tmp_path):
    payload = v301_logic_analysis()
    assert payload["pepforge_version"] == "3.0.1"
    paths = export_v301_logic_audit(tmp_path)
    assert Path(paths["logic_audit_json"]).exists()


def test_design_developability_report_available():
    pe = _load_peptide_engine()
    seq = ["W","W","W","W","W","W","W","W"]
    report = pe.design_developability_report(seq)
    assert "developability_score" in report
    assert "long_hydrophobic_stretch" in report["developability_penalties"]


def test_docking_pose_quality_annotation():
    from suite_gui.docking_workbench_gui import pose_quality_annotation
    grade, note = pose_quality_annotation({
        "contact_count": 14,
        "clash_count": 1,
        "hydrophobic_contacts": 4,
        "hydrogen_bond_contacts": 2,
        "min_distance_A": 2.4,
    })
    assert grade.startswith("A_")
