from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from peptiforg_core.interaction_evidence import analyze_interaction_evidence, profile
from peptiforg_core.workflow_gui import WorkflowApp
from spps_v4_gui import state_persistence
from spps_v4_gui.resin_profiles import default_loading_for_resin
from suite_gui.spps_tk_gui import _workflow_handoff_from_env
from apps.spps_planner_app.spps_planner.engine import direct_loading_enabled

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _df(rows):
    return pd.DataFrame(rows, columns=["atom","resn","chain","resi","x","y","z","element","aa"])


def test_spps_saved_sequence_survives_json_roundtrip_and_startup_restores_saved_item():
    item = {"project":"P","peptide":"pep","sequence":"Ac-EEMQRR-NH2","resin":"2-CTC","loading":"0.8","apply_loading_calc":True}
    state = state_persistence.project_state(app_version="V5.0.0", saved_at="now", selected_pm_index=0, pm_items=[item])
    restored = state_persistence.normalize_items(state["pm_items"])
    assert restored[0]["sequence"] == "Ac-EEMQRR-NH2"
    src = (ROOT / "spps_v4_gui" / "ui_build.py").read_text(encoding="utf-8")
    base = (ROOT / "spps_v4_gui" / "classic_base.py").read_text(encoding="utf-8")
    menu = (ROOT / "spps_v4_gui" / "v3_menu.py").read_text(encoding="utf-8")
    assert "_startup_loaded_session" in src and "plan_workflow._restore_item" in src
    assert 'self.protocol("WM_DELETE_WINDOW", self.on_close)' in base
    assert 'label="Exit", command=_command(gui, "on_close")' in menu


def test_original_resin_defaults_are_reused_without_inventing_unknown_values():
    assert default_loading_for_resin("Rink Amide AM") == 0.4
    assert default_loading_for_resin("Rink Amide MBHA") == 0.35
    assert default_loading_for_resin("Sieber Amide") == 0.5
    assert default_loading_for_resin("2-CTC") == 0.8
    assert default_loading_for_resin("Trityl chloride resin") == 0.8
    assert default_loading_for_resin("Wang") == 0.7
    assert default_loading_for_resin("HMPB") is None


def test_loading_checkbox_defaults_on_but_engine_only_applies_direct_loading_when_applicable():
    assert direct_loading_enabled(SimpleNamespace(resin="2-CTC", apply_resin_loading=True)) is True
    assert direct_loading_enabled(SimpleNamespace(resin="2-CTC", apply_resin_loading=False)) is False
    assert direct_loading_enabled(SimpleNamespace(resin="Rink Amide AM", apply_resin_loading=True)) is False
    plan_src = (ROOT / "spps_v4_gui" / "modules" / "plan_workflow.py").read_text(encoding="utf-8")
    assert "tk.BooleanVar(value=True)" in plan_src


def test_workflow_handoff_opens_spps_with_loading_toggle_on():
    handoff = _workflow_handoff_from_env({
        "PEPFORGE_WORKFLOW_SPPS_SEQUENCE":"EEMQRR",
        "PEPFORGE_WORKFLOW_SPPS_RESIN":"2-CTC",
        "PEPFORGE_WORKFLOW_SPPS_LOADING":"0.8",
        "PEPFORGE_WORKFLOW_SPPS_SCALE":"0.4",
        "PEPFORGE_WORKFLOW_SPPS_APPLY_LOADING":"1",
    })
    assert handoff["apply_loading_calc"] is True
    off = _workflow_handoff_from_env({
        "PEPFORGE_WORKFLOW_SPPS_SEQUENCE":"EEMQRR",
        "PEPFORGE_WORKFLOW_SPPS_APPLY_LOADING":"0",
    })
    assert off["apply_loading_calc"] is False


def test_workflow_pde_length_controls_map_to_native_backend_keys():
    app = WorkflowApp.__new__(WorkflowApp)
    app.pde_len_mode_var = _Var("FIX")
    app.pde_fix_len_var = _Var("22")
    app.pde_min_len_var = _Var("18")
    app.pde_max_len_var = _Var("30")
    cfg = WorkflowApp._pde_length_overrides(app)
    assert cfg["LEN_MODE"] == "FIX" and cfg["FIX_LENGTH"] == 22
    assert cfg["LENGTH_COUNT_MODE"] == "TOKEN" and cfg["TRIM_TO_LENGTH"] is True
    app.pde_len_mode_var.set("RANDOM")
    app.pde_min_len_var.set("16")
    app.pde_max_len_var.set("28")
    cfg = WorkflowApp._pde_length_overrides(app)
    assert cfg["MIN_LENGTH"] == 16 and cfg["MAX_LENGTH"] == 28


