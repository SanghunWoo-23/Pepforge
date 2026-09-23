from pathlib import Path
import subprocess
import sys

from peptiforg_core.public_api import PUBLIC_API_VERSION
from peptiforg_core.public_release_stability import export_public_stability_report


def test_public_api_version():
    assert PUBLIC_API_VERSION == "4.0.0"


def test_stability_report_exports(tmp_path):
    paths = export_public_stability_report(tmp_path)
    assert Path(paths["public_output_contract_json"]).exists()
    assert Path(paths["public_release_stability_report"]).exists()


def test_cli_version_runs():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "version"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "4.0.0" in proc.stdout
