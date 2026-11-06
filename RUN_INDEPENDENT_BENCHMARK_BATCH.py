"""Receptor-aligned docking benchmark with case and family bootstrap intervals.

Independence is a provenance claim requiring external dataset audits, not just a
CSV split label.  Reject reused reference paths and duplicate case identifiers.
"""
import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from peptiforg_core.v6_independent_benchmark import benchmark

REQUIRED = ('case_id', 'family', 'split', 'reference_peptide_pdb',
            'predicted_peptide_pdb', 'reference_receptor_pdb',
            'predicted_receptor_pdb')

def _interval(values, bootstrap, rng):
    if not values:
        raise ValueError('Empty bootstrap population')
    n = len(values)
    scores = sorted(sum(rng.choice(values) for _ in range(n)) / n
                    for _ in range(bootstrap))
    return [scores[int(.025 * (bootstrap - 1))], scores[int(.975 * (bootstrap - 1))]]

def run(manifest, output, bootstrap=2000, seed=2026):
    if type(bootstrap) is not int or not 100 <= bootstrap <= 100000:
        raise ValueError('bootstrap must be 100..100000')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('invalid seed')
    manifest, output = Path(manifest).resolve(), Path(output)
    if output.exists():
        raise FileExistsError('Cannot overwrite existing benchmark')
    with manifest.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(REQUIRED).issubset(reader.fieldnames):
            raise ValueError('Missing required benchmark columns')
        rows = list(reader)
    if not rows:
        raise ValueError('Empty benchmark')
    seen_cases, seen_references = set(), set()
    for r in rows:
        if any(not (r.get(k) or '').strip() for k in REQUIRED):
            raise ValueError('Missing benchmark fields')
        if r['split'].strip() != 'test':
            raise ValueError('Test-only manifest required')
        case = r['case_id'].strip()
        if case in seen_cases:
            raise ValueError('Duplicate case ID')
        seen_cases.add(case)
        ref = tuple(str((manifest.parent / r[k]).resolve()) for k in ('reference_peptide_pdb','reference_receptor_pdb'))
        if ref in seen_references:
            raise ValueError('Reused reference complex; non-independent case')
        seen_references.add(ref)
        for k in REQUIRED[3:]:
            candidate = Path(r[k])
            if not candidate.is_absolute():
                candidate = manifest.parent / candidate
            if not candidate.is_file():
                raise FileNotFoundError(f'{case}: missing {k}: {candidate}')
            r[k] = str(candidate.resolve())
    # Existing evaluator writes a result; use temporary workspace so evaluation
    # failures cannot leave a misleading final report.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='pepforge_benchmark_') as work:
        normalized = Path(work) / 'manifest.csv'
        with normalized.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=reader.fieldnames)
            writer.writeheader(); writer.writerows(rows)
        intermediate = Path(work) / 'result.json'
        report = benchmark(normalized, intermediate)
    cases = report['cases']
    values = [int(c['receptor_aligned_under_2A']) for c in cases]
    families = defaultdict(list)
    for c in cases:
        families[c['family']].append(int(c['receptor_aligned_under_2A']))
    rng = random.Random(seed)
    report['receptor_aligned_success_at_2A'] = sum(values) / len(values)
    report['case_bootstrap_95_percent_CI'] = _interval(values, bootstrap, rng)
    family_names = sorted(families)
    family_means = [sum(families[f]) / len(families[f]) for f in family_names]
    report['family_macro_success_at_2A'] = sum(family_means) / len(family_means)
    report['family_cluster_bootstrap_95_percent_CI'] = _interval(family_means, bootstrap, rng)
    report['family_count'] = len(family_names)
    report['bootstrap_samples'] = bootstrap
    report['bootstrap_seed'] = seed
    report['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    report['independent_dataset_provenance_required'] = True
    report['limitations'].append('Family cluster CI resamples family means; independence from model training must be audited externally')
    if len(family_names) < 5:
        report['limitations'].append('Few families: family bootstrap interval may be unstable')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(output.name + '.tmp')
    if staging.exists():
        raise FileExistsError('Temporary benchmark output already exists')
    try:
        with staging.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write('\n')
        if output.exists():
            raise FileExistsError('Benchmark result appeared during evaluation')
        staging.replace(output)
    finally:
        if staging.exists(): staging.unlink()
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest'); p.add_argument('output')
    p.add_argument('--bootstrap', type=int, default=2000)
    p.add_argument('--seed', type=int, default=2026)
    a = p.parse_args()
    print(json.dumps(run(a.manifest, a.output, a.bootstrap, a.seed), indent=2))
