from pathlib import Path
from suite_gui import experimental_data, ml_advisor_v4


def _loading(db, eq, beq, value, status="parsed"):
    return experimental_data.add_record("loading", {"resin_type":"Trityl/2-CTC resin","amino_acid_raw":"Fmoc-Arg(Pbf)-OH","amino_acid_normalized":"Fmoc-Arg(Pbf)-OH","aa_eq":eq,"base":"DIEA","base_eq":beq,"loading_time_h":4,"loading_rate_mmol_g":value,"raw_note":"synthetic"}, db, status=status)


def _cleavage(db, product="Demo Product", sequence="Ac-AAAAAA-NH2", status="parsed"):
    return experimental_data.add_record("cleavage", {"product":product,"sequence":sequence,"scale_mmol":100,"tfa_ml":2850,"tis_ml":0,"water_ml":150,"other_scavengers_json":"{}","cleavage_eq":30,"cleavage_time_h":3,"raw_observation":"synthetic"}, db, status=status)


def test_loading_recommendation_uses_only_observed_exact_condition(tmp_path):
    db=tmp_path/"exp.sqlite"; _loading(db,1,3,0.4); _loading(db,2,4,0.55)
    result=ml_advisor_v4.loading_recommendation("Trityl/2-CTC resin","Fmoc-Arg(Pbf)-OH",target_loading_mmol_g=0.4,db_path=db,include_parsed=True)
    rec=result["recommended_condition"]; assert (float(rec["aa_eq"]),float(rec["base_eq"])) in {(1.0,3.0),(2.0,4.0)}


def test_loading_recommendation_does_not_apply_undemonstrated_target(tmp_path):
    db=tmp_path/"exp.sqlite"; _loading(db,1,3,0.4); _loading(db,2,4,0.55)
    result=ml_advisor_v4.loading_recommendation("Trityl/2-CTC resin","Fmoc-Arg(Pbf)-OH",target_loading_mmol_g=99,db_path=db,include_parsed=True)
    assert result["recommended_condition"] is not None and result["recommended_condition"]["apply_allowed"] is False


def test_cleavage_recommendation_is_sequence_first_and_keeps_one_record_cocktail(tmp_path):
    db=tmp_path/"exp.sqlite"; _cleavage(db)
    result=ml_advisor_v4.cleavage_recommendation(product="Demo Product",sequence="Ac-AAAAAA-NH2",resin="Rink Amide",scale_mmol=500,db_path=db,include_parsed=True)
    rec=result["recommended_condition"]; assert rec is not None and rec["sequence"]=="Ac-AAAAAA-NH2" and rec["composition_pct"]=={"TFA":95.0,"Water":5.0}


def test_cleavage_recommendation_does_not_use_stale_product_for_different_sequence(tmp_path):
    db=tmp_path/"exp.sqlite"; _cleavage(db)
    result=ml_advisor_v4.cleavage_recommendation(product="Demo Product",sequence="Ac-GGGGGG-NH2",resin="Rink Amide",scale_mmol=1,db_path=db,include_parsed=True)
    assert result["recommended_condition"].get("condition_source") != "recommended_exact_sequence_record"


def test_optimizer_ui_has_separate_recommend_apply_paths():
    src=(Path(__file__).resolve().parents[1]/"suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    assert "Apply Loading Rec" in src and "Apply Cleavage Rec" in src and "recommend_loading(" in src and "recommend_cleavage(" in src



def test_loading_lookup_is_case_insensitive_for_residue_and_bottle_name(tmp_path):
    db=tmp_path/"exp.sqlite"; _loading(db,1,3,0.4); _loading(db,2,4,0.55)
    lower_residue=ml_advisor_v4.loading_recommendation("2-ctc","r",target_loading_mmol_g=0.4,db_path=db,include_parsed=True)
    lower_bottle=ml_advisor_v4.loading_recommendation("TRITYL/2-CTC RESIN","fmoc-arg(pbf)-oh",target_loading_mmol_g=0.4,db_path=db,include_parsed=True)
    assert lower_residue["recommended_condition"] is not None
    assert lower_bottle["recommended_condition"] is not None
