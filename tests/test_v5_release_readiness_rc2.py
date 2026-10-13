from pathlib import Path

from peptiforg_core.v5_release_readiness import assess_v5_release_readiness


def test_release_readiness_does_not_fake_missing_native_backends(tmp_path):
    root = Path(__file__).resolve().parents[1]
    payload = assess_v5_release_readiness(root, tmp_path, run_release_gate=False)
    assert payload["software_gate"]["status"] == "NOT_RUN"
    assert payload["native_backends"]["haddock3"] in {"READY", "BACKEND_UNAVAILABLE"}
    assert payload["native_backends"]["openmm"] in {"READY", "BACKEND_UNAVAILABLE"}
    codes = {x["code"] for x in payload["blockers"]}
    assert "WINDOWS_WSL_FRESH_UNZIP_NATIVE_SMOKE" in codes
    assert "report_json" in payload and Path(payload["report_json"]).exists()
