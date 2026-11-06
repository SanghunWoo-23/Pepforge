from __future__ import annotations

import os
import pytest

from suite_gui import batch_workflow
from suite_gui import catalogs
from suite_gui.modules import project_manager_workflow


class _Tree:
    def __init__(self, columns, rows=()):
        self.columns = list(columns)
        self.rows = {
            str(index): tuple(row.get(column, "") for column in self.columns)
            for index, row in enumerate(rows)
        }

    def get_children(self):
        return tuple(self.rows)

    def item(self, item_id, option=None):
        values = self.rows[item_id]
        return values if option == "values" else {"values": values}

    def delete(self, *item_ids):
        for item_id in item_ids:
            self.rows.pop(item_id, None)

    def insert(self, _parent, _where, values):
        item_id = str(max([int(key) for key in self.rows] + [-1]) + 1)
        self.rows[item_id] = tuple(values)
        return item_id

    def cget(self, option):
        return tuple(self.columns) if option == "columns" else ""

    def configure(self, **kwargs):
        if "columns" in kwargs:
            self.columns = list(kwargs["columns"])

    def heading(self, *_args, **_kwargs):
        return None

    def column(self, *_args, **_kwargs):
        return None


BATCH_COLUMNS = [
    "No", "Project", "Peptide name", "Form", "Copies", "N-term",
    "Region 1 seq", "Region 1 eq", "Linker", "Region 2 seq",
    "Region 2 eq", "Tag", "Label", "C-term", "Chemistry",
    "Scale mmol", "AA conc M", "AA coupling eq", "Resin", "Loading",
    "LOT No", "Status",
]


def test_protected_fmoc_names_are_primary_unit_choices():
    assert catalogs.UNIT_VALUES[1:5] == [
        "Fmoc-Ala-OH", "Fmoc-Arg(Pbf)-OH", "Fmoc-Asn(Trt)-OH",
        "Fmoc-Asp(OtBu)-OH",
    ]
    assert "A" not in catalogs.UNIT_VALUES
    assert "Ala" not in catalogs.UNIT_VALUES
    assert "D-Arg" not in catalogs.UNIT_VALUES
    assert "Fmoc-D-Arg(Pbf)-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-NH-PEG4-CH2COOH" in catalogs.UNIT_VALUES


def test_project_driven_batch_ui_uses_clean_controller_method():
    from suite_gui.classic_base import ClassicControllerBase

    assert ClassicControllerBase._build_batch_tab.__name__ == "_build_batch_tab"
    assert ClassicControllerBase._build_batch_tab.__module__ == "suite_gui.modules.classic_batch_controller"


def test_compact_batch_columns_receive_all_canonical_values():
    record = {
        "Item": "Fmoc-Ala-OH", "Solvent": "DMF",
        "Calculated_mL": 12.5, "Chemistry": "DIC/HOBt",
        "Loading": 0.68,
    }

    assert batch_workflow._display_value(record, "AA") == "Fmoc-Ala-OH"
    assert batch_workflow._display_value(record, "solvent") == "DMF"
    assert batch_workflow._display_value(record, "calculated_mL") == 12.5
    assert batch_workflow._display_value(record, "chemistry") == "DIC/HOBt"
    assert batch_workflow._display_value(record, "loading_mmol_g") == 0.68


