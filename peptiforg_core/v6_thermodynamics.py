"""Auditable postprocessing of REAL alchemical reduced-potential samples.

This module never generates trajectories, invents free energies, or calls a docking
score a thermodynamic free energy. Energy samples must be supplied by a simulation.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np


def _read_npz(path):
    p=Path(path)
    if not p.is_file() or p.suffix.lower()!='.npz':
        raise ValueError('Supply a real .npz reduced-potential sample file')
    with np.load(p,allow_pickle=False) as z:
        if not {'u_kn','N_k','lambda_values'}.issubset(z.files):
            raise ValueError('Requires u_kn, N_k, lambda_values arrays')
        u=np.array(z['u_kn'],dtype=np.float64)
        counts=np.array(z['N_k'])
        lam=np.array(z['lambda_values'],dtype=np.float64)
    if u.ndim!=2 or counts.ndim!=1 or lam.ndim!=1:
        raise ValueError('Invalid array dimensions')
    k=u.shape[0]
    if k<3 or counts.shape!=(k,) or lam.shape!=(k,):
        raise ValueError('At least 3 compatible thermodynamic states required')
    if not np.all(np.isfinite(u)) or not np.all(np.isfinite(lam)):
        raise ValueError('Nonfinite reduced potentials or lambda values')
    if not np.all(np.isfinite(counts)) or np.any(counts!=np.floor(counts)):
        raise ValueError('N_k must contain integer sample counts')
    counts=counts.astype(int)
    if np.any(counts<5) or int(counts.sum())!=u.shape[1]:
        raise ValueError('N_k must match concatenated samples; at least 5 per state')
    if np.any(np.diff(lam)<=0) or lam[0]<0 or lam[-1]>1:
        raise ValueError('Lambda values must be increasing inside [0,1]')
    return u,counts,lam,hashlib.sha256(p.read_bytes()).hexdigest()


def analyze_alchemical_samples(path, *, temperature_k, expected_lambda_endpoints=(0.0,1.0)):
    if not (math.isfinite(temperature_k) and temperature_k>0):
        raise ValueError('Positive finite temperature required')
    u,n,lam,digest=_read_npz(path)
    if not np.allclose(lam[[0,-1]],expected_lambda_endpoints,atol=1e-8):
        raise ValueError('Alchemical end states must be explicitly sampled')
    try:
        from pymbar import MBAR
    except ImportError as exc:
        raise RuntimeError('PyMBAR is required; no approximate replacement is permitted') from exc
    mbar=MBAR(u,n,verbose=False)
    estimates=mbar.compute_free_energy_differences(compute_uncertainty=True)
    dd=float(estimates['Delta_f'][0,-1]); se=float(estimates['dDelta_f'][0,-1])
    if not (math.isfinite(dd) and math.isfinite(se) and se>=0):
        raise ValueError('Invalid MBAR estimate')
    # k_B in kJ mol^-1 K^-1. These are state differences, NOT binding free energies.
    kbt=0.00831446261815324*temperature_k
    overlap=mbar.compute_overlap()['matrix']
    if np.shape(overlap)!=(len(n),len(n)) or not np.all(np.isfinite(overlap)):
        raise ValueError('Invalid overlap matrix')
    neighboring=[float(min(overlap[i,i+1],overlap[i+1,i])) for i in range(len(n)-1)]
    warnings=[]
    if min(neighboring)<0.01: warnings.append('LOW_NEIGHBOR_OVERLAP')
    if se>1: warnings.append('HIGH_STATISTICAL_UNCERTAINTY_KT')
    return {'result_type':'ALCHEMICAL_LEG_DELTA_G_NOT_BINDING_DELTA_G',
            'status':'DIAGNOSTICS_REQUIRED' if warnings else 'PRELIMINARY_MBAR_ESTIMATE',
            'delta_g_kj_mol':dd*kbt,'standard_error_kj_mol':se*kbt,
            'delta_f_kT':dd,'standard_error_kT':se,'temperature_k':temperature_k,
            'lambda_values':lam.tolist(),'samples_per_state':n.tolist(),
            'neighbor_min_overlap':neighboring,'warnings':warnings,
            'input_sha256':digest,
            'limitations':['Input samples must come from real equilibrated dynamics',
                           'No autocorrelation filtering is inferred from this file',
                           'One alchemical leg is NOT an absolute binding free energy',
                           'Binding requires solvent/complex legs, restraints and standard-state corrections',
                           'Independent replicas and convergence analysis required']}


def analyze_replica_observables(paths, *, min_samples=100, rhat_threshold=1.1):
    """Split-Rhat and between/within variance for observable CSV with identical headers.

    Inputs must contain time/step plus named numeric observables, e.g. RMSD and contacts.
    Warns on poor agreement; passing Rhat does not establish convergence.
    """
    import csv
    if len(paths)<3: raise ValueError('At least three independent replicas required')
    values=[]; hashes=[]; names=None
    for path in paths:
        raw=Path(path).read_bytes(); hashes.append(hashlib.sha256(raw).hexdigest())
        with Path(path).open(newline='',encoding='utf-8-sig') as f:
            rdr=csv.DictReader(f); fields=rdr.fieldnames
            if not fields or len(fields)!=len(set(fields)): raise ValueError('Invalid headers')
            obs=[v for v in fields if v.lower() not in ('step','time','time_ps','frame')]
            if names is None: names=obs
            if names!=obs or not names: raise ValueError('Replica observables differ')
            data=[]
            for r in rdr:
                a=[float(r[c]) for c in names]
                if not all(math.isfinite(v) for v in a): raise ValueError('Nonfinite observable')
                data.append(a)
        if len(data)<min_samples: raise ValueError('Insufficient samples per replica')
        values.append(np.asarray(data,float))
    n=min(len(x) for x in values)
    if n//2<4: raise ValueError('Not enough data for split chains')
    half=n//2
    chains=np.concatenate([np.stack([v[:half],v[-half:]]) for v in values],axis=0)
    m=chains.shape[0]
    means=chains.mean(axis=1)
    within=chains.var(axis=1,ddof=1).mean(axis=0)
    between=half*means.var(axis=0,ddof=1)
    var_hat=(half-1)/half*within+between/half
    rhat=np.where(within>1e-12,np.sqrt(var_hat/np.maximum(within,1e-12)),np.inf)
    result={name: {'split_rhat':float(rhat[i]),'replica_means':[float(v[:,i].mean()) for v in values],
                    'flag':'REVIEW' if not math.isfinite(rhat[i]) or rhat[i]>rhat_threshold else 'PRELIMINARY_AGREEMENT'}
            for i,name in enumerate(names)}
    return {'status':'DIAGNOSTICS_ONLY','replicas':len(paths),'samples_used_per_replica':n,
            'observables':result,'input_sha256':hashes,
            'limitations':['Split R-hat is a necessary diagnostic, not proof of equilibrium',
                           'Autocorrelated time series require ESS and additional structural checks',
                           'Independent initial velocities/seeds and distinct trajectories must be verified']}
