from pathlib import Path
import pandas as pd
from suite_gui.docking_workbench_gui import analyze_atom_level_contacts, atomic_structure_pdb

def test_atomic_structure_export_uses_supplied_coordinates_only():
    df=pd.DataFrame([{'record':'ATOM','atom':'CA','resn':'CYS','chain':'P','resi':'1','x':1.0,'y':2.0,'z':3.0,'element':'C','aa':'C'}])
    pdb=atomic_structure_pdb(df,'test atomic structure',forced_chain='P')
    assert 'CYS' in pdb and '   1.000   2.000   3.000' in pdb
    assert 'pseudo' not in pdb.lower()

def test_atom_level_contacts_for_imported_pdb_pair(tmp_path):
    target=tmp_path/'target.pdb'; peptide=tmp_path/'peptide.pdb'
    target.write_text('ATOM      1  OD1 ASP A   1       0.000   0.000   0.000  1.00  0.00           O\nEND\n')
    peptide.write_text('ATOM      1  NZ  LYS P   1       0.000   0.000   3.500  1.00  0.00           N\nEND\n')
    df=analyze_atom_level_contacts(target,peptide,cutoff_A=4.5)
    assert len(df)>=1 and float(df.iloc[0]['distance_A'])<=4.5
    assert 'hbond_distance_candidate' in str(df.iloc[0]['contact_class']) or 'opposite_charge_residue_atom_proximity' in str(df.iloc[0]['contact_class'])