def test_manual_interaction_profile_matches_user_supplied_cutoffs():
    p = profile("CONSERVATIVE_MANUAL")
    assert p.hbond_da_max_A == 3.5 and p.hbond_angle_min_deg == 120
    assert (p.hydrophobic_min_A, p.hydrophobic_max_A) == (3.3, 5.0)
    assert p.salt_bridge_max_A == 4.0
    assert p.pi_pi_centroid_max_A == 5.0 and p.pi_offset_max_A == 2.0
    assert p.cation_pi_max_A == 5.0 and p.cation_pi_offset_max_A == 2.0
    assert p.serious_clash_overlap_A == 0.4
    assert (p.disulfide_min_A, p.disulfide_max_A) == (2.0, 2.1)
    assert (p.water_bridge_min_A, p.water_bridge_max_A) == (2.5, 3.5)
    assert p.metal_coordination_max_A == 3.0
    assert p.halogen_bond_max_A == 3.5 and p.halogen_angle_min_deg == 150
    assert p.aromatic_s_max_A == 5.0
    assert p.weak_ch_acceptor_max_A == 3.5 and p.weak_ch_angle_min_deg == 120
    assert p.nh_pi_max_A == 3.9


def test_disulfide_distance_is_not_misreported_as_nonbonded_clash():
    target = _df([["SG","CYS","A","10",0,0,0,"S","C"]])
    peptide = _df([["SG","CYS","P","2",2.05,0,0,"S","C"]])
    ev = analyze_interaction_evidence(target, peptide, representative_only=False)
    assert "disulfide" in set(ev.interaction)
    same = ev[(ev.target_residue.str.contains("10CYS")) & (ev.peptide_residue.str.contains("2CYS"))]
    assert "clash" not in set(same.interaction)


def test_additional_manual_interactions_are_screened_with_required_measurement_points():
    # Halogen: C-Cl...O = 180 deg, Cl...O = 3.0 A.
    target = _df([
        ["C1","LIG","A","1",0,0,0,"C","X"],
        ["CL1","LIG","A","1",1.8,0,0,"CL","X"],
    ])
    peptide = _df([["OD1","ASP","P","2",4.8,0,0,"O","D"]])
    ev = analyze_interaction_evidence(target, peptide, representative_only=False)
    hb = ev[ev.interaction.eq("halogen_bond")].iloc[0]
    assert hb.distance_A <= 3.5 and hb.angle_deg >= 150 and hb.evidence_level == "geometry_supported"

    # Metal coordination <=3.0 A.
    metal = _df([["ZN","ZN","A","1",0,0,0,"ZN","X"]])
    coord = _df([["OD1","ASP","P","2",2.2,0,0,"O","D"]])
    ev = analyze_interaction_evidence(metal, coord, representative_only=False)
    assert "metal_coordination" in set(ev.interaction)

    # Water bridge: one explicit water O 3.0 A from polar atoms on both sides.
    tw = _df([
        ["OD1","ASN","A","5",0,0,0,"O","N"],
        ["O","HOH","W","1",3.0,0,0,"O","X"],
    ])
    qw = _df([["ND2","ASN","P","8",6.0,0,0,"N","N"]])
    ev = analyze_interaction_evidence(tw, qw, representative_only=False)
    assert "water_bridge" in set(ev.interaction)


def test_docking_workbench_surfaces_specific_interactions_and_updated_criteria():
    src = (ROOT / "suite_gui" / "docking_workbench_gui.py").read_text(encoding="utf-8")
    assert '"Specific interactions — conservative PyMOL criteria"' in src
    assert "specific_interaction_display_df" in src
    assert "serious_clash_vdw_overlap" in src
    assert "halogen_bond_cutoff" in src
    assert "aromatic_s_cutoff" in src
