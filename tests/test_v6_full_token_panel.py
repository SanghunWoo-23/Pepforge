import csv
from pathlib import Path
import pytest
from peptiforg_core.v6_pymol_full_token_panel import export_full_token_panel
from peptiforg_core.v6_pymol_tokens import export_pymol_token_view


def test_full_tokens_preserved(tmp_path):
    source=tmp_path/'tokens.tsv'
    with source.open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,delimiter='\t');w.writerow(['resi','full_chemical_token'])
        w.writerows([['1','D-Lys'],['2','PEG4'],['3','FITC']])
    dest=tmp_path/'panel.py'
    report=export_full_token_panel(source,dest)
    assert report['token_count']==3
    text=dest.read_text()
    assert 'D-Lys' in text and 'PEG4' in text and 'FITC' in text
    compile(text,str(dest),'exec')


def test_duplicate_rejected(tmp_path):
    source=tmp_path/'tokens.tsv';source.write_text('resi\tfull_chemical_token\n1\tAib\n1\tFITC\n')
    with pytest.raises(ValueError,match='duplicate'):
        export_full_token_panel(source,tmp_path/'out.py')


def test_unsafe_residue_rejected(tmp_path):
    source=tmp_path/'tokens.tsv';source.write_text('resi\tfull_chemical_token\n1;delete all\tFITC\n')
    with pytest.raises(ValueError):
        export_full_token_panel(source,tmp_path/'out.py')


def test_native_alias_plus_panel(tmp_path):
    pdb=tmp_path/'test.pdb'
    pdb.write_text('HETATM    1  C1  UNK A   1       0.000   0.000   0.000  1.00  0.00           C\nHETATM    2  C1  UNK A   2       1.000   0.000   0.000  1.00  0.00           C\nEND\n')
    mapping=tmp_path/'map.csv'
    mapping.write_text('resi,token\n1,D-Orn\n2,PEG8\n')
    result=export_pymol_token_view(pdb,mapping,tmp_path/'export')
    assert Path(result['full_token_panel']).is_file()
    assert 'pepforge_tokens' in Path(result['pml']).read_text()
