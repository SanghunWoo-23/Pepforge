
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peptiforg_core.public_api import PUBLIC_API_VERSION
from peptiforg_core.workflow_automation_runner import default_workflow_config, save_workflow_config, load_workflow_config, run_workflow
from peptiforg_core.experimental_data_importer import make_experimental_template, export_experimental_import_package
from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard
from peptiforg_core.evidence_engine import export_evidence_engine_report_from_project
from peptiforg_core.run_comparison import export_run_comparison_package
from peptiforg_core.runtime_validation import run_runtime_validation
from peptiforg_core.full_package_audit import audit_package
from peptiforg_core.regression_audit import run_regression_audit
from peptiforg_core.release_integrity import audit_release_integrity
from peptiforg_core.release_verify_matrix import verify_release_matrix
from peptiforg_core.release_gate import release_gate_check
from peptiforg_core.simulation_protocol import build_simulation_protocol
from peptiforg_core.structure_consensus import compare_structures
from peptiforg_core.psb_v5_full_pipeline import backend_status as v5_backend_status, run_psb_v5_pipeline
from peptiforg_core.openmm_md_backend import OpenMMProtocol
from peptiforg_core.structure_predictor_backends import (
    predictor_status as v5_predictor_status,
    run_esmfold_prediction,
    run_alphafold3_prediction,
)
from peptiforg_core.psb_ai_ranker import RankerTrainingConfig, train_validate_ranker_from_csv
from peptiforg_core.local_resource_manager import resource_status, write_manifest_template
from peptiforg_core.v5_release_readiness import assess_v5_release_readiness
from peptiforg_core.native_docking_v1 import NativeDockingConfig, run_native_docking
from peptiforg_core.native_geometry_dynamics_v1 import NativeGeometryDynamicsConfig, run_native_geometry_dynamics
from peptiforg_core.native_topology_v1 import build_native_topology, export_native_topology
from peptiforg_core.native_mechanics_v1 import NativeMechanicsConfig, run_native_mechanics
from peptiforg_core.native_mechanics_v2 import NativeMechanicsV2Config, run_native_mechanics_v2
from peptiforg_core.native_forcefield_v2 import NativeParameterSet
from peptiforg_core.native_end_to_end_v1 import NativeE2EConfig, run_native_end_to_end
from peptiforg_core.native_core_readiness_v1 import assess_native_core_readiness
from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.quality_preserving_peptide_builder_v1 import build_quality_preserving_peptide
from peptiforg_core.native_trajectory_analysis_v1 import analyze_native_frames
from peptiforg_core.native_docking_benchmark_v1 import DockingBenchmarkConfig, benchmark_model_set, evaluate_complex_against_reference
from peptiforg_core.native_mechanics_validation_v1 import MechanicsValidationConfig, validate_native_mechanics
from peptiforg_core.native_validation_suite_v1 import NativePromotionPolicy, aggregate_validation_evidence, discover_benchmark_summaries
from peptiforg_core.native_benchmark_dataset_v1 import BenchmarkDatasetPolicy, audit_benchmark_manifest, run_benchmark_dataset, write_benchmark_manifest_template
from peptiforg_core.native_benchmark_calibration_v1 import CalibrationPolicy, calibrate_benchmark_results, discover_target_summaries
from peptiforg_core.native_release_dossier_v1 import ReleaseDossierPolicy, build_release_dossier
from peptiforg_core.native_validation_finalize_v1 import finalize_native_validation
from peptiforg_core.native_validation_workspace_v1 import inspect_validation_workspace
from peptiforg_core.native_result_interpretation_v1 import export_native_result_interpretation
from peptiforg_core.docking_followup_v1 import load_normalized_result_export, run_native_docking_followup
from peptiforg_core.public_peptide_benchmark_v1 import PUBLIC_57_CASES, write_public_registry, sync_public_registry
from peptiforg_core.native_docking_tuning_v1 import tune_native_docking
from peptiforg_core.public_benchmark_leakage_v1 import audit_public_benchmark_split
from peptiforg_core.uniprot_bridge_v1 import get_uniprot_entry, search_uniprot
from peptiforg_core.v5_final_release_v1 import V5FinalPolicy, audit_v5_final_release


def cmd_version(args):
    print(f"Pepforge Public Research Release {PUBLIC_API_VERSION}")


def cmd_init_workflow(args):
    cfg = default_workflow_config(args.project_name)
    path = save_workflow_config(cfg, args.project_dir)
    print(path)


