"""Validation-only Platt scaling for existing held-out ranker predictions.

No docking or affinity claims. The test partition is never used for fitting.
"""
from __future__ import annotations
import csv, hashlib, json, math
from pathlib import Path
from .v6_ranker_validation import _metrics, _binary, _prob


def _logit(p):
    p = min(1 - 1e-8, max(1e-8, p))
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-max(-40., min(40., x))))


def calibrate_predictions(input_csv, output_json, output_csv, *, iterations=1200, learning_rate=0.03, l2=0.01):
    if not 1 <= iterations <= 100000 or not 0 < learning_rate <= 0.2 or not 0 <= l2 <= 10:
        raise ValueError('invalid optimizer settings')
    src = Path(input_csv)
    with src.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required={'candidate_id','family_id','split','label','prediction','ood'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError('missing required input columns')
        raw = list(reader)
    if not raw: raise ValueError('empty calibration dataset')
    ids=set(); family_split={}; rows=[]
    for line, item in enumerate(raw,2):
        candidate=(item['candidate_id'] or '').strip()
        family=(item['family_id'] or '').strip()
        split=(item['split'] or '').strip().lower()
        if not candidate or not family or candidate in ids or split not in ('train','validation','test'):
            raise ValueError(f'row {line}: invalid candidate/family/split or duplicate')
        if family in family_split and family_split[family]!=split:
            raise ValueError(f'row {line}: family-level split leakage')
        ids.add(candidate); family_split[family]=split
        rows.append(dict(candidate_id=candidate,family_id=family,split=split,label=_binary(item['label'],'label'),probability=_prob(item['prediction']),ood=_binary(item['ood'],'ood')))
    val=[r for r in rows if r['split']=='validation']
    test=[r for r in rows if r['split']=='test']
    if len(val)<10 or len({r['family_id'] for r in val})<2 or len({r['label'] for r in val})<2:
        raise ValueError('validation requires >=10 observations, >=2 families and both labels')
    if len(test)<1: raise ValueError('independent test rows required')
    # Two-parameter sigmoid map fit only to validation split.
    a,b=1.,0.
    for _ in range(iterations):
        ga=gb=0.
        for r in val:
            x=_logit(r['probability'])
            d=_sigmoid(a*x+b)-r['label']
            ga+=d*x;gb+=d
        ga=ga/len(val)+l2*(a-1)
        gb=gb/len(val)+l2*b
        a=max(-10.,min(10.,a-learning_rate*ga))
        b=max(-10.,min(10.,b-learning_rate*gb))
    transformed=[dict(r, calibrated=_sigmoid(a*_logit(r['probability'])+b)) for r in test]
    base=_metrics(test,10)
    adjusted=_metrics([dict(r,probability=r['calibrated']) for r in transformed],10)
    result={'protocol':'v6-validation-only-platt-1','input_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
            'validation_rows':len(val),'validation_families':len({r['family_id'] for r in val}),
            'test_rows':len(test),'test_families':len({r['family_id'] for r in test}),
            'coefficients':{'slope':a,'intercept':b},'raw_test_metrics':base,
            'calibrated_test_metrics':adjusted,'trained_on':'validation only',
            'warning':'Post-hoc calibration of supplied probabilities only; no new docking, MD or ranker model was trained. Independent external validation remains necessary.'}
    jout=Path(output_json); cout=Path(output_csv)
    if jout.resolve()==cout.resolve() or jout.resolve()==src.resolve() or cout.resolve()==src.resolve():
        raise ValueError('outputs must not overwrite inputs or each other')
    jout.parent.mkdir(parents=True,exist_ok=True); cout.parent.mkdir(parents=True,exist_ok=True)
    # Construct all results before writing and use atomic replacements.
    import os, tempfile
    def atomic(path,content):
        fd,name=tempfile.mkstemp(prefix='.pepforge-',dir=str(path.parent),text=True)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as f: f.write(content)
            os.replace(name,path)
        finally:
            if os.path.exists(name): os.unlink(name)
    import io
    buf=io.StringIO(newline='')
    writer=csv.DictWriter(buf,fieldnames=['candidate_id','family_id','label','ood','prediction','calibrated_prediction'])
    writer.writeheader()
    for r in transformed:
        writer.writerow(dict(candidate_id=r['candidate_id'],family_id=r['family_id'],label=r['label'],ood=r['ood'],prediction=r['probability'],calibrated_prediction=r['calibrated']))
    atomic(cout,buf.getvalue())
    atomic(jout,json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    return result
