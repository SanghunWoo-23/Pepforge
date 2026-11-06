"""Strict V5/V6 paired result input audit for scientific evaluation.

It validates case pairing and provenance, but does not perform docking or infer
accuracy from arbitrary scores.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

FIELDS = ('case_id', 'target_id', 'split', 'success')
SPLITS = {'train', 'validation', 'test', 'external'}


def read_rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as fd:
        reader = csv.DictReader(fd)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in FIELDS):
            raise ValueError('Required CSV columns: '+', '.join(FIELDS))
        cases = {}
        for line, row in enumerate(reader, 2):
            key = str(row['case_id']).strip()
            target = str(row['target_id']).strip()
            split = str(row['split']).strip().lower()
            outcome = str(row['success']).strip()
            if not key or not target or split not in SPLITS or outcome not in {'0', '1'}:
                raise ValueError(f'Invalid required value at line {line}')
            if key in cases:
                raise ValueError(f'Duplicate case_id: {key}')
            cases[key] = {'target_id': target, 'split': split, 'success': int(outcome)}
    if not cases:
        raise ValueError('Empty results file')
    return cases


def audit(base_path, candidate_path):
    a, b = read_rows(base_path), read_rows(candidate_path)
    if set(a) != set(b):
        raise ValueError(f'Unpaired case IDs (V5-only={len(set(a)-set(b))}, V6-only={len(set(b)-set(a))})')
    for key in a:
        if a[key]['target_id'] != b[key]['target_id'] or a[key]['split'] != b[key]['split']:
            raise ValueError(f'Target or split mismatch: {key}')
    splits = {}
    target_splits = {}
    for key, entry in a.items():
        target_splits.setdefault(entry['target_id'], set()).add(entry['split'])
        s = splits.setdefault(entry['split'], {'cases': 0, 'v5_successes': 0, 'v6_successes': 0, 'improved': 0, 'regressed': 0})
        s['cases'] += 1
        s['v5_successes'] += entry['success']
        s['v6_successes'] += b[key]['success']
        s['improved'] += int(entry['success'] == 0 and b[key]['success'] == 1)
        s['regressed'] += int(entry['success'] == 1 and b[key]['success'] == 0)
    leaked = sorted(k for k, v in target_splits.items() if len(v)>1)
    if leaked:
        raise ValueError('Target IDs span multiple splits: '+', '.join(leaked[:10]))
    for group in splits.values():
        n = group['cases']
        group['v5_success_rate'] = group['v5_successes']/n
        group['v6_success_rate'] = group['v6_successes']/n
        group['delta_success_rate'] = (group['v6_successes']-group['v5_successes'])/n
    hashes = {label: hashlib.sha256(Path(path).read_bytes()).hexdigest() for label, path in [('v5', base_path), ('v6', candidate_path)]}
    return {'schema':'pepforge.v6.paired_benchmark_audit.v1', 'case_count':len(a),
            'splits':splits, 'file_sha256':hashes,
            'provenance_note':'Outcomes are supplied by the user; no docking executed or accuracy independently verified.',
            'scientific_validation':'REQUIRES_INDEPENDENT_EVIDENCE'}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--v5', required=True, type=Path)
    ap.add_argument('--v6', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args=ap.parse_args(argv)
    try:
        report=audit(args.v5,args.v6)
    except (OSError, ValueError) as err:
        ap.error(str(err))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Paired benchmark inputs audited:', report['case_count'], 'cases')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
