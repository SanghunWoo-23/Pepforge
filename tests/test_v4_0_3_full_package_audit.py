from pathlib import Path
import subprocess
import sys
import json

from peptiforg_core.full_package_audit import audit_package, FULL_PACKAGE_AUDIT_VERSION


def test_full_package_audit_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = audit_package(root, tmp_path)
    assert FULL_PACKAGE_AUDIT_VERSION == "4.0.3"
    assert Path(paths["full_package_audit_summary"]).exists()
    summary = json.loads(Path(paths["full_package_audit_summary"]).read_text(encoding="utf-8"))
    assert summary["failed"] == 0


def test_cli_audit_package_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "audit-package", "--root-dir", str(root), "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "full_package_audit_summary" in proc.stdout
