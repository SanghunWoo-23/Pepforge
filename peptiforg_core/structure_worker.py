from __future__ import annotations

"""Isolated Peptide Structure Builder worker.

RDKit embedding and force-field optimization run in this child process so a
native-library failure cannot close the operator-facing Tk window.
"""

import json
import traceback
from pathlib import Path
from typing import Any

from peptiforg_core.pymol_structure_builder import export_modified_peptide_structure


def run_structure_request(request_path: str | Path) -> int:
    request_file = Path(request_path).expanduser().resolve()
    request = json.loads(request_file.read_text(encoding="utf-8"))
    result_file = Path(request["result_path"]).expanduser().resolve()
    result_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        paths = export_modified_peptide_structure(
            str(request["sequence"]),
            str(request["output_dir"]),
            str(request.get("name") or "modified_peptide"),
            environment_conditions=dict(request.get("environment_conditions") or {}),
            num_confs=int(request.get("num_confs", 8)),
            max_iters=int(request.get("max_iters", 200)),
            num_threads=int(request.get("num_threads", 2)),
            search_profile=str(request.get("search_profile", "evidence_fast")),
            min_final_conformers=int(request.get("min_final_conformers", 5)),
            max_embedding_retries=int(request.get("max_embedding_retries", 2)),
        )
        payload: dict[str, Any] = {"ok": True, "paths": paths}
        exit_code = 0
    except BaseException as exc:
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        exit_code = 1
    result_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return exit_code


__all__ = ["run_structure_request"]
