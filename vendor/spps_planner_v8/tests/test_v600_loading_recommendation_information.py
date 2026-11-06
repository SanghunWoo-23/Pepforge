from pathlib import Path

from suite_gui import experimental_data, ml_advisor_v5
from suite_gui.modules.evidence_detail_dialog import format_sections


def _add(db: Path, *, date: str, aa_eq: float, base_eq: float, loading: float,
         aa: str = 'Fmoc-Arg(Pbf)-OH', capping='1', locator=''):
    return experimental_data.add_record('loading', {
        'date': date,
        'resin_type': '2-CTC',
        'amino_acid_raw': aa,
        'amino_acid_normalized': aa,
        'aa_eq': aa_eq,
        'base': 'DIEA',
        'base_eq': base_eq,
        'loading_time_h': 4.0,
        'loading_rate_mmol_g': loading,
        'capping_performed': capping,
        'capping_method': 'recorded capping' if capping else '',
        'source_locator': locator,
    }, db, status='verified')


def test_loading_recommendation_exposes_exact_coverage_repeatability_and_nearest_conditions(tmp_path: Path):
    db = tmp_path / 'exp.sqlite'
    experimental_data.initialize(db)
    _add(db, date='2026-01-01', aa_eq=2, base_eq=4, loading=0.65, locator='pageA row1')
    _add(db, date='2026-01-02', aa_eq=2, base_eq=4, loading=0.70, locator='pageA row2')
    _add(db, date='2026-01-03', aa_eq=2, base_eq=4, loading=0.75, locator='pageA row3')
    _add(db, date='2026-01-04', aa_eq=1, base_eq=2, loading=0.40, locator='pageB row1')
    _add(db, date='2026-01-05', aa_eq=2, base_eq=4, loading=0.99, aa='Fmoc-Val-OH', locator='other-aa')

    out = ml_advisor_v5.loading_advice(
        resin='2-CTC', amino_acid='Fmoc-Arg(Pbf)-OH', aa_eq=2, base_eq=4,
        loading_time_h=4, target_loading_mmol_g=0.68, db_path=db, include_parsed=True,
    )
    profile = out['exact_evidence_profile']
    rec = out['target_recommendation']

    assert profile['exact_record_count'] == 4
    assert profile['verified_record_count'] == 4
    assert profile['distinct_condition_count'] == 2
    assert profile['repeated_condition_count'] == 1
    assert profile['date_min'] == '2026-01-01'
    assert profile['date_max'] == '2026-01-04'
    assert profile['observed_loading_min'] == 0.4
    assert profile['observed_loading_max'] == 0.75

    assert rec['recommendation_kind'] == 'OBSERVED REPEATED CONDITION'
    assert rec['condition_support']['evidence_count'] == 3
    assert rec['condition_support']['loading_median_mmol_g'] == 0.7
    assert rec['condition_support']['loading_min_mmol_g'] == 0.65
    assert rec['condition_support']['loading_max_mmol_g'] == 0.75
    assert rec['condition_support']['capping_observed_count'] == 3
    assert rec['condition_support']['capping_known_count'] == 3
    assert rec['target_delta_mmol_g'] == 0.02
    assert len(rec['nearest_observed_conditions']) == 2
    assert rec['nearest_observed_conditions'][0]['aa_eq'] == 2.0


def test_loading_evidence_detail_includes_coverage_and_condition_support(tmp_path: Path):
    db = tmp_path / 'exp.sqlite'
    experimental_data.initialize(db)
    _add(db, date='2026-02-01', aa_eq=2, base_eq=4, loading=0.65)
    _add(db, date='2026-02-02', aa_eq=2, base_eq=4, loading=0.70)
    out = ml_advisor_v5.loading_advice(
        resin='2-CTC', amino_acid='Fmoc-Arg(Pbf)-OH', aa_eq=2, base_eq=4,
        loading_time_h=4, target_loading_mmol_g=0.68, db_path=db, include_parsed=True,
    )
    text = format_sections([('Loading', out)])
    assert 'Exact resin + loaded-AA coverage:' in text
    assert 'Selected-condition support:' in text
    assert 'Nearest observed conditions:' in text
    assert 'records=2' in text
