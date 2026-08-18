from pathlib import Path

from peptiforg_core.source_integrity_audit import audit_source_tree
from spps_v4_gui.release import SPPSGui
from spps_v4_gui.release_contract import active_route_report


ROOT = Path(__file__).resolve().parents[1]


def test_release_has_no_runtime_patch_or_placeholder_findings():
    result = audit_source_tree(ROOT)
    assert result["status"] == "passed", result["findings"]
    assert result["finding_count"] == 0


def test_every_spps_release_route_comes_from_one_concrete_class():
    report = active_route_report(SPPSGui)
    assert report
    assert {row["module"] for row in report.values()} == {"spps_v4_gui.controller"}
    assert all(row["callable"] for row in report.values())


def test_removed_patch_stack_is_not_shipped():
    for relative in (
        "spps_v4_gui/legacy_controller.py",
        "spps_v4_gui/release_composition.py",
        "spps_v4_gui/classic_2094_tk_gui.py",
    ):
        assert not (ROOT / relative).exists()
