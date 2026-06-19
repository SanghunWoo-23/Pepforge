from pathlib import Path
import csv
import json

from peptiforg_core.external_docking_runner_bridge import export_external_docking_runner_bridge, DOCKING_BRIDGE_VERSION


def test_external_docking_runner_bridge_exports(tmp_path: Path):
    paths = export_external_docking_runner_bridge("FITC-Cha-AEEA-dK-NH2", tmp_path, "docktest")
    assert DOCKING_BRIDGE_VERSION == "2.2.0"
    assert Path(paths["vina_config_template"]).exists()
    assert Path(paths["run_vina_windows"]).exists()
    assert Path(paths["run_vina_linux_mac"]).exists()
    assert Path(paths["external_docking_scores_import_schema"]).exists()
    assert Path(paths["docking_claim_guard_table"]).exists()
    manifest = json.loads(Path(paths["external_docking_manifest"]).read_text(encoding="utf-8"))
    assert manifest["bridge_version"] == "2.2.0"
    assert "low_spec_bridge_outputs" in manifest
    assert "external_docking_bridge_outputs" in manifest


def test_claim_guard_blocks_overclaims(tmp_path: Path):
    paths = export_external_docking_runner_bridge("Pal-EEMQRR-NH2", tmp_path, "claimtest")
    rows = list(csv.DictReader(Path(paths["docking_claim_guard_table"]).open(encoding="utf-8-sig")))
    joined = "\n".join(r["claim"] + " " + r["status"] for r in rows)
    assert "true nM binder blocked" in joined
    assert "final Kd blocked" in joined
    assert "Pepforge replaces Vina/GROMACS/AMBER/OpenMM blocked" in joined
