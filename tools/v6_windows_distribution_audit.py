"""Conservative Windows packaging audit. No claim that an EXE was built."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

REQUIRED = ('main_launcher.py', 'pepforge_cli.py', 'installer/Pepforge.spec',
            'INSTALL_BUILD_TOOLS_AND_BUILD.bat', 'requirements.txt')

def audit(root: Path, exe: Path | None = None) -> dict:
    root = Path(root).resolve()
    inventory = {}
    for rel in REQUIRED:
        path = root / rel
        inventory[rel] = {'present': path.is_file()}
        if path.is_file():
            inventory[rel]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    bat = root / 'INSTALL_BUILD_TOOLS_AND_BUILD.bat'
    spec = root / 'installer/Pepforge.spec'
    build_script = bat.read_text(encoding='utf-8', errors='replace') if bat.is_file() else ''
    spec_content = spec.read_text(encoding='utf-8', errors='replace') if spec.is_file() else ''
    checks = {
        'source_layout': all(x['present'] for x in inventory.values()),
        'isolated_venv': bool(re.search(r'python\.exe|Scripts\\python', build_script, re.I)),
        'pyinstaller_build': 'PyInstaller' in build_script,
        'spec_uses_launcher': 'main_launcher.py' in spec_content,
    }
    exe_result = {'checked': exe is not None, 'found': False, 'sha256': None}
    if exe is not None:
        target = Path(exe)
        exe_result['found'] = target.is_file()
        if target.is_file():
            exe_result['sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    return {'checks': checks, 'inventory': inventory, 'exe': exe_result,
            'static_audit_pass': all(checks.values()),
            'windows_runtime_verified': False,
            'installer_end_to_end_verified': False,
            'release_approved': False}

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--exe', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(argv)
    result = audit(a.root, a.exe)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('STATIC_PASS_NOT_FINAL' if result['static_audit_pass'] else 'STATIC_FAIL', a.output)
    return 0 if result['static_audit_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
