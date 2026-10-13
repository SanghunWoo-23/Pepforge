"""Canonical evidence-first Loading/Cleavage advisor implementation.

The validated historical condition logic is retained as the stable chemistry/data foundation.
V5 adds outcome-aware evidence, residue difficulty context, similar-experiment lookup,
and separately bounded cleavage-volume/workup evidence from material-usage records.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import math
from statistics import median

from . import history_base as history_engine
from suite_gui import experimental_data
from . import model_registry
from .empirical_cleavage import cys_equivalent_override, operator_anchor, empirical_fallback
from .decision_support import (
    cleavage_amount_recommendation,
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
        model_pred=model_registry.predict_loading(resin=resin,amino_acid=amino_acid,aa_eq=rec_aa,base_eq=rec_base,loading_time_h=rec_time)
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

def _observed_condition_match(*, resin: str, amino_acid: str, target_loading_mmol_g: Any,
                              base_eq: Any = None, loading_time_h: Any = None,
                              db_path: str | Path | None = None, include_parsed: bool = True) -> dict[str, Any] | None:
    """Return a real repeated historical condition when target lies inside its observed range.

    This is not extrapolation: every recommended AA-equivalent is an actually observed
    condition for the same resin + loaded/C-terminal amino acid. Parsed rows remain
    provisional and outlier-flagged rows are excluded.
    """
    target=_num(target_loading_mmol_g)
    if target is None or target <= 0:
        return None
    statuses=['verified']+(['parsed'] if include_parsed else [])
    rows=experimental_data.list_records('loading',db_path,statuses=statuses)
    rkey=experimental_data.canonical_resin_key(resin)
    akey=experimental_data.canonical_amino_acid_key(amino_acid)
    qbase=_num(base_eq); qtime=_num(loading_time_h)
    groups={}
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
        b=_num(raw.get('base_eq')); t=_num(raw.get('loading_time_h'))
        key=(round(aa,6), None if b is None else round(b,6), None if t is None else round(t,3))
        groups.setdefault(key,[]).append(dict(raw, _load=load, _status=str(raw.get('status') or '')))
    candidates=[]
    for (aa,b,t), group in groups.items():
        if len(group) < 2:
            continue
        loads=sorted(float(r['_load']) for r in group)
        lo,hi=min(loads),max(loads)
        if not (lo-1e-12 <= target <= hi+1e-12):
            continue
        # Respect explicitly requested base/time when that information exists.
        context_penalty=0.0
        if qbase is not None and b is not None:
            context_penalty += abs(float(b)-qbase)
        if qtime is not None and qtime > 0 and t is not None:
            context_penalty += abs(float(t)-qtime)/2.0
        med=float(median(loads))
        parsed=any(r['_status']!='verified' for r in group)
        candidates.append((context_penalty, abs(med-target), -len(group), aa,b,t,loads,parsed,group))
    if not candidates:
        return None
    _,_,_,aa,b,t,loads,parsed,group=min(candidates,key=lambda x:x[:3])
    med=float(median(loads))
    return {
        'aa_eq':float(aa),'base_eq':None if b is None else float(b),
        'loading_time_h':None if t is None else float(t),'loading_solvent':'',
        'predicted_loading_mmol_g':round(med,4),
        'expected_low_mmol_g':round(min(loads),4),'expected_high_mmol_g':round(max(loads),4),
        'target_loading_mmol_g':target,'apply_allowed':True,
        'recommendation_kind':'OBSERVED REPEATED CONDITION',
        'confidence':'MEDIUM' if parsed else ('HIGH' if len(group)>=3 else 'MEDIUM'),
        'evidence_count':len(group),'verified_evidence_count':sum(r['_status']=='verified' for r in group),
        'source_status':'verified+parsed' if parsed else 'verified','provisional':parsed,
        'observed_loading_min':min(loads),'observed_loading_max':max(loads),
        'basis':'Repeated observed condition for exact resin + loaded/C-terminal AA; target lies inside the measured range; no extrapolation.',
    }



def _same_category_profile(*, resin: str, amino_acid: str, target_loading_mmol_g: Any = None,
                           db_path: str | Path | None = None, include_parsed: bool = True) -> dict[str, Any]:
    """Summarize auditable same-resin + same-AA loading evidence for the UI.

    This is descriptive only.  It never creates a condition, never extrapolates, and
    never changes Apply eligibility.  Outliers remain excluded exactly as in the
    recommendation path.
    """
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
        load=_num(raw.get('loading_rate_mmol_g'))
        if load is None or load < 0:
            continue
        row=dict(raw); row['_load']=float(load)
        exact.append(row)
    if not exact:
        return {
            'exact_record_count':0,'verified_record_count':0,'parsed_record_count':0,
            'distinct_condition_count':0,'repeated_condition_count':0,
            'date_min':'','date_max':'','observed_loading_min':None,'observed_loading_median':None,
            'observed_loading_max':None,'observed_aa_eq_min':None,'observed_aa_eq_max':None,
            'conditions':[],'nearest_conditions':[],'evidence_records':[],
        }

    def _date(row):
        return str(row.get('date') or '').strip()

    loads=sorted(r['_load'] for r in exact)
    aa_values=sorted(x for x in (_num(r.get('aa_eq')) for r in exact) if x is not None)
    dates=sorted(d for d in (_date(r) for r in exact) if d)
    groups={}
    for row in exact:
        aa=_num(row.get('aa_eq')); base=_num(row.get('base_eq')); time=_num(row.get('loading_time_h'))
        solvent=str(row.get('loading_solvent') or '').strip()
        key=(None if aa is None else round(aa,6), None if base is None else round(base,6), None if time is None else round(time,3), solvent)
        groups.setdefault(key,[]).append(row)

    target=_num(target_loading_mmol_g)
    condition_rows=[]
    for (aa,base,time,solvent), members in groups.items():
        gl=sorted(float(r['_load']) for r in members)
        gd=sorted(d for d in (_date(r) for r in members) if d)
        locators=[]; methods=[]; capped=0; capping_known=0
        for row in members:
            loc=str(row.get('source_locator') or '').strip()
            if loc and loc not in locators: locators.append(loc)
            method=str(row.get('capping_method') or '').strip()
            if method and method not in methods: methods.append(method)
            value=str(row.get('capping_performed') or '').strip().lower()
            if value:
                capping_known += 1
            if value in {'1','true','yes','y'}: capped += 1
        med=float(median(gl))
        item={
            'aa_eq':aa,'base_eq':base,'loading_time_h':time,'loading_solvent':solvent,
            'evidence_count':len(members),
            'verified_count':sum(str(r.get('status') or '').lower()=='verified' for r in members),
            'parsed_count':sum(str(r.get('status') or '').lower()=='parsed' for r in members),
            'loading_median_mmol_g':round(med,4),'loading_min_mmol_g':round(min(gl),4),'loading_max_mmol_g':round(max(gl),4),
            'date_min':gd[0] if gd else '','date_max':gd[-1] if gd else '',
            'capping_observed_count':capped,'capping_known_count':capping_known,'capping_record_count':len(members),
            'capping_methods':methods[:4],'source_locators':locators[:6],
        }
        if target is not None:
            item['target_gap_mmol_g']=round(abs(med-target),4)
        condition_rows.append(item)

    def _sort_key(item):
        gap=item.get('target_gap_mmol_g')
        return (float('inf') if gap is None else gap, -int(item.get('evidence_count') or 0),
                float('inf') if item.get('aa_eq') is None else float(item['aa_eq']))
    nearest=sorted(condition_rows,key=_sort_key)[:5]
    condition_rows=sorted(condition_rows,key=lambda item:(
        float('inf') if item.get('aa_eq') is None else float(item['aa_eq']),
        float('inf') if item.get('base_eq') is None else float(item['base_eq']),
        float('inf') if item.get('loading_time_h') is None else float(item['loading_time_h']),
    ))
    return {
        'exact_record_count':len(exact),
        'verified_record_count':sum(str(r.get('status') or '').lower()=='verified' for r in exact),
        'parsed_record_count':sum(str(r.get('status') or '').lower()=='parsed' for r in exact),
        'distinct_condition_count':len(condition_rows),
        'repeated_condition_count':sum(int(item.get('evidence_count') or 0)>=2 for item in condition_rows),
        'date_min':dates[0] if dates else '','date_max':dates[-1] if dates else '',
        'observed_loading_min':round(min(loads),4),'observed_loading_median':round(float(median(loads)),4),'observed_loading_max':round(max(loads),4),
        'observed_aa_eq_min':None if not aa_values else min(aa_values),'observed_aa_eq_max':None if not aa_values else max(aa_values),
        'conditions':condition_rows,'nearest_conditions':nearest,
        'evidence_records':[
            {k:v for k,v in row.items() if not str(k).startswith('_')}
            for row in exact
        ],
    }


def _attach_loading_support(rec: dict[str, Any] | None, profile: dict[str, Any]) -> dict[str, Any] | None:
    """Attach descriptive support to a recommendation without changing its decision."""
    if not rec:
        return rec
    out=dict(rec)
    aa=_num(out.get('aa_eq')); base=_num(out.get('base_eq')); time=_num(out.get('loading_time_h'))
    matches=[]
    for item in profile.get('conditions') or []:
        ia=_num(item.get('aa_eq')); ib=_num(item.get('base_eq')); it=_num(item.get('loading_time_h'))
        if aa is not None and ia is not None and abs(aa-ia) > 1e-6: continue
        if base is not None and ib is not None and abs(base-ib) > 1e-6: continue
        if time is not None and it is not None and abs(time-it) > 1e-6: continue
        if aa is not None and ia is None: continue
        matches.append(item)
    if matches:
        out['condition_support']=max(matches,key=lambda item:int(item.get('evidence_count') or 0))
    out['nearest_observed_conditions']=[dict(item) for item in (profile.get('nearest_conditions') or [])[:3]]
    pred=_num(out.get('predicted_loading_mmol_g')); target=_num(out.get('target_loading_mmol_g'))
    if pred is not None and target is not None:
        out['target_delta_mmol_g']=round(pred-target,4)
        out['target_abs_gap_mmol_g']=round(abs(pred-target),4)
    return out

def _loading_chemistry_default(*, resin: str, amino_acid: str, target_loading_mmol_g: Any,
                               base_eq: Any = None, loading_time_h: Any = None) -> dict[str, Any] | None:
    """Return an explicit planning default, never a fabricated target-loading prediction."""
    target=_num(target_loading_mmol_g)
    if target is None or target <= 0:
        return None
    rkey=experimental_data.canonical_resin_key(resin)
    text=(str(resin or '')+' '+str(rkey or '')).lower()
    if not any(token in text for token in ('trityl','ctc','chlorotrityl')):
        return None
    qbase=_num(base_eq); qtime=_num(loading_time_h)
    return {
        'aa_eq':2.0,'base_eq':qbase if qbase is not None and qbase>0 else 4.0,
        'loading_time_h':qtime if qtime is not None and qtime>0 else None,'loading_solvent':'',
        'predicted_loading_mmol_g':None,'expected_low_mmol_g':None,'expected_high_mmol_g':None,
        'target_loading_mmol_g':target,'apply_allowed':True,
        'recommendation_kind':'CHEMISTRY DEFAULT','confidence':'LOW','evidence_count':0,
        'verified_evidence_count':0,'source_status':'chemistry_default','provisional':True,
        'basis':'2-CTC/Trityl direct-loading planning default (AA 2 eq / DIEA 4 eq). This is not a prediction that the requested loading will be achieved.',
    }


def loading_advice(*args, **kwargs):
    result=dict(history_engine.loading_advice(*args, **kwargs))
    resin=kwargs.get('resin', args[0] if len(args)>0 else '')
    amino=kwargs.get('amino_acid', args[1] if len(args)>1 else '')
    model_pred=model_registry.predict_loading(
        resin=resin, amino_acid=amino, aa_eq=kwargs.get('aa_eq'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
    )
    result['implicit_model_prediction']=result.get('prediction') if 'random-forest' in str(result.get('method','')) else None
    if model_pred.get('available'):
        result['prediction']=model_pred.get('prediction'); result['method']='explicit loading model + historical evidence'
    else:
        if result.get('similarity_prediction') is not None:
            result['prediction']=result.get('similarity_prediction')
        result['method']='historical similarity (loading model not rebuilt)'
    result['model_registry']=model_pred.get('model')
    if model_pred.get('warning'): result.setdefault('warnings',[]).append('Loading model: '+str(model_pred['warning']))
    target_rec=_observed_condition_match(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    ) or _target_loading_inverse(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    if not target_rec or not target_rec.get('apply_allowed'):
        target_rec = target_rec or _loading_chemistry_default(
            resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
            base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        )
    profile=_same_category_profile(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    identity=experimental_data.describe_amino_acid_identity(amino)
    identity.update({
        'exact_history_count':int(profile.get('exact_record_count') or 0),
        'data_supported':bool(profile.get('exact_record_count')),
    })
    result['amino_acid_identity']=identity
    result['exact_evidence_profile']=profile
    # Keep broad similarity rows available for diagnostics, but operator-facing
    # Loading evidence is exact resin + exact normalized loaded-AA only. This is
    # especially important for D-form/special residues so L-form analogues never
    # appear as if they supported the recommendation.
    result['context_evidence']=list(result.get('evidence') or [])
    result['evidence']=list(profile.get('evidence_records') or [])
    result['target_recommendation']=_attach_loading_support(target_rec,profile)
    result['advisor_version']='6.0.0'
    return result


def loading_recommendation(*args, **kwargs):
    result=dict(history_engine.loading_recommendation(*args, **kwargs))
    resin=kwargs.get('resin', args[0] if len(args)>0 else '')
    amino=kwargs.get('amino_acid', args[1] if len(args)>1 else '')
    target=_observed_condition_match(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    ) or _target_loading_inverse(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    if not target or not target.get('apply_allowed'):
        target = target or _loading_chemistry_default(
            resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
            base_eq=kwargs.get('base_eq'), loading_time_h=kwargs.get('loading_time_h'),
        )
    profile=_same_category_profile(
        resin=resin, amino_acid=amino, target_loading_mmol_g=kwargs.get('target_loading_mmol_g'),
        db_path=kwargs.get('db_path'), include_parsed=bool(kwargs.get('include_parsed',True)),
    )
    identity=experimental_data.describe_amino_acid_identity(amino)
    identity.update({
        'exact_history_count':int(profile.get('exact_record_count') or 0),
        'data_supported':bool(profile.get('exact_record_count')),
    })
    target=_attach_loading_support(target,profile)
    result['amino_acid_identity']=identity
    result['exact_evidence_profile']=profile
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
    result['advisor_version']='6.0.0'
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
    result['method'] = 'empirical cleavage fallback (no complete exact condition)'
    result['confidence'] = (fallback.get('empirical_estimate') or {}).get('confidence', 'LOW')
    warnings = list(result.get('warnings') or [])
    warnings.append('Empirical fallback is an operator-confirmed estimate, not an observed exact condition. Exact history/SOP remains higher priority.')
    result['warnings'] = warnings
    result['empirical_fallback'] = fallback.get('empirical_estimate') or {}
    result['evidence_summary'] = dict(result.get('evidence_summary') or {}, source_kind='EMPIRICAL ESTIMATE', apply_allowed=True)
    return result


def cleavage_advice(*,product:str='',sequence:str='',resin:str='',scale_mmol:Any=None,db_path:str|Path|None=None,**kwargs):
    result=dict(history_engine.cleavage_advice(product=product,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path,**kwargs))
    result=_inject_empirical_condition(result,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path)
    result['advisor_version']='6.0.0'
    result['amount_evidence']=cleavage_amount_recommendation(product=product,sequence=sequence,scale_mmol=scale_mmol,db_path=db_path)
    result['sequence_difficulty']=sequence_difficulty_map(sequence) if sequence else {'positions':[],'apply_allowed':False}
    return result


def cleavage_recommendation(*,product:str='',sequence:str='',resin:str='',scale_mmol:Any=None,db_path:str|Path|None=None,**kwargs):
    result=dict(history_engine.cleavage_recommendation(product=product,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path,**kwargs))
    result=_inject_empirical_condition(result,sequence=sequence,resin=resin,scale_mmol=scale_mmol,db_path=db_path)
    result['advisor_version']='6.0.0'
    result['amount_evidence']=cleavage_amount_recommendation(product=product,sequence=sequence,scale_mmol=scale_mmol,db_path=db_path)
    return result


# Stable public recommendation API retained for UI/external compatibility.
def advise(*, db_path=None, **query):
    return loading_advice(db_path=db_path, **query)

def recommend(*, db_path=None, **query):
    return loading_recommendation(db_path=db_path, **query)


__all__=[
    'advise','recommend','loading_advice','loading_recommendation','cleavage_advice','cleavage_recommendation',
    'cleavage_amount_recommendation','sequence_difficulty_map','similar_experiments','validation_snapshot','stage_risk_advisor',
]
