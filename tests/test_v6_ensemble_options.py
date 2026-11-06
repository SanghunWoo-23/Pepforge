import pytest
from peptiforg_core.v6_ensemble_options import parse_binding_residues


def test_blind_does_not_require_residue():
    assert parse_binding_residues('', 'blind') == []
    assert parse_binding_residues('not used', 'blind') == []


def test_manual_hotspot_split_and_deduplicate():
    assert parse_binding_residues('A:42, A:42;B:7\nA:50', 'manual') == ['A:42','B:7','A:50']
    assert parse_binding_residues('A:42', 'hotspot') == ['A:42']

@pytest.mark.parametrize('value,mode', [('', 'manual'), ('A:42', 'unknown'), ('A:42 /bad','hotspot')])
def test_invalid_values_rejected(value,mode):
    with pytest.raises(ValueError):
        parse_binding_residues(value,mode)