def test_batch_uses_editable_rows_and_recognizes_protected_aa_linker_tag():
    row = {
        "No": 1, "Project": "P", "Peptide name": "Pep", "Copies": "2",
        "Region 1 seq": "ACDE", "Region 1 eq": "1", "Linker": "Ahx",
        "Tag": "His6", "Label": "FITC", "C-term": "NH2",
        "Chemistry": "DIC/HOBt",
        "Scale mmol": "0.2", "AA conc M": "0.25", "AA coupling eq": "5",
        "Resin": "Rink Amide AM", "Loading": "0.8", "LOT No": "L-1",
    }
    gui = type("Gui", (), {})()
    gui.pm_items = []
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(BATCH_COLUMNS, [row])

    tables = batch_workflow.calculate(gui)

    assert len(tables["Summary"]) == 1
    aa_items = set(tables["AA stock"]["Item"])
    assert aa_items == {
        "Fmoc-Ala-OH", "Fmoc-Cys(Trt)-OH", "Fmoc-Asp(OtBu)-OH",
        "Fmoc-Glu(OtBu)-OH",
    }
    assert not aa_items.intersection({"A", "C", "D", "E"})
    chemical_items = set(tables["Chemicals"]["Item"])
    assert "Fmoc-6-Ahx-OH" in chemical_items
    assert "His6 peptide tag macro (HHHHHH)" in chemical_items
    assert "FITC isothiocyanate" in chemical_items
    assert "His6 peptide tag macro (HHHHHH)" not in set(
        tables["Coupling reagents"]["Item"]
    )


class _Listbox:
    def curselection(self):
        return (1,)


def test_project_switch_does_not_reserialize_unchanged_output_trees(monkeypatch):
    gui = type("Gui", (), {})()
    gui.pm_items = [{"project": "A"}, {"project": "B"}]
    gui.pm_list = _Listbox()
    gui._v229_active_index = 0
    gui._v229_dirty_columns = {}
    gui._v2212_switching = False
    gui._v2212_dragging = False
    calls = []

    monkeypatch.setattr(
        project_manager_workflow, "_save_active",
        lambda _gui, _workflow, include_outputs=True: calls.append(include_outputs),
    )
    monkeypatch.setattr(
        project_manager_workflow, "_restore",
        lambda _gui, _workflow, _namespace, index: calls.append(("restore", index)),
    )

    project_manager_workflow.single_select(gui, object(), {})

    assert calls == [False, ("restore", 1)]


def test_batch_sequence_does_not_misread_dashed_alanine_cysteine_as_acetyl():
    row = {
        "Region 1 seq": "ACD", "Region 1 eq": "1", "Linker": "PEG4",
        "C-term": "NH2",
    }
    sequence = batch_workflow._batch_sequence(row)

    from spps_planner.parser import parse_sequence

    parsed = parse_sequence(sequence)
    assert parsed.nterm == ""
    assert parsed.core_tokens == ["A", "C", "D", "Fmoc-NH-PEG4-CH2COOH"]

    dashed = parse_sequence("A-C-D-NH2")
    assert dashed.nterm == ""
    assert dashed.core_tokens == ["A", "C", "D"]

    typed = parse_sequence("[His6]-[FITC]-ACD-[PEG4]-NH2")
    assert typed.nterm == "His6"
    assert typed.core_tokens == ["FITC", "A", "C", "D", "PEG4"]


def test_batch_restore_prefers_saved_operator_rows_and_empty_state_stays_empty():
    saved = {column: "" for column in BATCH_COLUMNS}
    saved.update({"Project": "Saved", "Peptide name": "Edited", "Region 1 seq": "ACD"})
    gui = type("Gui", (), {})()
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(BATCH_COLUMNS)
    gui.pm_items = [{"project": "Project", "peptide": "Pep", "sequence": "RRR"}]

    batch_workflow.restore_input_rows(gui, [saved])
    assert batch_workflow._batch_input_rows(gui)[0]["Project"] == "Saved"

    # No persisted Batch rows must not silently import Project Manager data.
    batch_workflow.restore_input_rows(gui, [])
    assert batch_workflow._batch_input_rows(gui) == []


def test_batch_calculation_requires_explicit_project_sync(monkeypatch):
    from spps_planner import engine

    original = engine.generate_step_reagent_plan
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "generate_step_reagent_plan", counted)
    gui = type("Gui", (), {})()
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(BATCH_COLUMNS)
    gui.pm_items = [{
        "project": "P", "peptide": "Pep", "sequence": "Ac-ACD-NH2",
        "copies": "1", "scale": "0.2", "resin": "Rink Amide AM",
        "loading": "0.8", "chemistry": "DIC/HOBt",
    }]

    # Mere presence of Project Manager data does not create Batch work.
    tables = batch_workflow.calculate(gui)
    assert len(calls) == 0
    assert tables["Summary"].empty

    # Explicit operator sync makes the Project an editable Batch input.
    batch_workflow.sync_input_from_projects(gui, replace=True)
    batch_workflow.calculate(gui)
    assert len(calls) == 1
    row = batch_workflow._batch_input_rows(gui)[0]
    assert row["Project"] == "P"
    assert row["Region 1 seq"] == "Ac-ACD-NH2"


