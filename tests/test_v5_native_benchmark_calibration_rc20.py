from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from peptiforg_core.native_benchmark_calibration_v1 import CalibrationPolicy, calibrate_benchmark_results
from peptiforg_core.native_release_dossier_v1 import ReleaseDossierPolicy, build_release_dossier


def _target(root: Path, name: str, split: str, vals: list[tuple[float,float]]):
    d=root/name; d.mkdir(parents=True)
    rows=[]
    for i,(score,dq) in enumerate(vals, start=1):
        rows.append({"model_name":f"pose_{i}.pdb","internal_score":score,"dockq_compatible":dq,"ligand_residue_count":6})
    csvp=d/'native_docking_reference_benchmark.csv'; pd.DataFrame(rows).to_csv(csvp,index=False)
    ranked=sorted(rows,key=lambda x:x['internal_score'])
    payload={
        "benchmark_csv":str(csvp),"models_evaluated":len(rows),
        "best_dockq_compatible":max(x['dockq_compatible'] for x in rows),
        "top1_by_internal_score_dockq":ranked[0]['dockq_compatible'],
        "best_top5_by_internal_score_dockq":max(x['dockq_compatible'] for x in ranked[:5]),
        "score_dockq_spearman":1.0,
        "dataset_target":{"target_id":name,"split":split,"source":"synthetic test fixture","experimental_id":name,"reference_sha256":name*8},
    }
    p=d/'native_docking_reference_benchmark.json'; p.write_text(json.dumps(payload))
    return p


def test_calibration_is_split_aware_and_deterministic(tmp_path):
    a=_target(tmp_path,'T1','train',[(-3,0.80),(-2,0.40),(-1,0.10)])
    b=_target(tmp_path,'T2','test',[(-3,0.60),(-2,0.30),(-1,0.05)])
    pol=CalibrationPolicy(bootstrap_iterations=100, bootstrap_seed=7)
    r=calibrate_benchmark_results([a,b],tmp_path/'out',policy=pol)
    assert r['status']=='CALIBRATION_REPORT_READY'
    assert r['targets']==2
    assert r['has_test_or_holdout_split'] is True
    assert {x['split'] for x in r['split_summaries']}=={'ALL','train','test'}
    assert r['global_pose_score_vs_structure_spearman'] > 0.9
    assert Path(r['targets_csv']).is_file()


def test_calibration_empty_is_explicit(tmp_path):
    r=calibrate_benchmark_results([],tmp_path/'out')
    assert r['status']=='NO_BENCHMARK_EVIDENCE'
    assert r['targets']==0
    assert r['global_pose_score_vs_structure_spearman'] is None


def test_release_dossier_does_not_promote_without_external_evidence(tmp_path):
    gate=tmp_path/'gate.json'; gate.write_text(json.dumps({'status':'PASS'}))
    r=build_release_dossier(tmp_path/'out',release_gate_json=gate)
    assert r['status']=='V5_CODE_COMPLETE_EXTERNAL_SCIENTIFIC_VALIDATION_PENDING'
    assert r['software_code_complete'] is True
    assert r['scientific_promotion_gate_pass'] is False


def test_release_dossier_can_pass_internal_research_gate_with_complete_evidence(tmp_path):
    cal=tmp_path/'cal.json'; cal.write_text(json.dumps({
        'targets':2,'has_test_or_holdout_split':True,'global_pose_score_vs_structure_pairs':6,
        'split_summaries':[{'split':'ALL','ranked_targets':2,'top5_acceptable':{'estimate':1.0}}]
    }))
    mech=tmp_path/'mech.json'; mech.write_text(json.dumps({'status':'PASS'}))
    gate=tmp_path/'gate.json'; gate.write_text(json.dumps({'status':'PASS'}))
    pol=ReleaseDossierPolicy(min_external_targets=2,min_ranked_targets=2,min_top5_acceptable_rate=.5,require_score_structure_pairs=6)
    r=build_release_dossier(tmp_path/'out',calibration_json=cal,mechanics_validation_json=mech,release_gate_json=gate,policy=pol)
    assert r['status']=='V5_NATIVE_RESEARCH_PROMOTION_GATE_PASS'
    assert r['scientific_promotion_gate_pass'] is True
    assert 'clinical utility' in r['claim_guard']


def test_finalize_orchestrates_calibration_and_dossier(tmp_path):
    from peptiforg_core.native_validation_finalize_v1 import finalize_native_validation
    a=_target(tmp_path/'bench','T1','test',[(-3,0.8),(-2,0.4),(-1,0.1)])
    gate=tmp_path/'gate.json'; gate.write_text(json.dumps({'passed':25,'failed':0}))
    r=finalize_native_validation(tmp_path/'bench',tmp_path/'final',release_gate_json=gate,
        dossier_policy=ReleaseDossierPolicy(min_external_targets=1,min_ranked_targets=1,require_score_structure_pairs=3,require_mechanics_numerical_pass=False))
    assert r['benchmark_summaries_discovered']==1
    assert r['software_code_complete'] is True
    assert r['scientific_promotion_gate_pass'] is True
