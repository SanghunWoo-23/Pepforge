from pathlib import Path

from spps_v4_gui import experimental_data, ml_advisor_v5


def _add(db: Path, aa_eq: float, loading: float, *, aa='Fmoc-Ile-OH'):
    experimental_data.add_record('loading', {
        'resin_type':'2-CTC','amino_acid_raw':aa,'aa_eq':aa_eq,
        'base':'DIEA','base_eq':2.0,'loading_time_h':4.0,
        'loading_rate_mmol_g':loading,
    }, db, status='verified')


def test_target_loading_inverse_interpolates_only_inside_exact_history(tmp_path: Path):
    db=tmp_path/'loading.sqlite'; experimental_data.initialize(db)
    _add(db,0.2,0.2); _add(db,0.4,0.4)
    out=ml_advisor_v5.loading_advice(
        resin='2-CTC',amino_acid='Fmoc-Ile-OH',aa_eq=0.2,base_eq=2,
        loading_time_h=4,target_loading_mmol_g=0.3,db_path=db,include_parsed=True,
    )
    rec=out['target_recommendation']
    assert rec['apply_allowed'] is True
    assert rec['recommendation_kind']=='BOUNDED TARGET INTERPOLATION'
    assert rec['aa_eq']==0.3
    assert rec['predicted_loading_mmol_g']==0.3


def test_target_loading_inverse_never_extrapolates(tmp_path: Path):
    db=tmp_path/'loading.sqlite'; experimental_data.initialize(db)
    _add(db,0.2,0.2); _add(db,0.4,0.4)
    out=ml_advisor_v5.loading_advice(
        resin='2-CTC',amino_acid='Fmoc-Ile-OH',base_eq=2,loading_time_h=4,
        target_loading_mmol_g=0.6,db_path=db,include_parsed=True,
    )
    rec=out['target_recommendation']
    assert rec['apply_allowed'] is False
    assert rec['recommendation_kind']=='TARGET OUTSIDE OBSERVED RANGE'


def test_target_loading_inverse_does_not_mix_other_amino_acid(tmp_path: Path):
    db=tmp_path/'loading.sqlite'; experimental_data.initialize(db)
    _add(db,0.2,0.2,aa='Fmoc-Ile-OH'); _add(db,0.4,0.4,aa='Fmoc-Ile-OH')
    out=ml_advisor_v5.loading_advice(
        resin='2-CTC',amino_acid='Fmoc-Val-OH',target_loading_mmol_g=0.3,
        db_path=db,include_parsed=True,
    )
    assert out['target_recommendation'] is None
