"""Strict, dependency-free held-out ranker probability evaluation.

Scores must already be predicted and exported. This module does NOT train models,
calibrate predictions, or claim that the probabilities are calibrated.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def _binary(raw, field):
    if str(raw).strip() not in ('0', '1'):
        raise ValueError(f'{field} must be 0 or 1')
    return int(raw)


def _prob(raw):
    try:
        p = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('prediction must be numeric') from exc
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('prediction must be finite and between 0 and 1')
    return p


def _auc(labels, probabilities):
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    pairs = sorted(zip(probabilities, labels), key=lambda t: t[0])
    rank_sum = 0.0
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[i][0] == pairs[j][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        rank_sum += avg_rank * sum(y for _, y in pairs[i:j])
        i = j
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _metrics(rows, bins):
    y = [r['label'] for r in rows]
    p = [r['probability'] for r in rows]
    n = len(rows)
    if not n:
        return {'count': 0, 'auroc': None, 'brier': None, 'ece': None}
    brier = sum((a-b)**2 for a,b in zip(p,y))/n
    occupied = defaultdict(list)
    for a,b in zip(p,y):
        bucket = min(int(a*bins), bins - 1)
        occupied[bucket].append((a,b))
    ece = sum(len(items)/n * abs(sum(a for a,_ in items)/len(items) - sum(b for _,b in items)/len(items)) for items in occupied.values())
    return {'count': n, 'positives': sum(y), 'negatives': n-sum(y),
            'auroc': _auc(y,p), 'brier': round(brier,8), 'ece': round(ece,8)}


def evaluate_ranker(input_csv, output_json, *, bins=10, minimum_test_rows=20,
                    minimum_test_families=5, strict=True):
    if not 2 <= bins <= 100:
        raise ValueError('bins must be between 2 and 100')
    if minimum_test_rows < 1 or minimum_test_families < 1:
        raise ValueError('minimum counts must be positive')
    source = Path(input_csv)
    with source.open(encoding='utf-8-sig',newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'candidate_id','family_id','split','label','prediction','ood'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f'missing required columns: {sorted(required-set(reader.fieldnames or []))}')
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError('empty input')
    rows=[]; seen=set(); splits_by_family=defaultdict(set)
    for line, r in enumerate(raw_rows,start=2):
        candidate = (r['candidate_id'] or '').strip()
        family = (r['family_id'] or '').strip()
        split = (r['split'] or '').strip().lower()
        if not candidate or not family:
            raise ValueError(f'row {line}: candidate and family IDs required')
        if candidate in seen:
            raise ValueError(f'row {line}: duplicate candidate_id {candidate}')
        if split not in ('train','validation','test'):
            raise ValueError(f'row {line}: invalid split')
        seen.add(candidate)
        splits_by_family[family].add(split)
        rows.append({'candidate_id':candidate, 'family_id':family, 'split':split,
                     'label':_binary(r['label'],'label'), 'probability':_prob(r['prediction']),
                     'ood':_binary(r['ood'],'ood')})
    leaks = {family:sorted(splits) for family,splits in splits_by_family.items() if len(splits)>1}
    if leaks:
        raise ValueError('family-level split leakage: '+json.dumps(leaks,ensure_ascii=False,sort_keys=True))
    test=[r for r in rows if r['split']=='test']
    if not test:
        raise ValueError('no test rows; held-out evaluation impossible')
    families=len({r['family_id'] for r in test})
    safeguards = {'minimum_test_rows_met':len(test)>=minimum_test_rows,
                  'minimum_test_families_met':families>=minimum_test_families,
                  'both_test_classes_present':len({r['label'] for r in test})==2,
                  'family_split_leakage_absent':True}
    if strict and not all(safeguards.values()):
        raise ValueError('release-level evaluation safeguards failed: '+json.dumps(safeguards,sort_keys=True))
    result={'protocol':'v6-ranker-heldout-1',
            'evaluation_only':True,
            'claim':'Held-out binary endpoint discrimination/calibration diagnostics only; not affinity or validated prediction accuracy.',
            'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'test_families':families,'safeguards':safeguards,
            'test_metrics':_metrics(test,bins),
            'test_subgroups':{'in_domain':_metrics([r for r in test if r['ood']==0],bins),
                              'out_of_domain':_metrics([r for r in test if r['ood']==1],bins)},
            'warning':'ECE and Brier are diagnostics; no calibration was performed. AUROC undefined for single-class subgroups.'}
    destination=Path(output_json)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result
