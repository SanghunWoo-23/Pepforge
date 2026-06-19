from pathlib import Path
import csv

from peptiforg_core.workflow_automation_runner import (
    default_workflow_config,
    save_workflow_config,
    load_workflow_config,
    run_workflow,
    create_default_workflow_package,
)


def test_default_config_save_load(tmp_path):
    cfg = default_workflow_config("Demo")
    path = save_workflow_config(cfg, tmp_path)
    loaded = load_workflow_config(path)
    assert loaded["project_name"] == "Demo"


def test_run_workflow_basic(tmp_path):
    cfg = default_workflow_config("Demo")
    paths = run_workflow(cfg, tmp_path)
    assert Path(paths["workflow_stage_results"]).exists()
    assert Path(paths["workflow_run_manifest"]).exists()
    assert Path(paths["workflow_run_report"]).exists()


def test_run_workflow_with_experimental_csv(tmp_path):
    p = tmp_path / "assay.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","target","assay_type","value_type","value","unit"])
        w.writeheader()
        w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","target":"T","assay_type":"SPR","value_type":"Kd","value":"85","unit":"nM"})
    cfg = default_workflow_config("Demo")
    cfg["inputs"]["experimental_csv"] = str(p)
    paths = run_workflow(cfg, tmp_path)
    assert Path(paths["workflow_stage_results"]).exists()
    text = Path(paths["workflow_stage_results"]).read_text(encoding="utf-8")
    assert "experimental_import" in text
