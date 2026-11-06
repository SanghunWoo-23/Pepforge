"""Paired, out-of-sample V5/V6 evaluation. Never substitutes for executed docking.

Input schema: target_id, split, baseline_success, candidate_success, family.
Each success is externally measured 0/1 for the SAME pre-registered endpoint.
No metrics are claimed without traceable input measurements.
"""
from __future__ import annotations
import csv, hashlib, json, math, random
from collections import defaultdict
from pathlib import Path

PROTOCOL = '6.0.0-dev-paired-benchmark-1'
REQUIRED = ('target_id', 'split', 'baseline_success', 'candidate_success', 'family')

def _success(value, label):
    if str(value).strip() not in ('0', '1'):
        raise ValueError(f'{label} must be 0 or 1, not {value!r}')
    return int(value)

def evaluate_paired(input_csv, output_json, *, seed=42, bootstrap_replicates=2000,
                    split='test', minimum_targets=20, minimum_families=5):
    """Cluster bootstrap by receptor family, avoiding false precision per complex.

    Test rows must be independently held out; this function audits labels but
    cannot verify their training provenance. It never declares a release PASS.
    """
    if bootstrap_replicates < 100 or minimum_targets < 1 or minimum_families < 1:
        raise ValueError('invalid evaluation policy')
    if split not in ('train', 'validation', 'test'):
        raise ValueError('unsupported split')
    path = Path(input_csv)
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or not set(REQUIRED).issubset(reader.fieldnames):
            raise ValueError('missing required columns: '+', '.join(REQUIRED))
        raw=list(reader)
    if not raw: raise ValueError('empty benchmark')
    seen=set(); records=[]
    for row in raw:
        target=(row.get('target_id') or '').strip()
        family=(row.get('family') or '').strip()
        row_split=(row.get('split') or '').strip().lower()
        if not target or not family or row_split not in ('train','validation','test'):
            raise ValueError('target, family, and recognized split are required')
        if target in seen: raise ValueError('duplicate target_id: '+target)
        seen.add(target)
        b=_success(row.get('baseline_success'), 'baseline_success')
        c=_success(row.get('candidate_success'), 'candidate_success')
        if row_split==split: records.append((target,family,b,c))
    records.sort()
    if not records: raise ValueError('no records for requested split')
    n=len(records); base=sum(x[2] for x in records)/n; cand=sum(x[3] for x in records)/n
    families=defaultdict(list)
    for item in records: families[item[1]].append(item)
    names=sorted(families)
    rng=random.Random(seed)
    deltas=[]
    for _ in range(bootstrap_replicates):
        sampled=[x for name in (names[rng.randrange(len(names))] for __ in names) for x in families[name]]
        deltas.append(sum(x[3]-x[2] for x in sampled)/len(sampled))
    deltas.sort()
    lo=deltas[math.floor((len(deltas)-1)*0.025)]
    hi=deltas[math.ceil((len(deltas)-1)*0.975)]
    sufficient=n>=minimum_targets and len(names)>=minimum_families
    result={
        'protocol':PROTOCOL,'status':'EVALUATED_NOT_RELEASE_CERTIFIED' if sufficient else 'INSUFFICIENT_EVALUATION_COVERAGE',
        'release_approved':False, 'split':split,'target_count':n,'family_count':len(names),
        'baseline_success_rate':round(base,6),'candidate_success_rate':round(cand,6),
        'paired_delta':round(cand-base,6),'family_bootstrap_95pct_delta_interval':[round(lo,6),round(hi,6)],
        'baseline_only_successes':sum(b==1 and c==0 for _,_,b,c in records),
        'candidate_only_successes':sum(c==1 and b==0 for _,_,b,c in records),
        'both_successes':sum(b==1 and c==1 for _,_,b,c in records),
        'both_failures':sum(b==0 and c==0 for _,_,b,c in records),
        'policy':{'min_targets':minimum_targets,'min_families':minimum_families,'bootstrap_replicates':bootstrap_replicates,'seed':seed},
        'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'limitations':['Input outcomes are user-supplied and not independently verified.',
                       'Split labels alone cannot establish training/test independence.',
                       'Bootstrap interval is descriptive, not proof of generalization.',
                       'Endpoint definition and registered test protocol must be supplied separately.',
                       'A positive paired difference does not prove statistical or scientific superiority.'],
    }
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result
