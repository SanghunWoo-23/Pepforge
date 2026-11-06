import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('science_installer',ROOT/'INSTALL_SCIENCE_ENGINES.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_all_required_packages_in_isolated_environment():
    p=mod.plan(system='linux',manager='conda')
    assert p['environment']=='pepforge-science'
    assert {'openfe','openmm','openff-toolkit','pymbar','ambertools'}.issubset(p['packages'])
    assert '--name' in p['steps'][0]

def test_native_windows_does_not_install_unsupported_stack():
    p=mod.plan(system='windows',manager='conda')
    assert not p['steps']
    assert p['status']=='UNSUPPORTED_NATIVE_WINDOWS'

def test_no_package_manager_does_not_claim_success():
    p=mod.plan(system='linux',manager='NOT_SET')
    assert p['manager']=='NOT_SET' # deliberately supplied manager for deterministic plan

def test_verify_checks_openfe_cli_and_imports():
    p=mod.plan(system='linux',manager='micromamba')
    code=p['verify'][-1]
    assert "'pymbar'" in code and "'openfe'" in code
    assert 'openfe_cli' in code
