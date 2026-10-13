from __future__ import annotations

import json
from pathlib import Path

from peptiforg_core.native_result_interpretation_v1 import interpret_native_result, export_native_result_interpretation
from peptiforg_core.native_validation_workspace_v1 import inspect_validation_workspace


def test_interpretation_keeps_claim_guard_and_quality():
    result = {
        "claim_guard": "score is not affinity",
        "poses": [{"pose_id":"pose_1","pose_rank":1,"engine_score":-4.2,"quality_status":"WARN","contact_count":4,"clash_count":1}],
        "evidence": [
            {"pose_id":"pose_1","interaction":"hydrogen_bond"},
            {"pose_id":"pose_1","interaction":"hydrophobic"},
        ],
    }
    data = interpret_native_result(result, [], selected_pose_id="pose_1")
    assert data["quality_status"] == "WARN"
    assert data["claim_guard"] == "score is not affinity"
    assert any("WARN" in x for x in data["warnings"])
    assert any("affinity" in x.lower() for x in data["not_supported"])


def test_interpretation_export(tmp_path: Path):
    result = {"poses":[{"pose_id":"p1","pose_rank":1,"quality_status":"PASS","contact_count":3,"clash_count":0}], "evidence":[]}
    paths = export_native_result_interpretation(result, [], tmp_path)
    assert Path(paths["json"]).is_file()
    assert Path(paths["markdown"]).is_file()
    assert "production MD" in Path(paths["markdown"]).read_text(encoding="utf-8")


def test_workspace_detects_pending_finalize_and_hashes(tmp_path: Path):
    target = tmp_path / "targetA"
    target.mkdir()
    csvp = target / "bench.csv"
    csvp.write_text("pose_id,dockq\np1,0.4\n", encoding="utf-8")
    summary = target / "native_docking_reference_benchmark.json"
    summary.write_text(json.dumps({"target_id":"A","split":"test","benchmark_csv":str(csvp)}), encoding="utf-8")
    out = tmp_path / "workspace_report"
    data = inspect_validation_workspace(tmp_path, out)
    assert data["status"] == "BENCHMARKS_PRESENT_FINALIZATION_PENDING"
    assert data["counts"]["benchmark_targets"] == 1
    assert data["split_counts"]["TEST"] == 1
    assert data["artifacts"][0]["sha256"]
    assert (out / "native_validation_workspace.json").is_file()


def test_workspace_no_data_is_explicit(tmp_path: Path):
    data = inspect_validation_workspace(tmp_path)
    assert data["status"] == "READY_FOR_EXTERNAL_BENCHMARK_INPUT"
    assert any("independently sourced" in x for x in data["recommended_actions"])
