"""Independent, read-only integrity audit of a Pepforge ensemble run.

A successful hash audit attests stored bytes only; it does not prove docking
accuracy, valid chemistry, or experimental affinity.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def _digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit_ensemble_run(directory: str | Path) -> dict:
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Run location must be a directory')
    manifest = root / 'ensemble_docking_report.json'
    report = json.loads(manifest.read_text(encoding='utf-8'))
    if report.get('schema') != 'pepforge.v6.ensemble_docking.v1':
        raise ValueError('Unsupported ensemble report schema')
    checks = []

    def check(label: str, filename: str, expected: str):
        requested = Path(filename)
        path = requested if requested.is_absolute() else root / requested
        resolved = path.resolve()
        # Guard against malicious or stale manifests referring outside the run.
        inside = resolved.is_relative_to(root)
        exists = inside and resolved.is_file() and not path.is_symlink()
        observed = _digest(resolved) if exists else None
        valid = bool(exists and isinstance(expected, str) and observed == expected)
        checks.append({'label': label, 'path': str(requested), 'exists_inside_run': bool(exists),
                       'hash_matches': valid, 'expected_sha256': expected, 'observed_sha256': observed})

    inputs = report.get('inputs', {})
    for filename_key, sha_key in [('receptor_snapshot', 'receptor_sha256'),
                                  ('peptide_snapshot', 'peptide_sdf_sha256')]:
        check(filename_key, inputs.get(filename_key, ''), inputs.get(sha_key))
    ff = report.get('force_field')
    if ff:
        check('force_field_report', ff.get('report_path', ''), ff.get('report_sha256'))
    runs = report.get('runs', [])
    for i, row in enumerate(runs):
        base = f'conformer_{i+1}'
        sdf = root / f'conformer_{i+1:03d}' / 'peptide.sdf'
        check(base + '_sdf', str(sdf), row.get('sdf_sha256'))
        if row.get('manifest'):
            check(base + '_docking_manifest', row['manifest'], row.get('manifest_sha256'))
        if row.get('pymol_script'):
            check(base + '_pymol_script', row['pymol_script'], row.get('pymol_script_sha256'))
    count = sum(row.get('status') == 'COMPLETED' for row in runs)
    consistent = count == report.get('successful_conformers') and len(runs) - count == report.get('failed_conformers')
    if report.get('status') == 'COMPLETED':
        consistent = consistent and bool(runs) and count == len(runs)
    return {'status': 'PASS' if checks and all(c['hash_matches'] for c in checks) and consistent else 'FAIL',
            'run_status': report.get('status'), 'checks': checks, 'counts_consistent': consistent,
            'meaning': 'Integrity only; does not establish accuracy or force-field validity'}
