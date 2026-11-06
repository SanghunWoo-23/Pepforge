from __future__ import annotations
"""Strict chemical parameter evidence registry. This registry does not generate parameters."""
import hashlib
import json
import re
from pathlib import Path

_SHA = re.compile(r'^[0-9a-f]{64}$')


def audit_registry(source_path, output_path):
    source = Path(source_path)
    records = json.loads(source.read_text(encoding='utf-8'))
    if not isinstance(records, list): raise ValueError('Registry must be a JSON array')
    used = set(); assessed = []
    for item in records:
        if not isinstance(item, dict): raise ValueError('Registry items must be objects')
        identity = str(item.get('canonical_identity') or '').strip()
        if not identity or identity in used: raise ValueError('Missing or repeated canonical identity')
        used.add(identity)
        required = ('attachment_graph_sha256', 'coordinate_template_sha256',
                    'forcefield_name', 'parameter_file_sha256', 'charge_provenance',
                    'atom_typing_provenance', 'validation_report_sha256')
        missing = [field for field in required if not str(item.get(field) or '').strip()]
        for field in required:
            if field.endswith('_sha256') and item.get(field) and not _SHA.fullmatch(str(item[field]).lower()):
                missing.append(field + '_INVALID_HASH')
        level = str(item.get('validation_level') or 'unverified').lower()
        if level not in ('unverified', 'documented', 'validated'):
            raise ValueError('Unsupported validation_level')
        # Metadata hashes represent claims, not file verification. No amount of
        # self-declared evidence is sufficient to mark a forcefield as verified.
        assessed.append({'canonical_identity': identity, 'status': 'EXTERNAL_REVIEW_REQUIRED' if not missing and level == 'validated' else 'UNSUPPORTED',
                         'missing_or_invalid_fields': sorted(set(missing)),
                         'forcefield_ready': False,
                         'note': 'Metadata only. Force-field parameter files and scientific validation must be independently verified.'})
    result = {'protocol': 'v6-parameter-registry-audit-1', 'status': 'METADATA_AUDIT_ONLY',
              'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'records': assessed}
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return result
