from __future__ import annotations
"""V6 evidence-aware scoring and external-backend agreement.

No score is interpreted as an affinity. Backend scores may have incompatible
scales/directions: only within-backend ranks across common candidate IDs are
combined. No experimental validation is implied.
"""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

PROTOCOL = '6.0.0-dev-assessment-1'

def _finite(value, field):
    try: number = float(value)
    except (TypeError, ValueError): raise ValueError(f'{field} must be numeric')
    if not math.isfinite(number): raise ValueError(f'{field} must be finite')
    return number

def assess_evidence(row: dict) -> dict:
    """Fail-closed triage of evidence, not a calibrated confidence probability."""
    flags=[]
    residue=(row.get('residue_status') or 'unknown').strip().lower()
    parameter=(row.get('parameter_status') or 'unknown').strip().lower()
    if residue not in ('standard','verified_modified'):
        flags.append('UNSUPPORTED_OR_UNVERIFIED_RESIDUE')
    if parameter != 'verified': flags.append('FORCEFIELD_PARAMETERS_NOT_VERIFIED')
    if (row.get('receptor_provenance') or '').strip().lower() not in ('pdb','experimental','predicted_documented'):
        flags.append('RECEPTOR_PROVENANCE_MISSING')
    if (row.get('pose_source') or '').strip().lower() not in ('executed_native','executed_external'):
        flags.append('EXECUTED_POSE_EVIDENCE_MISSING')
    if (row.get('benchmark_domain') or '').strip().lower() != 'in_domain_verified':
        flags.append('OUT_OF_DOMAIN_OR_UNVERIFIED')
    result={'candidate_id':str(row.get('candidate_id','')).strip(),
            'status':'REVIEW_REQUIRED' if flags else 'EVIDENCE_DOCUMENTED',
            'flags':flags,'calibrated_probability':None,
            'claim':'Evidence triage only; not experimental binding, affinity, or verified accuracy.'}
    if not result['candidate_id']:raise ValueError('candidate_id required')
    return result

def _rank(values: list[tuple[str,float]], higher_better: bool) -> dict[str,float]:
    ordered=sorted(values,key=lambda item:((-item[1] if higher_better else item[1]),item[0]))
    # tied values get midrank; return normalized [0,1] preference
    n=len(ordered)
    result={};index=0
    while index<n:
        end=index+1
        while end<n and ordered[end][1]==ordered[index][1]: end+=1
        mean_index=(index+end-1)/2
        desirability=1.0-mean_index/(n-1) if n>1 else 0.5
        for k in range(index,end):result[ordered[k][0]]=desirability
        index=end
    return result

def consensus_rank(rows: list[dict], *, minimum_backends: int=2) -> dict:
    """Each backend must score each identical candidate; missing values stop evaluation."""
    if minimum_backends<2:raise ValueError('minimum_backends must be >=2')
    pairs={}; by_backend=defaultdict(list);candidate_ids=set()
    for row in rows:
        candidate=str(row.get('candidate_id','')).strip();backend=str(row.get('backend','')).strip()
        direction=str(row.get('direction','')).strip().lower()
        if not candidate or not backend:raise ValueError('candidate_id and backend required')
        if direction not in ('higher','lower'):raise ValueError('direction must be higher or lower')
        key=(backend,candidate)
        if key in pairs:raise ValueError(f'duplicate backend/candidate: {key}')
        number=_finite(row.get('score'),'score')
        pairs[key]=(number,direction);by_backend[backend].append((candidate,number));candidate_ids.add(candidate)
    if len(by_backend)<minimum_backends:raise ValueError('not enough independent backends')
    if len(candidate_ids)<2:raise ValueError('at least two candidates required')
    for backend,values in by_backend.items():
        if {c for c,_ in values} !=candidate_ids:raise ValueError(f'incomplete candidate coverage: {backend}')
        if len({pairs[(backend,c)][1] for c in candidate_ids})!=1:raise ValueError('inconsistent score direction')
    backend_rank={b:_rank(vals,pairs[(b,vals[0][0])][1]=='higher') for b,vals in by_backend.items()}
    output=[]
    for candidate in sorted(candidate_ids):
        scores=[backend_rank[b][candidate] for b in sorted(backend_rank)]
        mean=sum(scores)/len(scores)
        spread=max(scores)-min(scores)
        output.append({'candidate_id':candidate,'consensus_rank_score':round(mean,6),
                       'backend_rank_spread':round(spread,6),
                       'agreement':'DISAGREEMENT' if spread>0.5 else 'RANK_AGREEMENT',
                       'backend_normalized_ranks':{b:round(backend_rank[b][candidate],6) for b in sorted(backend_rank)}})
    output.sort(key=lambda x:(-x['consensus_rank_score'],x['candidate_id']))
    return {'protocol':PROTOCOL,'status':'RANK_AGGREGATION_ONLY',
            'claim':'Uncalibrated cross-backend rank consensus; not ΔG, Kd or experimental affinity.',
            'backends':sorted(by_backend),'candidate_count':len(candidate_ids),'results':output}

def run_assessment(input_csv,output_json, *, mode):
    source=Path(input_csv)
    with source.open(encoding='utf-8-sig',newline='') as handle: rows=list(csv.DictReader(handle))
    if not rows:raise ValueError('empty input CSV')
    if mode=='evidence': result={'protocol':PROTOCOL,'results':[assess_evidence(row) for row in rows]}
    elif mode=='consensus':result=consensus_rank(rows)
    else:raise ValueError('unknown assessment mode')
    result['input_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result
