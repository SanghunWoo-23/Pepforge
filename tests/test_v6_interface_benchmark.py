from pathlib import Path
import pytest
from peptiforg_core.v6_independent_benchmark import receptor_aligned_ligand_rmsd

def save(path, coords):
    records=[]
    for i,(x,y,z) in enumerate(coords,1):
        records.append(f'ATOM  {i:5d}  CA  ALA A{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}{1.:6.2f}{0.:6.2f}           C\n')
    Path(path).write_text(''.join(records))

def test_correct_receptor_aligned(tmp_path):
    r=tmp_path/'r.pdb'; p=tmp_path/'p.pdb';l=tmp_path/'l.pdb'; n=tmp_path/'n.pdb'
    save(r,[(0,0,0),(10,0,0),(0,10,0)])
    save(p,[(5,6,7),(15,6,7),(5,16,7)])
    save(l,[(2,2,3)])
    save(n,[(7,8,10)])
    assert receptor_aligned_ligand_rmsd(r,p,l,n)<0.001
    save(n,[(17,8,10)])
    assert receptor_aligned_ligand_rmsd(r,p,l,n)>9.9

def test_bad_mapping(tmp_path):
    r=tmp_path/'r.pdb';l=tmp_path/'l.pdb'
    save(r,[(0,0,0)])
    save(l,[(0,0,0)])
    with pytest.raises(ValueError):
        receptor_aligned_ligand_rmsd(r,r,l,l)
