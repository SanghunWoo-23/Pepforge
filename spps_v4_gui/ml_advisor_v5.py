"""Evidence-first V5 advisor composition.

V4 historical condition logic is retained as the stable chemistry/data foundation.
V5 adds outcome-aware evidence, residue difficulty context, similar-experiment lookup,
and separately bounded cleavage-volume/workup evidence from material-usage records.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import math
from statistics import median

from spps_v4_gui import ml_advisor_v4
from spps_v4_gui import experimental_data
from spps_v4_gui import model_registry_v5
from spps_v4_gui.empirical_cleavage_v5 import cys_equivalent_override, operator_anchor, empirical_fallback
from spps_v4_gui.decision_support_v5 import (    cleavage_amount_recommendation,
    sequence_difficulty_map,
    similar_experiments,
    validation_snapshot,
    stage_risk_advisor,
)



def _num(value: Any) -> float | None:
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _pava(points: list[tuple[float, float, int]]) -> list[tuple[float, float]]:
    """Small weighted isotonic fit used only for target-loading inversion."""
    blocks=[]
    for x,y,w in points:
        blocks.append([x,x,float(y),int(max(1,w))])
        while len(blocks)>=2 and blocks[-2][2] > blocks[-1][2]:
            b=blocks.pop(); a=blocks.pop(); total=a[3]+b[3]
            blocks.append([a[0],b[1],(a[2]*a[3]+b[2]*b[3])/total,total])
    out=[]
    for lo,hi,y,w in blocks:
        members=[x for x,_,_ in points if lo-1e-12 <= x <= hi+1e-12]
        for x in members:
            out.append((x,float(y)))
    return sorted(out)


def _target_loading_inverse(*, resin: str, amino_acid: str, target_loading_mmol_g: Any,
                            base_eq: Any = None, loading_time_h: Any = None,
                            db_path: str | Path | None = None, include_parsed: bool = True) -> dict[str, Any] | None:
    """Estimate AA eq needed for a requested loading from exact resin+AA history.

    Verified measured results are always attempted first. Parsed historical rows are
    only a provisional fallback when Verified rows cannot support a bounded inverse.
    Neither path extrapolates beyond the observed AA-eq/loading envelope, and
    outlier-flagged rows are never used.
    """
    target=_num(target_loading_mmol_g)
    if target is None or target <= 0:
        return None
    statuses=['verified']+(['parsed'] if include_parsed else [])
    rows=experimental_data.list_records('loading',db_path,statuses=statuses)
    rkey=experimental_data.canonical_resin_key(resin)
    akey=experimental_data.canonical_amino_acid_key(amino_acid)
    exact=[]
    for raw in rows:
        if int(raw.get('outlier_flag') or 0):
            continue
        if experimental_data.canonical_resin_key(raw.get('resin_type')) != rkey:
            continue
        aa_name=raw.get('amino_acid_normalized') or raw.get('amino_acid_raw')
        if experimental_data.canonical_amino_acid_key(aa_name) != akey:
            continue
        aa=_num(raw.get('aa_eq')); load=_num(raw.get('loading_rate_mmol_g'))
        if aa is None or aa <= 0 or load is None or load < 0:
            continue
        row=dict(raw); row['_aa']=aa; row['_load']=load; row['_status']=str(raw.get('status') or '')
        exact.append(row)
    if len(exact) < 2 or len({round(r['_aa'],8) for r in exact}) < 2:
        return None

    qbase=_num(base_eq); qtime=_num(loading_time_h)

    def fit(pool: list[dict[str,Any]], *, provisional: bool, source_status: str) -> dict[str,Any] | None:
        if len(pool) < 2 or len({round(r['_aa'],8) for r in pool}) < 2:
            return None
        context=list(pool); basis=[]
        if qbase is not None:
            same=[r for r in context if _num(r.get('base_eq')) is not None and abs(float(r.get('base_eq'))-qbase) <= 0.15]
            if len({round(r['_aa'],8) for r in same}) >= 2:
                context=same; basis.append(f'base eq ≈ {qbase:g}')
        if qtime is not None and qtime > 0:
            same=[r for r in context if _num(r.get('loading_time_h')) is not None and abs(float(r.get('loading_time_h'))-qtime) <= 0.5]
            if len({round(r['_aa'],8) for r in same}) >= 2:
                context=same; basis.append(f'time ≈ {qtime:g} h')
        if len({round(r['_aa'],8) for r in context}) < 2:
            context=list(pool); basis=[]
        if context != pool:
            cmin=min(r['_load'] for r in context); cmax=max(r['_load'] for r in context)
            emin=min(r['_load'] for r in pool); emax=max(r['_load'] for r in pool)
            if not (cmin <= target <= cmax) and emin <= target <= emax:
                context=list(pool); basis=[]

        grouped={}
        for r in context:
            grouped.setdefault(round(r['_aa'],8),[]).append(r)
        pts=[]
        for aa,group in sorted(grouped.items()):
            loads=sorted(float(r['_load']) for r in group)
            pts.append((float(aa),float(median(loads)),len(group)))
        if len(pts)<2:
            return None
        fitted=_pava(pts) if len(pts)>=3 else [(x,y) for x,y,_ in pts]
        if len(fitted)==2 and fitted[1][1] < fitted[0][1]:
            return {
                'apply_allowed':False,'recommendation_kind':'INSUFFICIENT MONOTONIC EVIDENCE',
                'target_loading_mmol_g':target,'evidence_count':len(context),'verified_evidence_count':sum(r['_status']=='verified' for r in context),
                'observed_aa_eq_min':min(x for x,_,_ in pts),'observed_aa_eq_max':max(x for x,_,_ in pts),
                'observed_loading_min':min(y for _,y,_ in pts),'observed_loading_max':max(y for _,y,_ in pts),
                'source_status':source_status,'provisional':provisional,
                'basis':'Exact resin + AA history is not monotonic enough for bounded interpolation.',
            }
        ymin=min(y for _,y in fitted); ymax=max(y for _,y in fitted)
        if not (ymin-1e-12 <= target <= ymax+1e-12):
            nearest=min(pts,key=lambda p:abs(p[1]-target))
            return {
                'aa_eq':nearest[0],'predicted_loading_mmol_g':nearest[1],
                'target_loading_mmol_g':target,'apply_allowed':False,
                'recommendation_kind':'TARGET OUTSIDE OBSERVED RANGE',
                'evidence_count':len(context),'verified_evidence_count':sum(r['_status']=='verified' for r in context),
                'observed_aa_eq_min':min(x for x,_,_ in pts),'observed_aa_eq_max':max(x for x,_,_ in pts),
                'observed_loading_min':ymin,'observed_loading_max':ymax,
                'source_status':source_status,'provisional':provisional,
                'basis':'Target lies outside observed exact resin + AA loading range; extrapolation disabled.',
            }
        rec_aa=fitted[0][0]; pred=fitted[0][1]
        for (x1,y1),(x2,y2) in zip(fitted,fitted[1:]):
            if y1 <= target <= y2:
                if abs(y2-y1) < 1e-12:
                    rec_aa=x1; pred=y1
                else:
                    frac=(target-y1)/(y2-y1); rec_aa=x1+(x2-x1)*frac; pred=y1+(y2-y1)*frac
                break
        rec_aa=round(float(rec_aa),2)
        nearest_rows=sorted(context,key=lambda r:abs(r['_aa']-rec_aa))[:max(2,min(5,len(context)))]
        base_values=[_num(r.get('base_eq')) for r in nearest_rows]; base_values=[x for x in base_values if x is not None]
        time_values=[_num(r.get('loading_time_h')) for r in nearest_rows]; time_values=[x for x in time_values if x is not None and x>0]
        solvent_values=[str(r.get('loading_solvent') or '').strip() for r in nearest_rows if str(r.get('loading_solvent') or '').strip()]
        rec_base=qbase if qbase is not None else (float(median(base_values)) if base_values else None)
        rec_time=qtime if qtime is not None and qtime>0 else (float(median(time_values)) if time_values else None)
        rec_solvent=max(set(solvent_values),key=solvent_values.count) if solvent_values else ''
        fit_map={x:y for x,y in fitted}; residuals=[]
        for r in context:
            x=min(fit_map,key=lambda z:abs(z-r['_aa']))
            residuals.append(abs(r['_load']-fit_map[x]))
        robust_err=float(median(residuals)) if residuals else 0.0
        half=max(0.02,robust_err)
        verified_n=sum(r['_status']=='verified' for r in context)
        if provisional:
            confidence='MEDIUM' if len(context)>=5 and verified_n>=1 else 'LOW'
        else:
            confidence='HIGH' if len(context)>=5 else 'MEDIUM' if len(context)>=3 else 'LOW'
        result={
            'aa_eq':rec_aa,'base_eq':rec_base,'loading_time_h':rec_time,'loading_solvent':rec_solvent,
            'predicted_loading_mmol_g':round(float(pred),4),'expected_low_mmol_g':max(0.0,round(float(pred-half),4)),
            'expected_high_mmol_g':round(float(pred+half),4),'target_loading_mmol_g':target,
            'apply_allowed':True,'recommendation_kind':'BOUNDED TARGET INTERPOLATION',
            'confidence':confidence,'evidence_count':len(context),'verified_evidence_count':verified_n,'exact_record_count':len(exact),
            'observed_aa_eq_min':min(x for x,_,_ in pts),'observed_aa_eq_max':max(x for x,_,_ in pts),
            'observed_loading_min':ymin,'observed_loading_max':ymax,
            'source_status':source_status,'provisional':provisional,
            'basis':('Verified measured exact resin + C-terminal AA history' if not provisional else 'Exact resin + C-terminal AA historical fallback (includes Parsed rows)') + (('; constrained to '+', '.join(basis)) if basis else '') + '; monotonic bounded interpolation; no extrapolation.',
        }
        # The explicit rebuilt ML model is only a cross-check here.  It never
        # expands the observed eq range or silently replaces the auditable inverse.
        model_pred=model_registry_v5.predict_loading(resin=resin,amino_acid=amino_acid,aa_eq=rec_aa,base_eq=rec_base,loading_time_h=rec_time)
        if model_pred.get('available'):
            mp=_num(model_pred.get('prediction'))
            result['model_cross_check_mmol_g']=None if mp is None else round(mp,4)
            result['model_id']=str((model_pred.get('model') or {}).get('model_id') or '')
            if mp is not None:
                result['model_target_gap_mmol_g']=round(abs(mp-target),4)
                active_mae=_num((model_pred.get('model') or {}).get('cross_validated_mae_mmol_g'))
                tolerance=max(0.05,2.0*(active_mae or 0.0))
                result['model_agrees']=abs(mp-target) <= tolerance
        return result

    verified=[r for r in exact if r['_status']=='verified']
    verified_result=fit(verified,provisional=False,source_status='verified')
    if verified_result and verified_result.get('apply_allowed'):
        return verified_result

    if include_parsed and any(r['_status']=='parsed' for r in exact):
        fallback=fit(exact,provisional=True,source_status='verified+parsed')
        if fallback and fallback.get('apply_allowed'):
            fallback['verified_only_attempt']=verified_result
            return fallback
        if verified_result is None:
            return fallback
    return verified_result

def loading_advice(*args, **kwargs):
    result=dict(ml_advisor_v4.loading_advice(*args, **kwargs))
    resin=kwargs.get('resin', args[0] if len(args)>0 else '')
    amino=kwargs.get('amino_acid', args[1] if len(args)>1 else '')
    model_pred=model_registry_v5.predict_loading(
        resin=resin, amino_acid=amino, aa_eq=kwargs.get('aa_eq'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
    )
    result['implicit_v4_model_prediction']=result.get('prediction') if 'random-forest' in str(result.get('method','')) else None
    if model_pred.get('available'):
        result['prediction']=model_pred.get('prediction'); result['method']='explicit V5 loading model + historical evidence'
    else:
        if result.get('similarity_prediction') is not None:
            result['prediction']=result.get('similarity_prediction')
        result['method']='historical similarity (V5 model not rebuilt)'
    result['model_registry']=model_pred.get('model')
    if model_pred.get('warning'): result.setdefault('warnings',[]).append('V5 loading model: '+str(model_pred['warning']))
    target_rec=_target_loading_inverse(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    result['target_recommendation']=target_rec
    result['advisor_version']='5.0.0'
    return result


def loading_recommendation(*args, **kwargs):
    # The base observed-condition API intentionally accepts fewer fields than
    # loading_advice().  Filter shared controller/query extras instead of
    # leaking AA/base/time fields into that narrower signature.
    base_kwargs = {
        key: kwargs[key]
        for key in ("target_loading_mmol_g", "db_path", "include_parsed")
        if key in kwargs
    }
    resin=kwargs.get('resin', args[0] if len(args)>0 else '')
    amino=kwargs.get('amino_acid', args[1] if len(args)>1 else '')
    result=dict(ml_advisor_v4.loading_recommendation(
        resin=resin, amino_acid=amino, **base_kwargs
    ))
    target=_target_loading_inverse(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    result['target_recommendation']=target
    if target and target.get('apply_allowed'):
        rec=dict(target)
        rec.update({
            'expected_loading_mmol_g':target.get('predicted_loading_mmol_g'),
            'observed_min':target.get('observed_loading_min'),'observed_max':target.get('observed_loading_max'),
            'condition_evidence_count':target.get('evidence_count',0),
            'source_record_id':'bounded-history-fit','basis':target.get('basis'),
        })
        result['recommended_condition']=rec
        result['method']='target-loading bounded inverse recommendation'
        result['confidence']=target.get('confidence','LOW')
    result['advisor_version']='5.0.0'
    return result


def _inject_empirical_condition(result: dict, *, sequence: str, resin: str, scale_mmol: Any, db_path):
    """Apply operator Cys rule first, then exact anchors/history, then fallback."""
    cys_rule = cys_equivalent_override(sequence, scale_mmol=scale_mmol, resin=resin)
    if cys_rule:
        result = dict(result)
        result['recommended_condition'] = cys_rule
        result['method'] = 'operator Cys equivalent rule'
        result['confidence'] = 'HIGH'
        result.setdefault('warnings', [])
        result['warnings'] = [w for w in result['warnings'] if 'No sequence-matched' not in str(w)]
        result['warnings'].append('Cys override active: 100 TFA eq per Cys; mer-count and similar-sequence eq estimates are bypassed.')
        result['empirical_fallback'] = cys_rule.get('empirical_estimate') or {}
        result['evidence_summary'] = dict(result.get('evidence_summary') or {}, source_kind='OPERATOR CYS RULE', apply_allowed=True)
        return result
    anchor = operator_anchor(sequence, scale_mmol=scale_mmol)
    if anchor:
        result = dict(result)
        result['recommended_condition'] = anchor
        result['method'] = 'operator-approved exact sequence anchor'
        result['confidence'] = 'HIGH'
        result.setdefault('warnings', [])
        result['warnings'] = [w for w in result['warnings'] if 'No sequence-matched' not in str(w)]
        result['evidence_summary'] = dict(result.get('evidence_summary') or {}, source_kind='OPERATOR ANCHOR', apply_allowed=True)
        return result
    rec = result.get('recommended_condition') or {}
    source = str(rec.get('condition_source') or '')
    # Whole recorded exact conditions always outrank interpolation/chemistry fallback.
    if rec and source in {'recommended_exact_sequence_record','exact_lab_record'}:
        return result
    fallback = empirical_fallback(sequence, scale_mmol=scale_mmol, db_path=db_path, resin=resin)
    if not fallback:
        return result
    result = dict(result)
    result['recommended_condition'] = fallback
    result['method'] = 'V5 empirical cleavage fallback (no complete exact condition)'
    result['confidence'] = (fallback.get('empirical_estimate') or {}).get('confidence', 'LOW')
    warnings = list(result.get('warnings') or [])
    warnings.append('Empirical fallback is an operator-confirmed estimate, not an observed exact condition. Exact history/SOP remains higher priority.')
    result['warnings'] = warnings
    result['empirical_fallback'] = fallback.get('empirical_estimate') or {}
    result['evidence_summary'] = dict(result.get('evidence_summary') or {}, source_kind='EMPIRICAL ESTIMATE', apply_allowed=True)
    return result


def cleavage_advice(*,product:str='',sequence:str='',resin:str='',scale_mmol:Any=None,db_path:str|Path|None=None,**kwargs):
    result=dict(ml_advisor_v4.cleavage_advice(product=product,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path,**kwargs))
    result=_inject_empirical_condition(result,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path)
    result['advisor_version']='5.0.0'
    result['amount_evidence']=cleavage_amount_recommendation(product=product,sequence=sequence,scale_mmol=scale_mmol,db_path=db_path)
    result['sequence_difficulty']=sequence_difficulty_map(sequence) if sequence else {'positions':[],'apply_allowed':False}
    return result


def cleavage_recommendation(*,product:str='',sequence:str='',resin:str='',scale_mmol:Any=None,db_path:str|Path|None=None,**kwargs):
    result=dict(ml_advisor_v4.cleavage_recommendation(product=product,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path,**kwargs))
    result=_inject_empirical_condition(result,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path)
    result['advisor_version']='5.0.0'
    result['amount_evidence']=cleavage_amount_recommendation(product=product,sequence=sequence,scale_mmol=scale_mmol,db_path=db_path)
    return result


__all__=[
    'loading_advice','loading_recommendation','cleavage_advice','cleavage_recommendation',
    'cleavage_amount_recommendation','sequence_difficulty_map','similar_experiments','validation_snapshot','stage_risk_advisor',
]
