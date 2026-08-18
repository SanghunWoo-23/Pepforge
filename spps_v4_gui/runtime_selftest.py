"""Headless single-plan functional proof for the packaged Pepforge SPPS UI.

Batch and LOT workflows are intentionally outside the Pepforge integration.
This check exercises only the parser, chemistry-aware plan generator, process
times, and the confirmed cleavage contract exposed by the integrated UI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BUILD_REVISION = "2026-08-13-pepforge-spps-v4-r2"


def run() -> dict[str, Any]:
    from spps_planner.engine import (
        PlanInput,
        generate_cleavage_cocktail,
        generate_step_reagent_plan,
    )
    from spps_planner.parser import parse_sequence
    from spps_planner.version import VERSION_NUMBER
    from spps_v4_gui import catalogs, position_rules

    parsed = parse_sequence("[His6]-[FITC]-ACD-[PEG4]-NH2")
    ac_plan = generate_step_reagent_plan(PlanInput(sequence="Ac-AAAA-NH2"))
    pal_plan = generate_step_reagent_plan(PlanInput(sequence="Pal-EEMQRR-NH2"))
    loading_base = generate_step_reagent_plan(PlanInput(
        sequence="AEK", resin="2-CTC", apply_resin_loading=True,
        loading_aa_eq=2, loading_diea_eq=4,
    )).iloc[0]
    loading_timed = generate_step_reagent_plan(PlanInput(
        sequence="AEK", resin="2-CTC", apply_resin_loading=True,
        loading_aa_eq=2, loading_diea_eq=4, loading_time_h=4,
    )).iloc[0]
    cleavage = generate_cleavage_cocktail(PlanInput(
        sequence="Ac-EEMQRR-NH2", scale_mmol=0.5,
    ))
    cocktail = {
        str(row["component"]): float(row["volume_mL"])
        for _, row in cleavage.iterrows()
        if str(row["component"]) != "Total cocktail"
    }
    checks = {
        "version": VERSION_NUMBER == "4.0.0",
        "protected_aa_catalog": catalogs.UNIT_VALUES[1] == "Fmoc-Ala-OH",
        "parser_tokens": parsed.core_tokens == ["FITC", "A", "C", "D", "PEG4"],
        "chemical_tag_linker_parser": parsed.core_tokens == ["FITC", "A", "C", "D", "PEG4"],
        "terminal_ac_plan": (
            len(ac_plan) == 5
            and str(ac_plan.iloc[-1]["unit"]) == "Ac"
            and "Acetic anhydride" in str(ac_plan.iloc[-1]["protected_reagent"])
        ),
        "terminal_pal_plan": (
            len(pal_plan) == 7
            and str(pal_plan.iloc[-1]["unit"]) == "Pal"
            and "Palmitic acid" in str(pal_plan.iloc[-1]["protected_reagent"])
        ),
        "loading_time_is_non_stoichiometric": (
            loading_base["planned_reagent_mmol"] == loading_timed["planned_reagent_mmol"]
            and "time=4 h" in str(loading_timed["note"])
        ),
        "confirmed_ac_eemqrr_cleavage": (
            set(cocktail) == {"TFA", "DW / water"}
            and abs(cocktail["TFA"] - 14.25) < 1e-9
            and abs(cocktail["DW / water"] - 0.75) < 1e-9
        ),
        "terminal_note_not_filtered": not position_rules.is_fmoc_removal({
            "Unit name": "Acetic anhydride (Ac2O) for N-terminal acetylation",
            "Phase": "Last / N-term cap",
            "Note": "Flow: final Fmoc removal then terminal chemical reaction",
        }),
    }
    return {
        "app_version": "V4.0.0",
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
