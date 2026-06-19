from pathlib import Path
from peptiforg_core.target_structure_preparation import summarize_target_structure, chain_summary_rows, write_cleaned_pdb, export_target_preparation_package
PDB="""HEADER TEST
ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 10.00           N
ATOM      2  N   ALA B   1       0.000   3.000   0.000  1.00 10.00           N
HETATM    3  O   HOH A 101       5.000   5.000   5.000  1.00 10.00           O
HETATM    4  NA  NA  A 102       6.000   6.000   6.000  1.00 10.00          NA
END
"""
def test_target_summary(tmp_path):
    p=tmp_path/'t.pdb'; p.write_text(PDB); s=summarize_target_structure(p); assert s['chain_count']==2 and s['water_count']==1
    assert {r['chain'] for r in chain_summary_rows(p)}=={'A','B'}
def test_cleaned_pdb(tmp_path):
    p=tmp_path/'t.pdb'; p.write_text(PDB); out=tmp_path/'c.pdb'; write_cleaned_pdb(p,out,selected_chains=['A'],keep_waters=False,keep_ions=True); t=out.read_text(); assert 'GLY A' in t and 'ALA B' not in t and 'HOH' not in t and 'NA' in t
def test_package(tmp_path):
    p=tmp_path/'t.pdb'; p.write_text(PDB); paths=export_target_preparation_package(p,tmp_path,selected_chains=['A']); assert Path(paths['target_cleaned_pdb']).exists()
