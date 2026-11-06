import tempfile
from pathlib import Path
import pytest
from peptiforg_core.v6_independent_benchmark import read_heavy_atoms

def make_atom(x='  1.000', alt=' '):
    return f'ATOM      1  CA {alt}ALA A   1    {x:>8}   2.000   3.000  1.00 20.00           C\n'

def test_nonfinite_coordinate_rejected():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'x.pdb';p.write_text(make_atom('     nan'))
        with pytest.raises(ValueError, match='Nonfinite'): read_heavy_atoms(p)

def test_ambiguous_alternate_location_rejected():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'x.pdb';p.write_text(make_atom(alt='B'))
        with pytest.raises(ValueError, match='Alternate'): read_heavy_atoms(p)

def test_normal_atom_supported():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'x.pdb';p.write_text(make_atom())
        assert len(read_heavy_atoms(p))==1
