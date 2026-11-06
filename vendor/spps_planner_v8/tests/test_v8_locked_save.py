from concurrent.futures import ThreadPoolExecutor
import json
import threading
import pytest
from suite_gui import state_persistence as sp


def test_compare_and_swap_prevents_lost_update(tmp_path):
    p = tmp_path / 'test.json'
    sp.atomic_write_json_with_backup(p, {'v': 1})
    old = sp.file_sha256(p)
    sp.atomic_write_json_with_backup(p, {'v': 2})
    with pytest.raises(RuntimeError, match='changed outside'):
        sp.atomic_write_json_with_backup(p, {'v': 3}, expected_sha256=old)
    assert sp.read_json_object(p) == {'v': 2}


def test_save_as_destination_appears(tmp_path):
    p = tmp_path / 'appeared.json'
    sp.atomic_write_json(p, {'someone_else': True})
    with pytest.raises(RuntimeError, match='appeared'):
        sp.atomic_write_json_with_backup(p, {'v': 1}, expected_absent=True)
    assert sp.read_json_object(p) == {'someone_else': True}


def test_concurrent_writes_do_not_corrupt_backup(tmp_path):
    p = tmp_path / 'concurrent.json'
    barrier = threading.Barrier(2)
    def worker(value):
        barrier.wait()
        for idx in range(12):
            sp.atomic_write_json_with_backup(p, {'writer': value, 'index': idx, 'payload': '한글' * 200})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker, ('A','B')))
    primary = sp.read_json_object(p)
    backup = sp.read_json_object(p.with_suffix('.json.bak'))
    assert primary['writer'] in ('A','B')
    assert backup['writer'] in ('A','B')
    assert primary['payload'] == backup['payload'] == '한글' * 200


def test_lock_released_after_write_error(tmp_path, monkeypatch):
    p = tmp_path / 'failed.json'
    def error(*a, **kw):
        raise OSError('disk full')
    original = sp._write_temp_json
    monkeypatch.setattr(sp, '_write_temp_json', error)
    with pytest.raises(OSError, match='disk full'):
        sp.atomic_write_json_with_backup(p, {'v': 1})
    monkeypatch.setattr(sp, '_write_temp_json', original)
    assert sp.atomic_write_json_with_backup(p, {'v': 2}) == p
