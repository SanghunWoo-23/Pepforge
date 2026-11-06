from pathlib import Path
from tools.v6_public_release_audit import audit

ROOT=Path(__file__).resolve().parents[1]

def test_release_package_identifiers_and_current_manuals_are_consistent():
    result=audit(ROOT)
    assert result['pass'], result['issues']
    assert result['version']=='V6.0.0'
    assert result['bundled_spps_version']=='V8.0.0'

def test_root_exposes_only_two_supported_batch_entrypoints():
    assert {x.name for x in ROOT.glob('*.bat')}=={
        'INSTALL_BUILD_TOOLS_AND_BUILD.bat','RUN_PEPFORGE_SOURCE.bat'}
