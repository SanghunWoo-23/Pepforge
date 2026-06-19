from pathlib import Path
import csv

from peptiforg_core.run_comparison import (
    compare_file_inventories,
    compare_candidate_dashboards,
    export_run_comparison_package,
)


def test_compare_file_inventories(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir(); new.mkdir()
    (old / "a.txt").write_text("1")
    (new / "a.txt").write_text("2")
    (new / "b.txt").write_text("3")
    rows = compare_file_inventories(old, new)
    statuses = {r["relative_path"]: r["status"] for r in rows}
    assert statuses["a.txt"] == "modified"
    assert statuses["b.txt"] == "added"


def test_compare_candidate_dashboards(tmp_path):
    old = tmp_path / "old.csv"
    new = tmp_path / "new.csv"
    for path, score in [(old, "1.0"), (new, "2.0")]:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["candidate_id","dashboard_rank","dashboard_score","recommendation"])
            w.writeheader()
            w.writerow({"candidate_id":"PDE_0001","dashboard_rank":"1","dashboard_score":score,"recommendation":"keep"})
    rows = compare_candidate_dashboards(old, new)
    assert rows[0]["candidate_id"] == "PDE_0001"
    assert rows[0]["score_delta"] == 1.0


def test_export_run_comparison_package(tmp_path):
    oldp = tmp_path / "old"; newp = tmp_path / "new"
    oldp.mkdir(); newp.mkdir()
    (oldp / "x.txt").write_text("old")
    (newp / "x.txt").write_text("new")
    paths = export_run_comparison_package(oldp, newp, tmp_path)
    assert Path(paths["changed_files_inventory"]).exists()
    assert Path(paths["run_comparison_report"]).exists()
