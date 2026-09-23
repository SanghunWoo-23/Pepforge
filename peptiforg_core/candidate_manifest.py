from __future__ import annotations

"""Stable candidate identity and cross-module artifact manifest helpers.

The manifest is an audit/transfer object.  It never upgrades computational
scores into experimental evidence and it does not fabricate missing artifacts.
"""

from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import re

SCHEMA = "pepforge_candidate_manifest_v1"


def canonical_construct_tokens(sequence: str | Iterable[str]) -> list[str]:
    if isinstance(sequence, str):
        text = re.sub(r"[\u2010-\u2015]", "-", sequence.strip())
        text = re.sub(r"\s*[-]\s*", "-", text)
        text = re.sub(r"\s+", "", text)
        try:
            from pepforge_structure_tool.pepforge_core import expand_and_tokenize
        except ImportError as exc:
            raise RuntimeError("Pepforge peptide parser is unavailable; candidate identity cannot be created safely.") from exc
        tokens = [str(token) for token in expand_and_tokenize(text)]
        if not tokens:
            raise ValueError("Peptide parser returned no construct tokens; candidate identity was not created.")
        return tokens
    return [str(token).strip() for token in sequence if str(token).strip()]


def construct_key(sequence: str | Iterable[str]) -> str:
    return "|".join(canonical_construct_tokens(sequence))


def stable_candidate_id(sequence: str | Iterable[str]) -> str:
    digest = hashlib.sha256(construct_key(sequence).encode("utf-8")).hexdigest()[:12].upper()
    return f"PF-CAND-{digest}"




def resolve_candidate_id(sequence: str | Iterable[str], selected_candidates: Iterable[dict[str, Any]] | None = None) -> str:
    """Reuse a stored workflow/PDE candidate ID when the construct matches.

    PDE may provide its own stable candidate identifier. Downstream PSB/SPPS
    must not silently replace it with a newly hashed ID merely because the UI
    carries the sequence text. Matching uses Pepforge's canonical token key.
    """
    target = construct_key(sequence)
    matches: list[str] = []
    for row in selected_candidates or []:
        try:
            if construct_key(str(row.get("sequence") or "")) != target:
                continue
        except Exception:
            continue
        cid = str(row.get("candidate_id") or "").strip()
        if cid and cid not in matches:
            matches.append(cid)
    return matches[0] if len(matches) == 1 else stable_candidate_id(sequence)

def new_candidate_manifest(sequence: str | Iterable[str], candidate_id: str | None = None, **fields: Any) -> dict[str, Any]:
    tokens = canonical_construct_tokens(sequence)
    manifest = {
        "schema": SCHEMA,
        "candidate_id": candidate_id or stable_candidate_id(tokens),
        "sequence": "-".join(tokens),
        "construct_tokens": tokens,
        "artifacts": {},
        "claim_boundary": "Audit/transfer record only; computational ranks/scores are not measured activity, affinity, yield, or native-structure proof.",
    }
    manifest.update(fields)
    return manifest


def add_artifacts(manifest: dict[str, Any], stage: str, artifacts: dict[str, str | Path]) -> dict[str, Any]:
    result = dict(manifest or {})
    result.setdefault("schema", SCHEMA)
    result.setdefault("artifacts", {})
    stage_rows = dict(result["artifacts"].get(stage, {}))
    for key, value in (artifacts or {}).items():
        if value is None:
            continue
        path = Path(value)
        # Only record files/folders that actually exist; absent artifacts are omitted.
        if path.exists():
            stage_rows[str(key)] = str(path)
    result["artifacts"][str(stage)] = stage_rows
    return result


def write_manifest(path: str | Path, manifest: dict[str, Any]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(p)


def read_manifest(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"Unsupported candidate manifest schema: {data.get('schema')}")
    return data
