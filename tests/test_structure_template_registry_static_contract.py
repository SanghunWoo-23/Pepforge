"""Dependency-light integrity checks for the curated Structure template registry.

These checks deliberately do not import RDKit: they protect the registry/manifest
contract even in a source-only review environment.  RDKit-backed readability and
chemical-graph checks remain covered by ``test_structure_explicit_chemistry_v2``.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "pepforge_structure_tool" / "data"


def _load_registry() -> dict:
    return json.loads((DATA / "supported_tokens_v130.json").read_text(encoding="utf-8"))


def test_registry_and_manifest_have_the_same_curated_token_set():
    registry = _load_registry()["template_registry"]
    manifest = json.loads((DATA / "template_manifest_v130.json").read_text(encoding="utf-8"))["templates"]
    assert set(registry) == set(manifest)
    for token in registry:
        for field in ("buildable", "source", "smiles", "template_file", "attach_points", "curation_status"):
            assert registry[token].get(field) == manifest[token].get(field), (token, field)


def test_every_buildable_entry_has_one_nonempty_sdf_and_every_blocked_entry_has_none():
    registry = _load_registry()["template_registry"]
    blocked = []
    buildable = []
    for token, record in registry.items():
        rel = record.get("template_file")
        if record.get("buildable"):
            buildable.append(token)
            assert rel, token
            template = ROOT / rel
            assert template.is_file(), token
            text = template.read_text(encoding="utf-8")
            assert text.strip() and "M  END" in text and text.rstrip().endswith("$$$$"), token
        else:
            blocked.append(token)
            assert rel is None, token
            assert record.get("curation_status") == "requires_curated_derivative", token
    assert len(buildable) == 44
    assert len(blocked) == 33
    assert {"Chol", "Cy5", "DOTA", "Dde", "Mal", "NBD", "TAMRA"}.issubset(blocked)
