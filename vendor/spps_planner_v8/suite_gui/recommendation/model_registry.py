"""Canonical loading-model registry with explicit version history.

The model is never retrained as a side effect of opening an advisor. Operators must
request a rebuild. Every successful rebuild is stored as a distinct local version and
can be rolled back explicitly. Apply actions remain tied to real historical conditions,
not model predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import tempfile
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
from suite_gui import experimental_data


def _paths() -> tuple[Path, Path]:
    try:
        from spps_planner.user_paths import user_file
        registry=Path(user_file('model_registry_v5.json'))
        model=Path(user_file('loading_model_v5.joblib'))
    except Exception:
        base=experimental_data.default_db_path().parent
        registry=base/'model_registry_v5.json'; model=base/'loading_model_v5.joblib'
    registry.parent.mkdir(parents=True,exist_ok=True)
    return registry,model


def _empty_registry() -> dict[str,Any]:
    return {'schema_version':2,'models':{'loading':{'active_model_id':'','versions':[]}}}


def _read_registry() -> dict[str,Any]:
    path,_=_paths()
    if not path.is_file(): return _empty_registry()
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except Exception as primary_exc:
        backup=path.with_suffix(path.suffix+'.bak')
        try:
            data=json.loads(backup.read_text(encoding='utf-8'))
        except Exception:
            # Corruption is an integrity event; do not silently pretend a populated registry is empty.
            raise RuntimeError(f"Model registry is unreadable: {path}") from primary_exc
    if not isinstance(data,dict): return _empty_registry()
    # Migrate the pre-history registry format in memory. The next write persists schema 2.
    models=data.setdefault('models',{})
    block=models.get('loading')
    if isinstance(block,dict) and 'versions' not in block:
        versions=[dict(block)] if block.get('built') else []
        models['loading']={'active_model_id':str(block.get('model_id') or ''),'versions':versions}
    elif not isinstance(block,dict):
        models['loading']={'active_model_id':'','versions':[]}
    else:
        block.setdefault('active_model_id',''); block.setdefault('versions',[])
    data['schema_version']=2
    return data


def _atomic_bytes(path:Path, payload:bytes)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=str(path.parent)); os.close(fd)
    tmp=Path(name)
    try:
        with tmp.open('wb') as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        if path.exists():
            try: shutil.copy2(path,path.with_suffix(path.suffix+'.bak'))
            except OSError: pass
        os.replace(tmp,path)
    finally:
        try: tmp.unlink(missing_ok=True)
        except OSError: pass

def _write_registry(data:dict[str,Any])->None:
    path,_=_paths(); _atomic_bytes(path,json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True).encode('utf-8'))

def _atomic_joblib_dump(joblib, model, path:Path)->None:
    fd,name=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=str(path.parent)); os.close(fd); tmp=Path(name)
    try:
        joblib.dump(model,tmp); os.replace(tmp,path)
    finally:
        try: tmp.unlink(missing_ok=True)
        except OSError: pass


def _loading_block(data:dict[str,Any]) -> dict[str,Any]:
    models=data.setdefault('models',{})
    block=models.setdefault('loading',{'active_model_id':'','versions':[]})
    block.setdefault('active_model_id',''); block.setdefault('versions',[])
    return block


def loading_model_history()->list[dict[str,Any]]:
    data=_read_registry(); block=_loading_block(data)
    versions=[dict(v) for v in block.get('versions',[]) if isinstance(v,dict)]
    active=str(block.get('active_model_id') or '')
    for row in versions: row['active']=str(row.get('model_id') or '')==active
    return list(reversed(versions))


def loading_model_info()->dict[str,Any]|None:
    data=_read_registry(); block=_loading_block(data)
    versions=[v for v in block.get('versions',[]) if isinstance(v,dict)]
    if not versions: return None
    active=str(block.get('active_model_id') or '')
    selected=next((v for v in versions if str(v.get('model_id') or '')==active),versions[-1])
    info=dict(selected); info['active_model_id']=str(selected.get('model_id') or '')
    info['version_count']=len(versions); info['active']=True
    return info




def loading_rebuild_status(db_path:str|Path|None=None)->dict[str,Any]:
    """Report whether enough new Verified measured loading results justify a rebuild.

    This never retrains.  With no model, the normal 12-record build threshold is
    reported.  With an active model, five new eligible Verified results since the
    active build are used as the operator-facing reminder threshold.
    """
    rows=experimental_data.list_records('loading',db_path,statuses=['verified'])
    eligible=[]
    for row in rows:
        try:
            measured=float(row.get('loading_rate_mmol_g'))
            if not math.isfinite(measured):
                continue
        except Exception:
            continue
        if int(row.get('outlier_flag') or 0):
            continue
        eligible.append(row)
    info=loading_model_info()
    if not info or not info.get('built'):
        count=len(eligible); threshold=12
        return {
            'active_model':False,'eligible_verified_count':count,'new_verified_count':count,
            'threshold':threshold,'rebuild_ready':count>=threshold,
            'message':(f'{count} Verified measured loading results available; {threshold} are required for the first model build.'),
        }
    built_at=str(info.get('built_at') or '')
    newer=[r for r in eligible if str(r.get('created_at') or '') > built_at] if built_at else eligible
    count=len(newer); threshold=5
    return {
        'active_model':True,'eligible_verified_count':len(eligible),'new_verified_count':count,
        'threshold':threshold,'rebuild_ready':count>=threshold,'active_model_id':str(info.get('active_model_id') or ''),
        'built_at':built_at,
        'message':(f'{count} new measured loading result' + ('s' if count!=1 else '') + ' since the active model; rebuild is recommended.' if count>=threshold else f'{count} new measured loading result' + ('s' if count!=1 else '') + ' since the active model.'),
    }

def _version_model_path(model_id:str)->Path:
    _,active_path=_paths()
    safe=''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in model_id)
    return active_path.with_name(f'{active_path.stem}_{safe}{active_path.suffix}')


def rebuild_loading_model(db_path:str|Path|None=None)->dict[str,Any]:
    """Build a new candidate from Verified measured loading records only.

    Rebuild is explicit.  A candidate is promoted only when there is no active
    model yet or its cross-validated MAE is not materially worse than the active
    version (2% tolerance).  Worse candidates remain stored for audit/manual
    promotion instead of silently replacing the active model.
    """
    rows=experimental_data.list_records('loading',db_path,statuses=['verified'])
    frame=pd.DataFrame(rows)
    if not frame.empty:
        if 'outlier_flag' in frame.columns:
            frame=frame[frame['outlier_flag'].fillna(0).astype(int)==0].copy()
        frame['loading_rate_mmol_g']=pd.to_numeric(frame['loading_rate_mmol_g'],errors='coerce')
        frame=frame.dropna(subset=['loading_rate_mmol_g'])
    if len(frame)<12 or (0 if frame.empty else frame['loading_rate_mmol_g'].nunique())<3:
        return {'built':False,'reason':'At least 12 Verified loading records with 3 distinct measured loading values are required.','training_count':int(len(frame))}
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.model_selection import KFold, cross_val_predict
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder
        import joblib
    except ImportError as exc:
        return {'built':False,'reason':f'ML dependency unavailable: {exc}','training_count':int(len(frame))}
    categorical=['resin_type','amino_acid_normalized']; numeric=['aa_eq','base_eq','loading_time_h']
    for c in categorical:
        if c not in frame.columns: frame[c]=''
        frame[c]=frame[c].fillna('').astype(str)
    for c in numeric:
        if c not in frame.columns: frame[c]=None
        frame[c]=pd.to_numeric(frame[c],errors='coerce')
    X=frame[categorical+numeric]; y=frame['loading_rate_mmol_g'].astype(float)
    def make_model():
        pre=ColumnTransformer([('cat',OneHotEncoder(handle_unknown='ignore'),categorical),('num',SimpleImputer(strategy='median'),numeric)])
        return Pipeline([('preprocess',pre),('model',RandomForestRegressor(n_estimators=320,max_depth=8,min_samples_leaf=2,random_state=50,n_jobs=1))])
    folds=min(5,len(frame)); cv=KFold(n_splits=folds,shuffle=True,random_state=50)
    pred=cross_val_predict(make_model(),X,y,cv=cv,n_jobs=1)
    mae=float((abs(pred-y.to_numpy())).mean())
    model=make_model(); model.fit(X,y)
    registry_path,active_path=_paths()
    created=datetime.now(timezone.utc).isoformat(timespec='microseconds')
    model_id='loading-rf-v5-'+created.replace(':','').replace('-','').replace('+','_').replace('.','_')
    version_path=_version_model_path(model_id)
    _atomic_joblib_dump(joblib,model,version_path)

    registry=_read_registry(); block=_loading_block(registry)
    versions=[v for v in block.get('versions',[]) if isinstance(v,dict)]
    active_id=str(block.get('active_model_id') or '')
    active_info=next((v for v in versions if str(v.get('model_id') or '')==active_id),None)
    active_mae=None
    if active_info is not None:
        try: active_mae=float(active_info.get('cross_validated_mae_mmol_g'))
        except Exception: active_mae=None
    # If the active alias/version is missing, the candidate may recover the registry.
    active_source=None
    if active_info is not None:
        active_source=active_path.with_name(str(active_info.get('model_file') or ''))
    active_missing=bool(active_info is not None and not ((active_source and active_source.is_file()) or active_path.is_file()))
    promote=(active_info is None) or active_missing or active_mae is None or mae <= active_mae*1.02
    if active_info is None:
        reason='first model'
    elif active_missing:
        reason='active model file missing; candidate promoted as recovery'
    elif active_mae is None:
        reason='active validation metric unavailable'
    elif promote:
        reason=f'candidate CV MAE {mae:.6g} is not worse than active {active_mae:.6g} beyond 2% tolerance'
    else:
        reason=f'candidate CV MAE {mae:.6g} is worse than active {active_mae:.6g}; active model retained'

    info={
        'model_id':model_id,'built':True,'built_at':created,'training_count':int(len(frame)),
        'verified_only':True,'features':categorical+numeric,'target':'loading_rate_mmol_g','cv_folds':folds,
        'cross_validated_mae_mmol_g':mae,'observed_min_mmol_g':float(y.min()),'observed_max_mmol_g':float(y.max()),
        'model_file':version_path.name,'active_alias_file':active_path.name,
        'promoted':bool(promote),'promotion_status':'PROMOTED' if promote else 'CANDIDATE',
        'promotion_reason':reason,'compared_to_model_id':str((active_info or {}).get('model_id') or ''),
        'compared_to_mae_mmol_g':active_mae,
        'note':'Verified measured results only. Rebuild is explicit; no result entry triggers retraining. Apply remains historical-evidence bounded.',
    }
    block['versions']=[v for v in versions if str(v.get('model_id') or '')!=model_id]
    block['versions'].append(info)
    if promote:
        _atomic_joblib_dump(joblib,model,active_path)
        block['active_model_id']=model_id
    _write_registry(registry)
    result=dict(info); result['version_count']=len(block['versions']); result['active']=bool(promote)
    result['active_model_id']=str(block.get('active_model_id') or '')
    return result


def promote_latest_loading_candidate()->dict[str,Any]:
    """Explicitly activate the newest stored non-active loading model candidate."""
    data=_read_registry(); block=_loading_block(data)
    active=str(block.get('active_model_id') or '')
    candidates=[v for v in block.get('versions',[]) if isinstance(v,dict) and str(v.get('model_id') or '')!=active and v.get('built')]
    if not candidates:
        return {'activated':False,'reason':'No stored non-active loading model candidate is available.'}
    return activate_loading_model(str(candidates[-1].get('model_id') or ''))

def activate_loading_model(model_id:str)->dict[str,Any]:
    registry=_read_registry(); block=_loading_block(registry)
    versions=[v for v in block.get('versions',[]) if isinstance(v,dict)]
    selected=next((v for v in versions if str(v.get('model_id') or '')==str(model_id)),None)
    if selected is None: return {'activated':False,'reason':'Requested loading model version was not found.','model_id':model_id}
    try:
        import joblib
        _,active_path=_paths(); source=active_path.with_name(str(selected.get('model_file') or ''))
        if not source.is_file(): return {'activated':False,'reason':'Stored model file is missing.','model_id':model_id}
        model=joblib.load(source); _atomic_joblib_dump(joblib,model,active_path)
    except Exception as exc:
        return {'activated':False,'reason':f'Could not activate stored model: {exc}','model_id':model_id}
    block['active_model_id']=str(selected.get('model_id') or ''); _write_registry(registry)
    info=dict(selected); info.update({'activated':True,'active':True,'version_count':len(versions),'active_model_id':block['active_model_id']})
    return info


def rollback_loading_model()->dict[str,Any]:
    registry=_read_registry(); block=_loading_block(registry)
    versions=[v for v in block.get('versions',[]) if isinstance(v,dict)]
    if len(versions)<2: return {'activated':False,'reason':'No earlier loading model version is available.'}
    active=str(block.get('active_model_id') or '')
    index=next((i for i,v in enumerate(versions) if str(v.get('model_id') or '')==active),len(versions)-1)
    if index<=0: return {'activated':False,'reason':'The oldest stored loading model is already active.'}
    return activate_loading_model(str(versions[index-1].get('model_id') or ''))


def predict_loading(*,resin:str,amino_acid:str,aa_eq:Any=None,base_eq:Any=None,loading_time_h:Any=None)->dict[str,Any]:
    info=loading_model_info()
    if not info or not info.get('built'):
        return {'available':False,'prediction':None,'model':info}
    _,active_path=_paths()
    source=active_path.with_name(str(info.get('model_file') or ''))
    if not source.is_file(): source=active_path
    if not source.is_file(): return {'available':False,'prediction':None,'model':info,'warning':'Registered model file is missing.'}
    try:
        import joblib
        model=joblib.load(source)
        query=pd.DataFrame([{'resin_type':experimental_data.normalize_resin(resin),'amino_acid_normalized':experimental_data.normalize_amino_acid(amino_acid),'aa_eq':aa_eq,'base_eq':base_eq,'loading_time_h':loading_time_h}])
        pred=float(model.predict(query)[0])
        if not math.isfinite(pred): raise ValueError('Non-finite model prediction')
        return {'available':True,'prediction':max(0.0,pred),'model':info}
    except Exception as exc:
        return {'available':False,'prediction':None,'model':info,'warning':str(exc)}


__all__=['loading_model_info','loading_rebuild_status','loading_model_history','rebuild_loading_model','activate_loading_model','promote_latest_loading_candidate','rollback_loading_model','predict_loading']
