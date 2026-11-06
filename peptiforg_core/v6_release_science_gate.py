from __future__ import annotations
"""Evidence-based V6 scientific gate: no default PASS and no inferred measurements."""
import hashlib
import json
from pathlib import Path

CHECKS = (
    'v5_regression', 'modified_peptide_regression', 'version_metadata',
    'independent_split', 'leakage_audit', 'ranker_holdout',
    'native_v2_benchmark', 'uncertainty_ood', 'backend_absence',
    'windows_ui', 'package_hygiene', 'scientific_claims',
)


def audit_science_evidence(evidence_path, output_path):
    source = Path(evidence_path)
    evidence = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(evidence, dict) or set(evidence) - set(CHECKS):
        raise ValueError('Evidence must be an object with recognized check IDs only')
    checks = {}
    for key in CHECKS:
        item = evidence.get(key)
        if not isinstance(item, dict):
            checks[key] = {'status': 'MISSING', 'reason': 'No evidence supplied'}
            continue
        status = item.get('status')
        artifact = str(item.get('artifact', '')).strip()
        expected_hash = str(item.get('sha256', '')).lower().strip()
        reason = str(item.get('reason', '')).strip()
        if status != 'PASS':
            checks[key] = {'status': 'NOT_VERIFIED', 'reason': reason or 'No passing verification'}
            continue
        if not artifact or len(expected_hash) != 64 or any(x not in '0123456789abcdef' for x in expected_hash):
            checks[key] = {'status': 'FAIL', 'reason': 'PASS requires an existing artifact and SHA-256'}
            continue
        candidate = (source.parent / artifact).resolve()
        if not candidate.is_file():
            checks[key] = {'status': 'FAIL', 'reason': 'Evidence artifact not found'}
            continue
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        checks[key] = {'status': 'PASS' if observed == expected_hash else 'FAIL',
                       'artifact': artifact, 'sha256': observed,
                       'reason': 'Artifact hash verified; scientific validity requires external review' if observed == expected_hash else 'Hash mismatch'}
    passed = sum(x['status'] == 'PASS' for x in checks.values())
    result = {'protocol': 'v6-scientific-release-gate-1',
              'status': 'EVIDENCE_PRESENT_REQUIRES_REVIEW' if passed == len(CHECKS) else 'NOT_READY',
              'checks_passed': passed, 'checks_required': len(CHECKS),
              'scientific_validation': 'NOT_AUTOMATICALLY_CERTIFIED',
              'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'checks': checks}
    dest = Path(output_path); dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def write_template(path):
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({k: {'status': 'NOT_VERIFIED', 'reason': 'Provide externally verified real execution output'} for k in CHECKS}, indent=2) + '\n', encoding='utf-8')
    return output
