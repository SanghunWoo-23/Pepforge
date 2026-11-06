import pytest
from peptiforg_core.v6_solvated_gaff_md import run_solvated_gaff_md
@pytest.mark.parametrize('kwargs',[
    {'production_steps':0}, {'report_interval':0}, {'report_interval':6000},
    {'temperature_k':float('nan')}, {'ionic_strength_molar':-1},
    {'equilibration_steps':1.4}, {'seed':True}, {'padding_nm':0}])
def test_reject_bad_protocol_prior_to_execution(tmp_path,kwargs):
    with pytest.raises(ValueError):
        run_solvated_gaff_md('none.pdb','none.sdf',tmp_path/'out',**kwargs)
def test_reject_missing_input_without_backend(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_solvated_gaff_md('missing.pdb','missing.sdf',tmp_path/'out')