def cmd_run_workflow(args):
    if args.config:
        cfg = load_workflow_config(args.config)
    else:
        cfg = default_workflow_config(args.project_name)
    paths = run_workflow(cfg, args.project_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_experimental_template(args):
    print(make_experimental_template(args.output_dir))


def cmd_import_experimental(args):
    paths = export_experimental_import_package(args.input_csv, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_dashboard(args):
    paths = export_candidate_dashboard(
        output_dir=args.output_dir,
        design_candidates_csv=args.design_csv,
        docking_contacts_csv=args.docking_csv,
        external_docking_scores_csv=args.external_csv,
        calibration_predictions_csv=args.calibration_csv,
        experimental_candidate_summary_csv=args.experimental_csv,
    )
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_evidence_autoscan(args):
    paths = export_evidence_engine_report_from_project(args.project_dir, output_dir=args.output_dir or args.project_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_compare_runs(args):
    paths = export_run_comparison_package(
        old_project_dir=args.old_project,
        new_project_dir=args.new_project,
        output_dir=args.output_dir,
        old_dashboard_csv=args.old_dashboard,
        new_dashboard_csv=args.new_dashboard,
        old_evidence_summary_json=args.old_evidence,
        new_evidence_summary_json=args.new_evidence,
    )
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_validate_runtime(args):
    paths = run_runtime_validation(args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_audit_package(args):
    paths = audit_package(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_regression_audit(args):
    paths = run_regression_audit(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_release_integrity(args):
    paths = audit_release_integrity(args.root_dir, args.output_dir, run_nested=args.run_nested)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_verify_matrix(args):
    paths = verify_release_matrix(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_release_gate(args):
    paths = release_gate_check(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))
    summary = json.loads(Path(paths["release_gate_summary"]).read_text(encoding="utf-8"))
    if int(summary.get("failed", 0)):
        raise SystemExit(1)



def cmd_simulation_protocol(args):
    payload = build_simulation_protocol(
        args.sequence,
        design_mode=args.design_mode,
        preferred_structure=args.preferred_structure,
        environment=args.environment,
        peptide_class=args.peptide_class or None,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json:
        path = Path(args.output_json); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text + "\n", encoding="utf-8")
        print(path)
    else:
        print(text)


def cmd_compare_structures(args):
    paths = compare_structures(args.reference, args.comparison, args.output_dir, name=args.name)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_v5_backend_status(args):
    print(json.dumps(v5_backend_status(args.execution_mode, args.resource_root or None), indent=2, ensure_ascii=False))


def cmd_v5_resource_status(args):
    if args.init_manifest:
        print(write_manifest_template(args.resource_root or None))
    print(json.dumps(resource_status(args.resource_root or None, execution_mode=args.execution_mode), indent=2, ensure_ascii=False))


def cmd_v5_predictor_status(args):
    print(json.dumps(v5_predictor_status(), indent=2, ensure_ascii=False))


def cmd_v5_predict_esmfold(args):
    payload = run_esmfold_prediction(
        args.sequence, args.output_dir, model_name=args.model_name, device=args.device,
        local_files_only=bool(args.local_files_only), chunk_size=(int(args.chunk_size) if int(args.chunk_size) > 0 else None),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("status") not in {"COMPLETED", "BACKEND_UNAVAILABLE"}:
        raise SystemExit(1)


def cmd_v5_predict_af3(args):
    seeds = tuple(int(x.strip()) for x in str(args.seeds).split(",") if x.strip())
    payload = run_alphafold3_prediction(
        args.sequence, args.output_dir, run_script=args.run_script, model_dir=args.model_dir, db_dir=args.db_dir,
        python_executable=(args.python_executable or None), name=args.name, model_seeds=seeds,
        timeout_seconds=(int(args.timeout) if int(args.timeout) > 0 else None),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("status") not in {"COMPLETED", "BACKEND_UNAVAILABLE"}:
        raise SystemExit(1)


def cmd_v5_train_ranker(args):
    columns = [x.strip() for x in str(args.features or "").split(",") if x.strip()] or None
    cfg = RankerTrainingConfig(
        n_estimators=int(args.trees), random_state=int(args.seed),
        min_training_rows=int(args.min_rows), cv_folds=int(args.folds),
    )
    payload = train_validate_ranker_from_csv(
        args.csv, args.output_dir, target_column=args.target, feature_columns=columns,
        sequence_column=(args.sequence_column or None), row_id_column=(args.row_id_column or None),
        use_esm=bool(args.use_esm), config=cfg,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_psb_simulate(args):
    residues=[x.strip() for x in str(args.binding_residues or "").replace(",",";").split(";") if x.strip()]
    protocol=OpenMMProtocol(
        production_ns=float(args.production_ns),
        equilibration_ps=float(args.equilibration_ps),
        replicates=int(args.replicates),
    )
    payload=run_psb_v5_pipeline(
        args.psb_meta, args.receptor, args.output_dir,
        model_limit=int(args.models), pose_limit_per_model=int(args.poses),
        binding_site_mode=args.binding_mode, binding_site_residues=residues,
        docking_preset=args.preset, run_docking=not args.prepare_only,
        run_dockbench=not args.skip_dockbench, run_md=bool(args.run_md),
        run_native_mechanics_followup=bool(args.run_native_followup), native_mechanics_steps=int(args.native_mechanics_steps),
        md_pose_policy=args.md_pose_policy, md_protocol=protocol,
        haddock_timeout_seconds=(int(args.timeout) if int(args.timeout)>0 else None),
        haddock_executable=args.haddock_executable, docking_backend=args.docking_backend,
        execution_mode=args.execution_mode, resource_root=(args.resource_root or None),
    )
    print(json.dumps({k:v for k,v in payload.items() if k not in {"model_results","md_results"}}, indent=2, ensure_ascii=False))





def cmd_v5_native_relax(args):
    cfg=NativeGeometryDynamicsConfig(
        steps=int(args.steps), step_size=float(args.step_size), bond_k=float(args.bond_k),
        repulsion_k=float(args.repulsion_k), weak_attraction_k=float(args.weak_attraction_k),
        noise_scale=float(args.noise_scale), save_every=int(args.save_every),
        freeze_receptor=not bool(args.move_all), peptide_chain=str(args.peptide_chain or "P"),
    )
    payload=run_native_geometry_dynamics(
        args.pdb,args.output_dir,config=cfg,restart_state=(args.restart or None)
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))




def cmd_v5_native_build_peptide(args):
    def parse_list(text):
        return [float(x.strip()) for x in str(text).split(",") if x.strip()] if str(text or "").strip() else None
    payload=export_native_backbone(args.sequence,args.output_dir,phi_deg=parse_list(args.phi),psi_deg=parse_list(args.psi),omega_deg=parse_list(args.omega),chain=args.chain)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_build_peptide(args):
    def parse_list(text):
        return [float(x.strip()) for x in str(text).split(",") if x.strip()] if str(text or "").strip() else None
    payload=build_quality_preserving_peptide(
        args.sequence,args.output_dir,phi_deg=parse_list(args.phi),psi_deg=parse_list(args.psi),omega_deg=parse_list(args.omega),
        chain=args.chain,enable_rdkit=not bool(args.native_only),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def cmd_v5_native_topology(args):
    top=build_native_topology(args.pdb)
    path=export_native_topology(top,args.output)
    print(json.dumps({"status":"COMPLETED","topology":top.summary(),"output":path}, indent=2, ensure_ascii=False))


def cmd_v5_native_mechanics(args):
    cfg=NativeMechanicsConfig(
        steps=int(args.steps), dt_reduced=float(args.dt_reduced), bond_k=float(args.bond_k),
        angle_k=float(args.angle_k), repulsion_k=float(args.repulsion_k), attraction_k=float(args.attraction_k),
        electrostatic_k=float(args.electrostatic_k), dielectric=float(args.dielectric), damping=float(args.damping),
        velocity_noise=float(args.velocity_noise), max_displacement_A=float(args.max_displacement),
        save_every=int(args.save_every), freeze_receptor=bool(args.freeze_receptor),
        peptide_chain=str(args.peptide_chain or "P"),
    )
    payload=run_native_mechanics(args.pdb,args.output_dir,config=cfg,restart_state=(args.restart or None))
    print(json.dumps(payload, indent=2, ensure_ascii=False))



def cmd_v5_native_mechanics_v2(args):
    cfg=NativeMechanicsV2Config(
        steps=int(args.steps),dt_reduced=float(args.dt_reduced),damping=float(args.damping),
        velocity_noise=float(args.velocity_noise),max_displacement_A=float(args.max_displacement),
        save_every=int(args.save_every),freeze_receptor=bool(args.freeze_receptor),
        peptide_chain=str(args.peptide_chain or "P"),
    )
    prm=NativeParameterSet(
        bond_k=float(args.bond_k),angle_k=float(args.angle_k),torsion_14_k=float(args.torsion_14_k),
        lj_scale=float(args.lj_scale),coulomb_scale=float(args.coulomb_scale),
        dielectric=float(args.dielectric),cutoff_A=float(args.cutoff),scale_14_nonbonded=float(args.scale_14),
    )
    payload=run_native_mechanics_v2(args.pdb,args.output_dir,config=cfg,parameters=prm,restart_state=(args.restart or None))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_native_e2e(args):
    residues=[x.strip() for x in str(args.binding_residues or "").replace(",",";").split(";") if x.strip()]
    cfg=NativeE2EConfig(
        enable_rdkit_quality_layer=not bool(args.native_only),docking_mode=args.binding_mode,
        docking_poses=int(args.poses),docking_anchors=int(args.anchors),docking_rotations=int(args.rotations),
        docking_candidates=int(args.max_candidates),mechanics_steps=int(args.mechanics_steps),
        mechanics_save_every=int(args.save_every),mechanics_dt_reduced=float(args.dt_reduced),
        run_mechanics_on_top_pose=not bool(args.skip_mechanics),peptide_chain="P",
    )
    payload=run_native_end_to_end(args.sequence,args.receptor,args.output_dir,config=cfg,binding_residues=residues)
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def cmd_v5_native_trajectory(args):
    frames=[]
    if args.frames_dir:
        frames=sorted(str(p) for p in Path(args.frames_dir).expanduser().resolve().glob("*.pdb"))
    if args.frames:
        frames.extend([x.strip() for x in str(args.frames).split(",") if x.strip()])
    payload=analyze_native_frames(frames,args.output_dir,clusters=int(args.clusters))
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def cmd_v5_native_dock(args):
    residues=[x.strip() for x in str(args.binding_residues or "").replace(",",";").split(";") if x.strip()]
    profile={}
    if getattr(args,"score_profile",""):
        profile=json.loads(Path(args.score_profile).expanduser().read_text(encoding="utf-8"))
        allowed={"clash_penalty","smooth_contact_weight","contact_count_weight","interaction_score_scale"}
        profile={k:profile[k] for k in allowed if k in profile}
    cfg=NativeDockingConfig(
        mode=args.binding_mode, poses=int(args.poses), anchor_count=int(args.anchors),
        rotations_per_anchor=int(args.rotations), shell_distance_A=float(args.shell_distance),
        local_refine_steps=int(args.refine_steps), local_step_A=float(args.refine_step),
        cluster_centroid_A=float(args.cluster_centroid), max_candidates=int(args.max_candidates),
        **profile,
    )
    payload=run_native_docking(args.receptor,args.peptide,args.output_dir,config=cfg,binding_residues=residues)
    if profile:
        payload["score_profile"]={"path":str(Path(args.score_profile).expanduser().resolve()),"applied":profile,"claim_guard":"Tuned weights are computational calibration, not affinity parameters."}
        Path(args.output_dir).mkdir(parents=True,exist_ok=True)
        (Path(args.output_dir)/"native_docking_result.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))




def cmd_v5_native_followup(args):
    normalized=load_normalized_result_export(args.docking_result)
    cfg=NativeMechanicsV2Config(
        steps=int(args.steps), dt_reduced=float(args.dt_reduced), damping=float(args.damping),
        save_every=int(args.save_every), freeze_receptor=not bool(args.move_all), peptide_chain=str(args.peptide_chain or "P"),
    )
    payload=run_native_docking_followup(normalized,args.output_dir,mechanics_config=cfg,allow_warn_pose=not bool(args.pass_only))
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def cmd_v5_native_core_readiness(args):
    payload=assess_native_core_readiness(args.output_dir,run_self_smoke=not bool(args.skip_smoke))
    print(json.dumps(payload, indent=2, ensure_ascii=False))

def cmd_v5_release_readiness(args):
    payload = assess_v5_release_readiness(
        args.root_dir, args.output_dir, execution_mode=args.execution_mode,
        resource_root=(args.resource_root or None), ranker_metadata=(args.ranker_metadata or None),
        run_release_gate=not args.skip_release_gate,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))




def cmd_v5_native_docking_benchmark(args):
    cfg = DockingBenchmarkConfig(receptor_chain=args.receptor_chain, ligand_chain=args.ligand_chain)
    models=[]
    if args.models_dir:
        models.extend(sorted(str(p) for p in Path(args.models_dir).glob("*.pdb")))
    if args.models:
        models.extend(x.strip() for x in args.models.split(",") if x.strip())
    if not models:
        raise SystemExit("No model PDB files were provided")
    payload=benchmark_model_set(args.reference, models, args.output_dir, config=cfg, score_csv=args.score_csv or None)
    print(json.dumps(payload, indent=2, ensure_ascii=False))




def cmd_v5_native_benchmark_dataset(args):
    policy = BenchmarkDatasetPolicy(
        require_unique_reference_content=not bool(args.allow_duplicate_reference),
        reject_reference_as_model=not bool(args.allow_reference_as_model),
        require_models=not bool(args.audit_only),
        minimum_models_per_target=max(0, int(args.min_models)),
    )
    if args.write_template:
        path = write_benchmark_manifest_template(args.write_template)
        print(json.dumps({"status":"TEMPLATE_WRITTEN","path":path}, indent=2, ensure_ascii=False))
        return
    if not args.manifest:
        raise SystemExit("--manifest is required unless --write-template is used")
    if args.audit_only:
        payload = audit_benchmark_manifest(args.manifest, args.output_dir, policy=policy)
    else:
        payload = run_benchmark_dataset(args.manifest, args.output_dir, policy=policy, fail_on_target_error=bool(args.fail_fast))
    print(json.dumps(payload, indent=2, ensure_ascii=False))



def cmd_v5_public_benchmark_registry(args):
    path=write_public_registry(args.output_csv)
    print(json.dumps({"status":"WRITTEN","case_count":len(PUBLIC_57_CASES),"path":path}, indent=2, ensure_ascii=False))


def cmd_v5_public_benchmark_sync(args):
    ids=[x.strip().upper() for x in str(args.targets or "").replace(",",";").split(";") if x.strip()]
    payload=sync_public_registry(
        args.output_dir,target_ids=ids or None,include_unbound=not bool(args.bound_only),
        include_uniprot=not bool(args.no_uniprot),continue_on_error=not bool(args.fail_fast),
        local_cache=(args.local_cache or None),allow_network=not bool(args.offline_only))
    print(json.dumps(payload, indent=2, ensure_ascii=False))



def cmd_v5_public_benchmark_split_audit(args):
    payload=audit_public_benchmark_split(args.registry,args.prepared_root,args.output_dir)
    print(json.dumps(payload,indent=2,ensure_ascii=False))


def cmd_v5_uniprot_lookup(args):
    if args.accession:
        payload=get_uniprot_entry(args.accession,raw_output=(args.raw_output or None))
    else:
        payload={"query":args.query,"results":search_uniprot(args.query,rows=int(args.rows),reviewed_only=bool(args.reviewed_only))}
    print(json.dumps(payload,indent=2,ensure_ascii=False))


def cmd_v5_final_release_audit(args):
    policy=V5FinalPolicy()
    payload=audit_v5_final_release(args.root_dir,args.output_dir,policy=policy)
    print(json.dumps(payload,indent=2,ensure_ascii=False))

def cmd_v5_native_docking_tune(args):
    base=NativeDockingConfig(poses=int(args.poses),anchor_count=int(args.anchors),rotations_per_anchor=int(args.rotations),max_candidates=int(args.max_candidates))
    payload=tune_native_docking(args.registry,args.prepared_root,args.output_dir,base_config=base,prefer_unbound=not bool(args.bound_receptor),max_train_targets=(args.max_train_targets or None),max_holdout_targets=(args.max_holdout_targets or None))
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_native_benchmark_calibration(args):
    files = discover_target_summaries(args.benchmarks_root) if args.benchmarks_root else []
    if args.benchmarks:
        files.extend(x.strip() for x in args.benchmarks.split(",") if x.strip())
    policy = CalibrationPolicy(
        acceptable_dockq=args.acceptable_dockq,
        medium_dockq=args.medium_dockq,
        high_dockq=args.high_dockq,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
        min_pairs_for_correlation=args.min_pairs_for_correlation,
    )
    payload = calibrate_benchmark_results(files, args.output_dir, policy=policy)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_native_release_dossier(args):
    policy = ReleaseDossierPolicy(
        min_external_targets=args.min_targets,
        min_ranked_targets=args.min_ranked_targets,
        require_holdout_split=not args.allow_no_holdout,
        min_top5_acceptable_rate=args.min_top5_acceptable_rate,
        require_score_structure_pairs=args.min_score_structure_pairs,
        require_mechanics_numerical_pass=not args.allow_missing_mechanics_validation,
    )
    payload = build_release_dossier(
        args.output_dir,
        calibration_json=args.calibration or None,
        mechanics_validation_json=args.mechanics_validation or None,
        release_gate_json=args.release_gate or None,
        policy=policy,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))



def cmd_v5_native_validation_finalize(args):
    cpol = CalibrationPolicy(bootstrap_iterations=args.bootstrap_iterations, bootstrap_seed=args.bootstrap_seed)
    dpol = ReleaseDossierPolicy(
        min_external_targets=args.min_targets, min_ranked_targets=args.min_ranked_targets,
        require_holdout_split=not args.allow_no_holdout, min_top5_acceptable_rate=args.min_top5_acceptable_rate,
        require_score_structure_pairs=args.min_score_structure_pairs,
        require_mechanics_numerical_pass=not args.allow_missing_mechanics_validation,
    )
    payload = finalize_native_validation(
        args.benchmarks_root, args.output_dir,
        mechanics_validation_json=args.mechanics_validation or None, release_gate_json=args.release_gate or None,
        calibration_policy=cpol, dossier_policy=dpol,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))




def cmd_v5_native_result_interpret(args):
    normalized = load_normalized_result_export(args.docking_result)
    followups = []
    if args.followup:
        fp = Path(args.followup).expanduser().resolve()
        if fp.is_dir():
            fp = fp / "native_followup_contract.json"
        if fp.is_file():
            followups = [json.loads(fp.read_text(encoding="utf-8"))]
    payload = export_native_result_interpretation(
        normalized, followups, args.output_dir, selected_pose_id=args.pose_id or ""
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_v5_native_validation_workspace(args):
    payload = inspect_validation_workspace(args.root, args.output_dir or None)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("status") == "WORKSPACE_NEEDS_REPAIR":
        raise SystemExit(2)


def cmd_v5_native_mechanics_validate(args):
    cfg=MechanicsValidationConfig(
        finite_difference_h_A=args.fd_h, max_coordinates=args.max_coordinates,
        force_abs_tolerance=args.abs_tolerance, force_rel_tolerance=args.rel_tolerance,
        integration_steps=args.steps, integration_dt_reduced=args.dt_reduced, max_score_ratio=args.max_score_ratio,
    )
    payload=validate_native_mechanics(args.pdb, args.output_dir, config=cfg)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("status") != "PASS":
        raise SystemExit(1)



def cmd_v5_native_validation_suite(args):
    files=discover_benchmark_summaries(args.benchmarks_root) if args.benchmarks_root else []
    if args.benchmarks:
        files.extend(x.strip() for x in args.benchmarks.split(",") if x.strip())
    policy=NativePromotionPolicy(
        min_docking_targets=args.min_targets,
        min_targets_with_ranked_poses=args.min_ranked_targets,
        min_top5_acceptable_rate=args.min_top5_acceptable_rate,
        require_mechanics_numerical_pass=not args.allow_missing_mechanics_validation,
    )
    payload=aggregate_validation_evidence(files,args.output_dir,mechanics_validation_json=args.mechanics_validation or None,policy=policy)
    print(json.dumps(payload,indent=2,ensure_ascii=False))

def build_parser():
    p = argparse.ArgumentParser(
        prog="pepforge_cli",
        description="Pepforge public research CLI. Screening/planning/evidence workflow only; not final binding proof.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("version")
    sp.set_defaults(func=cmd_version)

    sp = sub.add_parser("init-workflow")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--project-name", default="Pepforge_Project")
    sp.set_defaults(func=cmd_init_workflow)

    sp = sub.add_parser("run-workflow")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--project-name", default="Pepforge_Project")
    sp.add_argument("--config", default="")
    sp.set_defaults(func=cmd_run_workflow)

    sp = sub.add_parser("experimental-template")
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_experimental_template)

    sp = sub.add_parser("import-experimental")
    sp.add_argument("--input-csv", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_import_experimental)

    sp = sub.add_parser("dashboard")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--design-csv", default="")
    sp.add_argument("--docking-csv", default="")
    sp.add_argument("--external-csv", default="")
    sp.add_argument("--calibration-csv", default="")
    sp.add_argument("--experimental-csv", default="")
    sp.set_defaults(func=cmd_dashboard)

    sp = sub.add_parser("evidence-autoscan")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--output-dir", default="")
    sp.set_defaults(func=cmd_evidence_autoscan)

    sp = sub.add_parser("validate-runtime")
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_validate_runtime)

    sp = sub.add_parser("audit-package")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_audit_package)

    sp = sub.add_parser("regression-audit")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_regression_audit)

    sp = sub.add_parser("release-integrity")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--run-nested", action="store_true")
    sp.set_defaults(func=cmd_release_integrity)

    sp = sub.add_parser("verify-matrix")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_verify_matrix)

    sp = sub.add_parser("release-gate")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_release_gate)


    sp = sub.add_parser("simulation-protocol")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--design-mode", default="BALANCED")
    sp.add_argument("--preferred-structure", default="NONE")
    sp.add_argument("--environment", default="AQUEOUS")
    sp.add_argument("--peptide-class", default="")
    sp.add_argument("--output-json", default="")
    sp.set_defaults(func=cmd_simulation_protocol)

    sp = sub.add_parser("compare-structures")
    sp.add_argument("--reference", required=True)
    sp.add_argument("--comparison", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--name", default="structure_consensus")
    sp.set_defaults(func=cmd_compare_structures)

    sp = sub.add_parser("compare-runs")
    sp.add_argument("--old-project", required=True)
    sp.add_argument("--new-project", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--old-dashboard", default="")
    sp.add_argument("--new-dashboard", default="")
    sp.add_argument("--old-evidence", default="")
    sp.add_argument("--new-evidence", default="")
    sp.set_defaults(func=cmd_compare_runs)


    sp = sub.add_parser("v5-release-readiness")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--execution-mode", choices=["offline","auto","online_enhanced"], default="offline")
    sp.add_argument("--resource-root", default="")
    sp.add_argument("--ranker-metadata", default="")
    sp.add_argument("--skip-release-gate", action="store_true")
    sp.set_defaults(func=cmd_v5_release_readiness)

    sp = sub.add_parser("v5-backend-status")
    sp.add_argument("--execution-mode", choices=["offline","auto","online_enhanced"], default="offline")
    sp.add_argument("--resource-root", default="")
    sp.set_defaults(func=cmd_v5_backend_status)

    sp = sub.add_parser("v5-resource-status")
    sp.add_argument("--execution-mode", choices=["offline","auto","online_enhanced"], default="offline")
    sp.add_argument("--resource-root", default="")
    sp.add_argument("--init-manifest", action="store_true")
    sp.set_defaults(func=cmd_v5_resource_status)

    sp = sub.add_parser("v5-predictor-status")
    sp.set_defaults(func=cmd_v5_predictor_status)

    sp = sub.add_parser("v5-predict-esmfold")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--model-name", default="facebook/esmfold_v1")
    sp.add_argument("--device", default="auto")
    sp.add_argument("--chunk-size", type=int, default=128)
    sp.add_argument("--local-files-only", action="store_true")
    sp.set_defaults(func=cmd_v5_predict_esmfold)

    sp = sub.add_parser("v5-predict-af3")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--run-script", required=True)
    sp.add_argument("--model-dir", required=True)
    sp.add_argument("--db-dir", required=True)
    sp.add_argument("--python-executable", default="")
    sp.add_argument("--name", default="Pepforge_receptor")
    sp.add_argument("--seeds", default="20260928")
    sp.add_argument("--timeout", type=int, default=0)
    sp.set_defaults(func=cmd_v5_predict_af3)

    sp = sub.add_parser("v5-train-ranker")
    sp.add_argument("--csv", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--target", required=True)
    sp.add_argument("--features", default="", help="Comma-separated numeric columns; blank auto-detects numeric columns.")
    sp.add_argument("--sequence-column", default="")
    sp.add_argument("--row-id-column", default="")
    sp.add_argument("--use-esm", action="store_true")
    sp.add_argument("--folds", type=int, default=5)
    sp.add_argument("--trees", type=int, default=300)
    sp.add_argument("--seed", type=int, default=20260923)
    sp.add_argument("--min-rows", type=int, default=12)
    sp.set_defaults(func=cmd_v5_train_ranker)

    sp = sub.add_parser("v5-native-relax")
    sp.add_argument("--pdb", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--steps", type=int, default=250)
    sp.add_argument("--step-size", type=float, default=0.003)
    sp.add_argument("--bond-k", type=float, default=30.0)
    sp.add_argument("--repulsion-k", type=float, default=2.0)
    sp.add_argument("--weak-attraction-k", type=float, default=0.02)
    sp.add_argument("--noise-scale", type=float, default=0.0)
    sp.add_argument("--save-every", type=int, default=25)
    sp.add_argument("--peptide-chain", default="P")
    sp.add_argument("--move-all", action="store_true")
    sp.add_argument("--restart", default="")
    sp.set_defaults(func=cmd_v5_native_relax)

    sp = sub.add_parser("v5-native-build-peptide")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--phi", default="", help="Comma-separated phi angles; blank uses alpha-like seed")
    sp.add_argument("--psi", default="", help="Comma-separated psi angles; blank uses alpha-like seed")
    sp.add_argument("--omega", default="", help="Comma-separated peptide omega angles; blank uses trans 180")
    sp.add_argument("--chain", default="P")
    sp.set_defaults(func=cmd_v5_native_build_peptide)

    sp = sub.add_parser("v5-build-peptide")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--phi", default="")
    sp.add_argument("--psi", default="")
    sp.add_argument("--omega", default="")
    sp.add_argument("--chain", default="P")
    sp.add_argument("--native-only", action="store_true", help="Disable optional RDKit quality enhancement")
    sp.set_defaults(func=cmd_v5_build_peptide)

    sp = sub.add_parser("v5-native-topology")
    sp.add_argument("--pdb", required=True)
    sp.add_argument("--output", required=True)
    sp.set_defaults(func=cmd_v5_native_topology)

    sp = sub.add_parser("v5-native-mechanics")
    sp.add_argument("--pdb", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--steps", type=int, default=500)
    sp.add_argument("--dt-reduced", type=float, default=0.0008)
    sp.add_argument("--bond-k", type=float, default=45.0)
    sp.add_argument("--angle-k", type=float, default=6.0)
    sp.add_argument("--repulsion-k", type=float, default=3.0)
    sp.add_argument("--attraction-k", type=float, default=0.025)
    sp.add_argument("--electrostatic-k", type=float, default=0.35)
    sp.add_argument("--dielectric", type=float, default=20.0)
    sp.add_argument("--damping", type=float, default=0.06)
    sp.add_argument("--velocity-noise", type=float, default=0.0)
    sp.add_argument("--max-displacement", type=float, default=0.12)
    sp.add_argument("--save-every", type=int, default=50)
    sp.add_argument("--peptide-chain", default="P")
    sp.add_argument("--freeze-receptor", action="store_true")
    sp.add_argument("--restart", default="")
    sp.set_defaults(func=cmd_v5_native_mechanics)



    sp = sub.add_parser("v5-native-mechanics-v2")
    sp.add_argument("--pdb", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--steps", type=int, default=750)
    sp.add_argument("--dt-reduced", type=float, default=0.0006)
    sp.add_argument("--bond-k", type=float, default=55.0)
    sp.add_argument("--angle-k", type=float, default=8.0)
    sp.add_argument("--torsion-14-k", type=float, default=0.50)
    sp.add_argument("--lj-scale", type=float, default=1.0)
    sp.add_argument("--coulomb-scale", type=float, default=0.30)
    sp.add_argument("--dielectric", type=float, default=20.0)
    sp.add_argument("--cutoff", type=float, default=12.0)
    sp.add_argument("--scale-14", type=float, default=0.50)
    sp.add_argument("--damping", type=float, default=0.035)
    sp.add_argument("--velocity-noise", type=float, default=0.0)
    sp.add_argument("--max-displacement", type=float, default=0.08)
    sp.add_argument("--save-every", type=int, default=50)
    sp.add_argument("--peptide-chain", default="P")
    sp.add_argument("--freeze-receptor", action="store_true")
    sp.add_argument("--restart", default="")
    sp.set_defaults(func=cmd_v5_native_mechanics_v2)

    sp = sub.add_parser("v5-native-e2e")
    sp.add_argument("--sequence", required=True)
    sp.add_argument("--receptor", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--native-only", action="store_true", help="Disable optional local RDKit quality enhancement")
    sp.add_argument("--poses", type=int, default=5)
    sp.add_argument("--binding-mode", choices=["blind","hotspot","manual"], default="blind")
    sp.add_argument("--binding-residues", default="")
    sp.add_argument("--anchors", type=int, default=10)
    sp.add_argument("--rotations", type=int, default=14)
    sp.add_argument("--max-candidates", type=int, default=300)
    sp.add_argument("--mechanics-steps", type=int, default=300)
    sp.add_argument("--dt-reduced", type=float, default=0.0004)
    sp.add_argument("--save-every", type=int, default=50)
    sp.add_argument("--skip-mechanics", action="store_true")
    sp.set_defaults(func=cmd_v5_native_e2e)

    sp = sub.add_parser("v5-native-trajectory")
    sp.add_argument("--frames-dir", default="", help="Directory containing ordered PDB frames")
    sp.add_argument("--frames", default="", help="Comma-separated PDB frame paths")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--clusters", type=int, default=5)
    sp.set_defaults(func=cmd_v5_native_trajectory)

    sp = sub.add_parser("v5-native-dock")
    sp.add_argument("--receptor", required=True)
    sp.add_argument("--peptide", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--poses", type=int, default=5)
    sp.add_argument("--binding-mode", choices=["blind","hotspot","manual"], default="blind")
    sp.add_argument("--binding-residues", default="")
    sp.add_argument("--anchors", type=int, default=12)
    sp.add_argument("--rotations", type=int, default=18)
    sp.add_argument("--shell-distance", type=float, default=4.5)
    sp.add_argument("--refine-steps", type=int, default=2)
    sp.add_argument("--refine-step", type=float, default=0.75)
    sp.add_argument("--cluster-centroid", type=float, default=2.0)
    sp.add_argument("--max-candidates", type=int, default=500)
    sp.add_argument("--score-profile", default="", help="JSON score profile produced by v5-native-docking-tune")
    sp.set_defaults(func=cmd_v5_native_dock)

    sp = sub.add_parser("v5-native-docking-benchmark")
    sp.add_argument("--reference", required=True, help="Reference complex PDB")
    sp.add_argument("--models-dir", default="", help="Directory containing predicted complex PDB files")
    sp.add_argument("--models", default="", help="Comma-separated predicted complex PDB files")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--receptor-chain", default="A")
    sp.add_argument("--ligand-chain", default="P")
    sp.add_argument("--score-csv", default="", help="Optional internal docking-score table for rank correlation")
    sp.set_defaults(func=cmd_v5_native_docking_benchmark)


    sp = sub.add_parser("v5-native-benchmark-dataset")
    sp.add_argument("--manifest", default="", help="CSV/JSON target manifest with explicit reference and predicted models")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--audit-only", action="store_true", help="Validate manifest integrity without running benchmarks")
    sp.add_argument("--write-template", default="", help="Write a benchmark manifest CSV template and exit")
    sp.add_argument("--min-models", type=int, default=1)
    sp.add_argument("--allow-duplicate-reference", action="store_true", help="Allow identical reference content across target IDs")
    sp.add_argument("--allow-reference-as-model", action="store_true", help="Disable reference/model leakage hard block; not recommended")
    sp.add_argument("--fail-fast", action="store_true", help="Stop on the first target benchmark execution error")
    sp.set_defaults(func=cmd_v5_native_benchmark_dataset)


    sp = sub.add_parser("v5-public-benchmark-registry")
    sp.add_argument("--output-csv", required=True)
    sp.set_defaults(func=cmd_v5_public_benchmark_registry)

    sp = sub.add_parser("v5-public-benchmark-sync")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--targets", default="", help="Comma/semicolon-separated bound PDB IDs; default syncs all 57")
    sp.add_argument("--bound-only", action="store_true", help="Skip unbound receptor download")
    sp.add_argument("--no-uniprot", action="store_true", help="Skip UniProt enrichment")
    sp.add_argument("--local-cache", default="", help="Optional local PDB/UniProt mirror or cache; checked before network retrieval")
    sp.add_argument("--offline-only", action="store_true", help="Do not use network; require coordinates in --local-cache or existing output")
    sp.add_argument("--fail-fast", action="store_true")
    sp.set_defaults(func=cmd_v5_public_benchmark_sync)

    sp = sub.add_parser("v5-public-benchmark-split-audit")
    sp.add_argument("--registry", required=True)
    sp.add_argument("--prepared-root", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_v5_public_benchmark_split_audit)

    sp = sub.add_parser("v5-uniprot-lookup")
    g=sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--accession", default="")
    g.add_argument("--query", default="")
    sp.add_argument("--rows", type=int, default=10)
    sp.add_argument("--reviewed-only", action="store_true")
    sp.add_argument("--raw-output", default="", help="Optional raw UniProt JSON output path for accession lookup")
    sp.set_defaults(func=cmd_v5_uniprot_lookup)

    sp = sub.add_parser("v5-native-docking-tune")
    sp.add_argument("--registry", required=True)
    sp.add_argument("--prepared-root", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--poses", type=int, default=10)
    sp.add_argument("--anchors", type=int, default=16)
    sp.add_argument("--rotations", type=int, default=24)
    sp.add_argument("--max-candidates", type=int, default=600)
    sp.add_argument("--bound-receptor", action="store_true", help="Use bound receptor instead of available apo/unbound receptor")
    sp.add_argument("--max-train-targets", type=int, default=0)
    sp.add_argument("--max-holdout-targets", type=int, default=0)
    sp.set_defaults(func=cmd_v5_native_docking_tune)

    sp = sub.add_parser("v5-native-benchmark-calibration")
    sp.add_argument("--benchmarks-root", default="", help="Recursively discover per-target benchmark summaries")
    sp.add_argument("--benchmarks", default="", help="Comma-separated benchmark summary JSON files")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--acceptable-dockq", type=float, default=0.23)
    sp.add_argument("--medium-dockq", type=float, default=0.49)
    sp.add_argument("--high-dockq", type=float, default=0.80)
    sp.add_argument("--bootstrap-iterations", type=int, default=1000)
    sp.add_argument("--bootstrap-seed", type=int, default=20261002)
    sp.add_argument("--min-pairs-for-correlation", type=int, default=3)
    sp.set_defaults(func=cmd_v5_native_benchmark_calibration)

    sp = sub.add_parser("v5-native-release-dossier")
    sp.add_argument("--calibration", default="")
    sp.add_argument("--mechanics-validation", default="")
    sp.add_argument("--release-gate", default="")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--min-targets", type=int, default=20)
    sp.add_argument("--min-ranked-targets", type=int, default=10)
    sp.add_argument("--min-top5-acceptable-rate", type=float, default=0.50)
    sp.add_argument("--min-score-structure-pairs", type=int, default=30)
    sp.add_argument("--allow-no-holdout", action="store_true")
    sp.add_argument("--allow-missing-mechanics-validation", action="store_true")
    sp.set_defaults(func=cmd_v5_native_release_dossier)


    sp = sub.add_parser("v5-native-validation-finalize")
    sp.add_argument("--benchmarks-root", required=True)
    sp.add_argument("--mechanics-validation", default="")
    sp.add_argument("--release-gate", default="")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--bootstrap-iterations", type=int, default=1000)
    sp.add_argument("--bootstrap-seed", type=int, default=20261002)
    sp.add_argument("--min-targets", type=int, default=20)
    sp.add_argument("--min-ranked-targets", type=int, default=10)
    sp.add_argument("--min-top5-acceptable-rate", type=float, default=0.50)
    sp.add_argument("--min-score-structure-pairs", type=int, default=30)
    sp.add_argument("--allow-no-holdout", action="store_true")
    sp.add_argument("--allow-missing-mechanics-validation", action="store_true")
    sp.set_defaults(func=cmd_v5_native_validation_finalize)

    sp = sub.add_parser("v5-native-result-interpret")
    sp.add_argument("--docking-result", required=True, help="Shared docking-result contract JSON or folder")
    sp.add_argument("--followup", default="", help="Optional native follow-up contract JSON or folder")
    sp.add_argument("--pose-id", default="", help="Optional pose to interpret; defaults to top-ranked pose")
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_v5_native_result_interpret)

    sp = sub.add_parser("v5-native-validation-workspace")
    sp.add_argument("--root", required=True, help="Validation/benchmark workspace root to inspect")
    sp.add_argument("--output-dir", default="", help="Optional folder for JSON/Markdown workspace report")
    sp.set_defaults(func=cmd_v5_native_validation_workspace)


    sp = sub.add_parser("v5-final-release-audit")
    sp.add_argument("--root-dir", default=".", help="Pepforge package root")
    sp.add_argument("--output-dir", required=True, help="Audit/report output directory")
    sp.set_defaults(func=cmd_v5_final_release_audit)

    sp = sub.add_parser("v5-native-mechanics-validate")
    sp.add_argument("--pdb", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--fd-h", type=float, default=1e-5)
    sp.add_argument("--max-coordinates", type=int, default=48)
    sp.add_argument("--abs-tolerance", type=float, default=2e-4)
    sp.add_argument("--rel-tolerance", type=float, default=2e-4)
    sp.add_argument("--steps", type=int, default=40)
    sp.add_argument("--dt-reduced", type=float, default=0.0003)
    sp.add_argument("--max-score-ratio", type=float, default=25.0)
    sp.set_defaults(func=cmd_v5_native_mechanics_validate)

    sp = sub.add_parser("v5-native-validation-suite")
    sp.add_argument("--benchmarks-root", default="", help="Recursively discover native docking benchmark JSON files")
    sp.add_argument("--benchmarks", default="", help="Comma-separated benchmark summary JSON files")
    sp.add_argument("--mechanics-validation", default="")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--min-targets", type=int, default=20)
    sp.add_argument("--min-ranked-targets", type=int, default=10)
    sp.add_argument("--min-top5-acceptable-rate", type=float, default=0.50)
    sp.add_argument("--allow-missing-mechanics-validation", action="store_true")
    sp.set_defaults(func=cmd_v5_native_validation_suite)


    sp = sub.add_parser("v5-native-followup")
    sp.add_argument("--docking-result", required=True, help="Shared docking-result contract JSON or its folder")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--steps", type=int, default=400)
    sp.add_argument("--dt-reduced", type=float, default=0.0006)
    sp.add_argument("--damping", type=float, default=0.035)
    sp.add_argument("--save-every", type=int, default=40)
    sp.add_argument("--peptide-chain", default="P")
    sp.add_argument("--move-all", action="store_true", help="Allow receptor atoms to move in experimental native mechanics")
    sp.add_argument("--pass-only", action="store_true", help="Reject WARN docking poses; require PASS")
    sp.set_defaults(func=cmd_v5_native_followup)

    sp = sub.add_parser("v5-native-core-readiness")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--skip-smoke", action="store_true")
    sp.set_defaults(func=cmd_v5_native_core_readiness)

    sp = sub.add_parser("v5-psb-simulate")
    sp.add_argument("--psb-meta", required=True)
    sp.add_argument("--receptor", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--models", type=int, default=5)
    sp.add_argument("--poses", type=int, default=5)
    sp.add_argument("--binding-mode", choices=["blind","hotspot","manual"], default="blind")
    sp.add_argument("--binding-residues", default="")
    sp.add_argument("--preset", choices=["fast","standard","deep"], default="standard")
    sp.add_argument("--prepare-only", action="store_true")
    sp.add_argument("--skip-dockbench", action="store_true")
    sp.add_argument("--run-md", action="store_true")
    sp.add_argument("--run-native-followup", action="store_true", help="Run Pepforge Native Mechanics + Trajectory after native docking")
    sp.add_argument("--native-mechanics-steps", type=int, default=400)
    sp.add_argument("--md-pose-policy", choices=["top1_per_model","global_top1"], default="top1_per_model")
    sp.add_argument("--production-ns", type=float, default=1.0)
    sp.add_argument("--equilibration-ps", type=float, default=100.0)
    sp.add_argument("--replicates", type=int, default=3)
    sp.add_argument("--timeout", type=int, default=0)
    sp.add_argument("--haddock-executable", default="haddock3")
    sp.add_argument("--docking-backend", choices=["native","haddock3"], default="haddock3")
    sp.add_argument("--execution-mode", choices=["offline","auto","online_enhanced"], default="offline")
    sp.add_argument("--resource-root", default="")
    sp.set_defaults(func=cmd_v5_psb_simulate)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
