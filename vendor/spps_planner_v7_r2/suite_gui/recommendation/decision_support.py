"""SPPS Planner V5 evidence-driven decision-support helpers.

V5 deliberately separates observed history, bounded interpolation and chemistry/risk
rules. No function in this module mutates a synthesis plan.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from suite_gui import experimental_data


def _num(value: Any) -> float | None:
    try:
        number=float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _sequence_match(observed: Any, current: Any) -> bool:
    a=experimental_data.sequence_signature(observed); b=experimental_data.sequence_signature(current)
    if not a or not b:
        return experimental_data.canonical_sequence_key(observed)==experimental_data.canonical_sequence_key(current)
    an,at,ac=a; bn,bt,bc=b
    if an!=bn or at!=bt: return False
    return not (ac and bc and ac!=bc)


def _composition(row: Mapping[str,Any]) -> dict[str,float]:
    try:
        parsed=json.loads(str(row.get('composition_pct_json') or '{}'))
    except Exception:
        parsed={}
    return {str(k):float(v) for k,v in parsed.items() if _num(v) is not None and float(v)>0} if isinstance(parsed,dict) else {}


def _dedupe_usage(rows: Iterable[Mapping[str,Any]]) -> list[dict[str,Any]]:
    """Keep one provenance row per independent synthesis key.

    Single-product sheets outrank aggregate copies; Verified outranks Parsed. This
    avoids counting integrated monthly copies as independent experiments.
    """
    chosen: dict[str,dict[str,Any]]={}
    def rank(row: Mapping[str,Any]) -> tuple[int,int,int]:
        return (
            1 if str(row.get('status'))=='verified' else 0,
            1 if str(row.get('record_scope'))=='single' else 0,
            1 if not int(row.get('unit_review_required') or 0) else 0,
        )
    for i,raw in enumerate(rows):
        row=dict(raw)
        key=str(row.get('synthesis_key') or '').strip() or f"record:{row.get('record_id') or i}"
        if key not in chosen or rank(row)>rank(chosen[key]): chosen[key]=row
    return list(chosen.values())


def cleavage_amount_recommendation(*,product:str='',sequence:str='',scale_mmol:Any=None,db_path:str|Path|None=None,include_parsed:bool=True)->dict[str,Any]:
    """Rank observed cleavage-volume and precipitation/workup evidence.

    Only single-product, unit-resolved observations may drive automatic scaling.
    Aggregate sheets remain visible as reference evidence. Cocktail identity and
    workup solvent are learned independently; neither is synthesized by combining
    unrelated records.
    """
    statuses=['verified']+(['parsed'] if include_parsed else [])
    rows=_dedupe_usage(experimental_data.list_records('cleavage_usage',db_path,statuses=statuses))
    seq=str(sequence or '').strip(); pkey=experimental_data.canonical_product_key(product); target=_num(scale_mmol)
    matched=[]; aggregate_reference=[]; unresolved=[]
    for row in rows:
        seq_ok=bool(seq and row.get('sequence') and _sequence_match(row.get('sequence'),seq))
        prod_ok=bool(pkey and experimental_data.canonical_product_key(row.get('product'))==pkey)
        if seq and not seq_ok and not prod_ok: continue
        if not seq and pkey and not prod_ok: continue
        r=dict(row); r['sequence_match']=seq_ok; r['product_match']=prod_ok
        if str(r.get('record_scope') or 'single').lower()!='single':
            aggregate_reference.append(r); continue
        matched.append(r)

    # Workup evidence is independent of whether the cocktail amount is complete.
    workup_candidates=[]
    for solvent,field in [('Ethyl Ether','ether_ml_per_mmol'),('n-Hexane','hexane_ml_per_mmol')]:
        group=[r for r in matched if _num(r.get(field)) is not None and _num(r.get('scale_mmol')) is not None]
        if not group: continue
        scales=[float(r['scale_mmol']) for r in group]; per=[float(r[field]) for r in group]
        exact=[r for r in group if target is not None and abs(float(r.get('scale_mmol') or 0)-target)<=max(1e-9,target*0.001)]
        within=bool(target is not None and min(scales)<=target<=max(scales)); repeated=len(group)>=2
        median_per=sorted(per)[len(per)//2]; scaled=None; kind='OBSERVED WORKUP CANDIDATE'
        if exact:
            chosen=sorted(exact,key=lambda r:(0 if r.get('status')=='verified' else 1))[0]
            ml_key='ether_ml' if solvent=='Ethyl Ether' else 'hexane_ml'
            scaled=_num(chosen.get(ml_key)); kind='HISTORICAL EXACT SCALE'
        elif repeated and within:
            scaled=median_per*target; kind='BOUNDED MODEL INTERPOLATION'
        quality=sum(4 if r.get('sequence_match') else 0 for r in group)+sum(3 if r.get('product_match') else 0 for r in group)+sum(2 if r.get('status')=='verified' else 0 for r in group)+len(group)
        workup_candidates.append({'solvent':solvent,'scaled_workup_ml':scaled,'workup_ml_per_mmol_median':median_per,'observed_scale_min_mmol':min(scales),'observed_scale_max_mmol':max(scales),'independent_syntheses':len(group),'amount_kind':kind,'quality_rank':quality,'source_records':[r.get('record_id') for r in group]})
    workup_candidates.sort(key=lambda c:(c['scaled_workup_ml'] is not None,c['quality_rank'],c['independent_syntheses']),reverse=True)
    workup=workup_candidates[0] if workup_candidates else None

    normalized=[]
    for row in matched:
        if int(row.get('unit_review_required') or 0) or _num(row.get('cocktail_ml_per_mmol')) is None:
            unresolved.append(row); continue
        normalized.append(row)
    if not normalized:
        warnings=[]
        if unresolved: warnings.append(f"{len(unresolved)} matching material-usage record(s) exist but their cocktail units are unresolved; no mL/L value is guessed.")
        else: warnings.append('No normalized matching material-usage cocktail record is available.')
        if aggregate_reference: warnings.append(f"{len(aggregate_reference)} aggregate/multi-product record(s) are reference-only and excluded from auto-scaling.")
        return {'method':'observed cleavage-volume candidates','recommendation_kind':'INSUFFICIENT EVIDENCE','confidence':'LOW','recommended_amount':None,'recommended_workup':workup,'candidate_count':0,'unresolved_unit_count':len(unresolved),'aggregate_reference_count':len(aggregate_reference),'apply_allowed':False,'workup_apply_allowed':bool(workup and workup.get('scaled_workup_ml') is not None),'warnings':warnings,'evidence':unresolved[:20],'aggregate_reference':aggregate_reference[:20]}

    groups: dict[tuple[tuple[str,float],...],list[dict[str,Any]]]={}
    for row in normalized:
        comp=tuple(sorted((k,round(v,4)) for k,v in _composition(row).items()))
        groups.setdefault(comp,[]).append(row)
    candidates=[]
    for comp,group in groups.items():
        scales=[float(r['scale_mmol']) for r in group if _num(r.get('scale_mmol')) is not None]
        per=[float(r['cocktail_ml_per_mmol']) for r in group if _num(r.get('cocktail_ml_per_mmol')) is not None]
        if not scales or not per: continue
        median_per=sorted(per)[len(per)//2]
        exact_scale=[r for r in group if target is not None and abs(float(r.get('scale_mmol') or 0)-target)<=max(1e-9,target*0.001)]
        within=bool(target is not None and min(scales)<=target<=max(scales)); repeated=len(group)>=2
        scaled=None; amount_kind='OBSERVED CANDIDATE'
        if exact_scale:
            chosen_exact=sorted(exact_scale,key=lambda r:(0 if r.get('status')=='verified' else 1))[0]
            scaled=float(chosen_exact['cocktail_total_ml']); amount_kind='HISTORICAL EXACT SCALE'
        elif repeated and within:
            scaled=median_per*target; amount_kind='BOUNDED MODEL INTERPOLATION'
        quality=sum(3 if r.get('product_match') else 0 for r in group)+sum(4 if r.get('sequence_match') else 0 for r in group)+sum(2 if r.get('status')=='verified' else 0 for r in group)+len(group)
        candidates.append({'composition_pct':dict(comp),'independent_syntheses':len(group),'verified_count':sum(r.get('status')=='verified' for r in group),'observed_scale_min_mmol':min(scales),'observed_scale_max_mmol':max(scales),'observed_ml_per_mmol_median':median_per,'observed_ml_per_mmol_min':min(per),'observed_ml_per_mmol_max':max(per),'scaled_total_ml':scaled,'amount_kind':amount_kind,'within_observed_scale_range':within,'quality_rank':quality,'source_records':[r.get('record_id') for r in group],'source_products':sorted({str(r.get('product') or '') for r in group})})
    candidates.sort(key=lambda c:(c['scaled_total_ml'] is not None,c['quality_rank'],c['independent_syntheses'],c['verified_count']),reverse=True)
    chosen=candidates[0] if candidates else None
    if not chosen:
        return {'method':'observed cleavage-volume candidates','recommendation_kind':'INSUFFICIENT EVIDENCE','confidence':'LOW','recommended_amount':None,'recommended_workup':workup,'warnings':['No complete normalized cocktail candidate remains.'],'evidence':[],'aggregate_reference_count':len(aggregate_reference),'apply_allowed':False,'workup_apply_allowed':bool(workup and workup.get('scaled_workup_ml') is not None)}
    actionable=bool(chosen['scaled_total_ml'] is not None)
    confidence='HIGH' if chosen['verified_count']>=2 and chosen['independent_syntheses']>=3 else 'MEDIUM' if chosen['independent_syntheses']>=2 or chosen['verified_count']>=1 else 'LOW'
    warnings=[]
    if target is None: warnings.append('Target scale is blank; observed per-mmol amounts are shown but no scaled amount is generated.')
    elif not actionable: warnings.append('Target scale lies outside the observed range and no exact-scale record exists; extrapolation is disabled.')
    if unresolved: warnings.append(f"{len(unresolved)} matching single-product record(s) are retained as raw evidence but excluded from normalized amount learning pending unit review.")
    if aggregate_reference: warnings.append(f"{len(aggregate_reference)} aggregate/multi-product record(s) are reference-only and excluded from auto-scaling.")
    if workup:
        chosen['workup_solvent']=workup.get('solvent'); chosen['scaled_workup_ml']=workup.get('scaled_workup_ml'); chosen['workup_amount_kind']=workup.get('amount_kind'); chosen['workup_independent_syntheses']=workup.get('independent_syntheses')
        if workup.get('solvent')=='Ethyl Ether': chosen['scaled_ether_ml']=workup.get('scaled_workup_ml')
    return {'method':'candidate-ranked observed cleavage-volume evidence','recommendation_kind':chosen['amount_kind'],'confidence':confidence,'recommended_amount':chosen,'recommended_workup':workup,'candidate_count':len(candidates),'unresolved_unit_count':len(unresolved),'aggregate_reference_count':len(aggregate_reference),'apply_allowed':actionable,'workup_apply_allowed':bool(workup and workup.get('scaled_workup_ml') is not None),'warnings':warnings,'evidence':candidates[:12],'aggregate_reference':aggregate_reference[:20]}

HYDROPHOBIC=set('AVILMFWY'); BETA=set('ITV'); BULKY=set('FWYPITV')

def sequence_difficulty_map(sequence: str) -> dict[str,Any]:
    """Return deterministic residue-level review scores, not failure probabilities."""
    try:
        from spps_planner.parser import parse_sequence
        parsed=parse_sequence(str(sequence or '')); tokens=list(parsed.core_tokens or [])
    except Exception as exc:
        return {'positions':[],'warnings':[str(exc)],'score_kind':'deterministic review score'}
    natural=[]
    for token in tokens:
        t=str(token); aa=(t[1:] if len(t)==2 and t.lower().startswith('d') else t).upper()
        natural.append(aa if len(aa)==1 and aa in set('ARNDCQEGHILKMFPSTWYV') else '')
    positions=[]
    for i,(token,aa) in enumerate(zip(tokens,natural),1):
        score=0; reasons=[]
        if aa in BETA or aa=='P': score+=20; reasons.append('steric/beta-branched or Pro')
        if not aa: score+=25; reasons.append('non-standard/modified core token')
        if aa=='C': score+=10; reasons.append('Cys protection/oxidation review')
        if aa in {'M','W'}: score+=8; reasons.append('oxidation-sensitive residue')
        if i<len(natural) and aa=='D' and natural[i] in {'G','N','S','T','C'}: score+=30; reasons.append('Aspartimide-prone motif start')
        left=max(0,i-3); right=min(len(natural),i+2); window=[x for x in natural[left:right] if x]
        if len(window)>=4 and sum(x in HYDROPHOBIC for x in window)>=4: score+=18; reasons.append('local hydrophobic cluster')
        if i<len(natural) and aa in BULKY and natural[i] in BULKY: score+=15; reasons.append('adjacent bulky pair')
        level='HIGH' if score>=45 else 'MEDIUM' if score>=25 else 'LOW' if score>0 else 'INFO'
        positions.append({'position':i,'token':str(token),'score':min(score,100),'level':level,'reasons':reasons})
    return {'positions':positions,'max_score':max([p['score'] for p in positions],default=0),'score_kind':'deterministic review score','warnings':list(getattr(parsed,'warnings',[]) or []),'apply_allowed':False}


def _edit_distance(a:tuple[str,...],b:tuple[str,...])->int:
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1): cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]


def similar_experiments(sequence:str,*,db_path:str|Path|None=None,limit:int=12)->list[dict[str,Any]]:
    current=experimental_data.sequence_signature(sequence)
    if not current: return []
    _,ctokens,_=current
    seq_rows=experimental_data.list_records('sequence',db_path,statuses=['verified','parsed'])
    outcome_rows=experimental_data.list_records('outcome',db_path,statuses=['verified','parsed'])
    outcomes:dict[str,list[dict[str,Any]]]={}
    for row in outcome_rows: outcomes.setdefault(str(row.get('product_key') or ''),[]).append(row)
    best:dict[tuple[str,str],dict[str,Any]]={}
    for row in seq_rows:
        sig=experimental_data.sequence_signature(row.get('sequence'))
        if not sig: continue
        _,tokens,_=sig; denom=max(len(ctokens),len(tokens),1); sim=max(0.0,1.0-_edit_distance(ctokens,tokens)/denom)
        key=(str(row.get('product_key') or ''),experimental_data.canonical_sequence_key(row.get('sequence')))
        candidate={'product':row.get('product'),'sequence':row.get('sequence'),'similarity':sim,'status':row.get('status'),'source_file':row.get('source_file'),'source_page':row.get('source_page'),'outcomes':outcomes.get(str(row.get('product_key') or ''),[])[:4]}
        if key not in best or sim>best[key]['similarity']: best[key]=candidate
    return sorted(best.values(),key=lambda r:r['similarity'],reverse=True)[:limit]


def validation_snapshot(db_path:str|Path|None=None)->dict[str,Any]:
    health=experimental_data.data_health(db_path)
    usage=experimental_data.list_records('cleavage_usage',db_path,statuses=['verified','parsed'])
    complete=[r for r in _dedupe_usage(usage) if not int(r.get('unit_review_required') or 0) and _num(r.get('cocktail_ml_per_mmol')) is not None]
    # Leave-one-out absolute error within exact product+composition groups, bounded to observed evidence.
    groups:dict[tuple[str,str],list[float]]={}
    for row in complete:
        comp=json.dumps(_composition(row),sort_keys=True); key=(str(row.get('product_key') or ''),comp)
        groups.setdefault(key,[]).append(float(row['cocktail_ml_per_mmol']))
    errors=[]
    for vals in groups.values():
        if len(vals)<2: continue
        for i,obs in enumerate(vals):
            peers=vals[:i]+vals[i+1:]; pred=sorted(peers)[len(peers)//2]; errors.append(abs(obs-pred))
    return {
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'schema_version':experimental_data.SCHEMA_VERSION,
        'data_health':health,'cleavage_amount_leave_one_out_mae_ml_per_mmol':(sum(errors)/len(errors) if errors else None),
        'cleavage_amount_leave_one_out_evaluated':len(errors),'normalized_independent_cleavage_usage_runs':len(complete),
        'note':'Retrospective consistency snapshot; not a biochemical success probability.',
    }


def _max_level(levels: Iterable[str]) -> str:
    order={'INFO':0,'LOW':1,'WARNING':2,'MEDIUM':3,'HIGH':4,'CRITICAL':5}
    return max((str(v or 'INFO').upper() for v in levels), key=lambda v:order.get(v,0), default='INFO')


def stage_risk_advisor(*, sequence:str='', product:str='', resin:str='', scale_mmol:Any=None,
                       selected_plan_rows:Iterable[Mapping[str,Any]]|None=None,
                       db_path:str|Path|None=None)->dict[str,Any]:
    """Summarize Loading/Coupling/Cleavage review risks without generating chemistry.

    The stage levels combine deterministic sequence/plan flags with the presence or
    absence of reviewed historical evidence. They are triage labels, not probabilities.
    """
    seq=str(sequence or '').strip(); rows=list(selected_plan_rows or [])
    try:
        from suite_gui import risk_engine
        rule_report=risk_engine.evaluate_rules({'sequence':seq,'selected_plan_rows':rows,'runs':[]})
        findings=list(rule_report.get('findings') or [])
    except Exception as exc:
        rule_report={'findings':[],'parser_warnings':[str(exc)]}; findings=[]

    # Loading evidence is matched to the actual resin and C-terminal residue.  No
    # protecting group is guessed when the parser cannot resolve a usable token.
    loading_rows=experimental_data.list_records('loading',db_path,statuses=['verified','parsed'])
    exact_loading=[]; cterm=''
    try:
        from spps_planner.parser import parse_sequence
        parsed=parse_sequence(seq); tokens=list(parsed.core_tokens or [])
        cterm=str(tokens[-1]) if tokens else ''
    except Exception:
        cterm=''
    if resin and cterm:
        rkey=experimental_data.canonical_resin_key(resin)
        akey=experimental_data.canonical_amino_acid_key(cterm)
        exact_loading=[r for r in loading_rows if experimental_data.canonical_resin_key(r.get('resin_type'))==rkey and experimental_data.canonical_amino_acid_key(r.get('amino_acid_normalized') or r.get('amino_acid_raw'))==akey]
    loading_reasons=[]
    if not seq: loading_reasons.append('Sequence is blank; C-terminal loading evidence cannot be matched.')
    elif not resin: loading_reasons.append('Resin is blank; loading evidence cannot be matched.')
    elif not exact_loading: loading_reasons.append('No exact resin + C-terminal building-block loading history was found.')
    else: loading_reasons.append(f'{len(exact_loading)} exact loading history record(s) matched the current resin + C-terminal building block.')
    loading_level='WARNING' if not exact_loading and seq and resin else 'INFO'

    # Coupling risks reuse the established transparent rule engine plus recorded
    # coupling outcomes for the same canonical sequence.
    coupling_findings=[f for f in findings if str(f.get('category')) in {'Coupling','Aggregation','Side reaction','Plan'}]
    outcomes=experimental_data.list_records('outcome',db_path,statuses=['verified','parsed'])
    skey=experimental_data.canonical_sequence_key(seq)
    coupling_outcomes=[o for o in outcomes if str(o.get('stage') or '').lower()=='coupling' and skey and experimental_data.canonical_sequence_key(o.get('sequence'))==skey]
    coupling_fail=sum(1 for o in coupling_outcomes if o.get('success_flag')==0)
    coupling_reasons=[f"{f.get('title')}: {f.get('evidence')}" for f in coupling_findings[:8]]
    if coupling_outcomes: coupling_reasons.append(f'{len(coupling_outcomes)} recorded coupling outcome(s) for this sequence; failures={coupling_fail}.')
    else: coupling_reasons.append('No recorded coupling outcome exists for this exact sequence.')
    coupling_level=_max_level([f.get('severity','INFO') for f in coupling_findings]+(['HIGH'] if coupling_fail else []))

    # Structured synthesis issues are operator-entered process evidence.  They are
    # shown in risk review but never automatically converted into chemistry changes.
    issue_rows=experimental_data.list_records('issue',db_path,statuses=['verified'])
    matching_issues=[]
    for issue in issue_rows:
        seq_ok=bool(skey and experimental_data.canonical_sequence_key(issue.get('sequence'))==skey)
        prod_ok=bool(experimental_data.canonical_product_key(product) and experimental_data.canonical_product_key(issue.get('product'))==experimental_data.canonical_product_key(product))
        if seq_ok or prod_ok:
            matching_issues.append(issue)

    def issue_summary(stage_name:str)->tuple[list[dict[str,Any]],list[str],list[str]]:
        aliases={
            'Loading':{'loading','swelling'},
            'Coupling':{'coupling','deprotection','modification'},
            'Cleavage':{'cleavage','precipitation / workup','purification'},
        }
        allowed=aliases.get(stage_name,{stage_name.lower()})
        rows=[r for r in matching_issues if str(r.get('stage') or '').strip().lower() in allowed]
        reasons=[]; levels=[]
        if rows:
            counts=Counter(str(r.get('issue_type') or 'Other') for r in rows)
            top=', '.join(f"{name}×{count}" for name,count in counts.most_common(4))
            unresolved=sum(str(r.get('resolution') or '').lower() not in {'resolved','improved'} for r in rows)
            reasons.append(f"{len(rows)} historical synthesis issue record(s): {top}; unresolved={unresolved}.")
            levels.extend(str(r.get('severity') or 'INFO').upper() for r in rows)
        return rows,reasons,levels

    loading_issues, loading_issue_reasons, loading_issue_levels = issue_summary('Loading')
    coupling_issues, coupling_issue_reasons, coupling_issue_levels = issue_summary('Coupling')
    cleavage_issues, cleavage_issue_reasons, cleavage_issue_levels = issue_summary('Cleavage')
    loading_reasons.extend(loading_issue_reasons)
    coupling_reasons.extend(coupling_issue_reasons)
    loading_level=_max_level([loading_level]+loading_issue_levels)
    coupling_level=_max_level([coupling_level]+coupling_issue_levels)

    # Cleavage review separates historical condition evidence from usage normalization.
    pkey=experimental_data.canonical_product_key(product)
    cleavage_rows=experimental_data.list_records('cleavage',db_path,statuses=['verified','parsed'])
    matched_cleavage=[]
    for row in cleavage_rows:
        seq_ok=bool(skey and experimental_data.canonical_sequence_key(row.get('sequence'))==skey)
        prod_ok=bool(pkey and experimental_data.canonical_product_key(row.get('product'))==pkey)
        if seq_ok or prod_ok: matched_cleavage.append(row)
    usage=experimental_data.list_records('cleavage_usage',db_path,statuses=['verified','parsed'])
    matched_usage=[]
    for row in usage:
        seq_ok=bool(skey and experimental_data.canonical_sequence_key(row.get('sequence'))==skey)
        prod_ok=bool(pkey and experimental_data.canonical_product_key(row.get('product'))==pkey)
        if seq_ok or prod_ok: matched_usage.append(row)
    unresolved=sum(int(r.get('unit_review_required') or 0) for r in matched_usage)
    cleavage_findings=[f for f in findings if str(f.get('category')) in {'Oxidation / protection','Oxidation'}]
    cleavage_reasons=[f"{f.get('title')}: {f.get('evidence')}" for f in cleavage_findings[:8]]
    if matched_cleavage: cleavage_reasons.append(f'{len(matched_cleavage)} historical cleavage condition record(s) matched by sequence/product.')
    else: cleavage_reasons.append('No historical cleavage condition matched the current sequence/product.')
    if matched_usage: cleavage_reasons.append(f'{len(matched_usage)} material-usage record(s) matched; unresolved-unit records={unresolved}.')
    else: cleavage_reasons.append('No material-usage record matched the current sequence/product.')
    cleavage_reasons.extend(cleavage_issue_reasons)
    cleavage_levels=[f.get('severity','INFO') for f in cleavage_findings] + cleavage_issue_levels
    if unresolved: cleavage_levels.append('WARNING')
    if not matched_cleavage and seq: cleavage_levels.append('WARNING')
    cleavage_level=_max_level(cleavage_levels)

    stages=[
        {'stage':'Loading','level':loading_level,'evidence_count':len(exact_loading)+len(loading_issues),'reasons':loading_reasons,'apply_allowed':False},
        {'stage':'Coupling','level':coupling_level,'evidence_count':len(coupling_outcomes)+len(coupling_issues),'reasons':coupling_reasons,'apply_allowed':False},
        {'stage':'Cleavage','level':cleavage_level,'evidence_count':len(matched_cleavage)+len(matched_usage)+len(cleavage_issues),'reasons':cleavage_reasons,'apply_allowed':False},
    ]
    return {'stages':stages,'rule_report':rule_report,'issues':matching_issues,'risk_kind':'deterministic/evidence review; not failure probability','apply_allowed':False}


__all__=['cleavage_amount_recommendation','sequence_difficulty_map','similar_experiments','validation_snapshot','stage_risk_advisor']
