"""Auditable manual target-chain handoff. Does not run or approve docking."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def _digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare_handoff(project_dir: str | Path, structure: str, chain: str, output_json: str | Path, *, reviewer: str = '', notes: str = '') -> dict:
    from peptiforg_core.v6_target_readiness import inspect_target_project
    root = Path(project_dir).resolve()
    assessment = inspect_target_project(root)  # fresh verification; never trust an old report
    if not isinstance(chain, str) or not chain.strip():
        raise ValueError('Explicit nonempty chain ID required')
    rel = Path(structure)
    if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() not in ('.pdb', '.cif') or rel.parts[0] != 'structures':
        raise ValueError('Structure must be a safe relative path inside structures/')
    selected = next((s for s in assessment['structures'] if s['path'] == rel.as_posix()), None)
    if selected is None:
        raise ValueError('Requested structure not found in verified import manifest')
    if not selected['sha256_verified'] or selected['warnings']:
        raise ValueError('Structure has integrity or parsing warnings; handoff blocked')
    matching = [c for c in selected['chains'] if c['chain_id'] == chain]
    if len(matching) != 1 or matching[0]['observed_residues'] == 0:
        raise ValueError('Selected protein chain not found or empty')
    if not all(v['verified'] for v in assessment['file_verification']):
        raise ValueError('Project input verification failed')
    if assessment['import_errors']:
        raise ValueError('Import errors remain unresolved')
    if matching[0]['backbone_incomplete_residues'] or matching[0]['unknown_sequence_codes']:
        raise ValueError('Selected chain has missing backbone atoms or unknown sequence codes')
    output = Path(output_json).resolve()
    if output == root / 'import_manifest.json' or output == root / rel or output == root / 'target.fasta':
        raise ValueError('Refusing to overwrite source evidence')
    record = {
        'schema': 'pepforge.v6.target_handoff.v1',
        'status': 'review_required',
        'automatic_docking_authorized': False,
        'source_manifest_sha256': assessment['source_manifest_sha256'],
        'uniprot_accession': assessment['uniprot_accession'],
        'structure_path': rel.as_posix(),
        'structure_sha256': _digest(root / rel),
        'reference_fasta_sha256': _digest(root / 'target.fasta'),
        'chain_id': chain,
        'chain_observations': matching[0],
        'reviewer': reviewer.strip(),
        'review_notes': notes.strip(),
        'unresolved_requirements': [
            'Confirm biological assembly and chain suitability',
            'Verify structure quality, missing segments and alternate locations',
            'Prepare protonation and ligands; audit modified residue chemistry',
            'Validate receptor preparation and docking method independently',
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return record
