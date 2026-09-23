from __future__ import annotations

from pathlib import Path

from peptiforg_core.workflow_pde_bridge import (
    QUALITY_OPTIONS,
    STRUCTURE_OPTIONS,
    build_workflow_pde_config,
    normalize_structure_choice,
)

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_hotspot_selection_targets_embedded_pde_field():
    src = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'text="PDE target sequence"' in src
    assert 'self.pde_target_var.set(sequence)' in src
    assert 'self._sync_hotspot_to_pde_field(row)' in src
    assert 'text="Run PDE"' in src
    assert 'text="Open Design"' not in src
    assert 'text="Import PDE results"' not in src
    assert 'text="Open selected in PDE"' not in src


def test_workflow_has_structure_objective_and_ranked_candidate_selector():
    src = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'text="Preferred structure"' in src
    assert 'values=STRUCTURE_OPTIONS' in src
    assert 'self.pde_candidate_combo' in src
    assert 'text="Quality"' in src
    assert 'values=QUALITY_OPTIONS' in src
    assert 'self.pde_candidate_combo.bind("<<ComboboxSelected>>", self._on_pde_candidate_choice)' in src
    assert 'text="Build Structure"' in src
    assert 'text="Open SPPS Planner"' in src


def test_hotspot_gui_selection_is_automatic_workflow_handoff_not_pde_launcher():
    src = (ROOT / "suite_gui" / "hotspot_gui.py").read_text(encoding="utf-8")
    assert 'self._sync_selected_for_pde(silent=True)' in src
    assert 'write_design_handoff(' in src
    assert 'text="Open selected in PDE"' not in src


def test_workflow_pde_bridge_structure_mode_mapping():
    assert normalize_structure_choice("AUTO / BALANCED") == ("BALANCED", "NONE")
    assert normalize_structure_choice("ALPHA_HELIX") == ("STRUCTURE_GUIDED", "ALPHA_HELIX")
    assert "BETA_HAIRPIN" in STRUCTURE_OPTIONS


def test_workflow_pde_config_uses_real_pde_backend_contract(tmp_path: Path):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    cfg = build_workflow_pde_config("ACDEFG", "BETA_HAIRPIN", "Quick", hotspot_profile_path=profile)
    assert cfg["TARGETS"] == [list("ACDEFG")]
    assert cfg["TARGET_MODE_LABEL"] == "SINGLE"
    assert cfg["DESIGN_MODE"] == "SINGLE_TARGET"
    assert cfg["PDE_OBJECTIVE_MODE"] == "STRUCTURE_GUIDED"
    assert cfg["PREFERRED_STRUCTURE"] == "BETA_HAIRPIN"
    assert cfg["HOTSPOT_CHEMISTRY_PROFILE_PATH"] == str(profile)
    assert cfg["USE_OPTIONAL_ML"] is False
    assert cfg["POP"] == 60 and cfg["GEN"] == 4 and cfg["FINAL_TOPK"] == 8
    assert QUALITY_OPTIONS[0] == "Balanced (recommended)"


def test_pde_standalone_launcher_has_nonblocking_import_loader():
    src = (ROOT / "main_launcher.py").read_text(encoding="utf-8")
    assert 'Loading design engine...' in src
    assert 'PepforgePDEImport' in src
    assert 'worker = threading.Thread' in src
    assert 'loader.after(250, _show_loader_if_needed)' in src
    assert 'loader.after(50, _poll)' in src


def test_workflow_downstream_tools_share_selected_pde_candidate_directly():
    src = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'self.candidate_var.set(seq)' in src
    assert 'self.psb_status_var.set(f"PDE candidate #{rank} selected. Build Structure will use this sequence.")' in src
    assert 'self.spps_status_var.set(f"PDE candidate #{rank} linked to SPPS: {seq}")' in src
    assert 'seq = self.candidate_var.get().strip()' in src
    assert 'def _execute_spps_plan' in src
    assert 'self.launch_tool("spps")' in src
    assert 'PEPFORGE_WORKFLOW_SPPS_SEQUENCE' in src
    assert 'def import_design_candidates' not in src
    assert 'def open_selected_hotspot_in_pde' not in src


def test_workflow_pde_psb_are_nonblocking_workers_and_spps_opens_full_planner():
    src = (ROOT / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'name="PepforgeWorkflowPDE"' in src
    assert 'name="PepforgeWorkflowPSB"' in src
    assert 'name="PepforgeWorkflowSPPS"' not in src
    assert 'self.root.after(150, self._poll_pde_worker)' in src
    assert 'self.root.after(150, self._poll_psb_worker)' in src
    assert 'self.launch_tool("spps")' in src
