from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "peptide_design_engine" / "Python"))

import peptide_engine as pe
from suite_gui.docking_workbench_gui import parse_pdb_atoms


def test_nterm_terminal_tokens_are_single_by_default():
    old = dict(pe.CONFIG)
    try:
        pe.update_config({"ALLOW_MULTIPLE_NTERM_MODIFIERS": False})
        seq = ["T7", "Succinyl", "E", "E", "M", "Q", "R", "R", "NH2"]
        fixed = pe.enforce_terminal_rules(seq)
        nterm = [x for x in fixed if pe.is_terminal_chem_token(x)]
        assert len(nterm) <= 1
        assert not ("T7" in fixed and "Succinyl" in fixed)
    finally:
        pe.CONFIG.clear(); pe.CONFIG.update(old)


def test_af3_mmcif_atom_site_parse(tmp_path):
    cif = tmp_path / "af3_mock.cif"
    cif.write_text("""data_mock
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 1.0 2.0 3.0
ATOM 2 C CA ARG A 2 4.0 5.0 6.0
#
""")
    df = parse_pdb_atoms(cif)
    assert len(df) == 2
    assert df.iloc[0]["aa"] == "A"
    assert df.iloc[1]["aa"] == "R"
