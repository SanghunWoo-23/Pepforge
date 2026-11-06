from __future__ import annotations
"""Tamper-evident benchmark split lock and holdout overlap guard.

This is a local immutable-reference checker, not proof of blind experimental conduct.
A previously published checksum must be retained independently to establish blinding.
"""
import csv
import hashlib
import json
from pathlib import Path

SPLITS = {'train', 'validation', 'test'}


def _load(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows or not {'target_id','split','cluster'}.issubset(rows[0]):
        raise ValueError('Require non-empty target_id,split,cluster CSV')
    ids=set(); clusters={}; result=[]
    for row in rows:
        tid=str(row.get('target_id') or '').strip()
        cluster=str(row.get('cluster') or '').strip()
        split=str(row.get('split') or '').strip().lower()
        if not tid or not cluster or split not in SPLITS or tid in ids:
            raise ValueError('Missing/invalid split fields or duplicate target')
        if cluster in clusters and clusters[cluster] != split:
            raise ValueError('One receptor cluster assigned to multiple splits')
        ids.add(tid); clusters[cluster]=split
        result.append((tid,split,cluster))
    return sorted(result)


def _digest(rows):
    payload=json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()
    return hashlib.sha256(payload).hexdigest()


def create_lock(split_csv, output_json):
    rows=_load(split_csv)
    if set(r[1] for r in rows) != SPLITS:
        raise ValueError('Cannot lock without all train/validation/test partitions')
    result={'protocol':'v6-blind-split-lock-1', 'assignments_sha256':_digest(rows),
            'counts':{split:sum(r[1]==split for r in rows) for split in sorted(SPLITS)},
            'locked_target_ids':[r[0] for r in rows],
            'note':'Store this record independently BEFORE analysis; creation alone is not proof of blinding.'}
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def verify_lock(split_csv, lock_json, output_json):
    rows=_load(split_csv)
    lock=json.loads(Path(lock_json).read_text(encoding='utf-8'))
    expected=str(lock.get('assignments_sha256') or '')
    observed=_digest(rows)
    result={'protocol':'v6-blind-split-lock-1','status':'MATCH' if expected==observed else 'FAIL',
            'expected_sha256':expected,'observed_sha256':observed,
            'claim':'Checks assignment integrity only, not independence or prospective blinding.'}
    out=Path(output_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
