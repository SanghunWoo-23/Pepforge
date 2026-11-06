from types import SimpleNamespace

from suite_gui import condition_optimizer_v4, experimental_data


def _reviewed_item(project, compound, reagent="DIC", catalyst="HOBt", base="", unit_mmol=5.0, r1_mmol=5.0, r2_mmol=5.0, time_h="0.5"):
    return {
        "work_item_id": project,
        "project": project,
        "peptide": project,
        "sequence": "AAAA",
        "resin": "Rink Amide AM",
        "scale": "1",
        "coupling_eq": "5",
        "coupling_repeats": "1",
        "coupling_time_h": time_h,
        "default_reagent": reagent,
        "default_reagent_eq": "5",
        "default_catalyst": catalyst,
        "default_catalyst_eq": "5",
        "default_base": base,
        "default_base_eq": "0",
        "default_coupling_solution_solvent": "DMF",
        "selected_plan_rows": [{
            "Unit name": compound, "Unit mmol": unit_mmol, "Reagent 1": reagent,
            "R1 mmol": r1_mmol, "Reagent 2 / catalyst": catalyst,
            "R2 mmol": r2_mmol, "Base": base, "Base mmol": "",
            "Coupling solvent": "DMF", "Solvent mL": 5, "Repeat": 1, "Note": "coupling",
        }],
        "ml_review": {"revision": 1, "versions": [], "current": {
            "reviewed": True, "included": True, "failure_flag": False,
            "actual_purity_percent": 90.0, "actual_yield_percent": 70.0,
        }},
    }


def test_coupling_exact_compound_repeated_condition_becomes_consensus():
    history = [
        _reviewed_item("P1", "Fmoc-Lys(Boc)-OH"),
        _reviewed_item("P2", "Fmoc-Lys(Boc)-OH"),
    ]
    current = {
        "sequence": "AK", "resin": "Rink Amide AM", "scale": "1",
        "selected_plan_rows": [{"Unit name": "Fmoc-Lys(Boc)-OH", "Note": "coupling"}],
    }
    result = condition_optimizer_v4.coupling_advice([*history, current], current)
    unit = result["unit_recommendations"][0]
    assert unit["recommendation_kind"] == "HISTORICAL CONSENSUS"
    assert unit["evidence_count"] == 2
    assert unit["condition"]["default_reagent"] == "DIC"
    assert unit["condition"]["default_catalyst"] == "HOBt"
    assert unit["condition"]["default_reagent_eq"] == 5.0
    assert unit["condition"]["coupling_time_h"] == 0.5
    assert result["recommended_condition"]["apply_allowed"] is True


def test_coupling_single_occurrence_does_not_become_exact_consensus():
    history = [_reviewed_item("P1", "Fmoc-Lys(Boc)-OH")]
    current = {
        "sequence": "AK", "resin": "Rink Amide AM", "scale": "1",
        "selected_plan_rows": [{"Unit name": "Fmoc-Lys(Boc)-OH", "Note": "coupling"}],
    }
    result = condition_optimizer_v4.coupling_advice([*history, current], current)
    assert result["unit_recommendations"][0]["apply_allowed"] is False



def test_coupling_duplicate_positions_in_one_synthesis_do_not_fake_consensus():
    item = _reviewed_item("P1", "Fmoc-Lys(Boc)-OH")
    item["selected_plan_rows"] = item["selected_plan_rows"] * 2
    current = {
        "sequence": "AKK", "resin": "Rink Amide AM", "scale": "1",
        "selected_plan_rows": [{"Unit name": "Fmoc-Lys(Boc)-OH", "Note": "coupling"}],
    }
    result = condition_optimizer_v4.coupling_advice([item, current], current)
    unit = result["unit_recommendations"][0]
    assert unit["apply_allowed"] is False
    assert unit["observation_count"] == 2
    assert unit["independent_experiment_count"] == 1


def test_coupling_consensus_reports_observations_and_independent_syntheses_separately():
    p1 = _reviewed_item("P1", "Fmoc-Lys(Boc)-OH")
    p2 = _reviewed_item("P2", "Fmoc-Lys(Boc)-OH")
    p1["selected_plan_rows"] = p1["selected_plan_rows"] * 2
    p2["selected_plan_rows"] = p2["selected_plan_rows"] * 2
    current = {
        "sequence": "AKK", "resin": "Rink Amide AM", "scale": "1",
        "selected_plan_rows": [{"Unit name": "Fmoc-Lys(Boc)-OH", "Note": "coupling"}],
    }
    result = condition_optimizer_v4.coupling_advice([p1, p2, current], current)
    unit = result["unit_recommendations"][0]
    assert unit["recommendation_kind"] == "HISTORICAL CONSENSUS"
    assert unit["observation_count"] == 4
    assert unit["independent_experiment_count"] == 2
    assert unit["evidence_count"] == 2

def test_operator_loading_and_cleavage_records_can_be_added_directly(tmp_path):
    db = tmp_path / "experimental.sqlite"
    loading = experimental_data.add_record("loading", {
        "resin_type": "2-CTC", "amino_acid_raw": "Fmoc-Lys(Boc)-OH",
        "aa_eq": 0.5, "base": "DIEA", "base_eq": 2.0,
        "loading_time_h": 4.0, "loading_rate_mmol_g": 0.51,
    }, db, status="verified")
    cleavage = experimental_data.add_record("cleavage", {
        "product": "Test", "sequence": "Ac-AAAA-NH2", "scale_mmol": 1.0,
        "tfa_ml": 28.5, "water_ml": 1.5, "tis_ml": 0.0,
        "cleavage_eq": 30.0, "cleavage_time_h": 3.0,
    }, db, status="verified")
    assert loading["status"] == "verified"
    assert loading["resin_type"] == "Trityl/2-CTC resin"
    assert cleavage["status"] == "verified"
    assert len(experimental_data.list_records("loading", db)) == 1
    assert len(experimental_data.list_records("cleavage", db)) == 1
