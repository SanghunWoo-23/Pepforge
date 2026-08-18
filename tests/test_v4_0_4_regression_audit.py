from pathlib import Path
import subprocess
import sys
import json

from peptiforg_core.regression_audit import run_regression_audit, REGRESSION_AUDIT_VERSION


def test_regression_audit_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = run_regression_audit(root, tmp_path)
    assert REGRESSION_AUDIT_VERSION == "2.0.0"
    assert Path(paths["regression_audit_summary"]).exists()
    summary = json.loads(Path(paths["regression_audit_summary"]).read_text(encoding="utf-8"))
    assert summary["failed"] == 0


def test_cli_regression_audit_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "regression-audit", "--root-dir", str(root), "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "regression_audit_summary" in proc.stdout
