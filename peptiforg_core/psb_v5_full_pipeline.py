from __future__ import annotations

"""End-to-end Pepforge V5 PSB -> docking -> DockBench -> PyMOL -> optional MD.

The pipeline is strict about scientific state. Missing external backends are
reported as unavailable; no pose, MD trajectory, affinity, or convergence result
is synthesized as a fallback.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable
import json
import shutil

from peptiforg_core.psb_v5_orchestrator import prepare_psb_docking_plan
from peptiforg_core.haddock3_backend import detect_haddock3, prepare_haddock3_job, run_haddock3_job
from peptiforg_core.openmm_md_backend import OpenMMProtocol, detect_openmm, run_openmm_replicates
from peptiforg_core.trajectory_analysis_v5 import backend_readiness as trajectory_backend_readiness, analyze_trajectory, summarize_replicates
from peptiforg_core.pymol_v5_export import export_pymol_docking_ensemble
from peptiforg_core.docking_interaction_export import analyze_pose_collection
from peptiforg_core.docking_lineage import export_lineage, lineage_record
from peptiforg_core.structure_predictor_backends import predictor_status
from peptiforg_core.esm_peptide_embedding import backend_readiness as esm_embedding_readiness
from peptiforg_core.local_resource_manager import resource_status, normalize_execution_mode
from peptiforg_core.native_docking_v1 import NativeDockingConfig, run_native_docking, NATIVE_DOCKING_VERSION
from peptiforg_core.docking_result_contract_v1 import normalize_native_docking_result, export_normalized_result, DOCKING_RESULT_CONTRACT_VERSION
from peptiforg_core.docking_followup_v1 import run_native_docking_followup
from peptiforg_core.native_mechanics_v2 import NativeMechanicsV2Config

PSB_V5_FULL_PIPELINE_VERSION = "5.0.0-rc13"


def backend_status(execution_mode: str = "offline", resource_root: str | Path | None = None) -> dict[str, Any]:
    mode = normalize_execution_mode(execution_mode)
    return {
        "execution": resource_status(resource_root, execution_mode=mode),
        "pipeline_version": PSB_V5_FULL_PIPELINE_VERSION,
        "native_docking": {"status": "READY", "engine": "Pepforge Native Docking v1", "version": NATIVE_DOCKING_VERSION, "requires_network": False, "external_scientific_engine": False},
        "haddock3": detect_haddock3(),
        "openmm": detect_openmm(),
        "trajectory_analysis": trajectory_backend_readiness(),
        "esm_embedding": esm_embedding_readiness(),
        "structure_predictors": predictor_status(),
    }


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_psb_v5_pipeline(
    psb_meta_path: str | Path,
    receptor_path: str | Path,
    output_dir: str | Path,
    *,
    candidate_id: str | None = None,
    model_limit: int = 5,
    pose_limit_per_model: int = 5,
    binding_site_mode: str = "blind",
    binding_site_residues: Iterable[str] = (),
    docking_preset: str = "standard",
    run_docking: bool = True,
    run_dockbench: bool = True,
    run_md: bool = False,
    run_native_mechanics_followup: bool = False,
    native_mechanics_steps: int = 400,
    md_pose_policy: str = "top1_per_model",
    md_protocol: OpenMMProtocol | None = None,
    haddock_timeout_seconds: int | None = None,
    haddock_executable: str = "haddock3",
    docking_backend: str = "haddock3",
    execution_mode: str = "offline",
    resource_root: str | Path | None = None,
) -> dict[str, Any]:
    execution_mode = normalize_execution_mode(execution_mode)
    execution_resources = resource_status(resource_root, execution_mode=execution_mode)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    plan_paths = prepare_psb_docking_plan(
        psb_meta_path, receptor_path, out / "01_plan", candidate_id=candidate_id,
        model_limit=model_limit, pose_limit_per_model=pose_limit_per_model,
        docking_backend=str(docking_backend), binding_site_mode=binding_site_mode,
        binding_site_residues=list(binding_site_residues), require_exact_model_count=False,
    )
    plan = _load_json(plan_paths["run_plan_json"])
    model_results: list[dict[str, Any]] = []
    native_followup_results: list[dict[str, Any]] = []
    actual_lineage: list[dict[str, Any]] = []

    for job in plan.get("jobs", []):
        rank = int(job["psb_rank"])
        job_dir = out / "02_docking" / f"model_{rank:02d}"
        backend = str(docking_backend or "haddock3").strip().lower()
        native_followup = None
        if backend == "native":
            prepared = {
                "status": "READY", "engine": "Pepforge Native Docking v1",
                "version": NATIVE_DOCKING_VERSION, "job_dir": str(job_dir),
                "claim_guard": "Experimental native coordinate search; score is not affinity or binding free energy.",
            }
            if run_docking:
                native_cfg = NativeDockingConfig(
                    mode=job["binding_site_mode"], poses=int(job["requested_pose_limit"]),
                    anchor_count=8 if docking_preset == "fast" else (16 if docking_preset == "deep" else 12),
                    rotations_per_anchor=10 if docking_preset == "fast" else (30 if docking_preset == "deep" else 18),
                    max_candidates=180 if docking_preset == "fast" else (900 if docking_preset == "deep" else 500),
                )
                native = run_native_docking(
                    job["receptor_pdb"], job["peptide_pdb"], job_dir, config=native_cfg,
                    binding_residues=job.get("binding_site_residues", []),
                )
                normalized_native = normalize_native_docking_result(native)
                normalized_paths = export_normalized_result(normalized_native, job_dir / "normalized_result")
                poses = [
                    {
                        "rank": int(x["rank"]), "pose_pdb": x["pose_pdb"],
                        "score": float(x["pepforge_native_score"]),
                        "pepforge_native_score": float(x["pepforge_native_score"]),
                        "evidence_grade": "EXPERIMENTAL_NATIVE",
                        "quality_gate": dict(x.get("quality_gate") or {}),
                    }
                    for x in native.get("poses", [])
                    if str((x.get("quality_gate") or {}).get("status", "WARN")) != "FAIL"
                ]
                execution = {
                    "status": "COMPLETED" if poses else native.get("status", "NO_USABLE_POSES"),
                    "poses": poses, "readiness": {"status": "READY", "engine_version": NATIVE_DOCKING_VERSION},
                    "native_summary": native,
                    "docking_result_contract_version": DOCKING_RESULT_CONTRACT_VERSION,
                    "normalized_result": normalized_paths,
                }
                if run_native_mechanics_followup and poses:
                    follow_cfg = NativeMechanicsV2Config(
                        steps=max(20, int(native_mechanics_steps)),
                        save_every=max(1, max(20, int(native_mechanics_steps)) // 10),
                        freeze_receptor=True, peptide_chain="P",
                    )
                    native_followup = run_native_docking_followup(
                        normalized_native, job_dir / "native_followup", mechanics_config=follow_cfg
                    )
                    native_followup_results.append({
                        "model_rank": rank,
                        "selected_pose": native_followup.get("selected_pose"),
                        "status": native_followup.get("status"),
                        "summary_csv": native_followup.get("summary_csv"),
                        "frames_csv": native_followup.get("frames_csv"),
                        "contract_json": str((job_dir / "native_followup" / "native_followup_contract.json").resolve()),
                    })
            else:
                poses = []
                execution = {"status": "PREPARED_NOT_RUN", "poses": [], "readiness": {"status": "READY", "engine_version": NATIVE_DOCKING_VERSION}}
        elif backend == "haddock3":
            prepared = prepare_haddock3_job(
                job["receptor_pdb"], job["peptide_pdb"], job_dir,
                pose_limit=int(job["requested_pose_limit"]),
                binding_site_mode=job["binding_site_mode"],
                binding_site_residues=job.get("binding_site_residues", []),
                preset=docking_preset,
            )
            if run_docking:
                execution = run_haddock3_job(job_dir, executable=haddock_executable, timeout_seconds=haddock_timeout_seconds)
            else:
                execution = {"status": "PREPARED_NOT_RUN", "poses": [], "readiness": detect_haddock3(haddock_executable)}
            poses = list(execution.get("poses") or [])
        else:
            raise ValueError("docking_backend must be 'native' or 'haddock3'")
        model_result = {
            "model_rank": rank, "psb_structure_id": job["psb_structure_id"],
            "job_dir": str(job_dir), "prepared": prepared, "execution_status": execution.get("status"),
            "engine_version": (execution.get("readiness") or {}).get("engine_version"), "poses": poses,
            "normalized_result": execution.get("normalized_result"),
            "native_followup": native_followup,
        }
        model_results.append(model_result)
        if poses:
            for pose in poses:
                actual_lineage.append(lineage_record(
                    plan["candidate_id"], plan["sequence"], conformer_rank=rank, pose_rank=int(pose["rank"]),
                    structure_path=job["peptide_pdb"], pose_path=pose["pose_pdb"], docking_engine=str(docking_backend),
                    docking_status="COMPLETED_SCORED_POSE",
                    notes=(f"Pepforge native score={pose.get('score')} (experimental search score; not affinity)." if str(docking_backend)=="native" else f"HADDOCK score={pose.get('score')}; score is not experimental affinity."),
                ))
        else:
            actual_lineage.append(lineage_record(
                plan["candidate_id"], plan["sequence"], conformer_rank=rank,
                structure_path=job["peptide_pdb"], docking_engine=str(docking_backend),
                docking_status=str(execution.get("status") or "UNKNOWN"),
                notes="No verified scored pose artifact was produced.",
            ))

    lineage = export_lineage(actual_lineage, out / "03_lineage", target_path=plan["receptor_path"])
    verified_pose_count = sum(len(x.get("poses", [])) for x in model_results)
    pymol: dict[str, Any]
    dockbench: dict[str, Any]
    if verified_pose_count:
        pymol = export_pymol_docking_ensemble(model_results, out / "04_pymol", candidate_id=plan["candidate_id"])
        dockbench = analyze_pose_collection(model_results, out / "05_dockbench") if run_dockbench else {"status": "SKIPPED"}
    else:
        pymol = {"status": "NO_VERIFIED_POSES"}
        dockbench = {"status": "NO_VERIFIED_POSES"}

    md_results: list[dict[str, Any]] = []
    if run_md and verified_pose_count:
        selected: list[tuple[int, dict[str, Any]]] = []
        if md_pose_policy == "top1_per_model":
            for model in model_results:
                if model.get("poses"):
                    selected.append((int(model["model_rank"]), model["poses"][0]))
        elif md_pose_policy == "global_top1":
            candidates = [(int(m["model_rank"]), p) for m in model_results for p in m.get("poses", [])]
            if candidates:
                selected = [min(candidates, key=lambda item: float(item[1].get("score", 1e99)))]
        else:
            raise ValueError("md_pose_policy must be top1_per_model or global_top1")
        for model_rank, pose in selected:
            md_dir = out / "06_md" / f"model_{model_rank:02d}_pose_{int(pose['rank']):02d}"
            run = run_openmm_replicates(pose["pose_pdb"], md_dir, protocol=md_protocol)
            analyses: list[dict[str, Any]] = []
            for rep in run.get("replicate_results", []) or []:
                if rep.get("status") != "COMPLETED":
                    continue
                ana = analyze_trajectory(
                    rep["topology_pdb"], rep["trajectory"],
                    md_dir / "analysis" / f"replicate_{int(rep['replicate']):02d}",
                    peptide_chain_ids=("B", "P"),
                )
                ana["replicate"] = int(rep["replicate"])
                analyses.append(ana)
            comparison = summarize_replicates(analyses, md_dir / "analysis") if analyses else {"status": "NO_COMPLETED_REPLICATES"}
            md_results.append({"model_rank": model_rank, "pose_rank": int(pose["rank"]), "openmm": run, "trajectory_analyses": analyses, "replicate_comparison": comparison})

    statuses = [str(x.get("execution_status")) for x in model_results]
    if verified_pose_count:
        pipeline_status = "DOCKING_COMPLETED"
        if run_md:
            md_completed = any(str(x.get("openmm", {}).get("status")) == "COMPLETED" for x in md_results)
            pipeline_status = "MD_COMPLETED" if md_completed else "DOCKING_COMPLETED_MD_NOT_COMPLETED"
    elif any(x == "BACKEND_UNAVAILABLE" for x in statuses):
        pipeline_status = "PREPARED_DOCKING_BACKEND_UNAVAILABLE"
    elif all(x == "PREPARED_NOT_RUN" for x in statuses):
        pipeline_status = "PREPARED_NOT_RUN"
    else:
        pipeline_status = "DOCKING_FAILED_OR_NO_SCORED_POSES"

    if run_native_mechanics_followup and str(docking_backend).lower() == "native" and verified_pose_count:
        if native_followup_results and all(str(x.get("status")) in {"COMPLETED", "TERMINATED_GUARD"} for x in native_followup_results):
            pipeline_status = "NATIVE_DOCKING_FOLLOWUP_COMPLETED"
        elif not native_followup_results:
            pipeline_status = "DOCKING_COMPLETED_NATIVE_FOLLOWUP_NOT_COMPLETED"

    payload = {
        "version": PSB_V5_FULL_PIPELINE_VERSION,
        "status": pipeline_status,
        "candidate_id": plan["candidate_id"], "sequence": plan["sequence"],
        "requested_models": int(model_limit), "prepared_models": len(model_results),
        "requested_poses_per_model": int(pose_limit_per_model), "verified_pose_count": verified_pose_count,
        "execution_mode": execution_mode, "docking_backend": str(docking_backend), "resource_status": execution_resources,
        "backend_status": backend_status(execution_mode, resource_root),
        "plan_paths": plan_paths, "model_results": model_results, "lineage": lineage,
        "pymol": pymol, "dockbench": dockbench, "md_results": md_results,
        "native_followup_results": native_followup_results,
        "run_native_mechanics_followup": bool(run_native_mechanics_followup),
        "claim_guards": [
            "Docking score is not measured affinity/Kd.",
            "Top pose is not asserted to be the native pose.",
            "Short MD is not equilibrium proof.",
            "Pepforge Native Mechanics follow-up is experimental mechanics/descriptive trajectory evidence, not production MD or physical-time validation.",
            "Trajectory/cluster population is not folding probability or binding affinity.",
            "Unsupported modified chemistry is blocked until validated parameters exist.",
        ],
    }
    manifest = out / "PSB_V5_FULL_PIPELINE_MANIFEST.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = out / "README_PSB_V5_FULL_PIPELINE.txt"
    readme.write_text(
        "Pepforge V5 PSB Full Pipeline\n==============================\n\n"
        f"Status: {pipeline_status}\nCandidate: {plan['candidate_id']}\n"
        f"Prepared PSB models: {len(model_results)}\nVerified docking poses: {verified_pose_count}\n\n"
        "This run never substitutes fake poses, scores, trajectories, affinities or parameters when an optional backend is unavailable.\n",
        encoding="utf-8",
    )
    return {**payload, "manifest": str(manifest), "readme": str(readme)}


__all__ = ["PSB_V5_FULL_PIPELINE_VERSION", "backend_status", "run_psb_v5_pipeline"]
