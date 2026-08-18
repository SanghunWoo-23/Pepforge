import pytest
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from pepforge_structure_tool.pepforge_core import (
    LINKER_UNITS,
    SIDECHAIN_AMINE_LABEL_SUBSTITUENTS,
    PepforgeBuildError,
    expand_and_tokenize,
    tokens_to_smiles,
    audit_template_files,
)


def formula(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, smiles
    return rdMolDescriptors.CalcMolFormula(mol)


def test_exact_linker_conventions_have_expected_free_acid_formulae():
    assert formula(LINKER_UNITS["Ahx"] + "O") == "C6H13NO2"
    assert formula(LINKER_UNITS["bAla"] + "O") == "C3H7NO2"
    assert formula(LINKER_UNITS["gAla"] + "O") == "C4H9NO2"
    assert formula(LINKER_UNITS["AEEA"] + "O") == "C6H13NO4"
    assert formula(LINKER_UNITS["PEG4"] + "O") == "C11H23NO6"
    assert formula(LINKER_UNITS["PEG8"] + "O") == "C19H39NO10"


def test_exact_label_primary_amine_products_match_reaction_stoichiometry():
    # Methylamine is used only as a one-carbon primary-amine test handle.
    assert formula("CN" + SIDECHAIN_AMINE_LABEL_SUBSTITUENTS["FITC"]) == "C22H16N2O5S"
    assert formula("CN" + SIDECHAIN_AMINE_LABEL_SUBSTITUENTS["Biotin"]) == "C11H19N3O2S"
    assert formula("CN" + SIDECHAIN_AMINE_LABEL_SUBSTITUENTS["FAM"]) == "C22H15NO6"


def test_historical_fitc_and_fam_tokens_report_explicit_5_isomer_convention():
    _, _, fitc_warnings, _ = tokens_to_smiles(expand_and_tokenize("FITC-A-NH2"))
    _, _, fam_warnings, _ = tokens_to_smiles(expand_and_tokenize("FAM-A-NH2"))
    assert any("5-FITC" in w for w in fitc_warnings)
    assert any("5-FAM" in w for w in fam_warnings)


def test_defined_sidechain_label_and_linker_label_graphs_build():
    for seq in ("Ac-K(FITC)-LVFF-NH2", "Ac-K(Ahx-Biotin)-LVFF-NH2", "Ac-K(Ahx-FAM)-LVFF-NH2"):
        smiles, *_ = tokens_to_smiles(expand_and_tokenize(seq))
        assert Chem.MolFromSmiles(smiles) is not None


def test_ambiguous_derivatives_are_recognized_but_not_fabricated():
    for seq in ("TAMRA-A-NH2", "Cy5-A-NH2", "DOTA-A-NH2", "NBD-A-NH2", "Chol-A-NH2", "Mal-A-NH2", "Dde-A-NH2"):
        with pytest.raises(PepforgeBuildError, match="curated derivative|does not define one unique"):
            tokens_to_smiles(expand_and_tokenize(seq))
    with pytest.raises(PepforgeBuildError, match="explicit Cys attachment chemistry"):
        tokens_to_smiles(expand_and_tokenize("C(NBD)-A-NH2"))


def test_acyl_chemical_placement_is_explicit():
    smiles, *_ = tokens_to_smiles(expand_and_tokenize("Pal-A-NH2"))
    assert Chem.MolFromSmiles(smiles) is not None
    with pytest.raises(PepforgeBuildError, match="only buildable at the N-terminus"):
        tokens_to_smiles(expand_and_tokenize("A-Pal-NH2"))


def test_template_audit_distinguishes_unavailable_by_design(tmp_path):
    # Use the actual project root for expected buildable templates; the summary
    # must not count intentionally unsupported derivatives as missing files.
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    summary = audit_template_files(root)["summary"]
    assert summary["missing"] == 0
    assert summary["unreadable"] == 0
    assert summary["unavailable_by_design"] == 33
