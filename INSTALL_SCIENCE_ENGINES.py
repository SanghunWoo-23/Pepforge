"""Pepforge V6.0.0: opt-in WSL2/Ubuntu + Miniforge science-engine installer.

Windows: --via-wsl --install --bootstrap-wsl can provision a missing Ubuntu
instance (OS administrator approval/reboot/first-user setup may be required).
Linux/WSL2: --install bootstraps checksum-verified Miniforge if necessary, then
creates or updates an isolated conda-forge environment named pepforge-science.

A VERIFIED status covers installation/import checks only; it does not establish
scientific convergence or accurate peptide-protein binding free energies.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import locale
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ENV = 'pepforge-science'
PACKAGES = [
    'openfe', 'openmm', 'openff-toolkit', 'openmmforcefields',
    'ambertools', 'pymbar', 'rdkit', 'mdanalysis',
]
# Official conda-forge/Miniforge release, published 2026-10-21.
# Pin both the artifact and checksum; never execute an unverified download.
MINIFORGE_RELEASE = '26.7.2-1'
MINIFORGE_SHA256 = {
    'x86_64': 'cf0df84220e1c83a1cb2f447056594ca458fa4c6a353430c498f281ec21bd187',
    'aarch64': 'cddb03fec3794a5dfd948750583bb3464bd8b8f21cc4db6bf37cf7c537b08eac',
}
VERIFY = r'''import importlib, json, shutil
mods = {'openfe':'openfe', 'openmm':'openmm', 'openff':'openff.toolkit',
        'openmmforcefields':'openmmforcefields', 'pymbar':'pymbar',
        'rdkit':'rdkit', 'MDAnalysis':'MDAnalysis'}
out = {}
for name, mod in mods.items():
 try:
  loaded = importlib.import_module(mod)
  out[name] = {'ok':True, 'version':str(getattr(loaded,'__version__','unknown'))}
 except Exception as exc:
  out[name] = {'ok':False, 'error':str(exc)}
out['openfe_cli'] = {'ok':shutil.which('openfe') is not None}
if out['openmm']['ok']:
 try:
  from openmm import Platform
  out['openmm_platforms']={'ok':True,'available':[Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())]}
 except Exception as exc:
  out['openmm_platforms']={'ok':False,'error':str(exc)}
print(json.dumps(out, sort_keys=True))
if not all(v['ok'] for v in out.values()): raise SystemExit(3)
'''


def _manager():
    """Find a Linux manager, including Miniforge without shell initialization."""
    home = Path.home()
    for path in (home / 'miniforge3/bin/conda', home / 'miniforge3/bin/mamba',
                 home / 'miniconda3/bin/conda'):
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return next((path for cmd in ('micromamba', 'mamba', 'conda')
                 if (path := shutil.which(cmd))), None)


def plan(system=None, manager=None):
    system = (system or platform.system()).lower()
    if manager is None:
        manager = _manager()
    if system == 'windows':
        return {'status': 'UNSUPPORTED_NATIVE_WINDOWS', 'manager': manager, 'steps': [],
                'warning': 'Run with --via-wsl; OpenFE is not supported on native Windows.'}
    if system not in ('linux', 'darwin'):
        return {'status': 'UNSUPPORTED_PLATFORM', 'manager': manager, 'steps': [],
                'warning': 'Use Linux/macOS, or WSL2 Ubuntu from Windows.'}
    if not manager:
        return {'status': 'MISSING_PACKAGE_MANAGER', 'manager': None, 'steps': [],
                'warning': 'Use --install to bootstrap verified Miniforge on Linux/WSL2.'}
    common = ['--yes', '--name', ENV, '--channel', 'conda-forge',
              '--strict-channel-priority', 'python=3.11',
              *[('openmm!=8.3.0' if p == 'openmm' else p) for p in PACKAGES]]
    return {'status': 'READY', 'manager': manager, 'environment': ENV,
            'packages': PACKAGES, 'steps': [[manager, 'create', *common]],
            'update_step': [manager, 'install', *common],
            'verify': [manager, 'run', '--name', ENV, 'python', '-c', VERIFY],
            'warning': 'Network install in an isolated conda-forge environment; not part of Windows EXE.'}


def wsl_command(linux_script_path, action, project_dir=None, distro=None):
    """Return argv: never interpolate a Windows/WSL pathname into cmd.exe."""
    if action not in ('--install', '--verify-only'):
        raise ValueError('Invalid science action')
    script = str(linux_script_path)
    root = str(project_dir or Path(script).parent)
    command = f'cd {shlex.quote(root)} && python3 {shlex.quote(script)} {action}'
    return ['wsl.exe', *(['--distribution', distro] if distro else []),
            '--exec', 'bash', '-lc', command]


def _windows_output(raw):
    """WSL's `--list --quiet` may use UTF-16LE even under UTF-8 Windows Python."""
    if isinstance(raw, str):
        return raw.replace('\x00', '').replace('\ufeff', '')
    if not raw:
        return ''
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16', errors='replace')
    if raw.count(b'\x00') >= max(1, len(raw) // 5):
        return raw.decode('utf-16-le', errors='replace')
    return raw.decode(locale.getpreferredencoding(False) or 'utf-8', errors='replace')


def choose_ubuntu(installed):
    """Never accidentally run science installation in an unrelated default distro."""
    names = [n.strip().lstrip('* ').strip() for n in installed.splitlines() if n.strip()]
    for preferred in ('Ubuntu', 'Ubuntu-26.04', 'Ubuntu-24.04', 'Ubuntu-22.04', 'Ubuntu-20.04'):
        if preferred in names:
            return preferred
    return next((n for n in names if n.lower().startswith('ubuntu-')), None)


def _wsl_installed_distros():
    cp = subprocess.run(['wsl.exe', '--list', '--quiet'], capture_output=True,
                        text=False, check=False, timeout=30)
    return choose_ubuntu(_windows_output(cp.stdout)) if cp.returncode == 0 else None


def _is_windows_admin():
    """Only used to decide whether to request UAC for optional WSL setup."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _install_ubuntu_windows():
    """Request administrator consent via UAC when provisioning Ubuntu needs it."""
    if _is_windows_admin():
        return subprocess.run(['wsl.exe', '--install', '-d', 'Ubuntu'],
                              check=False, timeout=1800)
    # The user explicitly selected Science setup; do not bypass Windows UAC.
    print('[INFO] Requesting Windows administrator approval for Ubuntu/WSL setup (UAC).', flush=True)
    script = (
        '$p = Start-Process -FilePath "wsl.exe" '
        '-ArgumentList @("--install", "-d", "Ubuntu") '
        '-Verb RunAs -Wait -PassThru; exit $p.ExitCode'
    )
    return subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
                          check=False, timeout=1800)


def _wsl_delegate(action, bootstrap_wsl=False):
    """Provision Ubuntu only after explicit --install --bootstrap-wsl consent."""
    if platform.system().lower() != 'windows':
        print('[ERROR] --via-wsl is only valid from Windows.')
        return 2
    if not shutil.which('wsl.exe'):
        print('[ERROR] wsl.exe unavailable. Windows 10/11 WSL support is required.')
        print('[ACTION] Run an administrator PowerShell: wsl --install -d Ubuntu')
        return 2
    try:
        distro = _wsl_installed_distros()
        if not distro:
            if action == '--verify-only' or not bootstrap_wsl:
                print('[ERROR] No Ubuntu WSL distribution found. Verification never installs an OS.')
                print('[ACTION] Launch administrator PowerShell: wsl --install -d Ubuntu')
                return 2
            print('[INFO] Ubuntu missing. Requesting official WSL Ubuntu installation.')
            print('[NOTICE] Administrator approval, a Windows restart, and first-launch user setup may be required.')
            install = _install_ubuntu_windows()
            if install.returncode:
                print('[ERROR] Ubuntu provisioning did not finish successfully (exit', install.returncode, ').')
                print('[ACTION] Run as administrator: wsl --install -d Ubuntu')
                print('[ACTION] Restart Windows if prompted, start Ubuntu and create your Linux user, then rerun this installer.')
                return 3
            distro = _wsl_installed_distros()
            if not distro:
                print('[ACTION] WSL installation initiated. Restart Windows, open Ubuntu to finish user setup, then rerun this installer.')
                return 3
        kernel = subprocess.run(['wsl.exe', '--distribution', distro, '--exec', 'uname', '-r'],
                                capture_output=True, text=True, errors='replace',
                                check=False, timeout=120)
        if kernel.returncode != 0 or 'wsl2' not in kernel.stdout.lower():
            print('[ERROR] Selected Ubuntu is not yet running under WSL2:', distro)
            print(f'[ACTION] Run: wsl --set-version {distro} 2')
            print('[ACTION] If newly installed, finish Ubuntu first launch and restart Windows if required.')
            return 3
        converted = subprocess.run(['wsl.exe', '--distribution', distro, '--exec',
                                    'wslpath', '-a', str(Path(__file__).resolve())],
                                   capture_output=True, text=True, errors='replace',
                                   check=False, timeout=60)
        script = converted.stdout.strip()
        if converted.returncode or not script.startswith('/') or '\n' in script:
            print('[ERROR] Unable to translate the installer path inside Ubuntu.')
            return 2
        command = wsl_command(script, action, distro=distro)
        print(f'[INFO] Running {action} inside {distro} (WSL2).', flush=True)
        return subprocess.run(command, check=False).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        print('[ERROR] WSL2 Ubuntu startup/provisioning failed:', exc)
        print('[ACTION] Check `wsl --list --verbose`, restart if needed, then rerun.')
        return 3


def _bootstrap_miniforge(logfile):
    """Download SHA-256-pinned Miniforge into the Linux user's home directory."""
    if platform.system().lower() != 'linux':
        raise RuntimeError('Automatic Miniforge bootstrap requires Linux/WSL2.')
    arch = platform.machine().lower()
    if arch == 'amd64':
        arch = 'x86_64'
    if arch == 'arm64':
        arch = 'aarch64'
    digest = MINIFORGE_SHA256.get(arch)
    if not digest:
        raise RuntimeError(f'No verified Miniforge installer for {arch}')
    prefix = Path.home() / 'miniforge3'
    if prefix.exists():
        raise RuntimeError(f'{prefix} exists but conda was not executable; refusing overwrite')
    filename = f'Miniforge3-{MINIFORGE_RELEASE}-Linux-{arch}.sh'
    url = f'https://github.com/conda-forge/miniforge/releases/download/{MINIFORGE_RELEASE}/{filename}'
    print(f'[INFO] Installing SHA-256-verified Miniforge {MINIFORGE_RELEASE} ({arch}).', flush=True)
    with tempfile.TemporaryDirectory(prefix='pepforge_miniforge_') as directory:
        target = Path(directory) / filename
        current = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=90) as stream, target.open('wb') as output:
            while chunk := stream.read(1024 * 1024):
                current.update(chunk)
                output.write(chunk)
        if current.hexdigest() != digest:
            raise RuntimeError('Miniforge SHA-256 mismatch: refusing to execute the downloaded installer')
        result = _execute(['bash', str(target), '-b', '-p', str(prefix)], logfile)
        if result:
            raise RuntimeError(f'Miniforge installer failed (exit code {result}); see {logfile}')
    manager = prefix / 'bin' / 'conda'
    if not manager.is_file():
        raise RuntimeError('Miniforge installer finished but conda executable was not found')
    return str(manager)


