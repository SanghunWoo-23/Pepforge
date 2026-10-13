"""Headless functional proof executed from the packaged Windows EXE."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BUILD_REVISION = "2026-10-06-v7-final"
BATCH_COLUMNS = [
    "No", "Project", "Peptide name", "Form", "Copies", "N-term",
    "Region 1 seq", "Region 1 eq", "Linker", "Region 2 seq",
    "Region 2 eq", "Tag", "Label", "C-term", "Chemistry",
    "Scale mmol", "AA conc M", "AA coupling eq", "Resin", "Loading",
    "LOT No", "Status",
]


class _Tree:
    def __init__(self, row: dict[str, Any]):
        self._values = tuple(row.get(column, "") for column in BATCH_COLUMNS)

    def get_children(self):
        return ("0",)

    def item(self, _item_id, option=None):
        return self._values if option == "values" else {"values": self._values}


def run() -> dict[str, Any]:
    from spps_planner.engine import PlanInput, generate_step_reagent_plan
    from spps_planner.parser import parse_sequence
    from spps_planner.version import VERSION_NUMBER
    from suite_gui import batch_workflow, catalogs, position_rules

    parsed = parse_sequence("[His6]-[FITC]-ACD-[PEG4]-NH2")
    row = {
        "Project": "SELFTEST", "Peptide name": "Runtime", "Copies": "1",
        "Region 1 seq": "ACD", "Region 1 eq": "1", "Linker": "PEG4",
        "Tag": "His6", "Label": "FITC", "C-term": "NH2",
        "Chemistry": "DIC/HOBt", "Scale mmol": "0.2",
        "AA conc M": "0.25", "AA coupling eq": "5",
        "Resin": "Rink Amide AM", "Loading": "0.8",
    }
    gui = type("RuntimeGui", (), {})()
    gui.pm_items = []
    gui.batch_columns = list(BATCH_COLUMNS)
    gui.batch_tree = _Tree(row)
    tables = batch_workflow.calculate(gui)
    aa_items = set(tables["AA stock"]["Item"])
    chemical_items = set(tables["Chemicals"]["Item"])
    ac_plan = generate_step_reagent_plan(PlanInput(sequence="Ac-AAAA-NH2"))
    pal_plan = generate_step_reagent_plan(PlanInput(sequence="Pal-AAAA-NH2"))
    checks = {
        "version": VERSION_NUMBER == "7.0.0",
        "protected_aa_catalog": catalogs.UNIT_VALUES[1] == "Fmoc-Ala-OH",
        "parser_tokens": parsed.core_tokens == ["FITC", "A", "C", "D", "PEG4"],
        "batch_summary": len(tables["Summary"]) == 1,
        "batch_protected_aa": {
            "Fmoc-Ala-OH", "Fmoc-Cys(Trt)-OH", "Fmoc-Asp(OtBu)-OH",
        } <= aa_items,
        "batch_linker_tag_label": {
            "Fmoc-NH-PEG4-CH2COOH",
            "His6 peptide tag macro (HHHHHH)",
            "FITC isothiocyanate",
        } <= chemical_items,
        "terminal_ac_plan": (
            len(ac_plan) == 5
            and str(ac_plan.iloc[-1]["unit"]) == "Ac"
            and "Acetic anhydride" in str(ac_plan.iloc[-1]["protected_reagent"])
        ),
        "terminal_pal_plan": (
            len(pal_plan) == 5
            and str(pal_plan.iloc[-1]["unit"]) == "Pal"
            and "Palmitic acid" in str(pal_plan.iloc[-1]["protected_reagent"])
        ),
        "terminal_note_not_filtered": not position_rules.is_fmoc_removal({
            "Unit name": "Acetic anhydride (Ac2O)",
            "Phase": "Last / N-term cap",
            "Note": "Flow: final Fmoc removal then terminal chemical reaction",
        }),
    }
    return {
        "app_version": "V7.0.0",
        "build_revision": BUILD_REVISION,
        "checks": checks,
        "ok": all(checks.values()),
    }


def write_report() -> int:
    report = run()
    destination = Path(os.environ.get(
        "SPPS_PLANNER_SELFTEST_OUTPUT", "runtime_selftest.json",
    ))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return 0 if report["ok"] else 1


__all__ = ["BUILD_REVISION", "run", "write_report"]
