from suite_gui.sequence_risk_map_v8 import build_sequence_risk_map
from suite_gui.sequence_risk_ui_v8 import export_risk_report
import json
import csv
import pytest


def test_v8_export_without_experimental_claim(tmp_path):
    report=build_sequence_risk_map('ADGVPVVVVVV')
    assert report['findings']
    js=tmp_path/'risk.json'; csvfile=tmp_path/'risk.csv'
    export_risk_report(report,js); export_risk_report(report,csvfile)
    stored=json.loads(js.read_text(encoding='utf-8'))
    assert stored['recommendations_auto_applied'] is False
    assert all(not x['provenance']['experimental_observation'] for x in stored['findings'])
    with csvfile.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==len(report['findings'])
    assert 'SEQ-ASPARTIMIDE' in {r['rule_id'] for r in rows}


def test_v8_bad_export_extension(tmp_path):
    with pytest.raises(ValueError):
        export_risk_report(build_sequence_risk_map('AAAA'),tmp_path/'report.txt')
