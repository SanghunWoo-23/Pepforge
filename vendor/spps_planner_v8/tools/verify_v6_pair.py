#!/usr/bin/env python3
"""Compare a V6 Private/Public development pair without reading private data content."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path

IGNORED_NAMES={"__pycache__", ".pytest_cache"}

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def source_map(root: Path) -> dict[str,str]:
    selected=[]
    for base in (root/'suite_gui', root/'tools'):
        if base.exists():
            selected.extend(p for p in base.rglob('*.py') if not any(part in IGNORED_NAMES for part in p.parts))
    app=root/'apps'/'spps_planner_app'/'spps_planner'
    if app.exists():
        selected.extend(p for p in app.rglob('*.py') if p.name!='build_profile.py' and not any(part in IGNORED_NAMES for part in p.parts))
    for rel in ('SPPS_Planner.spec','VERSION','VERSION.txt','installer/SPPS_Planner_Setup.iss','installer/version_info.txt'):
        p=root/rel
        if p.exists(): selected.append(p)
    return {str(p.relative_to(root)).replace('\\','/'):sha(p) for p in selected}

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('private_root', type=Path)
    ap.add_argument('public_root', type=Path)
    ns=ap.parse_args()
    pri,pub=ns.private_root.resolve(),ns.public_root.resolve()
    pm,um=source_map(pri),source_map(pub)
    keys=sorted(set(pm)|set(um))
    diffs=[k for k in keys if pm.get(k)!=um.get(k)]
    if diffs:
        print('[FAIL] Shared V6 source parity mismatch:')
        for k in diffs[:100]: print(' -',k)
        return 1
    seed=pub/'apps'/'spps_planner_app'/'data'/'experimental_seed'
    seed_files=sorted(str(p.relative_to(seed)).replace('\\','/') for p in seed.rglob('*') if p.is_file()) if seed.exists() else []
    if seed_files not in ([], ['README.md']):
        print('[FAIL] Public experimental_seed is not documentation-only:', seed_files)
        return 1
    bad=[]
    for p in pub.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.sqlite','.sqlite3','.db'}:
            bad.append(str(p.relative_to(pub)))
    if bad:
        print('[FAIL] Public package contains database files:', bad)
        return 1
    print(f'[OK] Shared V6 source parity: {len(keys)} files match')
    print(f'[OK] Public experimental_seed policy: {seed_files or "empty"}')
    print('[OK] Public source tree contains no sqlite/db files')
    return 0
if __name__=='__main__':
    raise SystemExit(main())
