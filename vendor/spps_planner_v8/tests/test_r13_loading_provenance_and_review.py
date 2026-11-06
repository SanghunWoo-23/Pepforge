from __future__ import annotations

import csv
from pathlib import Path

import pytest

from suite_gui import experimental_data
from tools import loading_seed_review


def _write_loading_csv(path: Path, rows: list[dict], *, include_locator: bool = True) -> Path:
    fields = [
        'status','date','resin_type','amino_acid_raw','amino_acid_normalized',
        'aa_eq','base','base_eq','loading_time_h','absorbance','loading_rate_mmol_g',
    ]
    if include_locator:
        fields += ['source_file','source_locator']
    fields += ['raw_note']
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _base_row(**changes):
    row = {
        'status':'parsed','date':'2026-09-01','resin_type':'2-CTC',
        'amino_acid_raw':'Fmoc-Gly-OH','amino_acid_normalized':'Fmoc-Gly-OH',
        'aa_eq':'2','base':'DIEA','base_eq':'4','loading_time_h':'4',
        'absorbance':'0.5','loading_rate_mmol_g':'0.7','raw_note':'repeat experiment',
        'source_file':'','source_locator':'',
    }
    row.update(changes)
    return row


def test_general_loading_csv_preserves_legitimate_identical_repeats(tmp_path: Path):
    source = _write_loading_csv(tmp_path/'operator_loading.csv', [_base_row(), _base_row()])
    db = tmp_path/'exp.sqlite'
    result = experimental_data.import_loading_csv(source, db)
    assert result['inserted'] == 2
    rows = experimental_data.list_records('loading', db)
    assert len(rows) == 2
    assert {row['source_locator'] for row in rows} == {'row2', 'row3'}


def test_seed_revision_dedup_survives_operator_verification_and_enriches_locator(tmp_path: Path):
    source = tmp_path/'loading_history_seed.csv'
    db = tmp_path/'exp.sqlite'
    _write_loading_csv(source, [_base_row()], include_locator=True)
    assert experimental_data.import_loading_csv(source, db)['inserted'] == 1
    original = experimental_data.list_records('loading', db)[0]
    experimental_data.set_status('loading', [original['record_id']], 'verified', db)

    _write_loading_csv(source, [_base_row(source_file='photo_001.jpg', source_locator='entry A')], include_locator=True)
    assert experimental_data.import_loading_csv(source, db)['inserted'] == 0
    rows = experimental_data.list_records('loading', db)
    assert len(rows) == 1
    assert rows[0]['status'] == 'verified'
    assert rows[0]['source_locator'] == 'photo_001.jpg | entry A'


def test_loading_csv_preserves_explicit_source_provenance(tmp_path: Path):
    source = _write_loading_csv(
        tmp_path/'loading.csv',
        [_base_row(source_file='uvvis_14.jpg', source_locator='table row 3')],
    )
    db = tmp_path/'exp.sqlite'
    experimental_data.import_loading_csv(source, db)
    row = experimental_data.list_records('loading', db)[0]
    assert row['source_locator'] == 'uvvis_14.jpg | table row 3'



def _write_duplicate_cleavage_report(path: Path) -> Path:
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Report'
    for _ in range(2):
        sheet.append(['P1','',0.2,'OP',''])
        sheet.append(['Cleavage','TFA','1 mL','30 eq / 2 h','same observation'])
        sheet.append(['','TIS','0.05 mL','',''])
        sheet.append([])
    workbook.save(path)
    return path


def test_general_cleavage_report_preserves_identical_repeat_blocks_but_seed_dedups(tmp_path: Path):
    general = _write_duplicate_cleavage_report(tmp_path/'operator_report.xlsx')
    general_db = tmp_path/'general.sqlite'
    assert experimental_data.import_cleavage_report(general, general_db)['inserted'] == 2
    assert len(experimental_data.list_records('cleavage', general_db)) == 2

    seed = _write_duplicate_cleavage_report(tmp_path/'Cleavage_Report_seed.xlsx')
    seed_db = tmp_path/'seed.sqlite'
    assert experimental_data.import_cleavage_report(seed, seed_db)['inserted'] == 1
    assert len(experimental_data.list_records('cleavage', seed_db)) == 1

