import math
import pytest
from peptiforg_core.v6_boresch_correction import BoreschRestraint,numerical_boresch_release,R_KCAL,V_STANDARD_A3

def params(ktheta=15.):
    return BoreschRestraint(4.,1.2,1.4,(0.5,-2.0,2.7),12.,ktheta,ktheta,(12.,12.,12.))

def test_finite_release():
    d=numerical_boresch_release(params())
    assert d['result_type']=='RESTRAINT_RELEASE_ONLY_NOT_BINDING_DG'
    assert -30 < d['delta_g_release_kcal_mol'] < 0
    assert d['delta_g_release_kj_mol']==pytest.approx(d['delta_g_release_kcal_mol']*4.184)

def test_stiffer_restrictions_more_negative_release():
    assert numerical_boresch_release(params(100.))['delta_g_release_kcal_mol'] < numerical_boresch_release(params(10.))['delta_g_release_kcal_mol']

def test_phi_reference_invariant():
    a=params()
    b=BoreschRestraint(a.r0_angstrom,a.theta_a_rad,a.theta_b_rad,(1.,2.,-3.),a.k_r_kcal_mol_a2,a.k_theta_a_kcal_mol_rad2,a.k_theta_b_kcal_mol_rad2,a.k_phi_kcal_mol_rad2)
    assert numerical_boresch_release(a)['delta_g_release_kcal_mol']==pytest.approx(numerical_boresch_release(b)['delta_g_release_kcal_mol'])

@pytest.mark.parametrize('field,value', [('r0_angstrom',0),('theta_a_rad',0),('theta_b_rad',math.pi),('k_r_kcal_mol_a2',-1),('k_theta_a_kcal_mol_rad2',0)])
def test_invalid(field,value):
    from dataclasses import replace
    with pytest.raises(ValueError):numerical_boresch_release(replace(params(),**{field:value}))

def test_weak_force_finite():
    d=numerical_boresch_release(params(0.05))
    assert math.isfinite(d['delta_g_release_kcal_mol'])

def test_volume():
    assert V_STANDARD_A3 == pytest.approx(1660.539,rel=1e-5)
