from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from peptiforg_core.pymol_structure_builder import export_modified_peptide_coordinate_seed
from peptiforg_core.workflow_pde_bridge import build_workflow_chemistry_overrides
from suite_gui.docking_workbench_gui import annotate_peptide_atoms_from_structure_metadata, parse_pdb_atoms


def test_psb_pdb_exposes_amino_acid_residue_names_to_pymol(tmp_path: Path):
    paths = export_modified_peptide_coordinate_seed("Ac-EEMQRR-NH2", tmp_path, name="pep", max_iters=3, num_threads=1)
    text = Path(paths["pdb"]).read_text(encoding="utf-8", errors="ignore")
    assert "REMARK 900 PEPFORGE RESIDUE-AWARE REVIEW PDB" in text
    assert " ACE X   1" in text
    assert " GLU P   1" in text
    assert " GLU P   2" in text
    assert " ARG P   6" in text
    assert " UNL " not in text


def test_docking_metadata_annotation_accepts_strict_string_dtype(tmp_path: Path):
    paths = export_modified_peptide_coordinate_seed("Ac-EEMQRR-NH2", tmp_path, name="pep", max_iters=3, num_threads=1)
    atoms = parse_pdb_atoms(paths["pdb"])
    # Reproduce pandas 3.x strict string columns seen on Windows.
    for col in ("chain", "resi", "resn", "aa"):
        atoms[col] = atoms[col].astype("string")
    mapped = annotate_peptide_atoms_from_structure_metadata(atoms, paths["json"])
    assert mapped["resi"].astype(str).str.fullmatch(r"\d*", na=False).all()
    assert pd.to_numeric(mapped["resi"], errors="coerce").max() >= 6
    assert set(mapped.loc[mapped["aa"].eq("E"), "resn"].astype(str)) == {"GLU"}


def test_workflow_pde_chemistry_selectors_restrict_existing_options_only():
    cfg = build_workflow_chemistry_overrides(
        use_d=False,
        use_non_nat=True,
        nterm_chem="Ac",
        linker="PEG4",
        tag="Off",
        label="FITC",
        cterm="COOH",
    )
    assert cfg["USE_D"] is False
    assert cfg["USE_NON_NAT"] is True
    assert cfg["USE_BASE_CHEM"] is True and cfg["BASE_CHEM_TYPES"] == ["Ac"]
    assert cfg["USE_LINKER"] is True and cfg["LINKER_TYPES"] == ["PEG4"]
    assert cfg["LINKER_MODE"] == "FIX" and cfg["FIX_LINKER_TYPE"] == "PEG4"
    assert cfg["USE_TAG"] is False
    assert cfg["USE_LABEL"] is True and cfg["LABEL_TYPES"] == ["FITC"]
    assert cfg["USE_CTERM_NH2"] is False


def test_workflow_gui_contains_progress_and_compact_pde_chemistry_controls():
    source = (Path(__file__).resolve().parents[1] / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert "Workflow progress" in source
    assert "PDE chemistry" in source
    for label in ("N-term chem", "Linker", "Tag", "Label", "C-term"):
        assert label in source
    assert "warm_pde_engine" in source
