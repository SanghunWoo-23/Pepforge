from __future__ import annotations

import csv
from pathlib import Path

from peptiforg_core.native_benchmark_dataset_v1 import (
    audit_benchmark_manifest,
    run_benchmark_dataset,
    write_benchmark_manifest_template,
)
from peptiforg_core.native_peptide_builder_v1 import export_native_backbone


def _merge_complex(a_pdb: str, p_pdb: str, out: Path, ligand_shift=(0.0, 0.0, 0.0)) -> str:
    lines = []
    serial = 1
    for path, shift in [(a_pdb, (0, 0, 0)), (p_pdb, ligand_shift)]:
        for line in Path(path).read_text().splitlines():
            if not line.startswith(("ATOM", "HETATM")):
                continue
            x = float(line[30:38]) + shift[0]
            y = float(line[38:46]) + shift[1]
            z = float(line[46:54]) + shift[2]
            line = f"{line[:6]}{serial:5d}{line[11:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"
            lines.append(line)
            serial += 1
    out.write_text("\n".join(lines) + "\nEND\n")
    return str(out)


def _dataset_files(tmp_path: Path):
    r = export_native_backbone("AAAAAAAAAA", tmp_path / "r", chain="A")["pdb"]
    p = export_native_backbone("EEMQRR", tmp_path / "p", chain="P")["pdb"]
    ref = Path(_merge_complex(r, p, tmp_path / "ref.pdb", ligand_shift=(0.0, 4.0, 0.0)))
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    _merge_complex(r, p, model_dir / "pose_1.pdb", ligand_shift=(0.05, 4.0, 0.0))
    _merge_complex(r, p, model_dir / "pose_2.pdb", ligand_shift=(5.0, 4.0, 0.0))
    score = tmp_path / "scores.csv"
    score.write_text("pose_pdb,score\npose_1.pdb,-2\npose_2.pdb,-1\n")
    return ref, model_dir, score


def _write_manifest(path: Path, ref: Path, model_dir: Path, score: Path):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["target_id", "reference_pdb", "receptor_chain", "ligand_chain", "models_dir", "score_csv", "split"])
        w.writeheader()
        w.writerow({
            "target_id": "T1",
            "reference_pdb": ref.name,
            "receptor_chain": "A",
            "ligand_chain": "P",
            "models_dir": model_dir.name,
            "score_csv": score.name,
            "split": "test",
        })


def test_manifest_audit_and_dataset_run(tmp_path):
    ref, model_dir, score = _dataset_files(tmp_path)
    manifest = tmp_path / "benchmark.csv"
    _write_manifest(manifest, ref, model_dir, score)
    audit = audit_benchmark_manifest(manifest, tmp_path / "audit")
    assert audit["status"] == "PASS"
    assert audit["targets_ready"] == 1
    run = run_benchmark_dataset(manifest, tmp_path / "dataset")
    assert run["status"] == "COMPLETED"
    assert run["targets_completed"] == 1
    assert run["results"][0]["best_dockq_compatible"] > 0.99
    summary = Path(run["results"][0]["summary_json"]).read_text(encoding="utf-8")
    assert '"target_id": "T1"' in summary


def test_manifest_rejects_reference_as_model_leakage(tmp_path):
    ref, _model_dir, _score = _dataset_files(tmp_path)
    manifest = tmp_path / "leak.csv"
    with manifest.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["target_id", "reference_pdb", "models"])
        w.writeheader()
        w.writerow({"target_id": "LEAK", "reference_pdb": ref.name, "models": ref.name})
    audit = audit_benchmark_manifest(manifest, tmp_path / "audit")
    assert audit["status"] == "FAIL"
    assert "REFERENCE_AS_MODEL_LEAKAGE" in audit["targets"][0]["errors"]


def test_manifest_duplicate_target_id_is_blocked(tmp_path):
    ref, model_dir, _score = _dataset_files(tmp_path)
    manifest = tmp_path / "dup.csv"
    with manifest.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["target_id", "reference_pdb", "models_dir"])
        w.writeheader()
        w.writerow({"target_id": "T1", "reference_pdb": ref.name, "models_dir": model_dir.name})
        w.writerow({"target_id": "T1", "reference_pdb": ref.name, "models_dir": model_dir.name})
    audit = audit_benchmark_manifest(manifest, tmp_path / "audit")
    assert audit["status"] == "FAIL"
    assert any(x["code"] == "DUPLICATE_TARGET_ID" for x in audit["errors"])


def test_manifest_template_is_written(tmp_path):
    p = Path(write_benchmark_manifest_template(tmp_path / "template.csv"))
    text = p.read_text(encoding="utf-8-sig")
    assert "target_id" in text
    assert "reference_pdb" in text
    assert "models_dir" in text
