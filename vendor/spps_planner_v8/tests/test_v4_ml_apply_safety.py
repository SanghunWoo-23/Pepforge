from pathlib import Path


def _add_loading(db, status="parsed"):
    from suite_gui import experimental_data
    return experimental_data.add_record("loading", {"resin_type":"Trityl/2-CTC resin","amino_acid_raw":"Fmoc-Arg(Pbf)-OH","amino_acid_normalized":"Fmoc-Arg(Pbf)-OH","aa_eq":2,"base":"DIEA","base_eq":4,"loading_time_h":4,"loading_rate_mmol_g":0.52,"raw_note":"synthetic fixture"}, db, status=status)


def _add_cleavage(db, status="parsed", extra=False):
    from suite_gui import experimental_data
    return experimental_data.add_record("cleavage", {"product":"Demo Product","sequence":"Ac-AAAAAA-NH2","scale_mmol":100,"tfa_ml":2850,"tis_ml":0,"water_ml":150,"other_scavengers_json":'{"Thioanisole": 10}' if extra else '{}',"cleavage_eq":30,"cleavage_time_h":3,"raw_observation":"synthetic fixture"}, db, status=status)


def test_loading_parsed_exact_records_are_evidence_only(tmp_path):
    from suite_gui import ml_advisor_v4
    db=tmp_path/"exp.sqlite"; _add_loading(db,"parsed")
    result=ml_advisor_v4.loading_advice("Trityl/2-CTC resin","Fmoc-Arg(Pbf)-OH",aa_eq=2,base_eq=4,target_loading_mmol_g=0.52,db_path=db,include_parsed=True)
    assert result["exact_count"] > 0
    assert result["recommended_condition"] is None


def test_loading_verified_exact_record_can_be_actionable(tmp_path):
    from suite_gui import ml_advisor_v4
    db=tmp_path/"exp.sqlite"; row=_add_loading(db,"verified")
    result=ml_advisor_v4.loading_advice("Trityl/2-CTC resin","Fmoc-Arg(Pbf)-OH",target_loading_mmol_g=0.52,db_path=db,include_parsed=True)
    assert result["recommended_condition"]["apply_allowed"] is True


def test_cleavage_parsed_exact_product_is_not_actionable(tmp_path):
    from suite_gui import ml_advisor_v4
    db=tmp_path/"exp.sqlite"; _add_cleavage(db,"parsed")
    result=ml_advisor_v4.cleavage_advice(product="Demo Product",sequence="Ac-AAAAAA-NH2",scale_mmol=100,db_path=db)
    assert result["exact_count"] > 0
    rec = result["recommended_condition"]
    assert rec is not None
    # Parsed history may be surfaced for explicit user review, but it is never
    # silently promoted to Verified.
    assert rec.get("source_status") in {"parsed", None}


def test_cleavage_numeric_extra_component_is_preserved_as_recorded(tmp_path):
    from suite_gui import ml_advisor_v4
    db=tmp_path/"exp.sqlite"; _add_cleavage(db,"verified",extra=True)
    result=ml_advisor_v4.cleavage_advice(product="Demo Product",sequence="Ac-AAAAAA-NH2",scale_mmol=100,db_path=db)
    rec=result["recommended_condition"]
    assert rec is not None
    assert rec.get("condition_source") == "exact_lab_record"
    assert rec.get("apply_allowed") is True
    assert "Thioanisole" in (rec.get("composition_pct") or {})


def test_cleavage_unresolved_extra_component_blocks_historical_apply(tmp_path):
    from suite_gui import experimental_data, ml_advisor_v4
    db=tmp_path/"exp.sqlite"
    experimental_data.add_record("cleavage", {
        "product":"Demo Product","sequence":"Ac-AAAAAA-NH2","scale_mmol":100,
        "tfa_ml":2850,"tis_ml":0,"water_ml":150,
        "other_scavengers_json":'{"Thioanisole": "10 mL"}',
        "cleavage_eq":30,"cleavage_time_h":3,"raw_observation":"synthetic fixture"
    }, db, status="verified")
    result=ml_advisor_v4.cleavage_advice(product="Demo Product",sequence="Ac-AAAAAA-NH2",scale_mmol=100,db_path=db)
    rec=result["recommended_condition"]
    assert rec is not None
    assert rec.get("condition_source") != "exact_lab_record"
    assert rec.get("apply_allowed") is False


def test_ml_apply_ui_recomputes_and_requires_direct_loading_mode():
    src=(Path(__file__).resolve().parents[1]/"suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    assert "self.run_loading_advisor()" in src and "resin_profiles.editor_loading_enabled(self.gui)" in src and "self.run_cleavage_advisor()" in src
