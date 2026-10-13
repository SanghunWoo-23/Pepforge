from __future__ import annotations

from pathlib import Path

from peptiforg_core.docking_access_contract_v1 import (
    canonical_input_matrix_label,
    feature_access_rows,
    input_matrix_contract,
)


def test_all_four_input_matrix_labels_and_ready_contracts(tmp_path: Path):
    target = tmp_path / "target.pdb"
    pep = tmp_path / "pep.pdb"
    target.write_text("END\n", encoding="utf-8")
    pep.write_text("END\n", encoding="utf-8")
    cases = [
        ("PDB", "PDB", str(target), "", str(pep), ""),
        ("PDB", "Sequence", str(target), "", "", "EEMQRR"),
        ("Sequence", "PDB", "", "MKKLL", str(pep), ""),
        ("Sequence", "Sequence", "", "MKKLL", "", "EEMQRR"),
    ]
    labels = []
    for tm, pm, tp, ts, pp, ps in cases:
        payload = input_matrix_contract(
            target_mode=tm, peptide_mode=pm,
            target_path=tp, target_sequence=ts,
            peptide_path=pp, peptide_sequence=ps,
        )
        labels.append(payload["matrix"])
        assert payload["status"] == "READY"
        assert payload["target"]["readiness"].startswith("READY")
        assert payload["peptide"]["readiness"].startswith("READY")
    assert labels == [
        "PDB / PDB", "PDB / Sequence", "Sequence / PDB", "Sequence / Sequence"
    ]
    assert canonical_input_matrix_label("sequence", "pdb") == "Sequence / PDB"


def test_sequence_runtime_provenance_never_claims_experimental_structure():
    payload = input_matrix_contract(
        target_mode="Sequence", peptide_mode="Sequence",
        target_sequence="MKKLL", peptide_sequence="EEMQRR",
        target_runtime={
            "source":"Pepforge native fallback",
            "evidence_grade":"EXPERIMENTAL_SEQUENCE_DERIVED_GEOMETRY",
            "claim_guard":"not experimental",
        },
        peptide_runtime={
            "source":"Pepforge peptide structure builder",
            "evidence_grade":"SEQUENCE_DERIVED_PEPTIDE_STRUCTURE",
            "claim_guard":"candidate only",
        },
    )
    assert payload["target"]["evidence_grade"] == "EXPERIMENTAL_SEQUENCE_DERIVED_GEOMETRY"
    assert payload["peptide"]["evidence_grade"] == "SEQUENCE_DERIVED_PEPTIDE_STRUCTURE"
    assert "experimental" in payload["target"]["claim_guard"].lower()


def test_feature_inventory_is_always_visible_and_marks_optional_resources():
    rows = feature_access_rows()
    names = {r["feature"] for r in rows}
    for expected in (
        "PDB / PDB docking", "PDB / Sequence docking", "Sequence / PDB docking",
        "Sequence / Sequence docking", "Pepforge Native Docking",
        "Native mechanics / trajectory", "RDKit quality enhancement",
        "Local ESMFold enhancement", "RCSB online search",
    ):
        assert expected in names
    assert all(r["status"] for r in rows)
    assert all(r["note"] for r in rows)


def test_docking_gui_contains_access_provenance_progress_and_failure_surfaces():
    root = Path(__file__).resolve().parents[1]
    source = (root / "suite_gui" / "docking_workbench_gui.py").read_text(encoding="utf-8")
    assert 'self._make_tab("Feature access / status")' in source
    assert "Current input matrix / provenance" in source
    assert "All feature visibility / readiness" in source
    assert "Run progress history" in source
    assert "Last failure / recovery guidance" in source
    assert '"input_matrix_provenance":self._input_provenance_df()' in source
    assert '"feature_access_status":self._feature_access_df()' in source
    assert '"run_progress_history":self._progress_history_df()' in source
