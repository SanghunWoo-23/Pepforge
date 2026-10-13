from __future__ import annotations

"""Pepforge V5 PSB -> Docking orchestration primitives.

This module intentionally separates *planned work* from *completed scientific
results*.  It consumes real PSB ranked conformer files, validates a receptor
structure, creates one docking job per PSB model, and records candidate/PSB
lineage without fabricating docking poses or scores.

V5 target workflow
------------------
PSB conformer ensemble -> Top-N peptide models -> docking jobs -> Top poses ->
interaction review -> optional MD/trajectory analysis.

Only the preparation/orchestration layer is implemented here.  A docking job is
reported as PREPARED_NOT_RUN until an actual backend executes and real pose
artifacts are verified.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
import csv
import hashlib
import json
import shutil

from peptiforg_core.candidate_manifest import stable_candidate_id
from peptiforg_core.docking_lineage import export_lineage, lineage_record, psb_structure_id

PSB_V5_ORCHESTRATOR_VERSION = "5.0.0-rc2"
SUPPORTED_RECEPTOR_SUFFIXES = {".pdb", ".cif", ".mmcif"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _copy_file(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


@dataclass(frozen=True)
class PSBModel:
    rank: int
    conformer_id: int | None
    family: str
    pdb_path: str
    pdb_sha256: str
    source: str = "PSB"
    psb_energy: float | None = None
    severe_steric_clashes: int | None = None
    requested_structure_match: bool | None = None
    selection_fallback: bool | None = None


@dataclass(frozen=True)
class DockingJob:
    job_id: str
    candidate_id: str
    psb_structure_id: str
    psb_rank: int
    peptide_pdb: str
    receptor_pdb: str
    docking_backend: str
    binding_site_mode: str
    binding_site_residues: tuple[str, ...]
    requested_pose_limit: int
    status: str = "PREPARED_NOT_RUN"


@dataclass(frozen=True)
class PSBV5RunPlan:
    version: str
    candidate_id: str
    sequence: str
    receptor_path: str
    receptor_sha256: str
    docking_backend: str
    binding_site_mode: str
    requested_model_limit: int
    requested_pose_limit_per_model: int
    models: tuple[PSBModel, ...]
    jobs: tuple[DockingJob, ...]
    claim_guard: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["models"] = [asdict(model) for model in self.models]
        payload["jobs"] = [
            {**asdict(job), "binding_site_residues": list(job.binding_site_residues)}
            for job in self.jobs
        ]
        return payload


def _rank_row_map(meta: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in ((meta.get("conformation_analysis") or {}).get("top_conformers") or []):
        try:
            rank = int(row.get("rank"))
        except Exception:
            continue
        out[rank] = dict(row)
    return out


def load_psb_models(psb_meta_path: str | Path, limit: int = 5) -> tuple[str, list[PSBModel]]:
    """Load real ranked PSB PDBs from an existing PSB metadata JSON.

    Missing ranked PDBs are not substituted.  The caller gets only verified
    existing artifacts and may decide whether a shortfall should block docking.
    """
    meta_path = Path(psb_meta_path).expanduser().resolve()
    if not meta_path.exists() or not meta_path.is_file():
        raise FileNotFoundError(f"PSB metadata JSON not found: {meta_path}")
    meta = _load_json(meta_path)
    sequence = str(meta.get("input") or "").strip()
    if not sequence:
        raise ValueError("PSB metadata does not contain the input peptide construct.")

    rank_rows = _rank_row_map(meta)
    paths = list(meta.get("top5_conformer_pdb_paths") or [])
    models: list[PSBModel] = []
    for index, raw in enumerate(paths[: max(1, int(limit))], 1):
        path = Path(raw)
        if not path.is_absolute():
            path = (meta_path.parent / path).resolve()
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            continue
        row = rank_rows.get(index, {})
        energy = row.get("energy")
        try:
            energy = None if energy in (None, "") else float(energy)
        except Exception:
            energy = None
        try:
            conf_id = int(row.get("conf_id")) if row.get("conf_id") not in (None, "") else None
        except Exception:
            conf_id = None
        models.append(PSBModel(
            rank=index,
            conformer_id=conf_id,
            family=str(row.get("family") or "unknown"),
            pdb_path=str(path),
            pdb_sha256=_sha256(path),
            psb_energy=energy,
            severe_steric_clashes=(int(row.get("severe_steric_clashes")) if row.get("severe_steric_clashes") not in (None, "") else None),
            requested_structure_match=(bool(row.get("requested_structure_match")) if "requested_structure_match" in row else None),
            selection_fallback=(bool(row.get("selection_fallback")) if "selection_fallback" in row else None),
        ))
    return sequence, models


def validate_receptor_structure(path: str | Path) -> Path:
    receptor = Path(path).expanduser().resolve()
    if not receptor.exists() or not receptor.is_file():
        raise FileNotFoundError(f"Receptor structure not found: {receptor}")
    if receptor.suffix.lower() not in SUPPORTED_RECEPTOR_SUFFIXES:
        raise ValueError(
            f"Unsupported receptor format {receptor.suffix!r}; expected PDB/mmCIF."
        )
    if receptor.stat().st_size <= 0:
        raise ValueError(f"Receptor structure is empty: {receptor}")
    return receptor


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    data = [dict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in data:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)


def prepare_psb_docking_plan(
    psb_meta_path: str | Path,
    receptor_path: str | Path,
    output_dir: str | Path,
    *,
    candidate_id: str | None = None,
    model_limit: int = 5,
    pose_limit_per_model: int = 5,
    docking_backend: str = "haddock3",
    binding_site_mode: str = "blind",
    binding_site_residues: Sequence[str] | None = None,
    require_exact_model_count: bool = False,
) -> dict[str, str]:
    """Prepare the V5 Top-model -> docking work queue from real PSB outputs.

    The function creates job manifests and lineage only.  It never emits fake
    pose files or scores.  The planned number of final complexes is therefore a
    request (model_count x pose_limit), not a completed result count.
    """
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    sequence, models = load_psb_models(psb_meta_path, limit=model_limit)
    if not models:
        raise ValueError("No usable ranked PSB PDB models were found.")
    if require_exact_model_count and len(models) != int(model_limit):
        raise ValueError(f"PSB produced {len(models)}/{int(model_limit)} usable ranked PDB models.")

    receptor = validate_receptor_structure(receptor_path)
    cid = str(candidate_id or stable_candidate_id(sequence)).strip()
    backend = str(docking_backend or "").strip() or "unselected"
    site_mode = str(binding_site_mode or "blind").strip().lower()
    if site_mode not in {"blind", "hotspot", "manual"}:
        raise ValueError("binding_site_mode must be blind, hotspot, or manual")
    residues = tuple(str(x).strip() for x in (binding_site_residues or []) if str(x).strip())
    if site_mode in {"hotspot", "manual"} and not residues:
        raise ValueError(f"{site_mode} docking requires at least one binding-site residue.")

    receptor_copy = _copy_file(receptor, out / "inputs" / receptor.name)
    model_dir = out / "inputs" / "psb_models"
    prepared_models: list[PSBModel] = []
    jobs: list[DockingJob] = []
    lineage_rows: list[dict[str, Any]] = []
    for model in models:
        model_copy = _copy_file(Path(model.pdb_path), model_dir / f"model_{model.rank:02d}.pdb")
        prepared = PSBModel(
            rank=model.rank,
            conformer_id=model.conformer_id,
            family=model.family,
            pdb_path=str(model_copy),
            pdb_sha256=_sha256(model_copy),
            source=model.source,
            psb_energy=model.psb_energy,
            severe_steric_clashes=model.severe_steric_clashes,
            requested_structure_match=model.requested_structure_match,
            selection_fallback=model.selection_fallback,
        )
        prepared_models.append(prepared)
        sid = psb_structure_id(cid, model.rank)
        job_id = f"{sid}/DOCK-RUN"
        job = DockingJob(
            job_id=job_id,
            candidate_id=cid,
            psb_structure_id=sid,
            psb_rank=model.rank,
            peptide_pdb=str(model_copy),
            receptor_pdb=str(receptor_copy),
            docking_backend=backend,
            binding_site_mode=site_mode,
            binding_site_residues=residues,
            requested_pose_limit=max(1, int(pose_limit_per_model)),
        )
        jobs.append(job)
        lineage_rows.append(lineage_record(
            cid,
            sequence,
            conformer_rank=model.rank,
            structure_path=model_copy,
            docking_engine=backend,
            docking_status="PREPARED_NOT_RUN",
            notes=(
                f"Prepared V5 docking job; requested pose limit={job.requested_pose_limit}; "
                f"binding_site_mode={site_mode}. No pose or score exists until a real backend succeeds."
            ),
        ))
        job_folder = out / "jobs" / f"model_{model.rank:02d}"
        job_folder.mkdir(parents=True, exist_ok=True)
        (job_folder / "job.json").write_text(
            json.dumps({**asdict(job), "binding_site_residues": list(residues)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    plan = PSBV5RunPlan(
        version=PSB_V5_ORCHESTRATOR_VERSION,
        candidate_id=cid,
        sequence=sequence,
        receptor_path=str(receptor_copy),
        receptor_sha256=_sha256(receptor_copy),
        docking_backend=backend,
        binding_site_mode=site_mode,
        requested_model_limit=max(1, int(model_limit)),
        requested_pose_limit_per_model=max(1, int(pose_limit_per_model)),
        models=tuple(prepared_models),
        jobs=tuple(jobs),
        claim_guard=(
            "Prepared docking jobs are not docking results. Engine scores, pose files, interaction evidence, "
            "affinity estimates, and final Top-5 poses may be recorded only after a real docking backend runs "
            "successfully and its artifacts are validated."
        ),
    )
    manifest = out / "psb_v5_run_plan.json"
    manifest.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    jobs_csv = out / "psb_v5_docking_jobs.csv"
    _write_csv(jobs_csv, [
        {**asdict(job), "binding_site_residues": ";".join(job.binding_site_residues)} for job in jobs
    ])
    models_csv = out / "psb_v5_models.csv"
    _write_csv(models_csv, [asdict(model) for model in prepared_models])
    lineage_paths = export_lineage(lineage_rows, out / "lineage", target_path=receptor_copy)

    readme = out / "README_PSB_V5_RUN_PLAN.txt"
    readme.write_text(
        "\n".join([
            "Pepforge V5 PSB / Docking run plan",
            "=================================",
            f"Candidate: {cid}",
            f"Sequence: {sequence}",
            f"Prepared peptide models: {len(prepared_models)}",
            f"Requested poses per model: {max(1, int(pose_limit_per_model))}",
            f"Requested maximum final complexes: {len(prepared_models) * max(1, int(pose_limit_per_model))}",
            f"Docking backend: {backend}",
            f"Binding-site mode: {site_mode}",
            "",
            "STATUS: PREPARED_NOT_RUN",
            "No docking pose, docking score, affinity, Kd, or native-state claim has been generated.",
            "The next step is a real backend adapter that executes the recorded jobs and validates pose artifacts.",
            "",
        ]),
        encoding="utf-8",
    )
    return {
        "run_plan_json": str(manifest),
        "models_csv": str(models_csv),
        "jobs_csv": str(jobs_csv),
        "readme": str(readme),
        **lineage_paths,
    }


__all__ = [
    "PSB_V5_ORCHESTRATOR_VERSION",
    "PSBModel",
    "DockingJob",
    "PSBV5RunPlan",
    "load_psb_models",
    "validate_receptor_structure",
    "prepare_psb_docking_plan",
]
