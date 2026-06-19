from pathlib import Path
from peptiforg_core.peptide_target_complex_builder import export_complex_builder_package, build_pseudo_peptide_pdb, parse_pdb_atoms

TARGET = """HEADER TEST
ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 10.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 10.00           C
END
"""

def test_pseudo_peptide_builder():
    txt = build_pseudo_peptide_pdb('Ac-EEMQRR-NH2', (0,0,0))
    assert 'ATOM' in txt
    assert ' P' in txt

def test_complex_builder_exports(tmp_path):
    target = tmp_path / 'target.pdb'
    target.write_text(TARGET)
    paths = export_complex_builder_package(target, tmp_path, peptide_sequence='Ac-EEMQRR-NH2')
    assert Path(paths['initial_complex_candidate_pdb']).exists()
    assert Path(paths['complex_contact_preview']).exists()
    atoms = parse_pdb_atoms(paths['initial_complex_candidate_pdb'])
    assert any(a['chain'] == 'P' for a in atoms)
