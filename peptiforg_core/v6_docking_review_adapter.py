"""Convert *verified* direct V6 native docking artifacts to the shared GUI viewer.

Do not invent poses, success status, or an affinity value when an engine fails.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


def load_direct_docking_review(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    from .docking_result_contract_v1 import normalize_native_docking_result
    report = dict(report or {})
    status = str(report.get('status') or 'UNKNOWN')
    stage = (report.get('stages') or {}).get('native_docking') or {}
    manifest = report.get('manifest')
    run_dir = Path(str(manifest)).parent if manifest else None
    verified = {str(Path(str(p['pose_pdb'])).resolve()) for p in (stage.get('pose_artifacts') or []) if isinstance(p, dict) and p.get('pose_pdb')}
    native_file = run_dir / 'native_docking' / 'native_docking_summary.json' if run_dir else None
    raw: dict[str, Any] = {}
    if native_file and native_file.is_file():
        import json
        raw = json.loads(native_file.read_text(encoding='utf-8'))
    native_root = (run_dir / 'native_docking').resolve() if run_dir else None
    rows = []
    for candidate in raw.get('poses') or []:
        if not isinstance(candidate, dict):
            continue
        target = Path(str(candidate.get('pose_pdb') or '')).resolve()
        if (str(target) in verified and target.is_file() and target.stat().st_size
                and native_root is not None and target.is_relative_to(native_root)):
            rows.append(candidate)
    raw['poses'] = rows
    raw['status'] = status
    result = normalize_native_docking_result(raw)
    result['status'] = status
    error = str(report.get('error') or '')
    if status not in {'COMPLETED', 'DOCKING_COMPLETED_MD_NOT_REQUESTED', 'MD_NOT_COMPLETED', 'MD_FAILED_DOCKING_COMPLETED', 'MD_BLOCKED_QUALITY_GATE'} and not error:
        error = str(stage.get('engine_status') or stage.get('status') or 'No usable docking poses were verified.')
    info = {'status': status, 'verified_pose_count': len(rows), 'error': error}
    return result, info
