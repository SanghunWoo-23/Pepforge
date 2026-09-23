from __future__ import annotations

import csv
import json
from pathlib import Path

from peptiforg_core.hotspot_workflow_bridge import ranked_region_to_transfer, write_design_handoff
from peptiforg_core.project_io import new_project, load_project

ROOT = Path(__file__).resolve().parents[1]


def _ranked(rank: int, start: int, seq: str, priority: float) -> dict:
    return {
        "rank": rank,
        "region_start": start,
        "region_end": start + len(seq) - 1,
        "region_sequence": seq,
        "priority_score": priority,
        "record_name": "input",
        "center_position": start + len(seq) // 2,
        "center_residue": seq[len(seq) // 2],
        "why_hotspot": "local contact-like residue density",
    }


def test_project_can_be_created_under_user_selected_base(tmp_path: Path):
    chosen = tmp_path / "chosen-location"
    chosen.mkdir()
    project = new_project("Demo", "ACDEFG", base_dir=chosen)
    assert project.parent == chosen
    assert (project / "project.json").exists()
    assert load_project(project)["input_sequence"] == "ACDEFG"


def test_rank_selection_bridge_immediately_rewrites_pde_handoff(tmp_path: Path):
    project = new_project("Demo", "ACDEFGHIK", base_dir=tmp_path)
    rows = [_ranked(1, 4, "EFGHI", 0.82), _ranked(2, 2, "CDEFG", 0.71)]

    first = ranked_region_to_transfer(rows[0])
    paths = write_design_handoff(project, [first], ranked_rows=rows)
    assert Path(paths["selected_hotspots_csv"]).exists()
    assert Path(paths["profile_json"]).exists()
    assert load_project(project)["selected_hotspots"][0]["sequence"] == "EFGHI"

    second = ranked_region_to_transfer(rows[1])
    write_design_handoff(project, [second], ranked_rows=rows)
    payload = load_project(project)
    assert payload["selected_hotspots"][0]["rank"] == 2
    assert payload["selected_hotspots"][0]["sequence"] == "CDEFG"

    with (project / "design" / "selected_hotspots_for_design.csv").open(newline="", encoding="utf-8-sig") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 1
    assert csv_rows[0]["sequence"] == "CDEFG"

    profile = json.loads((project / "design" / "hotspot_chemistry_profile_for_PDE.json").read_text(encoding="utf-8"))
    assert profile["status"] == "available"
    assert profile["source_hotspots"][0]["sequence"] == "CDEFG"


def test_workflow_create_uses_folder_picker_and_custom_base_dir():
    source = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'title="Choose location for the new Pepforge project"' in source
    assert "base_dir=Path(base)" in source
    assert "if not base:" in source


def test_hotspot_selection_auto_syncs_to_workflow_project():
    source = (ROOT / "suite_gui" / "hotspot_gui.py").read_text(encoding="utf-8")
    assert "self._sync_selected_for_pde(silent=True)" in source
    assert "write_design_handoff(" in source
    assert 'text="Open selected in PDE"' not in source


def test_pde_can_live_refresh_selected_hotspot_from_project():
    source = (ROOT / "apps" / "peptide_design_engine" / "Python" / "desktop_gui.py").read_text(encoding="utf-8")
    assert "def _poll_workflow_hotspot_selection" in source
    assert 'payload.get("selected_hotspots")' in source
    assert "self.var_targets.set(sequence)" in source
    assert "self.after(700, self._poll_workflow_hotspot_selection)" in source
