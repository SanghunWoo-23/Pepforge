"""Pepforge V6 reproducible release preflight (not a scientific certification)."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys


def run_check(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return {'status': 'PASS' if p.returncode == 0 else 'FAIL', 'exit_code': p.returncode,
                'command': cmd, 'stdout_tail': p.stdout[-8000:], 'stderr_tail': p.stderr[-8000:]}
    except subprocess.TimeoutExpired as e:
        return {'status': 'TIMEOUT', 'command': cmd, 'timeout_seconds': timeout,
                'stdout_tail': (e.stdout or b'').decode(errors='replace')[-2000:] if isinstance(e.stdout, bytes) else (e.stdout or '')[-2000:]}
    except OSError as e:
        return {'status': 'ERROR', 'command': cmd, 'error': str(e)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--full-suite', action='store_true', help='Also run all repository tests; may be slow')
    ap.add_argument('--timeout', type=int, default=180)
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if not (root / 'pepforge_cli.py').is_file():
        ap.error('root must contain pepforge_cli.py')
    checks = {
        'cli_help': run_check([sys.executable, 'pepforge_cli.py', '--help'], root, min(a.timeout, 40)),
        'syntax': run_check([sys.executable, '-m', 'compileall', '-q', 'peptiforg_core', 'pepforge_cli.py'], root, a.timeout),
    }
    # pytest does not expand globs by itself on Windows; enumerate explicitly.
    v6_tests = sorted(str(x.relative_to(root)) for x in (root / 'tests').glob('test_v6_*.py'))
    checks['v6_tests'] = run_check([sys.executable, '-m', 'pytest', '-q', *v6_tests], root, a.timeout) if v6_tests else {'status': 'FAIL', 'reason': 'No V6 tests found'}
    if a.full_suite:
        checks['full_suite'] = run_check([sys.executable, '-m', 'pytest', '-q'], root, a.timeout)
    files = [root / 'pepforge_cli.py', root / 'main_launcher.py', root / 'peptiforg_core' / 'version.py']
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
    result = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'platform': platform.platform(),
              'python': sys.version.split()[0], 'root': str(root), 'checks': checks,
              'entrypoint_sha256': hashes, 'windows_gui_verified': False,
              'native_docking_benchmark_verified': False, 'production_md_verified': False,
              'final_approval': False,
              'status': 'PREFLIGHT_PASS_NOT_FINAL' if all(c['status'] == 'PASS' for c in checks.values()) else 'NOT_READY'}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'], '=>', a.output)
    return 0 if result['status'] == 'PREFLIGHT_PASS_NOT_FINAL' else 1

if __name__ == '__main__':
    raise SystemExit(main())
