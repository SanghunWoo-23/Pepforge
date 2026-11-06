"""Offline safety/contract tests: Ubuntu provisioning and Miniforge bootstrapping."""
import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('science_wsl_bootstrap', ROOT / 'INSTALL_SCIENCE_ENGINES.py')
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)


def test_windows_distro_list_handles_utf16_and_unicode():
    raw = ('Ubuntu\nUbuntu-24.04\n').encode('utf-16-le')
    assert inst.choose_ubuntu(inst._windows_output(raw)) == 'Ubuntu'
    assert inst.choose_ubuntu('Debian\nUbuntu-24.04') == 'Ubuntu-24.04'
    assert inst.choose_ubuntu('Debian\nAlpine') is None


def test_ubuntu_is_pinned_when_windows_default_is_debian():
    cmd = inst.wsl_command('/mnt/c/연구 자료/science.py', '--install', distro='Ubuntu-24.04')
    assert cmd[1:3] == ['--distribution','Ubuntu-24.04']
    assert cmd[3:6] == ['--exec','bash','-lc']
    assert "'/mnt/c/연구 자료/science.py'" in cmd[-1]


def _make_fake_windows(monkeypatch, installed):
    monkeypatch.setattr(inst.platform, 'system', lambda:'Windows')
    monkeypatch.setattr(inst.shutil, 'which', lambda name:'/windows/wsl.exe')
    monkeypatch.setattr(inst, '_is_windows_admin', lambda:True)
    invoked = []
    def fake_run(cmd, **kwargs):
        invoked.append(cmd)
        if cmd[1:3] == ['--list','--quiet']:
            value = installed.pop(0) if len(installed)>1 else installed[0]
            return SimpleNamespace(returncode=0,stdout=value.encode('utf-16-le'))
        if cmd[1:3] == ['--install','-d']:
            return SimpleNamespace(returncode=0)
        if cmd[-2:] == ['uname','-r']:
            return SimpleNamespace(returncode=0,stdout='5.15-microsoft-standard-WSL2')
        if 'wslpath' in cmd:
            return SimpleNamespace(returncode=0,stdout='/mnt/c/Pepforge/INSTALL_SCIENCE_ENGINES.py\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(inst.subprocess, 'run', fake_run)
    return invoked


def test_missing_ubuntu_install_is_requested_only_with_consent(monkeypatch):
    invoked = _make_fake_windows(monkeypatch, ['', 'Ubuntu'])
    assert inst._wsl_delegate('--install',bootstrap_wsl=True) == 0
    assert ['wsl.exe','--install','-d','Ubuntu'] in invoked
    assert invoked[-1][1:3] == ['--distribution','Ubuntu']


def test_missing_ubuntu_is_not_installed_during_verify(monkeypatch):
    invoked = _make_fake_windows(monkeypatch, [''])
    assert inst._wsl_delegate('--verify-only',bootstrap_wsl=True) != 0
    assert not any('--install' in cmd for cmd in invoked)


def test_missing_ubuntu_reports_pending_reboot_and_stops(monkeypatch):
    invoked = _make_fake_windows(monkeypatch, ['', ''])
    assert inst._wsl_delegate('--install',bootstrap_wsl=True) != 0
    assert ['wsl.exe','--install','-d','Ubuntu'] in invoked
    assert not any('wslpath' in cmd for cmd in invoked)


def test_miniforge_checksums_are_real_hex():
    assert set(inst.MINIFORGE_SHA256) >= {'x86_64','aarch64'}
    assert all(len(v)==64 and int(v,16)>=0 for v in inst.MINIFORGE_SHA256.values())


def test_miniforge_hash_mismatch_never_executes(monkeypatch, tmp_path):
    monkeypatch.setattr(inst.platform,'system',lambda:'Linux')
    monkeypatch.setattr(inst.platform,'machine',lambda:'x86_64')
    monkeypatch.setattr(inst.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(inst.urllib.request,'urlopen',lambda *args,**kwargs:io.BytesIO(b'bad payload'))
    calls=[]
    monkeypatch.setattr(inst,'_execute',lambda *args,**kwargs:calls.append(args))
    with pytest.raises(RuntimeError,match='SHA-256 mismatch'):
        inst._bootstrap_miniforge(tmp_path/'install.log')
    assert not calls


def test_verify_only_does_not_download_miniforge(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(inst, 'plan', lambda: {'status':'MISSING_PACKAGE_MANAGER','manager':None,'steps':[]})
    monkeypatch.setattr(inst,'_bootstrap_miniforge', lambda *_: pytest.fail('Downloaded during verify-only'))
    assert inst.main(['--verify-only'])!=0


def test_bootstrap_flag_requires_explicit_install():
    with pytest.raises(SystemExit):
        inst.main(['--verify-only','--via-wsl','--bootstrap-wsl'])


def test_existing_ubuntu_skips_wsl_installer(monkeypatch):
    invoked = _make_fake_windows(monkeypatch, ['Debian\nUbuntu-24.04'])
    assert inst._wsl_delegate('--install', bootstrap_wsl=True) == 0
    assert not any('--install' in cmd for cmd in invoked)
    assert invoked[-1][1:3] == ['--distribution', 'Ubuntu-24.04']


def test_ubuntu_provisioning_denied_fails_clearly(monkeypatch):
    invoked = _make_fake_windows(monkeypatch, [''])
    previous = inst.subprocess.run
    def fake_run(cmd, **kwargs):
        if cmd[1:3] == ['--install','-d']:
            invoked.append(cmd)
            return SimpleNamespace(returncode=740)
        return previous(cmd, **kwargs)
    monkeypatch.setattr(inst.subprocess, 'run', fake_run)
    assert inst._wsl_delegate('--install', bootstrap_wsl=True) == 3
    assert ['wsl.exe','--install','-d','Ubuntu'] in invoked


def test_verified_miniforge_bootstrap_runs_unattended_installer(monkeypatch, tmp_path):
    payload = b'controlled test miniforge bytes'
    monkeypatch.setattr(inst.platform, 'system', lambda:'Linux')
    monkeypatch.setattr(inst.platform, 'machine', lambda:'x86_64')
    monkeypatch.setattr(inst.Path, 'home', classmethod(lambda cls:tmp_path))
    monkeypatch.setattr(inst, 'MINIFORGE_SHA256', {'x86_64':hashlib.sha256(payload).hexdigest()})
    monkeypatch.setattr(inst.urllib.request, 'urlopen', lambda *args,**kwargs:io.BytesIO(payload))
    commands=[]
    def fake_install(cmd, logfile):
        commands.append(cmd)
        assert cmd[0]=='bash' and cmd[-3:]==['-b','-p',str(tmp_path/'miniforge3')]
        destination=tmp_path/'miniforge3/bin/conda'
        destination.parent.mkdir(parents=True)
        destination.write_text('#!/bin/sh\n')
        return 0
    monkeypatch.setattr(inst,'_execute',fake_install)
    manager = inst._bootstrap_miniforge(tmp_path/'installation.log')
    assert manager == str(tmp_path/'miniforge3/bin/conda')
    assert len(commands)==1


def test_missing_ubuntu_requests_windows_uac_for_non_admin(monkeypatch):
    monkeypatch.setattr(inst, '_is_windows_admin', lambda:False)
    observed=[]
    def fake_run(cmd, **kwargs):
        observed.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(inst.subprocess,'run',fake_run)
    assert inst._install_ubuntu_windows().returncode == 0
    assert observed[0][:3] == ['powershell.exe','-NoProfile','-Command']
    assert '-Verb RunAs' in observed[0][-1]
    assert '--install' in observed[0][-1]
