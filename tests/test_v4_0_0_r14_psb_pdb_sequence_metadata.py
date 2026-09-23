from pathlib import Path

from peptiforg_core.pymol_structure_builder import (
    export_modified_peptide_coordinate_seed,
    export_modified_peptide_structure,
)
from suite_gui.docking_workbench_gui import (
    pdb_to_peptide_notation,
    pdb_to_sequence,
)


def _text(path):
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def test_ac_psb_pdb_contains_exact_construct_and_seqres(tmp_path):
    paths = export_modified_peptide_coordinate_seed(
        "Ac-EEMQRR-NH2", tmp_path, name="ac_peptide", max_iters=3, num_threads=1
    )
    text = _text(paths["pdb"])
    assert "PEPFORGE_EXACT_SEQUENCE: Ac-EEMQRR-NH2" in text
    assert "SEQRES   1 P    6" in text
    for resn in ("GLU", "MET", "GLN", "ARG"):
        assert resn in text
    assert " ACE X   1" in text
    assert pdb_to_peptide_notation(paths["pdb"]) == "Ac-EEMQRR-NH2"
    assert pdb_to_sequence(paths["pdb"]) == "EEMQRR"


def test_pal_linker_d_residue_construct_is_preserved_without_fabricating_linker_as_aa(tmp_path):
    seq = "Pal-AEEA-dK-NH2"
    paths = export_modified_peptide_coordinate_seed(
        seq, tmp_path, name="pal_linker_d", max_iters=3, num_threads=1
    )
    text = _text(paths["pdb"])
    assert f"PEPFORGE_EXACT_SEQUENCE: {seq}" in text
    assert "PEPFORGE_MODIFIER_TOKENS:" in text
    assert "PAL X" in text or " Pal " in text or "PAL" in text
    # The polymer sequence has one peptide residue. AEEA/Pal are coordinate-bearing
    # chemistry but must not inflate peptide residue numbering.
    assert "SEQRES   1 P    1" in text
    assert "AEE" not in next(line for line in text.splitlines() if line.startswith("SEQRES"))
    assert pdb_to_peptide_notation(paths["pdb"]) == seq


def test_ranked_psb_pdbs_also_keep_sequence_metadata(tmp_path):
    paths = export_modified_peptide_structure(
        "Ac-EEMQRR-NH2", tmp_path, name="ranked", num_confs=5, max_iters=10, num_threads=1,
        min_final_conformers=1,
    )
    text = _text(paths["top1_pdb"])
    assert "PEPFORGE_EXACT_SEQUENCE: Ac-EEMQRR-NH2" in text
    assert "SEQRES   1 P    6" in text


def test_external_seqres_only_pdb_is_usable_for_sequence_recovery(tmp_path):
    path = tmp_path / "seqres_only.pdb"
    path.write_text(
        "HEADER    SEQRES ONLY TEST\n"
        "SEQRES   1 P    4  GLY HIS LYS ARG\n"
        "END\n",
        encoding="utf-8",
    )
    assert pdb_to_sequence(path) == "GHKR"
    assert pdb_to_peptide_notation(path) == "GHKR"


def test_long_exact_sequence_remark_continuation_roundtrips(tmp_path):
    seq = "Ac-" + ("G" * 55) + "-NH2"
    paths = export_modified_peptide_coordinate_seed(
        seq, tmp_path, name="long_peptide", max_iters=1, num_threads=1
    )
    text = _text(paths["pdb"])
    assert "PEPFORGE_EXACT_SEQUENCE_CONT:" in text
    assert pdb_to_peptide_notation(paths["pdb"]) == seq
