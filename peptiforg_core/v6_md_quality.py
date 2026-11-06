"""Auditable diagnostics for actual OpenMM production time series.

A diagnostic PASS is not proof of conformational convergence or binding free energy.
No fake samples, no invented thermodynamic estimates.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path


def _read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as fp:
        rows=list(csv.reader(fp))
    if len(rows) < 2:
        raise ValueError('MD state log has no data rows')
    header=[x.strip().strip('#').strip('"').strip() for x in rows[0]]
    if len(set(header)) != len(header):
        raise ValueError('Duplicate state log headers')
    data=[]
    for line_no,row in enumerate(rows[1:],2):
        if len(row)!=len(header):
            raise ValueError(f'Invalid number of columns on line {line_no}')
        parsed=[]
        for item in row:
            try:
                x=float(item)
            except (ValueError,TypeError) as exc:
                raise ValueError(f'Invalid numeric value on line {line_no}') from exc
            if not math.isfinite(x):
                raise ValueError(f'Nonfinite value on line {line_no}')
            parsed.append(x)
        data.append(parsed)
    return {key:[r[i] for r in data] for i,key in enumerate(header)}


def _key(fields, needle):
    hits=[k for k in fields if needle in k.lower()]
    if len(hits)!=1:
        raise ValueError(f'Expected exactly one {needle} column, found {hits}')
    return hits[0]


def analyze_md_state_log(path, *, target_temperature_k=300.0, minimum_samples=100,
                         minimum_effective_samples=30, temperature_tolerance_fraction=0.10):
    """Calculate finite/logical diagnostics; no claim of full molecular convergence."""
    import numpy as np
    from scipy import stats
    if not (math.isfinite(target_temperature_k) and target_temperature_k>0):
        raise ValueError('Invalid target temperature')
    if type(minimum_samples) is not int or minimum_samples<4:
        raise ValueError('Invalid minimum samples')
    if type(minimum_effective_samples) is not int or minimum_effective_samples<2:
        raise ValueError('Invalid minimum effective samples')
    data=_read_csv(path)
    step=np.asarray(data[_key(data,'step')],float)
    energy=np.asarray(data[_key(data,'potential energy')],float)
    temperature=np.asarray(data[_key(data,'temperature')],float)
    if len(step)<4 or not np.all(np.diff(step)>0):
        raise ValueError('Steps must be strictly increasing with four or more samples')
    if np.any(temperature<0):
        raise ValueError('Negative temperatures in log')
    n=len(step)
    latter=energy[n//2:]
    first=energy[:n//2]
    # A half-window shift detects gross drift without claiming equilibrium.
    scale=float(np.std(energy,ddof=1))
    drift=abs(float(np.mean(first)-np.mean(latter)))/(scale if scale>1e-12 else 1.0)
    tmean=float(np.mean(temperature))
    issues=[]
    if n<minimum_samples: issues.append('INSUFFICIENT_SAMPLES')
    if abs(tmean-target_temperature_k)>temperature_tolerance_fraction*target_temperature_k:
        issues.append('TEMPERATURE_OFF_TARGET')
    # PyMBAR equilibration detection is optional. Do not silently assign Neff=n.
    equilibration=None
    try:
        from pymbar import timeseries
        t0,g,neff=timeseries.detect_equilibration(energy)
        if not all(math.isfinite(float(x)) for x in (t0,g,neff)):
            raise ValueError('Nonfinite timeseries statistics')
        equilibration={'start_index':int(t0),'statistical_inefficiency':float(g),
                       'effective_samples':float(neff)}
        if neff<minimum_effective_samples: issues.append('INSUFFICIENT_INDEPENDENT_SAMPLES')
    except ImportError:
        issues.append('PYMBAR_NOT_INSTALLED')
    # Drift is a warning, not a formal stationarity test.
    if drift>1.5: issues.append('LARGE_ENERGY_HALF_WINDOW_SHIFT')
    result={'status':'PRELIMINARY_DIAGNOSTICS_PASS' if not issues else 'NOT_VALIDATED',
            'issues':issues,'sample_count':n,'energy_mean_kj_mol':float(np.mean(energy)),
            'energy_std_kj_mol':scale,'temperature_mean_k':tmean,
            'temperature_std_k':float(np.std(temperature,ddof=1)),
            'energy_half_window_shift_standardized':drift,'equilibration':equilibration,
            'input_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'limitations':['State log diagnostics alone cannot establish structural convergence',
                           'Multiple independent replicas and structural observables are required',
                           'No binding free energy is calculated']}
    return result


def write_md_quality_report(csv_path, output_json, **kwargs):
    path=Path(output_json)
    if path.exists() or path.is_symlink():
        raise FileExistsError('Refusing to overwrite diagnostics')
    record=analyze_md_state_log(csv_path,**kwargs)
    path.parent.mkdir(parents=True,exist_ok=True)
    import os,tempfile
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=path.parent,suffix='.json',delete=False) as fp:
            temp=Path(fp.name)
            json.dump(record,fp,indent=2,ensure_ascii=False)
            fp.write('\n')
        os.replace(temp,path)
        temp=None
    finally:
        if temp is not None: temp.unlink(missing_ok=True)
    return record
