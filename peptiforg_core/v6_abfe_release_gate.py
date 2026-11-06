"""Conservative ABFE release gate: never equate an OpenFE estimate with validation.

A report is REVIEW_REQUIRED until independently generated replica and experimental
reference evidence is reviewed. This module does not synthesize measurements.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_result(result_file, *, min_repeats=3):
    from peptiforg_core.v6_openfe_result_runner import inspect_openfe_result, OpenFERunError
    path = Path(result_file)
    preliminary = inspect_openfe_result(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    findings = []
    raw = data.get('protocol_result', {})
    if not isinstance(raw, dict):
        raise OpenFERunError('protocol_result must be structured data')
    for name in ('estimate', 'uncertainty'):
        q = data[name]
        if not isinstance(q, dict):
            raise OpenFERunError(f'{name}: invalid quantity')
        magnitude = q.get('magnitude')
        if magnitude is not None:
            if isinstance(magnitude, bool) or not isinstance(magnitude, (int,float)) or not math.isfinite(magnitude):
                raise OpenFERunError(f'{name}: non-finite magnitude')
            if name == 'uncertainty' and magnitude < 0:
                raise OpenFERunError('negative uncertainty')
        if not (q.get('unit') or q.get('units')):
            findings.append(f'{name}: unit serialization not independently verified')
    repeats = raw.get('n_protocol_dag_results')
    if not isinstance(repeats, int) or isinstance(repeats,bool) or repeats < min_repeats:
        findings.append('Independent repeat count not demonstrably sufficient')
    # Do not treat numerical success as proof of convergence or experimental accuracy.
    findings.extend([
        'Complex and solvent MBAR overlap and per-leg diagnostics require inspection',
        'Restraint geometry, chemical parameterization, and charge-state consistency require inspection',
        'Structural trajectory convergence and external experimental comparison remain unverified',
    ])
    return {'status':'REVIEW_REQUIRED','result_sha256':_hash(path),
            'openfe_result_status':preliminary['status'], 'repeat_count_reported':repeats,
            'review_findings':findings,'scientific_accuracy_certified':False}
