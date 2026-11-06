"""Fail-closed, reusable target-to-design project contract (not a simulated run)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def _inside(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not relative:
        raise ValueError('Unsafe relative source path')
    path = (root / rel).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Source path escaped project directory')
    return path


def generate_project_workflow(project_dir: str | Path, handoff_json: str | Path,
                              output_dir: str | Path) -> dict:
    from peptiforg_core.v6_target_readiness import _parse_structure
    from Bio.SeqUtils import seq1
    root = Path(project_dir).resolve()
    handoff_file = Path(handoff_json).resolve()
    out = Path(output_dir).resolve()
    if not handoff_file.is_file():
        raise FileNotFoundError('Handoff JSON is missing')
    record = json.loads(handoff_file.read_text(encoding='utf-8'))
    if record.get('schema') != 'pepforge.v6.target_handoff.v1' or record.get('status') != 'review_required':
        raise ValueError('Unsupported or unreviewed handoff')
    if record.get('automatic_docking_authorized') is not False:
        raise ValueError('Handoff permission must be explicitly false')
    manifest = root/'import_manifest.json'
    fasta = root/'target.fasta'
    structure = _inside(root, record['structure_path'])
    if not structure.is_file() or not fasta.is_file() or not manifest.is_file():
        raise FileNotFoundError('Imported source file missing')
    for src, key in ((manifest,'source_manifest_sha256'),(fasta,'reference_fasta_sha256'),(structure,'structure_sha256')):
        if digest(src) != record.get(key):
            raise ValueError(f'Provenance SHA-256 mismatch for {src.name}')
    # Re-run the import verification rather than blindly trusting handoff JSON.
    from peptiforg_core.v6_target_readiness import inspect_target_project
    report = inspect_target_project(root)
    if any(not item['verified'] for item in report['file_verification']) or report['import_errors']:
        raise ValueError('Current imported target verification failed')
    matched = next((s for s in report['structures'] if s['path'] == record['structure_path']), None)
    if not matched or matched['warnings']:
        raise ValueError('Structure failed current readiness checks')
    chain_id = record['chain_id']
    chain_report = next((c for c in matched['chains'] if c['chain_id'] == chain_id), None)
    if not chain_report or chain_report['backbone_incomplete_residues'] or chain_report['unknown_sequence_codes']:
        raise ValueError('Chain is missing or unsuitable')
    if chain_report != record['chain_observations']:
        raise ValueError('Chain assessment changed since handoff')
    model = next(_parse_structure(structure).get_models())
    if chain_id not in model:
        raise ValueError('Chain no longer present')
    chain = model[chain_id]
    residues = [r for r in chain if r.id[0] == ' ']
    sequence = ''.join(seq1(r.resname, custom_map={'MSE':'M'}, undef_code='X') for r in residues)
    if not sequence or 'X' in sequence:
        raise ValueError('No unambiguous sequence to export')
    if out == root or out == structure.parent or out == root.parent:
        raise ValueError('Output must be a dedicated workflow directory')
    out.mkdir(parents=True, exist_ok=True)
    chain_fasta = out/'selected_chain.fasta'
    chain_fasta.write_text(f'>{record["uniprot_accession"]}|chain={chain_id}|observed_only\n' +
                           '\n'.join(sequence[i:i+80] for i in range(0,len(sequence),80))+'\n',encoding='utf-8')
    jobs = {name: {'status': 'not_executed', 'required_manual_review': True}
            for name in ('hotspot_finder','peptide_design','docking','molecular_dynamics','spps_planner')}
    data = {
        'schema':'pepforge.v6.project_workflow.v1',
        'status':'inputs_verified_manual_review_required',
        'automatic_docking_authorized':False,
        'uniprot_accession':record['uniprot_accession'],
        'selected_chain':chain_id,
        'selected_chain_sequence_length':len(sequence),
        'sequence_scope':'observed_polymer_residues_only',
        'inputs':{
           'handoff':{'path':str(handoff_file),'sha256':digest(handoff_file)},
           'reference_fasta':{'path':str(fasta),'sha256':digest(fasta)},
           'coordinate_file':{'path':str(structure),'sha256':digest(structure)},
           'selected_chain_fasta':{'path':str(chain_fasta),'sha256':digest(chain_fasta)},
        },
        'pipeline':jobs,
        'review_checks':[ 'Check chain and biological assembly', 'Resolve unresolved structure/ligand/chemistry issues',
                          'Review design settings and modified residue parameters',
                          'Verify native docking evidence before downstream simulation',
                          'Review SPPS synthesis settings and cleavage chemistry'],
        'disclaimer':'Project contract is not a docked pose, peptide candidate, experimental measurement, or MD simulation.'
    }
    (out/'workflow_manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'WORKFLOW_README.md').write_text('# Pepforge V6 project handoff\nNo calculation has been executed. Review workflow_manifest.json before using downstream tools.\n',encoding='utf-8')
    return data


def verify_project_workflow(workflow_json: str | Path) -> dict:
    """Conservatively verify an *unexecuted* workflow contract and input provenance.

    Integrity of file contents alone does not authorize docking or attest that a
    computation occurred. Any altered stage status must be treated as unverified.
    """
    p = Path(workflow_json).resolve()
    data = json.loads(p.read_text(encoding='utf-8'))
    if data.get('schema') != 'pepforge.v6.project_workflow.v1':
        raise ValueError('Unsupported workflow manifest')
    required = {'handoff', 'reference_fasta', 'coordinate_file', 'selected_chain_fasta'}
    inputs = data.get('inputs')
    if not isinstance(inputs, dict) or set(inputs) != required:
        raise ValueError('Missing or unexpected workflow inputs')
    verified = {}
    for name, item in inputs.items():
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('sha256'), str):
            verified[name] = False
            continue
        f = Path(item['path'])
        verified[name] = f.is_file() and len(item['sha256']) == 64 and digest(f) == item['sha256']
    required_stages = {'hotspot_finder', 'peptide_design', 'docking', 'molecular_dynamics', 'spps_planner'}
    pipeline = data.get('pipeline')
    safe_stages = (isinstance(pipeline, dict) and set(pipeline) == required_stages and
                   all(isinstance(stage, dict) and stage.get('status') == 'not_executed' and
                       stage.get('required_manual_review') is True for stage in pipeline.values()))
    safe_status = (data.get('automatic_docking_authorized') is False and
                   data.get('status') == 'inputs_verified_manual_review_required')
    return {'schema':'pepforge.v6.workflow_integrity.v1',
            'verified': all(verified.values()) and safe_stages and safe_status,
            'inputs':verified, 'stage_contract_verified':bool(safe_stages),
            'automatic_docking_authorized':False,
            'executed_steps':[] if safe_stages else ['UNVERIFIED_STAGE_STATUS']}