def test_ac_is_visible_in_project_plan_and_batch_chemical_preparation():
    from spps_planner.engine import PlanInput
    from suite_gui.modules import plan_workflow

    class _Var:
        def __init__(self, current):
            self.current = current

        def get(self):
            return self.current

    gui = type("Gui", (), {})()
    gui.custom_materials = {}
    gui.pm_sequence = _Var("Ac-EEMQRR-NH2")
    gui.use_position_aa_eq = _Var(True)
    gui.use_position_doubling = _Var(True)
    gui.position_aa_eq_rules = _Var("")
    gui.position_doubling_rules = _Var("")
    gui.reagent_eq_follows_coupling_eq = _Var(True)
    gui.coupling_eq = _Var("5")

    plan_rows = plan_workflow._generated_plan_rows(
        gui, {}, PlanInput(
            sequence="Ac-EEMQRR-NH2", scale_mmol=0.5,
            resin="Rink Amide AM", resin_loading_mmol_g=0.68,
        ),
    )
    assert len(plan_rows) == 7
    assert plan_rows[-1]["Unit name"] == (
        "Acetic anhydride (Ac2O)"
    )

    gui.pm_items = [{
        "project": "P", "peptide": "Pep", "sequence": "Ac-EEMQRR-NH2",
        "copies": "1", "scale": "0.5", "resin": "Rink Amide AM",
        "loading": "0.68", "chemistry": "DIC/HOBt",
    }]
    tables = batch_workflow.calculate(gui)
    ac = tables["Chemicals"].iloc[0]
    assert ac["Item"] == "Acetic anhydride"
    assert ac["MW"] == 102.09
    assert ac["Density"] == 1.08
    assert float(ac["Volume_mL"]) > 0


def test_classic_batch_dashboard_schema_is_fully_populated_and_separated():
    gui = type("Gui", (), {})()
    gui.pm_items = [{
        "project": "P", "peptide": "Pep", "sequence": "Ac-EEMQRR-NH2",
        "copies": "1", "scale": "0.5", "resin": "Rink Amide AM",
        "loading": "0.68", "chemistry": "DIC/HOBt",
    }]
    gui.batch_aa_tree = _Tree(
        ["AA", "count", "eq", "conc_M", "calc_mL", "actual_mL", "MW", "weight_g", "note"]
    )
    common = [
        "item", "purpose", "count", "eq", "conc_M", "calculated",
        "actual", "unit", "MW", "density", "weight_g", "volume_mL", "note",
    ]
    gui.batch_coupling_reagent_tree = _Tree(common)
    gui.batch_catalyst_tree = _Tree(common)
    gui.batch_base_tree = _Tree(common)
    gui.batch_solvent_tree = _Tree(common)
    gui.batch_modifier_tree = _Tree(common)
    gui.batch_project_tree = _Tree([
        "no", "project", "peptide_name", "lot_no", "copies", "sequence",
        "scale_mmol", "resin", "output_folder",
    ])
    # R19 compact Batch reads PM sequences, but preparation quantities come only
    # from Solution prep defaults.  Project chemistry is not aggregated.
    batch_workflow.refresh(gui, force=True)

    aa_values = next(iter(gui.batch_aa_tree.rows.values()))
    assert aa_values[0].startswith("Fmoc-")
    assert aa_values[1] and aa_values[2] and aa_values[3]
    assert aa_values[4] and aa_values[5] and aa_values[6] and aa_values[7]
    base_items = {row[0] for row in gui.batch_base_tree.rows.values()}
    assert base_items == {"NMM"}
    assert list(gui.batch_catalyst_tree.rows.values()) == []
    coupling_items = {row[0] for row in gui.batch_coupling_reagent_tree.rows.values()}
    assert coupling_items == {"HBTU"}
    modifier_items = {row[0] for row in gui.batch_modifier_tree.rows.values()}
    assert "Acetic anhydride" in modifier_items
    project_values = next(iter(gui.batch_project_tree.rows.values()))
    assert project_values[1:3] == ("P", "Pep")


