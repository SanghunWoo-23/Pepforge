"""Numerical six-coordinate Boresch restraint release free energy.

Computes a *single protocol-defined* restraint release contribution only.
Never silently inserts it into an ABFE cycle: the sign of a cycle term depends
on the exact order of attachment, decoupling and removal steps.

Coordinates: r (Å), theta A/B (rad), three periodic torsions (rad).
Force constants: kcal/mol/Å² for r; kcal/mol/rad² for the angles/torsions.
U = 1/2 sum_i k_i delta_i²; dihedral deltas are wrapped to [-pi,pi].
The six-dimensional measure is r² sin(theta A) sin(theta B) dr dthetaA
 dthetaB dphi1 dphi2 dphi3, following the Boresch orientational convention.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import pi, sin, log, isfinite
from scipy.integrate import quad

R_KCAL = 0.00198720425864083  # kcal/(mol K)
AVOGADRO = 6.02214076e23
# 1 molecule at 1 mol/L occupies 1e27/NA cubic Å.
V_STANDARD_A3 = 1e27 / AVOGADRO

@dataclass(frozen=True)
class BoreschRestraint:
    r0_angstrom: float
    theta_a_rad: float
    theta_b_rad: float
    phi_rad: tuple[float, float, float]
    k_r_kcal_mol_a2: float
    k_theta_a_kcal_mol_rad2: float
    k_theta_b_kcal_mol_rad2: float
    k_phi_kcal_mol_rad2: tuple[float, float, float]


def _require_real(value, name, *, lower=None, upper=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if lower is not None and value <= lower: raise ValueError(f'{name} must be > {lower}')
    if upper is not None and value >= upper: raise ValueError(f'{name} must be < {upper}')


def numerical_boresch_release(restraint: BoreschRestraint, *, temperature_k: float = 298.15):
    """Compute F(unrestrained 1M) - F(restrained) by 1D quadrature.

    The reference unrestrained six-coordinate volume is 8*pi²*V°.
    Negative release values are expected for stiff localization.
    No estimator of physical binding free energy is returned.
    """
    _require_real(temperature_k, 'temperature_k', lower=0)
    _require_real(restraint.r0_angstrom, 'r0_angstrom', lower=0)
    for nm, theta in [('theta_a_rad',restraint.theta_a_rad),('theta_b_rad',restraint.theta_b_rad)]:
        _require_real(theta, nm, lower=0, upper=pi)
    if len(restraint.phi_rad)!=3 or len(restraint.k_phi_kcal_mol_rad2)!=3:
        raise ValueError('Exactly three torsions and stiffnesses required')
    for i,p in enumerate(restraint.phi_rad): _require_real(p, f'phi_{i}')
    ks=[restraint.k_r_kcal_mol_a2,restraint.k_theta_a_kcal_mol_rad2,
        restraint.k_theta_b_kcal_mol_rad2,*restraint.k_phi_kcal_mol_rad2]
    for i,k in enumerate(ks): _require_real(k,f'force_constant_{i}',lower=0)
    beta=1/(R_KCAL*temperature_k)
    r0=restraint.r0_angstrom
    kr=restraint.k_r_kcal_mol_a2
    # Avoid fixed truncation of radial tail; scipy integrates to infinity.
    radial=quad(lambda r: r*r * __import__('math').exp(-0.5*beta*kr*(r-r0)**2),0,__import__('math').inf,
                epsrel=1e-10, limit=350)[0]
    angles=[]
    for theta0,k in zip((restraint.theta_a_rad,restraint.theta_b_rad),ks[1:3]):
        angles.append(quad(lambda t: sin(t)*__import__('math').exp(-0.5*beta*k*(t-theta0)**2),0,pi,
                           epsrel=1e-10,limit=350)[0])
    torsions=[]
    for k in ks[3:]:
        # Periodic signed difference; integrals invariant to reference phi.
        torsions.append(2*quad(lambda p: __import__('math').exp(-0.5*beta*k*p*p),0,pi,
                               epsrel=1e-10,limit=350)[0])
    values=[radial,*angles,*torsions]
    if any(v<=0 or not isfinite(v) for v in values):
        raise ValueError('Numerical quadrature failed; inspect stiffness and geometry')
    z=1.
    for v in values: z*=v
    ratio=z/(8*pi*pi*V_STANDARD_A3)
    dg=R_KCAL*temperature_k*log(ratio)
    return {
        'result_type':'RESTRAINT_RELEASE_ONLY_NOT_BINDING_DG',
        'delta_g_release_kcal_mol':dg,
        'delta_g_release_kj_mol':dg*4.184,
        'temperature_k':temperature_k,
        'standard_concentration_mol_l':1.0,
        'standard_volume_angstrom_cubed':V_STANDARD_A3,
        'integral_factor_angstrom_cubed':z,
        'restraint_dimension':6,
        'sign_convention':'F(unrestrained_1M)-F(restrained), NOT a plug-in ABFE correction without cycle sign audit',
        'assumptions':['harmonic distance/angle restraints and minimum-image periodic torsions',
                       'separable 6-coordinate rigid-rotor Jacobian',
                       'does not account for restraints coupling to flexible host/guest internal coordinates',
                       'check anchor non-collinearity, restrained distributions, and protocol match before use']}
