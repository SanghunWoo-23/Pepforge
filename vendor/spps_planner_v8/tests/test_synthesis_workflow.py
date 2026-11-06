from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from suite_gui import synthesis_workflow
from suite_gui.controller import SPPSGui
from suite_gui import position_rules
from suite_gui.modules import plan_workflow


ROOT = Path(__file__).resolve().parents[1]


def test_generate_preserves_final_wrapper_order(monkeypatch):
    events = []
    gui = object()
    namespace = {"accepted": True}
    monkeypatch.setattr(
        synthesis_workflow.project_manager_workflow,
        "_sync_modifier_to_aa",
        lambda actual: events.append(("sync", actual)),
    )
    monkeypatch.setattr(synthesis_workflow, "_namespace", lambda: namespace)
    monkeypatch.setattr(
        synthesis_workflow.plan_workflow,
        "generate",
        lambda actual, ns: events.append(("generate", actual, ns)) or "generated",
    )

    assert synthesis_workflow.generate(gui) == "generated"
    assert events == [("sync", gui), ("generate", gui, namespace)]


def test_apply_change_preserves_final_wrapper_order(monkeypatch):
    events = []
    gui = object()
    namespace = {"accepted": True}
    monkeypatch.setattr(
        synthesis_workflow.project_manager_workflow,
        "_sync_modifier_to_aa",
        lambda actual: events.append(("sync", actual)),
    )
    monkeypatch.setattr(synthesis_workflow, "_namespace", lambda: namespace)
    monkeypatch.setattr(
        synthesis_workflow.plan_workflow,
        "apply_change",
        lambda actual, ns: events.append(("apply", actual, ns)) or "applied",
    )

    assert synthesis_workflow.apply_change(gui) == "applied"
    assert events == [("sync", gui), ("apply", gui, namespace)]


def test_controller_synthesis_routes_do_not_use_super():
    path = ROOT / "suite_gui" / "controller.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SPPSGui"
    )
    direct_routes = {
        "generate_update_plan",
        "pm_generate_selected",
        "pm_calculate_all",
        "apply_change",
        "pm_apply_change",
        "apply_plan_mw_density",
    }
    methods = {
        node.name: ast.unparse(node)
        for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name in direct_routes
    }

    assert set(methods) == direct_routes
    assert all("super()" not in source for source in methods.values())
    assert all("synthesis_workflow." in source for source in methods.values())


def test_all_controller_synthesis_aliases_reach_direct_service(monkeypatch):
    calls = []
    monkeypatch.setattr(
        synthesis_workflow,
        "generate",
        lambda gui, *args, **kwargs: calls.append(("generate", gui, args, kwargs)) or True,
    )
    monkeypatch.setattr(
        synthesis_workflow,
        "apply_change",
        lambda gui, *args, **kwargs: calls.append(("apply", gui, args, kwargs)) or True,
    )
    gui = object.__new__(SPPSGui)

    assert gui.generate_update_plan("g") is True
    assert gui.pm_generate_selected("s") is True
    assert gui.pm_calculate_all("a") is True
    assert gui.apply_change("c") is True
    assert gui.pm_apply_change("p") is True
    assert gui.apply_plan_mw_density("m") is True
    assert [entry[0] for entry in calls] == [
        "generate", "generate", "generate", "apply", "apply", "apply",
    ]


def test_plan_buttons_are_bound_to_direct_controller_routes():
    source = (
        ROOT / "suite_gui" / "modules" / "plan_workflow.py"
    ).read_text(encoding="utf-8")
    assert '"pm_generate_button": gui.generate_update_plan' in source
    assert '"pm_apply_button": gui.apply_change' in source
    assert 'text == "Generate"' not in source
    assert 'text == "Apply Change"' not in source
    assert "workspace_widgets._install_action_buttons(gui, ns)" not in source


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _RuleGui:
    pm_sequence = _Var("Ac-AAAAAA-NH2")
    coupling_eq = _Var("5")
    reagent_eq_follows_coupling_eq = _Var(True)
    use_position_aa_eq = _Var(False)
    position_aa_eq_rules = _Var("")
    use_position_doubling = _Var(True)
    position_doubling_rules = _Var("")