def _write_staging(path: Path, rows: list[dict]) -> Path:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=loading_seed_review.STAGING_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _write_canonical(path: Path, rows: list[dict]) -> Path:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=loading_seed_review.CANONICAL_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _stage_row(**changes):
    row = {field:'' for field in loading_seed_review.STAGING_FIELDS}
    row.update({
        'review_state':'APPROVED','date':'2026-09-02','resin_type':'Trityl/2-CTC resin',
        'amino_acid_raw':'Fmoc-Arg(Pbf)-OH','amino_acid_normalized':'Fmoc-Arg(Pbf)-OH',
        'aa_eq':'2','base':'DIEA','base_eq':'4','loading_time_h':'4',
        'loading_rate_mmol_g':'0.68','source_file':'source_A.jpg',
        'source_locator':'handwritten row 1','raw_note':'transcribed without correction',
    })
    row.update(changes)
    return row


def test_staging_review_blocks_ambiguous_and_duplicate_rows_and_promotes_only_ready(tmp_path: Path):
    canonical = _write_canonical(tmp_path/'canonical.csv', [])
    staging = _write_staging(tmp_path/'staging.csv', [
        _stage_row(),
        _stage_row(date='2026-09-03', ambiguity_reason='base eq unreadable'),
        _stage_row(date='2026-09-04', review_state='PENDING'),
        _stage_row(),
    ])
    report = loading_seed_review.review_staging(staging, canonical)
    assert [row['review_result'] for row in report] == ['READY','AMBIGUOUS','REVIEW','DUPLICATE']

    out = tmp_path/'promoted.csv'
    result = loading_seed_review.promote_staging(staging, canonical, out)
    assert result['promoted_rows'] == 1
    _, promoted = loading_seed_review._read_csv(out)
    assert len(promoted) == 1
    assert promoted[0]['source_locator'] == 'source_A.jpg | handwritten row 1'


def test_staging_promotion_refuses_in_place_seed_overwrite(tmp_path: Path):
    canonical = _write_canonical(tmp_path/'canonical.csv', [])
    staging = _write_staging(tmp_path/'staging.csv', [_stage_row()])
    with pytest.raises(ValueError, match='in-place'):
        loading_seed_review.promote_staging(staging, canonical, canonical)


def test_loading_import_default_base_is_resin_aware(tmp_path: Path):
    rows = [
        _base_row(resin_type='2-CTC', base='', base_eq='4', source_locator='trityl'),
        _base_row(resin_type='Wang resin', base='', base_eq='0', source_locator='wang'),
        _base_row(resin_type='Rink Amide AM resin', base='', base_eq='0', source_locator='rink'),
    ]
    source = _write_loading_csv(tmp_path/'loading.csv', rows)
    db = tmp_path/'exp.sqlite'
    experimental_data.import_loading_csv(source, db)
    imported = {row['source_locator']: row for row in experimental_data.list_records('loading', db)}
    assert imported['trityl']['base'] == 'DIEA'
    assert imported['wang']['base'] == ''
    assert imported['rink']['base'] == ''


def test_seed_promotion_enriches_canonical_duplicate_provenance(tmp_path: Path):
    base = _stage_row(source_file='', source_locator='')
    canonical_row = {field: base.get(field, '') for field in loading_seed_review.CANONICAL_FIELDS}
    canonical = _write_canonical(tmp_path/'canonical.csv', [canonical_row])
    staged = _stage_row(source_file='uvvis_source.jpg', source_locator='handwritten row 07')
    staging = _write_staging(tmp_path/'staging.csv', [staged])
    out = tmp_path/'promoted.csv'
    result = loading_seed_review.promote_staging(staging, canonical, out)
    assert result['promoted_rows'] == 0
    assert result['enriched_duplicates'] == 1
    _, rows = loading_seed_review._read_csv(out)
    assert len(rows) == 1
    assert rows[0]['source_locator'] == 'uvvis_source.jpg | handwritten row 07'
