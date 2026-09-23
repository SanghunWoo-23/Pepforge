from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

from peptiforg_core.pymol_structure_builder import export_modified_peptide_coordinate_seed
from peptiforg_core.workflow_pde_bridge import (
    WORKFLOW_BASE_CHEM_TYPES,
    WORKFLOW_LABEL_TYPES,
    WORKFLOW_LINKER_TYPES,
    WORKFLOW_NON_NAT_TYPES,
    WORKFLOW_TAG_TYPES,
    build_workflow_pde_config,
)
from peptiforg_core.workflow_state import derive_workflow_progress, mark_pde_clean, mark_pde_dirty
from suite_gui.docking_workbench_gui import (
    _points_from_structure_builder_metadata,
    annotate_peptide_atoms_from_structure_metadata,
    combined_complex_pdb,
    parse_pdb_atoms,
    pdb_to_peptide_points,
)


def _build(seq: str, tmp_path: Path):
    return export_modified_peptide_coordinate_seed(seq, tmp_path, name="pep", max_iters=3, num_threads=1)


def test_docking_annotation_preserves_terminal_and_d_residue_identity(tmp_path: Path):
    paths = _build("Ac-dA-E-NH2", tmp_path)
    atoms = parse_pdb_atoms(paths["pdb"])
    for col in ("chain", "resi", "resn", "aa"):
        atoms[col] = atoms[col].astype("string")
    mapped = annotate_peptide_atoms_from_structure_metadata(atoms, paths["json"])
    residues = mapped[["chain", "resi", "resn", "aa"]].drop_duplicates().to_dict("records")
    assert {"chain": "X", "resi": "1", "resn": "ACE", "aa": "X"} in residues
    assert {"chain": "P", "resi": "1", "resn": "DA", "aa": "A"} in residues
    assert {"chain": "P", "resi": "2", "resn": "GLU", "aa": "E"} in residues
    assert not mapped["resn"].astype(str).eq("ALA").any()
    assert not mapped["resn"].astype(str).eq("NH2").any()


def test_non_natural_residue_is_not_canonicalized_to_l_alanine(tmp_path: Path):
    paths = _build("Aib-E-NH2", tmp_path)
    mapped = annotate_peptide_atoms_from_structure_metadata(parse_pdb_atoms(paths["pdb"]), paths["json"])
    first = mapped[mapped["resi"].astype(str).eq("1")][["resn", "aa"]].drop_duplicates().iloc[0]
    assert first["resn"] == "AIB"
    assert first["aa"] == "X"
    assert "ALA" not in set(mapped["resn"].astype(str))


def test_modifier_and_linker_do_not_consume_peptide_residue_numbers(tmp_path: Path):
    for seq, modifier in (("Ac-EEMQRR-NH2", "Ac"), ("Ahx-EEMQRR-NH2", "Ahx")):
        out = tmp_path / modifier
        paths = _build(seq, out)
        points = _points_from_structure_builder_metadata(paths["pdb"], paths["json"])
        mod = points[points["token"].eq(modifier)].iloc[0]
        peptide = points[points["token_class"].isin({"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"})]
        assert int(mod["pep_pos"]) == 0
        assert peptide["pep_pos"].astype(int).tolist() == list(range(1, 7))
        assert peptide["token"].tolist() == list("EEMQRR")


def test_sidecar_free_residue_aware_pdb_keeps_chain_p_numbering(tmp_path: Path):
    paths = _build("Ac-EEMQRR-NH2", tmp_path)
    Path(paths["json"]).unlink()
    points = pdb_to_peptide_points(paths["pdb"])
    assert points["pep_pos"].astype(int).tolist() == list(range(1, 7))
    assert points["aa"].tolist() == list("EEMQRR")
    assert not points["token"].astype(str).str.contains("ACE").any()


def test_combined_complex_export_does_not_fabricate_gly_for_modified_tokens():
    target = pd.DataFrame([
        {"atom": "CA", "resn": "ASP", "chain": "A", "resi": "10", "x": 0.0, "y": 0.0, "z": 0.0, "element": "C", "aa": "D"},
    ])
    peptide = pd.DataFrame([
        {"pep_pos": 0, "aa": "X", "token": "Ac", "token_class": "n_terminal", "x": 1.0, "y": 0.0, "z": 0.0},
        {"pep_pos": 1, "aa": "X", "token": "Aib", "token_class": "non_natural_aa", "x": 2.0, "y": 0.0, "z": 0.0},
        {"pep_pos": 2, "aa": "E", "token": "E", "token_class": "std_aa", "x": 3.0, "y": 0.0, "z": 0.0},
    ])
    text = combined_complex_pdb(target, peptide)
    assert " ACE X   1" in text
    assert " AIB P   1" in text
    assert " GLU P   2" in text
    assert " GLY P" not in text


