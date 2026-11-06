import csv
import numpy as np
import pytest
from peptiforg_core.v6_thermodynamics import _read_npz, analyze_alchemical_samples, analyze_replica_observables

def test_reject_missing_samples(tmp_path):
    p=tmp_path/'wrong.npz';np.savez(p,bad=[1]);
    with pytest.raises(ValueError): _read_npz(p)

def test_reject_nonfinite(tmp_path):
    p=tmp_path/'bad.npz';u=np.ones((3,15));u[1,2]=np.nan
    np.savez(p,u_kn=u,N_k=[5,5,5],lambda_values=[0,.5,1])
    with pytest.raises(ValueError,match='Nonfinite'): _read_npz(p)

def test_reject_sample_count(tmp_path):
    p=tmp_path/'bad.npz';np.savez(p,u_kn=np.ones((3,14)),N_k=[5,5,5],lambda_values=[0,.5,1])
    with pytest.raises(ValueError): _read_npz(p)

def test_reject_missing_endpoint(tmp_path):
    p=tmp_path/'bad.npz';np.savez(p,u_kn=np.ones((3,15)),N_k=[5,5,5],lambda_values=[.1,.5,1])
    with pytest.raises(ValueError,match='end states'): analyze_alchemical_samples(p,temperature_k=300)

def test_replica_agreement(tmp_path):
    paths=[]
    for i in range(3):
        p=tmp_path/f'replica{i}.csv';paths.append(p)
        with p.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['step','rmsd','contacts'])
            for j in range(120):w.writerow([j,3+np.sin(j)*.1+i*.01,10+np.cos(j)*.2])
    report=analyze_replica_observables(paths)
    assert report['replicas']==3
    assert report['observables']['rmsd']['split_rhat']<1.1

def test_replica_malformed(tmp_path):
    paths=[]
    for i in range(3):
        p=tmp_path/f'r{i}.csv';paths.append(p)
        p.write_text('step,rmsd\n0,NaN\n')
    with pytest.raises(ValueError):analyze_replica_observables(paths,min_samples=1)
