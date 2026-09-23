from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import zipfile

from peptiforg_core.output_bundle import (
    bundle_folder_name,
    build_bundle_zip,
    create_result_bundle,
    sanitize_component,
    write_bundle_manifest,
)
from peptiforg_core.version import PEPFORGE_VERSION


def test_v4_suite_version_is_canonical():
    assert PEPFORGE_VERSION == "4.0.0"


def test_result_folder_name_uses_date_and_name_or_sequence():
    dt = datetime(2026, 8, 27, 11, 0, 0)
    assert bundle_folder_name(name="Project Alpha", date=dt) == "2026-08-27_Project_Alpha"
    assert bundle_folder_name(sequence="Ac-EEMQRR-NH2", date=dt) == "2026-08-27_Ac-EEMQRR-NH2"


def test_windows_invalid_and_reserved_names_are_safe():
    value = sanitize_component('CON:bad/name*?<>|')
    assert ':' not in value and '/' not in value and '*' not in value and '?' not in value
    assert sanitize_component('CON') != 'CON'


def test_result_bundle_contains_manifest_and_zip_inside_folder(tmp_path):
    bundle = create_result_bundle(tmp_path, sequence="Ac-EEMQRR-NH2", tool="PSB")
    csv_path = bundle / "result.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    zip_path = Path(build_bundle_zip(bundle, filename="PSB_Result_Package.zip"))
    write_bundle_manifest(bundle, tool="PSB", sequence="Ac-EEMQRR-NH2", artifacts={"csv": csv_path, "zip": zip_path})
    assert zip_path.parent == bundle
    assert (bundle / "RESULT_BUNDLE.json").exists()
    payload = json.loads((bundle / "RESULT_BUNDLE.json").read_text(encoding="utf-8"))
    assert payload["pepforge_version"] == "4.0.0"
    assert payload["sequence"] == "Ac-EEMQRR-NH2"
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "result.csv" in names
    assert "PSB_Result_Package.zip" not in names


def test_same_day_same_label_does_not_overwrite(tmp_path):
    a = create_result_bundle(tmp_path, name="Run", tool="PDE")
    b = create_result_bundle(tmp_path, name="Run", tool="PDE")
    assert a != b
    assert b.name.endswith("_01")


def test_pde_rebuild_zip_stays_inside_result_bundle(tmp_path):
    import importlib.util

    engine_path = Path(__file__).resolve().parents[1] / "apps" / "peptide_design_engine" / "Python" / "peptide_engine.py"
    spec = importlib.util.spec_from_file_location("pepforge_v4_pde_engine_bundle_test", engine_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    bundle = create_result_bundle(tmp_path, name="PDE_Balanced", tool="PDE")
    (bundle / "candidate.csv").write_text("rank,sequence\n1,ACDE\n", encoding="utf-8")
    zip_path = Path(module.rebuild_output_zip(bundle))
    assert zip_path == bundle / "PDE_Result_Package.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "candidate.csv" in names
    assert "PDE_Result_Package.zip" not in names
