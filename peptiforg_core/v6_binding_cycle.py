"""Evidence-gated standard-state absolute binding free-energy cycle assembly.

This analyzes independent REAL leg estimates. It cannot generate missing alchemical
simulations or restraint corrections and never treats a docking score as a free energy.

Convention: decouple ligand fully interacting -> decoupled, in solvent and in
complex. DeltaG_binding = DeltaG_decouple(solvent) - DeltaG_decouple(complex)
 + sum(signed restraint/release/standard-state/other corrections).

Correction signs are protocol-dependent. They MUST be provided explicitly by a
validated thermodynamic protocol; this module never infers their signs.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import statistics

_KB = 0.00831446261815324  # kJ mol^-1 K^-1


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def _load_json(path):
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise ValueError('Expected an existing, regular JSON evidence file')
    raw = p.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def assemble_binding_cycle(manifest_path):
    """Produce a traced numeric deltaG_bind ONLY from complete specified cycle.

    manifest fields: temperature_k, protocol_id, ligand_chemical_id,
    leg_direction='coupled_to_decoupled', solvent_replicas and complex_replicas
    (lists of independent existing MBAR audit JSON paths), corrections
    (nonempty list of signed estimates with uncertainty and provenance).
    Required correction kinds: restraint, standard_state. 'restraint' may
    include Boresch application/release as an explicitly net signed term.
    """
    manifest, manifest_hash = _load_json(manifest_path)
    if not isinstance(manifest, dict): raise ValueError('Manifest must be an object')
    temp = _finite_number(manifest.get('temperature_k'), 'temperature_k')
    if temp <= 0: raise ValueError('Temperature must be positive')
    if manifest.get('leg_direction') != 'coupled_to_decoupled':
        raise ValueError('Both leg endpoints must be coupled -> decoupled')
    for field in ('protocol_id', 'ligand_chemical_id', 'thermodynamic_cycle_description'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f'Missing required {field}')
    root = Path(manifest_path).resolve().parent
    records = {}; used = {str(Path(manifest_path).resolve())}
    for leg in ('solvent', 'complex'):
        files = manifest.get(f'{leg}_replicas')
        if not isinstance(files, list) or len(files) < 3 or len(set(files)) != len(files):
            raise ValueError(f'{leg} needs >=3 distinct independent replica audit files')
        parsed=[]
        for rel in files:
            if not isinstance(rel, str) or not rel or Path(rel).is_absolute():
                raise ValueError('Replica reference must be relative')
            path = (root / rel).resolve()
            if not path.is_relative_to(root) or str(path) in used:
                raise ValueError('Duplicated or external replica file')
            used.add(str(path))
            obj, sha = _load_json(path)
            if obj.get('result_type') != 'ALCHEMICAL_LEG_DELTA_G_NOT_BINDING_DELTA_G':
                raise ValueError('Replica must contain authentic alchemical-leg audit')
            if obj.get('status') != 'PRELIMINARY_MBAR_ESTIMATE' or obj.get('warnings'):
                raise ValueError('Leg must pass the preliminary MBAR diagnostic gate')
            if abs(_finite_number(obj.get('temperature_k'),'leg temperature')-temp)>1e-6:
                raise ValueError('Leg temperature mismatch')
            lambdas = obj.get('lambda_values')
            if not isinstance(lambdas,list) or len(lambdas)<3 or abs(lambdas[0])>1e-8 or abs(lambdas[-1]-1)>1e-8:
                raise ValueError('Explicit lambda 0 and 1 endpoints required')
            val=_finite_number(obj.get('delta_g_kj_mol'),'leg deltaG')
            err=_finite_number(obj.get('standard_error_kj_mol'),'leg uncertainty')
            if err <= 0: raise ValueError('A positive statistical uncertainty is required')
            if not isinstance(obj.get('input_sha256'),str) or len(obj['input_sha256'])!=64:
                raise ValueError('Missing raw sample provenance')
            parsed.append({'delta_g_kj_mol':val,'mbar_se_kj_mol':err,'audit_sha256':sha,'raw_sha256':obj['input_sha256']})
        if len({x['raw_sha256'] for x in parsed})!=len(parsed):
            raise ValueError('Same raw samples used in multiple replicas')
        records[leg]=parsed
    kinds=set(); correction_total=0; correction_var=0; cleaned=[]
    corrections=manifest.get('corrections')
    if not isinstance(corrections,list) or not corrections:
        raise ValueError('Complete correction accounting required')
    for c in corrections:
        if not isinstance(c,dict): raise ValueError('Invalid correction')
        kind=c.get('kind'); method=c.get('method'); provenance=c.get('source')
        if not all(isinstance(v,str) and v.strip() for v in (kind,method,provenance)):
            raise ValueError('Corrections require kind, method, source')
        if c.get('sign_convention_verified') is not True:
            raise ValueError('Correction sign convention must be verified')
        val=_finite_number(c.get('signed_delta_g_kj_mol'),'correction value')
        err=_finite_number(c.get('standard_error_kj_mol'),'correction uncertainty')
        if err < 0: raise ValueError('Negative correction uncertainty')
        if err == 0 and c.get('uncertainty_basis')!='exact_analytic':
            raise ValueError('Zero uncertainty requires exact_analytic justification')
        cleaned.append({'kind':kind,'signed_delta_g_kj_mol':val,'standard_error_kj_mol':err,'method':method,'source':provenance})
        correction_total+=val; correction_var+=err*err; kinds.add(kind)
    if not {'restraint','standard_state'}.issubset(kinds):
        raise ValueError('Both restraint and standard_state corrections required')
    means={leg:statistics.mean(r['delta_g_kj_mol'] for r in records[leg]) for leg in records}
    # Conservative combined uncertainty: MBAR within-replica variance of mean plus
    # between-replica sample variance of mean (can double-count; explicitly labeled).
    uncertainties={}
    for leg, rows in records.items():
        n=len(rows)
        between=statistics.variance(r['delta_g_kj_mol'] for r in rows)/n
        within=sum(r['mbar_se_kj_mol']**2 for r in rows)/(n*n)
        uncertainties[leg]=math.sqrt(between+within)
    delta=means['solvent']-means['complex']+correction_total
    se=math.sqrt(uncertainties['solvent']**2+uncertainties['complex']**2+correction_var)
    strict_audit = None
    if 'strict_protocol_evidence' in manifest:
        from .v6_abfe_protocol_audit import audit_abfe_protocol
        strict_audit = audit_abfe_protocol(manifest_path)
    # 1 M standard-state affinity derived ONLY from an explicitly defined cycle.
    # Report log-scale quantities to avoid overflow for very strong/weak estimates.
    pkd = -delta / (_KB * temp * math.log(10.0))
    return {'standard_state_pKd_preliminary':pkd,
      'standard_state_log10_Kd_molar_preliminary':-pkd,
      'affinity_conversion_warning':'Thermodynamic conversion of the preliminary estimate, NOT an independently measured affinity',
      'strict_protocol_audit':strict_audit,'result_type':'ABSOLUTE_BINDING_FREE_ENERGY_ESTIMATE',
      'status':'PRELIMINARY_NOT_INDEPENDENTLY_VALIDATED',
      'delta_g_bind_kj_mol':delta,'combined_uncertainty_kj_mol':se,
      'temperature_k':temp,'cycle_convention':'solvent_decouple - complex_decouple + signed_corrections',
      'solvent_mean_kj_mol':means['solvent'],'complex_mean_kj_mol':means['complex'],
      'replica_uncertainty_kj_mol':uncertainties,'correction_sum_kj_mol':correction_total,
      'corrections':cleaned,'replica_evidence':records,'manifest_sha256':manifest_hash,
      'protocol_id':manifest['protocol_id'],'ligand_chemical_id':manifest['ligand_chemical_id'],
      'limitations':['Correction values and signs must be independently validated against the exact restraint protocol',
       'Independent samples, pose interconversion, charge finite-size corrections and structural convergence are not established by this calculation',
       'Uncertainty combines within-MBAR and between-replica variability conservatively; does not quantify systematic error',
       'No trajectories or missing thermodynamic legs were generated by this tool']}
