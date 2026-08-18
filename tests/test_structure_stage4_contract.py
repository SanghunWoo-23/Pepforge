from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_explicit_derivative_contract_blocks_generic_surrogates():
    path = ROOT / "pepforge_structure_tool" / "data" / "explicit_derivative_contracts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["generic_tokens"]) == {"TAMRA", "Cy5", "NBD", "DOTA", "Chol", "Mal", "Dde"}
    for token, record in payload["generic_tokens"].items():
        assert record["required_fields"]
        assert record["blocked_reason"]
        assert "smiles" not in record


def test_windows_structure_preflight_is_real_executable_contract():
    path = ROOT / "scripts" / "windows_structure_release_preflight.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")
    assert any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in ast.walk(tree))
    assert "Ac-EEMQRR-NH2" in text
    assert "top5_rank_contract" in text
    assert "rdkit_import" in text


def test_structure_builder_records_conditions_without_fake_energy_correction():
    text = (ROOT / "pepforge_structure_tool" / "pepforge_core.py").read_text(encoding="utf-8")
    assert '"used_in_coordinate_energy": False' in text
    assert "not an explicit-solvent constant-pH calculation" in text
    assert "pairwise_conformer_rmsd" in text


def test_shared_theme_is_used_by_primary_first_party_windows():
    expected = [
        ROOT / "main_launcher.py",
        ROOT / "suite_gui" / "hotspot_gui.py",
        ROOT / "suite_gui" / "docking_workbench_gui.py",
        ROOT / "suite_gui" / "pymol_structure_builder_gui.py",
        ROOT / "suite_gui" / "spps_tk_gui.py",
    ]
    for path in expected:
        assert "apply_pepforge_theme" in path.read_text(encoding="utf-8"), path