def test_batch_uses_each_rows_aa_concentration_and_equivalents():
    first = {column: "" for column in BATCH_COLUMNS}
    first.update({
        "No": "1", "Project": "P1", "Peptide name": "One",
        "Copies": "1", "Region 1 seq": "A", "Region 1 eq": "1",
        "C-term": "NH2", "Chemistry": "DIC/HOBt", "Scale mmol": "1",
        "AA conc M": "0.5", "AA coupling eq": "2",
        "Resin": "Rink Amide AM", "Loading": "0.8",
    })
    second = dict(first)
    second.update({
        "No": "2", "Project": "P2", "Peptide name": "Two",
        "AA conc M": "0.25", "AA coupling eq": "4",
    })
    gui = type("Gui", (), {})()
    gui.pm_items = []
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(BATCH_COLUMNS, [first, second])

    aa = batch_workflow.calculate(gui)["AA stock"]

    assert set(aa["Eq"]) == {2.0, 4.0}
    assert set(aa["Conc_M"]) == {0.5, 0.25}


def test_compact_material_list_groups_l_d_non_natural_then_chemical():
    gui = type("Gui", (), {})()
    gui.pm_items = [{
        "project": "P", "peptide": "Grouped", "sequence": "Ac-dR-V-Cit-NH2",
        "copies": "1", "scale": "0.2", "resin": "Rink Amide AM",
        "loading": "0.8", "chemistry": "DIC/HOBt",
        "tag": "His6", "label": "FITC", "linker": "AEEA", "c_term": "NH2",
    }]

    grouped = batch_workflow.calculate(gui)["AA + Chemicals"]
    pairs = list(grouped[["Category", "Item"]].itertuples(index=False, name=None))
    categories = [category for category, _ in pairs]
    order = {"L-AA": 0, "D-AA": 1, "Non-natural AA": 2, "Chemical": 3}
    assert [order[category] for category in categories] == sorted(order[category] for category in categories)
    assert ("D-AA", "Fmoc-D-Arg(Pbf)-OH") in pairs
    assert ("Non-natural AA", "Fmoc-Cit-OH") in pairs
    assert ("Chemical", "Acetic anhydride") in pairs
    # R19 intentionally ignores separate PM tag/label/linker fields: only the
    # sequence itself is imported into the compact Batch preparation calculator.
    assert ("Chemical", "FITC isothiocyanate") not in pairs
    assert ("Chemical", "Fmoc-AEEA-OH") not in pairs
    assert not any(category == "Chemical" and item.startswith("His6") for category, item in pairs)
    for category in ("L-AA", "D-AA", "Non-natural AA", "Chemical"):
        items = [item for current, item in pairs if current == category]
        assert items == sorted(items, key=str.casefold)


def test_shared_compact_tree_is_not_overwritten_by_chemical_repaint():
    gui = type("Gui", (), {})()
    gui.pm_items = [{
        "project": "P", "peptide": "Grouped", "sequence": "dR-V-Cit-NH2",
        "copies": "1", "scale": "0.2", "resin": "Rink Amide AM",
        "loading": "0.8", "chemistry": "DIC/HOBt", "label": "FITC",
    }]
    shared = _Tree(batch_workflow.BATCH_COLUMNS)
    gui.batch_aa_tree = shared
    gui.batch_modifier_tree = shared
    gui.batch_coupling_reagent_tree = None
    gui.batch_catalyst_tree = None
    gui.batch_base_tree = None
    gui.batch_solvent_tree = None
    gui.batch_project_tree = None
    gui.v29_batch_trees = {}

    batch_workflow.refresh(gui, force=True)
    pairs = [(row[0], row[1]) for row in shared.rows.values()]
    assert ("L-AA", "Fmoc-Val-OH") in pairs
    assert ("D-AA", "Fmoc-D-Arg(Pbf)-OH") in pairs
    assert ("Non-natural AA", "Fmoc-Cit-OH") in pairs
    assert ("Chemical", "FITC isothiocyanate") not in pairs


