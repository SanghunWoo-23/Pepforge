from suite_gui.runtime_selftest import run


def test_packaged_runtime_selftest_contract_is_current_and_passing():
    report = run()
    assert report["app_version"] == "V8.0.0"
    assert report["build_revision"] == "2026-10-14-v8-final-source"
    assert report["checks"]["terminal_ac_plan"] is True
    assert report["checks"]["terminal_pal_plan"] is True
    assert report["ok"] is True
