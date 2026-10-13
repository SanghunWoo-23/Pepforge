from __future__ import annotations

"""Leakage-aware tuning/evaluation for Pepforge Native Docking scoring weights.

The tuner consumes prepared public benchmark target folders created by
public_peptide_benchmark_v1. It tunes ONLY on targets marked train in a registry
CSV and evaluates the selected configuration on holdout targets separately.
"""

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
import csv, json, itertools, statistics

from .native_docking_v1 import NativeDockingConfig, run_native_docking
from .native_docking_benchmark_v1 import DockingBenchmarkConfig, benchmark_model_set
from .public_benchmark_leakage_v1 import audit_public_benchmark_split

NATIVE_DOCKING_TUNING_VERSION='0.1.0'


def _registry_rows(path: str|Path) -> list[dict[str,str]]:
    with Path(path).open('r',encoding='utf-8-sig',newline='') as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _target_paths(prepared_root: Path, target_id: str, *, prefer_unbound: bool=True) -> tuple[Path,Path,Path]:
    base=prepared_root/target_id/'prepared'
    ref=base/'reference_complex_A_P.pdb'
    rec=(base/'receptor_unbound_A.pdb') if prefer_unbound and (base/'receptor_unbound_A.pdb').exists() else base/'receptor_bound_A.pdb'
    pep=base/'peptide_bound_P.pdb'
    for p in (ref,rec,pep):
        if not p.exists(): raise FileNotFoundError(str(p))
    return ref,rec,pep


def _score_one(target_id: str, prepared_root: Path, out: Path, cfg: NativeDockingConfig, *, prefer_unbound: bool) -> dict[str,Any]:
    ref,rec,pep=_target_paths(prepared_root,target_id,prefer_unbound=prefer_unbound)
    dock_dir=out/target_id/'dock'
    dock=run_native_docking(rec,pep,dock_dir,config=cfg)
    poses=[p.get('pose_pdb') for p in dock.get('poses',[]) if p.get('pose_pdb')]
    score_csv=dock_dir/'native_pose_ranking.csv'
    bench=benchmark_model_set(ref,poses,out/target_id/'benchmark',config=DockingBenchmarkConfig(receptor_chain='A',ligand_chain='P'),score_csv=score_csv)
    return {'target_id':target_id,'dock_status':dock.get('status'),'selected_pose_count':len(poses),**{k:v for k,v in bench.items() if k in {'best_dockq_compatible','top1_by_internal_score_dockq','best_top5_by_internal_score_dockq','score_dockq_spearman','class_counts'}}}


def _aggregate(rows: list[dict[str,Any]]) -> dict[str,Any]:
    vals=[float(r['top1_by_internal_score_dockq']) for r in rows if r.get('top1_by_internal_score_dockq') is not None]
    top5=[float(r['best_top5_by_internal_score_dockq']) for r in rows if r.get('best_top5_by_internal_score_dockq') is not None]
    best=[float(r['best_dockq_compatible']) for r in rows if r.get('best_dockq_compatible') is not None]
    acceptable=sum(1 for x in vals if x>=0.23)
    return {'targets_evaluated':len(rows),'targets_ranked':len(vals),'mean_top1_dockq':statistics.fmean(vals) if vals else None,'median_top1_dockq':statistics.median(vals) if vals else None,
            'top1_acceptable_rate':acceptable/len(vals) if vals else None,'mean_best_top5_dockq':statistics.fmean(top5) if top5 else None,'mean_best_sampled_dockq':statistics.fmean(best) if best else None}


