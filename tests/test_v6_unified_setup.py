"""Offline contract tests for the consolidated Windows/WSL2 installer."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pepforge_science_unified',ROOT/'INSTALL_SCIENCE_ENGINES.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_unified_menu_and_modes_are_present():
    bat=(ROOT/'INSTALL_BUILD_TOOLS_AND_BUILD.bat').read_text()
    for mode in ('--build','--all','--science','--verify-science'):
        assert mode in bat
    assert 'set "AFTER_BUILD_SCIENCE=1"' in bat
    assert 'set "SCIENCE_ACTION=--install --bootstrap-wsl"' in bat
    assert 'Pepforge_Setup_v6.0.0.exe' in bat
    assert not (ROOT/'INSTALL_SCIENCE_ENGINES.bat').exists()


def test_inno_and_citation_version_v6():
    iss=(ROOT/'installer'/'Pepforge_Setup.iss').read_text()
    assert '#define MyAppVersion "6.0.0"' in iss
    assert 'OutputBaseFilename=Pepforge_Setup_v6.0.0' in iss
    assert 'AppVersion={#MyAppVersion}' in iss
    assert (ROOT/'VERSION.txt').read_text().strip()=='V6.0.0'
    assert 'version: "6.0.0"' in (ROOT/'CITATION.cff').read_text()
    assert "(str(ROOT / 'vendor' / 'spps_planner_v8'), 'vendor/spps_planner_v8')" in (ROOT/'installer'/'Pepforge.spec').read_text()


def test_science_package_selection_excludes_openmm_8_3():
    p=mod.plan(system='linux', manager='micromamba')
    assert p['status']=='READY'
    assert {'openfe','openmm','openff-toolkit','openmmforcefields','ambertools','pymbar'}.issubset(set(p['packages']))
    assert 'openmm!=8.3.0' in p['steps'][0]
    assert p['steps'][0][1]=='create'
    assert p['update_step'][1]=='install'
    assert 'openfe_cli' in p['verify'][-1]


def test_windows_never_proposes_native_openfe_install():
    p=mod.plan(system='windows',manager='conda')
    assert p['steps']==[]
    assert p['status']=='UNSUPPORTED_NATIVE_WINDOWS'


def test_wsl_path_with_unicode_and_spaces_quoted():
    command=mod.wsl_command('/mnt/c/연구 자료/a b/INSTALL_SCIENCE_ENGINES.py','--install')
    assert command[:3]==['wsl.exe','--exec','bash']
    assert command[3]=='-lc'
    assert "'/mnt/c/연구 자료/a b/INSTALL_SCIENCE_ENGINES.py'" in command[4]


def test_wsl_action_whitelist():
    import pytest
    with pytest.raises(ValueError):
        mod.wsl_command('/tmp/install.py','--evil')


def test_wsl_absent_fails_safely(monkeypatch):
    monkeypatch.setattr(mod.platform,'system',lambda:'Windows')
    monkeypatch.setattr(mod.shutil,'which',lambda name:None)
    assert mod._wsl_delegate('--install')!=0


def test_wsl1_or_failed_kernel_not_accepted(monkeypatch):
    monkeypatch.setattr(mod.platform,'system',lambda:'Windows')
    monkeypatch.setattr(mod.shutil,'which',lambda name:'/windows/wsl.exe')
    def fake_run(cmd, **kwargs):
        if cmd[1:3] == ['--list','--quiet']:
            return SimpleNamespace(returncode=0,stdout='Ubuntu\n'.encode('utf-16-le'))
        if cmd[-2:] == ['uname','-r']:
            return SimpleNamespace(returncode=0,stdout='4.4.0-microsoft')
        raise AssertionError(cmd)
    monkeypatch.setattr(mod.subprocess,'run',fake_run)
    assert mod._wsl_delegate('--install') != 0


def test_wsl2_delegate_calls_linux_not_windows_python(monkeypatch):
    monkeypatch.setattr(mod.platform,'system',lambda:'Windows')
    monkeypatch.setattr(mod.shutil,'which',lambda name:'/windows/wsl.exe')
    commands=[]
    def fake_run(cmd,**kwargs):
        commands.append(cmd)
        if cmd[1:3]==['--list','--quiet']:
            return SimpleNamespace(returncode=0, stdout=b'\xff\xfeU\x00b\x00u\x00n\x00t\x00u\x00\n\x00')
        if cmd[-2:]==['uname','-r']:
            return SimpleNamespace(returncode=0,stdout='5.15.153.1-microsoft-standard-WSL2')
        if 'wslpath' in cmd:
            return SimpleNamespace(returncode=0,stdout='/mnt/c/pep forge/INSTALL_SCIENCE_ENGINES.py\n')
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(mod.subprocess,'run',fake_run)
    assert mod._wsl_delegate('--verify-only')==0
    assert len(commands)==4
    assert commands[-1][1:3]==['--distribution','Ubuntu']
    assert 'python3' in commands[-1][-1]
    assert '--verify-only' in commands[-1][-1]


def test_linux_plan_only_does_not_claim_verified(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    original_plan=mod.plan
    monkeypatch.setattr(mod,'plan',lambda:original_plan(system='linux',manager='conda'))
    assert mod.main([])==0
    data=json.loads((tmp_path/'SCIENCE_ENGINE_INSTALL_REPORT.json').read_text())
    assert data['status']=='PLAN_ONLY'


def test_import_verification_failure_propagates(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    original_plan=mod.plan
    monkeypatch.setattr(mod,'plan',lambda:original_plan(system='linux',manager='conda'))
    monkeypatch.setattr(mod,'_execute',lambda command, logfile:3)
    assert mod.main(['--verify-only'])==2
    assert json.loads((tmp_path/'SCIENCE_ENGINE_INSTALL_REPORT.json').read_text())['status']=='VERIFICATION_FAILED'


def test_existing_environment_updates_and_verifies(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    original_plan=mod.plan
    monkeypatch.setattr(mod,'plan',lambda:original_plan(system='linux',manager='conda'))
    monkeypatch.setattr(mod,'_env_exists',lambda manager:True)
    commands=[]
    monkeypatch.setattr(mod,'_execute',lambda command,logfile:(commands.append(command),0)[1])
    assert mod.main(['--install'])==0
    assert commands[0][1]=='install' and commands[1][1]=='run'
    assert json.loads((tmp_path/'SCIENCE_ENGINE_INSTALL_REPORT.json').read_text())['status']=='VERIFIED'


def test_new_environment_creates_and_verifies(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    original_plan=mod.plan
    monkeypatch.setattr(mod,'plan',lambda:original_plan(system='linux',manager='conda'))
    monkeypatch.setattr(mod,'_env_exists',lambda manager:False)
    commands=[]
    monkeypatch.setattr(mod,'_execute',lambda command,logfile:(commands.append(command),0)[1])
    assert mod.main(['--install'])==0
    assert commands[0][1]=='create' and commands[1][1]=='run'