def _seven_mixed_unit_rows():
    names = [
        "Fmoc-Arg(Pbf)-OH",
        "Fmoc-d-Arg(Pbf)-OH",
        "AEEA",
        "Fmoc-Gln(Trt)-OH",
        "FITC",
        "Biotin",
        "Acetic anhydride (Ac2O)",
    ]
    return [
        {
            "No": str(index),
            "Unit name": name,
            "Repeat": "1",
            "Unit eq": "5",
        }
        for index, name in enumerate(names, 1)
    ]


def test_doubling_blank_single_and_range_rules_cover_every_unit_class():
    gui = _RuleGui()

    blank = position_rules._apply_generated_position_rules(
        gui, _seven_mixed_unit_rows(),
    )
    assert [row["Repeat"] for row in blank] == ["1"] * 7

    gui.position_doubling_rules.set("7:2")
    single = position_rules._apply_generated_position_rules(
        gui, _seven_mixed_unit_rows(),
    )
    assert [row["Repeat"] for row in single] == [
        "1", "1", "1", "1", "1", "1", "2",
    ]

    gui.position_doubling_rules.set("4-7:3")
    ranged = position_rules._apply_generated_position_rules(
        gui, _seven_mixed_unit_rows(),
    )
    assert [row["Repeat"] for row in ranged] == [
        "1", "1", "1", "3", "3", "3", "3",
    ]


class _Tree:
    def __init__(self, rows):
        self.columns = list(plan_workflow.PLAN_COLUMNS)
        self.rows = {
            str(index): [row.get(column, "") for column in self.columns]
            for index, row in enumerate(rows)
        }

    def __getitem__(self, key):
        assert key == "columns"
        return self.columns

    def get_children(self):
        return tuple(self.rows)

    def item(self, iid, option=None, **kwargs):
        if "values" in kwargs:
            self.rows[iid] = list(kwargs["values"])
        if option == "values":
            return tuple(self.rows[iid])
        return {"values": tuple(self.rows[iid])}


class _OutputTree:
    def __init__(self, rows=None):
        self.rows = list(rows or [])


class _ResultNotebook:
    def __init__(self, label="Selected Plan"):
        self.label = label

    def select(self):
        return "current"

    def tab(self, _tab, option):
        assert option == "text"
        return self.label


def test_generate_linked_output_paints_every_table_and_preserves_cleavage(monkeypatch):
    materials = [{"material": "Fmoc-Gly-OH", "planned_mmol": "2"}]
    checklist = [{"operation": "Coupling 1"}]
    totals = [{"material": "Fmoc-Gly-OH", "total mmol": "2"}]
    prior_cleavage = [{"component": "TFA", "volume_mL": "9.5"}]
    gui = SimpleNamespace(
        pm_results_notebook=_ResultNotebook(),
        pm_selected_material_tree=_OutputTree(),
        pm_selected_total_tree=_OutputTree(),
        progress_tree=_OutputTree(),
        pm_cleavage_tree=_OutputTree(prior_cleavage),
        pm_items=[{"selected_cleavage_rows": list(prior_cleavage)}],
        _v229_active_index=0,
        _pm_rendered_output_index={"selected_cleavage_rows": 0},
        _update_progress_widgets=lambda: None,
    )
    monkeypatch.setattr(
        plan_workflow, "_visible_protocol",
        lambda *_args: (list(materials), list(checklist)),
    )
    monkeypatch.setattr(plan_workflow, "_total_rows", lambda _rows: list(totals))
    monkeypatch.setattr(
        plan_workflow.workspace_widgets, "_write_rows",
        lambda tree, rows, *_args: setattr(tree, "rows", list(rows)),
    )

    plan_workflow._write_linked(
        gui, {}, object(),
        include_cleavage=False,
        paint_all_linked=True,
    )

    assert gui.pm_selected_material_tree.rows == materials
    assert gui.pm_selected_total_tree.rows == totals
    assert gui.progress_tree.rows == checklist
    assert gui.pm_cleavage_tree.rows == prior_cleavage
    assert gui.pm_items[0]["selected_cleavage_rows"] == prior_cleavage
    assert gui._pm_rendered_output_index == {
        "selected_material_rows": 0,
        "selected_total_rows": 0,
        "selected_checklist_rows": 0,
        "selected_cleavage_rows": 0,
    }


