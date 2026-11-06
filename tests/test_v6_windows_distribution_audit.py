from pathlib import Path
from tools.v6_windows_distribution_audit import audit


def test_real_project_source_layout():
    result = audit(Path(__file__).resolve().parents[1])
    assert result['static_audit_pass']
    assert not result['release_approved']
    assert not result['windows_runtime_verified']


def test_missing_build_files_fail_closed(tmp_path):
    (tmp_path / 'main_launcher.py').write_text('print(1)')
    result = audit(tmp_path)
    assert not result['static_audit_pass']
    assert not result['release_approved']


def test_missing_exe_never_marked_verified(tmp_path):
    result = audit(Path(__file__).resolve().parents[1], tmp_path / 'Pepforge.exe')
    assert result['exe']['checked']
    assert not result['exe']['found']
    assert not result['windows_runtime_verified']
