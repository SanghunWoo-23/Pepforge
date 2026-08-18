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


def test_docking_uses_explicit_geometry_rank_not_quality_grade():
    import pandas as pd
    from suite_gui import docking_workbench_gui as dw

    target = pd.DataFrame([
        {"chain":"A", "resi":"1", "resn":"ALA", "aa":"A", "atom":"CA", "element":"C", "x":0.0, "y":0.0, "z":0.0},
        {"chain":"A", "resi":"2", "resn":"LYS", "aa":"K", "atom":"CA", "element":"C", "x":4.0, "y":0.0, "z":0.0},
    ])
    peptide = pd.DataFrame([
        {"pep_pos":1, "aa":"K", "token":"K", "token_class":"std_aa", "x":0.0, "y":0.0, "z":0.0},
        {"pep_pos":2, "aa":"L", "token":"L", "token_class":"std_aa", "x":3.8, "y":0.0, "z":0.0},
    ])
    poses, _contacts, _best = dw.run_pose_search(target, peptide, pose_limit=4)
    assert not poses.empty
    assert list(poses["pose_rank"]) == sorted(poses["pose_rank"].tolist())
    assert "score_lower_better" not in poses.columns
    assert not hasattr(dw, "pose_quality_annotation")
