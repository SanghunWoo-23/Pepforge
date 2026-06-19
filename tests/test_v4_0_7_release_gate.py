from pathlib import Path
import subprocess
import sys
import json

from peptiforg_core.release_gate import release_gate_check, RELEASE_GATE_VERSION


def test_release_gate_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = release_gate_check(root, tmp_path)
    assert RELEASE_GATE_VERSION == "4.0.7"
    assert Path(paths["release_gate_summary"]).exists()
    summary = json.loads(Path(paths["release_gate_summary"]).read_text(encoding="utf-8"))
    assert summary["failed"] == 0


def test_cli_release_gate_runs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "release-gate", "--root-dir", str(root), "--output-dir", str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "release_gate_summary" in proc.stdout
