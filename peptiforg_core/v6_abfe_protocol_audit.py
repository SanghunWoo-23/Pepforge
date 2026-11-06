"""Fail-closed scientific evidence gate for paired ABFE legs.

This checks protocol identity and correction accounting; it is NOT an
alchemical simulator and cannot establish experimental accuracy.
"""
from __future__ import annotations
from pathlib import Path
import json, hashlib, math

REQUIRED_SHARED = ('ligand_chemical_id', 'forcefield_id', 'water_model',
                   'temperature_k', 'pressure_bar', 'charge_model',
                   'ligand_formal_charge', 'alchemical_protocol_id')
REQUIRED_LEG = ('leg', 'endpoint_start', 'endpoint_end',
                'electrostatics_schedule', 'sterics_schedule',
                'softcore_model', 'sampling_method', 'replica_seed',
                'restraint_protocol_id', 'system_sha256')


def audit_abfe_protocol(manifest_path):
    """Validate a fully documented protocol, including 3 independent repeats/leg.

    Strict schema is opt-in so historical PRELIMINARY cycles remain readable.
    The cycle assembler calls this only when strict_protocol_evidence is present.
    """
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text(encoding='utf-8'))
    block = manifest.get('strict_protocol_evidence')
    if not isinstance(block, dict):
        raise ValueError('strict_protocol_evidence object is required')
    if block.get('schema_version') != 1:
        raise ValueError('Unrecognized strict ABFE protocol schema')
    legs = block.get('legs')
    if not isinstance(legs, dict) or set(legs) != {'solvent', 'complex'}:
        raise ValueError('Both solvent and complex protocol records are required')
    shared = block.get('shared')
    if not isinstance(shared, dict):
        raise ValueError('Missing shared protocol identity')
    for key in REQUIRED_SHARED:
        v=shared.get(key)
        if v is None or isinstance(v, (str, list, dict)) and not v:
            raise ValueError('Missing protocol identity: '+key)
    if shared['ligand_chemical_id'] != manifest.get('ligand_chemical_id'):
        raise ValueError('Ligand identity differs from ABFE manifest')
    if not math.isclose(float(shared['temperature_k']),float(manifest['temperature_k']),abs_tol=1e-6):
        raise ValueError('Temperature differs from ABFE manifest')
    for num in ('temperature_k','pressure_bar'):
        x = shared[num]
        if isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) or x<=0:
            raise ValueError('Invalid '+num)
    if isinstance(shared['ligand_formal_charge'],bool) or not isinstance(shared['ligand_formal_charge'],int):
        raise ValueError('Ligand charge must be an integer')
    if shared['ligand_formal_charge'] and block.get('charged_ligand_finite_size_review') != 'documented':
        raise ValueError('Charged ligand finite-size/electrostatic corrections require review')
    allowed_methods = {'HREX','SAMS','independent_windows'}
    seeds=set()
    for leg in ('solvent','complex'):
        records=legs[leg]
        if not isinstance(records,list) or len(records)!=len(manifest.get(leg+'_replicas',[])):
            raise ValueError('Protocol records must match '+leg+' replica count')
        for i,item in enumerate(records):
            if not isinstance(item,dict): raise ValueError('Invalid leg record')
            for key in REQUIRED_LEG:
                if key not in item or item[key] in ('',None):
                    raise ValueError('Missing leg protocol field: '+key)
            if item['leg']!=leg: raise ValueError('Wrong leg label')
            if item['endpoint_start']!='fully_interacting' or item['endpoint_end']!='decoupled':
                raise ValueError('Incompatible alchemical endpoints')
            if item['sampling_method'] not in allowed_methods:
                raise ValueError('Unsupported sampling declaration')
            if not isinstance(item['replica_seed'],int) or isinstance(item['replica_seed'],bool):
                raise ValueError('Replica seed must be an integer')
            identifier=(leg,item['replica_seed'])
            if identifier in seeds: raise ValueError('Duplicate replica seed in a leg')
            seeds.add(identifier)
            digest=item['system_sha256']
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('Invalid system fingerprint')
            if leg=='solvent' and item['restraint_protocol_id']!='none':
                raise ValueError('Solvent leg cannot use protein-ligand orientational restraints')
            if leg=='complex' and item['restraint_protocol_id']=='none':
                raise ValueError('Complex leg requires explicit restraint protocol')
    corrections = manifest.get('corrections', [])
    sources = []
    for c in corrections:
        if not isinstance(c,dict) or not c.get('correction_id') or not c.get('accounting_stage'):
            raise ValueError('Strict corrections require correction_id and accounting_stage')
        sources.append(c['correction_id'])
        if c['accounting_stage'] not in ('separate_cycle_term','already_in_leg'):
            raise ValueError('Unknown correction accounting stage')
        if c['accounting_stage']=='already_in_leg':
            raise ValueError('Correction already included in leg cannot be added again')
    if len(set(sources))!=len(sources):
        raise ValueError('Duplicate correction identifiers')
    complex_restraints={x['restraint_protocol_id'] for x in legs['complex']}
    if len(complex_restraints)!=1:
        raise ValueError('Complex replicas use inconsistent restraint protocols')
    for key in ('softcore_model','electrostatics_schedule','sterics_schedule'):
        for leg in ('solvent','complex'):
            if len({json.dumps(r[key],sort_keys=True) for r in legs[leg]}) != 1:
                raise ValueError('Inconsistent '+key+' within '+leg+' replicas')
    if block.get('independent_replica_initializations') is not True:
        raise ValueError('Independent initial conditions must be documented')
    return {'status':'PROTOCOL_ACCOUNTING_CHECKED_NOT_SCIENTIFICALLY_VALIDATED',
            'checks': ['chemical and forcefield identity','endpoint orientation',
                       'replica independence declaration','restraint bookkeeping',
                       'duplicate correction rejection','charged species warning'],
            'protocol_manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
