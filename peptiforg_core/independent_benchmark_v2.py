from __future__ import annotations

"""Conservative V6 benchmark split with explicit evidence and fail-closed guards.

Global sequence identity is calculated from a deterministic Needleman-Wunsch
alignment. Identity = exact aligned matches / max(sequence lengths), with gaps
counted against identity. This is a screening metric, not an evolutionary
homology or receptor-family classification. Family assignments must be supplied.
"""

from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import random

PROTOCOL_VERSION = "0.1.0-dev"
SPLITS = ("train", "validation", "test")


def sequence_identity(a: str, b: str) -> float:
    a, b = a.upper().strip(), b.upper().strip()
    if not a or not b or any(x not in "ACDEFGHIKLMNPQRSTVWY" for x in a+b):
        raise ValueError("Sequences must be nonempty standard 20-AA sequences")
    # maximize matches first, then discourage gap proliferation: score +2/-1/-2
    prev = [(j * -2, 0) for j in range(len(b)+1)]
    for i, x in enumerate(a, 1):
        curr = [(i * -2, 0)]
        for j, y in enumerate(b, 1):
            candidates = [
                (prev[j-1][0] + (2 if x == y else -1), prev[j-1][1] + int(x == y)),
                (prev[j][0]-2, prev[j][1]),
                (curr[j-1][0]-2, curr[j-1][1]),
            ]
            curr.append(max(candidates))
        prev = curr
    return prev[-1][1] / max(len(a),len(b))


class _Union:
    def __init__(self, keys): self.parent = {k:k for k in keys}
    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x=self.parent[x]
        return x
    def join(self, x, y): self.parent[self.find(y)] = self.find(x)


def build_independent_split(manifest_csv: str | Path, output_dir: str | Path, *,
                            identity_threshold: float = 0.30, seed: int = 42) -> dict:
    """Create split candidates; PASS means guard compliance, not predictive performance.

    Required CSV columns: target_id, receptor_sequence, receptor_family,
    receptor_accession. Family labels must come from independent annotation.
    """
    if not 0 < identity_threshold <= 1: raise ValueError("identity_threshold must be in (0,1]")
    path = Path(manifest_csv)
    with path.open(encoding="utf-8-sig", newline="") as fh: rows = list(csv.DictReader(fh))
    required={"target_id","receptor_sequence","receptor_family","receptor_accession"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Manifest must have rows and columns: " + ', '.join(sorted(required)))
    normalized=[]; ids=set()
    for raw in rows:
        r={k:(raw.get(k) or '').strip() for k in required}
        if any(not v for v in r.values()): raise ValueError("Missing mandatory evidence for " + str(r.get("target_id")))
        if r['target_id'] in ids: raise ValueError("Duplicate target_id: " + r['target_id'])
        ids.add(r['target_id'])
        sequence_identity(r['receptor_sequence'],r['receptor_sequence'])
        normalized.append(r)
    normalized.sort(key=lambda r:r['target_id'])
    u=_Union(ids); comparisons=0; edges=[]
    for i,a in enumerate(normalized):
        for b in normalized[i+1:]:
            shared_evidence = (a['receptor_family'] == b['receptor_family'] or
                               a['receptor_accession'] == b['receptor_accession'])
            identity=sequence_identity(a['receptor_sequence'],b['receptor_sequence'])
            comparisons+=1
            if shared_evidence or identity >= identity_threshold:
                u.join(a['target_id'],b['target_id'])
                edges.append({'a':a['target_id'],'b':b['target_id'],
                              'identity':round(identity,6), 'shared_annotation':shared_evidence})
    groups=defaultdict(list)
    for r in normalized: groups[u.find(r['target_id'])].append(r)
    clusters=sorted(groups.values(),key=lambda g:min(x['target_id'] for x in g))
    rng=random.Random(seed); rng.shuffle(clusters)
    # Assign whole clusters greedily to approx 60/20/20 proportions.
    desired=[.6*len(rows),.2*len(rows),.2*len(rows)]; counts=[0,0,0]
    assigned={}
    for group in clusters:
        options=sorted(range(3),key=lambda k:(counts[k]/desired[k],k))
        chosen=options[0]
        for r in group: assigned[r['target_id']]=SPLITS[chosen]
        counts[chosen]+=len(group)
    verdict='PASS' if all(counts) else 'INSUFFICIENT_INDEPENDENT_CLUSTERS'
    report={'protocol':PROTOCOL_VERSION,'status':verdict,
            'scientific_performance':'NOT_EVALUATED',
            'identity_definition':'global NW alignment matches/max sequence length (gap penalized)',
            'threshold':identity_threshold,'seed':seed,'records':len(rows),
            'cluster_count':len(clusters),'pair_comparisons':comparisons,
            'counts':dict(zip(SPLITS,counts)),'cross_split_guard_edges':edges,
            'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'assignments':[{'target_id':r['target_id'],'split':assigned[r['target_id']],
                           'cluster':u.find(r['target_id'])} for r in normalized]}
    # verify that no linked evidence crossed a split
    report['cross_split_violations']=[e for e in edges if assigned[e['a']] != assigned[e['b']]]
    if report['cross_split_violations']: report['status']='FAIL'
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'independent_split_audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (out/'independent_splits.csv').open('w',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['target_id','split','cluster']); w.writeheader(); w.writerows(report['assignments'])
    return report
