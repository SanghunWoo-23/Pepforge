from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from peptiforg_core.psb_ai_ranker import RankerTrainingConfig, train_validate_ranker_from_csv
from peptiforg_core.structure_predictor_backends import (
    run_esmfold_prediction,
    run_alphafold3_prediction,
    write_alphafold3_protein_input,
)
from peptiforg_core.haddock3_backend import prepare_haddock3_job


def _write_minimal_pdb(path: Path, chain: str = "A") -> Path:
    path.write_text(
        "ATOM      1  N   ALA %s   1      11.104  13.207   9.000  1.00 20.00           N\n" % chain
        + "ATOM      2  CA  ALA %s   1      12.560  13.207   9.000  1.00 20.00           C\n" % chain
        + "ATOM      3  C   ALA %s   1      13.000  14.600   9.000  1.00 20.00           C\n" % chain
        + "ATOM      4  O   ALA %s   1      12.300  15.560   9.000  1.00 20.00           O\n" % chain
        + "END\n",
        encoding="utf-8",
    )
    return path


def test_ranker_grouped_cv_and_model_card(tmp_path: Path):
    source = tmp_path / "labels.csv"
    fieldnames = ["row_id", "sequence", "energy", "clashes", "label"]
    with source.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        # Six peptide groups x three conformers prevents conformer leakage under GroupKFold.
        for g in range(6):
            seq = "ACDEFG" + "A" * g
            for c in range(3):
                energy = float(g * 2 + c)
                clashes = float((g + c) % 3)
                writer.writerow({
                    "row_id": f"g{g}_c{c}", "sequence": seq,
                    "energy": energy, "clashes": clashes,
                    "label": 0.7 * energy + 0.3 * clashes,
                })
    result = train_validate_ranker_from_csv(
        source, tmp_path / "model", target_column="label",
        feature_columns=["energy", "clashes"], sequence_column="sequence",
        row_id_column="row_id", use_esm=False,
        config=RankerTrainingConfig(n_estimators=24, min_training_rows=12, cv_folds=3),
    )
    assert Path(result["model"]).is_file()
    assert Path(result["model_card"]).is_file()
    meta = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))
    assert meta["cross_validation"]["mode"] == "GroupKFold"
    assert meta["cross_validation"]["folds"] == 3
    assert meta["dataset_provenance"]["source_sha256"]
    rows = list(csv.DictReader(Path(result["cv_predictions"]).open(encoding="utf-8-sig")))
    assert len(rows) == 18
    # Every sequence group must appear in exactly one held-out fold.
    folds_by_group = {}
    for row in rows:
        folds_by_group.setdefault(row["group"], set()).add(row["fold"])
    assert all(len(v) == 1 for v in folds_by_group.values())


def test_esmfold_unavailable_is_explicit_and_no_fake_pdb(tmp_path: Path):
    result = run_esmfold_prediction("ACDEFGHIK", tmp_path / "esm", local_files_only=True)
    if result["status"] == "BACKEND_UNAVAILABLE":
        assert result["pdb"] is None
        assert not (tmp_path / "esm" / "esmfold_receptor.pdb").exists()
    else:
        # On a fully provisioned CI runner a real local ESMFold model may exist.
        assert result["status"] in {"COMPLETED", "FAILED"}


def test_af3_input_current_dialect_and_unavailable_is_explicit(tmp_path: Path):
    inp = Path(write_alphafold3_protein_input("ACDEFGHIK", tmp_path / "af3.json", model_seeds=(1, 2)))
    payload = json.loads(inp.read_text(encoding="utf-8"))
    assert payload["dialect"] == "alphafold3"
    assert payload["version"] == 4
    assert payload["modelSeeds"] == [1, 2]
    assert payload["sequences"][0]["protein"]["sequence"] == "ACDEFGHIK"

    result = run_alphafold3_prediction(
        "ACDEFGHIK", tmp_path / "run",
        run_script=tmp_path / "missing_run_alphafold.py",
        model_dir=tmp_path / "missing_models", db_dir=tmp_path / "missing_db",
    )
    assert result["status"] == "BACKEND_UNAVAILABLE"
    assert result["pdb"] is None
    assert Path(result["input_json"]).is_file()


def test_haddock_accepts_mmcif_receptor_by_real_conversion(tmp_path: Path):
    pytest.importorskip("Bio.PDB")
    from Bio.PDB import PDBParser, MMCIFIO

    receptor_pdb = _write_minimal_pdb(tmp_path / "receptor.pdb", "A")
    peptide_pdb = _write_minimal_pdb(tmp_path / "peptide.pdb", "P")
    structure = PDBParser(QUIET=True).get_structure("r", str(receptor_pdb))
    io = MMCIFIO(); io.set_structure(structure)
    cif = tmp_path / "receptor.cif"; io.save(str(cif))

    manifest = prepare_haddock3_job(cif, peptide_pdb, tmp_path / "job", pose_limit=5)
    prepared = manifest["prepared"]
    converted = Path(prepared["receptor_pdb"])
    assert converted.suffix.lower() == ".pdb"
    assert converted.is_file()
    assert "ATOM" in converted.read_text(encoding="utf-8", errors="ignore")
    assert Path(prepared["workflow_cfg"]).is_file()


def test_ranker_dataset_audit_and_baseline_are_explicit(tmp_path):
    from peptiforg_core.psb_ai_ranker import audit_supervised_dataset, train_validate_ranker
    import numpy as np, json
    X = np.asarray([[float(i), float(i % 3)] for i in range(20)], dtype=float)
    y = np.asarray([float(i) * 0.5 + 1.0 for i in range(20)], dtype=float)
    groups = [f"SEQ{i//2}" for i in range(20)]
    ids = [f"r{i}" for i in range(20)]
    audit = audit_supervised_dataset(X, y, groups=groups, row_ids=ids)
    assert audit["status"] == "READY_FOR_INTERNAL_CV"
    result = train_validate_ranker(X, y, ["f1", "f2"], tmp_path, target_name="label", groups=groups, row_ids=ids)
    meta = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))
    assert meta["promotion_status"] == "RESEARCH_ONLY_EXTERNAL_VALIDATION_REQUIRED"
    assert "naive_train_mean_baseline" in meta
    assert "baseline_comparison" in meta