def _execute(command, logfile):
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open('a', encoding='utf-8') as log:
        # Do not dump inline verification source into installation logs.
        shown = command[:command.index('-c')] + ['-c', '<inline-verifier>'] if '-c' in command else command
        log.write('$ ' + shlex.join([str(x) for x in shown]) + '\n')
        log.flush()
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        log.write('exit code: ' + str(completed.returncode) + '\n')
    return completed.returncode


def _env_exists(manager):
    try:
        process = subprocess.run([manager, 'run', '--name', ENV, 'python', '--version'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return process.returncode == 0
    except OSError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--install', action='store_true', help='Install/update science packages (may download Miniforge)')
    mode.add_argument('--verify-only', action='store_true', help='Verify existing science packages; never install')
    parser.add_argument('--via-wsl', action='store_true', help='Delegate from Windows to WSL2 Ubuntu')
    parser.add_argument('--bootstrap-wsl', action='store_true', help='Authorize Ubuntu provisioning if absent (Windows --via-wsl --install only)')
    parser.add_argument('--report', default='SCIENCE_ENGINE_INSTALL_REPORT.json')
    parser.add_argument('--log', default='SCIENCE_ENGINE_INSTALL.log')
    args = parser.parse_args(argv)
    if args.bootstrap_wsl and not (args.via_wsl and args.install):
        parser.error('--bootstrap-wsl requires --via-wsl --install')
    if args.via_wsl:
        if not (args.install or args.verify_only):
            parser.error('--via-wsl requires --install or --verify-only')
        return _wsl_delegate('--install' if args.install else '--verify-only', bootstrap_wsl=args.bootstrap_wsl)
    result = plan()
    result['timestamp_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not args.install and not args.verify_only:
        if result['status'] == 'READY':
            result['status'] = 'PLAN_ONLY'
    else:
        if args.install and result['status'] == 'MISSING_PACKAGE_MANAGER' and platform.system().lower() == 'linux':
            try:
                manager = _bootstrap_miniforge(Path(args.log))
                result = plan(manager=manager)
                result['timestamp_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                result['miniforge_bootstrapped'] = True
            except (OSError, RuntimeError, ValueError) as exc:
                result['status'] = 'MINIFORGE_INSTALL_FAILED'
                result['error'] = str(exc)
        if result['status'] == 'READY':
            manager = result['manager']
            existing = _env_exists(manager) if args.install else None
            if args.install:
                result['existing_environment'] = existing
                commands = [result['update_step'] if existing else result['steps'][0], result['verify']]
            else:
                commands = [result['verify']]
            result['status'] = 'RUNNING'
            for index, command in enumerate(commands):
                try:
                    returncode = _execute(command, Path(args.log))
                except OSError as exc:
                    result['error'] = str(exc)
                    result['status'] = 'FAILED'
                    break
                if returncode:
                    result['status'] = ('VERIFICATION_FAILED' if command is result['verify'] else 'INSTALL_FAILED')
                    result['failed_step'] = index
                    result['returncode'] = returncode
                    break
            else:
                result['status'] = 'VERIFIED'
        elif result['status'] not in ('MINIFORGE_INSTALL_FAILED',):
            result['status'] = 'BLOCKED_UNSUPPORTED_ENVIRONMENT'
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.install or args.verify_only:
        return 0 if result['status'] == 'VERIFIED' else 2
    return 0 if result['status'] == 'PLAN_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
