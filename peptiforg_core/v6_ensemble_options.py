"""Input contract shared by ensemble GUI and command line.

Residue identifiers are forwarded to the native engine unchanged after stripping
whitespace; the native engine remains responsible for structural validation.
"""
from __future__ import annotations
import re


def parse_binding_residues(value: str, mode: str) -> list[str]:
    if mode not in ('blind', 'manual', 'hotspot'):
        raise ValueError('Mode must be blind, manual, or hotspot')
    if mode == 'blind':
        return []
    tokens = [x.strip() for x in re.split(r'[,;\n]+', value or '') if x.strip()]
    if not tokens:
        raise ValueError(f'{mode} docking requires receptor residue identifiers (comma separated)')
    if len(tokens) > 200:
        raise ValueError('Too many residue identifiers (maximum 200)')
    if any(len(t) > 64 or not re.fullmatch(r'[\w:.-]+', t, re.UNICODE) for t in tokens):
        raise ValueError('Residue identifiers may only contain letters, digits, _, :, ., or -')
    return list(dict.fromkeys(tokens))