def test_r18_legacy_editable_batch_still_restores_saved_operator_rows(tmp_path):
    from suite_gui import state_persistence

    path = tmp_path / "spps_planner_session_v1.json"
    saved = {column: "" for column in BATCH_COLUMNS}
    saved.update({
        "Project": "Real batch", "Peptide name": "GHK run",
        "Region 1 seq": "GHK", "Copies": "1",
        "C-term": "NH2", "Scale mmol": "0.2",
        "Resin": "Rink Amide AM", "Loading": "0.8",
    })
    state_persistence.atomic_write_json(path, {
        "app_version": "V6.0.0",
        "pm_items": [{"project": "Project A", "sequence": "GHK"}],
        "batch_rows": [saved],
    })
    gui = type("Gui", (), {})()
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(BATCH_COLUMNS)
    gui.pm_items = [{"project": "Project A", "sequence": "GHK"}]
    gui.state_file = path

    batch_workflow.initialize(gui)
    rows = batch_workflow._batch_input_rows(gui)
    assert len(rows) == 1
    assert rows[0]["Project"] == "Real batch"
    assert rows[0]["Region 1 seq"] == "GHK"


class _Var:
    def __init__(self, current):
        self.current = current

    def get(self):
        return self.current


def _r19_compact_gui(pm_items, *, scale="0.2", aa_conc="0.25", aa_eq="5", hbtu_eq="4", hbtu_conc="0.4", round_ml="10", extra_ml="10"):
    gui = type("Gui", (), {})()
    gui.pm_items = pm_items
    gui.batch_default_scale = _Var(scale)
    gui.batch_solution_conc = _Var(aa_conc)
    gui.batch_coupling_eq = _Var(aa_eq)
    gui.batch_hbtu_eq = _Var(hbtu_eq)
    gui.batch_hbtu_conc = _Var(hbtu_conc)
    gui.batch_actual_round_ml = _Var(round_ml)
    gui.batch_actual_extra_ml = _Var(extra_ml)
    return gui


def test_r19_compact_batch_ignores_project_chemistry_and_uses_prep_defaults():
    gui = _r19_compact_gui([{
        "project": "P", "peptide": "GHK run", "sequence": "GHK",
        "copies": "1", "scale": "9.9", "resin": "2-CTC",
        "loading": "0.65", "chemistry": "DIC/HOBt",
        "coupling_eq": "2",
    }], scale="0.2", aa_eq="6", hbtu_eq="4", hbtu_conc="0.4")

    tables = batch_workflow.calculate(gui)
    coupling = tables["Coupling reagents"]
    assert set(coupling["Item"]) == {"HBTU"}
    assert set(coupling["Eq"]) == {4.0}
    assert "DIC" not in set(coupling["Item"])
    assert tables["Catalyst/additive"].empty
    assert set(tables["Base/Deprotection"]["Item"]) == {"NMM"}
    assert set(tables["AA stock"]["Eq"]) == {6.0}
    summary = tables["Summary"].iloc[0]
    assert float(summary["Scale mmol"]) == 0.2
    assert summary["Chemistry"] == "Solution prep defaults"


