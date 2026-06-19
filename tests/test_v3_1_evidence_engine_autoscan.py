from pathlib import Path
import csv
import json

from peptiforg_core.evidence_engine import (
    autoscan_project_folder,
    export_evidence_engine_report_from_project,
    render_readable_evidence_report,
)


def test_autoscan_project_folder_detects_files(tmp_path):
    q = tmp_path / "target_quality_warnings.csv"
    q.write_text("level,issue,recommendation\nok,basic,proceed\n", encoding="utf-8")
    c = tmp_path / "docking_residue_contact_report.csv"
    c.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    scan = autoscan_project_folder(tmp_path)
    assert scan["selected"]["target_quality_csv"].endswith("target_quality_warnings.csv")
    assert scan["selected"]["docking_contacts_csv"].endswith("docking_residue_contact_report.csv")


def test_export_evidence_from_project(tmp_path):
    (tmp_path / "target_quality_warnings.csv").write_text("level,issue,recommendation\nok,basic,proceed\n", encoding="utf-8")
    (tmp_path / "docking_residue_contact_report.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    paths = export_evidence_engine_report_from_project(tmp_path)
    assert Path(paths["project_autoscan_trace"]).exists()
    assert Path(paths["evidence_report_readable_md"]).exists()


def test_readable_report_contains_claim_sections():
    text = render_readable_evidence_report(
        {"evidence_grade":"B","claim_level":"computational_screening_package","total_points":5,"max_points":10,
         "allowed_claims":["screening-level candidate"],"blocked_claims":["final Kd"],"next_steps":["validate"]},
        [{"component":"x","present":True,"quality":"high","points":1,"weight":1,"note":"ok"}],
        {"selected":{"target_quality_csv":"target_quality_warnings.csv"}}
    )
    assert "Allowed wording" in text
    assert "Blocked wording" in text
