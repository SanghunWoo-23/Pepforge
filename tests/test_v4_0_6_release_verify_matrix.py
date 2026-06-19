from pathlib import Path
import subprocess
import sys
import json

from peptiforg_core.release_verify_matrix import verify_release_matrix, RELEASE_VERIFY_VERSION


def test_verify_matrix_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = verify_release_matrix(root, tmp_path)
    assert RELEASE_VERIFY_VERSION == "4.0.6"
    assert Path(paths["release_verify_matrix_summary"]).exists()
    summary = json.loads(Path(paths["release_verify_matrix_summary"]).read_text(encoding="utf-8"))
    assert summary["failed"] == 0


def test_cli_verify_matrix_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "verify-matrix", "--root-dir", str(root), "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "release_verify_matrix_summary" in proc.stdout
