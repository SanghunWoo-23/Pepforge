import csv, math
import pytest
from peptiforg_core.v6_abfe_experimental_validation import analyze_csv, ValidationError
FIELDS=['case_id','family','split','calc_dg_kcal_mol','calc_uncertainty_kcal_mol','kd_molar','temperature_K','replicates','source_doi']
def mk(tmp_path, rows):
 p=tmp_path/'reference.csv'
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
 return p
def row(i,f='F'):
 return dict(case_id=str(i),family=f,split='independent_test',calc_dg_kcal_mol=-7,calc_uncertainty_kcal_mol=0.2,kd_molar=1e-5,temperature_K=298.15,replicates=3,source_doi='10.1000/example')
def test_metrics_fixture_not_certified(tmp_path):
 p=mk(tmp_path,[row(1,'a'),row(2,'b')]); out=analyze_csv(p,min_cases=2,bootstrap=100)
 assert out['n_cases']==2 and out['science_accuracy_certified'] is False
 assert out['family_bootstrap_mae_95pct_ci'] is not None
 assert abs(out['cases'][0]['experimental']-(.00198720425864083*298.15*math.log(1e-5)))<1e-12
@pytest.mark.parametrize('mutator',[
 lambda r:r.update(kd_molar='0'),lambda r:r.update(split='train'),lambda r:r.update(replicates='1'),
 lambda r:r.update(calc_dg_kcal_mol='nan'),lambda r:r.update(source_doi='')])
def test_invalid_refused(tmp_path,mutator):
 r=row(1);mutator(r)
 with pytest.raises(ValidationError):analyze_csv(mk(tmp_path,[r]),min_cases=1)
def test_duplicate_refused(tmp_path):
 with pytest.raises(ValidationError):analyze_csv(mk(tmp_path,[row(1),row(1)]),min_cases=1)


def test_invalid_bootstrap_configuration_fails_before_file_read():
    from peptiforg_core.v6_abfe_experimental_validation import analyze_csv, ValidationError
    import pytest
    for kw in ({"bootstrap": 0}, {"bootstrap": -10}, {"bootstrap": True}, {"min_cases": 0}, {"seed": True}):
        with pytest.raises(ValidationError):
            analyze_csv("no_such_input_file.csv", **kw)
