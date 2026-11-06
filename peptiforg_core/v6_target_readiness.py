"""Conservative, read-only structure/sequence readiness assessment.

No docking, structure repair, chain assignment, force-field verification or
scientific confidence values are inferred from this report.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_structure(path: Path):
    try:
        from Bio.PDB import MMCIFParser, PDBParser
    except ImportError as exc:
        raise RuntimeError('Biopython required for coordinate analysis') from exc
    if path.suffix.lower() == '.cif':
        parser = MMCIFParser(QUIET=True)
    elif path.suffix.lower() == '.pdb':
        parser = PDBParser(QUIET=True)
    else:
        raise ValueError('Unsupported coordinate extension')
    return parser.get_structure('target', str(path))


def inspect_target_project(project_dir: str | Path, *, output_json: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_dir).resolve()
    manifest_path = root / 'import_manifest.json'
    if not manifest_path.is_file():
        raise FileNotFoundError('import_manifest.json is required')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'pepforge.v6.online_target_import.v1':
        raise ValueError('Unsupported import manifest schema')
    entries = manifest.get('files')
    if not isinstance(entries, list):
        raise ValueError('Malformed manifest files')
    verification = []
    for entry in entries:
        name = entry.get('path', '')
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or not name:
            raise ValueError('Unsafe manifest file path')
        p = (root / rel).resolve()
        if not p.is_relative_to(root):
            raise ValueError('Manifest path escapes project directory')
        okay = p.is_file() and _sha(p) == entry.get('sha256') and p.stat().st_size == entry.get('bytes')
        verification.append({'path': name, 'verified': bool(okay)})
    fasta_path = root / 'target.fasta'
    sequence = ''
    if fasta_path.is_file() and any(v['path'] == 'target.fasta' and v['verified'] for v in verification):
        sequence = ''.join(x.strip() for x in fasta_path.read_text(encoding='utf-8').splitlines() if not x.startswith('>')).upper()
    result: dict[str, Any] = {
        'schema': 'pepforge.v6.target_readiness.v1',
        'source_manifest_sha256': _sha(manifest_path),
        'uniprot_accession': manifest.get('uniprot_accession'),
        'file_verification': verification,
        'sequence_length': len(sequence),
        'structures': [],
        'import_errors': manifest.get('errors', []),
        'warnings': [],
        'ready_for_automatic_docking': False,
        'reason': 'Manual chain, biological assembly, missing-residue, chemistry and protonation review required.',
    }
    if not sequence:
        result['warnings'].append('Verified reference FASTA not available')
    if not all(v['verified'] for v in verification):
        result['warnings'].append('Import manifest file checksum or file size mismatch')
    if manifest.get('errors'):
        result['warnings'].append('One or more online imports failed')
    try:
        from Bio.SeqUtils import seq1
        from Bio.Align import PairwiseAligner
    except ImportError:
        seq1 = None
        PairwiseAligner = None
        result['warnings'].append('Biopython unavailable; structures not inspected')
    for entry in verification:
        name = entry['path']
        if not name.startswith('structures/') or Path(name).suffix.lower() not in ('.pdb', '.cif'):
            continue
        item: dict[str, Any] = {'path': name, 'sha256_verified': entry['verified'], 'chains': [], 'warnings': []}
        if not entry['verified']:
            item['warnings'].append('Integrity verification failed; skipped parsing')
            result['structures'].append(item)
            continue
        if seq1 is None:
            item['warnings'].append('Biopython dependency missing')
            result['structures'].append(item)
            continue
        try:
            structure = _parse_structure(root / name)
            models = list(structure.get_models())
            item['model_count'] = len(models)
            if len(models) != 1:
                item['warnings'].append('Multiple coordinate models: only first is summarized')
            for chain in models[0] if models else []:
                residues = [r for r in chain if r.id[0] == ' ']
                chain_seq = ''.join(seq1(r.resname, custom_map={'MSE':'M'}, undef_code='X') for r in residues)
                incomplete = sum(not {'N', 'CA', 'C', 'O'}.issubset(set(r.child_dict)) for r in residues)
                altlocs = sum(any(a.is_disordered() for a in r.get_atoms()) for r in residues)
                data = {'chain_id': chain.id, 'observed_residues': len(residues),
                        'backbone_incomplete_residues': incomplete, 'residues_with_alternate_locations': altlocs,
                        'unknown_sequence_codes': chain_seq.count('X')}
                if sequence and chain_seq and PairwiseAligner is not None:
                    aligner = PairwiseAligner(mode='local', match_score=2, mismatch_score=-1, open_gap_score=-5, extend_gap_score=-0.5)
                    aln = aligner.align(sequence, chain_seq)[0]
                    pair_a, pair_b = aln.aligned
                    aligned_positions = sum(end-start for start, end in pair_a)
                    identical = 0
                    for (a0,a1),(b0,b1) in zip(pair_a,pair_b):
                        identical += sum(x == y for x,y in zip(sequence[a0:a1],chain_seq[b0:b1]))
                    data['reference_coverage'] = round(aligned_positions / len(sequence), 4)
                    data['aligned_identity'] = round(identical / aligned_positions, 4) if aligned_positions else None
                item['chains'].append(data)
            item['hetero_residue_count'] = sum(1 for r in models[0].get_residues() if r.id[0] != ' ') if models else 0
            if not item['chains']:
                item['warnings'].append('No polymer protein chains detected')
        except Exception as exc:
            item['warnings'].append(f'Could not parse coordinates: {type(exc).__name__}: {exc}')
        result['structures'].append(item)
    if not result['structures']:
        result['warnings'].append('No downloaded structures to inspect')
    if output_json is not None:
        dest = Path(output_json).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return result
