from __future__ import annotations


def test_active_release_routes_are_semantic_and_not_legacy_patch_functions():
    from suite_gui.release import SPPSGui
    from suite_gui.release_contract import active_route_report

    report = active_route_report(SPPSGui)
    assert report
    assert all(details["callable"] for details in report.values())
    assert all(
        details["module"] in details["allowed_modules"]
        for details in report.values()
    )
    assert all(
        details["module"] != "suite_gui.legacy_controller"
        for details in report.values()
    )


def test_public_release_uses_direct_controller_not_runtime_composition():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "suite_gui" / "release.py"
    ).read_text(encoding="utf-8")
    assert "from suite_gui.controller import SPPSGui, main" in source
    assert "release_composition" not in source


def test_active_audit_separates_runtime_routes_from_historical_bindings():
    from tools.audit_monkey_patches import audit_active_release

    report = audit_active_release()
    assert report["route_count"] >= 10
    assert report["legacy_controller_routes"] == []
