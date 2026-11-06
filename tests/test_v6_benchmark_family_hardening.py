import csv
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('batch_bench', ROOT/'RUN_INDEPENDENT_BENCHMARK_BATCH.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def atom(x, y, z, name, res='ALA'):
    return f'ATOM      1 {name:<4} {res:>3} A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C\n'


def build(tmp_path, duplicated=False):
    rows=[]
    for i in range(2):
        r=tmp_path/f'r{i}.pdb'; p=tmp_path/f'p{i}.pdb'
        r.write_text(''.join(atom(*xyz,name) for xyz,name in [((0,0,0),'C1'),((1,0,0),'C2'),((0,1,0),'C3')]))
        p.write_text(atom(0,0,2,'C1'))
        rows.append({'case_id':str(i),'family':f'f{i}', 'split':'test',
            'reference_peptide_pdb':str(p), 'predicted_peptide_pdb':str(p),
            'reference_receptor_pdb':str(r), 'predicted_receptor_pdb':str(r)})
    if duplicated: rows[1]['reference_peptide_pdb']=rows[0]['reference_peptide_pdb']; rows[1]['reference_receptor_pdb']=rows[0]['reference_receptor_pdb']
    file=tmp_path/'manifest.csv'
    with file.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    return file


def test_family_ci_and_coverage(tmp_path):
    manifest=build(tmp_path)
    result=mod.run(manifest,tmp_path/'out.json',bootstrap=100,seed=7)
    assert result['family_count']==2
    assert result['family_macro_success_at_2A']==1.0
    assert result['family_cluster_bootstrap_95_percent_CI']==[1.,1.]
    assert (tmp_path/'out.json').is_file()


def test_duplicate_reference_rejected_before_output(tmp_path):
    manifest=build(tmp_path,duplicated=True)
    with pytest.raises(ValueError, match='Reused reference'):
        mod.run(manifest,tmp_path/'out.json',bootstrap=100)
    assert not (tmp_path/'out.json').exists()


def test_invalid_config_rejected(tmp_path):
    with pytest.raises(ValueError, match='bootstrap'):
        mod.run(tmp_path/'absent.csv',tmp_path/'out.json',bootstrap=0)
