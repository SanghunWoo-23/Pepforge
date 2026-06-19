from pathlib import Path
import subprocess
import sys

from peptiforg_core.runtime_validation import run_runtime_validation, RUNTIME_VALIDATION_VERSION


def test_runtime_validation_runs(tmp_path):
    paths = run_runtime_validation(tmp_path)
    assert RUNTIME_VALIDATION_VERSION == "2.0.0"
    assert Path(paths["runtime_validation_summary"]).exists()
    assert Path(paths["runtime_validation_report"]).exists()


def test_cli_validate_runtime_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "validate-runtime", "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "runtime_validation_summary" in proc.stdout
