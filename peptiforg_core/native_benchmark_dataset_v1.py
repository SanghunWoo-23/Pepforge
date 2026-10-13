from __future__ import annotations

"""Dataset-level orchestration for Pepforge native docking benchmarks.

This module turns an explicit user-supplied benchmark manifest into reproducible
per-target reference benchmarks. It never downloads structures, invents target
metadata, or treats reference structures as docking predictions.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import csv
import hashlib
import json

from .interface_quality import parse_pdb_atoms
from .native_docking_benchmark_v1 import DockingBenchmarkConfig, benchmark_model_set

NATIVE_BENCHMARK_DATASET_VERSION = "0.1.0"


@dataclass(frozen=True)
class BenchmarkDatasetPolicy:
    require_unique_reference_content: bool = True
    reject_reference_as_model: bool = True
    require_models: bool = True
    minimum_models_per_target: int = 1
    note: str = (
        "Pepforge benchmark-dataset integrity policy. It prevents obvious data leakage "
        "and malformed target manifests; it is not a scientific accuracy criterion."
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _resolve(base: Path, value: Any) -> Path | None:
    text = _clean(value)
    if not text:
        return None
    p = Path(text).expanduser()
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def _split_models(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    # Pipe is the canonical delimiter because Windows paths may contain ':' and
    # comma-delimited CSV fields are cumbersome to author by hand.
    return [x.strip() for x in text.split("|") if x.strip()]


def _load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            rows = data.get("targets", data.get("rows"))
        else:
            rows = data
        if not isinstance(rows, list):
            raise ValueError("JSON benchmark manifest must be a list or contain a 'targets' list")
        return [dict(x) for x in rows if isinstance(x, dict)]
    raise ValueError("Benchmark manifest must be .csv or .json")


def _discover_models(row: dict[str, Any], base: Path) -> list[Path]:
    models: list[Path] = []
    for item in _split_models(row.get("models")):
        p = _resolve(base, item)
        if p is not None:
            models.append(p)
    models_dir = _resolve(base, row.get("models_dir"))
    if models_dir is not None and models_dir.exists() and models_dir.is_dir():
        pattern = _clean(row.get("models_glob")) or "*.pdb"
        models.extend(sorted(p.resolve() for p in models_dir.glob(pattern) if p.is_file()))
    # Stable de-duplication by resolved path.
    seen: set[str] = set()
    out: list[Path] = []
    for p in models:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _chains_in_pdb(path: Path) -> set[str]:
    try:
        df = parse_pdb_atoms(path)
        return {str(x) for x in df["chain"].dropna().astype(str).tolist()}
    except Exception:
        return set()


def audit_benchmark_manifest(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    policy: BenchmarkDatasetPolicy | None = None,
) -> dict[str, Any]:
    pol = policy or BenchmarkDatasetPolicy()
    manifest = Path(manifest_path).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = manifest.parent
    rows = _load_manifest_rows(manifest)

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    ids: set[str] = set()
    ref_hash_owner: dict[str, str] = {}

    for index, row in enumerate(rows, start=1):
        target_id = _clean(row.get("target_id"))
        if not target_id:
            errors.append({"row": index, "code": "MISSING_TARGET_ID", "message": "target_id is required"})
            continue
        if target_id in ids:
            errors.append({"row": index, "target_id": target_id, "code": "DUPLICATE_TARGET_ID", "message": "target_id must be unique"})
            continue
        ids.add(target_id)

        reference = _resolve(base, row.get("reference_pdb"))
        rec_chain = _clean(row.get("receptor_chain")) or "A"
        lig_chain = _clean(row.get("ligand_chain")) or "P"
        score_csv = _resolve(base, row.get("score_csv"))
        models = _discover_models(row, base)
        target_errors: list[str] = []
        target_warnings: list[str] = []

        if reference is None or not reference.is_file():
            target_errors.append("REFERENCE_PDB_MISSING")
            ref_hash = None
        else:
            ref_hash = _sha256(reference)
            chains = _chains_in_pdb(reference)
            if rec_chain not in chains:
                target_errors.append("REFERENCE_RECEPTOR_CHAIN_MISSING")
            if lig_chain not in chains:
                target_errors.append("REFERENCE_LIGAND_CHAIN_MISSING")
            previous = ref_hash_owner.get(ref_hash)
            if previous and previous != target_id:
                msg = f"Reference content duplicates target {previous}"
                if pol.require_unique_reference_content:
                    target_errors.append("DUPLICATE_REFERENCE_CONTENT")
                else:
                    target_warnings.append(msg)
            else:
                ref_hash_owner[ref_hash] = target_id

        existing_models = [p for p in models if p.is_file()]
        missing_models = [p for p in models if not p.is_file()]
        if missing_models:
            target_errors.append("MODEL_PDB_MISSING")
        if pol.require_models and len(existing_models) < int(pol.minimum_models_per_target):
            target_errors.append("INSUFFICIENT_MODELS")

        if reference is not None and reference.is_file() and pol.reject_reference_as_model:
            for model in existing_models:
                try:
                    if model == reference or _sha256(model) == ref_hash:
                        target_errors.append("REFERENCE_AS_MODEL_LEAKAGE")
                        break
                except OSError:
                    pass

        if score_csv is not None and not score_csv.is_file():
            target_errors.append("SCORE_CSV_MISSING")

        record = {
            "target_id": target_id,
            "reference_pdb": str(reference) if reference else "",
            "reference_sha256": ref_hash,
            "receptor_chain": rec_chain,
            "ligand_chain": lig_chain,
            "models": [str(p) for p in existing_models],
            "model_count": len(existing_models),
            "score_csv": str(score_csv) if score_csv else "",
            "split": _clean(row.get("split")) or "unspecified",
            "source": _clean(row.get("source")),
            "experimental_id": _clean(row.get("experimental_id")),
            "notes": _clean(row.get("notes")),
            "status": "PASS" if not target_errors else "FAIL",
            "errors": sorted(set(target_errors)),
            "warnings": target_warnings,
        }
        targets.append(record)
        for code in sorted(set(target_errors)):
            errors.append({"row": index, "target_id": target_id, "code": code})
        for message in target_warnings:
            warnings.append({"row": index, "target_id": target_id, "message": message})

    payload = {
        "version": NATIVE_BENCHMARK_DATASET_VERSION,
        "manifest": str(manifest),
        "status": "PASS" if not errors and targets else "FAIL",
        "policy": asdict(pol),
        "targets_total": len(targets),
        "targets_ready": sum(1 for t in targets if t["status"] == "PASS"),
        "errors": errors,
        "warnings": warnings,
        "targets": targets,
        "claim_guard": (
            "Manifest integrity PASS means only that benchmark inputs are structurally usable and obvious "
            "reference/model leakage checks passed. It does not establish docking accuracy or dataset independence."
        ),
    }
    (out / "native_benchmark_manifest_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out / "native_benchmark_manifest_targets.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields = ["target_id", "status", "reference_pdb", "receptor_chain", "ligand_chain", "model_count", "score_csv", "split", "source", "experimental_id", "errors"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for t in targets:
            writer.writerow({k: ("|".join(t[k]) if k == "errors" else t.get(k, "")) for k in fields})
    return payload


def run_benchmark_dataset(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    policy: BenchmarkDatasetPolicy | None = None,
    fail_on_target_error: bool = False,
) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    audit_dir = out / "_manifest_audit"
    audit = audit_benchmark_manifest(manifest_path, audit_dir, policy=policy)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for target in audit["targets"]:
        target_id = target["target_id"]
        if target["status"] != "PASS":
            failures.append({"target_id": target_id, "stage": "manifest_audit", "errors": target["errors"]})
            continue
        target_out = out / target_id
        cfg = DockingBenchmarkConfig(
            receptor_chain=target["receptor_chain"],
            ligand_chain=target["ligand_chain"],
        )
        try:
            summary = benchmark_model_set(
                target["reference_pdb"],
                target["models"],
                target_out,
                config=cfg,
                score_csv=(target["score_csv"] or None),
            )
            summary["dataset_target"] = {
                k: target[k]
                for k in ("target_id", "split", "source", "experimental_id", "reference_sha256")
            }
            summary_path = target_out / "native_docking_reference_benchmark.json"
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append({
                "target_id": target_id,
                "status": "PASS",
                "summary_json": str(summary_path.resolve()),
                "models_evaluated": summary.get("models_evaluated", 0),
                "best_dockq_compatible": summary.get("best_dockq_compatible"),
                "top1_by_internal_score_dockq": summary.get("top1_by_internal_score_dockq"),
                "best_top5_by_internal_score_dockq": summary.get("best_top5_by_internal_score_dockq"),
                "split": target["split"],
            })
        except Exception as exc:
            failures.append({"target_id": target_id, "stage": "benchmark", "error": str(exc)})
            if fail_on_target_error:
                raise

    payload = {
        "version": NATIVE_BENCHMARK_DATASET_VERSION,
        "status": "COMPLETED" if results and not failures else ("PARTIAL" if results else "FAILED"),
        "manifest_audit_status": audit["status"],
        "targets_total": audit["targets_total"],
        "targets_completed": len(results),
        "targets_failed_or_blocked": len(failures),
        "results": results,
        "failures": failures,
        "manifest_audit_json": str((audit_dir / "native_benchmark_manifest_audit.json").resolve()),
        "claim_guard": (
            "Dataset execution reports reference-structure recovery only. Results must not be presented as "
            "affinity prediction, experimental binding validation, or broad generalization without independent evidence."
        ),
    }
    (out / "native_benchmark_dataset_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out / "native_benchmark_dataset_summary.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields = ["target_id", "status", "models_evaluated", "best_dockq_compatible", "top1_by_internal_score_dockq", "best_top5_by_internal_score_dockq", "split", "summary_json"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    return payload


def write_benchmark_manifest_template(path: str | Path) -> str:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "target_id", "reference_pdb", "receptor_chain", "ligand_chain", "models_dir",
        "models_glob", "models", "score_csv", "split", "source", "experimental_id", "notes",
    ]
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "target_id": "example_target",
            "reference_pdb": "references/example_complex.pdb",
            "receptor_chain": "A",
            "ligand_chain": "P",
            "models_dir": "predictions/example_target",
            "models_glob": "*.pdb",
            "models": "",
            "score_csv": "predictions/example_target/native_docking_poses.csv",
            "split": "test",
            "source": "public experimental structure source; fill explicitly",
            "experimental_id": "fill_explicitly",
            "notes": "Replace this example row before scientific use",
        })
    return str(p)


__all__ = [
    "NATIVE_BENCHMARK_DATASET_VERSION",
    "BenchmarkDatasetPolicy",
    "audit_benchmark_manifest",
    "run_benchmark_dataset",
    "write_benchmark_manifest_template",
]
