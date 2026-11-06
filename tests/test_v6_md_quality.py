import csv
import json
import math
import pytest
from peptiforg_core.v6_md_quality import analyze_md_state_log, write_md_quality_report


def state_csv(tmp_path,n=120,temp=300.0):
    path=tmp_path/'production.csv'
    with path.open('w',newline='') as fp:
        w=csv.writer(fp)
        w.writerow(['#"Step"','"Potential Energy (kJ/mole)"','"Temperature (K)"','"Box Volume (nm^3)"'])
        for i in range(n):w.writerow([(i+1)*500,-200+i*0.001,temp+math.sin(i),900])
    return path


def test_realistic_synthetic_log_is_not_claimed_converged(tmp_path):
    result=analyze_md_state_log(state_csv(tmp_path))
    assert result['status'] in ('PRELIMINARY_DIAGNOSTICS_PASS','NOT_VALIDATED')
    assert 'No binding free energy is calculated' in result['limitations']


def test_reject_duplicate_steps(tmp_path):
    p=state_csv(tmp_path,10)
    s=p.read_text().replace('1000,','500,',1)
    p.write_text(s)
    with pytest.raises(ValueError,match='increasing'):
        analyze_md_state_log(p)


def test_reject_nonfinite(tmp_path):
    p=state_csv(tmp_path,10)
    p.write_text(p.read_text().replace('300.0','nan',1))
    with pytest.raises(ValueError,match='Nonfinite'):
        analyze_md_state_log(p)


def test_json_report_and_no_overwrite(tmp_path):
    p=state_csv(tmp_path)
    output=tmp_path/'report.json'
    record=write_md_quality_report(p,output)
    assert json.loads(output.read_text())['input_sha256']==record['input_sha256']
    with pytest.raises(FileExistsError):write_md_quality_report(p,output)


def test_temperature_off_target(tmp_path):
    r=analyze_md_state_log(state_csv(tmp_path,temp=450))
    assert 'TEMPERATURE_OFF_TARGET' in r['issues']