def test_r19_compact_batch_rounds_solution_volumes_from_defaults():
    gui = _r19_compact_gui([{
        "project": "P", "sequence": "G", "copies": "1",
        "scale": "99", "chemistry": "DIC/HOBt",
    }], scale="0.2", aa_conc="0.25", aa_eq="5", hbtu_eq="4", hbtu_conc="0.4", round_ml="10", extra_ml="10")

    tables = batch_workflow.calculate(gui)
    aa = tables["AA stock"].iloc[0]
    # 1 residue × 0.2 mmol × 5 eq / 0.25 M = 4 mL -> 10 mL round + 10 mL reserve.
    assert float(aa["Calculated_mL"]) == pytest.approx(4.0)
    assert float(aa["Actual_mL"]) == pytest.approx(20.0)
    hbtu = tables["Coupling reagents"].iloc[0]
    # 1 × 0.2 × 4 / 0.4 M = 2 mL -> same practical 20 mL prep volume.
    assert float(hbtu["Calculated_mL"]) == pytest.approx(2.0)
    assert float(hbtu["Actual_mL"]) == pytest.approx(20.0)
    stock_solvent = tables["Solvents"].iloc[0]
    assert stock_solvent["Item"] == "DMF"
    assert float(stock_solvent["Actual_mL"]) == pytest.approx(20.0)
    nmm = tables["Base/Deprotection"].iloc[0]
    assert nmm["Item"] == "NMM"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_r18_real_tk_batch_auto_aggregates_project_manager_only(monkeypatch, tmp_path):
    from suite_gui import state_persistence
    from suite_gui.classic_2094_tk_gui import SPPSGui

    state_path = tmp_path / "spps_planner_session_v1.json"
    state_persistence.atomic_write_json(state_path, {
        "app_version": "V6.0.0",
        "pm_items": [{
            "project": "GHK project", "peptide": "GHK run",
            "sequence": "GHK", "copies": "1", "scale": "0.2",
            "resin": "Rink Amide AM", "loading": "0.8",
            "chemistry": "DIC/HOBt", "status": "Ready",
        }],
        "batch_rows": [],
    })
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(SPPSGui, "_state_file_path", lambda self: state_path, raising=False)

    gui = SPPSGui()
    try:
        gui.withdraw()
        gui.update_idletasks()
        assert [str(item.get("sequence", "")) for item in gui.pm_items] == ["GHK"]

        # Opening Batch Manager automatically calculates the real PM collection.
        for tab_id in gui.tabs.tabs():
            if gui.tabs.tab(tab_id, "text") == "Batch Manager":
                gui.tabs.select(tab_id)
                break
        gui.update()
        rows = [gui.batch_project_tree.item(iid, "values") for iid in gui.batch_project_tree.get_children()]
        assert len(rows) == 1
        assert rows[0][4] == "GHK"
        assert all("LN" not in str(value) for row in rows for value in row)

        # Refresh is only a recalculation button; it is not an activation gate.
        before = tuple(rows[0])
        gui.batch_refresh_totals()
        gui.update()
        rows2 = [gui.batch_project_tree.item(iid, "values") for iid in gui.batch_project_tree.get_children()]
        assert len(rows2) == 1
        assert tuple(rows2[0]) == before
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_r18_real_tk_blank_project_placeholder_does_not_create_batch_sequence(monkeypatch, tmp_path):
    from suite_gui import state_persistence
    from suite_gui.classic_2094_tk_gui import SPPSGui

    state_path = tmp_path / "spps_planner_session_v1.json"
    state_persistence.atomic_write_json(state_path, {
        "app_version": "V6.0.0",
        "pm_items": [{
            "project": "", "peptide": "", "sequence": "",
            "copies": "1", "scale": "0.2", "resin": "Rink Amide AM",
            "loading": "0.8", "chemistry": "DIC/HOBt", "status": "Ready",
        }],
        "batch_rows": [],
    })
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(SPPSGui, "_state_file_path", lambda self: state_path, raising=False)

    gui = SPPSGui()
    try:
        gui.withdraw()
        for tab_id in gui.tabs.tabs():
            if gui.tabs.tab(tab_id, "text") == "Batch Manager":
                gui.tabs.select(tab_id)
                break
        gui.update()
        assert list(gui.batch_project_tree.get_children()) == []
        assert list(gui.batch_aa_tree.get_children()) == []
    finally:
        gui.destroy()