def tune_native_docking(registry_csv: str|Path, prepared_root: str|Path, output_dir: str|Path, *, base_config: NativeDockingConfig|None=None,
                       clash_penalties=(20.0,25.0,30.0), smooth_contact_weights=(0.06,0.08,0.10), interaction_scales=(0.75,1.0,1.25),
                       prefer_unbound: bool=True, max_train_targets: int|None=None, max_holdout_targets: int|None=None) -> dict[str,Any]:
    root=Path(prepared_root).expanduser().resolve(); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    rows=_registry_rows(registry_csv)
    train=[r for r in rows if (r.get('split') or '').lower()=='train' and (root/(r.get('target_id') or '')/'prepared').exists()]
    hold=[r for r in rows if (r.get('split') or '').lower()=='holdout' and (root/(r.get('target_id') or '')/'prepared').exists()]
    if max_train_targets: train=train[:max_train_targets]
    if max_holdout_targets: hold=hold[:max_holdout_targets]
    if not train: raise ValueError('No prepared train targets are available; sync public benchmark targets first.')
    base=base_config or NativeDockingConfig(poses=10,anchor_count=16,rotations_per_anchor=24,max_candidates=600)
    trials=[]
    for ti,(cp,sw,isc) in enumerate(itertools.product(clash_penalties,smooth_contact_weights,interaction_scales),start=1):
        cfg=replace(base,clash_penalty=float(cp),smooth_contact_weight=float(sw),interaction_score_scale=float(isc))
        case_rows=[]; errs=[]
        for r in train:
            tid=r['target_id']
            try: case_rows.append(_score_one(tid,root,out/'train_trials'/f'trial_{ti:03d}',cfg,prefer_unbound=prefer_unbound))
            except Exception as exc: errs.append({'target_id':tid,'error':str(exc)})
        agg=_aggregate(case_rows)
        objective=(agg.get('mean_top1_dockq') or -1.0) + 0.35*(agg.get('top1_acceptable_rate') or 0.0) + 0.15*(agg.get('mean_best_top5_dockq') or 0.0)
        trials.append({'trial':ti,'config':asdict(cfg),'objective':objective,'train':agg,'errors':errs})
    trials.sort(key=lambda x:(x['objective'],x['train'].get('mean_top1_dockq') or -1),reverse=True)
    best=trials[0]; best_cfg=NativeDockingConfig(**best['config'])
    hold_rows=[]; hold_errors=[]
    for r in hold:
        try: hold_rows.append(_score_one(r['target_id'],root,out/'holdout_best',best_cfg,prefer_unbound=prefer_unbound))
        except Exception as exc: hold_errors.append({'target_id':r['target_id'],'error':str(exc)})
    split_audit=audit_public_benchmark_split(registry_csv, root, out/'split_audit')
    payload={'version':NATIVE_DOCKING_TUNING_VERSION,'status':'COMPLETED','registry':str(Path(registry_csv).resolve()),'prepared_root':str(root),'prefer_unbound':prefer_unbound,
             'train_target_ids':[r['target_id'] for r in train],'holdout_target_ids':[r['target_id'] for r in hold], 'trial_count':len(trials),'best_trial':best,
             'holdout':_aggregate(hold_rows),'holdout_rows':hold_rows,'holdout_errors':hold_errors,'split_audit':split_audit,
             'generalization_claim_status':'BLOCKED' if split_audit.get('sequence_identity_threshold_independence')!='PASS' else 'ELIGIBLE_FOR_REVIEW',
             'promotion_guard':'Selected weights are development calibration only. Exact-duplicate leakage is audited, but generalization remains blocked until an explicitly sequence-identity-controlled independent holdout is evaluated.'}
    (out/'native_docking_tuning.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'native_docking_best_config.json').write_text(json.dumps(best['config'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'native_docking_tuning_trials.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        f=['trial','objective','clash_penalty','smooth_contact_weight','interaction_score_scale','train_targets','mean_top1_dockq','top1_acceptable_rate','mean_best_top5_dockq']
        w=csv.DictWriter(fh,fieldnames=f); w.writeheader()
        for t in trials:
            c=t['config']; a=t['train']; w.writerow({'trial':t['trial'],'objective':t['objective'],'clash_penalty':c['clash_penalty'],'smooth_contact_weight':c['smooth_contact_weight'],'interaction_score_scale':c['interaction_score_scale'],'train_targets':a['targets_evaluated'],'mean_top1_dockq':a['mean_top1_dockq'],'top1_acceptable_rate':a['top1_acceptable_rate'],'mean_best_top5_dockq':a['mean_best_top5_dockq']})
    return payload

__all__=['NATIVE_DOCKING_TUNING_VERSION','tune_native_docking']
