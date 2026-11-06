from types import SimpleNamespace
from unittest.mock import patch
import json
import pytest
from suite_gui import persistence_workflow as pw


def test_empty_modern_project_remains_empty():
    gui = SimpleNamespace(pm_items=[{'project': 'existing'}])
    with patch.object(pw.synthesis_execution, 'ensure_execution'), patch.object(pw.ml_dataset, 'ensure_review'), patch.object(pw.data_system, 'ensure_hierarchy'), patch.object(pw.data_system, 'sync_active_run'):
        _, _, items, legacy, index = pw._prepare_state(gui, {'pm_items': []})
    assert items == [] and legacy is False and index == 0


def test_schema_invalid_primary_recovers_valid_backup(tmp_path):
    source = tmp_path / 'project.json'
    source.write_text(json.dumps({'pm_items': 'wrong'}), encoding='utf-8')
    backup = tmp_path / 'project.json.bak'
    backup.write_text(json.dumps({'pm_items': []}), encoding='utf-8')
    data, actual, recovered = pw._read_valid_project_with_recovery(SimpleNamespace(), source)
    assert recovered and actual == backup and data['pm_items'] == []


def test_schema_invalid_primary_and_backup_rejected(tmp_path):
    source = tmp_path / 'project.json'
    source.write_text(json.dumps({'pm_items': 'wrong'}), encoding='utf-8')
    backup = tmp_path / 'project.json.bak'
    backup.write_text(json.dumps({'pm_items': 7}), encoding='utf-8')
    with pytest.raises(ValueError):
        pw._read_valid_project_with_recovery(SimpleNamespace(), source)


def test_save_as_same_file_detects_external_modification(tmp_path):
    source = tmp_path / 'project.json'
    source.write_text('{"pm_items": []}', encoding='utf-8')
    gui = SimpleNamespace(_loaded_project_path=source, _loaded_project_fingerprint='outdated')
    with patch.object(pw.messagebox, 'askyesno', return_value=True), patch.object(pw.messagebox, 'showerror'), patch.object(pw, 'collect_state') as collect:
        assert pw.save_project_as(gui, source, show=False) is None
    collect.assert_not_called()
    assert source.read_text(encoding='utf-8') == '{"pm_items": []}'
    assert gui._loaded_project_path == source
