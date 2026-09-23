from __future__ import annotations

from pathlib import Path
import pandas as pd

from peptiforg_core.pymol_structure_builder import export_modified_peptide_coordinate_seed
from suite_gui.docking_workbench_gui import (
    _pose_display_columns,
    annotate_peptide_atoms_from_structure_metadata,
    atom_pair_display_df,
    contact_display_df,
    parse_pdb_atoms,
    pose_display_df,
    run_pose_search,
    screening_overview_df,
)


def _target_atoms() -> pd.DataFrame:
    rows=[]
    specs=[
        (1,"ASP","D",0.0),(2,"PHE","F",4.0),(3,"LYS","K",8.0),(4,"SER","S",12.0),
    ]
    for resi,resn,aa,x in specs:
        rows.extend([
            {"record":"ATOM","atom":"N","resn":resn,"chain":"A","resi":resi,"x":x-0.6,"y":0.0,"z":0.0,"element":"N","aa":aa},
            {"record":"ATOM","atom":"CA","resn":resn,"chain":"A","resi":resi,"x":x,"y":0.0,"z":0.0,"element":"C","aa":aa},
            {"record":"ATOM","atom":"O","resn":resn,"chain":"A","resi":resi,"x":x+0.7,"y":0.2,"z":0.0,"element":"O","aa":aa},
        ])
    return pd.DataFrame(rows)


def test_readable_pose_and_contact_tables_show_residue_identity():
    peptide=pd.DataFrame([
        {"pep_pos":1,"aa":"K","x":0.0,"y":0.0,"z":0.0},
        {"pep_pos":2,"aa":"L","x":3.8,"y":0.0,"z":0.0},
        {"pep_pos":3,"aa":"S","x":7.6,"y":0.0,"z":0.0},
    ])
    poses, contacts, _model=run_pose_search(_target_atoms(),peptide,"KLS",pose_limit=5)
    pv=pose_display_df(poses,contacts)
    cv=contact_display_df(contacts,poses,best_pose_only=True,top_n=20)
    ov=screening_overview_df(poses,contacts)
    assert list(pv.columns)==_pose_display_columns()
    assert pv["protein_residues"].astype(str).str.contains("A:").any()
    assert pv["peptide_residues"].astype(str).str.contains("1K|2L|3S",regex=True).any()
    assert not cv.empty
    assert set(["protein_residue","peptide_residue","distance_A","interaction"]).issubset(cv.columns)
    assert cv["protein_residue"].astype(str).str.contains("A:").all()
    assert ov.loc[ov["item"].eq("Residue contacts"),"value"].astype(str).str.len().gt(0).all()
    # Internal transform coordinates are intentionally not in the normal table.
    assert "translation_x_A" not in pv.columns and "rotation_z_deg" not in pv.columns


def test_structure_builder_pdb_is_residue_aware_and_metadata_mapping_remains_valid(tmp_path: Path):
    paths=export_modified_peptide_coordinate_seed("PSNRILVIESL",tmp_path,name="pep")
    atoms=parse_pdb_atoms(paths["pdb"])
    assert {"PRO", "SER", "ASN", "ARG", "ILE", "LEU", "VAL", "GLU"}.issubset(set(atoms["resn"].astype(str)))
    mapped=annotate_peptide_atoms_from_structure_metadata(atoms,paths["json"])
    heavy=mapped[mapped["element"].astype(str).str.upper().ne("H")]
    assert heavy["aa"].isin(list("PSNRILVIESL")).any()
    assert pd.to_numeric(heavy["resi"],errors="coerce").max() >= 11


def test_atom_pair_summary_keeps_contact_residue_position_and_type():
    atom_contacts=pd.DataFrame([
        {"target_residue":"A:15D","peptide_residue":"3R","distance_A":3.1,"contact_class":"opposite_charge_residue_atom_proximity","target_atom":"OD1","peptide_atom":"N8"},
        {"target_residue":"A:15D","peptide_residue":"3R","distance_A":3.4,"contact_class":"hbond_distance_candidate","target_atom":"OD2","peptide_atom":"N9"},
        {"target_residue":"A:22F","peptide_residue":"5I","distance_A":4.2,"contact_class":"hydrophobic_atom_proximity","target_atom":"CZ","peptide_atom":"C20"},
    ])
    out=atom_pair_display_df(atom_contacts)
    assert list(out["protein_residue"])[:2]==["A:15D","A:22F"]
    assert "Opposite-charge" in out.iloc[0]["interaction_candidates"]
    assert "H-bond" in out.iloc[0]["interaction_candidates"]
    assert out.iloc[0]["peptide_residue"]=="3R"


def test_docking_normal_ui_removes_redundant_sequence_copy_buttons_and_exports_readable_tables():
    source=(Path(__file__).resolve().parents[1]/"suite_gui"/"docking_workbench_gui.py").read_text(encoding="utf-8")
    assert "Use target PDB seq" not in source
    assert "Use peptide PDB seq" not in source
    assert "Best pose — contacting residues" in source
    assert "Atom-level residue pairs / interaction candidates" in source
    assert "docking_pose_summary_readable" in source
    assert "docking_best_pose_contacts_readable" in source
    assert "Show full result tables" in source


def test_pdb_structure_analysis_and_generic_compare_do_not_require_mdtraj(tmp_path: Path, monkeypatch):
    from peptiforg_core.structure_file_analyzer import analyze_structure_files
    import peptiforg_core.structure_consensus as sc
    paths=export_modified_peptide_coordinate_seed("PSNRILVIESL",tmp_path/"seed",name="pep")
    analysis=analyze_structure_files([paths["pdb"]],tmp_path/"analysis",name="pdb_only")
    assert Path(analysis["summary_csv"]).exists()
    monkeypatch.setattr(sc,"md",None)
    compared=sc.compare_structures(paths["pdb"],paths["pdb"],tmp_path/"compare",name="generic")
    assert compared["comparison_mode"] in {"residue_CA_backbone", "heavy_atom_order"}
    if compared["comparison_mode"] == "residue_CA_backbone":
        assert compared["ca_rmsd_A"] < 1e-8
    else:
        assert compared["heavy_atom_order_rmsd_A"] < 1e-8


def test_workflow_default_size_and_spps_startup_are_user_ready():
    root=Path(__file__).resolve().parents[1]
    workflow=(root/"peptiforg_core"/"workflow_gui.py").read_text(encoding="utf-8")
    spps=(root/"suite_gui"/"spps_tk_gui.py").read_text(encoding="utf-8")
    ui_build=(root/"spps_v4_gui"/"ui_build.py").read_text(encoding="utf-8")
    assert "preferred_height=880" in workflow
    # New planners remain blank, but an autosaved peptide must restore its
    # sequence instead of being wiped by the Pepforge integration wrapper.
    assert "Do not blank an autosaved/restored item" in spps
    assert "_startup_loaded_session" in ui_build
    assert "plan_workflow._restore_item" in ui_build