def test_workflow_pde_catalog_is_single_source_and_psb_safe():
    pde_dir = Path(__file__).resolve().parents[1] / "apps" / "peptide_design_engine" / "Python"
    if str(pde_dir) not in sys.path:
        sys.path.insert(0, str(pde_dir))
    import peptide_engine
    from pde_option_catalog import PDE_BASE_CHEM_TYPES, PDE_LABEL_TYPES, PDE_LINKER_TYPES, PDE_TAG_TYPES

    assert peptide_engine.CONFIG["BASE_CHEM_TYPES"] == PDE_BASE_CHEM_TYPES
    assert peptide_engine.CONFIG["LABEL_TYPES"] == PDE_LABEL_TYPES
    assert peptide_engine.CONFIG["LINKER_TYPES"][: len(PDE_LINKER_TYPES)] == PDE_LINKER_TYPES
    assert peptide_engine.CONFIG["TAG_TYPES"] == PDE_TAG_TYPES

    cfg = build_workflow_pde_config("EEMQRR")
    assert cfg["BASE_CHEM_TYPES"] == WORKFLOW_BASE_CHEM_TYPES
    assert cfg["LINKER_TYPES"] == WORKFLOW_LINKER_TYPES
    assert cfg["TAG_TYPES"] == WORKFLOW_TAG_TYPES
    assert cfg["LABEL_TYPES"] == WORKFLOW_LABEL_TYPES
    assert cfg["NON_NAT_TYPES"] == WORKFLOW_NON_NAT_TYPES
    assert {"Stear", "Fmoc", "Boc"}.issubset(WORKFLOW_BASE_CHEM_TYPES)
    assert {"His8", "His10", "Myc", "StrepII", "TwinStrep", "V5", "T7", "ALFA", "AviTag", "SpyTag"}.issubset(WORKFLOW_TAG_TYPES)
    assert {"PEG1", "PEG2", "PEG3", "PEG6", "PEG12", "PEG24"}.issubset(WORKFLOW_LINKER_TYPES)


def test_workflow_dirty_state_and_revision_prevent_stale_psb_spps_reuse():
    project = {
        "hotspot_ranked_regions": [{"rank": 1, "sequence": "EEMQRR"}],
        "active_candidate_id": "cand1",
        "active_candidate_sequence": "EEMQRR",
        "structure_results": {"cand1": {"top1_pdb": "old.pdb"}},
        "spps_settings": {"sequence": "EEMQRR", "candidate_id": "cand1"},
    }
    # Legacy project remains readable before a new revision exists.
    assert derive_workflow_progress(project)[0] == "COMPLETE"

    mark_pde_dirty(project, {"target_sequence": "EEMQRR", "chemistry": {"label": "Off"}})
    assert derive_workflow_progress(project)[0] == "PDE_DIRTY"
    assert project["active_candidate_id"] == ""

    project["active_candidate_id"] = "cand1"
    project["active_candidate_sequence"] = "EEMQRR"
    mark_pde_clean(project)
    assert project["workflow_state"]["pde_revision"] == 1
    # Old PSB/SPPS records have no revision and cannot masquerade as revision 1.
    assert derive_workflow_progress(project)[0] == "PDE_COMPLETE"

    project["structure_results"]["cand1"]["workflow_pde_revision"] = 1
    assert derive_workflow_progress(project)[0] == "PSB_COMPLETE"
    project["spps_settings"]["workflow_pde_revision"] = 1
    assert derive_workflow_progress(project)[0] == "COMPLETE"


def test_candidate_switch_drops_progress_to_active_candidate_lineage():
    project = {
        "workflow_state": {"pde_revision": 2, "pde_dirty": False},
        "hotspot_ranked_regions": [{"rank": 1}],
        "active_candidate_id": "A",
        "active_candidate_sequence": "AAAA",
        "structure_results": {
            "A": {"top1_pdb": "a.pdb", "workflow_pde_revision": 2},
            "B": {"top1_pdb": "b.pdb", "workflow_pde_revision": 1},
        },
        "spps_settings": {"candidate_id": "A", "sequence": "AAAA", "workflow_pde_revision": 2},
    }
    assert derive_workflow_progress(project)[0] == "COMPLETE"
    project["active_candidate_id"] = "B"
    project["active_candidate_sequence"] = "BBBB"
    assert derive_workflow_progress(project)[0] == "PDE_COMPLETE"


def test_workflow_gui_invalidates_chemistry_changes_and_pde_gui_lazy_loads_ml_trainer():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    desktop = (root / "apps" / "peptide_design_engine" / "Python" / "desktop_gui.py").read_text(encoding="utf-8")
    assert "command=self._on_pde_chemistry_choice" in workflow
    assert 'combo.bind("<<ComboboxSelected>>", self._on_pde_chemistry_choice)' in workflow
    assert "mark_pde_dirty" in workflow and "derive_workflow_progress" in workflow
    assert "import ml_trainer  # noqa: E402" not in desktop
    assert "def _get_ml_trainer" in desktop


def test_every_workflow_chemistry_selector_has_explicit_psb_graph():
    from peptiforg_core.workflow_pde_bridge import _psb_graph_buildability

    probes = []
    probes.extend((f"{token}-A-NH2", f"base:{token}") for token in WORKFLOW_BASE_CHEM_TYPES)
    probes.extend((f"A-{token}-G-NH2", f"linker:{token}") for token in WORKFLOW_LINKER_TYPES)
    probes.extend((f"{token}-A-NH2", f"tag:{token}") for token in WORKFLOW_TAG_TYPES)
    probes.extend((f"{token}-A-NH2", f"label:{token}") for token in WORKFLOW_LABEL_TYPES if token != "NONE")
    probes.extend((f"{token}-A-NH2", f"non_nat:{token}") for token in WORKFLOW_NON_NAT_TYPES)
    failures = []
    for sequence, label in probes:
        ok, reason = _psb_graph_buildability(sequence)
        if not ok:
            failures.append(f"{label} -> {sequence}: {reason}")
    assert not failures, "\n".join(failures)