def test_apply_change_linked_output_still_updates_cleavage(monkeypatch):
    cleavage = pd.DataFrame([
        {
            "component": "TFA", "volume_mL": 9.5, "approx_g": "",
            "density_g_mL": 1.49, "percent": 95, "percent_basis": "v/v",
        },
    ])
    gui = SimpleNamespace(
        pm_results_notebook=_ResultNotebook("Cleavage Cocktail"),
        pm_selected_material_tree=_OutputTree(),
        pm_selected_total_tree=_OutputTree(),
        progress_tree=_OutputTree(),
        pm_cleavage_tree=_OutputTree(),
        pm_items=[{}],
        _v229_active_index=0,
        _pm_rendered_output_index={},
        _update_progress_widgets=lambda: None,
    )
    monkeypatch.setattr(plan_workflow, "_visible_protocol", lambda *_args: ([], []))
    monkeypatch.setattr(plan_workflow, "_total_rows", lambda rows: list(rows))
    monkeypatch.setattr(
        plan_workflow, "_refresh_cleavage",
        lambda *_args, **_kwargs: cleavage.copy(),
    )
    monkeypatch.setattr(
        plan_workflow.workspace_widgets, "_write_rows",
        lambda tree, rows, *_args: setattr(tree, "rows", list(rows)),
    )

    plan_workflow._write_linked(gui, {}, object(), include_cleavage=True)

    assert gui.pm_items[0]["selected_cleavage_rows"][0]["component"] == "TFA"
    assert gui.pm_items[0]["selected_material_rows"][0]["phase"] == "Cleavage"
    assert gui._pm_rendered_output_index["selected_cleavage_rows"] == 0


def test_visible_protocol_expands_repeat_into_real_coupling_cycles(monkeypatch):
    import spps_planner.engine as engine
    from types import SimpleNamespace

    monkeypatch.setattr(engine, "working_volume_mL", lambda _inp: 8.0)
    monkeypatch.setattr(engine, "resin_profile", lambda _resin: "AMIDE")
    row = {column: "" for column in plan_workflow.PLAN_COLUMNS}
    row.update({
        "No": "1", "Unit name": "Fmoc-Gly-OH", "Unit eq": "2",
        "Unit mmol": "4", "Reagent 1": "DIC", "R1 eq": "2",
        "R1 mmol": "4", "Reagent 2 / catalyst": "HOBt",
        "R2 eq": "2", "R2 mmol": "4", "Coupling solvent": "DMF",
        "Solvent mL": "16", "Repeat": "2",
    })
    gui = SimpleNamespace(pm_selected_plan_tree=_Tree([row]))
    inp = SimpleNamespace(
        resin="Rink Amide AM", scale_mmol=1.0,
        resin_loading_mmol_g=0.8, apply_resin_loading=False,
        deprotection_count=2, deprotection_ratio="20% in DMF",
        deprotection_base="Piperidine",
    )

    materials, checklist = plan_workflow._visible_protocol(gui, {}, inp)
    operations = [record["operation"] for record in checklist]
    assert operations == [
        "Deprotection 1", "Deprotection 2", "DMF wash x6",
        "Coupling 1", "DMF wash x2", "Coupling 2",
        "Post-coupling DMF wash x2",
        "Last Fmoc deprotection 1", "Last Fmoc deprotection 2",
        "Final DMF wash x3", "Final MC/DCM wash x3",
    ]
    glycine = [row for row in materials if row["material"] == "Fmoc-Gly-OH"]
    assert [row["phase"] for row in glycine] == ["Coupling 1", "Coupling 2"]
    assert sum(float(row["planned_mmol"]) for row in glycine) == 4.0
    assert next(
        row for row in materials if row["class"] == "Pre-coupling wash solvent"
    )["use_count"] == 6


def test_total_rows_keep_accepted_operating_order_without_patch_layer():
    materials = [
        {"material": "TFA", "class": "Acid/Cleavage reagent", "planned_mL": "1"},
        {"material": "Fmoc-Gly-OH", "class": "AA/Chemical", "planned_mmol": "2"},
        {"material": "DIC", "class": "Coupling reagent", "planned_mmol": "2"},
        {"material": "Piperidine", "class": "Deprotection base", "planned_mL": "1"},
        {"material": "DMF", "class": "Solvent", "planned_mL": "8"},
        {"material": "Rink Amide AM", "class": "Resin", "planned_g": "1"},
        {"material": "nan", "class": "AA/Chemical"},
    ]
    rows = plan_workflow._total_rows(materials)
    assert [row["material"] for row in rows] == [
        "Rink Amide AM", "DMF", "Piperidine", "DIC", "Fmoc-Gly-OH", "TFA",
    ]
