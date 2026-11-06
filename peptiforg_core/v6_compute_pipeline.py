"""V6 fail-closed execution bridge for existing native docking and OpenMM MD.

This is an auditable orchestration layer, not a novel binding-energy model.
No step is marked completed unless its engine returns and artifacts are checked.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Any
import hashlib
import json
import math
import time
import os
import tempfile
import shutil

SCHEMA = 'pepforge.v6.compute_pipeline.v1'

def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def _input(path: str | Path) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_file() or p.stat().st_size <= 0 or p.suffix.lower() != '.pdb':
        raise ValueError(f'Existing nonempty PDB required: {p}')
    from .interface_quality import parse_pdb_atoms
    from .native_docking_v1 import _validate_atoms
    atoms = _validate_atoms(parse_pdb_atoms(p), p.name)
    if not all(math.isfinite(float(v)) for v in atoms[['x','y','z']].to_numpy().flat):
        raise ValueError(f'Nonfinite PDB coordinates: {p}')
    return {'path':str(p), 'sha256':sha256(p), 'bytes':p.stat().st_size,
            'parsed_atom_count':len(atoms)}

def validate_native_config(cfg: Any) -> None:
    if not isinstance(cfg.mode, str) or cfg.mode.lower() not in {'blind', 'manual', 'hotspot'}:
        raise ValueError('Invalid docking mode')
    for name in ('poses','anchor_count','rotations_per_anchor','max_candidates'):
        v = getattr(cfg,name)
        if isinstance(v,bool) or not isinstance(v,int) or v < 1:
            raise ValueError(f'{name} must be a positive integer')
    for name in ('shell_distance_A','local_step_A','cluster_centroid_A'):
        v = getattr(cfg,name)
        if not math.isfinite(float(v)) or float(v) <= 0:
            raise ValueError(f'{name} must be finite and > 0')
    if isinstance(cfg.local_refine_steps, bool) or not isinstance(cfg.local_refine_steps, int) or cfg.local_refine_steps < 0 or cfg.local_refine_steps > 100:
        raise ValueError('local_refine_steps out of bounds')
    if isinstance(cfg.seed, bool) or not isinstance(cfg.seed, int) or cfg.seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    if cfg.max_candidates > 200000:
        raise ValueError('max_candidates exceeds safety limit')
    for name in ('clash_penalty','smooth_contact_weight','contact_count_weight','interaction_score_scale'):
        v = float(getattr(cfg,name))
        if not math.isfinite(v) or v < 0:
            raise ValueError(f'{name} must be finite and nonnegative')

def preflight(receptor_pdb: str | Path, peptide_pdb: str | Path, *, config: Any = None, md_protocol: Any = None) -> dict:
    from .native_docking_v1 import NativeDockingConfig
    from .openmm_md_backend import OpenMMProtocol, validate_protocol, detect_openmm
    config = config or NativeDockingConfig()
    md_protocol = md_protocol or OpenMMProtocol()
    validate_native_config(config)
    validate_protocol(md_protocol)
    rec, pep = _input(receptor_pdb), _input(peptide_pdb)
    if rec['path'] == pep['path']:
        raise ValueError('Receptor and peptide files must differ')
    return {'schema':SCHEMA, 'status':'PREFLIGHT_ONLY', 'inputs':{'receptor':rec,'peptide':pep},
            'native_config':asdict(config), 'md_protocol':asdict(md_protocol),
            'openmm_readiness':detect_openmm(),
            'claim_guard':'Preflight alone does not execute docking or MD, and scores are not affinities.'}

def run_pipeline(receptor_pdb: str | Path, peptide_pdb: str | Path, output_dir: str | Path,
                 *, config: Any = None, run_md: bool = False, md_protocol: Any = None, binding_residues=None, progress_callback=None) -> dict:
    """Run actual native docking, optionally OpenMM on the best *valid* returned pose.

    Output directory must be new to avoid replaying a stale success manifest.
    MD failures do not erase successful docking results; they are separately flagged.
    """
    from .native_docking_v1 import NativeDockingConfig, run_native_docking
    from .openmm_md_backend import OpenMMProtocol, run_openmm_replicates
    config = config or NativeDockingConfig()
    md_protocol = md_protocol or OpenMMProtocol()
    binding_residues = list(binding_residues or [])
    if config.mode in {'hotspot', 'manual'} and not binding_residues:
        raise ValueError(f'{config.mode} mode requires receptor binding residues')
    if progress_callback is not None:
        progress_callback(0.0, "Checking input structures")
    initial = preflight(receptor_pdb, peptide_pdb, config=config, md_protocol=md_protocol)
    if progress_callback is not None:
        progress_callback(0.05, "Inputs validated")
    out = Path(output_dir).expanduser().resolve()
    # Never let results overwrite an input or land within a symlinked output root.
    if out == Path(initial['inputs']['receptor']['path']) or out == Path(initial['inputs']['peptide']['path']):
        raise ValueError('Output directory must differ from both input files')
    raw_out = Path(output_dir).expanduser()
    if raw_out.is_symlink():
        raise ValueError('Output directory must not be a symbolic link')
    if out.exists() and not out.is_dir():
        raise NotADirectoryError(f'Output path is not a folder: {out}')
    if out == Path(out.anchor) or out in (Path.home().resolve(), Path.cwd().resolve()):
        raise ValueError('Output directory must not be a filesystem root, home, or working directory')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('Output folder must be empty: refusing to mix or overwrite results')
    out.mkdir(parents=True, exist_ok=True)
    report = dict(initial)
    report.update({'status':'RUNNING','started_utc_epoch':time.time(),'stages':{},'run_md_requested':bool(run_md)})
    report_path=out/'v6_compute_pipeline.json'
    report['manifest'] = str(report_path)
    def save():
        # Atomic replacement prevents a crash from leaving a truncated state JSON.
        content = json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n'
        fd, temp_name = tempfile.mkstemp(prefix='.v6_compute_', suffix='.tmp', dir=str(out))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, report_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    report['binding_residues'] = binding_residues
    from .v6_execution_devices import inspect_compute_devices
    report['device_capabilities'] = inspect_compute_devices()
    save()
    try:
        # Guard against a changed input between preflight and computation.
        for item in initial['inputs'].values():
            if sha256(item['path']) != item['sha256']:
                raise RuntimeError(f'Input changed since preflight: {item["path"]}')
        # Pin the exact input bytes in this run; calculations never read mutable source paths.
        snapshots=out/'input_snapshots'
        snapshots.mkdir(exist_ok=False)
        source_paths=[]
        for role in ('receptor','peptide'):
            record=initial['inputs'][role]
            source=Path(record['path'])
            target=snapshots/f'{role}.pdb'
            with source.open('rb') as infile, target.open('xb') as outfile:
                shutil.copyfileobj(infile,outfile)
                outfile.flush()
                os.fsync(outfile.fileno())
            if sha256(target)!=record['sha256']:
                raise RuntimeError(f'Input changed during snapshot: {role}')
            source_paths.append(target)
        report['input_snapshots']={role:{'path':str(path),'sha256':sha256(path)}
            for role,path in zip(('receptor','peptide'),source_paths)}
        save()
        if progress_callback is not None:
            progress_callback(0.10, "Starting native pose search")
        search_progress = (lambda fraction, label: progress_callback(0.10 + 0.75 * max(0.0, min(1.0, fraction)), label)) if progress_callback is not None else None
        result=run_native_docking(source_paths[0],source_paths[1],out/'native_docking',config=config,binding_residues=binding_residues,progress_callback=search_progress)
        if progress_callback is not None:
            progress_callback(0.88, "Checking exported poses")
        rows=result.get('poses',result.get('pose_rows',[]))
        if not isinstance(rows,list): rows=[]
        # Trust only artifacts whose paths point to files created in this run.
        candidates=[]
        seen_paths=set()
        for row in rows:
            if not isinstance(row, dict) or not row.get('pose_pdb'):
                continue
            p=Path(str(row['pose_pdb'])).resolve()
            if p.is_file() and p.is_relative_to((out/'native_docking').resolve()) and p.suffix.lower()=='.pdb' and p.stat().st_size and p not in seen_paths:
                seen_paths.add(p)
                # Reject a pose whose PDB contents do not contain any parseable atoms.
                try:
                    _input(p)
                except (ValueError, OSError):
                    continue
                candidates.append({'pose_pdb':str(p),'sha256':sha256(p), 'rank':row.get('rank'),
                    'quality_gate':row.get('quality_gate')})
        expected = result.get('selected_pose_count')
        artifact_count_ok = (expected is None or (type(expected) is int and expected == len(candidates)))
        report['stages']['native_docking']={'engine_status':result.get('status'),'status':'COMPLETED' if result.get('status')=='COMPLETED' and candidates and artifact_count_ok else 'NO_VERIFIED_POSE','pose_artifacts':candidates, 'reported_pose_count':expected, 'verified_pose_count':len(candidates)}
        if report['stages']['native_docking']['status']!='COMPLETED':
            report['status']='NO_VERIFIED_POSE';save();return report
        if run_md:
            if progress_callback is not None:
                progress_callback(0.92, "Native poses verified; MD running (duration unknown)")
            # Never automatically propagate a quality-gate FAIL pose to MD.
            valid=[p for p in candidates if isinstance(p.get('quality_gate'),dict) and p['quality_gate'].get('status') in {'PASS','WARN'}]
            if not valid:
                report['stages']['production_md']={'status':'BLOCKED_NO_ACCEPTABLE_POSE'}
                report['status']='MD_BLOCKED_QUALITY_GATE';save();return report
            best=valid[0]
            if sha256(best['pose_pdb']) != best['sha256']:
                raise RuntimeError('Docking pose changed before MD')
            try:
                md=run_openmm_replicates(best['pose_pdb'],out/'production_md',protocol=md_protocol)
            except Exception as md_exc:
                report['stages']['production_md']={'status':'FAILED',
                    'input_pose_sha256':best['sha256'],
                    'error':f'{type(md_exc).__name__}: {md_exc}'}
                report['status']='MD_FAILED_DOCKING_COMPLETED'
                return report
            report['stages']['production_md']={'status':md.get('status','UNKNOWN'),'input_pose_sha256':best['sha256'],
                'replicate_statuses':[r.get('status') for r in md.get('replicate_results',[])]}
            report['status']='COMPLETED' if md.get('status')=='COMPLETED' else 'MD_NOT_COMPLETED'
        else:
            report['stages']['production_md']={'status':'NOT_REQUESTED'}
            report['status']='DOCKING_COMPLETED_MD_NOT_REQUESTED'
    except Exception as exc:
        report['status']='FAILED';report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        report['finished_utc_epoch']=time.time()
        save()
        if progress_callback is not None:
            progress_callback(1.0 if report['status'] in {'COMPLETED', 'DOCKING_COMPLETED_MD_NOT_REQUESTED'} else 0.0, f"Final status: {report['status']}")
    return report
