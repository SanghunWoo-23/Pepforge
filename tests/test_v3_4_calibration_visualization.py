from pathlib import Path
import csv
from peptiforg_core.calibration_visualization import group_calibration_by_target, summarize_target_calibration, export_calibration_visualization_package

def _write_cal(path):
    with path.open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=['target','sequence','affinity_nM','potency_class','calibration_score','source'])
        w.writeheader()
        w.writerow({'target':'T1','sequence':'AAA','affinity_nM':'5','potency_class':'very_strong_nM','calibration_score':'-9','source':'s1'})
        w.writerow({'target':'T1','sequence':'BBB','affinity_nM':'80','potency_class':'strong_nM','calibration_score':'-7','source':'s2'})
        w.writerow({'target':'T2','sequence':'CCC','affinity_nM':'2000','potency_class':'weak_uM','calibration_score':'-4','source':'s3'})

def test_group_and_summary(tmp_path):
    p=tmp_path/'calibration_dataset_normalized.csv'; _write_cal(p)
    rows=list(csv.DictReader(p.open()))
    groups=group_calibration_by_target(rows)
    assert set(groups)=={'T1','T2'}
    assert summarize_target_calibration('T1', groups['T1'])['usable_records']==2

def test_export_model_cards(tmp_path):
    p=tmp_path/'calibration_dataset_normalized.csv'; _write_cal(p)
    paths=export_calibration_visualization_package(p,tmp_path)
    assert Path(paths['target_model_card_index_csv']).exists()
    assert (tmp_path/'calibration_visualization_model_cards'/'T1'/'target_model_card.md').exists()
    assert (tmp_path/'calibration_visualization_model_cards'/'T1'/'target_class_count_chart.svg').exists()
