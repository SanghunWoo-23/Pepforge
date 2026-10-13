from pathlib import Path
import json
import pytest
from peptiforg_core.local_resource_manager import normalize_execution_mode, resource_status, write_manifest_template


def test_execution_modes_are_explicit():
    assert normalize_execution_mode('Offline / Local') == 'offline'
    assert normalize_execution_mode('auto') == 'auto'
    assert normalize_execution_mode('online enhanced') == 'online_enhanced'
    with pytest.raises(ValueError): normalize_execution_mode('magic')


def test_missing_manifest_is_valid_offline_state(tmp_path: Path):
    status = resource_status(tmp_path, execution_mode='offline')
    assert status['manifest_status'] == 'MANIFEST_NOT_FOUND'
    assert status['network_allowed'] is False
    assert status['local_first'] is True


def test_manifest_template_and_path_readiness(tmp_path: Path):
    path = Path(write_manifest_template(tmp_path))
    assert path.exists()
    payload = json.loads(path.read_text())
    assert 'haddock3' in payload['resources']
    (tmp_path/'models'/'esm2_8m').mkdir(parents=True)
    status = resource_status(tmp_path, execution_mode='auto')
    assert status['resources']['esm2_8m']['available'] is True
    assert status['network_allowed'] is True
