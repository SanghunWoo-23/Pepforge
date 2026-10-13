from pathlib import Path
import pandas as pd
import pytest

from peptiforg_core.docking_followup_v1 import select_followup_pose


def _normalized(tmp_path: Path):
    p1 = tmp_path / "pose1.pdb"
    p2 = tmp_path / "pose2.pdb"
    p1.write_text("END\n", encoding="utf-8")
    p2.write_text("END\n", encoding="utf-8")
    return {
        "poses": pd.DataFrame([
            {"pose_rank": 1, "pose_id": "native_pose_01", "quality_status": "PASS", "pose_pdb": str(p1)},
            {"pose_rank": 2, "pose_id": "native_pose_02", "quality_status": "WARN", "pose_pdb": str(p2)},
        ])
    }


def test_followup_can_select_explicit_pose(tmp_path):
    result = _normalized(tmp_path)
    selected = select_followup_pose(result, pose_id="native_pose_02")
    assert selected["pose_id"] == "native_pose_02"
    assert Path(selected["pose_pdb"]).exists()


def test_followup_rejects_missing_or_fail_pose(tmp_path):
    result = _normalized(tmp_path)
    with pytest.raises(ValueError):
        select_followup_pose(result, pose_id="does_not_exist")
    result["poses"].loc[result["poses"]["pose_id"] == "native_pose_02", "quality_status"] = "FAIL"
    with pytest.raises(ValueError):
        select_followup_pose(result, pose_id="native_pose_02")


def test_shared_viewer_has_selection_filter_and_rerun_hooks():
    root = Path(__file__).resolve().parents[1]
    panel = (root / "suite_gui" / "shared_native_result_panel.py").read_text(encoding="utf-8")
    wb = (root / "suite_gui" / "docking_workbench_gui.py").read_text(encoding="utf-8")
    psb = (root / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert '<<TreeviewSelect>>' in panel
    assert 'Run follow-up for selected' in panel
    assert 'def _render_detail_rows' in panel
    assert 'rerun_followup_callback=self.run_native_followup' in wb
    assert 'pose_id=pose_id' in wb
    assert 'rerun_followup_callback=self._rerun_selected_native_followup' in psb
    assert 'def _rerun_selected_native_followup' in psb
