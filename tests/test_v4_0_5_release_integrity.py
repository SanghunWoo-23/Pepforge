from pathlib import Path
import subprocess, sys, json
from peptiforg_core.release_integrity import audit_release_integrity, RELEASE_INTEGRITY_VERSION

def test_release_integrity_runs(tmp_path):
    root=Path(__file__).resolve().parents[1]
    paths=audit_release_integrity(root,tmp_path)
    assert RELEASE_INTEGRITY_VERSION == "2.0.0"
    assert Path(paths["release_integrity_summary"]).exists()
    summary=json.loads(Path(paths["release_integrity_summary"]).read_text(encoding="utf-8"))
    assert summary["failed"] == 0

def test_cli_release_integrity_runs(tmp_path):
    root=Path(__file__).resolve().parents[1]
    proc=subprocess.run([sys.executable,str(root/"pepforge_cli.py"),"release-integrity","--root-dir",str(root),"--output-dir",str(tmp_path)],capture_output=True,text=True)
    assert proc.returncode == 0
    assert "release_integrity_summary" in proc.stdout
