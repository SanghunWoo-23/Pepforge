import csv
import pytest
from peptiforg_core.v6_independent_benchmark import aligned_rmsd
from peptiforg_core.v6_pymol_tokens import export_pymol_token_view
from peptiforg_core.v6_physics_bridge import prepare_gaff_complex

def line(atom,xyz):
    return f'ATOM   {atom:4d}  CA  ALA A{atom:4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00           C\n'

def test_rmsd_translation(tmp_path):
    a=tmp_path/'a.pdb';b=tmp_path/'b.pdb'
    a.write_text(''.join(line(i,p) for i,p in enumerate([(0,0,0),(1,0,0),(0,1,0)],1)))
    b.write_text(''.join(line(i,tuple(x+10 for x in p)) for i,p in enumerate([(0,0,0),(1,0,0),(0,1,0)],1)))
    assert aligned_rmsd(a,b)<0.001

def test_tokens(tmp_path):
    a=tmp_path/'a.pdb';a.write_text(line(1,(0,0,0)))
    t=tmp_path/'t.csv';t.write_text('resi,token\n1,PEG4\n')
    out=export_pymol_token_view(a,t,tmp_path/'view')
    assert 'PEG4' in (tmp_path/'view.tsv').read_text(encoding='utf-8-sig')
    assert out['exact_full_length_native_sequence_labels'] is False

def test_gaff_dependency_fail_closed(tmp_path):
    with pytest.raises((RuntimeError,FileNotFoundError)):
        prepare_gaff_complex(tmp_path/'x',tmp_path/'y',tmp_path/'out')
