from __future__ import annotations

from pathlib import Path

import peptiforg_core.workflow_gui as workflow_gui
from peptiforg_core.workflow_gui import WorkflowApp
from spps_v4_gui.catalogs import RESIN_VALUES
from suite_gui.spps_tk_gui import _workflow_handoff_from_env


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Status(_Var):
    pass


def test_hotspot_to_pde_and_pde_to_psb_visible_handoff_contract():
    root = Path(__file__).resolve().parents[1]
    src = (root / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert "self._sync_hotspot_to_pde_field(row)" in src
    assert 'text="PSB input candidate"' in src
    assert 'self.psb_candidate_combo.bind("<<ComboboxSelected>>", self._on_psb_candidate_choice)' in src
    assert 'self.psb_candidate_combo.configure(values=values)' in src
    assert 'self.psb_candidate_var.set(self.pde_candidate_var.get())' in src
    assert 'text="Ranked structure"' in src
    assert 'self.structure_choice_combo.bind("<<ComboboxSelected>>", self._on_structure_choice)' in src


def test_psb_candidate_dropdown_mirrors_selected_pde_candidate():
    app = WorkflowApp.__new__(WorkflowApp)
    app.psb_candidate_var = _Var("candidate B")
    app.pde_candidate_var = _Var("candidate A")
    app._pde_candidate_map = {"candidate A": {"sequence": "AAAA"}, "candidate B": {"sequence": "BBBB"}}
    called = []
    app._on_pde_candidate_choice = lambda *args, **kwargs: called.append(app.pde_candidate_var.get())
    WorkflowApp._on_psb_candidate_choice(app)
    assert app.pde_candidate_var.get() == "candidate B"
    assert called == ["candidate B"]


def test_workflow_spps_uses_full_resin_catalog_and_requested_field_order():
    root = Path(__file__).resolve().parents[1]
    src = (root / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert len(list(dict.fromkeys(RESIN_VALUES))) > 4
    assert "self._workflow_resin_values = list(dict.fromkeys(RESIN_VALUES))" in src
    resin_at = src.index('text="Resin"')
    loading_at = src.index('text="Loading mmol/g"')
    scale_at = src.index('text="Scale mmol"')
    assert resin_at < loading_at < scale_at
    assert 'text="Open SPPS Planner"' in src


def test_workflow_spps_button_launches_planner_instead_of_invisible_background_plan(monkeypatch, tmp_path: Path):
    app = WorkflowApp.__new__(WorkflowApp)
    app.project_dir = tmp_path
    app.require_project = lambda: tmp_path
    app.candidate_var = _Var("Ac-EEMQRR-NH2")
    app.resin_var = _Var("Rink Amide AM")
    app.loading_var = _Var("0.72")
    app.scale_var = _Var("400")
    app.spps_status_var = _Status()
    app.write_log = lambda message: None
    app._refresh_workflow_progress_from_project = lambda: None
    launched = []
    app.launch_tool = lambda tool: launched.append(tool)

    project = {
        "active_candidate_id": "cand-1",
        "workflow_state": {"pde_revision": 7},
    }
    saved = {}
    monkeypatch.setattr(workflow_gui, "load_project", lambda folder: project)
    monkeypatch.setattr(workflow_gui, "save_project", lambda folder, payload: saved.update(payload))

    WorkflowApp.run_spps(app)
    assert launched == ["spps"]
    handoff = saved["workflow_state"]["spps_handoff"]
    assert handoff == {
        "sequence": "Ac-EEMQRR-NH2",
        "candidate_id": "cand-1",
        "resin": "Rink Amide AM",
        "resin_loading_mmol_g": 0.72,
        "scale_mmol": 400.0,
        "workflow_pde_revision": 7,
    }
    assert "spps_settings" not in saved


def test_spps_planner_reads_workflow_handoff_without_changing_normal_blank_startup():
    assert _workflow_handoff_from_env({}) == {}
    handoff = _workflow_handoff_from_env({
        "PEPFORGE_WORKFLOW_SPPS_PROJECT": r"C:\\Pepforge\\ProjectA",
        "PEPFORGE_WORKFLOW_SPPS_SEQUENCE": "Ac-EEMQRR-NH2",
        "PEPFORGE_WORKFLOW_SPPS_RESIN": "2-CTC",
        "PEPFORGE_WORKFLOW_SPPS_LOADING": "0.55",
        "PEPFORGE_WORKFLOW_SPPS_SCALE": "200",
    })
    assert handoff["sequence"] == "Ac-EEMQRR-NH2"
    assert handoff["resin"] == "2-CTC"
    assert handoff["loading"] == "0.55"
    assert handoff["scale"] == "200"


def test_evidence_runtime_status_panel_removed_but_internal_logging_retained():
    root = Path(__file__).resolve().parents[1]
    src = (root / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert 'text="4. Evidence / Runtime Status"' not in src
    assert "self.log = tk.Text" not in src
    assert "self._runtime_messages" in src
    assert 'LOGGER.info("Workflow: %s", text)' in src
    assert "Export Candidate Evidence Matrix" in src
    assert "Export Blind Review" in src


def test_launch_tool_passes_workflow_spps_prefill_to_child_process(monkeypatch, tmp_path: Path):
    app = WorkflowApp.__new__(WorkflowApp)
    app.project_dir = tmp_path
    app.candidate_var = _Var("Ac-EEMQRR-NH2")
    app.resin_var = _Var("Wang")
    app.loading_var = _Var("0.65")
    app.scale_var = _Var("250")
    captured = {}

    def fake_popen(cmd, cwd=None, env=None, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = dict(env or {})
        return object()

    monkeypatch.setattr(workflow_gui.subprocess, "Popen", fake_popen)
    WorkflowApp.launch_tool(app, "spps")
    env = captured["env"]
    assert env["PEPFORGE_WORKFLOW_SPPS_PROJECT"] == str(tmp_path)
    assert env["PEPFORGE_WORKFLOW_SPPS_SEQUENCE"] == "Ac-EEMQRR-NH2"
    assert env["PEPFORGE_WORKFLOW_SPPS_RESIN"] == "Wang"
    assert env["PEPFORGE_WORKFLOW_SPPS_LOADING"] == "0.65"
    assert env["PEPFORGE_WORKFLOW_SPPS_SCALE"] == "250"
    assert captured["cmd"][-1] == "spps"
